#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7e.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7E: eliminate the long synchronous Archive.org range-refill pause seen by
# V7D hardware.  Keep the proven decoder/audio-master path, but prefetch the
# next sequential media range on a second xsdk pthread while the current cache
# is being consumed.  At the cache boundary playback swaps buffers instead of
# starting a fresh blocking HTTPS request.

if '#include <pthread.h>' not in src:
    src = src.replace('#include <inttypes.h>\n', '#include <inttypes.h>\n#include <pthread.h>\n', 1)

src = src.replace('SPELUNKR360 V7D - PLAYBACK QUALITY + LONG-RUN STABILITY',
                  'SPELUNKR360 V7E - ASYNC PREFETCH + LONG-RUN STABILITY')
src = src.replace('SPELUNKR360 V7D - 60 SECOND STABILITY PLAYBACK',
                  'SPELUNKR360 V7E - ASYNC PREFETCH STABILITY PLAYBACK')
src = src.replace('V7D - B/BACK/START RETURNS TO AURORA',
                  'V7E - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7D soak failed:', 'V7E soak failed:')
src = src.replace('Spelunkr360 V7D PASS:', 'Spelunkr360 V7E PASS:')

old_struct_tail = '''    char curl_error[CURL_ERROR_SIZE];\n    char error[256];\n};'''
new_struct_tail = '''    char curl_error[CURL_ERROR_SIZE];\n    char error[256];\n\n    /* V7E sequential double buffer.  The worker owns prefetch_cache while\n     * prefetch_active is true; the playback thread only consumes cache. */\n    uint8_t *prefetch_cache;\n    size_t prefetch_capacity;\n    size_t prefetch_length;\n    int64_t prefetch_start;\n    pthread_t prefetch_thread;\n    bool prefetch_active;\n    bool prefetch_enabled;\n    volatile bool prefetch_done;\n    int prefetch_status;\n    long prefetch_http;\n    unsigned prefetch_started;\n    unsigned prefetch_hits;\n    unsigned prefetch_waits;\n    unsigned prefetch_fallbacks;\n    char prefetch_error[128];\n};'''
if old_struct_tail not in src:
    raise SystemExit('V7E remote_file struct marker missing')
src = src.replace(old_struct_tail, new_struct_tail, 1)

remote_open_marker = 'static int remote_open(struct remote_file *remote, const char *url)\n{'
if remote_open_marker not in src:
    raise SystemExit('V7E remote_open marker missing')

helpers = r'''static size_t v7e_prefetch_write(char *data, size_t size, size_t count, void *user)
{
    struct remote_file *remote = user;
    const size_t length = size * count;
    if (remote == NULL || remote->prefetch_cache == NULL ||
        length > remote->prefetch_capacity - remote->prefetch_length)
        return 0;
    memcpy(remote->prefetch_cache + remote->prefetch_length, data, length);
    remote->prefetch_length += length;
    return length;
}

static void *v7e_prefetch_worker(void *context)
{
    struct remote_file *remote = context;
    CURL *curl = NULL;
    CURLcode result = CURLE_FAILED_INIT;
    long http = 0;
    char range[96];
    int64_t end;
    size_t wanted;

    if (remote == NULL || remote->prefetch_start < 0 ||
        remote->prefetch_start >= remote->size || remote->prefetch_capacity == 0) {
        if (remote != NULL) {
            remote->prefetch_status = -1;
            remote->prefetch_done = true;
        }
        return NULL;
    }

    wanted = remote->range_chunk != 0 ? remote->range_chunk : REMOTE_CACHE_BYTES;
    if (wanted > remote->prefetch_capacity) wanted = remote->prefetch_capacity;
    end = remote->prefetch_start + (int64_t)wanted - 1;
    if (end >= remote->size) end = remote->size - 1;
    wanted = (size_t)(end - remote->prefetch_start + 1);
    snprintf(range, sizeof(range), "%" PRId64 "-%" PRId64, remote->prefetch_start, end);

    remote->prefetch_length = 0;
    remote->prefetch_http = 0;
    remote->prefetch_status = -1;
    remote->prefetch_error[0] = '\0';
    curl = curl_easy_init();
    if (curl == NULL) {
        snprintf(remote->prefetch_error, sizeof(remote->prefetch_error), "curl init failed");
        remote->prefetch_done = true;
        return NULL;
    }

    set_common_curl(curl, remote->url);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 60000L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 20L);
    curl_easy_setopt(curl, CURLOPT_BUFFERSIZE, 131072L);
    curl_easy_setopt(curl, CURLOPT_RANGE, range);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, v7e_prefetch_write);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, remote);
    curl_easy_setopt(curl, CURLOPT_ERRORBUFFER, remote->prefetch_error);
    result = curl_easy_perform(curl);
    (void)curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http);
    remote->prefetch_http = http;
    curl_easy_cleanup(curl);

    if (result == CURLE_OK && http == 206 && remote->prefetch_length == wanted) {
        remote->prefetch_status = 0;
    } else {
        if (remote->prefetch_error[0] == '\0')
            snprintf(remote->prefetch_error, sizeof(remote->prefetch_error),
                "curl=%d HTTP=%ld got=%u/%u", (int)result, http,
                (unsigned)remote->prefetch_length, (unsigned)wanted);
        remote->prefetch_status = -1;
    }
    remote->prefetch_done = true;
    return NULL;
}

static int v7e_prefetch_start(struct remote_file *remote)
{
    int64_t start;
    size_t wanted;
    uint8_t *grown;
    if (remote == NULL || !remote->prefetch_enabled || remote->prefetch_active ||
        remote->cache_start < 0 || remote->cache_length == 0)
        return 0;
    start = remote->cache_start + (int64_t)remote->cache_length;
    if (start < 0 || start >= remote->size) return 0;
    wanted = remote->range_chunk != 0 ? remote->range_chunk : REMOTE_CACHE_BYTES;
    if ((int64_t)wanted > remote->size - start) wanted = (size_t)(remote->size - start);
    if (wanted == 0) return 0;
    if (remote->prefetch_capacity < wanted) {
        grown = realloc(remote->prefetch_cache, wanted);
        if (grown == NULL) return -1;
        remote->prefetch_cache = grown;
        remote->prefetch_capacity = wanted;
    }
    remote->prefetch_start = start;
    remote->prefetch_length = 0;
    remote->prefetch_status = -1;
    remote->prefetch_done = false;
    remote->prefetch_active = true;
    remote->prefetch_started++;
    if (pthread_create(&remote->prefetch_thread, NULL, v7e_prefetch_worker, remote) != 0) {
        remote->prefetch_active = false;
        remote->prefetch_done = true;
        return -1;
    }
    return 0;
}

/* 1 = promoted prefetched bytes, 0 = no matching prefetch, -1 = prefetch failed. */
static int v7e_prefetch_promote(struct remote_file *remote, int64_t position)
{
    uint8_t *old_cache;
    size_t old_capacity;
    if (remote == NULL || !remote->prefetch_active) return 0;
    if (remote->prefetch_start != position) {
        (void)pthread_join(remote->prefetch_thread, NULL);
        remote->prefetch_active = false;
        remote->prefetch_done = true;
        return 0;
    }
    if (!remote->prefetch_done) remote->prefetch_waits++;
    (void)pthread_join(remote->prefetch_thread, NULL);
    remote->prefetch_active = false;
    if (remote->prefetch_status != 0 || remote->prefetch_length == 0) return -1;

    old_cache = remote->cache;
    old_capacity = remote->cache_capacity;
    remote->cache = remote->prefetch_cache;
    remote->cache_capacity = remote->prefetch_capacity;
    remote->cache_length = remote->prefetch_length;
    remote->cache_start = remote->prefetch_start;
    remote->last_http = remote->prefetch_http;
    remote->prefetch_cache = old_cache;
    remote->prefetch_capacity = old_capacity;
    remote->prefetch_length = 0;
    remote->prefetch_hits++;
    (void)v7e_prefetch_start(remote);
    return 1;
}

'''
src = src.replace(remote_open_marker, helpers + remote_open_marker, 1)

old_read_fill = '''        if (remote->cache_start < 0 || remote->position < remote->cache_start || remote->position >= cache_end) {\n            if (remote_fill(remote, remote->position) != 0)\n                return copied > 0 ? copied : AVERROR(EIO);\n            cache_end = remote->cache_start + (int64_t)remote->cache_length;\n        }'''
new_read_fill = '''        if (remote->cache_start < 0 || remote->position < remote->cache_start || remote->position >= cache_end) {\n            int promoted = v7e_prefetch_promote(remote, remote->position);\n            if (promoted <= 0) {\n                if (promoted < 0) remote->prefetch_fallbacks++;\n                if (remote_fill(remote, remote->position) != 0)\n                    return copied > 0 ? copied : AVERROR(EIO);\n                (void)v7e_prefetch_start(remote);\n            }\n            cache_end = remote->cache_start + (int64_t)remote->cache_length;\n        }'''
if old_read_fill not in src:
    raise SystemExit('V7E avio refill marker missing')
src = src.replace(old_read_fill, new_read_fill, 1)

old_close = '''static void remote_close(struct remote_file *remote)\n{\n    if (remote == NULL) return;\n    if (remote->curl != NULL) curl_easy_cleanup(remote->curl);\n    free(remote->cache);\n    memset(remote, 0, sizeof(*remote));\n}'''
new_close = '''static void remote_close(struct remote_file *remote)\n{\n    if (remote == NULL) return;\n    if (remote->prefetch_active) {\n        (void)pthread_join(remote->prefetch_thread, NULL);\n        remote->prefetch_active = false;\n    }\n    if (remote->curl != NULL) curl_easy_cleanup(remote->curl);\n    free(remote->prefetch_cache);\n    free(remote->cache);\n    memset(remote, 0, sizeof(*remote));\n}'''
if old_close not in src:
    raise SystemExit('V7E remote_close marker missing')
src = src.replace(old_close, new_close, 1)

old_seek_ready = '''    avcodec_flush_buffers(video_decoder);\n    avcodec_flush_buffers(audio_decoder);\n    format_hms(target_ms, target_text, sizeof(target_text));'''
new_seek_ready = '''    avcodec_flush_buffers(video_decoder);\n    avcodec_flush_buffers(audio_decoder);\n    /* The seek has synchronously filled the current 4 MiB media window.\n     * Start the following window now so HTTPS runs in parallel with decode. */\n    remote.prefetch_enabled = true;\n    if (v7e_prefetch_start(&remote) != 0)\n        xsdk_log_write("V7E prefetch start failed; synchronous fallback remains available");\n    format_hms(target_ms, target_text, sizeof(target_text));'''
if old_seek_ready not in src:
    raise SystemExit('V7E post-seek marker missing')
src = src.replace(old_seek_ready, new_seek_ready, 1)

old_overlay = (
    '                    "AUDIO %s %dHz %dch | PLAYED %u SILENT %u | RANGE HTTP %ld | SOAK 60s\\n"\\n'
    '                    "B/BACK/START: RETURN TO AURORA",'
)
new_overlay = (
    '                    "AUDIO %s %dHz %dch | PLAYED %u SILENT %u | RANGE HTTP %ld | SOAK 60s\\n"\\n'
    '                    "PREFETCH HIT %u WAIT %u START %u FALLBACK %u\\n"\\n'
    '                    "B/BACK/START: RETURN TO AURORA",'
)
if old_overlay not in src:
    raise SystemExit('V7E overlay format marker missing')
src = src.replace(old_overlay, new_overlay, 1)
old_overlay_args = '''                    audio_stats.played, audio_stats.silent, remote.last_http);'''
new_overlay_args = '''                    audio_stats.played, audio_stats.silent, remote.last_http,\n                    remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_started, remote.prefetch_fallbacks);'''
if old_overlay_args not in src:
    raise SystemExit('V7E overlay args marker missing')
src = src.replace(old_overlay_args, new_overlay_args, 1)

old_fail = '''        snprintf(error, error_size,\n            "V7E soak failed: video=%u drop=%u/%u vspan=%" PRId64\n            " audio=%u silent_delta=%u aspan=%" PRId64 " max_sync=%" PRId64 "ms HTTP=%ld",\n            rendered_frames, dropped_frames, drop_limit, video_span,\n            audio_stats.played, silent_delta, audio_span, max_abs_sync_ms, remote.last_http);'''
new_fail = '''        snprintf(error, error_size,\n            "V7E soak failed\\nVIDEO %u DROP %u/%u VSPAN %" PRId64 "ms\\n"\n            "AUDIO %u SILENT+%u ASPAN %" PRId64 "ms\\n"\n            "SYNCMAX %" PRId64 "ms HTTP %ld\\nPF HIT %u WAIT %u START %u FALLBACK %u",\n            rendered_frames, dropped_frames, drop_limit, video_span,\n            audio_stats.played, silent_delta, audio_span, max_abs_sync_ms, remote.last_http,\n            remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_started, remote.prefetch_fallbacks);'''
if old_fail not in src:
    raise SystemExit('V7E fail diagnostic marker missing')
src = src.replace(old_fail, new_fail, 1)

for needle in (
    'SPELUNKR360 V7E - ASYNC PREFETCH + LONG-RUN STABILITY',
    'SPELUNKR360 V7E - ASYNC PREFETCH STABILITY PLAYBACK',
    'v7e_prefetch_worker',
    'v7e_prefetch_promote',
    'PREFETCH HIT %u WAIT %u START %u FALLBACK %u',
    'V7E soak failed\\nVIDEO',
):
    if needle not in src:
        raise SystemExit(f'V7E marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7E asynchronous sequential range prefetch and readable failure metrics")
