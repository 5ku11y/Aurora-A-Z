#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8G create-probe anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

# V8F proved the idle arm and XUI resolver, but hardware showed Aurora's stock
# Network Debugger row has no settings page on this console.  V8G therefore
# removes the settings-dialog dependency and performs a native XuiSceneCreate
# probe directly from the already-validated Aurora UI-thread callback.  The
# created scene is immediately destroyed; navigation is deliberately deferred
# until scene creation itself has been proven on hardware.
runtime = replace_once(
    runtime,
    '"game:\\\\Data\\\\Logs\\\\WolfFactory-V8F-scene.bin";',
    '"game:\\\\Data\\\\Logs\\\\WolfFactory-V8G-create.bin";',
    "V8G marker path",
)

runtime = replace_once(
    runtime,
    "    marker.magic[3] = 'F';",
    "    marker.magic[3] = 'G';",
    "V8G marker magic",
)

runtime = runtime.replace("WolfFactory V8F:", "WolfFactory V8G:")
runtime = runtime.replace(
    "'8','F',' ','/','/',",
    "'8','G',' ','/','/',",
    1,
)

runtime = replace_once(
    runtime,
    '    if (parent_scene != 0u && create_fn != NULL && navigate_fn != NULL) {',
    '    (void)navigate_fn;\n    if (create_fn != NULL) {',
    "create without parent scene",
)

old_navigation = '''            marker.navigate_status = (uint32_t)navigate_fn(
                parent_scene, 0, scene, WOLF_V8F_USER_INDEX_ANY);
            if ((int32_t)marker.navigate_status >= 0) {
                marker.completed = 1u;
                store_u32(&g_runtime.wolf_v8f_last_scene, scene);
            }
            else if (destroy_fn != NULL) {
                destroy_fn(scene);
            }
'''
new_navigation = '''            /* V8G is intentionally create-only.  A successful create proves
             * the native loader/path/XUR combination without requiring a
             * live Aurora settings scene.  Destroy immediately so the probe
             * cannot strand an unattached XUI object. */
            marker.navigate_status = 0xFFFFFFFEu;
            marker.completed = 1u;
            store_u32(&g_runtime.wolf_v8f_last_scene, scene);
            if (destroy_fn != NULL) {
                destroy_fn(scene);
                marker.destroy_status = 0u;
            }
'''
runtime = replace_once(
    runtime,
    old_navigation,
    new_navigation,
    "replace navigation with create/destroy probe",
)

old_dispatch = '''    if (load_u32(&g_runtime.wolf_v8f_scene_pending) != 0u &&
        module_scene != 0u && g_runtime.settings_dialog_active != 0u) {
        if (__atomic_exchange_n(
                &g_runtime.wolf_v8f_scene_pending,
                0u,
                __ATOMIC_ACQ_REL) != 0u) {
            wolf_v8f_try_native_scene(module_scene);
            return;
        }
    }
'''
new_dispatch = '''    if (load_u32(&g_runtime.wolf_v8f_scene_pending) != 0u) {
        if (__atomic_exchange_n(
                &g_runtime.wolf_v8f_scene_pending,
                0u,
                __ATOMIC_ACQ_REL) != 0u) {
            wolf_v8f_try_native_scene(0u);
            return;
        }
    }
'''
runtime = replace_once(
    runtime,
    old_dispatch,
    new_dispatch,
    "remove settings-dialog gate",
)

# V8H diagnostics are folded into this branch so the already-warmed toolchain
# cache remains usable.  The trace marker is overwritten at each milestone:
# 0 runtime loaded, 1 idle armed, 2 UI dispatch saw pending, 3 immediately
# before XuiSceneCreate, 4 immediately after it returned, 5 final cleanup.
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
    '        write_wolf_v8e_xui_resolver_marker();\n'
    '        DbgPrint(',
    '        flush_wolf_v8b_idle_marker();\n'
    '        write_wolf_v8e_xui_resolver_marker();\n'
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
print("Wolf V8G create probe with V8H stage trace applied")
