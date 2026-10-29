#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_size64.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

old_header = r'''static size_t remote_size_header(char *data, size_t size, size_t count, void *user)
{
    int64_t *total = user;
    const size_t length = size * count;
    static const char name[] = "content-range:";
    const size_t name_len = sizeof(name) - 1u;
    size_t i;
    const char *slash;
    char number[32];
    size_t n = 0;
    unsigned long long value;
    if (data == NULL || total == NULL || length <= name_len) return length;
    for (i = 0; i < name_len; i++) if (ascii_lower((unsigned char)data[i]) != (unsigned char)name[i]) return length;
    slash = memchr(data, '/', length);
    if (slash == NULL) return length;
    slash++;
    while ((size_t)(slash - data) < length && (*slash == ' ' || *slash == '\t')) slash++;
    if ((size_t)(slash - data) >= length || *slash == '*') return length;
    while ((size_t)(slash - data) < length && *slash >= '0' && *slash <= '9' && n + 1u < sizeof(number)) number[n++] = *slash++;
    if (n == 0) return length;
    number[n] = '\0';
    value = strtoull(number, NULL, 10);
    if (value > 0 && value <= INT64_MAX) *total = (int64_t)value;
    return length;
}
'''

new_header = r'''static bool parse_decimal_u64_span(const char *p, const char *end, uint64_t *out_value)
{
    uint64_t value = 0;
    bool any = false;
    if (p == NULL || end == NULL || out_value == NULL || p >= end) return false;
    while (p < end && *p >= '0' && *p <= '9') {
        const uint64_t digit = (uint64_t)(unsigned)(*p - '0');
        if (value > (UINT64_MAX - digit) / 10u) return false;
        value = value * 10u + digit;
        any = true;
        p++;
    }
    if (!any) return false;
    *out_value = value;
    return true;
}

static size_t remote_size_header(char *data, size_t size, size_t count, void *user)
{
    int64_t *total = user;
    const size_t length = size * count;
    static const char name[] = "content-range:";
    const size_t name_len = sizeof(name) - 1u;
    const char *slash;
    const char *end;
    uint64_t value = 0;
    size_t i;
    if (data == NULL || total == NULL || length <= name_len) return length;
    for (i = 0; i < name_len; i++)
        if (ascii_lower((unsigned char)data[i]) != (unsigned char)name[i]) return length;
    end = data + length;
    slash = memchr(data, '/', length);
    if (slash == NULL) return length;
    slash++;
    while (slash < end && (*slash == ' ' || *slash == '\t')) slash++;
    if (slash >= end || *slash == '*') return length;
    if (parse_decimal_u64_span(slash, end, &value) && value > 0 && value <= (uint64_t)INT64_MAX)
        *total = (int64_t)value;
    return length;
}

static size_t remote_length_header(char *data, size_t size, size_t count, void *user)
{
    int64_t *total = user;
    const size_t length = size * count;
    static const char name[] = "content-length:";
    const size_t name_len = sizeof(name) - 1u;
    const char *p;
    const char *end;
    uint64_t value = 0;
    size_t i;
    if (data == NULL || total == NULL || length <= name_len) return length;
    for (i = 0; i < name_len; i++)
        if (ascii_lower((unsigned char)data[i]) != (unsigned char)name[i]) return length;
    p = data + name_len;
    end = data + length;
    while (p < end && (*p == ' ' || *p == '\t')) p++;
    if (parse_decimal_u64_span(p, end, &value) && value > 0 && value <= (uint64_t)INT64_MAX)
        *total = (int64_t)value;
    return length;
}

static int64_t remote_head_size(struct remote_file *remote)
{
    CURLcode result;
    long http = 0;
    int64_t total = -1;
    if (remote == NULL || remote->curl == NULL) return -1;
    remote->curl_error[0] = '\0';
    curl_easy_reset(remote->curl);
    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_NOBODY, 1L);
    curl_easy_setopt(remote->curl, CURLOPT_HEADERFUNCTION, remote_length_header);
    curl_easy_setopt(remote->curl, CURLOPT_HEADERDATA, &total);
    curl_easy_setopt(remote->curl, CURLOPT_ERRORBUFFER, remote->curl_error);
    result = curl_easy_perform(remote->curl);
    (void)curl_easy_getinfo(remote->curl, CURLINFO_RESPONSE_CODE, &http);
    if (result != CURLE_OK || http < 200 || http >= 400) return -1;
    return total;
}
'''

if old_header not in src:
    raise SystemExit("expected V7A Content-Range parser not found")
patched = src.replace(old_header, new_header, 1)

old_meta = r'''        char parsed_name[SP_FILE_BYTES];
        unsigned long long value;'''
new_meta = r'''        char parsed_name[SP_FILE_BYTES];
        uint64_t value = 0;'''
if old_meta not in patched:
    raise SystemExit("expected metadata size value declaration not found")
patched = patched.replace(old_meta, new_meta, 1)

old_meta_parse = r'''        value = strtoull(colon, NULL, 10);
        return (value > 0 && value <= INT64_MAX) ? (int64_t)value : -1;'''
new_meta_parse = r'''        if (!parse_decimal_u64_span(colon, obj_end, &value)) return -1;
        return (value > 0 && value <= (uint64_t)INT64_MAX) ? (int64_t)value : -1;'''
if old_meta_parse not in patched:
    raise SystemExit("expected metadata strtoull parser not found")
patched = patched.replace(old_meta_parse, new_meta_parse, 1)

old_fallback = r'''    if (total <= 0) total = archive_metadata_size(remote->url);
    if (total <= 0) { snprintf(remote->error, sizeof(remote->error), "initial range missing Content-Range total; metadata size fallback failed"); return -1; }'''
new_fallback = r'''    if (total <= 0) total = remote_head_size(remote);
    if (total <= 0) total = archive_metadata_size(remote->url);
    if (total <= 0) { snprintf(remote->error, sizeof(remote->error), "SIZE64 FAIL rangeHTTP=%ld", http); return -1; }'''
if old_fallback not in patched:
    raise SystemExit("expected V7A size fallback block not found")
patched = patched.replace(old_fallback, new_fallback, 1)

if 'strtoull(' in patched:
    raise SystemExit("strtoull survived V7A size64 patch")
patched = patched.replace('SPELUNKR360 V7A - LIVE VIDEO FRAME PROBE', 'SPELUNKR360 V7A.7 - LIVE VIDEO FRAME PROBE')
patched = patched.replace('V7A - B/BACK/START RETURNS TO AURORA', 'V7A.7 - B/BACK/START RETURNS TO AURORA')
if 'SPELUNKR360 V7A.7 - LIVE VIDEO FRAME PROBE' not in patched:
    raise SystemExit("V7A.7 visible build marker missing")
if 'remote_head_size(remote)' not in patched or 'SIZE64 FAIL' not in patched:
    raise SystemExit("V7A.7 64-bit fallback missing")

out.write_text(patched)
print(f"generated {out} with explicit uint64 parsing, manual HEAD Content-Length fallback, and visible V7A.7 marker")
