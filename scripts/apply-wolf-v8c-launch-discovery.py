#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8C discovery anchor missing: {label}")
    return text.replace(old, new, 1)


runtime_path = Path("native/src/rev1655_runtime.c")
runtime = runtime_path.read_text()

runtime = replace_once(
    runtime,
    '#define WOLF_V8B_IDLE_MARKER_VERSION 1u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    '#define WOLF_V8B_IDLE_MARKER_VERSION 1u\n'
    '#define WOLF_V8C_DUMP_MARKER_VERSION 1u\n'
    '#define WOLF_V8C_DUMP_PAGE_SIZE 0x1000u\n\n'
    '#define AZ_BROWSE_APPLY_NONE 0u',
    "V8C dump constants",
)

runtime = replace_once(
    runtime,
    'typedef char WolfV8bIdleMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8bIdleMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    'typedef char WolfV8bIdleMarkerMustBe64Bytes[\n'
    '    sizeof(WolfV8bIdleMarker) == 64u ? 1 : -1];\n\n'
    'typedef struct WolfV8cDumpMarker {\n'
    '    uint8_t magic[4];\n'
    '    uint32_t version;\n'
    '    uint32_t record_size;\n'
    '    uint32_t image_base;\n'
    '    uint32_t image_size;\n'
    '    uint32_t page_size;\n'
    '    uint32_t mapped_pages;\n'
    '    uint32_t zero_pages;\n'
    '    uint32_t bytes_written;\n'
    '    uint32_t runtime_state;\n'
    '    uint32_t completed;\n'
    '} WolfV8cDumpMarker;\n\n'
    'typedef char WolfV8cDumpMarkerMustBe44Bytes[\n'
    '    sizeof(WolfV8cDumpMarker) == 44u ? 1 : -1];\n\n'
    'typedef struct AzM2bRenderMarker {',
    "V8C dump marker structure",
)

runtime = replace_once(
    runtime,
    'static char g_wolf_v8b_idle_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8B-idle.bin";\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    'static char g_wolf_v8b_idle_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8B-idle.bin";\n'
    'static char g_wolf_v8c_image_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8C-image.bin";\n'
    'static char g_wolf_v8c_dump_marker_path[] =\n'
    '    "game:\\\\Data\\\\Logs\\\\WolfFactory-V8C-dump.bin";\n'
    '#if !defined(AURORAAZ_REV1655_RUNTIME_TEST_IO)',
    "V8C dump paths",
)

marker_writer_anchor = (
    'static void flush_wolf_v8b_idle_marker(void)\n'
    '{\n'
)
if marker_writer_anchor not in runtime:
    raise SystemExit("Wolf V8C discovery anchor missing: V8B marker writer")

# Put the dump helper immediately before the V8B marker writer so it can reuse
# write_complete_file while remaining independent of later overlay code.
dump_helpers = r'''static uint8_t wolf_v8c_page_is_mapped(
    uintptr_t address,
    uint32_t size)
{
    uintptr_t middle;

    if (size == 0u || address > UINTPTR_MAX - (uintptr_t)(size - 1u)) {
        return 0u;
    }
    middle = address + (uintptr_t)(size / 2u);
    return MmIsAddressValid((void *)address) &&
        MmIsAddressValid((void *)middle) &&
        MmIsAddressValid((void *)(address + (uintptr_t)size - 1u)) ? 1u : 0u;
}

static uint8_t write_wolf_v8c_image_dump(void)
{
    HANDLE file;
    uint8_t zero_page[WOLF_V8C_DUMP_PAGE_SIZE];
    WolfV8cDumpMarker marker;
    uint32_t offset = 0u;
    uint32_t mapped_pages = 0u;
    uint32_t zero_pages = 0u;
    uint32_t bytes_total = 0u;
    uint8_t succeeded = 1u;

    memset(zero_page, 0, sizeof(zero_page));
    memset(&marker, 0, sizeof(marker));

    file = CreateFileA(
        g_wolf_v8c_image_path,
        GENERIC_WRITE,
        FILE_SHARE_READ,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);
    if (file == NULL || file == INVALID_HANDLE_VALUE) {
        return 0u;
    }

    while (offset < AZ_REV1655_NT_IMAGE_SIZE) {
        const uint32_t remaining = AZ_REV1655_NT_IMAGE_SIZE - offset;
        const uint32_t chunk = remaining < WOLF_V8C_DUMP_PAGE_SIZE ?
            remaining : WOLF_V8C_DUMP_PAGE_SIZE;
        const uintptr_t address =
            (uintptr_t)AZ_REV1655_IMAGE_BASE + (uintptr_t)offset;
        const void *source;
        uint32_t bytes_written = 0u;

        if (wolf_v8c_page_is_mapped(address, chunk) != 0u) {
            source = (const void *)address;
            ++mapped_pages;
        }
        else {
            source = zero_page;
            ++zero_pages;
        }

        if (WriteFile(
                file,
                (void *)source,
                chunk,
                &bytes_written,
                NULL) == 0 ||
            bytes_written != chunk) {
            succeeded = 0u;
            break;
        }
        bytes_total += bytes_written;
        offset += chunk;
    }

    if (CloseHandle(file) == 0) {
        succeeded = 0u;
    }

    marker.magic[0] = 'W';
    marker.magic[1] = 'F';
    marker.magic[2] = '8';
    marker.magic[3] = 'C';
    marker.version = WOLF_V8C_DUMP_MARKER_VERSION;
    marker.record_size = (uint32_t)sizeof(marker);
    marker.image_base = AZ_REV1655_IMAGE_BASE;
    marker.image_size = AZ_REV1655_NT_IMAGE_SIZE;
    marker.page_size = WOLF_V8C_DUMP_PAGE_SIZE;
    marker.mapped_pages = mapped_pages;
    marker.zero_pages = zero_pages;
    marker.bytes_written = bytes_total;
    marker.runtime_state = load_u32(&g_runtime.state);
    marker.completed = succeeded != 0u &&
        bytes_total == AZ_REV1655_NT_IMAGE_SIZE ? 1u : 0u;

    (void)write_complete_file(
        g_wolf_v8c_dump_marker_path,
        (const uint8_t *)&marker,
        (uint32_t)sizeof(marker));
    return marker.completed != 0u ? 1u : 0u;
}

'''
runtime = runtime.replace(marker_writer_anchor, dump_helpers + marker_writer_anchor, 1)

runtime = replace_once(
    runtime,
    '    if (state == (uint32_t)AZ_REV1655_RUNTIME_RUNNING) {\n'
    '        wolf_idle_timer_init(\n',
    '    if (state == (uint32_t)AZ_REV1655_RUNTIME_RUNNING) {\n'
    '        if (write_wolf_v8c_image_dump() != 0u) {\n'
    '            DbgPrint(\n'
    '                "WolfFactory V8C: mapped Aurora image dump complete\\n");\n'
    '        }\n'
    '        else {\n'
    '            DbgPrint(\n'
    '                "WolfFactory V8C: mapped Aurora image dump failed\\n");\n'
    '        }\n'
    '        wolf_idle_timer_init(\n',
    "V8C one-shot discovery dump",
)

runtime_path.write_text(runtime)
print("Wolf V8C launch-discovery integration applied")
