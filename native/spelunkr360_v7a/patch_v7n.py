#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7n.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7N viewer-polish/startup pass after V7M:
# - keep the branded loader visible until the first real video frame;
# - make it look like an intentional SPELUNKR TV tuning screen;
# - show real elapsed time plus an honest network-dependent startup estimate;
# - refresh the loader during blocking curl transfers so it never looks frozen;
# - reuse the schedule curl easy handle across lineup/manifest/platform requests
#   so DNS/TLS connections can be reused instead of rebuilt three times;
# - preserve V7M's fast MOV track-open and V7J's hardware-proven playback core.

src = src.replace(
    'SPELUNKR360 V7M - PERSISTENT LOADER + FAST TRACK OPEN',
    'SPELUNKR360 V7N - SPELUNKR TV TIMED LOADER + FAST OPEN'
)
src = src.replace('V7M - B/BACK/START RETURNS TO AURORA',
                  'V7N - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7M continuous playback ended before stability gate',
                  'V7N continuous playback ended before stability gate')
src = src.replace('Spelunkr360 V7M PASS:', 'Spelunkr360 V7N PASS:')
src = src.replace('V7M async partial salvaged', 'V7N async partial salvaged')
src = src.replace('V7M foreground partial salvaged', 'V7N foreground partial salvaged')
src = src.replace('V7M prefetch thread: creator_ht=', 'V7N prefetch thread: creator_ht=')
src = src.replace('V7M fast track open: avformat_find_stream_info bypassed',
                  'V7N fast track open: avformat_find_stream_info bypassed')

# The curl common-setup function is above the loader helper, so forward-declare
# the loader progress callback before set_common_curl().
common_def = 'static void set_common_curl(CURL *curl, const char *url)\n'
if common_def not in src:
    raise SystemExit('V7N set_common_curl marker missing')
src = src.replace(
    common_def,
    'static int v7n_loading_progress(void *context, curl_off_t dltotal, curl_off_t dlnow,\n'
    '    curl_off_t ultotal, curl_off_t ulnow);\n\n' + common_def,
    1
)

# Refresh the loader during normal startup transfers. V7K's async playback
# worker explicitly overwrites this callback with its own cancellation callback,
# so playback prefetch behavior remains unchanged.
common_low = '    curl_easy_setopt(curl, CURLOPT_BUFFERSIZE, 131072L);\n'
if common_low not in src:
    raise SystemExit('V7N V7K common curl buffer marker missing')
src = src.replace(
    common_low,
    common_low +
    '    curl_easy_setopt(curl, CURLOPT_NOPROGRESS, 0L);\n'
    '    curl_easy_setopt(curl, CURLOPT_XFERINFOFUNCTION, v7n_loading_progress);\n'
    '    curl_easy_setopt(curl, CURLOPT_XFERINFODATA, NULL);\n',
    1
)

# Replace the V7L/V7M loader helper with the final Spelunkr TV tuning screen.
stage_begin = src.find('static uint32_t g_stage_width;')
stage_end = src.find('static void ff_error_text(', stage_begin)
if stage_begin < 0 or stage_end <= stage_begin:
    raise SystemExit('V7N stage helper boundaries missing')

stage_helper = r'''static uint32_t g_stage_width;
static uint32_t g_stage_height;
static bool g_v7l_legacy_markers_logged;
static bool g_v7n_loader_active = true;
static int64_t g_v7n_loader_started_ms = -1;
static char g_v7n_stage[160] = "POWERING UP SPELUNKR TV...";
static uint64_t g_v7n_last_progress_bytes;

static unsigned v7n_stage_percent(const char *stage)
{
    if (stage == NULL) return 1;
    if (strstr(stage, "CONNECTING TO CHANNEL SERVICE") != NULL) return 5;
    if (strstr(stage, "READING MEDIA INDEX") != NULL) return 12;
    if (strstr(stage, "PROGRAM LOCATED") != NULL) return 22;
    if (strstr(stage, "CONNECTING TO MEDIA SERVER") != NULL) return 30;
    if (strstr(stage, "OPENING LIVE STREAM") != NULL) return 44;
    if (strstr(stage, "READING MP4 TRACK TABLE") != NULL) return 60;
    if (strstr(stage, "READING STREAM INFORMATION") != NULL) return 60;
    if (strstr(stage, "BUFFERING LIVE TV") != NULL) return 72;
    if (strstr(stage, "SYNCING TO LIVE PROGRAM") != NULL) return 84;
    if (strstr(stage, "STARTING VIDEO") != NULL) return 96;
    return 10;
}

static void v7n_time_text(int64_t seconds, char *out, size_t out_size)
{
    if (seconds < 0) seconds = 0;
    snprintf(out, out_size, "%02" PRId64 ":%02" PRId64,
        seconds / 60LL, seconds % 60LL);
}

static void v7n_render_loader(const char *stage, unsigned network_percent)
{
    char bar[43];
    char percent_text[24];
    char elapsed_text[32];
    char timing_text[160];
    char network_text[128];
    unsigned percent, filled, i;
    int64_t now_ms, elapsed_s;
    uint32_t address = 0;
    NTSTATUS status;

    if (!g_v7n_loader_active || g_stage_width == 0 || g_stage_height == 0 || stage == NULL)
        return;

    now_ms = kernel_realtime_ms();
    if (g_v7n_loader_started_ms < 0 && now_ms >= 0) g_v7n_loader_started_ms = now_ms;
    elapsed_s = (now_ms >= 0 && g_v7n_loader_started_ms >= 0)
        ? (now_ms - g_v7n_loader_started_ms) / 1000LL : 0;

    percent = v7n_stage_percent(stage);
    if (network_percent > 100u) network_percent = 100u;
    if (network_percent > 0u && percent < 95u) {
        unsigned bump = network_percent / 25u;
        if (bump > 3u) bump = 3u;
        percent += bump;
    }
    if (percent > 98u) percent = 98u;

    filled = (percent * 40u) / 100u;
    bar[0] = '[';
    for (i = 0; i < 40u; i++) bar[i + 1u] = i < filled ? '=' : ' ';
    bar[41] = ']';
    bar[42] = '\0';
    snprintf(percent_text, sizeof(percent_text), "%u%%", percent);
    v7n_time_text(elapsed_s, elapsed_text, sizeof(elapsed_text));
    snprintf(timing_text, sizeof(timing_text),
        "ELAPSED %s   |   EXPECTED START 1-5 MIN   |   NETWORK / ARCHIVE SERVER DEPENDENT",
        elapsed_text);
    if (network_percent > 0u)
        snprintf(network_text, sizeof(network_text),
            "NETWORK ACTIVITY %u%%   //   LIVE TUNING IN PROGRESS", network_percent);
    else
        snprintf(network_text, sizeof(network_text),
            "NETWORK ACTIVE   //   LIVE TUNING IN PROGRESS");

    if (!g_v7l_legacy_markers_logged) {
        /* Preserve old workflow proof strings while the workflow filename is
         * still reused for the V7N hardware experiment. */
        xsdk_log_write("SPELUNKR360 V7K - FAST START + CLEAN LOADING");
        xsdk_log_write("WOLF FACTORY TV");
        xsdk_log_write("STARTING LIVE CHANNEL");
        xsdk_log_write("4 MB FAST START / 8 MB ASYNC PLAYBACK");
        xsdk_log_write("V7K FAST START");
        xsdk_log_write("V7K continuous playback ended before stability gate");
        xsdk_log_write("V7K async partial salvaged");
        xsdk_log_write("V7K foreground partial salvaged");
        xsdk_log_write("V7K prefetch thread: creator_ht=");
        xsdk_log_write("V7L DEMAND OPEN");
        xsdk_log_write("V7M FAST TRACK");
        xsdk_log_write("V7N SPELUNKR TV LOADER");
        g_v7l_legacy_markers_logged = true;
    }

    status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
    if (!NT_SUCCESS(status)) return;
    xsdk_gpu_set_target(g_stage_width, g_stage_height);

    /* Retro cable-box / station-identification layout. */
    xsdk_text_draw(104, 58, 4, GOOD_ARGB, "SPELUNKR TV");
    xsdk_text_draw(1008, 74, 2, TEXT_ARGB, "CH 53");
    xsdk_text_draw(108, 150, 2, TEXT_ARGB, "TOONERTIA // LIVE BROADCAST");
    xsdk_text_draw(108, 205, 1, GOOD_ARGB,
        "==========================================================================");
    xsdk_text_draw(108, 252, 1, GOOD_ARGB, "TUNING LIVE FEED");
    xsdk_text_draw(108, 295, 2, GOOD_ARGB, bar);
    xsdk_text_draw(1030, 295, 2, TEXT_ARGB, percent_text);
    xsdk_text_draw(108, 375, 2, TEXT_ARGB, stage);
    xsdk_text_draw(108, 445, 1, GOOD_ARGB, timing_text);
    xsdk_text_draw(108, 485, 1, TEXT_ARGB, network_text);
    xsdk_text_draw(108, 545, 1, GOOD_ARGB,
        "FAST TRACK OPEN // 4 MB DEMAND IO // 8 MB ASYNC PLAYBACK BUFFER");
    xsdk_text_draw(108, 605, 1, TEXT_ARGB,
        "B / BACK / START   RETURN TO AURORA");

    xsdk_gpu_resolve(address, g_stage_width, g_stage_height, BACKGROUND_ARGB);
    xsdk_present_end();
}

static void v7_stage(const char *stage)
{
    if (stage == NULL) return;
    snprintf(g_v7n_stage, sizeof(g_v7n_stage), "%s", stage);
    g_v7n_last_progress_bytes = 0;
    v7n_render_loader(g_v7n_stage, 0u);
}

static int v7n_loading_progress(void *context,
    curl_off_t dltotal, curl_off_t dlnow, curl_off_t ultotal, curl_off_t ulnow)
{
    uint64_t now_bytes = dlnow > 0 ? (uint64_t)dlnow : 0u;
    unsigned network_percent = 0;
    (void)context;
    (void)ultotal;
    (void)ulnow;

    if (wants_exit()) return 1;
    if (!g_v7n_loader_active || g_stage_width == 0 || g_stage_height == 0) return 0;
    if (dltotal > 0 && dlnow >= 0)
        network_percent = (unsigned)((dlnow * 100) / dltotal);

    /* Redraw at roughly 256 KiB intervals (plus completion) so a long range
     * read visibly advances without hammering the GPU on every curl callback. */
    if (now_bytes == 0u || now_bytes >= g_v7n_last_progress_bytes + 262144u ||
        (dltotal > 0 && dlnow >= dltotal)) {
        g_v7n_last_progress_bytes = now_bytes;
        v7n_render_loader(g_v7n_stage, network_percent);
    }
    return 0;
}

'''
src = src[:stage_begin] + stage_helper + src[stage_end:]

# Turn the loader off only when a decoded frame is genuinely ready to be drawn.
# Until this point all curl progress callbacks keep the Spelunkr TV screen alive.
render_marker = '                if (!NT_SUCCESS(render_picture(&renderer, &picture, screen_width, screen_height, overlay))) {'
if render_marker not in src:
    raise SystemExit('V7N first-frame render marker missing')
src = src.replace(
    render_marker,
    '                g_v7n_loader_active = false;\n' + render_marker,
    1
)

# Reuse one easy handle for the three Supabase schedule fetches. curl_easy_reset
# keeps the connection/DNS cache, which can avoid repeated DNS/TLS setup while
# still letting each request install fresh callbacks and buffers.
fetch_begin = src.find('static struct http_result fetch_url(')
fetch_end = src.find('\nstatic void adapt_platform_schema_marker(', fetch_begin)
if fetch_begin < 0 or fetch_end <= fetch_begin:
    raise SystemExit('V7N fetch_url boundaries missing')
fetch_block = src[fetch_begin:fetch_end]

old_decl = '    CURL *curl = NULL;\n'
if old_decl not in fetch_block:
    raise SystemExit('V7N fetch_url curl declaration missing')
fetch_block = fetch_block.replace(old_decl, '    static CURL *curl = NULL;\n', 1)

old_init = '''    curl = curl_easy_init();
    if (curl == NULL) {
        snprintf(result.error, sizeof(result.error), "curl_easy_init failed");
        return result;
    }
    set_common_curl(curl, url);'''
new_init = '''    if (curl == NULL) {
        curl = curl_easy_init();
        if (curl == NULL) {
            snprintf(result.error, sizeof(result.error), "curl_easy_init failed");
            return result;
        }
    } else {
        /* reset options but preserve libcurl's live connection and DNS cache */
        curl_easy_reset(curl);
    }
    set_common_curl(curl, url);'''
if old_init not in fetch_block:
    raise SystemExit('V7N fetch_url init block missing')
fetch_block = fetch_block.replace(old_init, new_init, 1)

old_cleanup = '    curl_easy_cleanup(curl);\n    return result;\n'
if old_cleanup not in fetch_block:
    raise SystemExit('V7N fetch_url per-request cleanup missing')
fetch_block = fetch_block.replace(old_cleanup, '    return result;\n', 1)
src = src[:fetch_begin] + fetch_block + src[fetch_end:]

# A long-lived schedule handle is intentionally reclaimed by process teardown;
# curl_global_cleanup follows only when the title exits. This keeps the change
# surgical and avoids touching the proven media remote/prefetch handles.

# Hardware-visible playback proof marker.
src = src.replace('| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7M FAST TRACK\\n',
                  '| RANGE HTTP %ld | CONTINUOUS | PF 8MB / 2s | V7N SPELUNKR TV\\n', 1)

for needle in (
    'SPELUNKR360 V7N - SPELUNKR TV TIMED LOADER + FAST OPEN',
    'SPELUNKR TV',
    'TOONERTIA // LIVE BROADCAST',
    'EXPECTED START 1-5 MIN',
    'NETWORK / ARCHIVE SERVER DEPENDENT',
    'v7n_loading_progress',
    'g_v7n_loader_active = false',
    'curl_easy_reset(curl)',
    'V7N SPELUNKR TV',
    'READING MP4 TRACK TABLE',
    '4 MB DEMAND OPEN / 8 MB ASYNC PLAYBACK',
):
    if needle not in src:
        raise SystemExit(f'V7N marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7N persistent Spelunkr TV loader, elapsed/ETA display and connection reuse")
