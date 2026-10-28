#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include <auroraaz/wolf_idle_timer.h>

static void test_fires_at_exact_threshold(void)
{
    WolfIdleTimer timer;

    wolf_idle_timer_init(&timer, 1000u, 12000u);
    assert(wolf_idle_timer_step(&timer, 12999u) ==
        WOLF_IDLE_TIMER_WAITING);
    assert(timer.trigger_count == 0u);
    assert(wolf_idle_timer_step(&timer, 13000u) ==
        WOLF_IDLE_TIMER_FIRED);
    assert(timer.trigger_count == 1u);
    assert(timer.fired == 1u);
    assert(wolf_idle_timer_step(&timer, 20000u) ==
        WOLF_IDLE_TIMER_ALREADY_FIRED);
    assert(timer.trigger_count == 1u);
}

static void test_activity_resets_and_rearms(void)
{
    WolfIdleTimer timer;

    wolf_idle_timer_init(&timer, 0u, 12000u);
    assert(wolf_idle_timer_step(&timer, 11999u) ==
        WOLF_IDLE_TIMER_WAITING);
    assert(wolf_idle_timer_note_activity(&timer, 11999u, 7u, 99u) ==
        WOLF_IDLE_TIMER_ACTIVITY_RESET);
    assert(timer.reset_count == 1u);
    assert(timer.last_activity_serial == 7u);
    assert(timer.last_input_frame == 99u);
    assert(wolf_idle_timer_step(&timer, 23998u) ==
        WOLF_IDLE_TIMER_WAITING);
    assert(wolf_idle_timer_step(&timer, 23999u) ==
        WOLF_IDLE_TIMER_FIRED);

    assert(wolf_idle_timer_note_activity(&timer, 24000u, 8u, 100u) ==
        WOLF_IDLE_TIMER_ACTIVITY_RESET);
    assert(timer.fired == 0u);
    assert(timer.reset_count == 2u);
    assert(wolf_idle_timer_step(&timer, 36000u) ==
        WOLF_IDLE_TIMER_FIRED);
    assert(timer.trigger_count == 2u);
}

static void test_clock_rollback_fails_safe(void)
{
    WolfIdleTimer timer;

    wolf_idle_timer_init(&timer, 50000u, 12000u);
    assert(wolf_idle_timer_step(&timer, 49000u) ==
        WOLF_IDLE_TIMER_ACTIVITY_RESET);
    assert(timer.fired == 0u);
    assert(timer.reset_count == 1u);
    assert(wolf_idle_timer_step(&timer, 60999u) ==
        WOLF_IDLE_TIMER_WAITING);
    assert(wolf_idle_timer_step(&timer, 61000u) ==
        WOLF_IDLE_TIMER_FIRED);
}

static void test_default_threshold(void)
{
    WolfIdleTimer timer;

    wolf_idle_timer_init(&timer, 0u, 0u);
    assert(timer.threshold_ms == 300000u);
    assert(wolf_idle_timer_elapsed_ms(&timer, 300000u) == 300000u);
}

int main(void)
{
    test_fires_at_exact_threshold();
    test_activity_resets_and_rearms();
    test_clock_rollback_fails_safe();
    test_default_threshold();
    puts("wolf_idle_timer_tests: PASS");
    return 0;
}
