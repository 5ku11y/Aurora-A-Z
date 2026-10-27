#include <limits.h>
#include <stddef.h>
#include <stdint.h>

#include <auroraaz/wolf_idle_timer.h>

static uint32_t saturating_u64_to_u32(uint64_t value)
{
    return value > (uint64_t)UINT32_MAX ? UINT32_MAX : (uint32_t)value;
}

void wolf_idle_timer_init(
    WolfIdleTimer *timer,
    uint64_t now_ms,
    uint32_t threshold_ms)
{
    if (timer == NULL) {
        return;
    }

    timer->threshold_ms = threshold_ms != 0u ?
        (uint64_t)threshold_ms :
        (uint64_t)WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS;
    timer->last_activity_ms = now_ms;
    timer->reset_count = 0u;
    timer->trigger_count = 0u;
    timer->last_activity_serial = 0u;
    timer->last_input_frame = 0u;
    timer->fired = 0u;
}

WolfIdleTimerResult wolf_idle_timer_note_activity(
    WolfIdleTimer *timer,
    uint64_t now_ms,
    uint32_t activity_serial,
    uint32_t input_frame)
{
    if (timer == NULL) {
        return WOLF_IDLE_TIMER_WAITING;
    }

    timer->last_activity_ms = now_ms;
    timer->last_activity_serial = activity_serial;
    timer->last_input_frame = input_frame;
    timer->fired = 0u;
    if (timer->reset_count != UINT32_MAX) {
        ++timer->reset_count;
    }
    return WOLF_IDLE_TIMER_ACTIVITY_RESET;
}

WolfIdleTimerResult wolf_idle_timer_step(
    WolfIdleTimer *timer,
    uint64_t now_ms)
{
    uint64_t elapsed;

    if (timer == NULL) {
        return WOLF_IDLE_TIMER_WAITING;
    }

    if (now_ms < timer->last_activity_ms) {
        timer->last_activity_ms = now_ms;
        timer->fired = 0u;
        if (timer->reset_count != UINT32_MAX) {
            ++timer->reset_count;
        }
        return WOLF_IDLE_TIMER_ACTIVITY_RESET;
    }

    if (timer->fired != 0u) {
        return WOLF_IDLE_TIMER_ALREADY_FIRED;
    }

    elapsed = now_ms - timer->last_activity_ms;
    if (elapsed < timer->threshold_ms) {
        return WOLF_IDLE_TIMER_WAITING;
    }

    timer->fired = 1u;
    if (timer->trigger_count != UINT32_MAX) {
        ++timer->trigger_count;
    }
    return WOLF_IDLE_TIMER_FIRED;
}

uint32_t wolf_idle_timer_elapsed_ms(
    const WolfIdleTimer *timer,
    uint64_t now_ms)
{
    if (timer == NULL || now_ms < timer->last_activity_ms) {
        return 0u;
    }
    return saturating_u64_to_u32(now_ms - timer->last_activity_ms);
}
