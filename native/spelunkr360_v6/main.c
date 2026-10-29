/* Spelunkr360 V6 direct-lineup probe.
 *
 * V5 proved real Xbox 360 DNS, HTTPS/TLS, HTTP 200, libcurl/Mbed TLS and the
 * V4 renderer can all coexist on hardware. The V5 content check failed only
 * because /directory is an HTML/JS shell. V6 talks to Spelunkr's public
 * broadcast storage directly, downloads lineup.json, finds dial 53, extracts
 * the channel name/id and first manifest path, and shows the result on-screen.
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
};

static const char *const LINEUP_URL =
    "https://jbuopkuluyfjwgsrigry.supabase.co/storage/v1/object/public/broadcast/lineup.json";
static const char *const CA_FILE = "cacert.pem";

struct response_buffer {
    char data[BODY_BYTES];
    size_t size;
    bool overflow;
};

struct lineup_result {
    CURLcode curl_code;
    long http_code;
    size_t bytes;
    bool dial_found;
    bool toonertia_found;
    bool manifest_found;
    unsigned offered_channels;
    char id[FIELD_BYTES];
    char name[FIELD_BYTES];
    char manifest[FIELD_BYTES];
    char error[CURL_ERROR_SIZE];
};

static size_t on_body(char *data, size_t size, size_t count, void *user)
{
    struct response_buffer *body = user;
    const size_t length = size * count;

    if (length > BODY_BYTES - 1u - body->size) {
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
    const size_t key_len = strlen(key);
    const char *p = start;

    while (p < end) {
        const char *hit = strstr(p, key);
        if (hit == NULL || hit >= end)
            return NULL;
        if ((size_t)(end - hit) >= key_len)
            return hit;
        p = hit + 1;
    }
    return NULL;
}

static bool parse_int_after_key(const char *key_pos, const char *end, long *value)
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

static unsigned count_numeric_dials(const char *start, const char *end)
{
    unsigned count = 0;
    const char *p = start;

    while (p < end) {
        const char *dial = find_key(p, end, "\"dial\"");
        long value = 0;
        if (dial == NULL)
            break;
        if (parse_int_after_key(dial, end, &value))
            count++;
        p = dial + 6;
    }
    return count;
}

static bool parse_channel_53(const char *body, size_t body_size, struct lineup_result *result)
{
    const char *end = body + body_size;
    const char *p = body;

    result->offered_channels = count_numeric_dials(body, end);

    while (p < end) {
        const char *dial = find_key(p, end, "\"dial\"");
        long dial_value = 0;
        if (dial == NULL)
            return false;

        if (parse_int_after_key(dial, end, &dial_value) && dial_value == 53) {
            const char *window_start = dial > body + 4096 ? dial - 4096 : body;
            const char *id_key = find_previous_key(window_start, dial, "\"id\"");
            const char *name_key = find_previous_key(window_start, dial, "\"name\"");
            const char *next_dial = find_key(dial + 6, end, "\"dial\"");
            const char *channel_end = next_dial != NULL ? next_dial : end;
            const char *manifest_key = find_key(dial, channel_end, "\"manifest\"");

            result->dial_found = true;
            if (id_key != NULL)
                (void)parse_string_after_key(id_key, dial, result->id, sizeof(result->id));
            if (name_key != NULL)
                (void)parse_string_after_key(name_key, dial, result->name, sizeof(result->name));
            if (manifest_key != NULL) {
                result->manifest_found = parse_string_after_key(
                    manifest_key, channel_end, result->manifest, sizeof(result->manifest));
            }
            result->toonertia_found = strcmp(result->name, "TOONERTIA") == 0;
            return true;
        }
        p = dial + 6;
    }

    return false;
}

static struct lineup_result fetch_lineup(void)
{
    struct lineup_result result;
    struct response_buffer body;
    CURL *curl = NULL;

    memset(&result, 0, sizeof(result));
    memset(&body, 0, sizeof(body));
    result.curl_code = CURLE_FAILED_INIT;

    if (curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
        snprintf(result.error, sizeof(result.error), "curl_global_init failed");
        return result;
    }

    curl = curl_easy_init();
    if (curl == NULL) {
        snprintf(result.error, sizeof(result.error), "curl_easy_init failed");
        curl_global_cleanup();
        return result;
    }

    curl_easy_setopt(curl, CURLOPT_URL, LINEUP_URL);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, on_body);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);
    curl_easy_setopt(curl, CURLOPT_ERRORBUFFER, result.error);
    curl_easy_setopt(curl, CURLOPT_CAINFO, CA_FILE);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_FAILONERROR, 1L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 15000L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, 1L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 10L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "Spelunkr360/0.6 (Xbox 360 homebrew)");

    result.curl_code = curl_easy_perform(curl);
    (void)curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &result.http_code);
    result.bytes = body.size;

    if (result.curl_code == CURLE_OK && !body.overflow)
        (void)parse_channel_53(body.data, body.size, &result);

    if (body.overflow && result.error[0] == '\0')
        snprintf(result.error, sizeof(result.error), "lineup exceeded %u bytes", BODY_BYTES);

    curl_easy_cleanup(curl);
    curl_global_cleanup();
    return result;
}

static bool wants_exit(void)
{
    INPUT_STATE input = { 0 };
    if (XamInputGetState(0, 0, &input) != ERROR_SUCCESS)
        return false;

    const uint16_t buttons = input.gamepad.buttons;
    return (buttons & (INPUT_GAMEPAD_B | INPUT_GAMEPAD_BACK | INPUT_GAMEPAD_START)) != 0;
}

int main(void)
{
    char screen[1800];
    struct lineup_result lineup;
    bool pass;

    xsdk_log_write("Spelunkr360 V6: direct lineup probe: %s", LINEUP_URL);
    lineup = fetch_lineup();
    pass = lineup.curl_code == CURLE_OK && lineup.http_code == 200 &&
        lineup.dial_found && lineup.toonertia_found && lineup.manifest_found;

    xsdk_log_write(
        "Spelunkr360 V6: curl=%d (%s), HTTP=%ld, bytes=%u, channels=%u, dial53=%u, toonertia=%u, id=%s, manifest=%s%s%s",
        (int)lineup.curl_code, curl_easy_strerror(lineup.curl_code), lineup.http_code,
        (unsigned)lineup.bytes, lineup.offered_channels,
        lineup.dial_found ? 1u : 0u, lineup.toonertia_found ? 1u : 0u,
        lineup.id[0] ? lineup.id : "(none)", lineup.manifest[0] ? lineup.manifest : "(none)",
        lineup.error[0] ? ", error=" : "", lineup.error);

    snprintf(screen, sizeof(screen),
        "SPELUNKR360 V6 - DIRECT LINEUP PROBE\n"
        "PUBLIC BROADCAST DATA\n\n"
        "HTTPS: %s\n"
        "HTTP STATUS: %ld\n"
        "RECEIVED: %u BYTES\n"
        "NUMERIC CHANNELS SEEN: %u\n\n"
        "CHANNEL 53 FOUND: %s\n"
        "NAME: %s\n"
        "ID: %s\n"
        "TOONERTIA MATCH: %s\n"
        "MANIFEST FOUND: %s\n"
        "MANIFEST: %s\n\n"
        "%s\n\n"
        "Press B, BACK, or START to return to Aurora.\n"
        "Auto-return after about 20 seconds.",
        lineup.curl_code == CURLE_OK ? "CONNECTED" : curl_easy_strerror(lineup.curl_code),
        lineup.http_code, (unsigned)lineup.bytes, lineup.offered_channels,
        lineup.dial_found ? "YES" : "NO",
        lineup.name[0] ? lineup.name : "(not parsed)",
        lineup.id[0] ? lineup.id : "(not parsed)",
        lineup.toonertia_found ? "YES" : "NO",
        lineup.manifest_found ? "YES" : "NO",
        lineup.manifest[0] ? lineup.manifest : "(not parsed)",
        pass ? "DIRECT SPELUNKR LINEUP TEST: PASS" : "DIRECT SPELUNKR LINEUP TEST: FAIL");

    NTSTATUS status = xsdk_gpu_open();
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V6: xsdk_gpu_open failed: 0x%08X", (unsigned)status);
        return 2;
    }

    uint32_t width = 0;
    uint32_t height = 0;
    status = xsdk_present_open(XSDK_DISPLAY_720P, BUFFERS, SWAP_INTERVAL, &width, &height);
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V6: xsdk_present_open failed: 0x%08X", (unsigned)status);
        (void)xsdk_gpu_close();
        return 3;
    }

    status = xsdk_text_open();
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V6: xsdk_text_open failed: 0x%08X", (unsigned)status);
        xsdk_present_close();
        (void)xsdk_gpu_close();
        return 4;
    }

    for (uint32_t frame = 0; frame < AUTO_EXIT_FRAMES; frame++) {
        uint32_t address = 0;
        status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
        if (!NT_SUCCESS(status)) {
            xsdk_log_write("Spelunkr360 V6: present begin failed at frame %u: 0x%08X",
                (unsigned)frame, (unsigned)status);
            break;
        }

        if (frame != 0) {
            xsdk_gpu_set_target(width, height);
            xsdk_text_draw(55, 45, 2, TEXT_ARGB, screen);
            xsdk_text_draw(55, 650, 2, pass ? PASS_ARGB : FAIL_ARGB,
                ((frame / 30u) & 1u) ? "LIVE PRESENT: A" : "LIVE PRESENT: B");
        }

        xsdk_gpu_resolve(address, width, height, BACKGROUND_ARGB);
        xsdk_present_end();

        if (wants_exit()) {
            xsdk_log_write("Spelunkr360 V6: controller exit at frame %u", (unsigned)frame);
            break;
        }
    }

    xsdk_text_close();
    xsdk_present_close();
    status = xsdk_gpu_close();
    if (!NT_SUCCESS(status))
        xsdk_log_write("Spelunkr360 V6: xsdk_gpu_close failed: 0x%08X", (unsigned)status);

    xsdk_log_write("Spelunkr360 V6: normal title exit to dashboard, lineup_pass=%u",
        pass ? 1u : 0u);
    return pass ? 0 : 6;
}
