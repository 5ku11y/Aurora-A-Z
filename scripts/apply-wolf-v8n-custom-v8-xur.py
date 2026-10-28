#!/usr/bin/env python3
import base64
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8N custom-v8 anchor missing: {label}")
    return text.replace(old, new, 1)


def c_bytes(data: bytes) -> str:
    lines = []
    for offset in range(0, len(data), 12):
        chunk = data[offset:offset + 12]
        lines.append("    " + ", ".join(f"0x{byte:02X}u" for byte in chunk) + ",")
    return "\n".join(lines)


def fnv1a32(data: bytes) -> int:
    value = 0x811C9DC5
    for byte in data:
        value ^= byte
        value = (value * 0x01000193) & 0xFFFFFFFF
    return value


# Start from the exact XUIB v8 GameInfoScene.xur that V8M passed on hardware.
OFFICIAL_XUR_B64 = """WFVJQgAAAAgAAAAAAA4AAAK4AAYGJgYdBgAAAAAAAAJTVFJOAAAAaAAAAG5W
RUNUAAAA1gAAADxDVVNUAAABEgAAAOBGTE9UAAAB8gAAACBDT0xSAAACEgAA
AChEQVRBAAACOgAAAH4AAABoAApYdWlDYW52YXMAWHVpU2NlbmUASW5mbwBm
c19HYW1lSW5mb1NjZW5lAFh1aUZpZ3VyZQBGYWRlcgBYdWlUZXh0AHR4dF9U
aXRsZU5hbWUAdHh0X0V4ZWN1dGlvbkluZm8AVG9wQmFyAAAAAABD6AAAAAAA
AEAAAABAAAAAP4AAAEEgAABD6AAAAAAAAEPdAABD6AAAAAAAAAAAAABD5wAA
AAAAAAAAAGxEXoAAQqoAAAAAAAQAAAAAAAAAAAAAAAAAAAAARF6AAAAAAABE
XoAAAAAAAERegAAAAAAARF6AAEKqAABEXoAAQqoAAERegABCqgAAAAAAAEKq
AAAAAAAAQqoAAAAAAABCqgAAAAAAAAAAAAAAAABsRAGAAECgAAAAAAAEAAAA
AAAAAAAAAAAAAAAAAEQBgAAAAAAARAGAAAAAAABEAYAAAAAAAEQBgABAoAAA
RAGAAECgAABEAYAAQKAAAAAAAABAoAAAAAAAAECgAAAAAAAAQKAAAAAAAAAA
AAAARFUAAEPwAABBgAAAAAAAAD+AAABDyAAAQQAAAEAAAAD/Dw+Avw8PD8gZ
GRkAAAAA/+vr6/8PDw//oKCg/0lTXf9QWmb/qrG3AQMCBgABAAECAwQHAwAB
AQQABAUBCA8GAAIADwABAgABB/WrAwECCg8BBAQCAwMCBAMDAwQBAgIBAQAH
AQgPCAUCAi4EBQb/AAARFQcBCA8JBQIDLgYFBv8AABIRBQEIDwoABwQPAwEC
AAQD9AoHBQcOAwMHCAkDAwQDAQFw
"""

original_xur = base64.b64decode(OFFICIAL_XUR_B64)
if len(original_xur) != 696:
    raise SystemExit(f"Wolf V8N base XUR length mismatch: {len(original_xur)}")
if original_xur[:4] != b"XUIB" or int.from_bytes(original_xur[4:8], "big") != 8:
    raise SystemExit("Wolf V8N base XUR integrity/version check failed")

custom_xur = bytearray(original_xur)
patches = (
    (b"Fader", b"ScanR"),
    (b"txt_TitleName", b"WolfTitleName"),
    (b"txt_ExecutionInfo", b"WolfFactoryStatus"),
    (b"TopBar", b"WolfUI"),
)
for old, new in patches:
    if len(old) != len(new):
        raise SystemExit(f"Wolf V8N patch length mismatch: {old!r} -> {new!r}")
    if custom_xur.count(old) != 1:
        raise SystemExit(f"Wolf V8N expected exactly one {old!r} string-table entry")
    offset = custom_xur.find(old)
    custom_xur[offset:offset + len(old)] = new

custom_xur = bytes(custom_xur)
if custom_xur[:8] != original_xur[:8] or len(custom_xur) != len(original_xur):
    raise SystemExit("Wolf V8N patch changed XUIB header or file length")
if custom_xur == original_xur:
    raise SystemExit("Wolf V8N custom XUR did not change")

original_fnv = fnv1a32(original_xur)
custom_fnv = fnv1a32(custom_xur)
if original_fnv == custom_fnv:
    raise SystemExit("Wolf V8N custom XUR digest unexpectedly unchanged")

runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    '#define WOLF_V8M_OFFICIAL_MARKER_VERSION 1u\n\n#define AZ_BROWSE_APPLY_NONE 0u',
    '#define WOLF_V8M_OFFICIAL_MARKER_VERSION 1u\n'
    '#define WOLF_V8N_CUSTOM_MARKER_VERSION 1u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    "V8N marker version",
)

runtime = replace_once(
    runtime,
    'typedef char WolfV8mOfficialMarkerMustBe96Bytes[\n'
    '    sizeof(WolfV8mOfficialMarker) == 96u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8mOfficialMarkerMustBe96Bytes[\n'
    '    sizeof(WolfV8mOfficialMarker) == 96u ? 1 : -1];\n\n'
    'typedef struct WolfV8nCustomMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t write_ok;\n'
    '    uint32_t xur_size;\n'
    '    uint32_t xur_magic_be;\n'
    '    uint32_t xur_version_be;\n'
    '    uint32_t patch_count;\n'
    '    uint32_t original_fnv1a;\n'
    '    uint32_t custom_fnv1a;\n'
    '    uint32_t create_status;\n'
    '    uint32_t created_scene;\n'
    '    uint32_t create_address;\n'
    '    uint32_t destroy_address;\n'
    '    uint32_t ui_thread_id;\n'
    '    uint32_t attempt_count;\n'
    '    uint32_t destroyed;\n'
    '    uint32_t completed;\n'
    '    uint32_t reserved0;\n'
    '    uint32_t reserved1;\n'
    '} WolfV8nCustomMarker;\n\n'
    'typedef char WolfV8nCustomMarkerMustBe80Bytes[\n'
    '    sizeof(WolfV8nCustomMarker) == 80u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8N marker structure",
)

asset_block = f'''static char g_wolf_v8n_marker_path[] =
    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8N-custom-v8.bin";
static char g_wolf_v8n_xur_path[] =
    "game:\\\\Data\\\\WolfFactory-V8N-custom-v8.xur";
static const uint8_t g_wolf_v8n_custom_xur[] = {{
{c_bytes(custom_xur)}
}};
'''
runtime = replace_once(
    runtime,
    'static const uint8_t g_wolf_v8m_official_xur[] = {',
    asset_block + 'static const uint8_t g_wolf_v8m_official_xur[] = {',
    "V8N embedded custom XUR",
)

runtime = replace_once(
    runtime,
    'static void wolf_v8m_write_official_marker(const WolfV8mOfficialMarker *marker)\n{',
    '''static void wolf_v8n_write_custom_marker(const WolfV8nCustomMarker *marker)
{
    if (marker == NULL || write_complete_file(
            g_wolf_v8n_marker_path,
            (const uint8_t *)marker,
            (uint32_t)sizeof(*marker)) == 0u) {
        DbgPrint("WolfFactory V8N: custom-v8 marker write failed\\n");
    }
}

static void wolf_v8m_write_official_marker(const WolfV8mOfficialMarker *marker)
{''',
    "V8N marker writer",
)

runtime = replace_once(
    runtime,
    "    static const uint16_t heading_id[] = {\n",
    "    static const uint16_t v8n_custom_scene[] = {\n"
    "        'W','o','l','f','F','a','c','t','o','r','y','-','V','8','N','-',\n"
    "        'c','u','s','t','o','m','-','v','8','.','x','u','r',0\n"
    "    };\n"
    "    static const uint16_t heading_id[] = {\n",
    "V8N custom scene path",
)

runtime = replace_once(
    runtime,
    '    WolfV8mOfficialMarker v8m;\n'
    '    WolfV8fXuiSceneCreateFn create_fn = NULL;',
    '    WolfV8mOfficialMarker v8m;\n'
    '    WolfV8nCustomMarker v8n;\n'
    '    WolfV8fXuiSceneCreateFn create_fn = NULL;',
    "V8N local marker",
)

runtime = replace_once(
    runtime,
    '    wolf_v8m_probe_installed_xur(&v8m);\n'
    "    marker.magic[0] = 'W';",
    '    wolf_v8m_probe_installed_xur(&v8m);\n'
    '    memset(&v8n, 0, sizeof(v8n));\n'
    "    v8n.magic[0] = 'W';\n"
    "    v8n.magic[1] = 'F';\n"
    "    v8n.magic[2] = '8';\n"
    "    v8n.magic[3] = 'N';\n"
    '    v8n.version = WOLF_V8N_CUSTOM_MARKER_VERSION;\n'
    '    v8n.record_size = (uint32_t)sizeof(v8n);\n'
    '    v8n.xur_size = (uint32_t)sizeof(g_wolf_v8n_custom_xur);\n'
    '    v8n.xur_magic_be = 0x58554942u;\n'
    '    v8n.xur_version_be = 8u;\n'
    f'    v8n.patch_count = {len(patches)}u;\n'
    f'    v8n.original_fnv1a = 0x{original_fnv:08X}u;\n'
    f'    v8n.custom_fnv1a = 0x{custom_fnv:08X}u;\n'
    '    v8n.create_status = 0xFFFFFFFFu;\n'
    "    marker.magic[0] = 'W';",
    "V8N marker initialization",
)

v8n_attempt = '''        /* V8N: take the exact Aurora XUIB v8 scene proven by V8M, mutate
         * four equal-length string-table entries without moving any binary
         * offsets, and verify that the customized v8 asset still creates. */
        if (v8m.completed != 0u) {
            uint32_t custom_scene = 0u;
            v8n.create_address = marker.create_address;
            v8n.destroy_address = marker.destroy_address;
            v8n.ui_thread_id = marker.ui_thread_id;
            v8n.attempt_count = marker.attempt_count;
            v8n.write_ok = write_complete_file(
                g_wolf_v8n_xur_path,
                g_wolf_v8n_custom_xur,
                (uint32_t)sizeof(g_wolf_v8n_custom_xur));
            if (v8n.write_ok != 0u) {
                v8n.create_status = (uint32_t)create_fn(
                    base_path,
                    v8n_custom_scene,
                    NULL,
                    &custom_scene);
                v8n.created_scene = custom_scene;
                if ((int32_t)v8n.create_status >= 0 && custom_scene != 0u) {
                    if (destroy_fn != NULL) {
                        destroy_fn(custom_scene);
                        v8n.destroyed = 1u;
                    }
                    v8n.completed = 1u;
                }
            }
            wolf_v8n_write_custom_marker(&v8n);
        }
'''

runtime = replace_once(
    runtime,
    '            wolf_v8m_write_official_marker(&v8m);\n'
    '        }\n'
    '        marker.created_scene = scene;',
    '            wolf_v8m_write_official_marker(&v8m);\n'
    '        }\n' + v8n_attempt + '        marker.created_scene = scene;',
    "V8N customized XUIB v8 attempt",
)

runtime_path.write_text(runtime)
print(
    "Wolf V8N custom XUIB v8 probe applied: "
    f"size={len(custom_xur)} patches={len(patches)} "
    f"fnv=0x{custom_fnv:08X}")
