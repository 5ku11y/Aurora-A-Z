#!/usr/bin/env python3
"""Patch pinned SynthXEX with a fixed Spelunkr360 Execution ID.

The pinned SynthXEX build currently has no 0x40006 Execution ID support.  Aurora
needs a stable TitleID to bind homebrew assets reliably, so this adds the small
24-byte header for Spelunkr360 (TitleID 0x53503601).

Run this only after openxechain-synthxex-image-base.patch has been applied.
"""

from pathlib import Path
import sys

TITLE_ID = 0x53503601


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise SystemExit(f"Spelunkr SynthXEX anchor missing in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1))


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch-spelunkr-synthxex-titleid.py <SynthXEX source dir>")

    root = Path(sys.argv[1])
    storage = root / "src/common/datastorage.h"
    optheaders = root / "src/setdata/optheaders.c"
    placer = root / "src/placer/placer.c"
    writer = root / "src/write/writexex.c"

    replace_once(
        storage,
        "#define XEX_OPT_ID_SYS_FLAGS       0x30000\n",
        "#define XEX_OPT_ID_SYS_FLAGS       0x30000\n"
        "#define XEX_OPT_ID_EXECUTION_ID    0x40006\n",
    )

    replace_once(
        storage,
        "struct optHeaders\n{\n"
        "    struct basefileFormat basefileFormat;\n"
        "    struct importLibraries importLibraries;\n"
        "    struct tlsInfo tlsInfo;\n"
        "};\n",
        "struct __attribute__((packed)) executionId\n"
        "{\n"
        "    uint32_t mediaId;\n"
        "    uint32_t version;\n"
        "    uint32_t baseVersion;\n"
        "    uint32_t titleId;\n"
        "    uint8_t platform;\n"
        "    uint8_t execType;\n"
        "    uint8_t discNumber;\n"
        "    uint8_t discCount;\n"
        "    uint32_t savegameId;\n"
        "};\n\n"
        "struct optHeaders\n"
        "{\n"
        "    struct basefileFormat basefileFormat;\n"
        "    struct importLibraries importLibraries;\n"
        "    struct tlsInfo tlsInfo;\n"
        "    struct executionId executionId;\n"
        "};\n",
    )

    replace_once(
        optheaders,
        "void setSysFlags(uint32_t *flags)\n"
        "{\n"
        "    if(flags == NULL)\n"
        "    { return; }\n\n"
        "    *flags = XEX_SYS_GAMEPAD_DISCONNECT |\n"
        "             XEX_SYS_INSECURE_SOCKETS |\n"
        "             XEX_SYS_XAM_HOOKS |\n"
        "             XEX_SYS_BACKGROUND_DL |\n"
        "             XEX_SYS_ALLOW_CONTROL_SWAP;\n"
        "}\n",
        "void setSysFlags(uint32_t *flags)\n"
        "{\n"
        "    if(flags == NULL)\n"
        "    { return; }\n\n"
        "    *flags = XEX_SYS_GAMEPAD_DISCONNECT |\n"
        "             XEX_SYS_INSECURE_SOCKETS |\n"
        "             XEX_SYS_XAM_HOOKS |\n"
        "             XEX_SYS_BACKGROUND_DL |\n"
        "             XEX_SYS_ALLOW_CONTROL_SWAP;\n"
        "}\n\n"
        "static void setSpelunkrExecutionId(struct executionId *executionId)\n"
        "{\n"
        "    memset(executionId, 0, sizeof(*executionId));\n"
        f"    executionId->titleId = 0x{TITLE_ID:08X}u;\n"
        "    executionId->discNumber = 1u;\n"
        "    executionId->discCount = 1u;\n"
        "}\n",
    )

    replace_once(
        optheaders,
        "    optHeaderEntries->count = 4;\n",
        "    optHeaderEntries->count = 5;\n",
    )

    replace_once(
        optheaders,
        "    setSysFlags(&(optHeaderEntries->optHeaderEntry[currentHeader].dataOrOffset));\n"
        "#pragma GCC diagnostic pop\n\n"
        "    //currentHeader++;\n\n"
        "    return SUCCESS;\n",
        "    setSysFlags(&(optHeaderEntries->optHeaderEntry[currentHeader].dataOrOffset));\n"
        "#pragma GCC diagnostic pop\n"
        "    currentHeader++;\n\n"
        "    // Execution ID (0x40006): stable identity for Aurora/homebrew assets.\n"
        "    optHeaderEntries->optHeaderEntry[currentHeader].id = XEX_OPT_ID_EXECUTION_ID;\n"
        "    setSpelunkrExecutionId(&(optHeaders->executionId));\n"
        "    currentHeader++;\n\n"
        "    return SUCCESS;\n",
    )

    replace_once(
        placer,
        "            case XEX_OPT_ID_TLS_INFO:\n"
        "                optHeaderEntries->optHeaderEntry[i].dataOrOffset = *currentOffset;\n"
        "                offsets->optHeaders[sepHeader] = *currentOffset;\n"
        "                *currentOffset += sizeof(struct tlsInfo);\n"
        "                sepHeader++;\n"
        "                break;\n",
        "            case XEX_OPT_ID_TLS_INFO:\n"
        "                optHeaderEntries->optHeaderEntry[i].dataOrOffset = *currentOffset;\n"
        "                offsets->optHeaders[sepHeader] = *currentOffset;\n"
        "                *currentOffset += sizeof(struct tlsInfo);\n"
        "                sepHeader++;\n"
        "                break;\n\n"
        "            case XEX_OPT_ID_EXECUTION_ID:\n"
        "                optHeaderEntries->optHeaderEntry[i].dataOrOffset = *currentOffset;\n"
        "                offsets->optHeaders[sepHeader] = *currentOffset;\n"
        "                *currentOffset += sizeof(struct executionId);\n"
        "                sepHeader++;\n"
        "                break;\n",
    )

    replace_once(
        writer,
        "    if(optHeaders->tlsInfo.slotCount != 0)\n"
        "    {\n"
        "        fseek(xex, offsets->optHeaders[currentHeader], SEEK_SET);\n\n"
        "#ifdef LITTLE_ENDIAN_SYSTEM\n"
        "        optHeaders->tlsInfo.slotCount = __builtin_bswap32(optHeaders->tlsInfo.slotCount);\n"
        "        optHeaders->tlsInfo.rawDataAddr = __builtin_bswap32(optHeaders->tlsInfo.rawDataAddr);\n"
        "        optHeaders->tlsInfo.dataSize = __builtin_bswap32(optHeaders->tlsInfo.dataSize);\n"
        "        optHeaders->tlsInfo.rawDataSize = __builtin_bswap32(optHeaders->tlsInfo.rawDataSize);\n"
        "#endif\n\n"
        "        fwrite(&(optHeaders->tlsInfo), sizeof(uint8_t), sizeof(struct tlsInfo), xex);\n"
        "    }\n\n"
        "    return SUCCESS;\n",
        "    if(optHeaders->tlsInfo.slotCount != 0)\n"
        "    {\n"
        "        fseek(xex, offsets->optHeaders[currentHeader], SEEK_SET);\n\n"
        "#ifdef LITTLE_ENDIAN_SYSTEM\n"
        "        optHeaders->tlsInfo.slotCount = __builtin_bswap32(optHeaders->tlsInfo.slotCount);\n"
        "        optHeaders->tlsInfo.rawDataAddr = __builtin_bswap32(optHeaders->tlsInfo.rawDataAddr);\n"
        "        optHeaders->tlsInfo.dataSize = __builtin_bswap32(optHeaders->tlsInfo.dataSize);\n"
        "        optHeaders->tlsInfo.rawDataSize = __builtin_bswap32(optHeaders->tlsInfo.rawDataSize);\n"
        "#endif\n\n"
        "        fwrite(&(optHeaders->tlsInfo), sizeof(uint8_t), sizeof(struct tlsInfo), xex);\n"
        "        currentHeader++;\n"
        "    }\n\n"
        "    fseek(xex, offsets->optHeaders[currentHeader], SEEK_SET);\n"
        "#ifdef LITTLE_ENDIAN_SYSTEM\n"
        "    optHeaders->executionId.mediaId = __builtin_bswap32(optHeaders->executionId.mediaId);\n"
        "    optHeaders->executionId.version = __builtin_bswap32(optHeaders->executionId.version);\n"
        "    optHeaders->executionId.baseVersion = __builtin_bswap32(optHeaders->executionId.baseVersion);\n"
        "    optHeaders->executionId.titleId = __builtin_bswap32(optHeaders->executionId.titleId);\n"
        "    optHeaders->executionId.savegameId = __builtin_bswap32(optHeaders->executionId.savegameId);\n"
        "#endif\n"
        "    fwrite(&(optHeaders->executionId), sizeof(uint8_t), sizeof(struct executionId), xex);\n\n"
        "    return SUCCESS;\n",
    )

    print(f"Spelunkr360 SynthXEX Execution ID enabled: TitleID {TITLE_ID:08X}")


if __name__ == "__main__":
    main()
