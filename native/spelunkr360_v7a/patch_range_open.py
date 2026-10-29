#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_range_open.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

old = r'''static int remote_open(struct remote_file *remote, const char *url)
{
    CURLcode result;
    long http = 0;
    curl_off_t length = -1;
    memset(remote, 0, sizeof(*remote));
    remote->size = -1;
    remote->cache_start = -1;
    if (snprintf(remote->url, sizeof(remote->url), "%s", url) >= (int)sizeof(remote->url)) {
        snprintf(remote->error, sizeof(remote->error), "media URL too long");
        return -1;
    }
    remote->cache_capacity = REMOTE_CACHE_BYTES;
    remote->cache = malloc(remote->cache_capacity);
    remote->curl = curl_easy_init();
    if (remote->cache == NULL || remote->curl == NULL) {
        snprintf(remote->error, sizeof(remote->error), "remote allocation failed");
        return -1;
    }
    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_NOBODY, 1L);
    curl_easy_setopt(remote->curl, CURLOPT_ERRORBUFFER, remote->curl_error);
    result = curl_easy_perform(remote->curl);
    (void)curl_easy_getinfo(remote->curl, CURLINFO_RESPONSE_CODE, &http);
    if (result != CURLE_OK || http < 200 || http >= 400) {
        snprintf(remote->error, sizeof(remote->error), "media HEAD curl=%d HTTP=%ld %.120s",
            (int)result, http, remote->curl_error);
        return -1;
    }
    if (curl_easy_getinfo(remote->curl, CURLINFO_CONTENT_LENGTH_DOWNLOAD_T, &length) != CURLE_OK || length <= 0) {
        snprintf(remote->error, sizeof(remote->error), "media size unavailable");
        return -1;
    }
    remote->size = (int64_t)length;
    remote->position = 0;
    remote->last_http = http;
    return 0;
}
'''

new = r'''static size_t remote_size_header(char *data, size_t size, size_t count, void *user)
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

    if (data == NULL || total == NULL || length <= name_len)
        return length;
    for (i = 0; i < name_len; i++) {
        if (ascii_lower((unsigned char)data[i]) != (unsigned char)name[i])
            return length;
    }

    slash = memchr(data, '/', length);
    if (slash == NULL)
        return length;
    slash++;
    while ((size_t)(slash - data) < length && (*slash == ' ' || *slash == '\t'))
        slash++;
    if ((size_t)(slash - data) >= length || *slash == '*')
        return length;

    while ((size_t)(slash - data) < length && *slash >= '0' && *slash <= '9' && n + 1u < sizeof(number))
        number[n++] = *slash++;
    if (n == 0)
        return length;
    number[n] = '\0';
    value = strtoull(number, NULL, 10);
    if (value > 0 && value <= INT64_MAX)
        *total = (int64_t)value;
    return length;
}

static int remote_open(struct remote_file *remote, const char *url)
{
    CURLcode result;
    long http = 0;
    int64_t total = -1;
    char range[96];

    memset(remote, 0, sizeof(*remote));
    remote->size = -1;
    remote->cache_start = -1;
    if (snprintf(remote->url, sizeof(remote->url), "%s", url) >= (int)sizeof(remote->url)) {
        snprintf(remote->error, sizeof(remote->error), "media URL too long");
        return -1;
    }

    remote->cache_capacity = REMOTE_CACHE_BYTES;
    remote->cache = malloc(remote->cache_capacity);
    remote->curl = curl_easy_init();
    if (remote->cache == NULL || remote->curl == NULL) {
        snprintf(remote->error, sizeof(remote->error), "remote allocation failed");
        return -1;
    }

    snprintf(range, sizeof(range), "0-%u", (unsigned)(remote->cache_capacity - 1u));
    remote->cache_length = 0;
    remote->curl_error[0] = '\0';
    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_RANGE, range);
    curl_easy_setopt(remote->curl, CURLOPT_WRITEFUNCTION, remote_write);
    curl_easy_setopt(remote->curl, CURLOPT_WRITEDATA, remote);
    curl_easy_setopt(remote->curl, CURLOPT_HEADERFUNCTION, remote_size_header);
    curl_easy_setopt(remote->curl, CURLOPT_HEADERDATA, &total);
    curl_easy_setopt(remote->curl, CURLOPT_ERRORBUFFER, remote->curl_error);

    result = curl_easy_perform(remote->curl);
    (void)curl_easy_getinfo(remote->curl, CURLINFO_RESPONSE_CODE, &http);
    remote->last_http = http;

    if (result != CURLE_OK) {
        snprintf(remote->error, sizeof(remote->error), "initial range curl=%d HTTP=%ld %.120s",
            (int)result, http, remote->curl_error);
        return -1;
    }
    if (http != 206) {
        snprintf(remote->error, sizeof(remote->error), "initial range expected 206, got HTTP %ld", http);
        return -1;
    }
    if (total <= 0) {
        snprintf(remote->error, sizeof(remote->error), "initial range missing Content-Range total");
        return -1;
    }
    if (remote->cache_length == 0) {
        snprintf(remote->error, sizeof(remote->error), "initial range returned no media bytes");
        return -1;
    }

    remote->size = total;
    remote->cache_start = 0;
    remote->position = 0;
    return 0;
}
'''

if old not in src:
    raise SystemExit("expected V7A remote_open block not found")
patched = src.replace(old, new, 1)
if 'static const char *const CA_FILE = "cacert.pem";' not in patched:
    raise SystemExit("expected V7A CA_FILE marker not found")
patched = patched.replace('static const char *const CA_FILE = "cacert.pem";',
                          'static const char *const CA_FILE = "ca.pem";', 1)
if 'media HEAD curl=' in patched or 'media size unavailable' in patched:
    raise SystemExit("legacy HEAD media-open path survived patch")
if 'initial range missing Content-Range total' not in patched:
    raise SystemExit("new range-open diagnostics missing")
if 'static const char *const CA_FILE = "ca.pem";' not in patched:
    raise SystemExit("short CA filename patch failed")
out.write_text(patched)
print(f"generated {out} with direct range media-open and ca.pem")
