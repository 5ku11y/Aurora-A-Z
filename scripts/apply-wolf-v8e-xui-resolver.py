#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8E resolver anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    '#define WOLF_V8B_IDLE_MARKER_VERSION 1u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    '#define WOLF_V8B_IDLE_MARKER_VERSION 1u\n'
    '#define WOLF_V8E_XUI_MARKER_VERSION 1u\n'
    '#define WOLF_V8E_XUI_CREATE_ORDINAL 855u\n'
    '#define WOLF_V8E_XUI_NAVIGATE_BACK_ORDINAL 856u\n'
    '#define WOLF_V8E_XUI_NAVIGATE_FIRST_ORDINAL 857u\n'
    '#define WOLF_V8E_XUI_NAVIGATE_FORWARD_ORDINAL 858u\n'
    '#define WOLF_V8E_XUI_RESOLVED_CREATE (1u << 0u)\n'
    '#define WOLF_V8E_XUI_RESOLVED_BACK (1u << 1u)\n'
    '#define WOLF_V8E_XUI_RESOLVED_FIRST (1u << 2u)\n'
    '#define WOLF_V8E_XUI_RESOLVED_FORWARD (1u << 3u)\n'
    '#define WOLF_V8E_XUI_RESOLVED_ALL 0x0Fu\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    "V8E resolver constants",
)

runtime = replace_once(
    runtime,
    'typedef char WolfV8bIdleMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8bIdleMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8bIdleMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8bIdleMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct WolfV8eXuiMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t runtime_state;\n'
    '    uint32_t module_status;\n'
    '    uint32_t xam_handle;\n'
    '    uint32_t create_status;\n'
    '    uint32_t create_address;\n'
    '    uint32_t back_status;\n'
    '    uint32_t back_address;\n'
    '    uint32_t first_status;\n'
    '    uint32_t first_address;\n'
    '    uint32_t forward_status;\n'
    '    uint32_t forward_address;\n'
    '    uint32_t resolved_mask;\n'
    '    uint32_t completed;\n'
    '} WolfV8eXuiMarker;\n\n'
    'typedef char WolfV8eXuiMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8eXuiMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8E marker structure",
)

runtime = replace_once(
    runtime,
    'static char g_wolf_v8b_idle_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8B-idle.bin";\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    'static char g_wolf_v8b_idle_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8B-idle.bin";\n'
    'static char g_wolf_v8e_xui_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8E-xui.bin";\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    "V8E marker path",
)

marker_writer_anchor = (
    'static void flush_wolf_v8b_idle_marker(void)\n'
    '{\n'
)
if marker_writer_anchor not in runtime:
    raise SystemExit("Wolf V8E resolver anchor missing: V8B marker writer")

resolver_helpers = r'''static uint32_t wolf_v8e_resolve_xam_export(
    HANDLE module,
    uint32_t ordinal,
    uint32_t *address_out)
{
    void *address = NULL;
    uint32_t status;

    if (address_out == NULL) {
        return 0xFFFFFFFFu;
    }
    *address_out = 0u;
    status = (uint32_t)XexGetProcedureAddress(module, ordinal, &address);
    if (status == 0u && address != NULL &&
        (uintptr_t)address <= UINT32_MAX) {
        *address_out = (uint32_t)(uintptr_t)address;
    }
    return status;
}

static void write_wolf_v8e_xui_resolver_marker(void)
{
    HANDLE xam_handle = NULL;
    WolfV8eXuiMarker marker;

    memset(&marker, 0, sizeof(marker));
    marker.magic[0] = 'W';
    marker.magic[1] = 'F';
    marker.magic[2] = '8';
    marker.magic[3] = 'E';
    marker.version = WOLF_V8E_XUI_MARKER_VERSION;
    marker.record_size = (uint32_t)sizeof(marker);
    marker.runtime_state = load_u32(&g_runtime.state);
    marker.create_status = 0xFFFFFFFFu;
    marker.back_status = 0xFFFFFFFFu;
    marker.first_status = 0xFFFFFFFFu;
    marker.forward_status = 0xFFFFFFFFu;

    marker.module_status = (uint32_t)XexGetModuleHandle("xam.xex", &xam_handle);
    if (marker.module_status == 0u && xam_handle != NULL &&
        (uintptr_t)xam_handle <= UINT32_MAX) {
        marker.xam_handle = (uint32_t)(uintptr_t)xam_handle;

        marker.create_status = wolf_v8e_resolve_xam_export(
            xam_handle,
            WOLF_V8E_XUI_CREATE_ORDINAL,
            &marker.create_address);
        if (marker.create_status == 0u && marker.create_address != 0u) {
            marker.resolved_mask |= WOLF_V8E_XUI_RESOLVED_CREATE;
        }

        marker.back_status = wolf_v8e_resolve_xam_export(
            xam_handle,
            WOLF_V8E_XUI_NAVIGATE_BACK_ORDINAL,
            &marker.back_address);
        if (marker.back_status == 0u && marker.back_address != 0u) {
            marker.resolved_mask |= WOLF_V8E_XUI_RESOLVED_BACK;
        }

        marker.first_status = wolf_v8e_resolve_xam_export(
            xam_handle,
            WOLF_V8E_XUI_NAVIGATE_FIRST_ORDINAL,
            &marker.first_address);
        if (marker.first_status == 0u && marker.first_address != 0u) {
            marker.resolved_mask |= WOLF_V8E_XUI_RESOLVED_FIRST;
        }

        marker.forward_status = wolf_v8e_resolve_xam_export(
            xam_handle,
            WOLF_V8E_XUI_NAVIGATE_FORWARD_ORDINAL,
            &marker.forward_address);
        if (marker.forward_status == 0u && marker.forward_address != 0u) {
            marker.resolved_mask |= WOLF_V8E_XUI_RESOLVED_FORWARD;
        }
    }

    marker.completed =
        marker.module_status == 0u &&
        marker.xam_handle != 0u &&
        marker.resolved_mask == WOLF_V8E_XUI_RESOLVED_ALL ? 1u : 0u;

    if (write_complete_file(
            g_wolf_v8e_xui_marker_path,
            (const uint8_t *)&marker,
            (uint32_t)sizeof(marker)) == 0u) {
        DbgPrint("WolfFactory V8E: XUI resolver marker write failed\n");
    }
    else {
        DbgPrint(
            "WolfFactory V8E: XUI resolver complete mask=0x%02X\n",
            marker.resolved_mask);
    }
}

'''
runtime = runtime.replace(marker_writer_anchor, resolver_helpers + marker_writer_anchor, 1)

runtime = replace_once(
    runtime,
    '        flush_wolf_v8b_idle_marker();\n'
    '        DbgPrint(',
    '        flush_wolf_v8b_idle_marker();\n'
    '        write_wolf_v8e_xui_resolver_marker();\n'
    '        DbgPrint(',
    "V8E one-shot resolver",
)

runtime_path.write_text(runtime)
print("Wolf V8E XUI resolver integration applied")
