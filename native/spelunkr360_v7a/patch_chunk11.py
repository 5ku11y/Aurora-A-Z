#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_chunk11.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7A.10 accidentally attached the 17 MB Stage-1 message to generic remote_fill().
# Remove that stage reset so later FFmpeg range reads do not masquerade as Stage 1.
old_fill = r'''    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_TIMEOUT_MS, 120000L);
    curl_easy_setopt(remote->curl, CURLOPT_LOW_SPEED_TIME, 30L);
    curl_easy_setopt(remote->curl, CURLOPT_BUFFERSIZE, 131072L);
    v7_stage("STAGE 1/5: DOWNLOADING 17 MB MP4 HEADER...\nTHIS CAN TAKE MORE THAN 30 SECONDS ON XBOX 360.");
    curl_easy_setopt(remote->curl, CURLOPT_RANGE, range);'''
new_fill = r'''    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_TIMEOUT_MS, 60000L);
    curl_easy_setopt(remote->curl, CURLOPT_LOW_SPEED_TIME, 20L);
    curl_easy_setopt(remote->curl, CURLOPT_BUFFERSIZE, 131072L);
    curl_easy_setopt(remote->curl, CURLOPT_RANGE, range);'''
if old_fill not in src:
    raise SystemExit('V7A.10 generic range instrumentation marker missing')
src = src.replace(old_fill, new_fill, 1)

old_prefetch = r'''    remote->cache = grown;
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
    return 1;'''

new_prefetch = r'''    remote->cache = grown;
    remote->cache_capacity = (size_t)target;
    remote->cache_length = 0;
    remote->curl_error[0] = '\0';
    {
        const size_t chunk_bytes = 1024u * 1024u;
        const size_t target_bytes = (size_t)target;
        const unsigned total_chunks = (unsigned)((target_bytes + chunk_bytes - 1u) / chunk_bytes);
        size_t completed = 0;
        unsigned chunk_index = 0;
        while (completed < target_bytes) {
            size_t chunk_end = completed + chunk_bytes;
            size_t before, got, expected;
            char progress[192];
            if (chunk_end > target_bytes) chunk_end = target_bytes;
            before = remote->cache_length;
            expected = chunk_end - completed;
            chunk_index++;
            snprintf(progress, sizeof(progress),
                "STAGE 1/5: DOWNLOADING MP4 HEADER IN CHUNKS...\nCHUNK %u/%u  %u/%u KB",
                chunk_index, total_chunks, (unsigned)(completed / 1024u), (unsigned)(target_bytes / 1024u));
            v7_stage(progress);
            snprintf(range, sizeof(range), "%u-%u", (unsigned)completed, (unsigned)(chunk_end - 1u));
            curl_easy_reset(remote->curl);
            set_common_curl(remote->curl, remote->url);
            curl_easy_setopt(remote->curl, CURLOPT_TIMEOUT_MS, 60000L);
            curl_easy_setopt(remote->curl, CURLOPT_LOW_SPEED_TIME, 20L);
            curl_easy_setopt(remote->curl, CURLOPT_BUFFERSIZE, 131072L);
            curl_easy_setopt(remote->curl, CURLOPT_RANGE, range);
            curl_easy_setopt(remote->curl, CURLOPT_WRITEFUNCTION, remote_write);
            curl_easy_setopt(remote->curl, CURLOPT_WRITEDATA, remote);
            curl_easy_setopt(remote->curl, CURLOPT_ERRORBUFFER, remote->curl_error);
            result = curl_easy_perform(remote->curl);
            (void)curl_easy_getinfo(remote->curl, CURLINFO_RESPONSE_CODE, &http);
            remote->last_http = http;
            got = remote->cache_length - before;
            if (result != CURLE_OK || http != 206) {
                snprintf(remote->error, sizeof(remote->error),
                    "MOOV CHUNK %u/%u curl=%d HTTP=%ld got=%u %.80s",
                    chunk_index, total_chunks, (int)result, http, (unsigned)got, remote->curl_error);
                return -1;
            }
            if (got != expected) {
                snprintf(remote->error, sizeof(remote->error),
                    "MOOV CHUNK %u/%u short %u/%u HTTP=%ld",
                    chunk_index, total_chunks, (unsigned)got, (unsigned)expected, http);
                return -1;
            }
            completed = chunk_end;
        }
    }
    if (remote->cache_length != (size_t)target) {
        snprintf(remote->error, sizeof(remote->error), "MOOV assembled %u/%u",
            (unsigned)remote->cache_length, (unsigned)target);
        return -1;
    }
    remote->cache_start = 0;
    remote->position = 0;
    v7_stage("STAGE 1/5: MP4 HEADER COMPLETE. MOVING TO FFMPEG...");
    return 1;'''

if old_prefetch not in src:
    raise SystemExit('V7A.10 single-shot moov prefetch block missing')
src = src.replace(old_prefetch, new_prefetch, 1)

src = src.replace('SPELUNKR360 V7A.10 - LIVE VIDEO FRAME PROBE', 'SPELUNKR360 V7A.11 - LIVE VIDEO FRAME PROBE')
src = src.replace('V7A.10 - B/BACK/START RETURNS TO AURORA', 'V7A.11 - B/BACK/START RETURNS TO AURORA')

for needle in (
    'SPELUNKR360 V7A.11 - LIVE VIDEO FRAME PROBE',
    'STAGE 1/5: DOWNLOADING MP4 HEADER IN CHUNKS',
    'MOOV CHUNK %u/%u',
    'MP4 HEADER COMPLETE. MOVING TO FFMPEG',
    'STAGE 5/5: READING / DECODING H.264 FRAME'):
    if needle not in src:
        raise SystemExit(f'V7A.11 marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7A.11 chunked front-moov transport and corrected stage labeling")
