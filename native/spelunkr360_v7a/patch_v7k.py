#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7k.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7K is the first user-experience pass after V7J proved smooth, zero-drop
# continuous playback on real Xbox 360 hardware. Preserve that decoder/audio/
# progressive-prefetch architecture and change only startup, shutdown and the
# visible loading presentation:
#
#   * use the hardware-proven 4 MiB synchronous seek window for FAST START;
#   * switch back to V7J's 8 MiB async range depth immediately after seek;
#   * give libcurl a 128 KiB receive buffer on all requests;
#   * cancel an in-flight async range before pthread_join() on shutdown;
#   * remove the old post-playback 600-frame PASS-screen delay;
#   * replace engineering stage text with a clean Wolf Factory TV loader.

src = src.replace(
    'SPELUNKR360 V7J - FAST-ROLLOVER CONTINUOUS PLAYBACK',
    'SPELUNKR360 V7K - FAST START + CLEAN LOADING'
)
src = src.replace('V7J - B/BACK/START RETURNS TO AURORA',
                  'V7K - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7J continuous playback ended before stability gate',
                  'V7K continuous playback ended before stability gate')
src = src.replace('Spelunkr360 V7J PASS:', 'Spelunkr360 V7K PASS:')
src = src.replace('V7J async partial salvaged', 'V7K async partial salvaged')
src = src.replace('V7J foreground partial salvaged', 'V7K foreground partial salvaged')
src = src.replace('V7J prefetch thread: creator_ht=', 'V7K prefetch thread: creator_ht=')

# Clean loading presentation. Keep v7_stage as the same low-risk single-frame
# status presenter, only replace its engineering copy. The fast-start split is
# printed by the loader itself so the visible proof marker does not depend on
# legacy stage wording surviving the earlier patch chain.
stage_begin = src.find('static uint32_t g_stage_width;')
stage_end = src.find('static void ff_error_text(', stage_begin)
if stage_begin < 0 or stage_end <= stage_begin:
    raise SystemExit('V7K stage helper markers missing')
stage_helper = r'''static uint32_t g_stage_width;
static uint32_t g_stage_height;

static void v7_stage(const char *stage)
{
    char text[768];
    if (g_stage_width == 0 || g_stage_height == 0 || stage == NULL) return;
    snprintf(text, sizeof(text),
        "WOLF FACTORY TV\n"
        "CH 53 // TOONERTIA\n\n"
        "STARTING LIVE CHANNEL\n\n"
        "%s\n\n"
        "4 MB FAST START / 8 MB ASYNC PLAYBACK\n"
        "B/BACK/START: CANCEL",
        stage);
    (void)present_status(g_stage_width, g_stage_height, text, GOOD_ARGB);
}

'''
src = src[:stage_begin] + stage_helper + src[stage_end:]

# Replace old probe/debug stage copy with viewer-facing loading states where the
# old wording is still present. The loader wrapper above keeps presentation
# clean even if an earlier patch changed one of these strings.
stage_replacements = {
    'STAGE 1/5: DOWNLOADING 17 MB MP4 HEADER...\\nTHIS CAN TAKE MORE THAN 30 SECONDS ON XBOX 360.':
        'READING MEDIA INDEX...\\nPREPARING CURRENT PROGRAM.',
    'STAGE 1/5: OPENING REMOTE MP4 / PREFETCHING HEADER...':
        'CONNECTING TO MEDIA SERVER...',
    'STAGE 2/5: OPENING MP4 CONTAINER IN FFMPEG...':
        'OPENING LIVE STREAM...',
    'STAGE 3/5: READING VIDEO STREAM INFO...':
        'READING STREAM INFORMATION...',
    'STAGE 4/5: SEEKING TO LIVE TOONERTIA POSITION...':
        'SYNCING TO LIVE PROGRAM...',
    'STAGE 5/5: READING / DECODING H.264 FRAME...':
        'STARTING VIDEO...',
    'V7B.3: PREPARING LIVE VIDEO...\\n16 MB CACHE / 8 MB ASYNC PREFETCH.\\nSTREAMING CLOCK WILL RE-SYNC AFTER REFILLS.':
        'BUFFERING LIVE TV...',
}
for old, new in stage_replacements.items():
    src = src.replace(old, new)

src = src.replace(
    'FETCHING LIVE SCHEDULE...\\nLOCATING CURRENT ARCHIVE MEDIA...\\nOPENING MP4 WITH HTTP RANGE IO...',
    'STARTING WOLF FACTORY TV...\\nCONNECTING TO CH 53 - TOONERTIA...\\nLOADING CURRENT PROGRAM...'
)
src = src.replace(
    'SCHEDULE: PASS\\nMEDIA URL: FOUND\\n\\nOPENING REMOTE MP4 / SEEKING / DECODING H.264...',
    'PROGRAM LOCATED\\n\\nCONNECTING TO LIVE VIDEO...'
)

# Give successful requests a larger libcurl receive buffer. This option is
# already proven in the V7E/V7J async worker; applying it in common setup also
# benefits metadata, the front-moov range and the first synchronous media read.
common_marker = '    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 15L);\n'
if common_marker not in src:
    raise SystemExit('V7K common curl marker missing')
src = src.replace(
    common_marker,
    common_marker + '    curl_easy_setopt(curl, CURLOPT_BUFFERSIZE, 131072L);\n',
    1
)

# V7B.3's 4 MiB synchronous window was already proven on hardware. Use it only
# for the initial seek so startup does not block on a full 8 MiB media range.
startup_range = 'remote.range_chunk = 8u * 1024u * 1024u;'
if startup_range not in src:
    raise SystemExit('V7K V7J range assignment missing')
src = src.replace(startup_range,
                  'remote.range_chunk = 4u * 1024u * 1024u;', 1)

# Immediately after the seek/decoder flush, restore V7J's 8 MiB depth before
# the asynchronous producer starts. Playback therefore keeps the V7J behavior
# that just passed with no visible lag and DROP=0.
prefetch_enable = '''    remote.prefetch_enabled = true;
    if (v7e_prefetch_start(&remote) != 0)'''
if prefetch_enable not in src:
    raise SystemExit('V7K post-seek prefetch marker missing')
src = src.replace(
    prefetch_enable,
    '''    remote.range_chunk = 8u * 1024u * 1024u;
    remote.prefetch_enabled = true;
    if (v7e_prefetch_start(&remote) != 0)''',
    1
)

# Make asynchronous curl cancellable so remote_close does not have to wait for
# an entire 8 MiB range to finish after the viewer presses B/BACK/START.
prefetch_done_field = '    volatile bool prefetch_done;\n'
if prefetch_done_field not in src:
    raise SystemExit('V7K prefetch_done field marker missing')
src = src.replace(prefetch_done_field,
                  prefetch_done_field + '    volatile bool prefetch_cancel;\n', 1)

worker_marker = 'static void *v7e_prefetch_worker(void *context)\n{'
if worker_marker not in src:
    raise SystemExit('V7K prefetch worker marker missing')
cancel_helper = r'''static int v7k_prefetch_progress(void *context,
    curl_off_t dltotal, curl_off_t dlnow, curl_off_t ultotal, curl_off_t ulnow)
{
    struct remote_file *remote = context;
    (void)dltotal;
    (void)dlnow;
    (void)ultotal;
    (void)ulnow;
    return (remote != NULL && remote->prefetch_cancel) ? 1 : 0;
}

'''
src = src.replace(worker_marker, cancel_helper + worker_marker, 1)

worker_curl = '''    set_common_curl(curl, remote->url);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 60000L);'''
if worker_curl not in src:
    raise SystemExit('V7K worker curl setup marker missing')
src = src.replace(
    worker_curl,
    '''    set_common_curl(curl, remote->url);
    curl_easy_setopt(curl, CURLOPT_NOPROGRESS, 0L);
    curl_easy_setopt(curl, CURLOPT_XFERINFOFUNCTION, v7k_prefetch_progress);
    curl_easy_setopt(curl, CURLOPT_XFERINFODATA, remote);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 60000L);''',
    1
)

start_marker = '''    remote->prefetch_status = -1;
    remote->prefetch_done = false;
    remote->prefetch_active = true;'''
if start_marker not in src:
    raise SystemExit('V7K prefetch start state marker missing')
src = src.replace(
    start_marker,
    '''    remote->prefetch_status = -1;
    remote->prefetch_cancel = false;
    remote->prefetch_done = false;
    remote->prefetch_active = true;''',
    1
)

close_begin = src.find('static void remote_close(struct remote_file *remote)')
close_end = src.find('static int avio_remote_read(', close_begin)
if close_begin < 0 or close_end <= close_begin:
    raise SystemExit('V7K remote_close markers missing')
close_block = src[close_begin:close_end]
old_join = '''    if (remote->prefetch_active) {
        (void)pthread_join(remote->prefetch_thread, NULL);'''
new_join = '''    if (remote->prefetch_active) {
        remote->prefetch_cancel = true;
        (void)pthread_join(remote->prefetch_thread, NULL);'''
if old_join not in close_block:
    raise SystemExit('V7K remote_close join marker missing')
close_block = close_block.replace(old_join, new_join, 1)
src = src[:close_begin] + close_block + src[close_end:]

# The old test harness intentionally held a PASS page for 600 frames after
# playback returned. The finished launcher should hand control straight back
# to Aurora; keep one frame at most for logging/visual confirmation.
old_success_hold = 'for (frame = 0; frame < 600 && !wants_exit(); frame++)'
if old_success_hold not in src:
    raise SystemExit('V7K post-playback hold marker missing')
src = src.replace(old_success_hold,
                  'for (frame = 0; frame < 1 && !wants_exit(); frame++)', 1)

# Visible proof marker for hardware photos.
src = src.replace(
    '| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s ROLLOVER\\n',
    '| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7K FAST START\\n',
    1
)

for needle in (
    'SPELUNKR360 V7K - FAST START + CLEAN LOADING',
    'WOLF FACTORY TV',
    'STARTING LIVE CHANNEL',
    '4 MB FAST START / 8 MB ASYNC PLAYBACK',
    'remote.range_chunk = 4u * 1024u * 1024u',
    'remote.range_chunk = 8u * 1024u * 1024u',
    'v7k_prefetch_progress',
    'remote->prefetch_cancel = true',
    'frame < 1 && !wants_exit()',
    'V7K FAST START',
):
    if needle not in src:
        raise SystemExit(f'V7K marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7K clean loader, 4 MiB fast-start seek, 8 MiB playback prefetch and fast exit")
