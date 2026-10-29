#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_retry12.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

old = r'''            snprintf(range, sizeof(range), "%u-%u", (unsigned)completed, (unsigned)(chunk_end - 1u));
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
            completed = chunk_end;'''

new = r'''            snprintf(range, sizeof(range), "%u-%u", (unsigned)completed, (unsigned)(chunk_end - 1u));
            {
                const unsigned max_attempts = 4u;
                unsigned attempt;
                bool chunk_ok = false;
                for (attempt = 1u; attempt <= max_attempts; attempt++) {
                    bool retryable;
                    before = remote->cache_length;
                    remote->curl_error[0] = '\0';
                    curl_easy_reset(remote->curl);
                    set_common_curl(remote->curl, remote->url);
                    curl_easy_setopt(remote->curl, CURLOPT_TIMEOUT_MS, 60000L);
                    curl_easy_setopt(remote->curl, CURLOPT_LOW_SPEED_TIME, 20L);
                    curl_easy_setopt(remote->curl, CURLOPT_BUFFERSIZE, 131072L);
                    curl_easy_setopt(remote->curl, CURLOPT_RANGE, range);
                    curl_easy_setopt(remote->curl, CURLOPT_WRITEFUNCTION, remote_write);
                    curl_easy_setopt(remote->curl, CURLOPT_WRITEDATA, remote);
                    curl_easy_setopt(remote->curl, CURLOPT_ERRORBUFFER, remote->curl_error);
                    if (attempt > 1u)
                        curl_easy_setopt(remote->curl, CURLOPT_FRESH_CONNECT, 1L);
                    result = curl_easy_perform(remote->curl);
                    (void)curl_easy_getinfo(remote->curl, CURLINFO_RESPONSE_CODE, &http);
                    remote->last_http = http;
                    got = remote->cache_length - before;
                    if (result == CURLE_OK && http == 206 && got == expected) {
                        chunk_ok = true;
                        break;
                    }

                    /* Never leave an Archive.org error body or partial range in the MP4 header. */
                    remote->cache_length = before;
                    retryable = result != CURLE_OK || http == 429 ||
                                (http >= 500 && http <= 599) ||
                                (http == 206 && got != expected);
                    if (attempt < max_attempts && retryable) {
                        snprintf(progress, sizeof(progress),
                            "STAGE 1/5: ARCHIVE RANGE RETRY...\nCHUNK %u/%u  RETRY %u/%u  HTTP %ld  GOT %u/%u",
                            chunk_index, total_chunks, attempt + 1u, max_attempts,
                            http, (unsigned)got, (unsigned)expected);
                        v7_stage(progress);
                        continue;
                    }

                    if (result != CURLE_OK || http != 206) {
                        snprintf(remote->error, sizeof(remote->error),
                            "MOOV CHUNK %u/%u try=%u curl=%d HTTP=%ld got=%u %.64s",
                            chunk_index, total_chunks, attempt, (int)result, http,
                            (unsigned)got, remote->curl_error);
                    } else {
                        snprintf(remote->error, sizeof(remote->error),
                            "MOOV CHUNK %u/%u try=%u short %u/%u HTTP=%ld",
                            chunk_index, total_chunks, attempt, (unsigned)got,
                            (unsigned)expected, http);
                    }
                    return -1;
                }
                if (!chunk_ok) {
                    snprintf(remote->error, sizeof(remote->error),
                        "MOOV CHUNK %u/%u retries exhausted", chunk_index, total_chunks);
                    return -1;
                }
            }
            completed = chunk_end;'''

if old not in src:
    raise SystemExit('V7A.11 chunk transfer block missing')
src = src.replace(old, new, 1)
src = src.replace('SPELUNKR360 V7A.11 - LIVE VIDEO FRAME PROBE', 'SPELUNKR360 V7A.12 - LIVE VIDEO FRAME PROBE')
src = src.replace('V7A.11 - B/BACK/START RETURNS TO AURORA', 'V7A.12 - B/BACK/START RETURNS TO AURORA')

for needle in (
    'SPELUNKR360 V7A.12 - LIVE VIDEO FRAME PROBE',
    'STAGE 1/5: ARCHIVE RANGE RETRY',
    'CURLOPT_FRESH_CONNECT',
    'remote->cache_length = before',
    'MOOV CHUNK %u/%u try=%u',
    'MP4 HEADER COMPLETE. MOVING TO FFMPEG',
):
    if needle not in src:
        raise SystemExit(f'V7A.12 marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7A.12 resilient Archive.org range retries")
