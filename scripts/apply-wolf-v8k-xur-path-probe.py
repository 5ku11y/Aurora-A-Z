#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8K XUR/path probe anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    '#define WOLF_V8H_TRACE_MARKER_VERSION 1u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    '#define WOLF_V8H_TRACE_MARKER_VERSION 1u\n'
    '#define WOLF_V8K_PATH_MARKER_VERSION 1u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    "V8K marker version",
)

runtime = replace_once(
    runtime,
    'typedef char WolfV8hTraceMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8hTraceMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8hTraceMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8hTraceMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct WolfV8kPathMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t file_read_ok;\n'
    '    uint32_t file_bytes_read;\n'
    '    uint32_t embedded_size;\n'
    '    uint32_t file_magic_be;\n'
    '    uint32_t file_version_be;\n'
    '    uint32_t path_a_status;\n'
    '    uint32_t path_a_scene;\n'
    '    uint32_t path_b_status;\n'
    '    uint32_t path_b_scene;\n'
    '    uint32_t create_address;\n'
    '    uint32_t destroy_address;\n'
    '    uint32_t ui_thread_id;\n'
    '    uint32_t attempt_count;\n'
    '    uint32_t completed;\n'
    '    uint32_t selected_path;\n'
    '} WolfV8kPathMarker;\n\n'
    'typedef char WolfV8kPathMarkerMustBe72Bytes[\n'
    '    sizeof(WolfV8kPathMarker) == 72u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8K marker structure",
)

runtime = replace_once(
    runtime,
    'static char g_wolf_v8h_trace_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8H-trace.bin";\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    'static char g_wolf_v8h_trace_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8H-trace.bin";\n'
    'static char g_wolf_v8k_path_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8K-path.bin";\n'
    'static uint8_t g_wolf_v8k_file_probe[2048u];\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    "V8K marker path",
)

runtime = replace_once(
    runtime,
    'static void wolf_v8h_write_trace(\n',
    '''static void wolf_v8k_write_path_marker(const WolfV8kPathMarker *marker)
{
    if (marker == NULL || write_complete_file(
            g_wolf_v8k_path_marker_path,
            (const uint8_t *)marker,
            (uint32_t)sizeof(*marker)) == 0u) {
        DbgPrint("WolfFactory V8K: path marker write failed\\n");
    }
}

static void wolf_v8k_probe_cached_xur(WolfV8kPathMarker *marker)
{
    HANDLE file;
    uint32_t bytes_read = 0u;
    int read_succeeded;
    int close_succeeded;

    if (marker == NULL) {
        return;
    }
    memset(g_wolf_v8k_file_probe, 0, sizeof(g_wolf_v8k_file_probe));
    file = CreateFileA(
        g_settings_xur_cache_path,
        GENERIC_READ,
        FILE_SHARE_READ,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        NULL);
    if (file == NULL || file == INVALID_HANDLE_VALUE) {
        return;
    }
    read_succeeded = ReadFile(
        file,
        g_wolf_v8k_file_probe,
        (uint32_t)sizeof(g_wolf_v8k_file_probe),
        &bytes_read,
        NULL);
    close_succeeded = CloseHandle(file);
    marker->file_bytes_read = bytes_read;
    marker->file_read_ok = read_succeeded != 0 && close_succeeded != 0 ? 1u : 0u;
    if (marker->file_read_ok != 0u && bytes_read >= 8u) {
        marker->file_magic_be =
            ((uint32_t)g_wolf_v8k_file_probe[0] << 24u) |
            ((uint32_t)g_wolf_v8k_file_probe[1] << 16u) |
            ((uint32_t)g_wolf_v8k_file_probe[2] << 8u) |
            (uint32_t)g_wolf_v8k_file_probe[3];
        marker->file_version_be =
            ((uint32_t)g_wolf_v8k_file_probe[4] << 24u) |
            ((uint32_t)g_wolf_v8k_file_probe[5] << 16u) |
            ((uint32_t)g_wolf_v8k_file_probe[6] << 8u) |
            (uint32_t)g_wolf_v8k_file_probe[7];
    }
}

static void wolf_v8h_write_trace(
''',
    "V8K writer and file probe",
)

runtime = replace_once(
    runtime,
    "    static const uint16_t scene_path[] = {\n"
    "        'A','u','r','o','r','a','A','Z','_','S','e','t','t','i','n','g','s','.',\n"
    "        'x','u','r',0\n"
    "    };\n"
    "    static const uint16_t heading_id[] = {",
    "    static const uint16_t scene_path[] = {\n"
    "        'A','u','r','o','r','a','A','Z','_','S','e','t','t','i','n','g','s','.',\n"
    "        'x','u','r',0\n"
    "    };\n"
    "    static const uint16_t alt_base_path[] = {\n"
    "        'f','i','l','e',':','/','/','g','a','m','e',':','/',0\n"
    "    };\n"
    "    static const uint16_t alt_scene_path[] = {\n"
    "        'D','a','t','a','/','A','u','r','o','r','a','A','Z','_',\n"
    "        'S','e','t','t','i','n','g','s','.','x','u','r',0\n"
    "    };\n"
    "    static const uint16_t heading_id[] = {",
    "alternate XUI path",
)

runtime = replace_once(
    runtime,
    '    WolfV8fSceneMarker marker;\n'
    '    WolfV8fXuiSceneCreateFn create_fn = NULL;',
    '    WolfV8fSceneMarker marker;\n'
    '    WolfV8kPathMarker v8k;\n'
    '    WolfV8fXuiSceneCreateFn create_fn = NULL;',
    "V8K local marker",
)

runtime = replace_once(
    runtime,
    '    memset(&marker, 0, sizeof(marker));\n'
    "    marker.magic[0] = 'W';",
    '    memset(&marker, 0, sizeof(marker));\n'
    '    memset(&v8k, 0, sizeof(v8k));\n'
    "    v8k.magic[0] = 'W';\n"
    "    v8k.magic[1] = 'F';\n"
    "    v8k.magic[2] = '8';\n"
    "    v8k.magic[3] = 'K';\n"
    '    v8k.version = WOLF_V8K_PATH_MARKER_VERSION;\n'
    '    v8k.record_size = (uint32_t)sizeof(v8k);\n'
    '    v8k.embedded_size = g_auroraaz_embedded_settings_xur_size;\n'
    '    v8k.path_a_status = 0xFFFFFFFFu;\n'
    '    v8k.path_b_status = 0xFFFFFFFFu;\n'
    '    wolf_v8k_probe_cached_xur(&v8k);\n'
    "    marker.magic[0] = 'W';",
    "V8K initialization",
)

runtime = replace_once(
    runtime,
    '        marker.create_status = (uint32_t)create_fn(\n'
    '            base_path, scene_path, NULL, &scene);',
    '''        v8k.create_address = marker.create_address;
        v8k.destroy_address = marker.destroy_address;
        v8k.ui_thread_id = marker.ui_thread_id;
        v8k.attempt_count = marker.attempt_count;
        marker.create_status = (uint32_t)create_fn(
            base_path, scene_path, NULL, &scene);
        v8k.path_a_status = marker.create_status;
        v8k.path_a_scene = scene;
        v8k.selected_path =
            (int32_t)marker.create_status >= 0 && scene != 0u ? 1u : 0u;
        if ((int32_t)marker.create_status < 0 || scene == 0u) {
            uint32_t alt_scene = 0u;
            v8k.path_b_status = (uint32_t)create_fn(
                alt_base_path, alt_scene_path, NULL, &alt_scene);
            v8k.path_b_scene = alt_scene;
            marker.create_status = v8k.path_b_status;
            scene = alt_scene;
            if ((int32_t)v8k.path_b_status >= 0 && alt_scene != 0u) {
                v8k.selected_path = 2u;
            }
        }
        else {
            v8k.path_b_status = 0xFFFFFFFEu;
        }''',
    "dual XUI path attempts",
)

runtime = replace_once(
    runtime,
    '    wolf_v8f_write_scene_marker(&marker);\n'
    '    wolf_v8h_write_trace(',
    '    v8k.completed = marker.completed;\n'
    '    wolf_v8k_write_path_marker(&v8k);\n'
    '    wolf_v8f_write_scene_marker(&marker);\n'
    '    wolf_v8h_write_trace(',
    "V8K final marker",
)

runtime_path.write_text(runtime)
print("Wolf V8K XUR integrity and dual-path probe applied")
