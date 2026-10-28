#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8I render-dispatch anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

# V8H proved that the worker arms wolf_v8f_scene_pending, but the input-driven
# module_ui_tick never consumes it on normal coverflow.  V8I exposes a tiny
# render-thread dispatcher that reuses the already-proven render detour instead
# of depending on controller polling.  The atomic exchange preserves the
# one-shot behavior if the old input tick happens to run at the same time.
runtime = replace_once(
    runtime,
    'static void module_ui_tick(void *context)\n{\n',
    '''void wolf_v8i_render_ui_tick(void)\n{\n    if (load_u32(&g_runtime.wolf_v8f_scene_pending) == 0u) {\n        return;\n    }\n\n    wolf_v8h_write_trace(\n        2u, GetCurrentThreadId(), 0u, 0xFFFFFFFFu, 0u, 0u, 0xFFFFFFFFu);\n    if (__atomic_exchange_n(\n            &g_runtime.wolf_v8f_scene_pending,\n            0u,\n            __ATOMIC_ACQ_REL) != 0u) {\n        wolf_v8f_try_native_scene(0u);\n    }\n}\n\nstatic void module_ui_tick(void *context)\n{\n''',
    "runtime render-thread dispatcher",
)

runtime_path.write_text(runtime)

render_path = Path("native/src/render_detours.c")
render = render_path.read_text()

render = replace_once(
    render,
    '#include <auroraaz/render_detours.h>\n\n',
    '#include <auroraaz/render_detours.h>\n\n'
    '#if defined(AURORAAZ_XBOX360)\n'
    'extern void wolf_v8i_render_ui_tick(void);\n'
    '#endif\n\n',
    "render dispatcher declaration",
)

render = replace_once(
    render,
    '    store_i32(&g_render_detours.last_render_menu_result, render_result);\n\n'
    '    /* Publish only after Aurora has restored its coverflow render targets. */',
    '    store_i32(&g_render_detours.last_render_menu_result, render_result);\n\n'
    '#if defined(AURORAAZ_XBOX360)\n'
    '    /* V8I: this detour is continuously reached on Aurora coverflow, so\n'
    '     * use it as the native-XUI dispatch point instead of the input tick. */\n'
    '    wolf_v8i_render_ui_tick();\n'
    '#endif\n\n'
    '    /* Publish only after Aurora has restored its coverflow render targets. */',
    "render-menu tick",
)

render_path.write_text(render)
print("Wolf V8I render-thread native XUI dispatch applied")
