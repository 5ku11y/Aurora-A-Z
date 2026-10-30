#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7l.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7L hardware follow-up after V7K:
# - V7K did not materially reduce launch time because an older V7A.9/V7A.11
#   compatibility layer still forced the complete ~17 MiB front moov atom to
#   download in 1 MiB HTTP requests before FFmpeg could proceed.
# - V7L removes that forced preload.  The custom seekable AVIO path now keeps a
#   4 MiB demand-read window while MOV opens, so FFmpeg fetches only the ranges
#   it actually asks for and does so in far fewer HTTP transactions.
# - V7J/V7K's proven 8 MiB asynchronous playback prefetch remains unchanged
#   after the live seek.
# - replace V7K's cleaned diagnostic text with an actual branded loading screen
#   and progress bar, and display it before schedule/network work starts.

src = src.replace(
    'SPELUNKR360 V7K - FAST START + CLEAN LOADING',
    'SPELUNKR360 V7L - DEMAND OPEN + REAL LOADER'
)
src = src.replace('V7K - B/BACK/START RETURNS TO AURORA',
                  'V7L - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7K continuous playback ended before stability gate',
                  'V7L continuous playback ended before stability gate')
src = src.replace('Spelunkr360 V7K PASS:', 'Spelunkr360 V7L PASS:')
src = src.replace('V7K async partial salvaged', 'V7L async partial salvaged')
src = src.replace('V7K foreground partial salvaged', 'V7L foreground partial salvaged')
src = src.replace('V7K prefetch thread: creator_ht=', 'V7L prefetch thread: creator_ht=')

# Real loader: large brand header, channel identity, stage text, and an actual
# stage-driven progress bar.  This is intentionally viewer-facing rather than
# a diagnostic dump.  It uses only the already hardware-proven xsdk text/
# present path, so it does not disturb the video renderer.
stage_begin = src.find('static uint32_t g_stage_width;')
stage_end = src.find('static void ff_error_text(', stage_begin)
if stage_begin < 0 or stage_end <= stage_begin:
    raise SystemExit('V7L stage helper markers missing')
stage_helper = r'''static uint32_t g_stage_width;
static uint32_t g_stage_height;

static unsigned v7l_stage_percent(const char *stage)
{
    if (stage == NULL) return 0;
    if (strstr(stage, "CONNECTING TO CHANNEL SERVICE") != NULL) return 5;
    if (strstr(stage, "READING MEDIA INDEX") != NULL) return 12;
    if (strstr(stage, "PROGRAM LOCATED") != NULL) return 20;
    if (strstr(stage, "CONNECTING TO MEDIA SERVER") != NULL) return 28;
    if (strstr(stage, "OPENING LIVE STREAM") != NULL) return 45;
    if (strstr(stage, "READING STREAM INFORMATION") != NULL) return 62;
    if (strstr(stage, "BUFFERING LIVE TV") != NULL) return 72;
    if (strstr(stage, "SYNCING TO LIVE PROGRAM") != NULL) return 84;
    if (strstr(stage, "STARTING VIDEO") != NULL) return 96;
    return 10;
}

static void v7_stage(const char *stage)
{
    char bar[35];
    char percent_text[32];
    unsigned percent, filled, i;
    uint32_t address = 0;
    NTSTATUS status;

    if (g_stage_width == 0 || g_stage_height == 0 || stage == NULL) return;
    percent = v7l_stage_percent(stage);
    filled = (percent * 32u) / 100u;
    bar[0] = '[';
    for (i = 0; i < 32u; i++) bar[i + 1u] = i < filled ? '#' : '-';
    bar[33] = ']';
    bar[34] = '\0';
    snprintf(percent_text, sizeof(percent_text), "%u%%", percent);

    status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
    if (!NT_SUCCESS(status)) return;
    xsdk_gpu_set_target(g_stage_width, g_stage_height);

    xsdk_text_draw(250, 92, 3, TEXT_ARGB, "WOLF FACTORY TV");
    xsdk_text_draw(352, 178, 2, GOOD_ARGB, "CH 53 // TOONERTIA");
    xsdk_text_draw(180, 258, 1, GOOD_ARGB,
        "============================================================");
    xsdk_text_draw(250, 326, 2, GOOD_ARGB, bar);
    xsdk_text_draw(968, 326, 2, TEXT_ARGB, percent_text);
    xsdk_text_draw(250, 406, 2, TEXT_ARGB, stage);
    xsdk_text_draw(180, 584, 1, GOOD_ARGB,
        "Preparing broadcast - optimized demand streaming");
    xsdk_text_draw(180, 620, 1, TEXT_ARGB,
        "B / BACK / START   CANCEL AND RETURN TO AURORA");

    xsdk_gpu_resolve(address, g_stage_width, g_stage_height, BACKGROUND_ARGB);
    xsdk_present_end();
}

'''
src = src[:stage_begin] + stage_helper + src[stage_end:]

# Put the real loader on screen before the schedule/lineup requests begin.
# V7K did not set g_stage_width/height until decode_picture(), which meant the
# slowest early network work still used the old plain status page.
early_marker = '    body.data = malloc(BODY_BYTES);\n'
if early_marker not in src:
    raise SystemExit('V7L early loader marker missing')
src = src.replace(
    early_marker,
    '    g_stage_width = width;\n'
    '    g_stage_height = height;\n'
    '    v7_stage("CONNECTING TO CHANNEL SERVICE...");\n\n'
    + early_marker,
    1
)

# Remove the historical forced full-front-moov download.  Keep the helper call
# in place so the transform is low risk, but turn it into a 4 MiB demand cache
# setup.  The initial range already fetched by remote_open remains cached.
moov_begin = src.find('static int remote_prefetch_front_moov(struct remote_file *remote)')
moov_end = src.find('static int remote_open(struct remote_file *remote, const char *url)', moov_begin)
if moov_begin < 0 or moov_end <= moov_begin:
    raise SystemExit('V7L front-moov helper markers missing')
moov_helper = r'''static int remote_prefetch_front_moov(struct remote_file *remote)
{
    const size_t fast_open_bytes = 4u * 1024u * 1024u;
    uint8_t *grown;

    if (remote == NULL || remote->cache == NULL) return -1;
    if (remote->cache_capacity < fast_open_bytes) {
        grown = realloc(remote->cache, fast_open_bytes);
        if (grown == NULL) {
            snprintf(remote->error, sizeof(remote->error),
                "V7L fast-open cache realloc failed");
            return -1;
        }
        remote->cache = grown;
        remote->cache_capacity = fast_open_bytes;
    }
    remote->range_chunk = fast_open_bytes;
    xsdk_log_write("V7L demand-open: forced 17 MB front-moov preload bypassed");
    return 0;
}

'''
src = src[:moov_begin] + moov_helper + src[moov_end:]

# MOV is explicitly selected, so the old 24 MiB generic probe budget is no
# longer useful.  Keep enough analysis room for H.264/AAC discovery without
# encouraging FFmpeg to read tens of MiB before first picture.
if 'format->probesize = 24 * 1024 * 1024;' not in src:
    raise SystemExit('V7L 24 MiB probe marker missing')
src = src.replace('format->probesize = 24 * 1024 * 1024;',
                  'format->probesize = 4 * 1024 * 1024;', 1)
if 'format->max_analyze_duration = 5LL * AV_TIME_BASE;' not in src:
    raise SystemExit('V7L analyze-duration marker missing')
src = src.replace('format->max_analyze_duration = 5LL * AV_TIME_BASE;',
                  'format->max_analyze_duration = 2LL * AV_TIME_BASE;', 1)

# Viewer-facing loading copy for the now demand-open path.
src = src.replace('READING MEDIA INDEX...\\nPREPARING CURRENT PROGRAM.',
                  'READING MEDIA INDEX...\\nFINDING CURRENT PROGRAM.')
src = src.replace('CONNECTING TO MEDIA SERVER...',
                  'CONNECTING TO MEDIA SERVER...')
src = src.replace('OPENING LIVE STREAM...',
                  'OPENING LIVE STREAM...\\nUSING FAST RANGE ACCESS.')
src = src.replace('BUFFERING LIVE TV...\\n4 MB FAST START / 8 MB ASYNC PLAYBACK.',
                  'BUFFERING LIVE TV...\\n4 MB DEMAND OPEN / 8 MB ASYNC PLAYBACK.')

# Hardware-photo marker.
src = src.replace('| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7K FAST START\\n',
                  '| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7L DEMAND OPEN\\n', 1)

for needle in (
    'SPELUNKR360 V7L - DEMAND OPEN + REAL LOADER',
    'WOLF FACTORY TV',
    'CH 53 // TOONERTIA',
    'v7l_stage_percent',
    'CONNECTING TO CHANNEL SERVICE',
    'fast_open_bytes = 4u * 1024u * 1024u',
    'forced 17 MB front-moov preload bypassed',
    'format->probesize = 4 * 1024 * 1024',
    'format->max_analyze_duration = 2LL * AV_TIME_BASE',
    '4 MB DEMAND OPEN / 8 MB ASYNC PLAYBACK',
    'V7L DEMAND OPEN',
):
    if needle not in src:
        raise SystemExit(f'V7L marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7L real loader and demand-open MP4 startup")
