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

static int hex_nibble(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static bool percent_decode_path(const char *src, size_t src_len, char *dst, size_t dst_size)
{
    size_t i = 0, o = 0;
    if (src == NULL || dst == NULL || dst_size == 0) return false;
    while (i < src_len) {
        unsigned char ch = (unsigned char)src[i++];
        if (ch == '%' && i + 1u < src_len) {
            const int hi = hex_nibble(src[i]);
            const int lo = hex_nibble(src[i + 1u]);
            if (hi >= 0 && lo >= 0) {
                ch = (unsigned char)((hi << 4) | lo);
                i += 2u;
            }
        }
        if (o + 1u >= dst_size) return false;
        dst[o++] = (char)ch;
    }
    dst[o] = '\0';
    return true;
}

static const char *json_read_name(const char *quote, char *out, size_t out_size)
{
    const char *p = quote;
    size_t o = 0;
    if (p == NULL || out == NULL || out_size == 0 || *p != '"') return NULL;
    p++;
    while (*p != '\0') {
        unsigned char ch = (unsigned char)*p++;
        if (ch == '"') {
            out[o] = '\0';
            return p;
        }
        if (ch == '\\') {
            ch = (unsigned char)*p++;
            if (ch == '\0') return NULL;
            switch (ch) {
                case '"': case '\\': case '/': break;
                case 'b': ch = '\b'; break;
                case 'f': ch = '\f'; break;
                case 'n': ch = '\n'; break;
                case 'r': ch = '\r'; break;
                case 't': ch = '\t'; break;
                case 'u': {
                    int value = 0;
                    int j;
                    for (j = 0; j < 4; j++) {
                        const int nibble = hex_nibble(*p++);
                        if (nibble < 0) return NULL;
                        value = (value << 4) | nibble;
                    }
                    ch = (unsigned char)(value <= 0x7f ? value : '?');
                    break;
                }
                default: return NULL;
            }
        }
        if (o + 1u >= out_size) return NULL;
        out[o++] = (char)ch;
    }
    return NULL;
}

static int64_t metadata_file_size(const char *json, const char *wanted_name)
{
    const char *p = json;
    if (json == NULL || wanted_name == NULL) return -1;

    while ((p = strstr(p, "\"name\"")) != NULL) {
        const char *q = p + 6;
        const char *after_name;
        const char *obj_end;
        const char *size_key;
        const char *colon;
        char parsed_name[SP_FILE_BYTES];
        unsigned long long value;

        while (*q == ' ' || *q == '\t' || *q == '\r' || *q == '\n') q++;
        if (*q++ != ':') { p += 6; continue; }
        while (*q == ' ' || *q == '\t' || *q == '\r' || *q == '\n') q++;
        if (*q != '"') { p += 6; continue; }
        after_name = json_read_name(q, parsed_name, sizeof(parsed_name));
        if (after_name == NULL) { p += 6; continue; }
        if (strcmp(parsed_name, wanted_name) != 0) { p = after_name; continue; }

        obj_end = strchr(after_name, '}');
        if (obj_end == NULL) return -1;
        size_key = strstr(after_name, "\"size\"");
        if (size_key == NULL || size_key >= obj_end) return -1;
        colon = strchr(size_key + 6, ':');
        if (colon == NULL || colon >= obj_end) return -1;
        colon++;
        while (colon < obj_end && (*colon == ' ' || *colon == '\t' || *colon == '\r' || *colon == '\n')) colon++;
        if (colon < obj_end && *colon == '"') colon++;
        if (colon >= obj_end || *colon < '0' || *colon > '9') return -1;
        value = strtoull(colon, NULL, 10);
        return (value > 0 && value <= INT64_MAX) ? (int64_t)value : -1;
    }
    return -1;
}

static int64_t archive_metadata_size(const char *media_url)
{
    static const char prefix[] = "https://archive.org/download/";
    const char *id_start;
    const char *slash;
    const char *file_start;
    const char *file_end;
    size_t id_len;
    size_t file_len;
    char metadata_url[SP_URL_BYTES];
    char filename[SP_FILE_BYTES];
    char *json;
    struct response_buffer body;
    struct http_result result;
    int64_t total = -1;

    if (media_url == NULL || strncmp(media_url, prefix, sizeof(prefix) - 1u) != 0)
        return -1;
    id_start = media_url + sizeof(prefix) - 1u;
    slash = strchr(id_start, '/');
    if (slash == NULL || slash == id_start) return -1;
    id_len = (size_t)(slash - id_start);
    file_start = slash + 1;
    file_end = strpbrk(file_start, "?#");
    if (file_end == NULL) file_end = file_start + strlen(file_start);
    file_len = (size_t)(file_end - file_start);
    if (!percent_decode_path(file_start, file_len, filename, sizeof(filename))) return -1;

    if (snprintf(metadata_url, sizeof(metadata_url), "https://archive.org/metadata/%.*s",
            (int)id_len, id_start) >= (int)sizeof(metadata_url))
        return -1;

    json = malloc(BODY_BYTES);
    if (json == NULL) return -1;
    body.data = json;
    body.capacity = BODY_BYTES;
    body.size = 0;
    body.overflow = false;
    result = fetch_url(metadata_url, &body);
    if (result.curl_code == CURLE_OK && result.http_code == 200 && !body.overflow)
        total = metadata_file_size(json, filename);
    free(json);
    return total;
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
    if (remote->cache_length == 0) {
        snprintf(remote->error, sizeof(remote->error), "initial range returned no media bytes");
        return -1;
    }
    if (total <= 0)
        total = archive_metadata_size(remote->url);
    if (total <= 0) {
        snprintf(remote->error, sizeof(remote->error), "range total missing; metadata size fallback failed");
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
if 'metadata size fallback failed' not in patched or 'https://archive.org/metadata/' not in patched:
    raise SystemExit("Archive metadata size fallback missing")
if 'static const char *const CA_FILE = "ca.pem";' not in patched:
    raise SystemExit("short CA filename patch failed")
out.write_text(patched)
print(f"generated {out} with direct range media-open, Archive metadata size fallback, and ca.pem")
