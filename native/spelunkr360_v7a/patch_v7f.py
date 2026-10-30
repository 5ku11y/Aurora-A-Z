#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7f.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7F hardware follow-up:
# V7E proved the async transport path but Archive.org can return CURLE_OPERATION_TIMEDOUT
# (curl 28) after already delivering a useful contiguous portion of a HTTP 206 range.
# Media payload bytes do not require an all-or-nothing range transaction: keep those bytes,
# consume them, and make the next sequential request begin exactly where they ended.

src = src.replace('SPELUNKR360 V7E - ASYNC PREFETCH + LONG-RUN STABILITY',
                  'SPELUNKR360 V7F - TIMEOUT-RESILIENT PREFETCH + STABILITY')
src = src.replace('SPELUNKR360 V7E - ASYNC PREFETCH STABILITY PLAYBACK',
                  'SPELUNKR360 V7F - TIMEOUT-RESILIENT PREFETCH PLAYBACK')
src = src.replace('V7E - B/BACK/START RETURNS TO AURORA',
                  'V7F - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7E soak failed', 'V7F soak failed')
src = src.replace('Spelunkr360 V7E PASS:', 'Spelunkr360 V7F PASS:')

old_counters = '''    unsigned prefetch_started;
    unsigned prefetch_hits;
    unsigned prefetch_waits;
    unsigned prefetch_fallbacks;
    char prefetch_error[128];'''
new_counters = '''    unsigned prefetch_started;
    unsigned prefetch_hits;
    unsigned prefetch_waits;
    unsigned prefetch_fallbacks;
    unsigned prefetch_partials;
    unsigned foreground_partials;
    char prefetch_error[128];'''
if old_counters not in src:
    raise SystemExit('V7F prefetch counter marker missing')
src = src.replace(old_counters, new_counters, 1)

# Background prefetch: a timed-out HTTP 206 that delivered one or more bytes is
# still a valid contiguous range prefix. Promote it instead of throwing it away.
old_worker_result = '''    if (result == CURLE_OK && http == 206 && remote->prefetch_length == wanted) {
        remote->prefetch_status = 0;
    } else {
        if (remote->prefetch_error[0] == '\\0')
            snprintf(remote->prefetch_error, sizeof(remote->prefetch_error),
                "curl=%d HTTP=%ld got=%u/%u", (int)result, http,
                (unsigned)remote->prefetch_length, (unsigned)wanted);
        remote->prefetch_status = -1;
    }'''
new_worker_result = '''    if (http == 206 && remote->prefetch_length > 0 &&
        (result == CURLE_OK || result == CURLE_OPERATION_TIMEDOUT)) {
        if (result == CURLE_OPERATION_TIMEDOUT || remote->prefetch_length < wanted) {
            remote->prefetch_partials++;
            xsdk_log_write("V7F async partial salvaged: start=%" PRId64
                " bytes=%u/%u curl=%d HTTP=%ld", remote->prefetch_start,
                (unsigned)remote->prefetch_length, (unsigned)wanted, (int)result, http);
        }
        remote->prefetch_status = 0;
    } else {
        if (remote->prefetch_error[0] == '\\0')
            snprintf(remote->prefetch_error, sizeof(remote->prefetch_error),
                "curl=%d HTTP=%ld got=%u/%u", (int)result, http,
                (unsigned)remote->prefetch_length, (unsigned)wanted);
        remote->prefetch_status = -1;
    }'''
if old_worker_result not in src:
    raise SystemExit('V7F async result marker missing')
src = src.replace(old_worker_result, new_worker_result, 1)

# Foreground fallback: apply the same rule. A curl 28 is fatal only if it
# delivered no usable range bytes. remote_fill's cache starts at `start`, so a
# nonempty 206 prefix can be consumed safely and the next fill starts after it.
old_fill_result = '''    remote->last_http = http;
    if (result != CURLE_OK) {
        snprintf(remote->error, sizeof(remote->error), "range curl=%d HTTP=%ld %.120s",
            (int)result, http, remote->curl_error);
        return -1;
    }
    if (http != 206 && !(http == 200 && start == 0)) {
        snprintf(remote->error, sizeof(remote->error), "server ignored range at %" PRId64 " (HTTP %ld)", start, http);
        return -1;
    }
    if (remote->cache_length == 0) {
        snprintf(remote->error, sizeof(remote->error), "empty range at %" PRId64, start);
        return -1;
    }
    remote->cache_start = start;
    return 0;'''
new_fill_result = '''    remote->last_http = http;
    if (result != CURLE_OK &&
        !(result == CURLE_OPERATION_TIMEDOUT && remote->cache_length > 0 &&
          (http == 206 || (http == 200 && start == 0)))) {
        snprintf(remote->error, sizeof(remote->error), "range curl=%d HTTP=%ld %.120s",
            (int)result, http, remote->curl_error);
        return -1;
    }
    if (http != 206 && !(http == 200 && start == 0)) {
        snprintf(remote->error, sizeof(remote->error), "server ignored range at %" PRId64 " (HTTP %ld)", start, http);
        return -1;
    }
    if (remote->cache_length == 0) {
        snprintf(remote->error, sizeof(remote->error), "empty range at %" PRId64, start);
        return -1;
    }
    if (result == CURLE_OPERATION_TIMEDOUT) {
        remote->foreground_partials++;
        xsdk_log_write("V7F foreground partial salvaged: start=%" PRId64
            " bytes=%u curl=%d HTTP=%ld", start, (unsigned)remote->cache_length,
            (int)result, http);
    }
    remote->cache_start = start;
    return 0;'''
if old_fill_result not in src:
    raise SystemExit('V7F foreground remote_fill marker missing')
src = src.replace(old_fill_result, new_fill_result, 1)

old_overlay = '                    "PREFETCH HIT %u WAIT %u START %u FALLBACK %u\\n"\n'
new_overlay = '                    "PF HIT %u WAIT %u FALL %u PART %u | FG PART %u\\n"\n'
if old_overlay not in src:
    raise SystemExit('V7F overlay format marker missing')
src = src.replace(old_overlay, new_overlay, 1)

old_overlay_args = '''                    remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_started, remote.prefetch_fallbacks);'''
new_overlay_args = '''                    remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
                    remote.prefetch_partials, remote.foreground_partials);'''
if old_overlay_args not in src:
    raise SystemExit('V7F overlay args marker missing')
src = src.replace(old_overlay_args, new_overlay_args, 1)

old_fail_format = '            "SYNCMAX %" PRId64 "ms HTTP %ld\\nPF HIT %u WAIT %u START %u FALLBACK %u",'
new_fail_format = '            "SYNCMAX %" PRId64 "ms HTTP %ld\\nPF H%u W%u F%u P%u | FG P%u",'
if old_fail_format not in src:
    raise SystemExit('V7F fail format marker missing')
src = src.replace(old_fail_format, new_fail_format, 1)

old_fail_args = '''            remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_started, remote.prefetch_fallbacks);'''
new_fail_args = '''            remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
            remote.prefetch_partials, remote.foreground_partials);'''
if old_fail_args not in src:
    raise SystemExit('V7F fail args marker missing')
src = src.replace(old_fail_args, new_fail_args, 1)

for needle in (
    'SPELUNKR360 V7F - TIMEOUT-RESILIENT PREFETCH + STABILITY',
    'SPELUNKR360 V7F - TIMEOUT-RESILIENT PREFETCH PLAYBACK',
    'result == CURLE_OK || result == CURLE_OPERATION_TIMEDOUT',
    'V7F async partial salvaged',
    'V7F foreground partial salvaged',
    'PF HIT %u WAIT %u FALL %u PART %u | FG PART %u',
    'V7F soak failed',
):
    if needle not in src:
        raise SystemExit(f'V7F marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7F curl-28 partial-range salvage for async and foreground media reads")
