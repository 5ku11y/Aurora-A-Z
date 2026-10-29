#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_moov9.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

old_struct = r'''struct remote_file {
    char url[SP_URL_BYTES];
    CURL *curl;
    uint8_t *cache;
    size_t cache_capacity;
    size_t cache_length;
    int64_t cache_start;
    int64_t position;
    int64_t size;
    long last_http;
    char curl_error[CURL_ERROR_SIZE];
    char error[256];
};'''
new_struct = r'''struct remote_file {
    char url[SP_URL_BYTES];
    CURL *curl;
    uint8_t *cache;
    size_t cache_capacity;
    size_t cache_length;
    size_t range_chunk;
    int64_t cache_start;
    int64_t position;
    int64_t size;
    long last_http;
    unsigned fill_count;
    unsigned read_calls;
    unsigned seek_calls;
    int64_t last_fill_start;
    int64_t last_fill_end;
    int64_t last_seek_target;
    int last_seek_whence;
    char curl_error[CURL_ERROR_SIZE];
    char error[256];
};'''
if old_struct not in src:
    raise SystemExit('remote_file struct marker missing')
src = src.replace(old_struct, new_struct, 1)

old_fill_head = r'''    end = start + (int64_t)remote->cache_capacity - 1;
    if (end >= remote->size) end = remote->size - 1;
    snprintf(range, sizeof(range), "%" PRId64 "-%" PRId64, start, end);'''
new_fill_head = r'''    {
        size_t chunk = remote->range_chunk != 0 ? remote->range_chunk : REMOTE_CACHE_BYTES;
        if (chunk > remote->cache_capacity) chunk = remote->cache_capacity;
        end = start + (int64_t)chunk - 1;
    }
    if (end >= remote->size) end = remote->size - 1;
    remote->fill_count++;
    remote->last_fill_start = start;
    remote->last_fill_end = end;
    snprintf(range, sizeof(range), "%" PRId64 "-%" PRId64, start, end);'''
if old_fill_head not in src:
    raise SystemExit('remote_fill range block missing')
src = src.replace(old_fill_head, new_fill_head, 1)

old_read = r'''    if (remote == NULL || buffer == NULL || buffer_size <= 0) return AVERROR(EINVAL);
    while (copied < buffer_size && remote->position < remote->size) {'''
new_read = r'''    if (remote == NULL || buffer == NULL || buffer_size <= 0) return AVERROR(EINVAL);
    remote->read_calls++;
    while (copied < buffer_size && remote->position < remote->size) {'''
if old_read not in src:
    raise SystemExit('avio read marker missing')
src = src.replace(old_read, new_read, 1)

old_seek_tail = r'''    if (target < 0 || target > remote->size) return AVERROR(EINVAL);
    remote->position = target;
    return target;'''
new_seek_tail = r'''    if (target < 0 || target > remote->size) return AVERROR(EINVAL);
    remote->seek_calls++;
    remote->last_seek_whence = base;
    remote->last_seek_target = target;
    remote->position = target;
    return target;'''
if old_seek_tail not in src:
    raise SystemExit('avio seek marker missing')
src = src.replace(old_seek_tail, new_seek_tail, 1)

helper_marker = r'''static int remote_open(struct remote_file *remote, const char *url)
{'''
if helper_marker not in src:
    raise SystemExit('remote_open marker missing')
helper = r'''static uint32_t sp_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static uint64_t sp_be64(const uint8_t *p)
{
    return ((uint64_t)sp_be32(p) << 32) | (uint64_t)sp_be32(p + 4);
}

static int remote_prefetch_front_moov(struct remote_file *remote)
{
    uint64_t first_size, moov_size, target;
    size_t off, header;
    uint8_t *grown;
    char range[96];
    CURLcode result;
    long http = 0;

    if (remote == NULL || remote->cache == NULL || remote->cache_length < 48u)
        return 0;

    first_size = sp_be32(remote->cache);
    header = 8u;
    if (first_size == 1u) {
        if (remote->cache_length < 16u) return 0;
        first_size = sp_be64(remote->cache + 8u);
        header = 16u;
    }
    if (first_size < header || first_size > remote->cache_length - 8u)
        return 0;
    off = (size_t)first_size;
    if (memcmp(remote->cache + off + 4u, "moov", 4u) != 0)
        return 0;

    moov_size = sp_be32(remote->cache + off);
    header = 8u;
    if (moov_size == 1u) {
        if (off + 16u > remote->cache_length) return 0;
        moov_size = sp_be64(remote->cache + off + 8u);
        header = 16u;
    }
    if (moov_size < header) return 0;
    target = (uint64_t)off + moov_size;
    if (target <= remote->cache_length) return 0;
    if (target > (32u * 1024u * 1024u) || target > (uint64_t)remote->size)
        return 0;

    grown = realloc(remote->cache, (size_t)target);
    if (grown == NULL) {
        snprintf(remote->error, sizeof(remote->error), "moov cache realloc %u failed", (unsigned)target);
        return -1;
    }
    remote->cache = grown;
    remote->cache_capacity = (size_t)target;
    remote->cache_length = 0;
    remote->curl_error[0] = '\0';
    snprintf(range, sizeof(range), "0-%" PRIu64, target - 1u);
    curl_easy_reset(remote->curl);
    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_RANGE, range);
    curl_easy_setopt(remote->curl, CURLOPT_WRITEFUNCTION, remote_write);
    curl_easy_setopt(remote->curl, CURLOPT_WRITEDATA, remote);
    curl_easy_setopt(remote->curl, CURLOPT_ERRORBUFFER, remote->curl_error);
    result = curl_easy_perform(remote->curl);
    (void)curl_easy_getinfo(remote->curl, CURLINFO_RESPONSE_CODE, &http);
    remote->last_http = http;
    if (result != CURLE_OK || http != 206) {
        snprintf(remote->error, sizeof(remote->error), "moov range curl=%d HTTP=%ld %.100s",
            (int)result, http, remote->curl_error);
        return -1;
    }
    if (remote->cache_length < (size_t)target) {
        snprintf(remote->error, sizeof(remote->error), "moov short %u/%u",
            (unsigned)remote->cache_length, (unsigned)target);
        return -1;
    }
    remote->cache_start = 0;
    remote->position = 0;
    return 1;
}

'''
src = src.replace(helper_marker, helper + helper_marker, 1)

old_cache_init = r'''    remote->cache_capacity = REMOTE_CACHE_BYTES;
    remote->cache = malloc(remote->cache_capacity);'''
new_cache_init = r'''    remote->cache_capacity = REMOTE_CACHE_BYTES;
    remote->range_chunk = REMOTE_CACHE_BYTES;
    remote->last_fill_start = -1;
    remote->last_fill_end = -1;
    remote->last_seek_target = -1;
    remote->cache = malloc(remote->cache_capacity);'''
if old_cache_init not in src:
    raise SystemExit('remote cache init marker missing')
src = src.replace(old_cache_init, new_cache_init, 1)

old_open_tail = r'''    remote->size = total;
    remote->cache_start = 0;
    remote->position = 0;
    return 0;'''
new_open_tail = r'''    remote->size = total;
    remote->cache_start = 0;
    remote->position = 0;
    if (remote_prefetch_front_moov(remote) < 0) return -1;
    return 0;'''
if old_open_tail not in src:
    raise SystemExit('remote_open success tail missing')
src = src.replace(old_open_tail, new_open_tail, 1)

old_open_input = r'''    format->pb = avio;
    format->flags |= AVFMT_FLAG_CUSTOM_IO;
    format->probesize = 2 * 1024 * 1024;
    format->max_analyze_duration = 5LL * AV_TIME_BASE;
    result = avformat_open_input(&format, NULL, NULL, NULL);
    if (result < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size, "MP4 open failed: %s; remote=%.120s", fferr, remote.error);
        goto fail;
    }'''
new_open_input = r'''    format->pb = avio;
    format->flags |= AVFMT_FLAG_CUSTOM_IO;
    avio->seekable = AVIO_SEEKABLE_NORMAL;
    format->probesize = 24 * 1024 * 1024;
    format->max_analyze_duration = 5LL * AV_TIME_BASE;
    {
        const AVInputFormat *mov_input = av_find_input_format("mov");
        if (mov_input == NULL) {
            snprintf(error, error_size, "MOV demuxer lookup failed");
            goto fail;
        }
        result = avformat_open_input(&format, NULL, mov_input, NULL);
    }
    if (result < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size,
            "MP4 OPEN: %s\nSIZE=%" PRId64 " POS=%" PRId64 " CACHE=%" PRId64 "+%u\n"
            "FILL=%u LAST=%" PRId64 "-%" PRId64 " HTTP=%ld\n"
            "READ=%u SEEK=%u W=%d T=%" PRId64 "\nREMOTE=%.100s",
            fferr, remote.size, remote.position, remote.cache_start, (unsigned)remote.cache_length,
            remote.fill_count, remote.last_fill_start, remote.last_fill_end, remote.last_http,
            remote.read_calls, remote.seek_calls, remote.last_seek_whence, remote.last_seek_target,
            remote.error);
        goto fail;
    }'''
if old_open_input not in src:
    raise SystemExit('FFmpeg open block missing')
src = src.replace(old_open_input, new_open_input, 1)

src = src.replace('SPELUNKR360 V7A.8 - LIVE VIDEO FRAME PROBE', 'SPELUNKR360 V7A.9 - LIVE VIDEO FRAME PROBE')
src = src.replace('V7A.8 - B/BACK/START RETURNS TO AURORA', 'V7A.9 - B/BACK/START RETURNS TO AURORA')

for needle in ('SPELUNKR360 V7A.9 - LIVE VIDEO FRAME PROBE', 'remote_prefetch_front_moov', 'MP4 OPEN:', 'av_find_input_format("mov")'):
    if needle not in src:
        raise SystemExit(f'V7A.9 marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7A.9 front-moov prefetch, forced MOV demuxer, and AVIO trace")
