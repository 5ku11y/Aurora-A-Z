#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7j.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7J hardware follow-up:
# V7I proved true continuous playback, but hardware reports a rhythmic
# ~1-3 second pause roughly every six seconds.  The decoder/audio path always
# recovers; this cadence matches range-boundary transport overhead.  Keep the
# V7H/V7I progressive reader intact, but (1) reuse one libcurl easy handle so
# Archive.org HTTPS/TLS connections can remain alive across sequential ranges,
# and (2) deepen async prefetch from 4 MiB to 8 MiB.  The foreground cache stays
# at the proven 16 MiB allocation.

src = src.replace('SPELUNKR360 V7I - TRUE CONTINUOUS PLAYBACK',
                  'SPELUNKR360 V7J - KEEPALIVE CONTINUOUS PLAYBACK')
src = src.replace('V7I - B/BACK/START RETURNS TO AURORA',
                  'V7J - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7I continuous playback ended before stability gate',
                  'V7J continuous playback ended before stability gate')
src = src.replace('Spelunkr360 V7I PASS:', 'Spelunkr360 V7J PASS:')
src = src.replace('V7I async partial salvaged', 'V7J async partial salvaged')
src = src.replace('V7I foreground partial salvaged', 'V7J foreground partial salvaged')
src = src.replace('V7I prefetch thread: creator_ht=', 'V7J prefetch thread: creator_ht=')

# Double the async range depth.  This value is consumed by v7e_prefetch_worker;
# the foreground cache remains the existing 16 MiB allocation.
old_range = '        remote.range_chunk = 4u * 1024u * 1024u;\n        v7_stage("V7B.3: PREPARING LIVE VIDEO...\\n16 MB CACHE / 4 MB RANGE FILLS.\\nSTREAMING CLOCK WILL RE-SYNC AFTER REFILLS.");'
new_range = '        remote.range_chunk = 8u * 1024u * 1024u;\n        v7_stage("V7J: PREPARING LIVE VIDEO...\\n16 MB CACHE / 8 MB ASYNC PREFETCH.\\nKEEPALIVE RANGE STREAMING ENABLED.");'
if old_range not in src:
    raise SystemExit('V7J range-depth marker missing')
src = src.replace(old_range, new_range, 1)

old_fields = '''    unsigned prefetch_stream_hits;
    unsigned prefetch_stream_waits;
    char prefetch_error[128];'''
new_fields = '''    unsigned prefetch_stream_hits;
    unsigned prefetch_stream_waits;
    CURL *prefetch_curl;
    unsigned prefetch_reuse_count;
    char prefetch_error[128];'''
if old_fields not in src:
    raise SystemExit('V7J prefetch-curl field marker missing')
src = src.replace(old_fields, new_fields, 1)

old_decl = '    CURL *curl = NULL;\n    CURLcode result = CURLE_FAILED_INIT;'
new_decl = '    CURL *curl = NULL;\n    CURLcode result = CURLE_FAILED_INIT;\n    bool reused = false;'
if old_decl not in src:
    raise SystemExit('V7J worker declaration marker missing')
src = src.replace(old_decl, new_decl, 1)

old_init = '''    curl = curl_easy_init();
    if (curl == NULL) {
        snprintf(remote->prefetch_error, sizeof(remote->prefetch_error), "curl init failed");
        remote->prefetch_done = true;
        return NULL;
    }

    set_common_curl(curl, remote->url);'''
new_init = '''    if (remote->prefetch_curl == NULL) {
        remote->prefetch_curl = curl_easy_init();
    } else {
        /* curl_easy_reset clears options but deliberately preserves the easy
         * handle's connection/session caches, allowing HTTPS keep-alive. */
        curl_easy_reset(remote->prefetch_curl);
        reused = true;
        remote->prefetch_reuse_count++;
    }
    curl = remote->prefetch_curl;
    if (curl == NULL) {
        snprintf(remote->prefetch_error, sizeof(remote->prefetch_error), "curl init failed");
        remote->prefetch_done = true;
        return NULL;
    }

    set_common_curl(curl, remote->url);
    curl_easy_setopt(curl, CURLOPT_FRESH_CONNECT, 0L);
    curl_easy_setopt(curl, CURLOPT_FORBID_REUSE, 0L);'''
if old_init not in src:
    raise SystemExit('V7J worker curl-init marker missing')
src = src.replace(old_init, new_init, 1)

old_cleanup = '''    remote->prefetch_http = http;
    curl_easy_cleanup(curl);

    if (http == 206'''
new_cleanup = '''    remote->prefetch_http = http;
    xsdk_log_write("V7J range complete: start=%" PRId64 " bytes=%u HTTP=%ld keepalive=%u",
        remote->prefetch_start, (unsigned)remote->prefetch_length, http, reused ? 1u : 0u);

    if (http == 206'''
if old_cleanup not in src:
    raise SystemExit('V7J worker cleanup marker missing')
src = src.replace(old_cleanup, new_cleanup, 1)

old_close = '''    if (remote->curl != NULL) curl_easy_cleanup(remote->curl);
    free(remote->prefetch_cache);'''
new_close = '''    if (remote->curl != NULL) curl_easy_cleanup(remote->curl);
    if (remote->prefetch_curl != NULL) curl_easy_cleanup(remote->prefetch_curl);
    free(remote->prefetch_cache);'''
if old_close not in src:
    raise SystemExit('V7J remote-close marker missing')
src = src.replace(old_close, new_close, 1)

old_overlay = '                    "PF H%u W%u F%u P%u | STR H%u W%u | HT%u\\n"\n'
new_overlay = '                    "PF H%u W%u F%u P%u | STR H%u W%u | HT%u KA%u\\n"\n'
if old_overlay not in src:
    raise SystemExit('V7J overlay marker missing')
src = src.replace(old_overlay, new_overlay, 1)

old_overlay_args = '''                    remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
                    remote.prefetch_partials, remote.prefetch_stream_hits, remote.prefetch_stream_waits,
                    remote.prefetch_hw_thread);'''
new_overlay_args = '''                    remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
                    remote.prefetch_partials, remote.prefetch_stream_hits, remote.prefetch_stream_waits,
                    remote.prefetch_hw_thread, remote.prefetch_reuse_count);'''
if old_overlay_args not in src:
    raise SystemExit('V7J overlay args marker missing')
src = src.replace(old_overlay_args, new_overlay_args, 1)

old_fail_format = '            "SYNCMAX %" PRId64 "ms HTTP %ld\\nPF H%u W%u F%u P%u | STR H%u W%u | HT%u",'
new_fail_format = '            "SYNCMAX %" PRId64 "ms HTTP %ld\\nPF H%u W%u F%u P%u | STR H%u W%u | HT%u KA%u",'
if old_fail_format in src:
    src = src.replace(old_fail_format, new_fail_format, 1)
    old_fail_args = '''            remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
            remote.prefetch_partials, remote.prefetch_stream_hits, remote.prefetch_stream_waits,
            remote.prefetch_hw_thread);'''
    new_fail_args = '''            remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
            remote.prefetch_partials, remote.prefetch_stream_hits, remote.prefetch_stream_waits,
            remote.prefetch_hw_thread, remote.prefetch_reuse_count);'''
    if old_fail_args not in src:
        raise SystemExit('V7J fail args marker missing')
    src = src.replace(old_fail_args, new_fail_args, 1)

for needle in (
    'SPELUNKR360 V7J - KEEPALIVE CONTINUOUS PLAYBACK',
    'remote.range_chunk = 8u * 1024u * 1024u',
    'KEEPALIVE RANGE STREAMING ENABLED',
    'CURL *prefetch_curl',
    'curl_easy_reset(remote->prefetch_curl)',
    'CURLOPT_FORBID_REUSE',
    'V7J range complete:',
    'prefetch_reuse_count',
    'HT%u KA%u',
):
    if needle not in src:
        raise SystemExit(f'V7J marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7J persistent HTTPS keepalive and 8 MiB async prefetch")
