#!/usr/bin/env python3
import base64
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8L smoke-probe anchor missing: {label}")
    return text.replace(old, new, 1)


def c_bytes(data: bytes) -> str:
    lines = []
    for offset in range(0, len(data), 12):
        chunk = data[offset:offset + 12]
        lines.append("    " + ", ".join(f"0x{byte:02X}u" for byte in chunk) + ",")
    return "\n".join(lines)


# Exact classless AuroraScripts NetworkSpeedCheck icon scene and its image.
# Source: XboxUnity/AuroraScripts, UtilityScripts/NetworkSpeedCheck/icon/.
SMOKE_XUR_B64 = """WFVJQgAAAAUAAAAAAAwAAAGzAANTVFJOAAAAOAAAAHxWRUNUAAAAtAAAAEhE
QVRBAAAA/AAAALcACQBYAHUAaQBDAGEAbgB2AGEAcwAIAFgAdQBpAFMAYwBl
AG4AZQAJAEkAYwBvAG4AUwBjAGUAbgBlAAgAWAB1AGkASQBtAGEAZwBlAA4A
QQBuAGkAbQBhAHQAaQBvAG4AUwB0AHIAaQBwAAgAaQBjAG8AbgAuAHAAbgBn
AAAAAAAAAAAAAAAAwoAAAAAAAAAAAAAAwwAAAAAAAAAAAAAAw0AAAAAAAAAA
AAAAw4AAAAAAAAAAAAAAw6AAAAAAAAAAAAAAAAEDAAIMAAAABkKAAABCgAAA
AAAAAAEAAgcABBwAAEAHAANCgAAAQoAAAAEAAAAAAAEABAEABRQAAAAHAAVD
wAAAQoAAAAkDAAAAAQAGAAAAAAAAAAEABQAAAAEBAQMAAAAHAAAAAAEAADIA
AAAAAAAABQEAADIAAAABAAAACgEAADIAAAACAAAADwEAADIAAAADAAAAFAEA
ADIAAAAEAAAAGQEAADIAAAAFAAAAHQAAADIAAAAF
"""
SMOKE_PNG_B64 = """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
6hc+lgAAAABJRU5ErkJggg==
"""

smoke_xur = base64.b64decode(SMOKE_XUR_B64)
smoke_png = base64.b64decode(SMOKE_PNG_B64)
if len(smoke_xur) != 435 or smoke_xur[:4] != b"XUIB" or int.from_bytes(smoke_xur[4:8], "big") != 5:
    raise SystemExit("Wolf V8L source XUR integrity check failed")
if len(smoke_png) != 1636 or smoke_png[:8] != b"\x89PNG\r\n\x1a\n":
    raise SystemExit("Wolf V8L source PNG integrity check failed")

runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    '#define WOLF_V8K_PATH_MARKER_VERSION 1u\n\n#define AZ_BROWSE_APPLY_NONE 0u',
    '#define WOLF_V8K_PATH_MARKER_VERSION 1u\n#define WOLF_V8L_SMOKE_MARKER_VERSION 1u\n\n#define AZ_BROWSE_APPLY_NONE 0u',
    "V8L marker version",
)

runtime = replace_once(
    runtime,
    'typedef char WolfV8kPathMarkerMustBe72Bytes[\n'
    '    sizeof(WolfV8kPathMarker) == 72u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8kPathMarkerMustBe72Bytes[\n'
    '    sizeof(WolfV8kPathMarker) == 72u ? 1 : -1];\n\n'
    'typedef struct WolfV8lSmokeMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t xur_write_ok;\n'
    '    uint32_t png_write_ok;\n'
    '    uint32_t xur_size;\n'
    '    uint32_t png_size;\n'
    '    uint32_t xur_magic_be;\n'
    '    uint32_t xur_version_be;\n'
    '    uint32_t create_status;\n'
    '    uint32_t created_scene;\n'
    '    uint32_t create_address;\n'
    '    uint32_t destroy_address;\n'
    '    uint32_t ui_thread_id;\n'
    '    uint32_t attempt_count;\n'
    '    uint32_t destroy_attempted;\n'
    '    uint32_t completed;\n'
    '    uint32_t reserved0;\n'
    '} WolfV8lSmokeMarker;\n\n'
    'typedef char WolfV8lSmokeMarkerMustBe72Bytes[\n'
    '    sizeof(WolfV8lSmokeMarker) == 72u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8L marker structure",
)

asset_block = f'''static char g_wolf_v8l_smoke_marker_path[] =
    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8L-xur-smoke.bin";
static char g_wolf_v8l_smoke_xur_path[] =
    "game:\\\\Data\\\\WolfFactory-V8L-smoke.xur";
static char g_wolf_v8l_smoke_png_path[] =
    "game:\\\\Data\\\\icon.png";
static const uint8_t g_wolf_v8l_smoke_xur[] = {{
{c_bytes(smoke_xur)}
}};
static const uint8_t g_wolf_v8l_smoke_png[] = {{
{c_bytes(smoke_png)}
}};
'''
runtime = replace_once(
    runtime,
    'static uint8_t g_wolf_v8k_file_probe[2048u];\n#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    'static uint8_t g_wolf_v8k_file_probe[2048u];\n' + asset_block + '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    "V8L embedded Aurora smoke assets",
)

runtime = replace_once(
    runtime,
    'static void wolf_v8k_write_path_marker(const WolfV8kPathMarker *marker)\n{',
    '''static void wolf_v8l_write_smoke_marker(const WolfV8lSmokeMarker *marker)
{
    if (marker == NULL || write_complete_file(
            g_wolf_v8l_smoke_marker_path,
            (const uint8_t *)marker,
            (uint32_t)sizeof(*marker)) == 0u) {
        DbgPrint("WolfFactory V8L: smoke marker write failed\\n");
    }
}

static void wolf_v8k_write_path_marker(const WolfV8kPathMarker *marker)
{''',
    "V8L marker writer",
)

runtime = replace_once(
    runtime,
    "    static const uint16_t heading_id[] = {\n",
    "    static const uint16_t smoke_scene_path[] = {\n"
    "        'W','o','l','f','F','a','c','t','o','r','y','-','V','8','L','-',\n"
    "        's','m','o','k','e','.','x','u','r',0\n"
    "    };\n"
    "    static const uint16_t heading_id[] = {\n",
    "V8L smoke scene path",
)

runtime = replace_once(
    runtime,
    '    WolfV8fSceneMarker marker;\n'
    '    WolfV8kPathMarker v8k;\n'
    '    WolfV8fXuiSceneCreateFn create_fn = NULL;',
    '    WolfV8fSceneMarker marker;\n'
    '    WolfV8kPathMarker v8k;\n'
    '    WolfV8lSmokeMarker v8l;\n'
    '    WolfV8fXuiSceneCreateFn create_fn = NULL;',
    "V8L local marker",
)

runtime = replace_once(
    runtime,
    '    wolf_v8k_probe_cached_xur(&v8k);\n'
    "    marker.magic[0] = 'W';",
    '    wolf_v8k_probe_cached_xur(&v8k);\n'
    '    memset(&v8l, 0, sizeof(v8l));\n'
    "    v8l.magic[0] = 'W';\n"
    "    v8l.magic[1] = 'F';\n"
    "    v8l.magic[2] = '8';\n"
    "    v8l.magic[3] = 'L';\n"
    '    v8l.version = WOLF_V8L_SMOKE_MARKER_VERSION;\n'
    '    v8l.record_size = (uint32_t)sizeof(v8l);\n'
    '    v8l.xur_size = (uint32_t)sizeof(g_wolf_v8l_smoke_xur);\n'
    '    v8l.png_size = (uint32_t)sizeof(g_wolf_v8l_smoke_png);\n'
    '    v8l.xur_magic_be = 0x58554942u;\n'
    '    v8l.xur_version_be = 5u;\n'
    '    v8l.create_status = 0xFFFFFFFFu;\n'
    "    marker.magic[0] = 'W';",
    "V8L marker initialization",
)

smoke_attempt = '''        /* V8L: if both Wolf asset path forms fail, A/B the same XUI loader
         * against a classless XUR taken directly from XboxUnity/AuroraScripts.
         * Keep the original V8G/V8K result untouched for diagnosis. */
        if (v8k.selected_path == 0u) {
            uint32_t smoke_scene = 0u;
            v8l.create_address = marker.create_address;
            v8l.destroy_address = marker.destroy_address;
            v8l.ui_thread_id = marker.ui_thread_id;
            v8l.attempt_count = marker.attempt_count;
            v8l.xur_write_ok = write_complete_file(
                g_wolf_v8l_smoke_xur_path,
                g_wolf_v8l_smoke_xur,
                (uint32_t)sizeof(g_wolf_v8l_smoke_xur));
            v8l.png_write_ok = write_complete_file(
                g_wolf_v8l_smoke_png_path,
                g_wolf_v8l_smoke_png,
                (uint32_t)sizeof(g_wolf_v8l_smoke_png));
            if (v8l.xur_write_ok != 0u && v8l.png_write_ok != 0u) {
                v8l.create_status = (uint32_t)create_fn(
                    base_path, smoke_scene_path, NULL, &smoke_scene);
                v8l.created_scene = smoke_scene;
                if ((int32_t)v8l.create_status >= 0 && smoke_scene != 0u) {
                    if (destroy_fn != NULL) {
                        destroy_fn(smoke_scene);
                        v8l.destroy_attempted = 1u;
                    }
                    v8l.completed = 1u;
                }
            }
            wolf_v8l_write_smoke_marker(&v8l);
        }
'''
runtime = replace_once(
    runtime,
    '        marker.created_scene = scene;\n'
    '        wolf_v8h_write_trace(',
    smoke_attempt + '        marker.created_scene = scene;\n        wolf_v8h_write_trace(',
    "V8L known-good XUR smoke attempt",
)

runtime_path.write_text(runtime)
print("Wolf V8L known-good Aurora XUR smoke probe applied")
