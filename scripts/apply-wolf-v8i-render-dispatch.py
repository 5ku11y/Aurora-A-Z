#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8I/V8J render-dispatch anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

# V8H proved that the worker arms wolf_v8f_scene_pending, but the input-driven
# module_ui_tick never consumes it on normal coverflow. V8I exposes a tiny
# render-thread dispatcher that reuses the already-proven render detour instead
# of depending on controller polling. The atomic exchange preserves one-shot
# behavior if another dispatch path happens to run at the same time.
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

# V8J root-cause fix: the bootstrap was still starting INPUT_OBSERVE, which
# never installs render_menu/font_end/settings hooks. V8I therefore compiled
# correctly but its render dispatcher was unreachable on hardware. Start the
# existing OVERLAY_CANARY stage so those already revision-gated hooks are live.
bootstrap_path = Path("native/src/netdbg_bootstrap.c")
bootstrap = bootstrap_path.read_text()
bootstrap = replace_once(
    bootstrap,
    "    result = az_rev1655_runtime_start(\n"
    "        AZ_REV1655_RUNTIME_STAGE_INPUT_OBSERVE);",
    "    result = az_rev1655_runtime_start(\n"
    "        AZ_REV1655_RUNTIME_STAGE_OVERLAY_CANARY);",
    "overlay-canary bootstrap stage",
)
bootstrap_path.write_text(bootstrap)

# V8K is chained here so the cache-warmed V8J workflow applies the XUR/path
# diagnostics without changing workflow/cache scope again.
v8k_script = Path("scripts/apply-wolf-v8k-xur-path-probe.py")
exec(compile(v8k_script.read_text(), str(v8k_script), "exec"), {"__name__": "__main__"})

# The first V8K draft used a generic marker initializer anchor. Correct that
# generated placement before the Xbox compile so initialization lives only in
# wolf_v8f_try_native_scene().
v8k_fix_script = Path("scripts/fix-wolf-v8k-init-anchor.py")
exec(compile(v8k_fix_script.read_text(), str(v8k_fix_script), "exec"), {"__name__": "__main__"})

# V8L A/B tests the same native XUI loader against a tiny classless XUR taken
# directly from XboxUnity/AuroraScripts after both Wolf XUR path forms fail.
v8l_script = Path("scripts/apply-wolf-v8l-known-good-xur.py")
exec(compile(v8l_script.read_text(), str(v8l_script), "exec"), {"__name__": "__main__"})

# V8M moves the A/B test to the actual Aurora 0.7b.2/Nova HudScene generation:
# an XUIB v8 GameInfoScene.xur, tested both in-place and as an exact Data copy.
v8m_script = Path("scripts/apply-wolf-v8m-official-xur-probe.py")
exec(compile(v8m_script.read_text(), str(v8m_script), "exec"), {"__name__": "__main__"})

# V8N mutates four equal-length string-table entries in the exact V8M-passing
# XUIB v8 scene, preserving all offsets while proving a customized Wolf-owned
# v8 asset is accepted by the same native XUI loader.
v8n_script = Path("scripts/apply-wolf-v8n-custom-v8-xur.py")
exec(compile(v8n_script.read_text(), str(v8n_script), "exec"), {"__name__": "__main__"})

# V8O is the first visible native scene test. It creates the V8N custom-v8
# asset, navigates forward from the scene-gate-verified Aurora_Main handle,
# leaves it visible for ~180 render frames, then navigates back automatically.
v8o_script = Path("scripts/apply-wolf-v8o-visible-native-scene.py")
exec(compile(v8o_script.read_text(), str(v8o_script), "exec"), {"__name__": "__main__"})

# V8P bypasses the Nova/HudScene asset and scene navigation entirely. It creates
# a built-in XuiText object, configures it, attaches it directly to Aurora_Main,
# and removes it after a short visible proof. V8O itself is disabled so its
# existing hardware marker is preserved for later decoding.
v8p_script = Path("scripts/apply-wolf-v8p-direct-xui-overlay.py")
exec(compile(v8p_script.read_text(), str(v8p_script), "exec"), {"__name__": "__main__"})

# V8Q leaves both invisible XUI experiments disabled and drives the known-good
# final Font::End renderer directly with a giant solid-pixel panel for 240
# frames. This is the first visibility proof of the production render route.
v8q_script = Path("scripts/apply-wolf-v8q-final-render-probe.py")
exec(compile(v8q_script.read_text(), str(v8q_script), "exec"), {"__name__": "__main__"})

print("Wolf V8I/V8J render dispatch + V8K/V8L diagnostics + V8M/V8N/V8O/V8P/V8Q probes applied")
