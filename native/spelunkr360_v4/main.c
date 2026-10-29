/* Spelunkr360 V4 hardware-safe display/title probe.
 *
 * V2 proved the XEX executes on Wolf's real Xbox 360.
 * V3 moved to xsdk's hardware present path, but its loop queued text after a
 * resolve without restoring the eDRAM render target.  xsdk_gpu_resolve()
 * invalidates that target.  V4 restores it before every draw, keeps a simple
 * live A/B pulse on screen, and returns through xsdk's normal title runtime.
 */

#include <stdbool.h>
#include <stdint.h>

#include "xsdk/gpu.h"
#include "xsdk/kernel.h"
#include "xsdk/log.h"
#include "xsdk/present.h"
#include "xsdk/text.h"

enum {
    BUFFERS = 2,
    SWAP_INTERVAL = 1,
    BEGIN_TIMEOUT_MS = 5000,
    /* Roughly ten seconds at 60 Hz; controller exit is available sooner. */
    AUTO_EXIT_FRAMES = 600,
    BACKGROUND_ARGB = 0xFF102418,
    TEXT_ARGB = 0xFFF0F0E8,
    ACCENT_ARGB = 0xFFFFD060,
};

static const char *const SCREEN_TEXT =
    "SPELUNKR360 V4\n"
    "CH 53 - TOONERTIA\n\n"
    "REAL XBOX 360 PRESENT LOOP ACTIVE\n"
    "XDBF TITLE NAME: Spelunkr360\n\n"
    "Press B, BACK, or START to return to Aurora.\n"
    "Auto-return after about 10 seconds.";

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
    xsdk_log_write("Spelunkr360 V4: start, TitleID 53503601, XDBF name Spelunkr360");

    NTSTATUS status = xsdk_gpu_open();
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V4: xsdk_gpu_open failed: 0x%08X", (unsigned)status);
        return 2;
    }

    uint32_t width = 0;
    uint32_t height = 0;
    status = xsdk_present_open(XSDK_DISPLAY_720P, BUFFERS, SWAP_INTERVAL, &width, &height);
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V4: xsdk_present_open failed: 0x%08X", (unsigned)status);
        (void)xsdk_gpu_close();
        return 3;
    }

    status = xsdk_text_open();
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V4: xsdk_text_open failed: 0x%08X", (unsigned)status);
        xsdk_present_close();
        (void)xsdk_gpu_close();
        return 4;
    }

    xsdk_log_write("Spelunkr360 V4: display %ux%u", (unsigned)width, (unsigned)height);

    for (uint32_t frame = 0; frame < AUTO_EXIT_FRAMES; frame++) {
        uint32_t address = 0;
        status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
        if (!NT_SUCCESS(status)) {
            xsdk_log_write("Spelunkr360 V4: present begin failed at frame %u: 0x%08X",
                (unsigned)frame, (unsigned)status);
            break;
        }

        /* A resolve copies eDRAM to the front buffer and then clears eDRAM,
         * invalidating the render target. Frame 0 establishes our background;
         * every later frame must set the target again before text is queued. */
        if (frame != 0) {
            xsdk_gpu_set_target(width, height);
            xsdk_text_draw(90, 90, 2, TEXT_ARGB, SCREEN_TEXT);
            xsdk_text_draw(90, 390, 2, ACCENT_ARGB,
                ((frame / 30u) & 1u) ? "LIVE PRESENT: A" : "LIVE PRESENT: B");
        }

        xsdk_gpu_resolve(address, width, height, BACKGROUND_ARGB);
        xsdk_present_end();

        if (wants_exit()) {
            xsdk_log_write("Spelunkr360 V4: controller exit at frame %u", (unsigned)frame);
            break;
        }
    }

    xsdk_text_close();
    xsdk_present_close();
    status = xsdk_gpu_close();
    if (!NT_SUCCESS(status))
        xsdk_log_write("Spelunkr360 V4: xsdk_gpu_close failed: 0x%08X", (unsigned)status);

    xsdk_log_write("Spelunkr360 V4: normal title exit to dashboard");
    return 0;
}
