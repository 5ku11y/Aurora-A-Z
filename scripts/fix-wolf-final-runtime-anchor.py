#!/usr/bin/env python3
from pathlib import Path

path = Path("scripts/apply-wolf-final-idle-key.py")
text = path.read_text()
old_anchor = (
    "    '    WolfIdleTimer wolf_idle_timer;\\n'\n"
    "    '} AzRev1655Runtime;',"
)
new_anchor = "    '    WolfIdleTimer wolf_idle_timer;\\n',"
old_replacement_tail = (
    "    '    uint32_t wolf_final_last_cancelled;\\n'\n"
    "    '} AzRev1655Runtime;',\n"
    "    \"runtime final idle state\","
)
new_replacement_tail = (
    "    '    uint32_t wolf_final_last_cancelled;\\n',\n"
    "    \"runtime final idle state\","
)
if old_anchor not in text:
    raise SystemExit("Wolf FINAL fixer: old runtime anchor missing")
if old_replacement_tail not in text:
    raise SystemExit("Wolf FINAL fixer: replacement tail missing")
text = text.replace(old_anchor, new_anchor, 1)
text = text.replace(old_replacement_tail, new_replacement_tail, 1)
path.write_text(text)
print("Wolf FINAL runtime struct anchor corrected")
