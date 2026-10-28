#!/usr/bin/env python3
import base64
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8M official-XUR anchor missing: {label}")
    return text.replace(old, new, 1)


def c_bytes(data: bytes) -> str:
    lines = []
    for offset in range(0, len(data), 12):
        chunk = data[offset:offset + 12]
        lines.append("    " + ", ".join(f"0x{byte:02X}u" for byte in chunk) + ",")
    return "\n".join(lines)


# Exact GameInfoScene.xur from the Aurora 0.7b.2 package HudScene set.
# This is XUIB version 8, unlike the V5 Wolf/AuroraScripts probe assets.
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

official_xur = base64.b64decode(OFFICIAL_XUR_B64)
if len(official_xur) != 696:
    raise SystemExit(f"Wolf V8M official XUR length mismatch: {len(official_xur)}")
if official_xur[:4] != b"XUIB" or int.from_bytes(official_xur[4:8], "big") != 8:
    raise SystemExit("Wolf V8M official XUR integrity/version check failed")

runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    '#define WOLF_V8L_SMOKE_MARKER_VERSION 1u\n\n#define AZ_BROWSE_APPLY_NONE 0u',
    '#define WOLF_V8L_SMOKE_MARKER_VERSION 1u\n#define WOLF_V8M_OFFICIAL_MARKER_VERSION 1u\n\n#define AZ_BROWSE_APPLY_NONE 0u',
    "V8M marker version",
)

runtime = replace_once(
    runtime,
    'typedef char WolfV8lSmokeMarkerMustBe72Bytes[\n'
    '    sizeof(WolfV8lSmokeMarker) == 72u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8lSmokeMarkerMustBe72Bytes[\n'
    '    sizeof(WolfV8lSmokeMarker) == 72u ? 1 : -1];\n\n'
    'typedef struct WolfV8mOfficialMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t installed_read_ok;\n'
    '    uint32_t installed_bytes_read;\n'
    '    uint32_t installed_magic_be;\n'
    '    uint32_t installed_version_be;\n'
    '    uint32_t embedded_write_ok;\n'
    '    uint32_t embedded_size;\n'
    '    uint32_t embedded_magic_be;\n'
    '    uint32_t embedded_version_be;\n'
    '    uint32_t installed_create_status;\n'
    '    uint32_t installed_scene;\n'
    '    uint32_t embedded_create_status;\n'
    '    uint32_t embedded_scene;\n'
    '    uint32_t create_address;\n'
    '    uint32_t destroy_address;\n'
    '    uint32_t ui_thread_id;\n'
    '    uint32_t attempt_count;\n'
    '    uint32_t installed_destroyed;\n'
    '    uint32_t embedded_destroyed;\n'
    '    uint32_t success_mask;\n'
    '    uint32_t completed;\n'
    '    uint32_t reserved0;\n'
    '} WolfV8mOfficialMarker;\n\n'
    'typedef char WolfV8mOfficialMarkerMustBe96Bytes[\n'
    '    sizeof(WolfV8mOfficialMarker) == 96u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8M marker structure",
)

asset_block = f'''static char g_wolf_v8m_marker_path[] =
    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8M-official-xur.bin";
static char g_wolf_v8m_installed_xur_path[] =
    "game:\\\\Plugins\\\\HudScene\\\\GameInfoScene.xur";
static char g_wolf_v8m_embedded_xur_path[] =
    "game:\\\\Data\\\\WolfFactory-V8M-GameInfoScene.xur";
static uint8_t g_wolf_v8m_file_probe[1024u];
static const uint8_t g_wolf_v8m_official_xur[] = {{
{c_bytes(official_xur)}
}};
'''
runtime = replace_once(
    runtime,
    'static const uint8_t g_wolf_v8l_smoke_png[] = {',
    asset_block + 'static const uint8_t g_wolf_v8l_smoke_png[] = {',
    "V8M paths and embedded official XUR",
)

runtime = replace_once(
    runtime,
    'static void wolf_v8l_write_smoke_marker(const WolfV8lSmokeMarker *marker)\n{',
    '''static void wolf_v8m_write_official_marker(const WolfV8mOfficialMarker *marker)
{
    if (marker == NULL || write_complete_file(
            g_wolf_v8m_marker_path,
            (const uint8_t *)marker,
            (uint32_t)sizeof(*marker)) == 0u) {
        DbgPrint("WolfFactory V8M: official-XUR marker write failed\\n");
    }
}

static void wolf_v8m_probe_installed_xur(WolfV8mOfficialMarker *marker)
{
    HANDLE file;
    uint32_t bytes_read = 0u;
    int read_succeeded;
    int close_succeeded;

    if (marker == NULL) {
        return;
    }
    memset(g_wolf_v8m_file_probe, 0, sizeof(g_wolf_v8m_file_probe));
    file = CreateFileA(
        g_wolf_v8m_installed_xur_path,
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
        g_wolf_v8m_file_probe,
        (uint32_t)sizeof(g_wolf_v8m_file_probe),
        &bytes_read,
        NULL);
    close_succeeded = CloseHandle(file);
    marker->installed_bytes_read = bytes_read;
    marker->installed_read_ok =
        read_succeeded != 0 && close_succeeded != 0 ? 1u : 0u;
    if (marker->installed_read_ok != 0u && bytes_read >= 8u) {
        marker->installed_magic_be =
            ((uint32_t)g_wolf_v8m_file_probe[0] << 24u) |
            ((uint32_t)g_wolf_v8m_file_probe[1] << 16u) |
            ((uint32_t)g_wolf_v8m_file_probe[2] << 8u) |
            (uint32_t)g_wolf_v8m_file_probe[3];
        marker->installed_version_be =
            ((uint32_t)g_wolf_v8m_file_probe[4] << 24u) |
            ((uint32_t)g_wolf_v8m_file_probe[5] << 16u) |
            ((uint32_t)g_wolf_v8m_file_probe[6] << 8u) |
            (uint32_t)g_wolf_v8m_file_probe[7];
    }
}

static void wolf_v8l_write_smoke_marker(const WolfV8lSmokeMarker *marker)
{''',
    "V8M writer and installed file probe",
)

runtime = replace_once(
    runtime,
    "    static const uint16_t smoke_scene_path[] = {\n"
    "        'W','o','l','f','F','a','c','t','o','r','y','-','V','8','L','-',\n"
    "        's','m','o','k','e','.','x','u','r',0\n"
    "    };\n"
    "    static const uint16_t heading_id[] = {",
    "    static const uint16_t smoke_scene_path[] = {\n"
    "        'W','o','l','f','F','a','c','t','o','r','y','-','V','8','L','-',\n"
    "        's','m','o','k','e','.','x','u','r',0\n"
    "    };\n"
    "    static const uint16_t v8m_installed_base[] = {\n"
    "        'f','i','l','e',':','/','/','g','a','m','e',':','/',\n"
    "        'P','l','u','g','i','n','s','/','H','u','d','S','c','e','n','e','/',0\n"
    "    };\n"
    "    static const uint16_t v8m_installed_scene[] = {\n"
    "        'G','a','m','e','I','n','f','o','S','c','e','n','e','.','x','u','r',0\n"
    "    };\n"
    "    static const uint16_t v8m_embedded_scene[] = {\n"
    "        'W','o','l','f','F','a','c','t','o','r','y','-','V','8','M','-',\n"
    "        'G','a','m','e','I','n','f','o','S','c','e','n','e','.','x','u','r',0\n"
    "    };\n"
    "    static const uint16_t heading_id[] = {",
    "V8M XUI paths",
)

runtime = replace_once(
    runtime,
    '    WolfV8kPathMarker v8k;\n'
    '    WolfV8lSmokeMarker v8l;\n'
    '    WolfV8fXuiSceneCreateFn create_fn = NULL;',
    '    WolfV8kPathMarker v8k;\n'
    '    WolfV8lSmokeMarker v8l;\n'
    '    WolfV8mOfficialMarker v8m;\n'
    '    WolfV8fXuiSceneCreateFn create_fn = NULL;',
    "V8M local marker",
)

runtime = replace_once(
    runtime,
    '    v8l.create_status = 0xFFFFFFFFu;\n'
    "    marker.magic[0] = 'W';",
    '    v8l.create_status = 0xFFFFFFFFu;\n'
    '    memset(&v8m, 0, sizeof(v8m));\n'
    "    v8m.magic[0] = 'W';\n"
    "    v8m.magic[1] = 'F';\n"
    "    v8m.magic[2] = '8';\n"
    "    v8m.magic[3] = 'M';\n"
    '    v8m.version = WOLF_V8M_OFFICIAL_MARKER_VERSION;\n'
    '    v8m.record_size = (uint32_t)sizeof(v8m);\n'
    '    v8m.embedded_size = (uint32_t)sizeof(g_wolf_v8m_official_xur);\n'
    '    v8m.embedded_magic_be = 0x58554942u;\n'
    '    v8m.embedded_version_be = 8u;\n'
    '    v8m.installed_create_status = 0xFFFFFFFFu;\n'
    '    v8m.embedded_create_status = 0xFFFFFFFFu;\n'
    '    wolf_v8m_probe_installed_xur(&v8m);\n'
    "    marker.magic[0] = 'W';",
    "V8M marker initialization",
)

v8m_attempt = '''        /* V8M: probe an XUIB v8 scene from the actual Aurora 0.7b.2
         * HudScene generation. Test the installed copy and an exact embedded
         * copy through the same XuiSceneCreate pointer on the same UI thread. */
        if (v8k.selected_path == 0u && v8l.completed == 0u) {
            uint32_t installed_scene = 0u;
            uint32_t embedded_scene = 0u;
            v8m.create_address = marker.create_address;
            v8m.destroy_address = marker.destroy_address;
            v8m.ui_thread_id = marker.ui_thread_id;
            v8m.attempt_count = marker.attempt_count;

            if (v8m.installed_read_ok != 0u) {
                v8m.installed_create_status = (uint32_t)create_fn(
                    v8m_installed_base,
                    v8m_installed_scene,
                    NULL,
                    &installed_scene);
                v8m.installed_scene = installed_scene;
                if ((int32_t)v8m.installed_create_status >= 0 &&
                    installed_scene != 0u) {
                    v8m.success_mask |= 1u;
                    if (destroy_fn != NULL) {
                        destroy_fn(installed_scene);
                        v8m.installed_destroyed = 1u;
                    }
                }
            }

            v8m.embedded_write_ok = write_complete_file(
                g_wolf_v8m_embedded_xur_path,
                g_wolf_v8m_official_xur,
                (uint32_t)sizeof(g_wolf_v8m_official_xur));
            if (v8m.embedded_write_ok != 0u) {
                v8m.embedded_create_status = (uint32_t)create_fn(
                    base_path,
                    v8m_embedded_scene,
                    NULL,
                    &embedded_scene);
                v8m.embedded_scene = embedded_scene;
                if ((int32_t)v8m.embedded_create_status >= 0 &&
                    embedded_scene != 0u) {
                    v8m.success_mask |= 2u;
                    if (destroy_fn != NULL) {
                        destroy_fn(embedded_scene);
                        v8m.embedded_destroyed = 1u;
                    }
                }
            }
            v8m.completed = v8m.success_mask != 0u ? 1u : 0u;
            wolf_v8m_write_official_marker(&v8m);
        }
'''

runtime = replace_once(
    runtime,
    '            wolf_v8l_write_smoke_marker(&v8l);\n'
    '        }\n'
    '        marker.created_scene = scene;',
    '            wolf_v8l_write_smoke_marker(&v8l);\n'
    '        }\n' + v8m_attempt + '        marker.created_scene = scene;',
    "V8M official Aurora XUR attempts",
)

runtime_path.write_text(runtime)
print("Wolf V8M official Aurora XUR v8 probe applied")
