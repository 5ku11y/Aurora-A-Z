#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7p.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7P hardware follow-up after Wolf's V7N/V7O observations:
# - loader percentage could climb to ~25/26% from curl transfer activity and
#   then fall back to the stage base (22%) when v7_stage() redrew with zero
#   network progress. Keep the displayed percentage monotonic.
# - continuous playback currently exits whenever av_read_frame() returns any
#   negative result. With custom Archive.org AVIO, a transient range failure can
#   surface as EIO/EOF even though remote.position is still before remote.size.
# - retry failed foreground range fills twice before exposing EIO to FFmpeg.
# - if av_read_frame still reports a negative result before the known remote end,
#   clear AVIO's latched eof/error state and retry the demux read up to 3 times.
# - never retry a genuine source end where remote.position >= remote.size.

src = src.replace(
    'SPELUNKR360 V7O - 1MB BOOTSTRAP + TIMED SPELUNKR TV',
    'SPELUNKR360 V7P - MONOTONIC TUNING + EOF RECOVERY'
)
src = src.replace('V7O - B/BACK/START RETURNS TO AURORA',
                  'V7P - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7O continuous playback ended before stability gate',
                  'V7P continuous playback ended before stability gate')
src = src.replace('Spelunkr360 V7O PASS:', 'Spelunkr360 V7P PASS:')
src = src.replace('V7O async partial salvaged', 'V7P async partial salvaged')
src = src.replace('V7O foreground partial salvaged', 'V7P foreground partial salvaged')
src = src.replace('V7O prefetch thread: creator_ht=', 'V7P prefetch thread: creator_ht=')
src = src.replace('V7O fast track open: avformat_find_stream_info bypassed',
                  'V7P fast track open: avformat_find_stream_info bypassed')

# Keep the visible loader from ever moving backwards. Network callbacks can add
# a few points to a stage; a later stage redraw with network_percent=0 must keep
# the highest already-shown value rather than dropping to its base percentage.
progress_field = 'static uint64_t g_v7n_last_progress_bytes;\n'
if progress_field not in src:
    raise SystemExit('V7P loader progress field marker missing')
src = src.replace(progress_field,
                  progress_field + 'static unsigned g_v7p_display_percent;\n', 1)

percent_anchor = '    if (percent > 98u) percent = 98u;\n'
if percent_anchor not in src:
    raise SystemExit('V7P loader percent clamp marker missing')
src = src.replace(
    percent_anchor,
    percent_anchor +
    '    if (percent < g_v7p_display_percent) percent = g_v7p_display_percent;\n'
    '    else g_v7p_display_percent = percent;\n',
    1
)

# Track retry activity in the remote transport for hardware logs.
retry_field = '    unsigned foreground_partials;\n'
if retry_field not in src:
    raise SystemExit('V7P foreground counter marker missing')
src = src.replace(retry_field,
                  retry_field + '    unsigned foreground_retries;\n', 1)

# Hide brief Archive.org zero-byte/range failures from FFmpeg when a retry can
# recover them. Later transport patches have changed the surrounding prefetch
# block several times, so patch only the stable remote_fill + EIO pair inside
# avio_remote_read instead of matching the entire historical block.
read_begin = src.find('static int avio_remote_read(void *opaque, uint8_t *buffer, int buffer_size)')
read_end = src.find('\nstatic int64_t avio_remote_seek(', read_begin)
if read_begin < 0 or read_end <= read_begin:
    raise SystemExit('V7P avio_remote_read boundaries missing')
read_block = src[read_begin:read_end]
fill_call = 'if (remote_fill(remote, remote->position) != 0)'
fill_at = read_block.find(fill_call)
if fill_at < 0:
    raise SystemExit('V7P AVIO remote_fill call missing')
return_token = 'return copied > 0 ? copied : AVERROR(EIO);'
return_at = read_block.find(return_token, fill_at)
if return_at < 0:
    raise SystemExit('V7P AVIO EIO return missing')
line_start = read_block.rfind('\n', 0, fill_at) + 1
line_end = read_block.find('\n', return_at)
if line_end < 0:
    line_end = len(read_block)
else:
    line_end += 1
indent = read_block[line_start:fill_at]
retry_code = (
    indent + 'int fill_result = remote_fill(remote, remote->position);\n' +
    indent + 'unsigned retry = 0;\n' +
    indent + 'while (fill_result != 0 && retry < 2u && !wants_exit()) {\n' +
    indent + '    retry++;\n' +
    indent + '    remote->foreground_retries++;\n' +
    indent + '    xsdk_log_write("V7P foreground refill retry %u pos=%" PRId64 " err=%.96s",\n' +
    indent + '        retry, remote->position, remote->error);\n' +
    indent + '    fill_result = remote_fill(remote, remote->position);\n' +
    indent + '}\n' +
    indent + 'if (fill_result != 0)\n' +
    indent + '    return copied > 0 ? copied : AVERROR(EIO);\n'
)
read_block = read_block[:line_start] + retry_code + read_block[line_end:]
src = src[:read_begin] + read_block + src[read_end:]

# V7I converted the hardware-proven soak loop into continuous playback, but the
# while condition still stops on the first negative av_read_frame result. Make
# that decision explicit so a false EOF/EIO before the known remote end can be
# retried without ever looping on a genuine end-of-file.
old_loop = '''    while (!wants_exit() && (result = av_read_frame(format, packet)) >= 0) {
        packets++;'''
new_loop = '''    {
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
if old_loop not in src:
    raise SystemExit('V7P V7I continuous loop marker missing')
src = src.replace(old_loop, new_loop, 1)

# The original loop body already has one closing brace. Add one more to close
# the local retry scope immediately before range_http is copied during cleanup.
cleanup_anchor = '    if (range_http != NULL) *range_http = remote.last_http;\n'
if cleanup_anchor not in src:
    raise SystemExit('V7P playback cleanup marker missing')
src = src.replace(cleanup_anchor, '    }\n' + cleanup_anchor, 1)

src = src.replace(
    '| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7O 1MB BOOT\\n',
    '| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7P EOF RECOVERY\\n',
    1
)

for needle in (
    'SPELUNKR360 V7P - MONOTONIC TUNING + EOF RECOVERY',
    'g_v7p_display_percent',
    'V7P foreground refill retry',
    'V7P transient demux retry',
    'V7P EOF stop:',
    'remote.position < remote.size',
    'V7P EOF RECOVERY',
):
    if needle not in src:
        raise SystemExit(f'V7P marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7P monotonic loader progress and guarded transient EOF/EIO recovery")
