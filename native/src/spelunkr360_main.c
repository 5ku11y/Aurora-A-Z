/* Spelunkr360 native Aurora-launchable prototype.
 *
 * Phase 1 goal: prove title launch, bundled asset visibility and the agreed
 * controller layout on real Xbox 360 hardware before adding HTTP/video.
 */

#include <stdint.h>

#include <xecore/xam.h>
#include <xecore/xboxkrnl.h>

extern uint32_t XamInputGetState(uint32_t user_index, uint32_t flags,
    void *state);
extern void XNotifyQueueUI(uint32_t type, uint32_t user_index, uint32_t area,
    const uint16_t *text, uint64_t parameter);

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

#define SPELUNKR_DPAD_LEFT  0x0004u
#define SPELUNKR_DPAD_RIGHT 0x0008u
#define SPELUNKR_START      0x0010u
#define SPELUNKR_LB         0x0100u
#define SPELUNKR_RB         0x0200u
#define SPELUNKR_A          0x1000u
#define SPELUNKR_B          0x2000u

static char g_index_path[] = "game:\\index.html";
static char g_cover_path[] = "game:\\cover.png";

static const uint16_t g_ready[] = {
    'S','p','e','l','u','n','k','r','3','6','0',' ','-',' ','C','H',' ','5','3',' ',
    'T','O','O','N','E','R','T','I','A',' ','r','e','a','d','y',0
};
static const uint16_t g_missing[] = {
    'S','p','e','l','u','n','k','r','3','6','0',' ','a','s','s','e','t','s',' ',
    'm','i','s','s','i','n','g',0
};
static const uint16_t g_previous[] = {
    'S','p','e','l','u','n','k','r','3','6','0',' ','-',' ','p','r','e','v','i','o','u','s',' ',
    'c','h','a','n','n','e','l',0
};
static const uint16_t g_next[] = {
    'S','p','e','l','u','n','k','r','3','6','0',' ','-',' ','n','e','x','t',' ',
    'c','h','a','n','n','e','l',0
};
static const uint16_t g_tune[] = {
    'S','p','e','l','u','n','k','r','3','6','0',' ','-',' ','t','u','n','e',' ','C','H',' ','5','3',0
};
static const uint16_t g_guide[] = {
    'S','p','e','l','u','n','k','r','3','6','0',' ','-',' ','g','u','i','d','e',' ','/',' ','b','a','c','k',0
};
static const uint16_t g_exit[] = {
    'S','p','e','l','u','n','k','r','3','6','0',' ','-',' ','r','e','t','u','r','n','i','n','g',' ','t','o',' ','A','u','r','o','r','a',0
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
    XNotifyQueueUI(0u, 0u, 0u, text, 0u);
}

static void sleep_50ms(void)
{
    int64_t interval = -500000LL;
    (void)KeDelayExecutionThread(0u, 0u, &interval);
}

int main(void)
{
    uint16_t previous_buttons = 0u;

    if (file_exists(g_index_path) == 0u || file_exists(g_cover_path) == 0u) {
        notify(g_missing);
    } else {
        notify(g_ready);
    }

    for (;;) {
        SpelunkrInputState state;
        uint16_t buttons = 0u;
        uint16_t pressed;

        if (XamInputGetState(0u, 0u, &state) == 0u) {
            buttons = state.gamepad.buttons;
        }
        pressed = (uint16_t)(buttons & (uint16_t)~previous_buttons);
        previous_buttons = buttons;

        if ((pressed & (SPELUNKR_DPAD_LEFT | SPELUNKR_LB)) != 0u) {
            notify(g_previous);
        }
        if ((pressed & (SPELUNKR_DPAD_RIGHT | SPELUNKR_RB)) != 0u) {
            notify(g_next);
        }
        if ((pressed & SPELUNKR_A) != 0u) {
            notify(g_tune);
        }
        if ((pressed & SPELUNKR_B) != 0u) {
            notify(g_guide);
        }
        if ((pressed & SPELUNKR_START) != 0u) {
            notify(g_exit);
            sleep_50ms();
            XamLoaderTerminateTitle();
            return 0;
        }

        sleep_50ms();
    }
}
