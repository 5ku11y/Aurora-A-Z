#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7b1.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7B.1 hardware fix:
# - the 256 KiB remote cache caused a multi-second Archive range refill after
#   only a handful of displayed frames;
# - the wall clock kept advancing during that blocking refill, so V7B then
#   discarded hundreds of valid frames as late;
# - decoded_frames also counted seek preroll, which could hit the safety cap
#   before ten seconds of post-target playback had been displayed.
old_cache = '#define REMOTE_CACHE_BYTES (256u * 1024u)'
new_cache = '#define REMOTE_CACHE_BYTES (4u * 1024u * 1024u)'
if old_cache not in src:
    raise SystemExit('V7B.1 remote cache marker missing')
src = src.replace(old_cache, new_cache, 1)

src = src.replace('SPELUNKR360 V7B - CONTINUOUS VIDEO PROBE',
                  'SPELUNKR360 V7B.1 - CONTINUOUS VIDEO PROBE')
src = src.replace('SPELUNKR360 V7B - CONTINUOUS VIDEO PLAYBACK',
                  'SPELUNKR360 V7B.1 - CONTINUOUS VIDEO PLAYBACK')
src = src.replace('V7B - B/BACK/START RETURNS TO AURORA',
                  'V7B.1 - B/BACK/START RETURNS TO AURORA')

old_count = '''            decoded_frames++;
            if (ts != AV_NOPTS_VALUE)
                actual_ms = av_rescale_q(ts - start_ts, stream->time_base, (AVRational){ 1, 1000 });
            if (actual_ms < 0) actual_ms = 0;
            if (actual_ms + 250 < target_ms) {
                av_frame_unref(frame);
                continue;
            }
'''
new_count = '''            if (ts != AV_NOPTS_VALUE)
                actual_ms = av_rescale_q(ts - start_ts, stream->time_base, (AVRational){ 1, 1000 });
            if (actual_ms < 0) actual_ms = 0;
            if (actual_ms + 250 < target_ms) {
                av_frame_unref(frame);
                continue;
            }
            /* Count only post-target frames; seek preroll must not consume the playback cap. */
            decoded_frames++;
'''
if old_count not in src:
    raise SystemExit('V7B.1 decoded-frame counter marker missing')
src = src.replace(old_count, new_count, 1)

old_drop = '''            elapsed_ms = v7b_wall_ms() - wall_start_ms;
            late_ms = elapsed_ms - desired_ms;
            if (late_ms > 250 && rendered_frames > 0) {
                dropped_frames++;
                free(picture.argb);
                picture.argb = NULL;
                av_frame_unref(frame);
                if (desired_ms >= V7B_PLAY_MS) goto stopped;
                continue;
            }
'''
new_drop = '''            elapsed_ms = v7b_wall_ms() - wall_start_ms;
            late_ms = elapsed_ms - desired_ms;
            if (late_ms > 750 && rendered_frames > 0) {
                /* A blocking range refill can pause decoding for seconds. Rebase the
                 * presentation clock once instead of purging hundreds of decoded frames. */
                wall_start_ms = v7b_wall_ms() - desired_ms;
                elapsed_ms = desired_ms;
                late_ms = 0;
                dropped_frames++;
            }
'''
if old_drop not in src:
    raise SystemExit('V7B.1 late-frame block marker missing')
src = src.replace(old_drop, new_drop, 1)

for needle in (
    'SPELUNKR360 V7B.1 - CONTINUOUS VIDEO PROBE',
    '#define REMOTE_CACHE_BYTES (4u * 1024u * 1024u)',
    'seek preroll must not consume the playback cap',
    'Rebase the',
):
    if needle not in src:
        raise SystemExit(f'V7B.1 marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7B.1 4 MiB media cache and stall-safe pacing")
