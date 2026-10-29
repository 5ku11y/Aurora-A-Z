/* Spelunkr360 V2 safe-screen prototype.
 *
 * Hardware goal: prove a visible XAM-owned screen and a clean return to
 * Aurora before adding a renderer, HTTP, or video playback.  The first
 * prototype deliberately had no present loop and therefore launched into a
 * black title.  V2 also has a hard ten-second software escape so a failed UI
 * call cannot leave the console trapped in that state.
 */

#include <stdint.h>

#include <xecore/xam.h>
#include <xecore/xboxkrnl.h>

extern uint32_t XamInputGetState(uint32_t user_index, uint32_t flags,
    void *state);
extern void XNotifyQueueUI(uint32_t type, uint32_t user_index, uint32_t area,
    const uint16_t *text, uint64_t parameter);
extern uint32_t XamShowMessageBoxUI(
    uint32_t user_index,
    const uint16_t *title,
    const uint16_t *text,
    uint32_t button_count,
    const uint16_t *const *buttons,
    uint32_t focus_button,
    uint32_t flags,
    uint32_t *pressed_button,
    void *overlapped);

typedef struct SpelunkrGamepad {
    uint16_t buttons;
    uint8_t left_trigger;
    uint8_t right_trigger;
    int16_t left_thumb_x;
    int16_t left_thumb_y;
    int16_t right_thumb_x;
    int16_t right_thumb_y;
} SpelunkrGamepad;

typedef struct SpelunkrInputState {
    uint32_t packet_number;
    SpelunkrGamepad gamepad;
} SpelunkrInputState;

/* XAM's 0x1C-byte overlapped layout.  An event is intentionally omitted so
 * the title can poll completion without owning a kernel event. */
typedef struct SpelunkrOverlapped {
    uint32_t result;
    uint32_t length;
    uint32_t context;
    uint32_t event;
    uint32_t completion_routine;
    uint32_t completion_context;
    uint32_t extended_error;
} SpelunkrOverlapped;

#define SPELUNKR_START 0x0010u
#define SPELUNKR_B     0x2000u
#define SPELUNKR_ERROR_IO_PENDING 0x000003E5u
#define SPELUNKR_OVERLAPPED_PATTERN 0xA5A5A5A5u
#define SPELUNKR_FAILSAFE_TICKS 200u /* 200 * 50 ms = 10 seconds */

static char g_index_path[] = "game:\\index.html";
static char g_cover_path[] = "game:\\cover.png";
static const char g_build_marker[] = "Spelunkr360 V2 safe-screen TitleID 53503601";

static const uint16_t g_title[] = {
    'S','p','e','l','u','n','k','r','3','6','0',' ','V','2',0
};
static const uint16_t g_ready_text[] = {
    'C','H',' ','5','3',' ','T','O','O','N','E','R','T','I','A',10,
    'S','a','f','e','-','s','c','r','e','e','n',' ','t','e','s','t',' ','i','s',' ','r','u','n','n','i','n','g','.',10,
    'P','r','e','s','s',' ','A',' ','o','n',' ','t','h','e',' ','b','u','t','t','o','n',' ','t','o',' ','r','e','t','u','r','n',' ','t','o',' ','A','u','r','o','r','a','.',0
};
static const uint16_t g_missing_text[] = {
    'S','p','e','l','u','n','k','r','3','6','0',' ','a','s','s','e','t','s',' ','a','r','e',' ','m','i','s','s','i','n','g','.',10,
    'P','r','e','s','s',' ','A',' ','t','o',' ','r','e','t','u','r','n',' ','t','o',' ','A','u','r','o','r','a','.',0
};
static const uint16_t g_button_return[] = {
    'R','e','t','u','r','n',' ','t','o',' ','A','u','r','o','r','a',0
};
static const uint16_t *const g_buttons[] = { g_button_return };
static const uint16_t g_ready_notify[] = {
    'S','p','e','l','u','n','k','r','3','6','0',' ','V','2',' ','-',' ','C','H',' ','5','3',' ','r','e','a','d','y',0
};
static const uint16_t g_timeout_notify[] = {
    'S','p','e','l','u','n','k','r','3','6','0',' ','V','2',' ','-',' ','f','a','i','l','-','s','a','f','e',' ','e','x','i','t',0
};

static uint8_t file_exists(char *path)
{
    HANDLE file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL,
        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == NULL || file == INVALID_HANDLE_VALUE) {
        return 0u;
    }
    (void)CloseHandle(file);
    return 1u;
}

static void notify(const uint16_t *text)
{
    XNotifyQueueUI(3u, 0u, 0u, text, 0u);
}

static void sleep_50ms(void)
{
    int64_t interval = -500000LL;
    (void)KeDelayExecutionThread(0u, 0u, &interval);
}

static void terminate_to_aurora(void)
{
    XamLoaderTerminateTitle();
}

int main(void)
{
    SpelunkrOverlapped overlapped = {0};
    uint32_t pressed_button = 0xFFFFFFFFu;
    uint32_t show_result;
    uint32_t tick;
    uint16_t previous_buttons = 0u;
    const uint8_t assets_ready =
        (uint8_t)(file_exists(g_index_path) != 0u && file_exists(g_cover_path) != 0u);

    DbgPrint("%s\n", g_build_marker);
    overlapped.result = SPELUNKR_OVERLAPPED_PATTERN;
    notify(g_ready_notify);

    show_result = XamShowMessageBoxUI(
        0u,
        g_title,
        assets_ready != 0u ? g_ready_text : g_missing_text,
        1u,
        g_buttons,
        0u,
        0u,
        &pressed_button,
        &overlapped);

    for (tick = 0u; tick < SPELUNKR_FAILSAFE_TICKS; ++tick) {
        SpelunkrInputState state;
        uint16_t buttons = 0u;
        uint16_t pressed;

        if (XamInputGetState(0u, 0u, &state) == 0u) {
            buttons = state.gamepad.buttons;
        }
        pressed = (uint16_t)(buttons & (uint16_t)~previous_buttons);
        previous_buttons = buttons;

        /* Start/B remain an emergency escape even if the XAM dialog fails. */
        if ((pressed & (SPELUNKR_START | SPELUNKR_B)) != 0u) {
            terminate_to_aurora();
            return 0;
        }

        if (show_result == SPELUNKR_ERROR_IO_PENDING) {
            if (overlapped.result != SPELUNKR_OVERLAPPED_PATTERN &&
                overlapped.result != SPELUNKR_ERROR_IO_PENDING) {
                terminate_to_aurora();
                return 0;
            }
        } else if (tick >= 20u) {
            /* A non-pending return should not leave the title resident.  Give
             * XAM one second to display anything useful, then leave cleanly. */
            terminate_to_aurora();
            return 0;
        }

        sleep_50ms();
    }

    notify(g_timeout_notify);
    sleep_50ms();
    terminate_to_aurora();
    return 0;
}
