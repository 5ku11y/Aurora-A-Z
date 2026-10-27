#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8B integration anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    '#include <auroraaz/scene_gate_rev1655.h>\n',
    '#include <auroraaz/scene_gate_rev1655.h>\n'
    '#include <auroraaz/wolf_idle_timer.h>\n',
    "wolf idle timer include",
)

runtime = replace_once(
    runtime,
    '#define AZ_M3C_TELEMETRY_FLUSH_TICKS 20u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    '#define AZ_M3C_TELEMETRY_FLUSH_TICKS 20u\n'
    '#define WOLF_V8B_IDLE_MARKER_VERSION 1u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    "V8B marker version",
)

runtime = replace_once(
    runtime,
    '    uint32_t telemetry_flush_ticks;\n'
    '    uint32_t render_telemetry_flush_ticks;\n'
    '    uint32_t m3c_telemetry_flush_ticks;\n'
    '} AzRev1655Runtime;\n\n'
    'typedef struct AzM2bRenderMarker {',
    '    uint32_t telemetry_flush_ticks;\n'
    '    uint32_t render_telemetry_flush_ticks;\n'
    '    uint32_t m3c_telemetry_flush_ticks;\n'
    '    WolfIdleTimer wolf_idle_timer;\n'
    '} AzRev1655Runtime;\n\n'
    'typedef struct WolfV8bIdleMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t threshold_ms;\n'
    '    uint32_t armed;\n'
    '    uint32_t fired;\n'
    '    uint32_t reset_count;\n'
    '    uint32_t trigger_count;\n'
    '    uint32_t elapsed_ms;\n'
    '    uint32_t last_activity_serial;\n'
    '    uint32_t last_input_frame;\n'
    '    uint32_t runtime_state;\n'
    '    uint32_t requested_stage;\n'
    '    uint32_t effective_stage;\n'
    '    uint32_t consumed_controls;\n'
    '    uint32_t observation_drops;\n'
    '} WolfV8bIdleMarker;\n\n'
    'typedef char WolfV8bIdleMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8bIdleMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "runtime state and V8B marker",
)

runtime = replace_once(
    runtime,
    'static char g_input_telemetry_slot_b_path[] =\n'
    '    AZ_M2A_INPUT_TELEMETRY_SLOT_B_PATH;\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    'static char g_input_telemetry_slot_b_path[] =\n'
    '    AZ_M2A_INPUT_TELEMETRY_SLOT_B_PATH;\n'
    'static char g_wolf_v8b_idle_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8B-idle.bin";\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    "V8B marker path",
)

runtime = replace_once(
    runtime,
    'static void wait_for_input(void)\n'
    '{\n'
    '    int64_t interval = AZ_WORKER_INTERVAL_100NS;\n\n'
    '    (void)KeDelayExecutionThread(0u, 0u, &interval);\n'
    '}\n\n'
    'static uint8_t write_complete_file(',
    'static void wait_for_input(void)\n'
    '{\n'
    '    int64_t interval = AZ_WORKER_INTERVAL_100NS;\n\n'
    '    (void)KeDelayExecutionThread(0u, 0u, &interval);\n'
    '}\n\n'
    'static uint64_t wolf_runtime_now_ms(void)\n'
    '{\n'
    '    int64_t now_100ns = 0;\n\n'
    '    KeQuerySystemTime(&now_100ns);\n'
    '    if (now_100ns <= 0) {\n'
    '        return 0u;\n'
    '    }\n'
    '    return (uint64_t)now_100ns / 10000u;\n'
    '}\n\n'
    'static uint8_t write_complete_file(',
    "wall-clock helper",
)

write_complete_end = (
    '    return write_succeeded != 0 &&\n'
    '        bytes_written == size &&\n'
    '        close_succeeded != 0 ? 1u : 0u;\n'
    '}\n\n'
    '#if defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)'
)
marker_writer = (
    '    return write_succeeded != 0 &&\n'
    '        bytes_written == size &&\n'
    '        close_succeeded != 0 ? 1u : 0u;\n'
    '}\n\n'
    'static void flush_wolf_v8b_idle_marker(void)\n'
    '{\n'
    '    AzInputDetourStatus status;\n'
    '    const uint64_t now_ms = wolf_runtime_now_ms();\n'
    '    WolfV8bIdleMarker marker = {\n'
    "        {'W', 'F', '8', 'B'},\n"
    '        WOLF_V8B_IDLE_MARKER_VERSION,\n'
    '        (uint32_t)sizeof(WolfV8bIdleMarker),\n'
    '        WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS,\n'
    '        g_runtime.wolf_idle_timer.fired == 0u ? 1u : 0u,\n'
    '        g_runtime.wolf_idle_timer.fired != 0u ? 1u : 0u,\n'
    '        g_runtime.wolf_idle_timer.reset_count,\n'
    '        g_runtime.wolf_idle_timer.trigger_count,\n'
    '        wolf_idle_timer_elapsed_ms(&g_runtime.wolf_idle_timer, now_ms),\n'
    '        g_runtime.wolf_idle_timer.last_activity_serial,\n'
    '        g_runtime.wolf_idle_timer.last_input_frame,\n'
    '        load_u32(&g_runtime.state),\n'
    '        0u,\n'
    '        0u,\n'
    '        0u,\n'
    '        0u\n'
    '    };\n\n'
    '    az_rev1655_input_detour_snapshot_status(&status);\n'
    '    marker.requested_stage = (uint32_t)status.requested_stage;\n'
    '    marker.effective_stage = (uint32_t)status.effective_stage;\n'
    '    marker.consumed_controls = status.consumed_controls;\n'
    '    marker.observation_drops = status.observation_drops;\n'
    '    if (write_complete_file(\n'
    '            g_wolf_v8b_idle_marker_path,\n'
    '            (const uint8_t *)&marker,\n'
    '            (uint32_t)sizeof(marker)) == 0u) {\n'
    '        DbgPrint("WolfFactory V8B: idle marker write failed\\n");\n'
    '    }\n'
    '}\n\n'
    '#if defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)'
)
runtime = replace_once(
    runtime, write_complete_end, marker_writer, "V8B marker writer"
)

runtime = replace_once(
    runtime,
    '        log_observation(&observation);\n'
    '        (void)az_m2a_input_telemetry_record(',
    '        {\n'
    '            const uint8_t was_fired = g_runtime.wolf_idle_timer.fired;\n\n'
    '            (void)wolf_idle_timer_note_activity(\n'
    '                &g_runtime.wolf_idle_timer,\n'
    '                wolf_runtime_now_ms(),\n'
    '                observation.serial,\n'
    '                observation.input_frame);\n'
    '            if (was_fired != 0u) {\n'
    '                DbgPrint(\n'
    '                    "WolfFactory V8B: idle timer re-armed by input\\n");\n'
    '                flush_wolf_v8b_idle_marker();\n'
    '            }\n'
    '        }\n\n'
    '        log_observation(&observation);\n'
    '        (void)az_m2a_input_telemetry_record(',
    "activity reset in observation drain",
)

runtime = replace_once(
    runtime,
    '    if (state == (uint32_t)AZ_REV1655_RUNTIME_RUNNING) {\n'
    '        DbgPrint(',
    '    if (state == (uint32_t)AZ_REV1655_RUNTIME_RUNNING) {\n'
    '        wolf_idle_timer_init(\n'
    '            &g_runtime.wolf_idle_timer,\n'
    '            wolf_runtime_now_ms(),\n'
    '            WOLF_IDLE_TIMER_DEFAULT_THRESHOLD_MS);\n'
    '        flush_wolf_v8b_idle_marker();\n'
    '        DbgPrint(',
    "timer initialization",
)

runtime = replace_once(
    runtime,
    '    while (load_u32(&g_runtime.state) ==\n'
    '           (uint32_t)AZ_REV1655_RUNTIME_RUNNING) {\n'
    '        (void)drain_observation_pass();\n'
    '        flush_input_telemetry(0u);',
    '    while (load_u32(&g_runtime.state) ==\n'
    '           (uint32_t)AZ_REV1655_RUNTIME_RUNNING) {\n'
    '        (void)drain_observation_pass();\n'
    '        if (wolf_idle_timer_step(\n'
    '                &g_runtime.wolf_idle_timer,\n'
    '                wolf_runtime_now_ms()) == WOLF_IDLE_TIMER_FIRED) {\n'
    '            DbgPrint(\n'
    '                "WolfFactory V8B: 12-second idle trigger fired\\n");\n'
    '            flush_wolf_v8b_idle_marker();\n'
    '        }\n'
    '        flush_input_telemetry(0u);',
    "timer worker step",
)

runtime_path.write_text(runtime)

build_path = Path("scripts/build-openxechain.sh")
build = build_path.read_text()
build = replace_once(
    build,
    '    "${repo_root}/native/src/m2a_input_telemetry.c" \\\n'
    '    "${repo_root}/native/src/rev1655_runtime.c"',
    '    "${repo_root}/native/src/m2a_input_telemetry.c" \\\n'
    '    "${repo_root}/native/src/wolf_idle_timer.c" \\\n'
    '    "${repo_root}/native/src/rev1655_runtime.c"',
    "OpenXeChain source list",
)
build_path.write_text(build)

print("Wolf V8B runtime integration applied")
