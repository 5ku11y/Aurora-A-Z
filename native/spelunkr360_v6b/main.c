/* Spelunkr360 V6B - live lineup -> TOONERTIA manifest chain probe.
 *
 * V6A proved that a retail Xbox 360 running xsdk homebrew can reach Spelunkr's
 * public broadcast bucket, download lineup.json, find dial 53 / TOONERTIA and
 * discover the live manifest path. V6B follows that path on the console,
 * downloads the manifest and extracts real program metadata.
 */

#include <curl/curl.h>

#include <ctype.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "xsdk/gpu.h"
#include "xsdk/kernel.h"
#include "xsdk/log.h"
#include "xsdk/present.h"
#include "xsdk/text.h"

enum {
    BUFFERS = 2,
    SWAP_INTERVAL = 1,
    BEGIN_TIMEOUT_MS = 5000,
    AUTO_EXIT_FRAMES = 1200,
    BACKGROUND_ARGB = 0xFF102418,
    TEXT_ARGB = 0xFFF0F0E8,
    PASS_ARGB = 0xFF8FE388,
    FAIL_ARGB = 0xFFFF8070,
    BODY_BYTES = 1024 * 1024,
    FIELD_BYTES = 192,
    URL_BYTES = 768,
};

static const char *const BUCKET_URL =
    "https://jbuopkuluyfjwgsrigry.supabase.co/storage/v1/object/public/broadcast/";
static const char *const LINEUP_URL =
    "https://jbuopkuluyfjwgsrigry.supabase.co/storage/v1/object/public/broadcast/lineup.json";
static const char *const CA_FILE = "cacert.pem";

struct response_buffer {
    char *data;
    size_t capacity;
    size_t size;
    bool overflow;
};

struct http_result {
    CURLcode curl_code;
    long http_code;
    size_t bytes;
    char error[CURL_ERROR_SIZE];
};

struct chain_result {
    struct http_result lineup_http;
    struct http_result manifest_http;
    bool dial_found;
    bool toonertia_found;
    bool manifest_path_found;
    bool manifest_channel_ok;
    bool manifest_version_found;
    bool first_item_found;
    bool platform_found;
    unsigned item_count;
    long manifest_version;
    long first_duration;
    char channel_name[FIELD_BYTES];
    char manifest_path[FIELD_BYTES];
    char platform_path[FIELD_BYTES];
    char first_title[FIELD_BYTES];
    char first_year[32];
    char first_id[FIELD_BYTES];
    char first_mp4[FIELD_BYTES];
};

static size_t on_body(char *data, size_t size, size_t count, void *user)
{
    struct response_buffer *body = user;
    const size_t length = size * count;

    if (body == NULL || body->data == NULL || body->capacity == 0)
        return 0;
    if (body->size >= body->capacity - 1u || length > body->capacity - 1u - body->size) {
        body->overflow = true;
        return 0;
    }

    memcpy(body->data + body->size, data, length);
    body->size += length;
    body->data[body->size] = '\0';
    return length;
}

static const char *skip_space(const char *p, const char *end)
{
    while (p < end && isspace((unsigned char)*p))
        p++;
    return p;
}

static const char *find_key(const char *start, const char *end, const char *key)
{
    const char *hit = strstr(start, key);
    return hit != NULL && hit < end ? hit : NULL;
}

static const char *find_previous_key(const char *start, const char *before, const char *key)
{
    const char *p = start;
    const char *last = NULL;

    while (p < before) {
        const char *hit = strstr(p, key);
        if (hit == NULL || hit >= before)
            break;
        last = hit;
        p = hit + 1;
    }
    return last;
}

static bool parse_long_after_key(const char *key_pos, const char *end, long *value)
{
    const char *p = strchr(key_pos, ':');
    char *tail = NULL;

    if (p == NULL || p >= end)
        return false;
    p = skip_space(p + 1, end);
    if (p >= end || (!isdigit((unsigned char)*p) && *p != '-'))
        return false;

    *value = strtol(p, &tail, 10);
    return tail != p && tail <= end;
}

static bool parse_string_after_key(const char *key_pos, const char *end, char *out, size_t out_size)
{
    const char *p = strchr(key_pos, ':');
    size_t written = 0;

    if (out_size == 0)
        return false;
    out[0] = '\0';
    if (p == NULL || p >= end)
        return false;
    p = skip_space(p + 1, end);
    if (p >= end || *p != '"')
        return false;
    p++;

    while (p < end && *p != '"') {
        char ch = *p++;
        if (ch == '\\') {
            if (p >= end)
                return false;
            ch = *p++;
            switch (ch) {
            case 'n': ch = '\n'; break;
            case 'r': ch = '\r'; break;
            case 't': ch = '\t'; break;
            case '"': ch = '"'; break;
            case '\\': ch = '\\'; break;
            default: break;
            }
        }
        if (written + 1u < out_size)
            out[written++] = ch;
    }

    if (p >= end || *p != '"')
        return false;
    out[written] = '\0';
    return true;
}

static struct http_result fetch_url(const char *url, struct response_buffer *body)
{
    struct http_result result;
    CURL *curl = NULL;

    memset(&result, 0, sizeof(result));
    result.curl_code = CURLE_FAILED_INIT;
    body->size = 0;
    body->overflow = false;
    body->data[0] = '\0';

    curl = curl_easy_init();
    if (curl == NULL) {
        snprintf(result.error, sizeof(result.error), "curl_easy_init failed");
        return result;
    }

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, on_body);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, body);
    curl_easy_setopt(curl, CURLOPT_ERRORBUFFER, result.error);
    curl_easy_setopt(curl, CURLOPT_CAINFO, CA_FILE);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_FAILONERROR, 1L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 15000L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 30000L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, 1L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 10L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "Spelunkr360/0.6.2 (Xbox 360 homebrew)");

    result.curl_code = curl_easy_perform(curl);
    (void)curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &result.http_code);
    result.bytes = body->size;
    if (body->overflow && result.error[0] == '\0')
        snprintf(result.error, sizeof(result.error), "response exceeded %u bytes", BODY_BYTES);

    curl_easy_cleanup(curl);
    return result;
}

static bool parse_lineup_53(const char *body, size_t body_size, struct chain_result *result)
{
    const char *end = body + body_size;
    const char *p = body;

    while (p < end) {
        const char *dial = find_key(p, end, "\"dial\"");
        long dial_value = 0;
        if (dial == NULL)
            return false;

        if (parse_long_after_key(dial, end, &dial_value) && dial_value == 53) {
            const char *window_start = dial > body + 4096 ? dial - 4096 : body;
            const char *name_key = find_previous_key(window_start, dial, "\"name\"");
            const char *next_dial = find_key(dial + 6, end, "\"dial\"");
            const char *channel_end = next_dial != NULL ? next_dial : end;
            const char *manifest_key = find_key(dial, channel_end, "\"manifest\"");

            result->dial_found = true;
            if (name_key != NULL)
                (void)parse_string_after_key(name_key, dial, result->channel_name, sizeof(result->channel_name));
            result->toonertia_found = strcmp(result->channel_name, "TOONERTIA") == 0;
            if (manifest_key != NULL)
                result->manifest_path_found = parse_string_after_key(
                    manifest_key, channel_end, result->manifest_path, sizeof(result->manifest_path));
            return result->manifest_path_found;
        }
        p = dial + 6;
    }
    return false;
}

static unsigned count_item_mp4s(const char *body, const char *end)
{
    const char *items = find_key(body, end, "\"items\"");
    const char *stop;
    const char *p;
    unsigned count = 0;

    if (items == NULL)
        return 0;
    p = strchr(items, '[');
    if (p == NULL || p >= end)
        return 0;
    stop = find_key(p, end, "\"bumps\"");
    if (stop == NULL)
        stop = end;

    while (p < stop) {
        const char *hit = find_key(p, stop, "\"mp4\"");
        if (hit == NULL)
            break;
        count++;
        p = hit + 5;
    }
    return count;
}

static void parse_manifest(const char *body, size_t body_size, struct chain_result *result)
{
    const char *end = body + body_size;
    const char *channel_key = find_key(body, end, "\"channel\"");
    const char *version_key = find_key(body, end, "\"version\"");
    const char *platform_key = find_key(body, end, "\"platform\"");
    const char *items_key = find_key(body, end, "\"items\"");
    char manifest_channel[FIELD_BYTES] = { 0 };

    if (channel_key != NULL && parse_string_after_key(channel_key, end, manifest_channel, sizeof(manifest_channel)))
        result->manifest_channel_ok = strcmp(manifest_channel, "toonertia") == 0;
    if (version_key != NULL)
        result->manifest_version_found = parse_long_after_key(version_key, end, &result->manifest_version);
    if (platform_key != NULL)
        result->platform_found = parse_string_after_key(
            platform_key, end, result->platform_path, sizeof(result->platform_path));

    result->item_count = count_item_mp4s(body, end);

    if (items_key != NULL) {
        const char *array = strchr(items_key, '[');
        const char *obj = array != NULL ? strchr(array, '{') : NULL;
        const char *obj_end = obj != NULL ? strchr(obj, '}') : NULL;
        if (obj != NULL && obj_end != NULL && obj_end < end) {
            const char *id_key = find_key(obj, obj_end, "\"id\"");
            const char *mp4_key = find_key(obj, obj_end, "\"mp4\"");
            const char *duration_key = find_key(obj, obj_end, "\"duration\"");
            const char *title_key = find_key(obj, obj_end, "\"title\"");
            const char *year_key = find_key(obj, obj_end, "\"year\"");

            if (id_key != NULL)
                (void)parse_string_after_key(id_key, obj_end, result->first_id, sizeof(result->first_id));
            if (mp4_key != NULL)
                (void)parse_string_after_key(mp4_key, obj_end, result->first_mp4, sizeof(result->first_mp4));
            if (duration_key != NULL)
                (void)parse_long_after_key(duration_key, obj_end, &result->first_duration);
            if (title_key != NULL)
                (void)parse_string_after_key(title_key, obj_end, result->first_title, sizeof(result->first_title));
            if (year_key != NULL)
                (void)parse_string_after_key(year_key, obj_end, result->first_year, sizeof(result->first_year));

            result->first_item_found = result->first_id[0] != '\0' &&
                result->first_mp4[0] != '\0' && result->first_title[0] != '\0';
        }
    }
}

static bool wants_exit(void)
{
    INPUT_STATE input = { 0 };
    if (XamInputGetState(0, 0, &input) != ERROR_SUCCESS)
        return false;
    return (input.gamepad.buttons & (INPUT_GAMEPAD_B | INPUT_GAMEPAD_BACK | INPUT_GAMEPAD_START)) != 0;
}

static NTSTATUS present_blank(uint32_t width, uint32_t height)
{
    uint32_t address = 0;
    NTSTATUS status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
    if (!NT_SUCCESS(status))
        return status;
    xsdk_gpu_resolve(address, width, height, BACKGROUND_ARGB);
    xsdk_present_end();
    return STATUS_SUCCESS;
}

static NTSTATUS present_text(uint32_t width, uint32_t height, const char *text, uint32_t color, bool phase)
{
    uint32_t address = 0;
    NTSTATUS status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
    if (!NT_SUCCESS(status))
        return status;
    xsdk_gpu_set_target(width, height);
    xsdk_text_draw(48, 35, 2, TEXT_ARGB, text);
    xsdk_text_draw(48, 685, 1, color, phase ? "LIVE PRESENT: A" : "LIVE PRESENT: B");
    xsdk_gpu_resolve(address, width, height, BACKGROUND_ARGB);
    xsdk_present_end();
    return STATUS_SUCCESS;
}

int main(void)
{
    char screen[2200];
    char manifest_url[URL_BYTES];
    struct response_buffer body;
    struct chain_result result;
    bool pass = false;
    NTSTATUS status;
    uint32_t width = 0;
    uint32_t height = 0;
    unsigned frame;

    memset(&body, 0, sizeof(body));
    memset(&result, 0, sizeof(result));
    memset(manifest_url, 0, sizeof(manifest_url));

    xsdk_log_write("Spelunkr360 V6B: start manifest chain probe");

    status = xsdk_gpu_open();
    if (!NT_SUCCESS(status))
        return 2;
    status = xsdk_present_open(XSDK_DISPLAY_720P, BUFFERS, SWAP_INTERVAL, &width, &height);
    if (!NT_SUCCESS(status)) {
        (void)xsdk_gpu_close();
        return 3;
    }
    status = xsdk_text_open();
    if (!NT_SUCCESS(status)) {
        xsdk_present_close();
        (void)xsdk_gpu_close();
        return 4;
    }

    (void)present_blank(width, height);
    (void)present_text(width, height,
        "SPELUNKR360 V6B - MANIFEST CHAIN PROBE\n\n"
        "RENDERER: ONLINE\n"
        "STEP 1: FETCHING LIVE LINEUP...\n"
        "STEP 2: FOLLOWING TOONERTIA MANIFEST...",
        PASS_ARGB, true);

    body.data = malloc(BODY_BYTES);
    if (body.data == NULL) {
        snprintf(screen, sizeof(screen),
            "SPELUNKR360 V6B - MANIFEST CHAIN PROBE\n\nMEMORY ALLOCATION FAILED");
        goto show_result;
    }
    body.capacity = BODY_BYTES;

    if (curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
        snprintf(screen, sizeof(screen),
            "SPELUNKR360 V6B - MANIFEST CHAIN PROBE\n\nCURL GLOBAL INIT FAILED");
        goto show_result;
    }

    result.lineup_http = fetch_url(LINEUP_URL, &body);
    if (result.lineup_http.curl_code == CURLE_OK && result.lineup_http.http_code == 200 && !body.overflow)
        (void)parse_lineup_53(body.data, body.size, &result);

    if (result.manifest_path_found && strstr(result.manifest_path, "..") == NULL &&
        strstr(result.manifest_path, "://") == NULL) {
        (void)snprintf(manifest_url, sizeof(manifest_url), "%s%s", BUCKET_URL, result.manifest_path);
        result.manifest_http = fetch_url(manifest_url, &body);
        if (result.manifest_http.curl_code == CURLE_OK && result.manifest_http.http_code == 200 && !body.overflow)
            parse_manifest(body.data, body.size, &result);
    }

    curl_global_cleanup();

    pass = result.lineup_http.curl_code == CURLE_OK && result.lineup_http.http_code == 200 &&
        result.dial_found && result.toonertia_found && result.manifest_path_found &&
        result.manifest_http.curl_code == CURLE_OK && result.manifest_http.http_code == 200 &&
        result.manifest_channel_ok && result.manifest_version_found &&
        result.item_count > 0 && result.first_item_found;

    xsdk_log_write(
        "Spelunkr360 V6B: lineup=%ld/%u manifest=%ld/%u path=%s version=%ld items=%u first=%s id=%s platform=%s pass=%u",
        result.lineup_http.http_code, (unsigned)result.lineup_http.bytes,
        result.manifest_http.http_code, (unsigned)result.manifest_http.bytes,
        result.manifest_path[0] ? result.manifest_path : "(none)", result.manifest_version,
        result.item_count, result.first_title[0] ? result.first_title : "(none)",
        result.first_id[0] ? result.first_id : "(none)",
        result.platform_path[0] ? result.platform_path : "(none)", pass ? 1u : 0u);

    snprintf(screen, sizeof(screen),
        "SPELUNKR360 V6B - MANIFEST CHAIN PROBE\n"
        "LIVE TOONERTIA BROADCAST DATA\n\n"
        "LINEUP HTTP: %ld   BYTES: %u\n"
        "CHANNEL 53 / TOONERTIA: %s\n"
        "MANIFEST: %s\n\n"
        "MANIFEST HTTP: %ld   BYTES: %u\n"
        "CHANNEL FIELD: %s\n"
        "VERSION: %ld\n"
        "PROGRAM ITEMS: %u\n"
        "PLATFORM FOUND: %s\n\n"
        "FIRST TITLE: %s%s%s\n"
        "ARCHIVE ID: %s\n"
        "DURATION: %ld SEC\n\n"
        "TOONERTIA MANIFEST TEST: %s\n\n"
        "B/BACK/START = Aurora | auto-return ~20 sec",
        result.lineup_http.http_code, (unsigned)result.lineup_http.bytes,
        result.toonertia_found ? "FOUND" : "NOT FOUND",
        result.manifest_path[0] ? result.manifest_path : "(not parsed)",
        result.manifest_http.http_code, (unsigned)result.manifest_http.bytes,
        result.manifest_channel_ok ? "toonertia" : "(mismatch/not parsed)",
        result.manifest_version, result.item_count,
        result.platform_found ? "YES" : "NO",
        result.first_title[0] ? result.first_title : "(not parsed)",
        result.first_year[0] ? " (" : "", result.first_year[0] ? result.first_year : "",
        result.first_id[0] ? result.first_id : "(not parsed)",
        result.first_duration,
        pass ? "PASS" : "FAIL");

show_result:
    for (frame = 0; frame < AUTO_EXIT_FRAMES; frame++) {
        const bool phase = ((frame / 30u) & 1u) == 0u;
        if (wants_exit())
            break;
        status = present_text(width, height, screen, pass ? PASS_ARGB : FAIL_ARGB, phase);
        if (!NT_SUCCESS(status))
            break;
    }

    if (body.data != NULL)
        free(body.data);
    xsdk_text_close();
    xsdk_present_close();
    (void)xsdk_gpu_close();
    return 0;
}
