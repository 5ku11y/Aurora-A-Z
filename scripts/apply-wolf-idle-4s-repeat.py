#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf idle 4s anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

# Final Lazy Susan timing: a fresh idle session waits five minutes before the
# first automatic move. After that first move, untouched coverflow continues
# at the already hardware-proven four-second cadence.

# Report the currently active interval instead of always claiming the original
# default threshold.
runtime = replace_once(
    runtime,
    '    marker.threshold_ms = WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS;\n',
    '    marker.threshold_ms = (uint32_t)g_runtime.wolf_idle_timer.threshold_ms;\n',
    "telemetry active threshold",
)

# Startup must begin as a fresh five-minute idle session too.
runtime = replace_once(
    runtime,
    '        wolf_idle_timer_init(\n'
    '            &g_runtime.wolf_idle_timer,\n'
    '            wolf_runtime_now_ms(),\n'
    '            WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS);\n'
    '        flush_wolf_v8b_idle_marker();\n',
    '        wolf_idle_timer_init(\n'
    '            &g_runtime.wolf_idle_timer,\n'
    '            wolf_runtime_now_ms(),\n'
    '            300000u);\n'
    '        DbgPrint("WolfFactory FINAL: 5-minute initial idle armed\\n");\n'
    '        flush_wolf_v8b_idle_marker();\n',
    "startup five-minute idle",
)

# Any real controller activity starts a brand-new idle session: wait five
# minutes again before automation resumes.
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
    '            g_runtime.wolf_idle_timer.threshold_ms = 300000u;\n'
    '            az_rev1655_input_detour_cancel_synthetic_key();\n',
    "real input restores five-minute start",
)

# Leaving coverflow/settings/game transition is also a fresh idle session on
# return, so time away never resumes the four-second rotation cadence.
runtime = replace_once(
    runtime,
    '                g_runtime.wolf_idle_timer.last_activity_ms = now_ms;\n'
    '                g_runtime.wolf_idle_timer.fired = 0u;\n'
    '                az_rev1655_input_detour_cancel_synthetic_key();\n',
    '                g_runtime.wolf_idle_timer.threshold_ms = 300000u;\n'
    '                g_runtime.wolf_idle_timer.last_activity_ms = now_ms;\n'
    '                g_runtime.wolf_idle_timer.fired = 0u;\n'
    '                az_rev1655_input_detour_cancel_synthetic_key();\n',
    "dashboard pause restores five-minute start",
)

# The old V8B diagnostic was tied to the original 12-second prototype. Keep the
# diagnostic accurate now that the first threshold is five minutes and repeats
# are four seconds.
runtime = replace_once(
    runtime,
    '                "WolfFactory V8B: 12-second idle trigger fired\\n");\n',
    '                "WolfFactory V8B: idle trigger fired\\n");\n',
    "generic idle-trigger diagnostic",
)

# Once the first five-minute move fires, an untouched dashboard becomes the
# proven carousel: one additional synthetic DPAD_LEFT every four seconds. Real
# input or leaving the dashboard resets this back to five minutes.
runtime = replace_once(
    runtime,
    '                /* Re-arm immediately so an untouched dashboard advances by\n'
    '                 * exactly one cover per idle interval. Synthetic input is not\n'
    '                 * reported as user activity. */\n'
    '                g_runtime.wolf_idle_timer.last_activity_ms = now_ms;\n'
    '                g_runtime.wolf_idle_timer.fired = 0u;\n',
    '                /* First idle move waits five minutes. After it fires, keep\n'
    '                 * the untouched dashboard rotating one cover every 4 seconds.\n'
    '                 * Real input or leaving coverflow restores five minutes. */\n'
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
print("Wolf idle timing applied: 5-minute start, 4-second repeats")
