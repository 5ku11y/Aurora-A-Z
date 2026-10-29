/* Spelunkr360 V5 native-network probe.
 *
 * V4 proved the real Xbox 360 GPU present loop, XDBF title metadata, and a
 * clean timed return to Aurora. V5 keeps that proven renderer and adds a
 * deliberately small native HTTPS test: fetch Spelunkr's public directory,
 * verify HTTP 200, and look for Channel 53 / TOONERTIA in the returned page.
 * No browser engine is involved. This is the first step toward a native
 * Spelunkr client that reads the schedule and plays Archive media directly.
 */

#include <curl/curl.h>

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
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
    BODY_BYTES = 512 * 1024,
};

static const char *const DIRECTORY_URL = "https://spelunkr.tv/directory";
static const char *const CA_FILE = "cacert.pem";

struct response_buffer {
    char data[BODY_BYTES];
    size_t size;
    bool overflow;
};

struct network_result {
    CURLcode curl_code;
    long http_code;
    size_t bytes;
    bool found_toonertia;
    bool found_channel_53;
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

static struct network_result fetch_directory(void)
{
    struct network_result result;
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

    curl_easy_setopt(curl, CURLOPT_URL, DIRECTORY_URL);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, on_body);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);
    curl_easy_setopt(curl, CURLOPT_ERRORBUFFER, result.error);
    curl_easy_setopt(curl, CURLOPT_CAINFO, CA_FILE);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_FAILONERROR, 1L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 15000L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, 1L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 10L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "Spelunkr360/0.5 (Xbox 360 homebrew)");

    result.curl_code = curl_easy_perform(curl);
    (void)curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &result.http_code);
    result.bytes = body.size;

    if (result.curl_code == CURLE_OK && !body.overflow) {
        result.found_toonertia = strstr(body.data, "TOONERTIA") != NULL;
        result.found_channel_53 = strstr(body.data, ">53<") != NULL ||
            strstr(body.data, "53") != NULL;
    }

    if (body.overflow && result.error[0] == '\0')
        snprintf(result.error, sizeof(result.error), "response exceeded %u bytes", BODY_BYTES);

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
    char screen[1400];
    struct network_result network;
    bool network_pass;

    xsdk_log_write("Spelunkr360 V5: start native HTTPS probe: %s", DIRECTORY_URL);
    network = fetch_directory();
    network_pass = network.curl_code == CURLE_OK && network.http_code == 200 &&
        network.found_toonertia && network.found_channel_53;

    xsdk_log_write(
        "Spelunkr360 V5: curl=%d (%s), HTTP=%ld, bytes=%u, channel53=%u, toonertia=%u%s%s",
        (int)network.curl_code, curl_easy_strerror(network.curl_code), network.http_code,
        (unsigned)network.bytes, network.found_channel_53 ? 1u : 0u,
        network.found_toonertia ? 1u : 0u,
        network.error[0] ? ", error=" : "", network.error);

    snprintf(screen, sizeof(screen),
        "SPELUNKR360 V5 - NATIVE CLIENT PROBE\n"
        "CH 53 - TOONERTIA\n\n"
        "HTTPS: %s\n"
        "HTTP STATUS: %ld\n"
        "RECEIVED: %u BYTES\n"
        "TOONERTIA FOUND: %s\n"
        "CHANNEL 53 FOUND: %s\n\n"
        "%s\n\n"
        "Press B, BACK, or START to return to Aurora.\n"
        "Auto-return after about 20 seconds.",
        network.curl_code == CURLE_OK ? "CONNECTED" : curl_easy_strerror(network.curl_code),
        network.http_code, (unsigned)network.bytes,
        network.found_toonertia ? "YES" : "NO",
        network.found_channel_53 ? "YES" : "NO",
        network_pass ? "NATIVE SPELUNKR NETWORK TEST: PASS" : "NATIVE SPELUNKR NETWORK TEST: FAIL");

    NTSTATUS status = xsdk_gpu_open();
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V5: xsdk_gpu_open failed: 0x%08X", (unsigned)status);
        return 2;
    }

    uint32_t width = 0;
    uint32_t height = 0;
    status = xsdk_present_open(XSDK_DISPLAY_720P, BUFFERS, SWAP_INTERVAL, &width, &height);
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V5: xsdk_present_open failed: 0x%08X", (unsigned)status);
        (void)xsdk_gpu_close();
        return 3;
    }

    status = xsdk_text_open();
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V5: xsdk_text_open failed: 0x%08X", (unsigned)status);
        xsdk_present_close();
        (void)xsdk_gpu_close();
        return 4;
    }

    for (uint32_t frame = 0; frame < AUTO_EXIT_FRAMES; frame++) {
        uint32_t address = 0;
        status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
        if (!NT_SUCCESS(status)) {
            xsdk_log_write("Spelunkr360 V5: present begin failed at frame %u: 0x%08X",
                (unsigned)frame, (unsigned)status);
            break;
        }

        if (frame != 0) {
            xsdk_gpu_set_target(width, height);
            xsdk_text_draw(70, 70, 2, TEXT_ARGB, screen);
            xsdk_text_draw(70, 560, 2, network_pass ? PASS_ARGB : FAIL_ARGB,
                ((frame / 30u) & 1u) ? "LIVE PRESENT: A" : "LIVE PRESENT: B");
        }

        xsdk_gpu_resolve(address, width, height, BACKGROUND_ARGB);
        xsdk_present_end();

        if (wants_exit()) {
            xsdk_log_write("Spelunkr360 V5: controller exit at frame %u", (unsigned)frame);
            break;
        }
    }

    xsdk_text_close();
    xsdk_present_close();
    status = xsdk_gpu_close();
    if (!NT_SUCCESS(status))
        xsdk_log_write("Spelunkr360 V5: xsdk_gpu_close failed: 0x%08X", (unsigned)status);

    xsdk_log_write("Spelunkr360 V5: normal title exit to dashboard, network_pass=%u",
        network_pass ? 1u : 0u);
    return network_pass ? 0 : 5;
}
