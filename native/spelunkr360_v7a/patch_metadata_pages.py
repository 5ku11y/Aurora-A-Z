#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_metadata_pages.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

old = r'''static int64_t archive_metadata_size(const char *media_url)
{
    static const char prefix[] = "https://archive.org/download/";
    const char *id_start, *slash, *file_start, *file_end;
    size_t id_len, file_len;
    char metadata_url[SP_URL_BYTES], filename[SP_FILE_BYTES], *json;
    struct response_buffer body;
    struct http_result result;
    int64_t total = -1;
    if (media_url == NULL || strncmp(media_url, prefix, sizeof(prefix) - 1u) != 0) return -1;
    id_start = media_url + sizeof(prefix) - 1u;
    slash = strchr(id_start, '/');
    if (slash == NULL || slash == id_start) return -1;
    id_len = (size_t)(slash - id_start);
    file_start = slash + 1;
    file_end = strpbrk(file_start, "?#");
    if (file_end == NULL) file_end = file_start + strlen(file_start);
    file_len = (size_t)(file_end - file_start);
    if (!percent_decode_path(file_start, file_len, filename, sizeof(filename))) return -1;
    if (snprintf(metadata_url, sizeof(metadata_url), "https://archive.org/metadata/%.*s", (int)id_len, id_start) >= (int)sizeof(metadata_url)) return -1;
    json = malloc(BODY_BYTES);
    if (json == NULL) return -1;
    body.data = json; body.capacity = BODY_BYTES; body.size = 0; body.overflow = false;
    result = fetch_url(metadata_url, &body);
    if (result.curl_code == CURLE_OK && result.http_code == 200 && !body.overflow) total = metadata_file_size(json, filename);
    free(json);
    return total;
}
'''

new = r'''static unsigned metadata_name_count(const char *json)
{
    const char *p = json;
    unsigned count = 0;
    if (json == NULL) return 0;
    while ((p = strstr(p, "\"name\"")) != NULL) {
        count++;
        p += 6;
    }
    return count;
}

static int64_t archive_metadata_size(const char *media_url)
{
    static const char prefix[] = "https://archive.org/download/";
    enum { PAGE_COUNT = 24, MAX_FILES = 4096 };
    const char *id_start, *slash, *file_start, *file_end;
    size_t id_len, file_len;
    char metadata_url[SP_URL_BYTES], filename[SP_FILE_BYTES], *json;
    struct response_buffer body;
    struct http_result result;
    int64_t total = -1;
    unsigned start;

    if (media_url == NULL || strncmp(media_url, prefix, sizeof(prefix) - 1u) != 0) return -1;
    id_start = media_url + sizeof(prefix) - 1u;
    slash = strchr(id_start, '/');
    if (slash == NULL || slash == id_start) return -1;
    id_len = (size_t)(slash - id_start);
    file_start = slash + 1;
    file_end = strpbrk(file_start, "?#");
    if (file_end == NULL) file_end = file_start + strlen(file_start);
    file_len = (size_t)(file_end - file_start);
    if (!percent_decode_path(file_start, file_len, filename, sizeof(filename))) return -1;

    json = malloc(BODY_BYTES);
    if (json == NULL) return -1;
    body.data = json;
    body.capacity = BODY_BYTES;

    for (start = 0; start < MAX_FILES; start += PAGE_COUNT) {
        unsigned seen;
        if (snprintf(metadata_url, sizeof(metadata_url),
            "https://archive.org/metadata/%.*s/files?start=%u&count=%u",
            (int)id_len, id_start, start, (unsigned)PAGE_COUNT) >= (int)sizeof(metadata_url))
            break;

        body.size = 0;
        body.overflow = false;
        result = fetch_url(metadata_url, &body);
        if (result.curl_code != CURLE_OK || result.http_code != 200 || body.overflow)
            break;

        total = metadata_file_size(json, filename);
        if (total > 0)
            break;

        seen = metadata_name_count(json);
        if (seen < PAGE_COUNT)
            break;
    }

    free(json);
    return total;
}
'''

if old not in src:
    raise SystemExit("expected single-shot Archive metadata function not found")
patched = src.replace(old, new, 1)
if 'files?start=%u&count=%u' not in patched:
    raise SystemExit("paged Archive metadata URL missing")
if 'PAGE_COUNT = 24' not in patched:
    raise SystemExit("paged Archive metadata constants missing")
out.write_text(patched)
print(f"generated {out} with paged Archive file metadata lookup")
