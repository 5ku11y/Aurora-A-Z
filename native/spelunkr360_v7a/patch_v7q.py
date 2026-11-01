#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7q.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7Q hardware follow-up after V7P:
# Wolf reported severely chopped audio once playback began. V7P's guarded EOF
# recovery performed foreground range retries and 120/240/360 ms sleeps inside
# the same demux path that feeds AAC, which can starve the audio queue.
# Keep V7P's good monotonic loader behavior, but restore the hardware-proven
# V7J/V7N real-time AVIO + av_read_frame loop with no blocking recovery sleeps.

src = src.replace(
    'SPELUNKR360 V7P - MONOTONIC TUNING + EOF RECOVERY',
    'SPELUNKR360 V7Q - AUDIO SAFE + MONOTONIC TUNING'
)
src = src.replace('V7P - B/BACK/START RETURNS TO AURORA',
                  'V7Q - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7P continuous playback ended before stability gate',
                  'V7Q continuous playback ended before stability gate')
src = src.replace('Spelunkr360 V7P PASS:', 'Spelunkr360 V7Q PASS:')
src = src.replace('V7P async partial salvaged', 'V7Q async partial salvaged')
src = src.replace('V7P foreground partial salvaged', 'V7Q foreground partial salvaged')
src = src.replace('V7P prefetch thread: creator_ht=', 'V7Q prefetch thread: creator_ht=')
src = src.replace('V7P fast track open: avformat_find_stream_info bypassed',
                  'V7Q fast track open: avformat_find_stream_info bypassed')

# Restore avio_remote_read() to the non-blocking foreground behavior used by the
# hardware-proven playback core. Leave the V7P counter field harmlessly present
# so this rollback does not perturb struct layout more than necessary.
read_begin = src.find('static int avio_remote_read(void *opaque, uint8_t *buffer, int buffer_size)')
read_end = src.find('\nstatic int64_t avio_remote_seek(', read_begin)
if read_begin < 0 or read_end <= read_begin:
    raise SystemExit('V7Q avio_remote_read boundaries missing')
read_block = src[read_begin:read_end]
retry_begin = read_block.find('int fill_result = remote_fill(remote, remote->position);')
retry_return = read_block.find('return copied > 0 ? copied : AVERROR(EIO);', retry_begin)
if retry_begin < 0 or retry_return < 0:
    raise SystemExit('V7Q V7P foreground retry block missing')
line_start = read_block.rfind('\n', 0, retry_begin) + 1
line_end = read_block.find('\n', retry_return)
if line_end < 0:
    line_end = len(read_block)
else:
    line_end += 1
indent = read_block[line_start:retry_begin]
original_fill = (
    indent + 'if (remote_fill(remote, remote->position) != 0)\n' +
    indent + '    return copied > 0 ? copied : AVERROR(EIO);\n'
)
read_block = read_block[:line_start] + original_fill + read_block[line_end:]
src = src[:read_begin] + read_block + src[read_end:]

# Restore the original continuous av_read_frame loop so AAC feeding is never
# paused by V7P retry sleeps. A transient EOF may still terminate this test, but
# that is preferable to corrupting real-time audio; rollover/recovery will be
# moved outside the A/V loop in a later build.
play_begin = src.find('static int play_av_continuous(')
main_begin = src.find('\nint main(void)', play_begin)
if play_begin < 0 or main_begin <= play_begin:
    raise SystemExit('V7Q play_av_continuous boundaries missing')
play = src[play_begin:main_begin]
retry_open = '''    {
        unsigned v7p_read_retries = 0;
        while (!wants_exit()) {
            result = av_read_frame(format, packet);
            if (result < 0) {
                const bool before_remote_end = remote.size > 0 && remote.position >= 0 &&
                    remote.position < remote.size;
                if (before_remote_end && v7p_read_retries < 3u) {
                    v7p_read_retries++;
                    xsdk_log_write("V7P transient demux retry %u result=%d pos=%" PRId64 "/%" PRId64
                        " avio_eof=%d avio_err=%d remote=%.96s",
                        v7p_read_retries, result, remote.position, remote.size,
                        avio != NULL ? avio->eof_reached : -1,
                        avio != NULL ? avio->error : 0, remote.error);
                    if (avio != NULL) {
                        avio->eof_reached = 0;
                        avio->error = 0;
                    }
                    av_packet_unref(packet);
                    v7c_sleep_ms(120u * v7p_read_retries);
                    continue;
                }
                if (result == AVERROR_EOF)
                    xsdk_log_write("V7P EOF stop: pos=%" PRId64 "/%" PRId64 " true_end=%d retries=%u",
                        remote.position, remote.size,
                        (remote.size > 0 && remote.position >= remote.size) ? 1 : 0,
                        v7p_read_retries);
                break;
            }
            v7p_read_retries = 0;
            packets++;'''
original_open = '''    while (!wants_exit() && (result = av_read_frame(format, packet)) >= 0) {
        packets++;'''
if retry_open not in play:
    raise SystemExit('V7Q V7P demux retry loop missing')
play = play.replace(retry_open, original_open, 1)
cleanup = '    if (range_http != NULL) *range_http = remote.last_http;\n'
cleanup_at = play.rfind(cleanup)
if cleanup_at < 0:
    raise SystemExit('V7Q cleanup marker missing')
# V7P added one extra scope-closing brace immediately before cleanup.
prefix = play[:cleanup_at]
if not prefix.endswith('    }\n'):
    raise SystemExit('V7Q extra retry-scope brace missing')
prefix = prefix[:-6]
play = prefix + play[cleanup_at:]
src = src[:play_begin] + play + src[main_begin:]

# Keep the monotonic percentage fix from V7P; only the real-time retry behavior
# is rolled back. Update the visible playback proof marker accordingly.
src = src.replace(
    '| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7P EOF RECOVERY\\n',
    '| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7Q AUDIO SAFE\\n',
    1
)

# Add a few harmless startup-only stages around track/decoder preparation so a
# future slow 60-72% run tells us which setup call is responsible. These occur
# before real-time playback starts and cannot starve AAC output.
video_find = 'video_index = av_find_best_stream(format, AVMEDIA_TYPE_VIDEO'
audio_find = 'audio_index = av_find_best_stream(format, AVMEDIA_TYPE_AUDIO'
video_at = src.find(video_find, play_begin, main_begin)
audio_at = src.find(audio_find, video_at, main_begin)
if video_at >= 0:
    line = src.rfind('\n', play_begin, video_at) + 1
    src = src[:line] + '    v7_stage("SELECTING H264 VIDEO TRACK...");\n' + src[line:]
    main_begin += len('    v7_stage("SELECTING H264 VIDEO TRACK...");\n')
if audio_at >= 0:
    # recompute after first insertion
    audio_at = src.find(audio_find, play_begin, main_begin)
    if audio_at >= 0:
        line = src.rfind('\n', play_begin, audio_at) + 1
        src = src[:line] + '    v7_stage("SELECTING AAC AUDIO TRACK...");\n' + src[line:]

# Give those diagnostic stages distinct monotonic percentages.
percent_anchor = '    if (strstr(stage, "READING MP4 TRACK TABLE") != NULL) return 60;\n'
if percent_anchor in src:
    src = src.replace(
        percent_anchor,
        percent_anchor +
        '    if (strstr(stage, "SELECTING H264 VIDEO TRACK") != NULL) return 63;\n'
        '    if (strstr(stage, "SELECTING AAC AUDIO TRACK") != NULL) return 66;\n',
        1
    )

for needle in (
    'SPELUNKR360 V7Q - AUDIO SAFE + MONOTONIC TUNING',
    'g_v7p_display_percent',
    'while (!wants_exit() && (result = av_read_frame(format, packet)) >= 0)',
    'V7Q AUDIO SAFE',
):
    if needle not in src:
        raise SystemExit(f'V7Q marker missing: {needle}')

if 'V7P transient demux retry' in src or 'V7P foreground refill retry' in src:
    raise SystemExit('V7Q blocking V7P recovery survived')

out.write_text(src)
print(f"generated {out} with V7Q audio-safe real-time loop and monotonic loader")
