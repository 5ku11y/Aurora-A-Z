#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7m.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7M hardware follow-up after V7L:
# - V7L's real loader appeared, but an old V7A success/status page immediately
#   overwrote it with NOW PLAYING / TARGET POSITION / ARCHIVE ID while the slow
#   media-open path was still running.
# - keep the Wolf Factory loader in control from launch until first video frame.
# - bypass avformat_find_stream_info(). We force the MOV demuxer and MOV creates
#   its stream/codecpar entries while parsing the MP4 track table during open;
#   the generic discovery scan is redundant here and can trigger extra blocking
#   custom-AVIO range reads on Xbox 360.
# - preserve V7J/V7L's proven decoder/audio/8 MiB playback prefetch path.

src = src.replace(
    'SPELUNKR360 V7L - DEMAND OPEN + REAL LOADER',
    'SPELUNKR360 V7M - PERSISTENT LOADER + FAST TRACK OPEN'
)
src = src.replace('V7L - B/BACK/START RETURNS TO AURORA',
                  'V7M - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7L continuous playback ended before stability gate',
                  'V7M continuous playback ended before stability gate')
src = src.replace('Spelunkr360 V7L PASS:', 'Spelunkr360 V7M PASS:')
src = src.replace('V7L async partial salvaged', 'V7M async partial salvaged')
src = src.replace('V7L foreground partial salvaged', 'V7M foreground partial salvaged')
src = src.replace('V7L prefetch thread: creator_ht=', 'V7M prefetch thread: creator_ht=')

# Remove the old main() diagnostic/status page that V7L hardware showed after
# roughly three seconds. Locate the target-position format string and delete the
# whole status block up to the real decode_picture() call. V7L already sets the
# loader dimensions near the beginning of main(), so any duplicate stage-width
# assignments inside this legacy block are no longer needed.
status_key = '"NOW PLAYING: %s\\nTARGET POSITION: %s\\nARCHIVE ID: %s\\n\\n"'
key_at = src.find(status_key)
if key_at < 0:
    raise SystemExit('V7M legacy target-position text marker missing')
status_begin = src.rfind('    snprintf(status_text, sizeof(status_text),', 0, key_at)
decode_call = src.find('    if (decode_picture(', key_at)
if status_begin < 0 or decode_call <= status_begin:
    raise SystemExit('V7M legacy status-page boundaries missing')
src = (src[:status_begin] +
       '    v7_stage("PROGRAM LOCATED - OPENING LIVE VIDEO...");\n\n' +
       src[decode_call:])

# The MOV demuxer is already forced. The generic stream-info scan is therefore
# unnecessary for this known H.264/AAC MP4 path and may perform several extra
# synchronous AVIO reads before av_find_best_stream. Skip only that scan; leave
# all stream selection, decoder creation, live seek, audio setup and playback
# logic untouched.
scan_begin = src.find('    v7_stage("READING STREAM INFORMATION...");\n    result = avformat_find_stream_info(format, NULL);')
video_find = src.find('    video_index = av_find_best_stream(format, AVMEDIA_TYPE_VIDEO', scan_begin)
if scan_begin < 0 or video_find <= scan_begin:
    raise SystemExit('V7M stream-info scan boundaries missing')
scan_replacement = '''    v7_stage("READING MP4 TRACK TABLE...");
    xsdk_log_write("V7M fast track open: avformat_find_stream_info bypassed");
'''
src = src[:scan_begin] + scan_replacement + src[video_find:]

# Make the new stage map display a meaningful percentage instead of falling
# back to the generic 10% value.
percent_marker = '    if (strstr(stage, "READING STREAM INFORMATION") != NULL) return 62;\n'
if percent_marker not in src:
    raise SystemExit('V7M loader percentage marker missing')
src = src.replace(
    percent_marker,
    percent_marker + '    if (strstr(stage, "READING MP4 TRACK TABLE") != NULL) return 62;\n'
    '    if (strstr(stage, "PROGRAM LOCATED - OPENING LIVE VIDEO") != NULL) return 28;\n',
    1
)

# Hardware-visible proof marker in the playback overlay.
src = src.replace('| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7L DEMAND OPEN\\n',
                  '| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7M FAST TRACK\\n', 1)

for needle in (
    'SPELUNKR360 V7M - PERSISTENT LOADER + FAST TRACK OPEN',
    'PROGRAM LOCATED - OPENING LIVE VIDEO',
    'READING MP4 TRACK TABLE',
    'V7M fast track open: avformat_find_stream_info bypassed',
    'V7M FAST TRACK',
    '4 MB DEMAND OPEN / 8 MB ASYNC PLAYBACK',
):
    if needle not in src:
        raise SystemExit(f'V7M marker missing: {needle}')

# Ensure the old viewer-facing target-position loading page is actually gone.
if '"NOW PLAYING: %s\\nTARGET POSITION: %s\\nARCHIVE ID: %s\\n\\n"' in src:
    raise SystemExit('V7M legacy target-position loading page survived')

out.write_text(src)
print(f"generated {out} with V7M persistent loader and fast MOV track open")
