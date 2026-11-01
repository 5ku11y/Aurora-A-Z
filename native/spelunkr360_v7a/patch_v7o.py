#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7o.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7O startup follow-up after Wolf's V7N hardware observation:
# - V7N spends most of its visible startup around 20-26%, which corresponds to
#   remote_open() doing the first Archive.org media range request.
# - V7B.1 globally enlarged REMOTE_CACHE_BYTES to 4 MiB for playback stability,
#   so remote_open() also inherited a full 4 MiB first request even though it
#   only needs enough bytes to bootstrap MP4 open and obtain Content-Range size.
# - keep the proven 4 MiB demand window and 8 MiB async playback depth, but make
#   the first request a 1 MiB bootstrap. If MOV needs more, normal demand IO can
#   still fetch the proven 4 MiB ranges immediately afterward.
# - add explicit loader stages around the bootstrap so hardware timing tells us
#   whether Archive connection/header transfer or later MOV/seek work dominates.

src = src.replace(
    'SPELUNKR360 V7N - SPELUNKR TV TIMED LOADER + FAST OPEN',
    'SPELUNKR360 V7O - 1MB BOOTSTRAP + TIMED SPELUNKR TV'
)
src = src.replace('V7N - B/BACK/START RETURNS TO AURORA',
                  'V7O - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7N continuous playback ended before stability gate',
                  'V7O continuous playback ended before stability gate')
src = src.replace('Spelunkr360 V7N PASS:', 'Spelunkr360 V7O PASS:')
src = src.replace('V7N async partial salvaged', 'V7O async partial salvaged')
src = src.replace('V7N foreground partial salvaged', 'V7O foreground partial salvaged')
src = src.replace('V7N prefetch thread: creator_ht=', 'V7O prefetch thread: creator_ht=')
src = src.replace('V7N fast track open: avformat_find_stream_info bypassed',
                  'V7O fast track open: avformat_find_stream_info bypassed')

# Give the new bootstrap stages their own visible percentages. These sit inside
# the old 20-30% band that Wolf identified as the long wait.
percent_anchor = '    if (strstr(stage, "PROGRAM LOCATED") != NULL) return 22;\n'
if percent_anchor not in src:
    raise SystemExit('V7O V7N stage-percent anchor missing')
src = src.replace(
    percent_anchor,
    percent_anchor +
    '    if (strstr(stage, "OPENING ARCHIVE MEDIA") != NULL) return 24;\n'
    '    if (strstr(stage, "MEDIA HEADER READY") != NULL) return 31;\n',
    1
)

# Limit only remote_open()'s first range. The backing cache remains 4 MiB, so
# later reads retain the hardware-proven demand window without realloc churn.
remote_begin = src.find('static int remote_open(struct remote_file *remote, const char *url)')
remote_end = src.find('\nstatic void remote_close(', remote_begin)
if remote_begin < 0 or remote_end <= remote_begin:
    raise SystemExit('V7O remote_open boundaries missing')
block = src[remote_begin:remote_end]

range_line = '    snprintf(range, sizeof(range), "0-%u", (unsigned)(remote->cache_capacity - 1u));\n'
if range_line not in block:
    raise SystemExit('V7O initial range marker missing')
block = block.replace(
    range_line,
    '    {\n'
    '        const size_t bootstrap_limit = 1u * 1024u * 1024u;\n'
    '        const size_t bootstrap_bytes = remote->cache_capacity < bootstrap_limit\n'
    '            ? remote->cache_capacity : bootstrap_limit;\n'
    '        snprintf(range, sizeof(range), "0-%u", (unsigned)(bootstrap_bytes - 1u));\n'
    '    }\n'
    '    v7_stage("OPENING ARCHIVE MEDIA - 1 MB BOOTSTRAP...");\n',
    1
)

# Advance the loader immediately before remote_open()'s final successful return.
# Later V7 patches added bookkeeping around the old cache_start/position lines,
# so key off the function's last indented success return instead of adjacency.
success_return = '    return 0;\n'
return_at = block.rfind(success_return)
if return_at < 0:
    raise SystemExit('V7O remote_open success return missing')
block = (block[:return_at] +
         '    v7_stage("MEDIA HEADER READY - OPENING MP4...");\n' +
         block[return_at:])

src = src[:remote_begin] + block + src[remote_end:]

# Update viewer-facing tuning details and playback proof marker.
src = src.replace(
    'FAST TRACK OPEN // 4 MB DEMAND IO // 8 MB ASYNC PLAYBACK BUFFER',
    '1 MB BOOTSTRAP // 4 MB DEMAND IO // 8 MB ASYNC PLAYBACK BUFFER',
    1
)
src = src.replace('| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7N SPELUNKR TV\\n',
                  '| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7O 1MB BOOT\\n', 1)

for needle in (
    'SPELUNKR360 V7O - 1MB BOOTSTRAP + TIMED SPELUNKR TV',
    'bootstrap_limit = 1u * 1024u * 1024u',
    'OPENING ARCHIVE MEDIA - 1 MB BOOTSTRAP',
    'MEDIA HEADER READY - OPENING MP4',
    '1 MB BOOTSTRAP // 4 MB DEMAND IO // 8 MB ASYNC PLAYBACK BUFFER',
    'V7O 1MB BOOT',
    'READING MP4 TRACK TABLE',
):
    if needle not in src:
        raise SystemExit(f'V7O marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7O 1 MiB media bootstrap and granular Archive-open timing")
