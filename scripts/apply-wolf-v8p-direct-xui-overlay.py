#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8P direct-XUI anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    '#define WOLF_V8O_VISIBLE_MARKER_VERSION 1u\n'
    '#define WOLF_V8O_VISIBLE_FRAMES 180u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    '#define WOLF_V8O_VISIBLE_MARKER_VERSION 1u\n'
    '#define WOLF_V8O_VISIBLE_FRAMES 180u\n'
    '#define WOLF_V8P_DYNAMIC_MARKER_VERSION 1u\n'
    '#define WOLF_V8P_VISIBLE_FRAMES 240u\n'
    '#define WOLF_V8P_XUI_CREATE_OBJECT_ORDINAL 805u\n'
    '#define WOLF_V8P_XUI_ADD_CHILD_ORDINAL 808u\n'
    '#define WOLF_V8P_XUI_SET_BOUNDS_ORDINAL 822u\n'
    '#define WOLF_V8P_XUI_SET_TEXT_ORDINAL 867u\n'
    '#define WOLF_V8P_XUI_SET_OPACITY_ORDINAL 894u\n'
    '#define WOLF_V8P_XUI_SET_POSITION_ORDINAL 945u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    "V8P constants",
)

runtime = replace_once(
    runtime,
    'typedef int32_t (*WolfV8oXuiSceneNavigateBackFn)(\n'
    '    uint32_t, uint32_t, uint32_t);\n'
    'typedef void (*WolfV8fXuiDestroyObjectFn)(uint32_t);',
    'typedef int32_t (*WolfV8oXuiSceneNavigateBackFn)(\n'
    '    uint32_t, uint32_t, uint32_t);\n'
    'typedef int32_t (*WolfV8pXuiCreateObjectFn)(\n'
    '    const uint16_t *, uint32_t *);\n'
    'typedef int32_t (*WolfV8pXuiElementAddChildFn)(uint32_t, uint32_t);\n'
    'typedef int32_t (*WolfV8pXuiElementSetBoundsFn)(uint32_t, float, float);\n'
    'typedef struct WolfV8pVector3 {\n'
    '    float x;\n'
    '    float y;\n'
    '    float z;\n'
    '} WolfV8pVector3;\n'
    'typedef int32_t (*WolfV8pXuiElementSetPositionFn)(\n'
    '    uint32_t, const WolfV8pVector3 *);\n'
    'typedef int32_t (*WolfV8pXuiSetTextFn)(uint32_t, const uint16_t *);\n'
    'typedef int32_t (*WolfV8pXuiSetOpacityFn)(uint32_t, float);\n'
    'typedef void (*WolfV8fXuiDestroyObjectFn)(uint32_t);',
    "V8P XUI typedefs",
)

runtime = replace_once(
    runtime,
    'typedef char WolfV8oVisibleMarkerMustBe96Bytes[\n'
    '    sizeof(WolfV8oVisibleMarker) == 96u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8oVisibleMarkerMustBe96Bytes[\n'
    '    sizeof(WolfV8oVisibleMarker) == 96u ? 1 : -1];\n\n'
    'typedef struct WolfV8pDynamicMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t gate_reason;\n'
    '    uint32_t main_scene;\n'
    '    uint32_t ui_thread_id;\n'
    '    uint32_t attempt_count;\n'
    '    uint32_t module_status;\n'
    '    uint32_t xam_handle;\n'
    '    uint32_t create_resolve_status;\n'
    '    uint32_t create_address;\n'
    '    uint32_t add_resolve_status;\n'
    '    uint32_t add_address;\n'
    '    uint32_t bounds_resolve_status;\n'
    '    uint32_t bounds_address;\n'
    '    uint32_t position_resolve_status;\n'
    '    uint32_t position_address;\n'
    '    uint32_t text_resolve_status;\n'
    '    uint32_t text_address;\n'
    '    uint32_t opacity_resolve_status;\n'
    '    uint32_t opacity_address;\n'
    '    uint32_t destroy_resolve_status;\n'
    '    uint32_t destroy_address;\n'
    '    uint32_t create_status;\n'
    '    uint32_t text_handle;\n'
    '    uint32_t bounds_status;\n'
    '    uint32_t position_status;\n'
    '    uint32_t text_status;\n'
    '    uint32_t opacity_status;\n'
    '    uint32_t add_status;\n'
    '    uint32_t visible_frames;\n'
    '    uint32_t phase;\n'
    '    uint32_t destroyed;\n'
    '    uint32_t completed;\n'
    '    uint32_t reserved0;\n'
    '} WolfV8pDynamicMarker;\n\n'
    'typedef char WolfV8pDynamicMarkerMustBe140Bytes[\n'
    '    sizeof(WolfV8pDynamicMarker) == 140u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8P marker structure",
)

runtime = replace_once(
    runtime,
    'static WolfV8oXuiSceneNavigateBackFn g_wolf_v8o_back_fn;\n'
    'static WolfV8oVisibleMarker g_wolf_v8o_marker;\n\n'
    'static char g_wolf_v8n_marker_path[] =',
    'static WolfV8oXuiSceneNavigateBackFn g_wolf_v8o_back_fn;\n'
    'static WolfV8oVisibleMarker g_wolf_v8o_marker;\n'
    'static char g_wolf_v8p_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8P-dynamic.bin";\n'
    'static volatile uint32_t g_wolf_v8p_phase;\n'
    'static uint32_t g_wolf_v8p_text;\n'
    'static uint32_t g_wolf_v8p_frames;\n'
    'static WolfV8fXuiDestroyObjectFn g_wolf_v8p_destroy_fn;\n'
    'static WolfV8pDynamicMarker g_wolf_v8p_marker;\n\n'
    'static char g_wolf_v8n_marker_path[] =',
    "V8P state and marker path",
)

runtime = replace_once(
    runtime,
    'static void wolf_v8o_write_visible_marker(const WolfV8oVisibleMarker *marker)\n{',
    '''static void wolf_v8p_write_dynamic_marker(const WolfV8pDynamicMarker *marker)
{
    if (marker == NULL || write_complete_file(
            g_wolf_v8p_marker_path,
            (const uint8_t *)marker,
            (uint32_t)sizeof(*marker)) == 0u) {
        DbgPrint("WolfFactory V8P: dynamic marker write failed\\n");
    }
}

static void wolf_v8o_write_visible_marker(const WolfV8oVisibleMarker *marker)
{''',
    "V8P marker writer",
)

# Preserve the already-generated V8O marker for tomorrow's decode. V8P does not
# rerun V8O or overwrite WolfFactory-V8O-visible.bin on hardware.
runtime = replace_once(
    runtime,
    'if (v8n.completed != 0u && load_u32(&g_wolf_v8o_phase) == 0u) {',
    'if (v8n.completed != 0u && load_u32(&g_wolf_v8o_phase) == 0xFFFFFFFFu) {',
    "disable V8O reattempt",
)

v8p_attempt = r'''        /* V8P: bypass XUR/Nova/navigation entirely. Create a built-in
         * XuiText object, fully configure it, then attach it directly to the
         * scene-gate-verified Aurora_Main tree. This is the smallest possible
         * native-XUI visibility proof and leaves Aurora's scene stack alone. */
        if (v8n.completed != 0u && load_u32(&g_wolf_v8p_phase) == 0u) {
            static const uint16_t v8p_text_class[] = {
                'X','u','i','T','e','x','t',0
            };
            static const uint16_t v8p_message[] = {
                'W','O','L','F',' ','F','A','C','T','O','R','Y',' ','V','8','P',
                ' ','/','/',' ','D','I','R','E','C','T',' ','N','A','T','I','V','E',0
            };
            AzSceneGateDecision v8p_gate;
            WolfV8pDynamicMarker v8p;
            WolfV8pXuiCreateObjectFn create_object_fn = NULL;
            WolfV8pXuiElementAddChildFn add_child_fn = NULL;
            WolfV8pXuiElementSetBoundsFn set_bounds_fn = NULL;
            WolfV8pXuiElementSetPositionFn set_position_fn = NULL;
            WolfV8pXuiSetTextFn set_text_fn = NULL;
            WolfV8pXuiSetOpacityFn set_opacity_fn = NULL;
            WolfV8pVector3 position;
            uint32_t text_handle = 0u;

            memset(&v8p, 0, sizeof(v8p));
            v8p.magic[0] = 'W';
            v8p.magic[1] = 'F';
            v8p.magic[2] = '8';
            v8p.magic[3] = 'P';
            v8p.version = WOLF_V8P_DYNAMIC_MARKER_VERSION;
            v8p.record_size = (uint32_t)sizeof(v8p);
            v8p.ui_thread_id = marker.ui_thread_id;
            v8p.attempt_count = marker.attempt_count;
            v8p.module_status = marker.module_status;
            v8p.xam_handle = marker.xam_handle;
            v8p.create_resolve_status = 0xFFFFFFFFu;
            v8p.add_resolve_status = 0xFFFFFFFFu;
            v8p.bounds_resolve_status = 0xFFFFFFFFu;
            v8p.position_resolve_status = 0xFFFFFFFFu;
            v8p.text_resolve_status = 0xFFFFFFFFu;
            v8p.opacity_resolve_status = 0xFFFFFFFFu;
            v8p.destroy_resolve_status = marker.destroy_status;
            v8p.destroy_address = marker.destroy_address;
            v8p.create_status = 0xFFFFFFFFu;
            v8p.bounds_status = 0xFFFFFFFFu;
            v8p.position_status = 0xFFFFFFFFu;
            v8p.text_status = 0xFFFFFFFFu;
            v8p.opacity_status = 0xFFFFFFFFu;
            v8p.add_status = 0xFFFFFFFFu;

            memset(&v8p_gate, 0, sizeof(v8p_gate));
            (void)az_rev1655_scene_gate_probe(&v8p_gate);
            v8p.gate_reason = (uint32_t)v8p_gate.reason;
            v8p.main_scene = v8p_gate.main_scene_handle;

            if (xam != NULL) {
                v8p.create_resolve_status = wolf_v8e_resolve_xam_export(
                    xam, WOLF_V8P_XUI_CREATE_OBJECT_ORDINAL,
                    &v8p.create_address);
                v8p.add_resolve_status = wolf_v8e_resolve_xam_export(
                    xam, WOLF_V8P_XUI_ADD_CHILD_ORDINAL,
                    &v8p.add_address);
                v8p.bounds_resolve_status = wolf_v8e_resolve_xam_export(
                    xam, WOLF_V8P_XUI_SET_BOUNDS_ORDINAL,
                    &v8p.bounds_address);
                v8p.position_resolve_status = wolf_v8e_resolve_xam_export(
                    xam, WOLF_V8P_XUI_SET_POSITION_ORDINAL,
                    &v8p.position_address);
                v8p.text_resolve_status = wolf_v8e_resolve_xam_export(
                    xam, WOLF_V8P_XUI_SET_TEXT_ORDINAL,
                    &v8p.text_address);
                v8p.opacity_resolve_status = wolf_v8e_resolve_xam_export(
                    xam, WOLF_V8P_XUI_SET_OPACITY_ORDINAL,
                    &v8p.opacity_address);
            }

            if (v8p.create_resolve_status == 0u && v8p.create_address != 0u)
                create_object_fn = (WolfV8pXuiCreateObjectFn)
                    (uintptr_t)v8p.create_address;
            if (v8p.add_resolve_status == 0u && v8p.add_address != 0u)
                add_child_fn = (WolfV8pXuiElementAddChildFn)
                    (uintptr_t)v8p.add_address;
            if (v8p.bounds_resolve_status == 0u && v8p.bounds_address != 0u)
                set_bounds_fn = (WolfV8pXuiElementSetBoundsFn)
                    (uintptr_t)v8p.bounds_address;
            if (v8p.position_resolve_status == 0u && v8p.position_address != 0u)
                set_position_fn = (WolfV8pXuiElementSetPositionFn)
                    (uintptr_t)v8p.position_address;
            if (v8p.text_resolve_status == 0u && v8p.text_address != 0u)
                set_text_fn = (WolfV8pXuiSetTextFn)
                    (uintptr_t)v8p.text_address;
            if (v8p.opacity_resolve_status == 0u && v8p.opacity_address != 0u)
                set_opacity_fn = (WolfV8pXuiSetOpacityFn)
                    (uintptr_t)v8p.opacity_address;

            if (v8p_gate.allows_capture != 0u && v8p.main_scene != 0u &&
                create_object_fn != NULL && add_child_fn != NULL &&
                set_bounds_fn != NULL && set_position_fn != NULL &&
                set_text_fn != NULL && set_opacity_fn != NULL &&
                destroy_fn != NULL) {
                v8p.create_status = (uint32_t)create_object_fn(
                    v8p_text_class, &text_handle);
                v8p.text_handle = text_handle;
                if ((int32_t)v8p.create_status >= 0 && text_handle != 0u) {
                    position.x = 190.0f;
                    position.y = 300.0f;
                    position.z = 0.0f;
                    v8p.bounds_status = (uint32_t)set_bounds_fn(
                        text_handle, 900.0f, 120.0f);
                    v8p.position_status = (uint32_t)set_position_fn(
                        text_handle, &position);
                    v8p.text_status = (uint32_t)set_text_fn(
                        text_handle, v8p_message);
                    v8p.opacity_status = (uint32_t)set_opacity_fn(
                        text_handle, 1.0f);
                    if ((int32_t)v8p.bounds_status >= 0 &&
                        (int32_t)v8p.position_status >= 0 &&
                        (int32_t)v8p.text_status >= 0 &&
                        (int32_t)v8p.opacity_status >= 0) {
                        v8p.add_status = (uint32_t)add_child_fn(
                            v8p.main_scene, text_handle);
                    }
                    if ((int32_t)v8p.add_status >= 0) {
                        v8p.phase = 1u;
                        g_wolf_v8p_text = text_handle;
                        g_wolf_v8p_frames = 0u;
                        g_wolf_v8p_destroy_fn = destroy_fn;
                        memcpy(&g_wolf_v8p_marker, &v8p, sizeof(v8p));
                        store_u32(&g_wolf_v8p_phase, 1u);
                    }
                    else {
                        destroy_fn(text_handle);
                        v8p.destroyed = 1u;
                        v8p.phase = 4u;
                    }
                }
            }
            wolf_v8p_write_dynamic_marker(&v8p);
        }
'''

runtime = replace_once(
    runtime,
    '            wolf_v8o_write_visible_marker(&v8o);\n'
    '        }\n'
    '        marker.created_scene = scene;',
    '            wolf_v8o_write_visible_marker(&v8o);\n'
    '        }\n' + v8p_attempt + '        marker.created_scene = scene;',
    "V8P direct overlay attempt",
)

v8p_tick = r'''static void wolf_v8p_render_tick(void)
{
    if (load_u32(&g_wolf_v8p_phase) != 1u) {
        return;
    }
    ++g_wolf_v8p_frames;
    g_wolf_v8p_marker.visible_frames = g_wolf_v8p_frames;
    if (g_wolf_v8p_frames < WOLF_V8P_VISIBLE_FRAMES) {
        return;
    }

    g_wolf_v8p_marker.phase = 2u;
    store_u32(&g_wolf_v8p_phase, 2u);
    if (g_wolf_v8p_destroy_fn != NULL && g_wolf_v8p_text != 0u) {
        g_wolf_v8p_destroy_fn(g_wolf_v8p_text);
        g_wolf_v8p_marker.destroyed = 1u;
        g_wolf_v8p_marker.phase = 3u;
        g_wolf_v8p_marker.completed = 1u;
        store_u32(&g_wolf_v8p_phase, 3u);
    }
    else {
        g_wolf_v8p_marker.phase = 4u;
        store_u32(&g_wolf_v8p_phase, 4u);
    }
    wolf_v8p_write_dynamic_marker(&g_wolf_v8p_marker);
}

'''

runtime = replace_once(
    runtime,
    'static void wolf_v8o_render_tick(void)\n{',
    v8p_tick + 'static void wolf_v8o_render_tick(void)\n{',
    "V8P render-tick lifecycle",
)

runtime = replace_once(
    runtime,
    'void wolf_v8i_render_ui_tick(void)\n{\n'
    '    wolf_v8o_render_tick();',
    'void wolf_v8i_render_ui_tick(void)\n{\n'
    '    wolf_v8p_render_tick();\n'
    '    wolf_v8o_render_tick();',
    "V8P render-tick dispatch",
)

runtime_path.write_text(runtime)
print("Wolf V8P direct native XUI overlay probe applied")
