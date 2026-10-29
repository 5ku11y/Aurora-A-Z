#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_size_diag8.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

marker = 'static int64_t metadata_file_size(const char *json, const char *wanted_name)\n{'
if marker not in src:
    raise SystemExit('metadata_file_size marker missing')

debug_globals = r'''static int64_t g_sz8_content_range = -1;
static int64_t g_sz8_head = -1;
static int64_t g_sz8_metadata = -1;
static long g_sz8_meta_http = 0;
static size_t g_sz8_meta_bytes = 0;
static unsigned g_sz8_meta_seen = 0;
static bool g_sz8_meta_match = false;

'''
src = src.replace(marker, debug_globals + marker, 1)

old_match = r'''        if (strcmp(parsed_name, wanted_name) != 0) { p = after_name; continue; }
        obj_end = strchr(after_name, '}');'''
new_match = r'''        if (strcmp(parsed_name, wanted_name) != 0) { p = after_name; continue; }
        g_sz8_meta_match = true;
        obj_end = strchr(after_name, '}');'''
if old_match not in src:
    raise SystemExit('metadata name-match block missing')
src = src.replace(old_match, new_match, 1)

old_start = r'''    int64_t total = -1;
    unsigned start;

    if (media_url == NULL'''
new_start = r'''    int64_t total = -1;
    unsigned start;

    g_sz8_meta_http = 0;
    g_sz8_meta_bytes = 0;
    g_sz8_meta_seen = 0;
    g_sz8_meta_match = false;
    if (media_url == NULL'''
if old_start not in src:
    raise SystemExit('metadata function setup block missing')
src = src.replace(old_start, new_start, 1)

old_fetch = r'''        result = fetch_url(metadata_url, &body);
        if (result.curl_code != CURLE_OK || result.http_code != 200 || body.overflow)
            break;

        total = metadata_file_size(json, filename);'''
new_fetch = r'''        result = fetch_url(metadata_url, &body);
        g_sz8_meta_http = result.http_code;
        g_sz8_meta_bytes = result.bytes;
        if (result.curl_code != CURLE_OK || result.http_code != 200 || body.overflow)
            break;

        total = metadata_file_size(json, filename);'''
if old_fetch not in src:
    raise SystemExit('metadata fetch block missing')
src = src.replace(old_fetch, new_fetch, 1)

old_seen = r'''        seen = metadata_name_count(json);
        if (seen < PAGE_COUNT)'''
new_seen = r'''        seen = metadata_name_count(json);
        g_sz8_meta_seen = seen;
        if (seen < PAGE_COUNT)'''
if old_seen not in src:
    raise SystemExit('metadata seen block missing')
src = src.replace(old_seen, new_seen, 1)

old_fallback = r'''    if (total <= 0) total = remote_head_size(remote);
    if (total <= 0) total = archive_metadata_size(remote->url);
    if (total <= 0) { snprintf(remote->error, sizeof(remote->error), "SIZE64 FAIL rangeHTTP=%ld", http); return -1; }'''
new_fallback = r'''    g_sz8_content_range = total;
    g_sz8_head = -1;
    g_sz8_metadata = -1;
    if (total <= 0) {
        total = remote_head_size(remote);
        g_sz8_head = total;
    }
    if (total <= 0) {
        total = archive_metadata_size(remote->url);
        g_sz8_metadata = total;
    }
    if (total <= 0) {
        snprintf(remote->error, sizeof(remote->error),
            "SZ8 CR=%" PRId64 " HEAD=%" PRId64 "\nMETA H=%ld B=%u N=%u MATCH=%u SIZE=%" PRId64,
            g_sz8_content_range, g_sz8_head, g_sz8_meta_http,
            (unsigned)g_sz8_meta_bytes, g_sz8_meta_seen, g_sz8_meta_match ? 1u : 0u,
            g_sz8_metadata);
        return -1;
    }'''
if old_fallback not in src:
    raise SystemExit('V7A.7 size fallback block missing')
src = src.replace(old_fallback, new_fallback, 1)

src = src.replace('SPELUNKR360 V7A.7 - LIVE VIDEO FRAME PROBE', 'SPELUNKR360 V7A.8 - LIVE VIDEO FRAME PROBE')
src = src.replace('V7A.7 - B/BACK/START RETURNS TO AURORA', 'V7A.8 - B/BACK/START RETURNS TO AURORA')

if 'SPELUNKR360 V7A.8 - LIVE VIDEO FRAME PROBE' not in src:
    raise SystemExit('V7A.8 visible marker missing')
if 'SZ8 CR=' not in src or 'META H=' not in src:
    raise SystemExit('V7A.8 diagnostics missing')

out.write_text(src)
print(f"generated {out} with V7A.8 per-source media size diagnostics")
