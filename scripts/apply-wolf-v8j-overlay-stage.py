#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Wolf V8J overlay-stage anchor missing: {label}")
    return text.replace(old, new, 1)


path = Path("native/src/netdbg_bootstrap.c")
text = path.read_text()

text = replace_once(
    text,
    "    result = az_rev1655_runtime_start(\n"
    "        AZ_REV1655_RUNTIME_STAGE_INPUT_OBSERVE);",
    "    /* V8J: V8H/V8I proved the idle worker arms correctly, but the\n"
    "     * bootstrap was still starting the input-only runtime stage.  The\n"
    "     * native scene dispatcher lives on the already-validated render\n"
    "     * detour, so start the full overlay-canary stage that installs the\n"
    "     * input/render/font/settings hooks under their existing revision\n"
    "     * gates. */\n"
    "    result = az_rev1655_runtime_start(\n"
    "        AZ_REV1655_RUNTIME_STAGE_OVERLAY_CANARY);",
    "bootstrap runtime stage",
)

path.write_text(text)
print("Wolf V8J overlay-canary bootstrap stage applied")
