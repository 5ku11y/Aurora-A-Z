#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf idle 4s anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

# Report the currently active interval instead of always claiming 12 seconds.
runtime = replace_once(
    runtime,
    '    marker.threshold_ms = WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS;\n',
    '    marker.threshold_ms = (uint32_t)g_runtime.wolf_idle_timer.threshold_ms;\n',
    "telemetry active threshold",
)

# Any real controller activity starts a brand-new idle session: first automatic
# move remains at the proven 12-second threshold.
runtime = replace_once(
    runtime,
    '            (void)wolf_idle_timer_note_activity(\n'
    '                &g_runtime.wolf_idle_timer,\n'
    '                wolf_runtime_now_ms(),\n'
    '                observation.serial,\n'
    '                observation.input_frame);\n'
    '            az_rev1655_input_detour_cancel_synthetic_key();\n',
    '            (void)wolf_idle_timer_note_activity(\n'
    '                &g_runtime.wolf_idle_timer,\n'
    '                wolf_runtime_now_ms(),\n'
    '                observation.serial,\n'
    '                observation.input_frame);\n'
    '            g_runtime.wolf_idle_timer.threshold_ms =\n'
    '                WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS;\n'
    '            az_rev1655_input_detour_cancel_synthetic_key();\n',
    "real input restores 12-second start",
)

# Leaving coverflow/settings/game transition is also a fresh idle session on
# return, so time away never resumes the 4-second rotation cadence.
runtime = replace_once(
    runtime,
    '                g_runtime.wolf_idle_timer.last_activity_ms = now_ms;\n'
    '                g_runtime.wolf_idle_timer.fired = 0u;\n'
    '                az_rev1655_input_detour_cancel_synthetic_key();\n',
    '                g_runtime.wolf_idle_timer.threshold_ms =\n'
    '                    WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS;\n'
    '                g_runtime.wolf_idle_timer.last_activity_ms = now_ms;\n'
    '                g_runtime.wolf_idle_timer.fired = 0u;\n'
    '                az_rev1655_input_detour_cancel_synthetic_key();\n',
    "dashboard pause restores 12-second start",
)

# Once the first 12-second move fires, an untouched dashboard becomes a slow
# carousel: one additional synthetic DPAD_LEFT every 4 seconds. Real input or
# leaving the dashboard resets this back to the 12-second initial delay above.
runtime = replace_once(
    runtime,
    '                /* Re-arm immediately so an untouched dashboard advances by\n'
    '                 * exactly one cover per idle interval. Synthetic input is not\n'
    '                 * reported as user activity. */\n'
    '                g_runtime.wolf_idle_timer.last_activity_ms = now_ms;\n'
    '                g_runtime.wolf_idle_timer.fired = 0u;\n',
    '                /* First idle move remains 12 seconds. After it fires, keep\n'
    '                 * the untouched dashboard rotating one cover every 4 seconds.\n'
    '                 * Real input or leaving coverflow restores 12 seconds. */\n'
    '                if (g_runtime.wolf_idle_timer.threshold_ms != 4000u) {\n'
    '                    DbgPrint(\n'
    '                        "WolfFactory FINAL: 4-second repeat armed\\n");\n'
    '                }\n'
    '                g_runtime.wolf_idle_timer.threshold_ms = 4000u;\n'
    '                g_runtime.wolf_idle_timer.last_activity_ms = now_ms;\n'
    '                g_runtime.wolf_idle_timer.fired = 0u;\n',
    "4-second automatic repeat",
)

runtime_path.write_text(runtime)
print("Wolf idle timing applied: 12-second start, 4-second repeats")
