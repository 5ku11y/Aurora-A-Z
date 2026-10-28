#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8Q final-render anchor missing: {label}")
    return text.replace(old, new, 1)


# V8Q deliberately stops exercising the invisible XUI attach path and instead
# drives the already-validated final Aurora render hook for a bounded proof.
runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    'typedef char WolfV8pDynamicMarkerMustBe140Bytes[\n'
    '    sizeof(WolfV8pDynamicMarker) == 140u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8pDynamicMarkerMustBe140Bytes[\n'
    '    sizeof(WolfV8pDynamicMarker) == 140u ? 1 : -1];\n\n'
    'typedef struct WolfV8qRenderMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t attempted_frames;\n'
    '    uint32_t drawn_frames;\n'
    '    uint32_t phase;\n'
    '    uint32_t completed;\n'
    '    uint32_t last_draw_result;\n'
    '    uint32_t render_menu_calls;\n'
    '    uint32_t font_end_calls;\n'
    '    uint32_t reserved0;\n'
    '    uint32_t reserved1;\n'
    '} WolfV8qRenderMarker;\n\n'
    'typedef char WolfV8qRenderMarkerMustBe48Bytes[\n'
    '    sizeof(WolfV8qRenderMarker) == 48u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8Q marker structure",
)

runtime = replace_once(
    runtime,
    'static char g_render_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\AuroraAZ-M2b.bin";',
    'static char g_wolf_v8q_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8Q-render.bin";\n'
    'static char g_render_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\AuroraAZ-M2b.bin";',
    "V8Q marker path",
)

# Preserve the V8P hardware marker and isolate V8Q from all XUI creation.
runtime = replace_once(
    runtime,
    'if (v8n.completed != 0u && load_u32(&g_wolf_v8p_phase) == 0u) {',
    'if (v8n.completed != 0u && load_u32(&g_wolf_v8p_phase) == 0xFFFFFFFFu) {',
    "disable V8P reattempt",
)

runtime = replace_once(
    runtime,
    '    AzSceneGateStatus scene_status;\n'
    '    AzM2bRenderMarker marker;\n',
    '    AzSceneGateStatus scene_status;\n'
    '    AzM2bRenderMarker marker;\n'
    '    WolfV8qRenderMarker v8q;\n',
    "V8Q flush local",
)

runtime = replace_once(
    runtime,
    '    (void)write_complete_file(\n'
    '        g_render_marker_path,\n'
    '        (const uint8_t *)&marker,\n'
    '        (uint32_t)sizeof(marker));\n'
    '}\n\nstatic void flush_filter_probe_telemetry',
    '    (void)write_complete_file(\n'
    '        g_render_marker_path,\n'
    '        (const uint8_t *)&marker,\n'
    '        (uint32_t)sizeof(marker));\n\n'
    '    memset(&v8q, 0, sizeof(v8q));\n'
    "    v8q.magic[0] = 'W';\n"
    "    v8q.magic[1] = 'F';\n"
    "    v8q.magic[2] = '8';\n"
    "    v8q.magic[3] = 'Q';\n"
    '    v8q.version = 1u;\n'
    '    v8q.record_size = (uint32_t)sizeof(v8q);\n'
    '    v8q.attempted_frames = az_wolf_v8q_attempted_frames();\n'
    '    v8q.drawn_frames = az_wolf_v8q_drawn_frames();\n'
    '    v8q.phase = az_wolf_v8q_phase();\n'
    '    v8q.completed = v8q.phase == 2u ? 1u : 0u;\n'
    '    v8q.last_draw_result = (uint32_t)render_status.last_draw_result;\n'
    '    v8q.render_menu_calls = render_status.render_menu_calls;\n'
    '    v8q.font_end_calls = render_status.font_end_calls;\n'
    '    (void)write_complete_file(\n'
    '        g_wolf_v8q_marker_path,\n'
    '        (const uint8_t *)&v8q,\n'
    '        (uint32_t)sizeof(v8q));\n'
    '}\n\nstatic void flush_filter_probe_telemetry',
    "V8Q telemetry write",
)

runtime_path.write_text(runtime)


header_path = Path("native/include/auroraaz/render_detours.h")
header = header_path.read_text()
header = replace_once(
    header,
    'void az_rev1655_render_detours_snapshot_status(\n'
    '    AzRenderDetourStatus *status);\n\n',
    'void az_rev1655_render_detours_snapshot_status(\n'
    '    AzRenderDetourStatus *status);\n\n'
    '/* Wolf Factory V8Q bounded final-render visibility probe telemetry. */\n'
    'uint32_t az_wolf_v8q_attempted_frames(void);\n'
    'uint32_t az_wolf_v8q_drawn_frames(void);\n'
    'uint32_t az_wolf_v8q_phase(void);\n\n',
    "V8Q status declarations",
)
header_path.write_text(header)


render_path = Path("native/src/render_detours.c")
render = render_path.read_text()
render = replace_once(
    render,
    '#define AZ_EXIT_ANIMATION_FRAMES 18u\n'
    '#define AZ_SELECTION_ANIMATION_FRAMES 15u\n',
    '#define AZ_EXIT_ANIMATION_FRAMES 18u\n'
    '#define AZ_SELECTION_ANIMATION_FRAMES 15u\n'
    '#define WOLF_V8Q_PROBE_FRAMES 240u\n',
    "V8Q frame budget",
)

render = replace_once(
    render,
    '    uint8_t selection_animation_from_index;\n'
    '    uint8_t selection_animation_frame;\n'
    '} AzRenderDetourBridge;',
    '    uint8_t selection_animation_from_index;\n'
    '    uint8_t selection_animation_frame;\n'
    '    volatile uint32_t wolf_v8q_attempted_frames;\n'
    '    volatile uint32_t wolf_v8q_drawn_frames;\n'
    '    volatile uint32_t wolf_v8q_phase;\n'
    '} AzRenderDetourBridge;',
    "V8Q bridge counters",
)

render = replace_once(
    render,
    '    status->cleanup_complete = load_u32(\n'
    '        &g_render_detours.cleanup_complete) != 0u ? 1u : 0u;\n'
    '}\n\n'
    'int32_t az_rev1655_render_menu_detour_c(void *game_content_manager)',
    '    status->cleanup_complete = load_u32(\n'
    '        &g_render_detours.cleanup_complete) != 0u ? 1u : 0u;\n'
    '}\n\n'
    'uint32_t az_wolf_v8q_attempted_frames(void)\n'
    '{\n'
    '    return load_u32(&g_render_detours.wolf_v8q_attempted_frames);\n'
    '}\n\n'
    'uint32_t az_wolf_v8q_drawn_frames(void)\n'
    '{\n'
    '    return load_u32(&g_render_detours.wolf_v8q_drawn_frames);\n'
    '}\n\n'
    'uint32_t az_wolf_v8q_phase(void)\n'
    '{\n'
    '    return load_u32(&g_render_detours.wolf_v8q_phase);\n'
    '}\n\n'
    'int32_t az_rev1655_render_menu_detour_c(void *game_content_manager)',
    "V8Q status getters",
)

render = replace_once(
    render,
    '            request.proven_modal_clear =\n'
    '                input_status.scene_allows_capture != 0u ? 1u : 0u;\n\n'
    '            draw_result = g_render_detours.bindings.try_draw(',
    '            request.proven_modal_clear =\n'
    '                input_status.scene_allows_capture != 0u ? 1u : 0u;\n\n'
    '            /* V8Q: use the proven final Font::End pass itself as the\n'
    '             * visibility proof. mode_notice=2 is intercepted by the\n'
    '             * renderer below and expanded into a giant solid panel. */\n'
    '            if (caller_lr == AZ_REV1655_FONT_END_CALLER_LR &&\n'
    '                request.proven_modal_clear == 1u &&\n'
    '                load_u32(&g_render_detours.wolf_v8q_phase) < 2u) {\n'
    '                if (load_u32(&g_render_detours.wolf_v8q_phase) == 0u) {\n'
    '                    store_u32(&g_render_detours.wolf_v8q_phase, 1u);\n'
    '                }\n'
    '                request.mode_notice = 2u;\n'
    '                increment_u32(&g_render_detours.wolf_v8q_attempted_frames);\n'
    '            }\n\n'
    '            draw_result = g_render_detours.bindings.try_draw(',
    "V8Q draw request",
)

render = replace_once(
    render,
    '            store_u32(\n'
    '                &g_render_detours.last_draw_result,\n'
    '                (uint32_t)draw_result);\n',
    '            if (load_u32(&g_render_detours.wolf_v8q_phase) == 1u &&\n'
    '                request.mode_notice == 2u) {\n'
    '                if (draw_result == AZ_OVERLAY_RENDERER_DRAWN) {\n'
    '                    increment_u32(&g_render_detours.wolf_v8q_drawn_frames);\n'
    '                }\n'
    '                if (load_u32(&g_render_detours.wolf_v8q_attempted_frames) >=\n'
    '                    WOLF_V8Q_PROBE_FRAMES) {\n'
    '                    store_u32(&g_render_detours.wolf_v8q_phase, 2u);\n'
    '                }\n'
    '            }\n'
    '            store_u32(\n'
    '                &g_render_detours.last_draw_result,\n'
    '                (uint32_t)draw_result);\n',
    "V8Q draw result counters",
)
render_path.write_text(render)


renderer_path = Path("native/src/overlay_renderer_xbox360.c")
renderer = renderer_path.read_text()
renderer = replace_once(
    renderer,
    '    if (model->count != 0u && (model->count < 3u || model->count > AZ_OVERLAY_MAX_QUADS ||\n'
    '        model->quads[0].layer != AZ_OVERLAY_LAYER_DIM ||\n'
    '        model->quads[model->count - 2u].layer !=\n'
    '            AZ_OVERLAY_LAYER_SELECTED_SHADOW ||\n'
    '        model->quads[model->count - 1u].layer !=\n'
    '            AZ_OVERLAY_LAYER_SELECTED)) {\n'
    '        return 0;\n'
    '    }\n\n'
    '    if (request->mode_notice != 0u) {',
    '    if (model->count != 0u && (model->count < 3u || model->count > AZ_OVERLAY_MAX_QUADS ||\n'
    '        model->quads[0].layer != AZ_OVERLAY_LAYER_DIM ||\n'
    '        model->quads[model->count - 2u].layer !=\n'
    '            AZ_OVERLAY_LAYER_SELECTED_SHADOW ||\n'
    '        model->quads[model->count - 1u].layer !=\n'
    '            AZ_OVERLAY_LAYER_SELECTED)) {\n'
    '        return 0;\n'
    '    }\n\n'
    '    /* V8Q reserves mode_notice=2 in this probe build for a deliberately\n'
    '     * unmistakable final-pass panel. Both quads sample the atlas solid\n'
    '     * pixel, so this exercises the same texture/shader/draw path used by\n'
    '     * the production overlay without introducing another asset format. */\n'
    '    if (request->mode_notice == 2u) {\n'
    '        AzOverlayQuad probe;\n'
    '        if (model->count > AZ_OVERLAY_MAX_QUADS - 2u) {\n'
    '            return 0;\n'
    '        }\n'
    '        probe.x = 0.0f;\n'
    '        probe.y = 0.0f;\n'
    '        probe.width = 1280.0f;\n'
    '        probe.height = 720.0f;\n'
    '        probe.source_x = (float)AZ_GLYPH_ATLAS_SOLID_X;\n'
    '        probe.source_y = (float)AZ_GLYPH_ATLAS_SOLID_Y;\n'
    '        probe.source_width = 1.0f;\n'
    '        probe.source_height = 1.0f;\n'
    '        probe.layer = AZ_OVERLAY_LAYER_DIM;\n'
    '        probe.color = 0xFF181818u;\n'
    '        model->quads[model->count++] = probe;\n'
    '        probe.x = 80.0f;\n'
    '        probe.y = 80.0f;\n'
    '        probe.width = 1120.0f;\n'
    '        probe.height = 560.0f;\n'
    '        probe.layer = AZ_OVERLAY_LAYER_NOTICE;\n'
    '        probe.color = 0xFFFF3030u;\n'
    '        model->quads[model->count++] = probe;\n'
    '    }\n\n'
    '    if (request->mode_notice != 0u) {',
    "V8Q giant panel",
)
renderer_path.write_text(renderer)

print("Wolf V8Q final-render panel probe applied")
