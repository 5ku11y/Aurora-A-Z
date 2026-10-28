#ifndef AURORAAZ_WOLF_IDLE_TIMER_H
#define AURORAAZ_WOLF_IDLE_TIMER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Final WolfIdle behavior: a fresh idle session waits five minutes before
 * automation begins. The runtime intentionally switches to 4000 ms only after
 * the first automatic cover move, and any real activity/scene reset restores
 * this default. */
#define WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS 300000u

typedef enum WolfIdleTimerResult {
    WOLF_IDLE_TIMER_WAITING = 0,
    WOLF_IDLE_TIMER_ACTIVITY_RESET,
    WOLF_IDLE_TIMER_FIRED,
    WOLF_IDLE_TIMER_ALREADY_FIRED
} WolfIdleTimerResult;

typedef struct WolfIdleTimer {
    uint64_t threshold_ms;
    uint64_t last_activity_ms;
    uint32_t reset_count;
    uint32_t trigger_count;
    uint32_t last_activity_serial;
    uint32_t last_input_frame;
    uint8_t fired;
} WolfIdleTimer;

void wolf_idle_timer_init(
    WolfIdleTimer *timer,
    uint64_t now_ms,
    uint32_t threshold_ms);

WolfIdleTimerResult wolf_idle_timer_note_activity(
    WolfIdleTimer *timer,
    uint64_t now_ms,
    uint32_t activity_serial,
    uint32_t input_frame);

WolfIdleTimerResult wolf_idle_timer_step(
    WolfIdleTimer *timer,
    uint64_t now_ms);

uint32_t wolf_idle_timer_elapsed_ms(
    const WolfIdleTimer *timer,
    uint64_t now_ms);

#ifdef __cplusplus
}
#endif

#endif
