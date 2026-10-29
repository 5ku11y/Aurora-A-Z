/* Spelunkr360 V3 hardware-safe display probe.
 *
 * V1 proved Aurora can discover and launch the title, but had no renderer.
 * V2 proved XAM executes and the fixed TitleID is present, but XAM dialogs
 * need a live present loop under them.  V3 uses xsdk's console-proven Xenos
 * present path and exits by returning normally through xsdk's title runtime.
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
    /* At 60 Hz this is roughly ten seconds.  It is a safety net only. */
    AUTO_EXIT_FRAMES = 600,
    BACKGROUND_ARGB = 0xFF102418,
    TEXT_ARGB = 0xFFF0F0E8,
};

static const char *const SCREEN_TEXT =
    "SPELUNKR360 V3\n"
    "CH 53 - TOONERTIA\n\n"
    "REAL XBOX 360 PRESENT LOOP ACTIVE\n"
    "Press B, BACK, or START to return to Aurora.\n\n"
    "This test returns automatically after about 10 seconds.";

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
    xsdk_log_write("Spelunkr360 V3: start, TitleID 53503601");

    NTSTATUS status = xsdk_gpu_open();
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V3: xsdk_gpu_open failed: 0x%08X", (unsigned)status);
        return 2;
    }

    uint32_t width = 0;
    uint32_t height = 0;
    status = xsdk_present_open(XSDK_DISPLAY_720P, BUFFERS, SWAP_INTERVAL, &width, &height);
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V3: xsdk_present_open failed: 0x%08X", (unsigned)status);
        (void)xsdk_gpu_close();
        return 3;
    }

    status = xsdk_text_open();
    if (!NT_SUCCESS(status)) {
        xsdk_log_write("Spelunkr360 V3: xsdk_text_open failed: 0x%08X", (unsigned)status);
        xsdk_present_close();
        (void)xsdk_gpu_close();
        return 4;
    }

    xsdk_log_write("Spelunkr360 V3: display %ux%u", (unsigned)width, (unsigned)height);

    for (uint32_t frame = 0; frame < AUTO_EXIT_FRAMES; frame++) {
        uint32_t address = 0;
        status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
        if (!NT_SUCCESS(status)) {
            xsdk_log_write("Spelunkr360 V3: present begin failed at frame %u: 0x%08X",
                (unsigned)frame, (unsigned)status);
            break;
        }

        /* resolve() copies the current eDRAM frame to the front buffer and
         * clears eDRAM to BACKGROUND_ARGB for the following frame.  From the
         * second frame onward this gives a stable background and native text. */
        if (frame != 0)
            xsdk_text_draw(90, 100, 2, TEXT_ARGB, SCREEN_TEXT);
        xsdk_gpu_resolve(address, width, height, BACKGROUND_ARGB);
        xsdk_present_end();

        if (wants_exit()) {
            xsdk_log_write("Spelunkr360 V3: controller exit at frame %u", (unsigned)frame);
            break;
        }
    }

    xsdk_text_close();
    xsdk_present_close();
    status = xsdk_gpu_close();
    if (!NT_SUCCESS(status))
        xsdk_log_write("Spelunkr360 V3: xsdk_gpu_close failed: 0x%08X", (unsigned)status);

    xsdk_log_write("Spelunkr360 V3: normal title exit to dashboard");
    return 0;
}
