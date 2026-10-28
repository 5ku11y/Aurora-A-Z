#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf FINAL idle-key anchor missing: {label}")
    return text.replace(old, new, 1)


# FINAL route: stop trying to draw or attach anything to Aurora. Reuse the
# hardware-proven idle timer + Aurora_Main focus gate, and fill exactly one
# otherwise-empty Aurora XInputGetKeystroke poll with DPAD_LEFT. Real controller
# input always wins and cancels any queued synthetic key.

header_path = Path("native/include/auroraaz/input_detour.h")
header = header_path.read_text()
header = replace_once(
    header,
    '    uint32_t browse_jump_rejected;\n'
    '    uint32_t in_flight;\n',
    '    uint32_t browse_jump_rejected;\n'
    '    uint32_t synthetic_queued;\n'
    '    uint32_t synthetic_delivered;\n'
    '    uint32_t synthetic_cancelled;\n'
    '    uint32_t synthetic_pending;\n'
    '    uint32_t synthetic_virtual_key;\n'
    '    uint32_t in_flight;\n',
    "input status synthetic counters",
)
header = replace_once(
    header,
    'uint8_t az_rev1655_input_detour_publish_browse_jump(\n'
    '    uintptr_t game_content_manager,\n'
    '    uint32_t target_index,\n'
    '    uint32_t item_count);\n\n'
    'void az_rev1655_input_detour_snapshot_selector(AzSelectorState *selector);',
    'uint8_t az_rev1655_input_detour_publish_browse_jump(\n'
    '    uintptr_t game_content_manager,\n'
    '    uint32_t target_index,\n'
    '    uint32_t item_count);\n\n'
    '/* Worker-thread producer for one synthetic Aurora keystroke. It never\n'
    ' * mutates XInput state; the main hook only substitutes the event when\n'
    ' * Aurora\'s original wrapper reports no real keystroke. */\n'
    'uint8_t az_rev1655_input_detour_publish_synthetic_key(\n'
    '    uint16_t virtual_key);\n'
    'void az_rev1655_input_detour_cancel_synthetic_key(void);\n\n'
    'void az_rev1655_input_detour_snapshot_selector(AzSelectorState *selector);',
    "synthetic key declarations",
)
header_path.write_text(header)


input_path = Path("native/src/input_detour.c")
source = input_path.read_text()
source = replace_once(
    source,
    '    volatile uint32_t browse_jump_queued;\n'
    '    volatile uint32_t browse_jump_applied;\n'
    '    volatile uint32_t browse_jump_rejected;\n'
    '} AzInputDetourBridge;',
    '    volatile uint32_t browse_jump_queued;\n'
    '    volatile uint32_t browse_jump_applied;\n'
    '    volatile uint32_t browse_jump_rejected;\n'
    '    volatile uint32_t synthetic_pending;\n'
    '    volatile uint32_t synthetic_virtual_key;\n'
    '    volatile uint32_t synthetic_queued;\n'
    '    volatile uint32_t synthetic_delivered;\n'
    '    volatile uint32_t synthetic_cancelled;\n'
    '} AzInputDetourBridge;',
    "bridge synthetic state",
)
source = replace_once(
    source,
    '    store_u32(&g_input_bridge.browse_jump_queued, 0u);\n'
    '    store_u32(&g_input_bridge.browse_jump_applied, 0u);\n'
    '    store_u32(&g_input_bridge.browse_jump_rejected, 0u);\n',
    '    store_u32(&g_input_bridge.browse_jump_queued, 0u);\n'
    '    store_u32(&g_input_bridge.browse_jump_applied, 0u);\n'
    '    store_u32(&g_input_bridge.browse_jump_rejected, 0u);\n'
    '    store_u32(&g_input_bridge.synthetic_pending, 0u);\n'
    '    store_u32(&g_input_bridge.synthetic_virtual_key, 0u);\n'
    '    store_u32(&g_input_bridge.synthetic_queued, 0u);\n'
    '    store_u32(&g_input_bridge.synthetic_delivered, 0u);\n'
    '    store_u32(&g_input_bridge.synthetic_cancelled, 0u);\n',
    "reset synthetic state",
)
source = replace_once(
    source,
    '    store_u32(&g_input_bridge.browse_jump_pending, 0u);\n'
    '}\n\nuint8_t az_rev1655_input_detour_shutdown_ready(void)',
    '    store_u32(&g_input_bridge.browse_jump_pending, 0u);\n'
    '    store_u32(&g_input_bridge.synthetic_pending, 0u);\n'
    '}\n\nuint8_t az_rev1655_input_detour_shutdown_ready(void)',
    "shutdown synthetic cancellation",
)

synthetic_functions = r'''uint8_t az_rev1655_input_detour_publish_synthetic_key(
    uint16_t virtual_key)
{
    uint32_t expected = 0u;

    if (virtual_key == 0u || shutdown_is_requested() != 0u ||
        bool_from_atomic(&g_input_bridge.image_verified) == 0u ||
        bool_from_atomic(&g_input_bridge.input_hook_verified) == 0u ||
        bool_from_atomic(&g_input_bridge.render_hook_verified) == 0u ||
        bool_from_atomic(&g_input_bridge.scene_allows_capture) == 0u) {
        return 0u;
    }

    /* 2 = producer owns the slot; 1 = ready for the main input poll. */
    if (!__atomic_compare_exchange_n(
            &g_input_bridge.synthetic_pending,
            &expected,
            2u,
            0,
            __ATOMIC_ACQ_REL,
            __ATOMIC_ACQUIRE)) {
        return 0u;
    }
    store_u32(&g_input_bridge.synthetic_virtual_key, (uint32_t)virtual_key);

    /* Revalidate after publication data is written. */
    if (shutdown_is_requested() != 0u ||
        bool_from_atomic(&g_input_bridge.scene_allows_capture) == 0u) {
        store_u32(&g_input_bridge.synthetic_pending, 0u);
        (void)increment_u32(&g_input_bridge.synthetic_cancelled);
        return 0u;
    }

    store_u32(&g_input_bridge.synthetic_pending, 1u);
    (void)increment_u32(&g_input_bridge.synthetic_queued);
    return 1u;
}

void az_rev1655_input_detour_cancel_synthetic_key(void)
{
    const uint32_t pending = __atomic_exchange_n(
        &g_input_bridge.synthetic_pending,
        0u,
        __ATOMIC_ACQ_REL);
    if (pending != 0u) {
        (void)increment_u32(&g_input_bridge.synthetic_cancelled);
    }
}

'''
source = replace_once(
    source,
    'void az_rev1655_input_detour_snapshot_selector(AzSelectorState *selector)\n{',
    synthetic_functions +
    'void az_rev1655_input_detour_snapshot_selector(AzSelectorState *selector)\n{',
    "synthetic producer functions",
)
source = replace_once(
    source,
    '    status->browse_jump_rejected =\n'
    '        load_u32(&g_input_bridge.browse_jump_rejected);\n'
    '    status->in_flight = load_u32(&g_input_bridge.in_flight);',
    '    status->browse_jump_rejected =\n'
    '        load_u32(&g_input_bridge.browse_jump_rejected);\n'
    '    status->synthetic_queued =\n'
    '        load_u32(&g_input_bridge.synthetic_queued);\n'
    '    status->synthetic_delivered =\n'
    '        load_u32(&g_input_bridge.synthetic_delivered);\n'
    '    status->synthetic_cancelled =\n'
    '        load_u32(&g_input_bridge.synthetic_cancelled);\n'
    '    status->synthetic_pending =\n'
    '        load_u32(&g_input_bridge.synthetic_pending);\n'
    '    status->synthetic_virtual_key =\n'
    '        load_u32(&g_input_bridge.synthetic_virtual_key);\n'
    '    status->in_flight = load_u32(&g_input_bridge.in_flight);',
    "snapshot synthetic counters",
)

injection = r'''    repeat_held_direction(input_frame);

    /* FINAL: a real hardware keystroke always wins. It also cancels a queued
     * idle move so the synthetic event can never trail a user's input. */
    if (result == AZ_REV1655_INPUT_RESULT_SUCCESS) {
        az_rev1655_input_detour_cancel_synthetic_key();
    }
    else if (bool_from_atomic(&g_input_bridge.scene_allows_capture) != 0u &&
        bool_from_atomic(&g_input_bridge.image_verified) != 0u &&
        bool_from_atomic(&g_input_bridge.input_hook_verified) != 0u &&
        bool_from_atomic(&g_input_bridge.render_hook_verified) != 0u &&
        load_u32(&g_input_bridge.synthetic_pending) == 1u &&
        address_range_is_valid(keystroke, sizeof(*keystroke)) != 0u) {
        uint32_t ready = 1u;
        if (__atomic_compare_exchange_n(
                &g_input_bridge.synthetic_pending,
                &ready,
                0u,
                0,
                __ATOMIC_ACQ_REL,
                __ATOMIC_ACQUIRE)) {
            keystroke->virtual_key = (uint16_t)load_u32(
                &g_input_bridge.synthetic_virtual_key);
            keystroke->unicode = 0u;
            keystroke->flags = AZ_KEYSTROKE_KEYDOWN;
            keystroke->user_index = user_index < 4u ?
                (uint8_t)user_index : 0u;
            keystroke->hid_code = 0u;
            (void)increment_u32(&g_input_bridge.synthetic_delivered);
            (void)__atomic_sub_fetch(
                &g_input_bridge.in_flight,
                1u,
                __ATOMIC_ACQ_REL);
            return AZ_REV1655_INPUT_RESULT_SUCCESS;
        }
    }

    if (result != AZ_REV1655_INPUT_RESULT_SUCCESS) {'''
source = replace_once(
    source,
    '    repeat_held_direction(input_frame);\n\n'
    '    if (result != AZ_REV1655_INPUT_RESULT_SUCCESS) {',
    injection,
    "main-poll synthetic substitution",
)
input_path.write_text(source)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()
runtime = replace_once(
    runtime,
    '    WolfIdleTimer wolf_idle_timer;\n'
    '} AzRev1655Runtime;',
    '    WolfIdleTimer wolf_idle_timer;\n'
    '    uint32_t wolf_final_last_main_calls;\n'
    '    uint32_t wolf_final_stale_ticks;\n'
    '    uint32_t wolf_final_dashboard_live;\n'
    '    uint32_t wolf_final_pause_count;\n'
    '    uint32_t wolf_final_last_delivered;\n'
    '    uint32_t wolf_final_last_cancelled;\n'
    '} AzRev1655Runtime;',
    "runtime final idle state",
)
runtime = replace_once(
    runtime,
    'typedef struct AzM2bRenderMarker {',
    'typedef struct WolfFinalIdleKeyMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t threshold_ms;\n'
    '    uint32_t dashboard_live;\n'
    '    uint32_t timer_elapsed_ms;\n'
    '    uint32_t timer_trigger_count;\n'
    '    uint32_t synthetic_pending;\n'
    '    uint32_t synthetic_virtual_key;\n'
    '    uint32_t synthetic_queued;\n'
    '    uint32_t synthetic_delivered;\n'
    '    uint32_t synthetic_cancelled;\n'
    '    uint32_t main_calls;\n'
    '    uint32_t scene_allows_capture;\n'
    '    uint32_t pause_count;\n'
    '    uint32_t last_input_frame;\n'
    '} WolfFinalIdleKeyMarker;\n\n'
    'typedef char WolfFinalIdleKeyMarkerMustBe64Bytes[\n'
    '    sizeof(WolfFinalIdleKeyMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "final marker structure",
)
runtime = replace_once(
    runtime,
    'static char g_wolf_v8r_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8R-render.bin";\n',
    'static char g_wolf_v8r_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8R-render.bin";\n'
    'static char g_wolf_final_idle_key_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-FINAL-idle-key.bin";\n',
    "final marker path",
)

final_flush = r'''static void flush_wolf_final_idle_key_marker(uint32_t dashboard_live)
{
    AzInputDetourStatus status;
    const uint64_t now_ms = wolf_runtime_now_ms();
    WolfFinalIdleKeyMarker marker;

    memset(&status, 0, sizeof(status));
    memset(&marker, 0, sizeof(marker));
    az_rev1655_input_detour_snapshot_status(&status);

    marker.magic[0] = 'W';
    marker.magic[1] = 'F';
    marker.magic[2] = 'K';
    marker.magic[3] = '1';
    marker.version = 1u;
    marker.record_size = (uint32_t)sizeof(marker);
    marker.threshold_ms = WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS;
    marker.dashboard_live = dashboard_live;
    marker.timer_elapsed_ms = wolf_idle_timer_elapsed_ms(
        &g_runtime.wolf_idle_timer, now_ms);
    marker.timer_trigger_count = g_runtime.wolf_idle_timer.trigger_count;
    marker.synthetic_pending = status.synthetic_pending;
    marker.synthetic_virtual_key = status.synthetic_virtual_key;
    marker.synthetic_queued = status.synthetic_queued;
    marker.synthetic_delivered = status.synthetic_delivered;
    marker.synthetic_cancelled = status.synthetic_cancelled;
    marker.main_calls = status.main_calls;
    marker.scene_allows_capture = status.scene_allows_capture;
    marker.pause_count = g_runtime.wolf_final_pause_count;
    marker.last_input_frame = status.input_frame;

    if (write_complete_file(
            g_wolf_final_idle_key_marker_path,
            (const uint8_t *)&marker,
            (uint32_t)sizeof(marker)) == 0u) {
        DbgPrint("WolfFactory FINAL: idle-key marker write failed\n");
    }
}

'''
runtime = replace_once(
    runtime,
    'static void flush_wolf_v8b_idle_marker(void)\n{',
    final_flush + 'static void flush_wolf_v8b_idle_marker(void)\n{',
    "final marker writer",
)
runtime = replace_once(
    runtime,
    '            (void)wolf_idle_timer_note_activity(\n'
    '                &g_runtime.wolf_idle_timer,\n'
    '                wolf_runtime_now_ms(),\n'
    '                observation.serial,\n'
    '                observation.input_frame);\n'
    '            if (was_fired != 0u) {',
    '            (void)wolf_idle_timer_note_activity(\n'
    '                &g_runtime.wolf_idle_timer,\n'
    '                wolf_runtime_now_ms(),\n'
    '                observation.serial,\n'
    '                observation.input_frame);\n'
    '            az_rev1655_input_detour_cancel_synthetic_key();\n'
    '            if (was_fired != 0u) {',
    "real input cancels synthetic key",
)
runtime = replace_once(
    runtime,
    '        wolf_idle_timer_init(\n'
    '            &g_runtime.wolf_idle_timer,\n'
    '            wolf_runtime_now_ms(),\n'
    '            WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS);\n'
    '        flush_wolf_v8b_idle_marker();',
    '        wolf_idle_timer_init(\n'
    '            &g_runtime.wolf_idle_timer,\n'
    '            wolf_runtime_now_ms(),\n'
    '            WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS);\n'
    '        g_runtime.wolf_final_last_main_calls = 0u;\n'
    '        g_runtime.wolf_final_stale_ticks = 0u;\n'
    '        g_runtime.wolf_final_dashboard_live = 0u;\n'
    '        g_runtime.wolf_final_pause_count = 0u;\n'
    '        g_runtime.wolf_final_last_delivered = 0u;\n'
    '        g_runtime.wolf_final_last_cancelled = 0u;\n'
    '        flush_wolf_v8b_idle_marker();\n'
    '        flush_wolf_final_idle_key_marker(0u);',
    "final idle initialization",
)

old_worker = (
    '        if (wolf_idle_timer_step(\n'
    '                &g_runtime.wolf_idle_timer,\n'
    '                wolf_runtime_now_ms()) == WOLF_IDLE_TIMER_FIRED) {\n'
    '            DbgPrint(\n'
    '                "WolfFactory V8B: 12-second idle trigger fired\\n");\n'
    '            flush_wolf_v8b_idle_marker();\n'
    '        }\n'
)
new_worker = r'''        {
            AzInputDetourStatus wolf_status;
            const uint64_t now_ms = wolf_runtime_now_ms();
            uint32_t dashboard_live;

            memset(&wolf_status, 0, sizeof(wolf_status));
            az_rev1655_input_detour_snapshot_status(&wolf_status);

            if (wolf_status.main_calls !=
                g_runtime.wolf_final_last_main_calls) {
                g_runtime.wolf_final_last_main_calls = wolf_status.main_calls;
                g_runtime.wolf_final_stale_ticks = 0u;
            }
            else if (g_runtime.wolf_final_stale_ticks < 0xFFFFFFFFu) {
                ++g_runtime.wolf_final_stale_ticks;
            }

            /* Aurora_Main must own focus and the main input loop must still be
             * alive. Ten stale worker ticks gives scheduling jitter room while
             * still pausing quickly when a game replaces Aurora. */
            dashboard_live =
                wolf_status.scene_allows_capture != 0u &&
                wolf_status.image_verified != 0u &&
                wolf_status.input_hook_verified != 0u &&
                wolf_status.render_hook_verified != 0u &&
                g_runtime.wolf_final_stale_ticks < 10u ? 1u : 0u;

            if (dashboard_live == 0u) {
                /* True pause: time spent in Settings, a game, or another scene
                 * never counts toward the next idle rotation. */
                g_runtime.wolf_idle_timer.last_activity_ms = now_ms;
                g_runtime.wolf_idle_timer.fired = 0u;
                az_rev1655_input_detour_cancel_synthetic_key();
                if (g_runtime.wolf_final_dashboard_live != 0u) {
                    if (g_runtime.wolf_final_pause_count < 0xFFFFFFFFu) {
                        ++g_runtime.wolf_final_pause_count;
                    }
                    DbgPrint("WolfFactory FINAL: dashboard idle paused\n");
                    flush_wolf_final_idle_key_marker(0u);
                }
            }
            else if (wolf_idle_timer_step(
                    &g_runtime.wolf_idle_timer,
                    now_ms) == WOLF_IDLE_TIMER_FIRED) {
                if (az_rev1655_input_detour_publish_synthetic_key(
                        AZ_VK_PAD_DPAD_LEFT) != 0u) {
                    DbgPrint(
                        "WolfFactory FINAL: queued synthetic DPAD_LEFT\n");
                }
                else {
                    DbgPrint(
                        "WolfFactory FINAL: synthetic DPAD_LEFT not queued\n");
                }

                /* Re-arm immediately so an untouched dashboard advances by
                 * exactly one cover per idle interval. Synthetic input is not
                 * reported as user activity. */
                g_runtime.wolf_idle_timer.last_activity_ms = now_ms;
                g_runtime.wolf_idle_timer.fired = 0u;
                flush_wolf_v8b_idle_marker();
                flush_wolf_final_idle_key_marker(1u);
            }

            g_runtime.wolf_final_dashboard_live = dashboard_live;
            az_rev1655_input_detour_snapshot_status(&wolf_status);
            if (wolf_status.synthetic_delivered !=
                    g_runtime.wolf_final_last_delivered ||
                wolf_status.synthetic_cancelled !=
                    g_runtime.wolf_final_last_cancelled) {
                g_runtime.wolf_final_last_delivered =
                    wolf_status.synthetic_delivered;
                g_runtime.wolf_final_last_cancelled =
                    wolf_status.synthetic_cancelled;
                flush_wolf_final_idle_key_marker(dashboard_live);
            }
        }
'''
runtime = replace_once(
    runtime, old_worker, new_worker, "dashboard-gated idle worker"
)
runtime_path.write_text(runtime)


# Disable the exhausted V8R visual path. The render hook remains installed only
# because it supplies the proven Aurora_Main/focus gate used above.
render_path = Path("native/src/render_detours.c")
render = render_path.read_text()
render = replace_once(
    render,
    '            if (caller_lr == AZ_REV1655_FONT_END_CALLER_LR &&\n'
    '                load_u32(&g_render_detours.wolf_v8r_phase) < 2u) {\n'
    '                draw_result = AZ_OVERLAY_RENDERER_OK;\n',
    '            if (caller_lr == AZ_REV1655_FONT_END_CALLER_LR &&\n'
    '                load_u32(&g_render_detours.wolf_v8r_phase) == 0xFFFFFFFFu) {\n'
    '                draw_result = AZ_OVERLAY_RENDERER_OK;\n',
    "disable V8R pre-End reservation",
)
render = replace_once(
    render,
    '        load_u32(&g_render_detours.cleanup_requested) == 0u &&\n'
    '        load_u32(&g_render_detours.wolf_v8r_phase) < 2u) {\n',
    '        load_u32(&g_render_detours.cleanup_requested) == 0u &&\n'
    '        load_u32(&g_render_detours.wolf_v8r_phase) == 0xFFFFFFFFu) {\n',
    "disable V8R post-End batch",
)
render_path.write_text(render)

print("Wolf FINAL dashboard idle synthetic-left route applied")
