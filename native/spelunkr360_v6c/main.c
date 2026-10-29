/* Spelunkr360 V6C - exact live "what's on now" probe. */
#include <curl/curl.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "schedule_core.h"
#include "xsdk/gpu.h"
#include "xsdk/kernel.h"
#include "xsdk/log.h"
#include "xsdk/present.h"
#include "xsdk/text.h"

enum {
    BUFFERS = 2, SWAP_INTERVAL = 1, BEGIN_TIMEOUT_MS = 5000,
    AUTO_EXIT_FRAMES = 1200, BACKGROUND_ARGB = 0xFF102418,
    TEXT_ARGB = 0xFFF0F0E8, PASS_ARGB = 0xFF8FE388,
    FAIL_ARGB = 0xFFFF8070, BODY_BYTES = 1024 * 1024,
};

static const char *const BUCKET_URL =
    "https://jbuopkuluyfjwgsrigry.supabase.co/storage/v1/object/public/broadcast/";
static const char *const LINEUP_URL =
    "https://jbuopkuluyfjwgsrigry.supabase.co/storage/v1/object/public/broadcast/lineup.json";
static const char *const CA_FILE = "cacert.pem";

struct response_buffer { char *data; size_t capacity; size_t size; bool overflow; };
struct http_result {
    CURLcode curl_code;
    long http_code;
    size_t bytes;
    char error[CURL_ERROR_SIZE];
    char date_header[96];
    int64_t server_ms;
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

static unsigned char ascii_lower(unsigned char c)
{
    return (c >= 'A' && c <= 'Z') ? (unsigned char)(c + ('a' - 'A')) : c;
}

static size_t on_header(char *data, size_t size, size_t count, void *user)
{
    struct http_result *result = user;
    const size_t length = size * count;
    size_t begin;
    size_t end;
    size_t copy;

    if (result == NULL || data == NULL || length < 5u)
        return length;

    if (ascii_lower((unsigned char)data[0]) != 'd' ||
        ascii_lower((unsigned char)data[1]) != 'a' ||
        ascii_lower((unsigned char)data[2]) != 't' ||
        ascii_lower((unsigned char)data[3]) != 'e' ||
        data[4] != ':')
        return length;

    begin = 5u;
    while (begin < length && (data[begin] == ' ' || data[begin] == '\t'))
        begin++;
    end = length;
    while (end > begin &&
           (data[end - 1u] == '\r' || data[end - 1u] == '\n' ||
            data[end - 1u] == ' ' || data[end - 1u] == '\t'))
        end--;

    copy = end - begin;
    if (copy >= sizeof(result->date_header))
        copy = sizeof(result->date_header) - 1u;
    memcpy(result->date_header, data + begin, copy);
    result->date_header[copy] = '\0';
    return length;
}

static struct http_result fetch_url(const char *url, struct response_buffer *body)
{
    struct http_result result;
    CURL *curl = NULL;
    time_t server_time;

    memset(&result, 0, sizeof(result));
    result.curl_code = CURLE_FAILED_INIT;
    result.server_ms = -1;
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
    curl_easy_setopt(curl, CURLOPT_HEADERFUNCTION, on_header);
    curl_easy_setopt(curl, CURLOPT_HEADERDATA, &result);
    curl_easy_setopt(curl, CURLOPT_ERRORBUFFER, result.error);
    curl_easy_setopt(curl, CURLOPT_CAINFO, CA_FILE);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_FAILONERROR, 1L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 15000L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 30000L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, 1L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 10L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "Spelunkr360/0.6.3.2 (Xbox 360 homebrew)");
    result.curl_code = curl_easy_perform(curl);
    (void)curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &result.http_code);
    result.bytes = body->size;
    if (body->overflow && result.error[0] == '\0')
        snprintf(result.error, sizeof(result.error), "response exceeded %u bytes", BODY_BYTES);

    if (result.date_header[0] != '\0') {
        server_time = curl_getdate(result.date_header, NULL);
        if (server_time != (time_t)-1)
            result.server_ms = (int64_t)server_time * 1000LL;
    }

    curl_easy_cleanup(curl);
    return result;
}

/* The network-wide platform data is schema engine 1 even when a channel
 * manifest uses schedule engine 5. schedule_core only needs its bumps, so
 * adapt that schema marker before feeding it to the schedule parser. */
static void adapt_platform_schema_marker(char *json)
{
    char *key;
    char *value;
    if (json == NULL)
        return;
    key = strstr(json, "\"engine\"");
    if (key == NULL)
        return;
    value = strchr(key, ':');
    if (value == NULL)
        return;
    value++;
    while (*value == ' ' || *value == '\t' || *value == '\r' || *value == '\n')
        value++;
    if (*value == '1')
        *value = '5';
}

static int64_t kernel_realtime_ms(void)
{
    static const int64_t NT_UNIX_EPOCH_100NS = 116444736000000000LL;
    uint64_t nt_time = 0;
    int64_t unix_ticks;

    KeQuerySystemTime(&nt_time);
    unix_ticks = (int64_t)nt_time - NT_UNIX_EPOCH_100NS;
    if (unix_ticks < 0)
        return -1;
    return unix_ticks / 10000LL;
}

static int64_t best_server_time_ms(
    const struct http_result *preferred,
    const struct http_result *second,
    const struct http_result *third,
    const char **source)
{
    if (preferred != NULL && preferred->server_ms >= 0) {
        if (source != NULL) *source = "HTTP DATE";
        return preferred->server_ms;
    }
    if (second != NULL && second->server_ms >= 0) {
        if (source != NULL) *source = "HTTP DATE";
        return second->server_ms;
    }
    if (third != NULL && third->server_ms >= 0) {
        if (source != NULL) *source = "HTTP DATE";
        return third->server_ms;
    }
    {
        const int64_t kernel_ms = kernel_realtime_ms();
        if (kernel_ms >= 0 && source != NULL)
            *source = "XBOX KERNEL";
        return kernel_ms;
    }
}

static void format_hms(int64_t ms, char *out, size_t out_size)
{
    int64_t s, h, m;
    if (ms < 0) ms = 0;
    s = ms / 1000LL; h = s / 3600LL; m = (s % 3600LL) / 60LL; s %= 60LL;
    snprintf(out, out_size, "%02" PRId64 ":%02" PRId64 ":%02" PRId64, h, m, s);
}

static bool wants_exit(void)
{
    INPUT_STATE input = { 0 };
    if (XamInputGetState(0, 0, &input) != ERROR_SUCCESS) return false;
    return (input.gamepad.buttons & (INPUT_GAMEPAD_B | INPUT_GAMEPAD_BACK | INPUT_GAMEPAD_START)) != 0;
}

static NTSTATUS present_blank(uint32_t width, uint32_t height)
{
    uint32_t address = 0;
    NTSTATUS status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
    if (!NT_SUCCESS(status)) return status;
    xsdk_gpu_resolve(address, width, height, BACKGROUND_ARGB);
    xsdk_present_end();
    return STATUS_SUCCESS;
}

static NTSTATUS present_text(uint32_t width, uint32_t height, const char *text, uint32_t color, bool phase)
{
    uint32_t address = 0;
    NTSTATUS status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
    if (!NT_SUCCESS(status)) return status;
    xsdk_gpu_set_target(width, height);
    xsdk_text_draw(42, 28, 2, TEXT_ARGB, text);
    xsdk_text_draw(42, 685, 1, color, phase ? "LIVE PRESENT: A" : "LIVE PRESENT: B");
    xsdk_gpu_resolve(address, width, height, BACKGROUND_ARGB);
    xsdk_present_end();
    return STATUS_SUCCESS;
}

int main(void)
{
    struct response_buffer body = { 0 };
    struct sp_schedule *schedule = NULL;
    struct sp_pointer pointer;
    struct sp_now now_result;
    struct http_result lineup_http = { 0 }, manifest_http = { 0 }, platform_http = { 0 };
    char channel_name[64] = { 0 }, channel_id[64] = { 0 };
    char manifest_url[SP_URL_BYTES] = { 0 }, platform_url[SP_URL_BYTES] = { 0 };
    char error[256] = { 0 }, screen[3200], offset_text[32], length_text[32];
    int64_t selected_ms = -1, final_ms = -1;
    const char *time_source = "NONE";
    bool pass = false, curl_ready = false;
    NTSTATUS status;
    uint32_t width = 0, height = 0;
    unsigned frame;

    memset(&pointer, 0, sizeof(pointer));
    memset(&now_result, 0, sizeof(now_result));
    xsdk_log_write("Spelunkr360 V6C: start exact what-is-on-now probe");

    status = xsdk_gpu_open(); if (!NT_SUCCESS(status)) return 2;
    status = xsdk_present_open(XSDK_DISPLAY_720P, BUFFERS, SWAP_INTERVAL, &width, &height);
    if (!NT_SUCCESS(status)) { (void)xsdk_gpu_close(); return 3; }
    status = xsdk_text_open();
    if (!NT_SUCCESS(status)) { xsdk_present_close(); (void)xsdk_gpu_close(); return 4; }

    (void)present_blank(width, height);
    (void)present_text(width, height,
        "SPELUNKR360 V6C - WHAT'S ON NOW\n\nRENDERER: ONLINE\n"
        "FETCHING LIVE TOONERTIA SCHEDULE...\nSYNCING CURRENT TIME FROM HTTPS SERVER...",
        PASS_ARGB, true);

    body.data = malloc(BODY_BYTES);
    schedule = calloc(1, sizeof(*schedule));
    if (body.data == NULL || schedule == NULL) { snprintf(error, sizeof(error), "memory allocation failed"); goto show_result; }
    body.capacity = BODY_BYTES; body.data[0] = '\0';
    if (curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) { snprintf(error, sizeof(error), "curl_global_init failed"); goto show_result; }
    curl_ready = true;

    lineup_http = fetch_url(LINEUP_URL, &body);
    selected_ms = best_server_time_ms(&lineup_http, NULL, NULL, &time_source);
    if (lineup_http.curl_code != CURLE_OK || lineup_http.http_code != 200 || selected_ms < 0) {
        snprintf(error, sizeof(error), "lineup/time failed: curl=%d HTTP=%ld date=%s",
            (int)lineup_http.curl_code, lineup_http.http_code,
            lineup_http.date_header[0] ? lineup_http.date_header : "(none)");
        goto show_result;
    }
    if (sp_parse_lineup_53(body.data, body.size, selected_ms, &pointer,
            channel_name, sizeof(channel_name), channel_id, sizeof(channel_id), error, sizeof(error)) != 0) goto show_result;
    if (strcmp(channel_name, "TOONERTIA") != 0 || strcmp(channel_id, "toonertia") != 0) {
        snprintf(error, sizeof(error), "channel 53 identity mismatch"); goto show_result;
    }
    if (snprintf(manifest_url, sizeof(manifest_url), "%s%s", BUCKET_URL, pointer.manifest) >= (int)sizeof(manifest_url)) {
        snprintf(error, sizeof(error), "manifest URL too long"); goto show_result;
    }
    manifest_http = fetch_url(manifest_url, &body);
    if (manifest_http.curl_code != CURLE_OK || manifest_http.http_code != 200) {
        snprintf(error, sizeof(error), "manifest failed: curl=%d HTTP=%ld", (int)manifest_http.curl_code, manifest_http.http_code); goto show_result;
    }
    if (sp_parse_manifest(body.data, body.size, schedule, error, sizeof(error)) != 0) goto show_result;
    if (schedule->version != pointer.version || strcmp(schedule->channel, "toonertia") != 0) {
        snprintf(error, sizeof(error), "manifest version/channel mismatch"); goto show_result;
    }
    if (schedule->engine != 5 || schedule->has_block || schedule->has_ads) {
        snprintf(error, sizeof(error), "unsupported live schedule shape: engine=%d block=%u ads=%u",
            schedule->engine, schedule->has_block ? 1u : 0u, schedule->has_ads ? 1u : 0u); goto show_result;
    }
    if (schedule->platform_path[0] == '\0' ||
        snprintf(platform_url, sizeof(platform_url), "%s%s", BUCKET_URL, schedule->platform_path) >= (int)sizeof(platform_url)) {
        snprintf(error, sizeof(error), "platform path/URL invalid"); goto show_result;
    }
    platform_http = fetch_url(platform_url, &body);
    if (platform_http.curl_code != CURLE_OK || platform_http.http_code != 200) {
        snprintf(error, sizeof(error), "platform failed: curl=%d HTTP=%ld", (int)platform_http.curl_code, platform_http.http_code); goto show_result;
    }
    adapt_platform_schema_marker(body.data);
    if (sp_parse_platform(body.data, body.size, schedule, error, sizeof(error)) != 0) goto show_result;

    final_ms = best_server_time_ms(&platform_http, &manifest_http, &lineup_http, &time_source);
    if (final_ms < 0) {
        snprintf(error, sizeof(error), "no usable HTTP Date or Xbox kernel time");
        goto show_result;
    }
    if (sp_find_now(schedule, &pointer, final_ms, &now_result, error, sizeof(error)) != 0 || !now_result.ok) goto show_result;
    pass = true;

show_result:
    if (pass) {
        format_hms(now_result.offset_ms, offset_text, sizeof(offset_text));
        format_hms(now_result.segment_length_ms, length_text, sizeof(length_text));
        if (now_result.kind == SP_SEGMENT_SHOW) {
            snprintf(screen, sizeof(screen),
                "SPELUNKR360 V6C - WHAT'S ON NOW\nCH 53 - TOONERTIA\n\n"
                "LINEUP HTTP: %ld    MANIFEST HTTP: %ld    PLATFORM HTTP: %ld\n"
                "TIME SOURCE: %s\nVERSION: %d    ENGINE: %d    CYCLE: %d    ENTRY: %d\n"
                "ITEMS: %d    CHANNEL BUMPS: %d    PLATFORM BUMPS: %d\n\n"
                "CURRENT SEGMENT: SHOW\nNOW PLAYING: %s\nYEAR: %s\nPOSITION: %s / %s\n"
                "ARCHIVE ID: %s\nMEDIA URL FOUND: %s\n\nWHAT'S ON NOW TEST: PASS\n\n"
                "Press B, BACK, or START to return to Aurora.\nAuto-return after about 20 seconds.",
                lineup_http.http_code, manifest_http.http_code, platform_http.http_code, time_source,
                now_result.version, schedule->engine, now_result.cycle, now_result.entry_index,
                schedule->item_count, schedule->channel_bump_count, schedule->platform_bump_count,
                now_result.title[0] ? now_result.title : "(untitled)", now_result.year[0] ? now_result.year : "?",
                offset_text, length_text, now_result.id[0] ? now_result.id : "(none)", now_result.archive_url[0] ? "YES" : "NO");
        } else {
            snprintf(screen, sizeof(screen),
                "SPELUNKR360 V6C - WHAT'S ON NOW\nCH 53 - TOONERTIA\n\n"
                "LINEUP HTTP: %ld    MANIFEST HTTP: %ld    PLATFORM HTTP: %ld\n"
                "TIME SOURCE: %s\nVERSION: %d    ENGINE: %d    CYCLE: %d    ENTRY: %d\n"
                "ITEMS: %d    CHANNEL BUMPS: %d    PLATFORM BUMPS: %d\n\n"
                "CURRENT SEGMENT: BUMP\nPOSITION: %s / %s\nCHANNEL BUMP: %s\nPLATFORM BUMP: %s\n"
                "MEDIA URL FOUND: N/A (TEXT/MUSIC BUMP)\n\nWHAT'S ON NOW TEST: PASS\n\n"
                "Press B, BACK, or START to return to Aurora.\nAuto-return after about 20 seconds.",
                lineup_http.http_code, manifest_http.http_code, platform_http.http_code, time_source,
                now_result.version, schedule->engine, now_result.cycle, now_result.entry_index,
                schedule->item_count, schedule->channel_bump_count, schedule->platform_bump_count,
                offset_text, length_text,
                now_result.channel_bump_id[0] ? now_result.channel_bump_id : "(none)",
                now_result.platform_bump_id[0] ? now_result.platform_bump_id : "(none)");
        }
    } else {
        snprintf(screen, sizeof(screen),
            "SPELUNKR360 V6C - WHAT'S ON NOW\nCH 53 - TOONERTIA\n\n"
            "LINEUP HTTP: %ld\nMANIFEST HTTP: %ld\nPLATFORM HTTP: %ld\n"
            "LINEUP DATE: %s\nPLATFORM DATE: %s\n\n"
            "WHAT'S ON NOW TEST: FAIL\nERROR: %s\n\nPress B, BACK, or START to return to Aurora.\nAuto-return after about 20 seconds.",
            lineup_http.http_code, manifest_http.http_code, platform_http.http_code,
            lineup_http.date_header[0] ? lineup_http.date_header : "(none)",
            platform_http.date_header[0] ? platform_http.date_header : "(none)",
            error[0] ? error : "unknown failure");
    }

    xsdk_log_write("Spelunkr360 V6C: pass=%u time=%s lineup_date=%s manifest_date=%s platform_date=%s kind=%s cycle=%d entry=%d start=%" PRId64 " len=%" PRId64 " off=%" PRId64 " title=%s archive=%s error=%s",
        pass ? 1u : 0u, time_source,
        lineup_http.date_header[0] ? lineup_http.date_header : "(none)",
        manifest_http.date_header[0] ? manifest_http.date_header : "(none)",
        platform_http.date_header[0] ? platform_http.date_header : "(none)",
        sp_segment_kind_name(now_result.kind), now_result.cycle, now_result.entry_index,
        now_result.segment_start_ms, now_result.segment_length_ms, now_result.offset_ms,
        now_result.title[0] ? now_result.title : "(none)", now_result.archive_url[0] ? now_result.archive_url : "(none)",
        error[0] ? error : "(none)");

    if (curl_ready) curl_global_cleanup();
    free(schedule); free(body.data);
    for (frame = 0; frame < AUTO_EXIT_FRAMES; frame++) {
        if (wants_exit()) break;
        status = present_text(width, height, screen, pass ? PASS_ARGB : FAIL_ARGB, ((frame / 30u) & 1u) == 0u);
        if (!NT_SUCCESS(status)) break;
    }
    xsdk_text_close(); xsdk_present_close(); (void)xsdk_gpu_close();
    return pass ? 0 : 1;
}
