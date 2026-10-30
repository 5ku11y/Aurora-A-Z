#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7g.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7G hardware follow-up:
# V7F survived the full 60-second media span with HTTP 206, zero video drops,
# and low A/V drift, but hardware reported thousands of xsdk silent audio
# callbacks. The V7F counters showed one async prefetch hit AND one wait, with
# no timeout/fallback/partial recovery. xsdk pthreads start on their creator's
# hardware thread, so give the Archive prefetch worker another physical core
# and +1 priority rather than weakening the underrun gate.

if '#include "xsdk/thread.h"' not in src:
    if '#include <pthread.h>\n' not in src:
        raise SystemExit('V7G pthread include marker missing')
    src = src.replace('#include <pthread.h>\n', '#include <pthread.h>\n#include "xsdk/thread.h"\n', 1)

src = src.replace('SPELUNKR360 V7F - TIMEOUT-RESILIENT PREFETCH + STABILITY',
                  'SPELUNKR360 V7G - DEDICATED PREFETCH THREAD + STABILITY')
src = src.replace('SPELUNKR360 V7F - TIMEOUT-RESILIENT PREFETCH PLAYBACK',
                  'SPELUNKR360 V7G - DEDICATED PREFETCH THREAD PLAYBACK')
src = src.replace('V7F - B/BACK/START RETURNS TO AURORA',
                  'V7G - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7F soak failed', 'V7G soak failed')
src = src.replace('Spelunkr360 V7F PASS:', 'Spelunkr360 V7G PASS:')
src = src.replace('V7F async partial salvaged', 'V7G async partial salvaged')
src = src.replace('V7F foreground partial salvaged', 'V7G foreground partial salvaged')

old_fields = '''    unsigned prefetch_partials;
    unsigned foreground_partials;
    char prefetch_error[128];'''
new_fields = '''    unsigned prefetch_partials;
    unsigned foreground_partials;
    uint32_t prefetch_hw_thread;
    NTSTATUS prefetch_place_status;
    NTSTATUS prefetch_priority_status;
    char prefetch_error[128];'''
if old_fields not in src:
    raise SystemExit('V7G scheduling field marker missing')
src = src.replace(old_fields, new_fields, 1)

old_create = '''    if (pthread_create(&remote->prefetch_thread, NULL, v7e_prefetch_worker, remote) != 0) {
        remote->prefetch_active = false;
        remote->prefetch_done = true;
        return -1;
    }
    return 0;'''
new_create = '''    if (pthread_create(&remote->prefetch_thread, NULL, v7e_prefetch_worker, remote) != 0) {
        remote->prefetch_active = false;
        remote->prefetch_done = true;
        return -1;
    }
    {
        HANDLE worker = xsdk_pthread_handle(remote->prefetch_thread);
        const uint32_t creator_hw = xsdk_thread_hardware_thread();
        const uint32_t target_hw = (creator_hw + 2u) % XSDK_HARDWARE_THREADS;
        remote->prefetch_hw_thread = target_hw;
        remote->prefetch_place_status = xsdk_thread_place(worker, target_hw);
        remote->prefetch_priority_status = xsdk_thread_set_priority(worker, 1, NULL);
        xsdk_log_write("V7G prefetch thread: creator_ht=%u worker_ht=%u place=0x%08X prio=0x%08X",
            (unsigned)creator_hw, (unsigned)target_hw,
            (unsigned)remote->prefetch_place_status,
            (unsigned)remote->prefetch_priority_status);
    }
    return 0;'''
if old_create not in src:
    raise SystemExit('V7G pthread-create marker missing')
src = src.replace(old_create, new_create, 1)

old_overlay = '                    "PF HIT %u WAIT %u FALL %u PART %u | FG PART %u\\n"\n'
new_overlay = '                    "PF H%u W%u F%u P%u | FG P%u | HT%u\\n"\n'
if old_overlay not in src:
    raise SystemExit('V7G overlay format marker missing')
src = src.replace(old_overlay, new_overlay, 1)

old_overlay_args = '''                    remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
                    remote.prefetch_partials, remote.foreground_partials);'''
new_overlay_args = '''                    remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
                    remote.prefetch_partials, remote.foreground_partials, remote.prefetch_hw_thread);'''
if old_overlay_args not in src:
    raise SystemExit('V7G overlay args marker missing')
src = src.replace(old_overlay_args, new_overlay_args, 1)

old_fail_format = '            "SYNCMAX %" PRId64 "ms HTTP %ld\\nPF H%u W%u F%u P%u | FG P%u",'
new_fail_format = '            "SYNCMAX %" PRId64 "ms HTTP %ld\\nPF H%u W%u F%u P%u | FG P%u | HT%u",'
if old_fail_format not in src:
    raise SystemExit('V7G fail format marker missing')
src = src.replace(old_fail_format, new_fail_format, 1)

old_fail_args = '''            remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
            remote.prefetch_partials, remote.foreground_partials);'''
new_fail_args = '''            remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
            remote.prefetch_partials, remote.foreground_partials, remote.prefetch_hw_thread);'''
if old_fail_args not in src:
    raise SystemExit('V7G fail args marker missing')
src = src.replace(old_fail_args, new_fail_args, 1)

for needle in (
    'SPELUNKR360 V7G - DEDICATED PREFETCH THREAD + STABILITY',
    'SPELUNKR360 V7G - DEDICATED PREFETCH THREAD PLAYBACK',
    '#include "xsdk/thread.h"',
    'xsdk_pthread_handle(remote->prefetch_thread)',
    'xsdk_thread_place(worker, target_hw)',
    'xsdk_thread_set_priority(worker, 1, NULL)',
    'V7G prefetch thread: creator_ht=',
    'PF H%u W%u F%u P%u | FG P%u | HT%u',
    'V7G soak failed',
):
    if needle not in src:
        raise SystemExit(f'V7G marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7G dedicated-core +1-priority Archive prefetch scheduling")
