#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7j.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7J hardware follow-up:
# V7I proved true continuous playback. Real hardware then showed a distinctive
# long-run pattern: ~30 seconds clean, progressively larger 0.5-5 second stalls,
# then an approximately 20-second stall before playback recovered and repeated.
# V7E explicitly gives the background range request a 20-second low-speed
# watchdog, and V7F already knows how to salvage any contiguous partial HTTP 206
# payload after CURLE_OPERATION_TIMEDOUT. So preserve the proven V7I decoder,
# audio clock, progressive staging and dedicated worker, but:
#   1) double the async range runway from 4 MiB to 8 MiB;
#   2) roll a stalled background range after 2 seconds instead of 20;
#   3) cap a synchronous fallback's dead-range wait at 3 seconds.
# This attacks the observed buffer-drain / watchdog cycle without replacing the
# transport architecture that is already stable on real Xbox 360 hardware.

src = src.replace('SPELUNKR360 V7I - TRUE CONTINUOUS PLAYBACK',
                  'SPELUNKR360 V7J - FAST-ROLLOVER CONTINUOUS PLAYBACK')
src = src.replace('V7I - B/BACK/START RETURNS TO AURORA',
                  'V7J - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7I continuous playback ended before stability gate',
                  'V7J continuous playback ended before stability gate')
src = src.replace('Spelunkr360 V7I PASS:', 'Spelunkr360 V7J PASS:')
src = src.replace('V7I async partial salvaged', 'V7J async partial salvaged')
src = src.replace('V7I foreground partial salvaged', 'V7J foreground partial salvaged')
src = src.replace('V7I prefetch thread: creator_ht=', 'V7J prefetch thread: creator_ht=')

# More producer runway. V7E reallocates prefetch_cache to range_chunk, while the
# foreground cache remains the proven 16 MiB allocation from V7B.2.
old_range = 'remote.range_chunk = 4u * 1024u * 1024u;'
new_range = 'remote.range_chunk = 8u * 1024u * 1024u;'
if old_range not in src:
    raise SystemExit('V7J range-depth assignment missing')
src = src.replace(old_range, new_range, 1)
src = src.replace('16 MB CACHE / 4 MB RANGE FILLS.',
                  '16 MB CACHE / 8 MB ASYNC PREFETCH.', 1)

# The ~20 second hardware freeze matches this exact V7E watchdog. V7F already
# accepts CURLE_OPERATION_TIMEDOUT + partial HTTP 206 bytes, so a 2-second
# rollover can keep useful bytes and immediately advance the next request.
old_bg_watchdog = 'curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 20L);'
new_bg_watchdog = 'curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 2L);'
if old_bg_watchdog not in src:
    raise SystemExit('V7J background low-speed watchdog marker missing')
src = src.replace(old_bg_watchdog, new_bg_watchdog, 1)

# Synchronous fallback must not reintroduce the old 15-second common-curl stall.
# Match remote_fill's reset sequence so remote_open / metadata requests retain
# their existing conservative timeout behavior.
old_fg = '''    curl_easy_reset(remote->curl);
    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_RANGE, range);'''
new_fg = '''    curl_easy_reset(remote->curl);
    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_LOW_SPEED_TIME, 3L);
    curl_easy_setopt(remote->curl, CURLOPT_RANGE, range);'''
if old_fg not in src:
    raise SystemExit('V7J foreground fallback watchdog marker missing')
src = src.replace(old_fg, new_fg, 1)

# Add a visible marker to make it impossible to confuse this XEX with V7I.
src = src.replace('| RANGE HTTP %ld | CONTINUOUS\\n',
                  '| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s ROLLOVER\\n', 1)

for needle in (
    'SPELUNKR360 V7J - FAST-ROLLOVER CONTINUOUS PLAYBACK',
    'remote.range_chunk = 8u * 1024u * 1024u',
    'CURLOPT_LOW_SPEED_TIME, 2L',
    'CURLOPT_LOW_SPEED_TIME, 3L',
    'PF 8MB / 2s ROLLOVER',
    'V7J continuous playback ended before stability gate',
):
    if needle not in src:
        raise SystemExit(f'V7J marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7J 8 MiB prefetch runway and fast stalled-range rollover")
