#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7m.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7M hardware follow-up after V7L:
# - V7L's real loader appeared, but the legacy V7A main() status page then
#   overwrote it with NOW PLAYING / TARGET POSITION / ARCHIVE ID.
# - keep the Wolf Factory loader in control until the continuous player renders
#   the first actual video frame.
# - bypass avformat_find_stream_info() only inside play_video_continuous(). The
#   MOV demuxer is forced and populates MP4 track codecpar during open; the
#   generic discovery scan can cause extra blocking custom-AVIO range reads.
# - preserve V7J/V7L decoder, AAC, live-seek and 8 MiB playback prefetch logic.

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

# Scope the viewer-facing fix explicitly to main(). Do not delete the legacy
# snprintf itself: keeping it avoids turning old diagnostic variables into
# -Werror unused-variable failures. We simply prevent that text buffer from ever
# being presented and draw the branded loader instead.
status_key = '"NOW PLAYING: %s\\nTARGET POSITION: %s\\nARCHIVE ID: %s\\n\\n"'
main_at = src.find('int main(void)')
if main_at < 0:
    raise SystemExit('V7M main marker missing')
key_at = src.find(status_key, main_at)
if key_at < 0:
    raise SystemExit('V7M main target-position text marker missing')
play_call = src.find('play_video_continuous(', key_at)
if play_call < 0:
    raise SystemExit('V7M main continuous-player handoff missing')
present_token = '(void)present_status(width, height, status_text, GOOD_ARGB);'
present_at = src.find(present_token, key_at, play_call)
if present_at < 0:
    raise SystemExit('V7M legacy main status presenter missing')
src = (src[:present_at] +
       'v7_stage("PROGRAM LOCATED - OPENING LIVE VIDEO...");' +
       src[present_at + len(present_token):])

# Scope the startup experiment explicitly to the hardware-proven continuous
# playback function. The older unused decode_picture() helper is intentionally
# left alone; it is not the path Wolf is running on hardware.
play_def = src.find('static int play_video_continuous(')
main_at = src.find('int main(void)', play_def)
if play_def < 0 or main_at <= play_def:
    raise SystemExit('V7M continuous-player function boundaries missing')
scan_at = src.find('avformat_find_stream_info(format, NULL)', play_def, main_at)
video_at = src.find('video_index = av_find_best_stream', scan_at, main_at)
if scan_at < 0 or video_at <= scan_at:
    raise SystemExit('V7M continuous stream-info boundaries missing')
scan_stage_at = src.rfind('v7_stage(', play_def, scan_at)
scan_begin = src.rfind('\n', play_def, scan_stage_at if scan_stage_at >= 0 else scan_at) + 1
video_line = src.rfind('\n', scan_at, video_at) + 1
if video_line <= scan_begin:
    raise SystemExit('V7M continuous stream-info line boundaries missing')
scan_replacement = '''    v7_stage("READING MP4 TRACK TABLE...");
    xsdk_log_write("V7M fast track open: avformat_find_stream_info bypassed");
'''
src = src[:scan_begin] + scan_replacement + src[video_line:]

# Give the new loader stages meaningful progress values.
percent_marker = '    if (strstr(stage, "READING STREAM INFORMATION") != NULL) return 62;\n'
if percent_marker not in src:
    raise SystemExit('V7M loader percentage marker missing')
src = src.replace(
    percent_marker,
    percent_marker +
    '    if (strstr(stage, "READING MP4 TRACK TABLE") != NULL) return 62;\n'
    '    if (strstr(stage, "PROGRAM LOCATED - OPENING LIVE VIDEO") != NULL) return 28;\n',
    1
)

# Hardware-visible proof marker once playback starts.
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

# Verify the actual paths, not obsolete helper copies.
play_def = src.find('static int play_video_continuous(')
main_at = src.find('int main(void)', play_def)
play_slice = src[play_def:main_at]
main_slice = src[main_at:]
if 'avformat_find_stream_info(format, NULL)' in play_slice:
    raise SystemExit('V7M generic stream-info scan survived in continuous player')
main_key = main_slice.find(status_key)
main_play = main_slice.find('play_video_continuous(', main_key)
if main_key < 0 or main_play < 0:
    raise SystemExit('V7M main verification boundaries missing')
if present_token in main_slice[main_key:main_play]:
    raise SystemExit('V7M legacy target-position page is still presented')

out.write_text(src)
print(f"generated {out} with V7M persistent loader and fast MOV track open")
