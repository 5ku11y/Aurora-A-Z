#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7b2.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7B.2 moves the expensive Archive.org refill to startup instead of allowing
# the 4 MiB streaming window to run dry halfway through the 10-second proof.
# The existing remote cache is grown (when needed) to 16 MiB and subsequent
# range fills use that entire playback window.

old_define = '#define V7B_MAX_DECODED_FRAMES 1800u'
new_define = '#define V7B_MAX_DECODED_FRAMES 1800u\n#define V7B2_PREFETCH_BYTES (16u * 1024u * 1024u)'
if old_define not in src:
    raise SystemExit('V7B.2 define marker missing')
src = src.replace(old_define, new_define, 1)

src = src.replace('SPELUNKR360 V7B.1 - CONTINUOUS VIDEO PROBE',
                  'SPELUNKR360 V7B.2 - BUFFERED VIDEO PROBE')
src = src.replace('SPELUNKR360 V7B.1 - CONTINUOUS VIDEO PLAYBACK',
                  'SPELUNKR360 V7B.2 - BUFFERED VIDEO PLAYBACK')
src = src.replace('V7B.1 - B/BACK/START RETURNS TO AURORA',
                  'V7B.2 - B/BACK/START RETURNS TO AURORA')
src = src.replace('10+ SECONDS OF LIVE H.264 VIDEO RENDERED',
                  '10+ SECONDS BUFFERED H.264 VIDEO RENDERED')

old_seek = '''    start_ts = stream->start_time == AV_NOPTS_VALUE ? 0 : stream->start_time;
    target_ts = start_ts + av_rescale_q(target_ms, (AVRational){ 1, 1000 }, stream->time_base);
    result = av_seek_frame(format, video_index, target_ts, AVSEEK_FLAG_BACKWARD);
'''
new_seek = '''    start_ts = stream->start_time == AV_NOPTS_VALUE ? 0 : stream->start_time;
    target_ts = start_ts + av_rescale_q(target_ms, (AVRational){ 1, 1000 }, stream->time_base);
    {
        size_t prefetch = V7B2_PREFETCH_BYTES;
        if (remote.size > 0 && remote.size < (int64_t)prefetch)
            prefetch = (size_t)remote.size;
        if (remote.cache_capacity < prefetch) {
            uint8_t *grown = realloc(remote.cache, prefetch);
            if (grown == NULL) {
                snprintf(error, error_size, "V7B.2 16 MB playback cache allocation failed");
                goto fail;
            }
            remote.cache = grown;
            remote.cache_capacity = prefetch;
        }
        remote.range_chunk = prefetch;
        v7_stage("V7B.2: PREBUFFERING LIVE VIDEO...\\nUP TO 16 MB BEFORE PLAYBACK.\\nNETWORK WAIT IS MOVED TO STARTUP.");
    }
    result = av_seek_frame(format, video_index, target_ts, AVSEEK_FLAG_BACKWARD);
'''
if old_seek not in src:
    raise SystemExit('V7B.2 seek marker missing')
src = src.replace(old_seek, new_seek, 1)

# Add the playback-window size to the live overlay so hardware photos prove
# the intended buffered build is running.
old_overlay = '"LIVE TARGET %s | CURRENT %s | FRAME %u | DROP %u | H.264 VIDEO ONLY\\n"'
new_overlay = '"LIVE TARGET %s | CURRENT %s | FRAME %u | DROP %u | 16MB BUFFER | H.264\\n"'
if old_overlay not in src:
    raise SystemExit('V7B.2 overlay marker missing')
src = src.replace(old_overlay, new_overlay, 1)

for needle in (
    'SPELUNKR360 V7B.2 - BUFFERED VIDEO PROBE',
    'SPELUNKR360 V7B.2 - BUFFERED VIDEO PLAYBACK',
    '#define V7B2_PREFETCH_BYTES (16u * 1024u * 1024u)',
    'V7B.2: PREBUFFERING LIVE VIDEO',
    'remote.range_chunk = prefetch',
    '16MB BUFFER',
):
    if needle not in src:
        raise SystemExit(f'V7B.2 marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7B.2 16 MiB prebuffered playback window")
