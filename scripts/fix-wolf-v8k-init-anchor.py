#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8K init-fix anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

bad_init = '''    memset(&marker, 0, sizeof(marker));
    memset(&v8k, 0, sizeof(v8k));
    v8k.magic[0] = 'W';
    v8k.magic[1] = 'F';
    v8k.magic[2] = '8';
    v8k.magic[3] = 'K';
    v8k.version = WOLF_V8K_PATH_MARKER_VERSION;
    v8k.record_size = (uint32_t)sizeof(v8k);
    v8k.embedded_size = g_auroraaz_embedded_settings_xur_size;
    v8k.path_a_status = 0xFFFFFFFFu;
    v8k.path_b_status = 0xFFFFFFFFu;
    wolf_v8k_probe_cached_xur(&v8k);
    marker.magic[0] = 'W';'''
runtime = replace_once(
    runtime,
    bad_init,
    '''    memset(&marker, 0, sizeof(marker));
    marker.magic[0] = 'W';''',
    "remove misplaced initializer",
)

scene_anchor = '''    WolfV8fSceneMarker marker;
    WolfV8kPathMarker v8k;
    WolfV8fXuiSceneCreateFn create_fn = NULL;
    WolfV8fXuiSceneNavigateForwardFn navigate_fn = NULL;
    WolfV8fXuiDestroyObjectFn destroy_fn = NULL;

    memset(&marker, 0, sizeof(marker));
    marker.magic[0] = 'W';'''
scene_replacement = '''    WolfV8fSceneMarker marker;
    WolfV8kPathMarker v8k;
    WolfV8fXuiSceneCreateFn create_fn = NULL;
    WolfV8fXuiSceneNavigateForwardFn navigate_fn = NULL;
    WolfV8fXuiDestroyObjectFn destroy_fn = NULL;

    memset(&marker, 0, sizeof(marker));
    memset(&v8k, 0, sizeof(v8k));
    v8k.magic[0] = 'W';
    v8k.magic[1] = 'F';
    v8k.magic[2] = '8';
    v8k.magic[3] = 'K';
    v8k.version = WOLF_V8K_PATH_MARKER_VERSION;
    v8k.record_size = (uint32_t)sizeof(v8k);
    v8k.embedded_size = g_auroraaz_embedded_settings_xur_size;
    v8k.path_a_status = 0xFFFFFFFFu;
    v8k.path_b_status = 0xFFFFFFFFu;
    wolf_v8k_probe_cached_xur(&v8k);
    marker.magic[0] = 'W';'''
runtime = replace_once(
    runtime,
    scene_anchor,
    scene_replacement,
    "scene-local initializer",
)

runtime_path.write_text(runtime)
print("Wolf V8K initializer anchor corrected")
