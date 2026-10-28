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
    '    if (create_fn != NULL) {',
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

runtime_path.write_text(runtime)
print("Wolf V8G settings-independent native XUI create probe applied")
