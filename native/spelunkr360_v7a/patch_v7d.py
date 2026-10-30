#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7d.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7D: playback quality + long-run stability.
# Keep the hardware-proven V7C H.264/AAC/audio-master path intact and extend
# it to a 60-second soak with explicit quality/stability gates.

src = src.replace('#define V7C_PLAY_MS 12000LL', '#define V7C_PLAY_MS 60000LL')
src = src.replace('#define V7C_MIN_VIDEO_FRAMES 60u', '#define V7C_MIN_VIDEO_FRAMES 300u')
src = src.replace('#define V7C_MAX_PACKETS 6000u', '#define V7C_MAX_PACKETS 20000u')

src = src.replace('SPELUNKR360 V7C - AUDIO + A/V SYNC PROBE',
                  'SPELUNKR360 V7D - PLAYBACK QUALITY + LONG-RUN STABILITY')
src = src.replace('SPELUNKR360 V7C - AUDIO + A/V SYNC PLAYBACK',
                  'SPELUNKR360 V7D - 60 SECOND STABILITY PLAYBACK')
src = src.replace('V7C - B/BACK/START RETURNS TO AURORA',
                  'V7D - B/BACK/START RETURNS TO AURORA')
src = src.replace('A/V SYNC TEST: PASS', 'LONG-RUN STABILITY TEST: PASS')
src = src.replace('A/V SYNC TEST: FAIL', 'LONG-RUN STABILITY TEST: FAIL')
src = src.replace('10+ SECONDS H.264 + AAC PLAYED IN SYNC',
                  '60+ SECONDS H.264 + AAC PLAYED STABLY')
src = src.replace('NEXT MILESTONE: PLAYBACK QUALITY + LONG-RUN STABILITY',
                  'NEXT MILESTONE: FINAL INTEGRATION + POLISH')

# Add quality counters beside the existing V7C playback counters.
old_counters = '    unsigned rendered_frames = 0, dropped_frames = 0, packets = 0;\n'
new_counters = (
    '    unsigned rendered_frames = 0, dropped_frames = 0, packets = 0;\n'
    '    int64_t max_abs_sync_ms = 0;\n'
    '    unsigned silent_at_start = 0;\n'
    '    bool silent_baseline_set = false;\n'
)
if old_counters not in src:
    raise SystemExit('V7D counter marker missing')
src = src.replace(old_counters, new_counters, 1)

# Record worst observed A/V error after the audio clock is live.
old_sync = '                sync_ms = audio_clock >= 0 ? actual_ms - audio_clock : 0;\n'
new_sync = (
    '                sync_ms = audio_clock >= 0 ? actual_ms - audio_clock : 0;\n'
    '                if (audio_clock >= 0) {\n'
    '                    int64_t abs_sync = sync_ms < 0 ? -sync_ms : sync_ms;\n'
    '                    if (abs_sync > max_abs_sync_ms) max_abs_sync_ms = abs_sync;\n'
    '                }\n'
)
if old_sync not in src:
    raise SystemExit('V7D sync marker missing')
src = src.replace(old_sync, new_sync, 1)

# Capture startup silence once video actually begins so the soak gate measures
# only underruns introduced during sustained playback, not normal audio startup.
old_rendered = '                rendered_frames++;\n                last_video_ms = actual_ms;\n'
new_rendered = (
    '                rendered_frames++;\n'
    '                if (!silent_baseline_set) {\n'
    '                    xsdk_audio_stats(&audio_stats);\n'
    '                    silent_at_start = audio_stats.silent;\n'
    '                    silent_baseline_set = true;\n'
    '                }\n'
    '                last_video_ms = actual_ms;\n'
)
if old_rendered not in src:
    raise SystemExit('V7D render marker missing')
src = src.replace(old_rendered, new_rendered, 1)

# Expand the live overlay with the soak target and worst drift seen so far.
old_overlay = (
    '                    "TARGET %s | VIDEO %s | FRAME %u DROP %u | A/V %+" PRId64 "ms\\n"\n'
    '                    "AUDIO %s %dHz %dch | PLAYED %u SILENT %u | RANGE HTTP %ld\\n"\n'
)
new_overlay = (
    '                    "TARGET %s | VIDEO %s | FRAME %u DROP %u | A/V %+" PRId64 "ms MAX %" PRId64 "ms\\n"\n'
    '                    "AUDIO %s %dHz %dch | PLAYED %u SILENT %u | RANGE HTTP %ld | SOAK 60s\\n"\n'
)
if old_overlay not in src:
    raise SystemExit('V7D overlay marker missing')
src = src.replace(old_overlay, new_overlay, 1)
old_args = (
    '                    title, year, target_text, current_text, rendered_frames + 1u, dropped_frames, sync_ms,\n'
    '                    audio_codec->name ? audio_codec->name : "audio", audio.source_rate, audio.source_channels,\n'
)
new_args = (
    '                    title, year, target_text, current_text, rendered_frames + 1u, dropped_frames, sync_ms, max_abs_sync_ms,\n'
    '                    audio_codec->name ? audio_codec->name : "audio", audio.source_rate, audio.source_channels,\n'
)
if old_args not in src:
    raise SystemExit('V7D overlay args marker missing')
src = src.replace(old_args, new_args, 1)

# Replace V7C's short proof gate with a 60-second quality/stability gate.
old_gate = '''        int64_t audio_span = ((int64_t)audio_stats.played * XSDK_AUDIO_FRAME_SAMPLES * 1000LL) / XSDK_AUDIO_RATE_HZ;\n        int64_t video_span = first_video_ms >= 0 && last_video_ms >= first_video_ms ? last_video_ms - first_video_ms : 0;\n        if (renderer_ready && audio.open && rendered_frames >= V7C_MIN_VIDEO_FRAMES &&\n            audio_span >= 9000 && video_span >= 8500) {\n            xsdk_log_write("Spelunkr360 V7C PASS: video=%u drop=%u vspan=%" PRId64\n                " audio_frames=%u silence=%u aspan=%" PRId64 " rate=%d ch=%d HTTP=%ld",\n                rendered_frames, dropped_frames, video_span, audio_stats.played, audio_stats.silent,\n                audio_span, audio.source_rate, audio.source_channels, remote.last_http);\n'''
new_gate = '''        int64_t audio_span = ((int64_t)audio_stats.played * XSDK_AUDIO_FRAME_SAMPLES * 1000LL) / XSDK_AUDIO_RATE_HZ;\n        int64_t video_span = first_video_ms >= 0 && last_video_ms >= first_video_ms ? last_video_ms - first_video_ms : 0;\n        unsigned silent_delta = silent_baseline_set && audio_stats.silent >= silent_at_start\n            ? audio_stats.silent - silent_at_start : audio_stats.silent;\n        unsigned drop_limit = rendered_frames / 20u + 3u;\n        if (renderer_ready && audio.open && rendered_frames >= V7C_MIN_VIDEO_FRAMES &&\n            audio_span >= 55000 && video_span >= 54000 && max_abs_sync_ms <= 200 &&\n            dropped_frames <= drop_limit && silent_delta <= 8u && remote.last_http == 206) {\n            xsdk_log_write("Spelunkr360 V7D PASS: video=%u drop=%u/%u vspan=%" PRId64\n                " audio_frames=%u silent_delta=%u aspan=%" PRId64 " max_sync=%" PRId64\n                " rate=%d ch=%d HTTP=%ld",\n                rendered_frames, dropped_frames, drop_limit, video_span, audio_stats.played, silent_delta,\n                audio_span, max_abs_sync_ms, audio.source_rate, audio.source_channels, remote.last_http);\n'''
if old_gate not in src:
    raise SystemExit('V7D pass gate marker missing')
src = src.replace(old_gate, new_gate, 1)

old_fail = '''        snprintf(error, error_size,\n            "V7C playback short: video=%u drop=%u vspan=%" PRId64\n            " audio=%u silent=%u aspan=%" PRId64 "ms",\n            rendered_frames, dropped_frames, video_span,\n            audio_stats.played, audio_stats.silent, audio_span);\n'''
new_fail = '''        snprintf(error, error_size,\n            "V7D soak failed: video=%u drop=%u/%u vspan=%" PRId64\n            " audio=%u silent_delta=%u aspan=%" PRId64 " max_sync=%" PRId64 "ms HTTP=%ld",\n            rendered_frames, dropped_frames, drop_limit, video_span,\n            audio_stats.played, silent_delta, audio_span, max_abs_sync_ms, remote.last_http);\n'''
if old_fail not in src:
    raise SystemExit('V7D fail gate marker missing')
src = src.replace(old_fail, new_fail, 1)

for needle in (
    'SPELUNKR360 V7D - PLAYBACK QUALITY + LONG-RUN STABILITY',
    'SPELUNKR360 V7D - 60 SECOND STABILITY PLAYBACK',
    'LONG-RUN STABILITY TEST: PASS',
    '60+ SECONDS H.264 + AAC PLAYED STABLY',
    'max_abs_sync_ms',
    'silent_delta <= 8u',
    'audio_span >= 55000',
    'video_span >= 54000',
    'remote.last_http == 206',
    'NEXT MILESTONE: FINAL INTEGRATION + POLISH',
):
    if needle not in src:
        raise SystemExit(f'V7D marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7D 60-second quality/stability soak gates")
