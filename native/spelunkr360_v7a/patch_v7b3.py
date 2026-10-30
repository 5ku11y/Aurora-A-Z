#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7b3.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7B.3 hardware follow-up:
# - V7B.2 reached the playback loop but produced rendered=0/dropped=0/span=0ms.
# - keep the larger 16 MiB allocation, but return to 4 MiB network range fills;
#   the one-shot 16 MiB refill is too aggressive for the Xbox/Archive path.
# - clear AVIO EOF/error after a successful live seek.
# - if av_read_frame fails before frame 1, surface the real FFmpeg + remote I/O
#   failure instead of the generic "playback short" message.

src = src.replace('SPELUNKR360 V7B.2 - BUFFERED VIDEO PROBE',
                  'SPELUNKR360 V7B.3 - STREAM-SAFE VIDEO PROBE')
src = src.replace('SPELUNKR360 V7B.2 - BUFFERED VIDEO PLAYBACK',
                  'SPELUNKR360 V7B.3 - STREAM-SAFE VIDEO PLAYBACK')
src = src.replace('V7B.2 - B/BACK/START RETURNS TO AURORA',
                  'V7B.3 - B/BACK/START RETURNS TO AURORA')
src = src.replace('10+ SECONDS BUFFERED H.264 VIDEO RENDERED',
                  '10+ SECONDS STREAM-SAFE H.264 VIDEO RENDERED')

old_range = '        remote.range_chunk = prefetch;\n        v7_stage("V7B.2: PREBUFFERING LIVE VIDEO...\\nUP TO 16 MB BEFORE PLAYBACK.\\nNETWORK WAIT IS MOVED TO STARTUP.");'
new_range = '        remote.range_chunk = 4u * 1024u * 1024u;\n        v7_stage("V7B.3: PREPARING LIVE VIDEO...\\n16 MB CACHE / 4 MB RANGE FILLS.\\nSTREAMING CLOCK WILL RE-SYNC AFTER REFILLS.");'
if old_range not in src:
    raise SystemExit('V7B.3 V7B.2 prebuffer marker missing')
src = src.replace(old_range, new_range, 1)

old_seek_done = '''    result = av_seek_frame(format, video_index, target_ts, AVSEEK_FLAG_BACKWARD);\n    if (result < 0) {\n        ff_error_text(result, fferr, sizeof(fferr));\n        snprintf(error, error_size, "V7B media seek failed: %s", fferr);\n        goto fail;\n    }\n    avcodec_flush_buffers(decoder);\n'''
new_seek_done = '''    result = av_seek_frame(format, video_index, target_ts, AVSEEK_FLAG_BACKWARD);\n    if (result < 0) {\n        ff_error_text(result, fferr, sizeof(fferr));\n        snprintf(error, error_size, "V7B.3 media seek failed: %s remote=%.100s", fferr, remote.error);\n        goto fail;\n    }\n    /* A failed/short custom-AVIO probe during seek can leave EOF/error latched\n     * even when mov seek itself succeeds.  Reset them before the first packet. */\n    avio->eof_reached = 0;\n    avio->error = 0;\n    avcodec_flush_buffers(decoder);\n'''
if old_seek_done not in src:
    raise SystemExit('V7B.3 seek completion marker missing')
src = src.replace(old_seek_done, new_seek_done, 1)

old_stopped = '''stopped:\n    if (range_http != NULL) *range_http = remote.last_http;\n'''
new_stopped = '''    if (result < 0 && rendered_frames == 0 && !wants_exit()) {\n        ff_error_text(result, fferr, sizeof(fferr));\n        snprintf(error, error_size,\n            "V7B.3 read before frame: %s HTTP=%ld pos=%" PRId64\n            " cache=%" PRId64 "+%u remote=%.80s",\n            fferr, remote.last_http, remote.position, remote.cache_start,\n            (unsigned)remote.cache_length, remote.error);\n        goto fail;\n    }\n\nstopped:\n    if (range_http != NULL) *range_http = remote.last_http;\n'''
if old_stopped not in src:
    raise SystemExit('V7B.3 stopped marker missing')
src = src.replace(old_stopped, new_stopped, 1)

src = src.replace('| 16MB BUFFER | H.264', '| 16MB CACHE / 4MB IO | H.264')

for needle in (
    'SPELUNKR360 V7B.3 - STREAM-SAFE VIDEO PROBE',
    '16 MB CACHE / 4 MB RANGE FILLS',
    'avio->eof_reached = 0',
    'V7B.3 read before frame',
    '16MB CACHE / 4MB IO',
):
    if needle not in src:
        raise SystemExit(f'V7B.3 marker missing: {needle}')

# V7C replaces V7B's wall-clock pacing with an audio-master clock. Strip the
# two V7B timing helpers before the V7C transform so -Werror does not reject
# the generated source as unused code.
helper_start = src.find('static int64_t v7b_wall_ms(void)')
play_start = src.find('static int play_video_continuous(')
if helper_start >= 0 and play_start > helper_start:
    src = src[:helper_start] + src[play_start:]
else:
    raise SystemExit('V7C could not locate obsolete V7B timing helpers')

# Layer the hardware-proven playback stack through V7I, then V7J keeps true
# continuous playback while reusing the Archive HTTPS connection and doubling
# async range depth to reduce the rhythmic V7I boundary stalls.
out.write_text(src)
v7c = Path(__file__).with_name('patch_v7c.py')
v7d = Path(__file__).with_name('patch_v7d.py')
v7e = Path(__file__).with_name('patch_v7e.py')
v7f = Path(__file__).with_name('patch_v7f.py')
v7g = Path(__file__).with_name('patch_v7g.py')
v7h = Path(__file__).with_name('patch_v7h.py')
v7i = Path(__file__).with_name('patch_v7i.py')
v7j = Path(__file__).with_name('patch_v7j.py')
tmp_c = out.with_name(out.name + '.v7c')
tmp_d = out.with_name(out.name + '.v7d')
tmp_e = out.with_name(out.name + '.v7e')
tmp_f = out.with_name(out.name + '.v7f')
tmp_g = out.with_name(out.name + '.v7g')
tmp_h = out.with_name(out.name + '.v7h')
tmp_i = out.with_name(out.name + '.v7i')
tmp_j = out.with_name(out.name + '.v7j')
subprocess.run([sys.executable, str(v7c), str(out), str(tmp_c)], check=True)
subprocess.run([sys.executable, str(v7d), str(tmp_c), str(tmp_d)], check=True)
subprocess.run([sys.executable, str(v7e), str(tmp_d), str(tmp_e)], check=True)
subprocess.run([sys.executable, str(v7f), str(tmp_e), str(tmp_f)], check=True)
subprocess.run([sys.executable, str(v7g), str(tmp_f), str(tmp_g)], check=True)
subprocess.run([sys.executable, str(v7h), str(tmp_g), str(tmp_h)], check=True)
subprocess.run([sys.executable, str(v7i), str(tmp_h), str(tmp_i)], check=True)
subprocess.run([sys.executable, str(v7j), str(tmp_i), str(tmp_j)], check=True)
tmp_j.replace(out)
for tmp in (tmp_c, tmp_d, tmp_e, tmp_f, tmp_g, tmp_h, tmp_i):
    if tmp.exists():
        tmp.unlink()
print(f"generated {out} through V7J keepalive continuous playback")
