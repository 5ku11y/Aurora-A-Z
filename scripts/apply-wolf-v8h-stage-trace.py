#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8H stage-trace anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    '#define WOLF_V8F_USER_INDEX_ANY 0xFFu\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    '#define WOLF_V8F_USER_INDEX_ANY 0xFFu\n'
    '#define WOLF_V8H_TRACE_MARKER_VERSION 1u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    "V8H marker version",
)

runtime = replace_once(
    runtime,
    'typedef char WolfV8fSceneMarkerMustBe80Bytes[\n'
    '    sizeof(WolfV8fSceneMarker) == 80u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8fSceneMarkerMustBe80Bytes[\n'
    '    sizeof(WolfV8fSceneMarker) == 80u ? 1 : -1];\n\n'
    'typedef struct WolfV8hTraceMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t stage;\n'
    '    uint32_t runtime_state;\n'
    '    uint32_t idle_trigger_count;\n'
    '    uint32_t pending_value;\n'
    '    uint32_t attempt_count;\n'
    '    uint32_t ui_thread_id;\n'
    '    uint32_t create_address;\n'
    '    uint32_t create_status;\n'
    '    uint32_t created_scene;\n'
    '    uint32_t destroy_address;\n'
    '    uint32_t destroy_status;\n'
    '    uint32_t reserved0;\n'
    '    uint32_t reserved1;\n'
    '} WolfV8hTraceMarker;\n\n'
    'typedef char WolfV8hTraceMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8hTraceMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8H marker structure",
)

runtime = replace_once(
    runtime,
    'static char g_wolf_v8f_scene_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8G-create.bin";\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    'static char g_wolf_v8f_scene_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8G-create.bin";\n'
    'static char g_wolf_v8h_trace_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8H-trace.bin";\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    "V8H marker path",
)

runtime = replace_once(
    runtime,
    'static void flush_wolf_v8b_idle_marker(void)\n'
    '{',
    '''static void wolf_v8h_write_trace(
    uint32_t stage,
    uint32_t ui_thread_id,
    uint32_t create_address,
    uint32_t create_status,
    uint32_t created_scene,
    uint32_t destroy_address,
    uint32_t destroy_status)
{
    WolfV8hTraceMarker marker = {
        {'W', 'F', '8', 'H'},
        WOLF_V8H_TRACE_MARKER_VERSION,
        (uint32_t)sizeof(WolfV8hTraceMarker),
        stage,
        load_u32(&g_runtime.state),
        g_runtime.wolf_idle_timer.trigger_count,
        load_u32(&g_runtime.wolf_v8f_scene_pending),
        load_u32(&g_runtime.wolf_v8f_attempt_count),
        ui_thread_id,
        create_address,
        create_status,
        created_scene,
        destroy_address,
        destroy_status,
        0u,
        0u
    };

    if (write_complete_file(
            g_wolf_v8h_trace_marker_path,
            (const uint8_t *)&marker,
            (uint32_t)sizeof(marker)) == 0u) {
        DbgPrint("WolfFactory V8H: trace marker write failed\\n");
    }
}

static void flush_wolf_v8b_idle_marker(void)
{''',
    "V8H trace writer",
)

runtime = replace_once(
    runtime,
    '        flush_wolf_v8b_idle_marker();\n'
    '        DbgPrint(',
    '        flush_wolf_v8b_idle_marker();\n'
    '        wolf_v8h_write_trace(0u, 0u, 0u, 0xFFFFFFFFu, 0u, 0u, 0xFFFFFFFFu);\n'
    '        DbgPrint(',
    "startup loaded trace",
)

runtime = replace_once(
    runtime,
    '            store_u32(&g_runtime.wolf_v8f_scene_pending, 1u);\n'
    '        }\n'
    '        flush_input_telemetry(0u);',
    '            store_u32(&g_runtime.wolf_v8f_scene_pending, 1u);\n'
    '            wolf_v8h_write_trace(1u, 0u, 0u, 0xFFFFFFFFu, 0u, 0u, 0xFFFFFFFFu);\n'
    '        }\n'
    '        flush_input_telemetry(0u);',
    "idle armed trace",
)

runtime = replace_once(
    runtime,
    '    if (load_u32(&g_runtime.wolf_v8f_scene_pending) != 0u) {\n'
    '        if (__atomic_exchange_n(',
    '    if (load_u32(&g_runtime.wolf_v8f_scene_pending) != 0u) {\n'
    '        wolf_v8h_write_trace(2u, GetCurrentThreadId(), 0u, 0xFFFFFFFFu, 0u, 0u, 0xFFFFFFFFu);\n'
    '        if (__atomic_exchange_n(',
    "UI dispatch trace",
)

runtime = replace_once(
    runtime,
    '    if (create_fn != NULL) {\n'
    '        marker.create_status = (uint32_t)create_fn(',
    '    if (create_fn != NULL) {\n'
    '        wolf_v8h_write_trace(\n'
    '            3u, marker.ui_thread_id, marker.create_address,\n'
    '            marker.create_status, 0u, marker.destroy_address,\n'
    '            marker.destroy_status);\n'
    '        marker.create_status = (uint32_t)create_fn(',
    "before XuiSceneCreate trace",
)

runtime = replace_once(
    runtime,
    '        marker.created_scene = scene;\n'
    '        if ((int32_t)marker.create_status >= 0 && scene != 0u) {',
    '        marker.created_scene = scene;\n'
    '        wolf_v8h_write_trace(\n'
    '            4u, marker.ui_thread_id, marker.create_address,\n'
    '            marker.create_status, marker.created_scene,\n'
    '            marker.destroy_address, marker.destroy_status);\n'
    '        if ((int32_t)marker.create_status >= 0 && scene != 0u) {',
    "after XuiSceneCreate trace",
)

runtime = replace_once(
    runtime,
    '    wolf_v8f_write_scene_marker(&marker);\n'
    '    DbgPrint(',
    '    wolf_v8f_write_scene_marker(&marker);\n'
    '    wolf_v8h_write_trace(\n'
    '        5u, marker.ui_thread_id, marker.create_address,\n'
    '        marker.create_status, marker.created_scene,\n'
    '        marker.destroy_address, marker.destroy_status);\n'
    '    DbgPrint(',
    "final trace",
)

runtime_path.write_text(runtime)
print("Wolf V8H staged dispatch/create trace applied")
