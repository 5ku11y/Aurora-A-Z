#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7i.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7I: turn the hardware-proven V7H 60-second soak into real continuous
# playback. Do NOT change the transport, decoder, audio-master clock, or
# progressive prefetch behavior that just passed on real Xbox 360 hardware.
# Remove only the synthetic test stop and the packet-count ceiling so playback
# runs until the user exits or the current media source genuinely reaches EOF.

src = src.replace('SPELUNKR360 V7H - PROGRESSIVE PREFETCH + STABILITY',
                  'SPELUNKR360 V7I - TRUE CONTINUOUS PLAYBACK')
src = src.replace('SPELUNKR360 V7H - PROGRESSIVE PREFETCH PLAYBACK',
                  'SPELUNKR360 V7I - TRUE CONTINUOUS PLAYBACK')
src = src.replace('V7H - B/BACK/START RETURNS TO AURORA',
                  'V7I - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7H soak failed', 'V7I continuous playback ended before stability gate')
src = src.replace('Spelunkr360 V7H PASS:', 'Spelunkr360 V7I PASS:')
src = src.replace('V7H async partial salvaged', 'V7I async partial salvaged')
src = src.replace('V7H foreground partial salvaged', 'V7I foreground partial salvaged')
src = src.replace('V7H prefetch thread: creator_ht=', 'V7I prefetch thread: creator_ht=')

old_loop = '    while (!wants_exit() && packets++ < V7C_MAX_PACKETS && (result = av_read_frame(format, packet)) >= 0) {'
new_loop = '''    while (!wants_exit() && (result = av_read_frame(format, packet)) >= 0) {
        packets++;'''
if old_loop not in src:
    raise SystemExit('V7I playback loop marker missing')
src = src.replace(old_loop, new_loop, 1)

old_stop = '                if (audio_clock >= audio.first_media_ms + V7C_PLAY_MS) goto stopped;\n'
if old_stop not in src:
    raise SystemExit('V7I 60-second auto-stop marker missing')
src = src.replace(old_stop, '', 1)

# Removing the only goto to this V7D/V7H soak label makes it obsolete. Keep the
# cleanup/result code in place, but let normal loop exit fall straight into it.
old_label = '\nstopped:\n    if (range_http != NULL) *range_http = remote.last_http;\n'
new_label = '\n    if (range_http != NULL) *range_http = remote.last_http;\n'
if old_label not in src:
    raise SystemExit('V7I stopped-label marker missing')
src = src.replace(old_label, new_label, 1)

src = src.replace('| RANGE HTTP %ld | SOAK 60s\\n',
                  '| RANGE HTTP %ld | CONTINUOUS\\n')
src = src.replace('LONG-RUN STABILITY TEST: PASS', 'CONTINUOUS PLAYBACK TEST: PASS')
src = src.replace('LONG-RUN STABILITY TEST: FAIL', 'CONTINUOUS PLAYBACK TEST: FAIL')
src = src.replace('60+ SECONDS H.264 + AAC PLAYED STABLY',
                  'H.264 + AAC CONTINUOUS PLAYBACK STABLE')
src = src.replace('NEXT MILESTONE: FINAL INTEGRATION + POLISH',
                  'NEXT MILESTONE: FINAL INTEGRATION + DISPLAY POLISH')

for needle in (
    'SPELUNKR360 V7I - TRUE CONTINUOUS PLAYBACK',
    'while (!wants_exit() && (result = av_read_frame(format, packet)) >= 0)',
    '| RANGE HTTP %ld | CONTINUOUS\\n',
    'CONTINUOUS PLAYBACK TEST: PASS',
    'H.264 + AAC CONTINUOUS PLAYBACK STABLE',
    'V7I continuous playback ended before stability gate',
):
    if needle not in src:
        raise SystemExit(f'V7I marker missing: {needle}')

if 'if (audio_clock >= audio.first_media_ms + V7C_PLAY_MS) goto stopped;' in src:
    raise SystemExit('V7I synthetic 60-second stop survived')
if 'packets++ < V7C_MAX_PACKETS' in src:
    raise SystemExit('V7I packet-count ceiling survived')
if '\nstopped:\n' in src:
    raise SystemExit('V7I obsolete stopped label survived')

out.write_text(src)
print(f"generated {out} with V7I true continuous playback until user exit or source EOF")
