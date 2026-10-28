#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8O visible-scene anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    '#define WOLF_V8N_CUSTOM_MARKER_VERSION 1u\n\n#define AZ_BROWSE_APPLY_NONE 0u',
    '#define WOLF_V8N_CUSTOM_MARKER_VERSION 1u\n'
    '#define WOLF_V8O_VISIBLE_MARKER_VERSION 1u\n'
    '#define WOLF_V8O_VISIBLE_FRAMES 180u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    "V8O constants",
)

runtime = replace_once(
    runtime,
    'typedef int32_t (*WolfV8fXuiSceneNavigateForwardFn)(\n'
    '    uint32_t, int32_t, uint32_t, uint32_t);\n'
    'typedef void (*WolfV8fXuiDestroyObjectFn)(uint32_t);',
    'typedef int32_t (*WolfV8fXuiSceneNavigateForwardFn)(\n'
    '    uint32_t, int32_t, uint32_t, uint32_t);\n'
    'typedef int32_t (*WolfV8oXuiSceneNavigateBackFn)(\n'
    '    uint32_t, uint32_t, uint32_t);\n'
    'typedef void (*WolfV8fXuiDestroyObjectFn)(uint32_t);',
    "V8O navigate-back typedef",
)

runtime = replace_once(
    runtime,
    'typedef char WolfV8nCustomMarkerMustBe80Bytes[\n'
    '    sizeof(WolfV8nCustomMarker) == 80u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8nCustomMarkerMustBe80Bytes[\n'
    '    sizeof(WolfV8nCustomMarker) == 80u ? 1 : -1];\n\n'
    'typedef struct WolfV8oVisibleMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t write_ok;\n'
    '    uint32_t xur_size;\n'
    '    uint32_t xur_version_be;\n'
    '    uint32_t custom_fnv1a;\n'
    '    uint32_t gate_reason;\n'
    '    uint32_t main_scene;\n'
    '    uint32_t create_status;\n'
    '    uint32_t created_scene;\n'
    '    uint32_t title_set_status;\n'
    '    uint32_t status_set_status;\n'
    '    uint32_t forward_status;\n'
    '    uint32_t forward_address;\n'
    '    uint32_t back_status;\n'
    '    uint32_t back_address;\n'
    '    uint32_t ui_thread_id;\n'
    '    uint32_t visible_frames;\n'
    '    uint32_t phase;\n'
    '    uint32_t attempt_count;\n'
    '    uint32_t completed;\n'
    '    uint32_t reserved0;\n'
    '    uint32_t reserved1;\n'
    '} WolfV8oVisibleMarker;\n\n'
    'typedef char WolfV8oVisibleMarkerMustBe96Bytes[\n'
    '    sizeof(WolfV8oVisibleMarker) == 96u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8O marker structure",
)

runtime = replace_once(
    runtime,
    'static char g_wolf_v8n_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8N-custom-v8.bin";',
    'static char g_wolf_v8o_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8O-visible.bin";\n'
    'static char g_wolf_v8o_xur_path[] =\n'
    '    "game:\\\\Data\\\\WolfFactory-V8O-visible.xur";\n'
    'static volatile uint32_t g_wolf_v8o_phase;\n'
    'static uint32_t g_wolf_v8o_scene;\n'
    'static uint32_t g_wolf_v8o_parent;\n'
    'static uint32_t g_wolf_v8o_frames;\n'
    'static WolfV8oXuiSceneNavigateBackFn g_wolf_v8o_back_fn;\n'
    'static WolfV8oVisibleMarker g_wolf_v8o_marker;\n\n'
    'static char g_wolf_v8n_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8N-custom-v8.bin";',
    "V8O paths and state",
)

runtime = replace_once(
    runtime,
    'static void wolf_v8n_write_custom_marker(const WolfV8nCustomMarker *marker)\n{',
    '''static void wolf_v8o_write_visible_marker(const WolfV8oVisibleMarker *marker)
{
    if (marker == NULL || write_complete_file(
            g_wolf_v8o_marker_path,
            (const uint8_t *)marker,
            (uint32_t)sizeof(*marker)) == 0u) {
        DbgPrint("WolfFactory V8O: visible marker write failed\\n");
    }
}

static void wolf_v8n_write_custom_marker(const WolfV8nCustomMarker *marker)
{''',
    "V8O marker writer",
)

runtime = replace_once(
    runtime,
    "    static const uint16_t heading_id[] = {\n",
    "    static const uint16_t v8o_scene_path[] = {\n"
    "        'W','o','l','f','F','a','c','t','o','r','y','-','V','8','O','-',\n"
    "        'v','i','s','i','b','l','e','.','x','u','r',0\n"
    "    };\n"
    "    static const uint16_t v8o_title_id[] = {\n"
    "        'W','o','l','f','T','i','t','l','e','N','a','m','e',0\n"
    "    };\n"
    "    static const uint16_t v8o_status_id[] = {\n"
    "        'W','o','l','f','F','a','c','t','o','r','y','S','t','a','t','u','s',0\n"
    "    };\n"
    "    static const uint16_t v8o_title_text[] = {\n"
    "        'W','O','L','F',' ','F','A','C','T','O','R','Y',' ','V','8','O',0\n"
    "    };\n"
    "    static const uint16_t v8o_status_text[] = {\n"
    "        'N','A','T','I','V','E',' ','X','U','I',' ','V','8',' ','/','/',' ',\n"
    "        'V','I','S','I','B','L','E',' ','P','A','S','S',0\n"
    "    };\n"
    "    static const uint16_t heading_id[] = {\n",
    "V8O scene strings",
)

runtime = replace_once(
    runtime,
    '    WolfV8nCustomMarker v8n;\n'
    '    WolfV8fXuiSceneCreateFn create_fn = NULL;',
    '    WolfV8nCustomMarker v8n;\n'
    '    WolfV8oVisibleMarker v8o;\n'
    '    WolfV8fXuiSceneCreateFn create_fn = NULL;',
    "V8O local marker",
)

runtime = replace_once(
    runtime,
    '    v8n.create_status = 0xFFFFFFFFu;\n'
    "    marker.magic[0] = 'W';",
    '    v8n.create_status = 0xFFFFFFFFu;\n'
    '    memset(&v8o, 0, sizeof(v8o));\n'
    "    v8o.magic[0] = 'W';\n"
    "    v8o.magic[1] = 'F';\n"
    "    v8o.magic[2] = '8';\n"
    "    v8o.magic[3] = 'O';\n"
    '    v8o.version = WOLF_V8O_VISIBLE_MARKER_VERSION;\n'
    '    v8o.record_size = (uint32_t)sizeof(v8o);\n'
    '    v8o.xur_size = (uint32_t)sizeof(g_wolf_v8n_custom_xur);\n'
    '    v8o.xur_version_be = 8u;\n'
    '    v8o.custom_fnv1a = v8n.custom_fnv1a;\n'
    '    v8o.create_status = 0xFFFFFFFFu;\n'
    '    v8o.title_set_status = 0xFFFFFFFFu;\n'
    '    v8o.status_set_status = 0xFFFFFFFFu;\n'
    '    v8o.forward_status = 0xFFFFFFFFu;\n'
    '    v8o.back_status = 0xFFFFFFFFu;\n'
    "    marker.magic[0] = 'W';",
    "V8O marker initialization",
)

v8o_attempt = r'''        /* V8O: navigate the proven custom XUIB v8 scene forward from the
         * exact focused Aurora_Main.xur handle discovered by the scene gate.
         * A render-tick state machine will navigate back after ~180 frames. */
        if (v8n.completed != 0u && load_u32(&g_wolf_v8o_phase) == 0u) {
            AzSceneGateDecision v8o_gate;
            uint32_t visible_scene = 0u;
            uint32_t title_element = 0u;
            uint32_t status_element = 0u;
            uint32_t back_resolve_status = 0xFFFFFFFFu;

            memset(&v8o_gate, 0, sizeof(v8o_gate));
            (void)az_rev1655_scene_gate_probe(&v8o_gate);
            v8o.gate_reason = (uint32_t)v8o_gate.reason;
            v8o.main_scene = v8o_gate.main_scene_handle;
            v8o.forward_address = marker.navigate_address;
            v8o.ui_thread_id = marker.ui_thread_id;
            v8o.attempt_count = marker.attempt_count;
            v8o.write_ok = write_complete_file(
                g_wolf_v8o_xur_path,
                g_wolf_v8n_custom_xur,
                (uint32_t)sizeof(g_wolf_v8n_custom_xur));

            if (xam != NULL) {
                back_resolve_status = wolf_v8e_resolve_xam_export(
                    xam,
                    WOLF_V8E_XUI_NAVIGATE_BACK_ORDINAL,
                    &v8o.back_address);
                if (back_resolve_status == 0u && v8o.back_address != 0u) {
                    g_wolf_v8o_back_fn = (WolfV8oXuiSceneNavigateBackFn)
                        (uintptr_t)v8o.back_address;
                }
            }
            if (back_resolve_status != 0u) {
                v8o.back_status = back_resolve_status;
            }

            if (v8o.write_ok != 0u &&
                v8o_gate.allows_capture != 0u &&
                v8o.main_scene != 0u &&
                create_fn != NULL && navigate_fn != NULL &&
                g_wolf_v8o_back_fn != NULL) {
                v8o.create_status = (uint32_t)create_fn(
                    base_path,
                    v8o_scene_path,
                    NULL,
                    &visible_scene);
                v8o.created_scene = visible_scene;
                if ((int32_t)v8o.create_status >= 0 && visible_scene != 0u) {
                    if (resolve_icon_xui() != 0u) {
                        if (find_live_descendant(
                                visible_scene,
                                v8o_title_id,
                                &title_element) >= 0 &&
                            title_element != 0u && g_runtime.xui_set_text != NULL) {
                            v8o.title_set_status = (uint32_t)
                                g_runtime.xui_set_text(
                                    title_element, v8o_title_text);
                        }
                        if (find_live_descendant(
                                visible_scene,
                                v8o_status_id,
                                &status_element) >= 0 &&
                            status_element != 0u && g_runtime.xui_set_text != NULL) {
                            v8o.status_set_status = (uint32_t)
                                g_runtime.xui_set_text(
                                    status_element, v8o_status_text);
                        }
                    }
                    v8o.forward_status = (uint32_t)navigate_fn(
                        v8o.main_scene,
                        0,
                        visible_scene,
                        WOLF_V8F_USER_INDEX_ANY);
                    if ((int32_t)v8o.forward_status >= 0) {
                        v8o.phase = 1u;
                        g_wolf_v8o_scene = visible_scene;
                        g_wolf_v8o_parent = v8o.main_scene;
                        g_wolf_v8o_frames = 0u;
                        memcpy(&g_wolf_v8o_marker, &v8o, sizeof(v8o));
                        store_u32(&g_wolf_v8o_phase, 1u);
                    }
                    else if (destroy_fn != NULL) {
                        destroy_fn(visible_scene);
                        v8o.phase = 4u;
                    }
                }
            }
            wolf_v8o_write_visible_marker(&v8o);
        }
'''

runtime = replace_once(
    runtime,
    '            wolf_v8n_write_custom_marker(&v8n);\n'
    '        }\n'
    '        marker.created_scene = scene;',
    '            wolf_v8n_write_custom_marker(&v8n);\n'
    '        }\n' + v8o_attempt + '        marker.created_scene = scene;',
    "V8O visible navigation attempt",
)

v8o_tick = r'''static void wolf_v8o_render_tick(void)
{
    uint32_t phase = load_u32(&g_wolf_v8o_phase);

    if (phase != 1u) {
        return;
    }
    ++g_wolf_v8o_frames;
    g_wolf_v8o_marker.visible_frames = g_wolf_v8o_frames;
    if (g_wolf_v8o_frames < WOLF_V8O_VISIBLE_FRAMES) {
        return;
    }

    g_wolf_v8o_marker.phase = 2u;
    store_u32(&g_wolf_v8o_phase, 2u);
    if (g_wolf_v8o_back_fn != NULL &&
        g_wolf_v8o_scene != 0u && g_wolf_v8o_parent != 0u) {
        g_wolf_v8o_marker.back_status = (uint32_t)g_wolf_v8o_back_fn(
            g_wolf_v8o_scene,
            g_wolf_v8o_parent,
            WOLF_V8F_USER_INDEX_ANY);
        if ((int32_t)g_wolf_v8o_marker.back_status >= 0) {
            g_wolf_v8o_marker.phase = 3u;
            g_wolf_v8o_marker.completed = 1u;
            store_u32(&g_wolf_v8o_phase, 3u);
        }
        else {
            g_wolf_v8o_marker.phase = 4u;
            store_u32(&g_wolf_v8o_phase, 4u);
        }
    }
    else {
        g_wolf_v8o_marker.back_status = 0xFFFFFFFDu;
        g_wolf_v8o_marker.phase = 4u;
        store_u32(&g_wolf_v8o_phase, 4u);
    }
    wolf_v8o_write_visible_marker(&g_wolf_v8o_marker);
}

'''

runtime = replace_once(
    runtime,
    'void wolf_v8i_render_ui_tick(void)\n{\n'
    '    if (load_u32(&g_runtime.wolf_v8f_scene_pending) == 0u) {',
    v8o_tick +
    'void wolf_v8i_render_ui_tick(void)\n{\n'
    '    wolf_v8o_render_tick();\n'
    '    if (load_u32(&g_runtime.wolf_v8f_scene_pending) == 0u) {',
    "V8O render-tick lifecycle",
)

runtime_path.write_text(runtime)
print("Wolf V8O visible native scene probe applied")
