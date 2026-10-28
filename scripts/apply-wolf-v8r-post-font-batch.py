#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8R post-FontEnd anchor missing: {label}")
    return text.replace(old, new, 1)


# V8R keeps V8Q's proven renderer, but changes ordering. V8Q drew inside the
# final Font::End hook before Aurora's own Font::End cleanup ran. V8R first lets
# Aurora close that batch, then calls the recovered Font::Begin directly, draws
# a bounded Wolf-only batch, and closes it through the existing original-End
# trampoline. This keeps the font/shader state valid while making Wolf the last
# batch in that final coverflow pass.

runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    'typedef char WolfV8qRenderMarkerMustBe48Bytes[\n'
    '    sizeof(WolfV8qRenderMarker) == 48u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8qRenderMarkerMustBe48Bytes[\n'
    '    sizeof(WolfV8qRenderMarker) == 48u ? 1 : -1];\n\n'
    'typedef struct WolfV8rRenderMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t attempted_frames;\n'
    '    uint32_t drawn_frames;\n'
    '    uint32_t begin_calls;\n'
    '    uint32_t end_calls;\n'
    '    uint32_t phase;\n'
    '    uint32_t completed;\n'
    '    uint32_t last_draw_result;\n'
    '    uint32_t render_menu_calls;\n'
    '    uint32_t font_end_calls;\n'
    '    uint32_t font_end_original_calls;\n'
    '    uint32_t reserved0;\n'
    '    uint32_t reserved1;\n'
    '    uint32_t reserved2;\n'
    '} WolfV8rRenderMarker;\n\n'
    'typedef char WolfV8rRenderMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8rRenderMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8R marker structure",
)

runtime = replace_once(
    runtime,
    'static char g_wolf_v8q_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8Q-render.bin";\n',
    'static char g_wolf_v8q_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8Q-render.bin";\n'
    'static char g_wolf_v8r_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8R-render.bin";\n',
    "V8R marker path",
)

runtime = replace_once(
    runtime,
    '    WolfV8qRenderMarker v8q;\n',
    '    WolfV8qRenderMarker v8q;\n'
    '    WolfV8rRenderMarker v8r;\n',
    "V8R flush local",
)

runtime = replace_once(
    runtime,
    '    (void)write_complete_file(\n'
    '        g_wolf_v8q_marker_path,\n'
    '        (const uint8_t *)&v8q,\n'
    '        (uint32_t)sizeof(v8q));\n'
    '}\n\nstatic void flush_filter_probe_telemetry',
    '    (void)write_complete_file(\n'
    '        g_wolf_v8q_marker_path,\n'
    '        (const uint8_t *)&v8q,\n'
    '        (uint32_t)sizeof(v8q));\n\n'
    '    memset(&v8r, 0, sizeof(v8r));\n'
    "    v8r.magic[0] = 'W';\n"
    "    v8r.magic[1] = 'F';\n"
    "    v8r.magic[2] = '8';\n"
    "    v8r.magic[3] = 'R';\n"
    '    v8r.version = 1u;\n'
    '    v8r.record_size = (uint32_t)sizeof(v8r);\n'
    '    v8r.attempted_frames = az_wolf_v8r_attempted_frames();\n'
    '    v8r.drawn_frames = az_wolf_v8r_drawn_frames();\n'
    '    v8r.begin_calls = az_wolf_v8r_begin_calls();\n'
    '    v8r.end_calls = az_wolf_v8r_end_calls();\n'
    '    v8r.phase = az_wolf_v8r_phase();\n'
    '    v8r.completed = v8r.phase == 2u ? 1u : 0u;\n'
    '    v8r.last_draw_result = (uint32_t)render_status.last_draw_result;\n'
    '    v8r.render_menu_calls = render_status.render_menu_calls;\n'
    '    v8r.font_end_calls = render_status.font_end_calls;\n'
    '    v8r.font_end_original_calls = render_status.font_end_original_calls;\n'
    '    (void)write_complete_file(\n'
    '        g_wolf_v8r_marker_path,\n'
    '        (const uint8_t *)&v8r,\n'
    '        (uint32_t)sizeof(v8r));\n'
    '}\n\nstatic void flush_filter_probe_telemetry',
    "V8R telemetry write",
)

runtime_path.write_text(runtime)


header_path = Path("native/include/auroraaz/render_detours.h")
header = header_path.read_text()
header = replace_once(
    header,
    'uint32_t az_wolf_v8q_phase(void);\n\n',
    'uint32_t az_wolf_v8q_phase(void);\n\n'
    '/* Wolf Factory V8R post-FontEnd batch visibility probe telemetry. */\n'
    'uint32_t az_wolf_v8r_attempted_frames(void);\n'
    'uint32_t az_wolf_v8r_drawn_frames(void);\n'
    'uint32_t az_wolf_v8r_begin_calls(void);\n'
    'uint32_t az_wolf_v8r_end_calls(void);\n'
    'uint32_t az_wolf_v8r_phase(void);\n\n',
    "V8R status declarations",
)
header_path.write_text(header)


render_path = Path("native/src/render_detours.c")
render = render_path.read_text()

render = replace_once(
    render,
    '#define WOLF_V8Q_PROBE_FRAMES 240u\n',
    '#define WOLF_V8Q_PROBE_FRAMES 240u\n'
    '#define WOLF_V8R_PROBE_FRAMES 240u\n'
    '#define WOLF_V8R_FONT_BEGIN_ADDRESS 0x8247E0C0u\n\n'
    'typedef void (*WolfV8rFontBeginFn)(void *font);\n',
    "V8R constants",
)

render = replace_once(
    render,
    '    volatile uint32_t wolf_v8q_attempted_frames;\n'
    '    volatile uint32_t wolf_v8q_drawn_frames;\n'
    '    volatile uint32_t wolf_v8q_phase;\n',
    '    volatile uint32_t wolf_v8q_attempted_frames;\n'
    '    volatile uint32_t wolf_v8q_drawn_frames;\n'
    '    volatile uint32_t wolf_v8q_phase;\n'
    '    volatile uint32_t wolf_v8r_attempted_frames;\n'
    '    volatile uint32_t wolf_v8r_drawn_frames;\n'
    '    volatile uint32_t wolf_v8r_begin_calls;\n'
    '    volatile uint32_t wolf_v8r_end_calls;\n'
    '    volatile uint32_t wolf_v8r_phase;\n',
    "V8R bridge counters",
)

render = replace_once(
    render,
    'uint32_t az_wolf_v8q_phase(void)\n'
    '{\n'
    '    return load_u32(&g_render_detours.wolf_v8q_phase);\n'
    '}\n\n'
    'int32_t az_rev1655_render_menu_detour_c(void *game_content_manager)',
    'uint32_t az_wolf_v8q_phase(void)\n'
    '{\n'
    '    return load_u32(&g_render_detours.wolf_v8q_phase);\n'
    '}\n\n'
    'uint32_t az_wolf_v8r_attempted_frames(void)\n'
    '{\n'
    '    return load_u32(&g_render_detours.wolf_v8r_attempted_frames);\n'
    '}\n\n'
    'uint32_t az_wolf_v8r_drawn_frames(void)\n'
    '{\n'
    '    return load_u32(&g_render_detours.wolf_v8r_drawn_frames);\n'
    '}\n\n'
    'uint32_t az_wolf_v8r_begin_calls(void)\n'
    '{\n'
    '    return load_u32(&g_render_detours.wolf_v8r_begin_calls);\n'
    '}\n\n'
    'uint32_t az_wolf_v8r_end_calls(void)\n'
    '{\n'
    '    return load_u32(&g_render_detours.wolf_v8r_end_calls);\n'
    '}\n\n'
    'uint32_t az_wolf_v8r_phase(void)\n'
    '{\n'
    '    return load_u32(&g_render_detours.wolf_v8r_phase);\n'
    '}\n\n'
    'int32_t az_rev1655_render_menu_detour_c(void *game_content_manager)',
    "V8R status getters",
)

# V8Q has already proven pre-End submission, so disable its bounded panel in
# this build. The ordinary overlay path stays intact outside the V8R window.
render = replace_once(
    render,
    '                load_u32(&g_render_detours.wolf_v8q_phase) < 2u) {',
    '                load_u32(&g_render_detours.wolf_v8q_phase) == 0xFFFFFFFFu) {',
    "disable V8Q panel",
)

# Do not consume the renderer epoch in the ordinary pre-End path while V8R is
# active; V8R needs that same epoch for its own post-End batch.
render = replace_once(
    render,
    '            draw_result = g_render_detours.bindings.try_draw(\n'
    '                g_render_detours.bindings.renderer,\n'
    '                &request);\n',
    '            if (caller_lr == AZ_REV1655_FONT_END_CALLER_LR &&\n'
    '                load_u32(&g_render_detours.wolf_v8r_phase) < 2u) {\n'
    '                draw_result = AZ_OVERLAY_RENDERER_OK;\n'
    '            }\n'
    '            else {\n'
    '                draw_result = g_render_detours.bindings.try_draw(\n'
    '                    g_render_detours.bindings.renderer,\n'
    '                    &request);\n'
    '            }\n',
    "reserve V8R render epoch",
)

render = replace_once(
    render,
    '    /* Font::End owns Aurora\'s state cleanup and must run exactly once. */\n'
    '    increment_u32(&g_render_detours.font_end_original_calls);\n'
    '    original(font);\n'
    '}\n\n'
    'const char *az_render_detour_result_name(AzRenderDetourResult result)',
    '    /* First let Aurora close its own font batch exactly as before. */\n'
    '    increment_u32(&g_render_detours.font_end_original_calls);\n'
    '    original(font);\n\n'
    '#if defined(AURORAAZ_XBOX360)\n'
    '    /* V8R: on the recovered final coverflow caller, open a fresh font\n'
    '     * batch after Aurora\'s original End has returned. The recovered\n'
    '     * Begin address is already signature-validated by the renderer. */\n'
    '    if (caller_lr == AZ_REV1655_FONT_END_CALLER_LR &&\n'
    '        load_u32(&g_render_detours.configured) != 0u &&\n'
    '        load_u32(&g_render_detours.cleanup_requested) == 0u &&\n'
    '        load_u32(&g_render_detours.wolf_v8r_phase) < 2u) {\n'
    '        AzInputDetourStatus post_status;\n'
    '        AzOverlayDrawRequest post_request;\n'
    '        AzOverlayRendererResult post_draw_result;\n'
    '        const WolfV8rFontBeginFn font_begin =\n'
    '            (WolfV8rFontBeginFn)(uintptr_t)WOLF_V8R_FONT_BEGIN_ADDRESS;\n\n'
    '        memset(&post_status, 0, sizeof(post_status));\n'
    '        memset(&post_request, 0, sizeof(post_request));\n'
    '        g_render_detours.bindings.snapshot_input_status(&post_status);\n'
    '        if (post_status.scene_allows_capture != 0u) {\n'
    '            if (load_u32(&g_render_detours.wolf_v8r_phase) == 0u) {\n'
    '                store_u32(&g_render_detours.wolf_v8r_phase, 1u);\n'
    '            }\n'
    '            font_begin(font);\n'
    '            increment_u32(&g_render_detours.wolf_v8r_begin_calls);\n\n'
    '            post_request.font = font;\n'
    '            post_request.caller_lr = AZ_REV1655_FONT_END_CALLER_LR;\n'
    '            post_request.viewport_width =\n'
    '                g_render_detours.bindings.viewport_width;\n'
    '            post_request.viewport_height =\n'
    '                g_render_detours.bindings.viewport_height;\n'
    '            post_request.proven_modal_clear = 1u;\n'
    '            post_request.mode_notice = 3u;\n'
    '            increment_u32(&g_render_detours.wolf_v8r_attempted_frames);\n'
    '            post_draw_result = g_render_detours.bindings.try_draw(\n'
    '                g_render_detours.bindings.renderer,\n'
    '                &post_request);\n'
    '            store_u32(\n'
    '                &g_render_detours.last_draw_result,\n'
    '                (uint32_t)post_draw_result);\n'
    '            if (post_draw_result == AZ_OVERLAY_RENDERER_DRAWN) {\n'
    '                increment_u32(&g_render_detours.wolf_v8r_drawn_frames);\n'
    '            }\n\n'
    '            /* Close only the Wolf batch through the already-selected\n'
    '             * original trampoline; this bypasses hook recursion. */\n'
    '            increment_u32(&g_render_detours.wolf_v8r_end_calls);\n'
    '            increment_u32(&g_render_detours.font_end_original_calls);\n'
    '            original(font);\n\n'
    '            if (load_u32(&g_render_detours.wolf_v8r_attempted_frames) >=\n'
    '                WOLF_V8R_PROBE_FRAMES) {\n'
    '                store_u32(&g_render_detours.wolf_v8r_phase, 2u);\n'
    '            }\n'
    '        }\n'
    '    }\n'
    '#endif\n'
    '}\n\n'
    'const char *az_render_detour_result_name(AzRenderDetourResult result)',
    "V8R post-End batch",
)

render_path.write_text(render)


renderer_path = Path("native/src/overlay_renderer_xbox360.c")
renderer = renderer_path.read_text()
renderer = replace_once(
    renderer,
    '    if (request->mode_notice == 2u) {\n',
    '    if (request->mode_notice == 2u || request->mode_notice == 3u) {\n',
    "V8R giant panel mode",
)
renderer = replace_once(
    renderer,
    '        probe.color = 0xFFFF3030u;\n'
    '        model->quads[model->count++] = probe;\n',
    '        probe.color = request->mode_notice == 3u ?\n'
    '            0xFF30FF30u : 0xFFFF3030u;\n'
    '        model->quads[model->count++] = probe;\n',
    "V8R green panel",
)
renderer_path.write_text(renderer)

print("Wolf V8R post-FontEnd batch probe applied")
