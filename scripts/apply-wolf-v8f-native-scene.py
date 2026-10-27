#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8F native scene anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    '#define WOLF_V8E_XUI_RESOLVED_ALL 0x0Fu\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    '#define WOLF_V8E_XUI_RESOLVED_ALL 0x0Fu\n'
    '#define WOLF_V8F_SCENE_MARKER_VERSION 1u\n'
    '#define WOLF_V8F_XUI_DESTROY_ORDINAL 806u\n'
    '#define WOLF_V8F_USER_INDEX_ANY 0xFFu\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    "V8F constants",
)

runtime = replace_once(
    runtime,
    'typedef int32_t (*AzXuiTreeGetFocusFn)(uint32_t, uint32_t *);\n'
    'typedef struct AzXInputGamepadState {',
    'typedef int32_t (*AzXuiTreeGetFocusFn)(uint32_t, uint32_t *);\n'
    'typedef int32_t (*WolfV8fXuiSceneCreateFn)(\n'
    '    const uint16_t *, const uint16_t *, void *, uint32_t *);\n'
    'typedef int32_t (*WolfV8fXuiSceneNavigateForwardFn)(\n'
    '    uint32_t, int32_t, uint32_t, uint32_t);\n'
    'typedef void (*WolfV8fXuiDestroyObjectFn)(uint32_t);\n'
    'typedef struct AzXInputGamepadState {',
    "V8F XUI typedefs",
)

runtime = replace_once(
    runtime,
    '    WolfIdleTimer wolf_idle_timer;\n'
    '} AzRev1655Runtime;',
    '    WolfIdleTimer wolf_idle_timer;\n'
    '    volatile uint32_t wolf_v8f_scene_pending;\n'
    '    volatile uint32_t wolf_v8f_attempt_count;\n'
    '    volatile uint32_t wolf_v8f_last_scene;\n'
    '} AzRev1655Runtime;',
    "V8F runtime fields",
)

runtime = replace_once(
    runtime,
    'typedef char WolfV8eXuiMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8eXuiMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8eXuiMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8eXuiMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct WolfV8fSceneMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t runtime_state;\n'
    '    uint32_t idle_trigger_count;\n'
    '    uint32_t parent_scene;\n'
    '    uint32_t module_status;\n'
    '    uint32_t xam_handle;\n'
    '    uint32_t create_status;\n'
    '    uint32_t create_address;\n'
    '    uint32_t created_scene;\n'
    '    uint32_t navigate_status;\n'
    '    uint32_t navigate_address;\n'
    '    uint32_t destroy_status;\n'
    '    uint32_t destroy_address;\n'
    '    uint32_t heading_set_status;\n'
    '    uint32_t attempt_count;\n'
    '    uint32_t pending_before;\n'
    '    uint32_t ui_thread_id;\n'
    '    uint32_t completed;\n'
    '} WolfV8fSceneMarker;\n\n'
    'typedef char WolfV8fSceneMarkerMustBe80Bytes[\n'
    '    sizeof(WolfV8fSceneMarker) == 80u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8F marker structure",
)

runtime = replace_once(
    runtime,
    'static char g_wolf_v8e_xui_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8E-xui.bin";\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    'static char g_wolf_v8e_xui_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8E-xui.bin";\n'
    'static char g_wolf_v8f_scene_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8F-scene.bin";\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    "V8F marker path",
)

runtime = replace_once(
    runtime,
    '            DbgPrint(\n'
    '                "WolfFactory V8B: 12-second idle trigger fired\\n");\n'
    '            flush_wolf_v8b_idle_marker();\n'
    '        }\n'
    '        flush_input_telemetry(0u);',
    '            DbgPrint(\n'
    '                "WolfFactory V8B: 12-second idle trigger fired\\n");\n'
    '            flush_wolf_v8b_idle_marker();\n'
    '            store_u32(&g_runtime.wolf_v8f_scene_pending, 1u);\n'
    '        }\n'
    '        flush_input_telemetry(0u);',
    "V8F arm on idle fire",
)

scene_helper_anchor = 'static void module_ui_tick(void *context)\n{\n'
if scene_helper_anchor not in runtime:
    raise SystemExit("Wolf V8F native scene anchor missing: module_ui_tick")

scene_helpers = r'''static void wolf_v8f_write_scene_marker(
    const WolfV8fSceneMarker *marker)
{
    if (marker == NULL || write_complete_file(
            g_wolf_v8f_scene_marker_path,
            (const uint8_t *)marker,
            (uint32_t)sizeof(*marker)) == 0u) {
        DbgPrint("WolfFactory V8F: scene marker write failed\n");
    }
}

static void wolf_v8f_try_native_scene(uint32_t parent_scene)
{
    static const uint16_t base_path[] = {
        'f','i','l','e',':','/','/','g','a','m','e',':','/','D','a','t','a','/',0
    };
    static const uint16_t scene_path[] = {
        'A','u','r','o','r','a','A','Z','_','S','e','t','t','i','n','g','s','.',
        'x','u','r',0
    };
    static const uint16_t heading_id[] = {
        'M','o','d','e','H','e','a','d','i','n','g',0
    };
    static const uint16_t pass_heading[] = {
        'W','O','L','F',' ','F','A','C','T','O','R','Y',' ','V','8','F',' ','/','/',
        ' ','N','A','T','I','V','E',' ','X','U','I',' ','P','A','S','S',0
    };
    HMODULE xam = NULL;
    void *create_proc = NULL;
    void *navigate_proc = NULL;
    void *destroy_proc = NULL;
    uint32_t scene = 0u;
    uint32_t heading = 0u;
    WolfV8fSceneMarker marker;
    WolfV8fXuiSceneCreateFn create_fn = NULL;
    WolfV8fXuiSceneNavigateForwardFn navigate_fn = NULL;
    WolfV8fXuiDestroyObjectFn destroy_fn = NULL;

    memset(&marker, 0, sizeof(marker));
    marker.magic[0] = 'W';
    marker.magic[1] = 'F';
    marker.magic[2] = '8';
    marker.magic[3] = 'F';
    marker.version = WOLF_V8F_SCENE_MARKER_VERSION;
    marker.record_size = (uint32_t)sizeof(marker);
    marker.runtime_state = load_u32(&g_runtime.state);
    marker.idle_trigger_count = g_runtime.wolf_idle_timer.trigger_count;
    marker.parent_scene = parent_scene;
    marker.create_status = 0xFFFFFFFFu;
    marker.navigate_status = 0xFFFFFFFFu;
    marker.destroy_status = 0xFFFFFFFFu;
    marker.heading_set_status = 0xFFFFFFFFu;
    marker.attempt_count = __atomic_add_fetch(
        &g_runtime.wolf_v8f_attempt_count, 1u, __ATOMIC_ACQ_REL);
    marker.pending_before = 1u;
    marker.ui_thread_id = GetCurrentThreadId();

    marker.module_status = (uint32_t)XexGetModuleHandle("xam.xex", &xam);
    if (marker.module_status == 0u && xam != NULL &&
        (uintptr_t)xam <= UINT32_MAX) {
        marker.xam_handle = (uint32_t)(uintptr_t)xam;

        marker.create_status = wolf_v8e_resolve_xam_export(
            xam, WOLF_V8E_XUI_CREATE_ORDINAL, &marker.create_address);
        if (marker.create_status == 0u && marker.create_address != 0u) {
            create_proc = (void *)(uintptr_t)marker.create_address;
            create_fn = (WolfV8fXuiSceneCreateFn)(uintptr_t)create_proc;
        }

        marker.navigate_status = wolf_v8e_resolve_xam_export(
            xam, WOLF_V8E_XUI_NAVIGATE_FORWARD_ORDINAL,
            &marker.navigate_address);
        if (marker.navigate_status == 0u && marker.navigate_address != 0u) {
            navigate_proc = (void *)(uintptr_t)marker.navigate_address;
            navigate_fn = (WolfV8fXuiSceneNavigateForwardFn)
                (uintptr_t)navigate_proc;
        }

        marker.destroy_status = wolf_v8e_resolve_xam_export(
            xam, WOLF_V8F_XUI_DESTROY_ORDINAL, &marker.destroy_address);
        if (marker.destroy_status == 0u && marker.destroy_address != 0u) {
            destroy_proc = (void *)(uintptr_t)marker.destroy_address;
            destroy_fn = (WolfV8fXuiDestroyObjectFn)(uintptr_t)destroy_proc;
        }
    }

    if (parent_scene != 0u && create_fn != NULL && navigate_fn != NULL) {
        marker.create_status = (uint32_t)create_fn(
            base_path, scene_path, NULL, &scene);
        marker.created_scene = scene;
        if ((int32_t)marker.create_status >= 0 && scene != 0u) {
            if (resolve_icon_xui() != 0u &&
                find_live_descendant(scene, heading_id, &heading) >= 0 &&
                heading != 0u && g_runtime.xui_set_text != NULL) {
                marker.heading_set_status = (uint32_t)
                    g_runtime.xui_set_text(heading, pass_heading);
            }
            marker.navigate_status = (uint32_t)navigate_fn(
                parent_scene, 0, scene, WOLF_V8F_USER_INDEX_ANY);
            if ((int32_t)marker.navigate_status >= 0) {
                marker.completed = 1u;
                store_u32(&g_runtime.wolf_v8f_last_scene, scene);
            }
            else if (destroy_fn != NULL) {
                destroy_fn(scene);
            }
        }
    }

    wolf_v8f_write_scene_marker(&marker);
    DbgPrint(
        "WolfFactory V8F: scene attempt=%u create=0x%08X nav=0x%08X "
        "scene=0x%08X complete=%u\n",
        marker.attempt_count,
        marker.create_status,
        marker.navigate_status,
        marker.created_scene,
        marker.completed);
}

'''
runtime = runtime.replace(scene_helper_anchor, scene_helpers + scene_helper_anchor, 1)

runtime = replace_once(
    runtime,
    '    scene_generation = az_module_settings_scene_generation();\n'
    '    module_scene = live_module_settings_scene_handle();\n'
    '    if (scene_generation != 0u &&',
    '    scene_generation = az_module_settings_scene_generation();\n'
    '    module_scene = live_module_settings_scene_handle();\n'
    '    if (load_u32(&g_runtime.wolf_v8f_scene_pending) != 0u &&\n'
    '        module_scene != 0u && g_runtime.settings_dialog_active != 0u) {\n'
    '        if (__atomic_exchange_n(\n'
    '                &g_runtime.wolf_v8f_scene_pending,\n'
    '                0u,\n'
    '                __ATOMIC_ACQ_REL) != 0u) {\n'
    '            wolf_v8f_try_native_scene(module_scene);\n'
    '            return;\n'
    '        }\n'
    '    }\n'
    '    if (scene_generation != 0u &&',
    "V8F UI-thread scene dispatch",
)

runtime_path.write_text(runtime)
print("Wolf V8F native XUI scene integration applied")
