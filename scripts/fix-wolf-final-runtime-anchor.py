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
old_worker_call = (
    'runtime = replace_once(\n'
    '    runtime, old_worker, new_worker, "dashboard-gated idle worker"\n'
    ')'
)
new_worker_call = '''worker_start = runtime.find('        if (wolf_idle_timer_step(\\n')
worker_end = runtime.find('        flush_input_telemetry(0u);', worker_start)
if worker_start < 0 or worker_end < 0:
    raise SystemExit("Wolf FINAL idle-key anchor missing: dashboard worker range")
# V8F/V8G inserted their old native-scene arming code inside this range.
# Replace the entire legacy idle-trigger section so the FINAL build cannot
# create/navigate any of those old probe scenes.
runtime = runtime[:worker_start] + new_worker + runtime[worker_end:]
'''

for old, new, label in (
    (old_anchor, new_anchor, "runtime struct anchor"),
    (old_replacement_tail, new_replacement_tail, "runtime struct replacement"),
    (old_worker_call, new_worker_call, "worker range replacement"),
):
    if old not in text:
        raise SystemExit(f"Wolf FINAL fixer: {label} missing")
    text = text.replace(old, new, 1)

path.write_text(text)
print("Wolf FINAL runtime anchors corrected")
