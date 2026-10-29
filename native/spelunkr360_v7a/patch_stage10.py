#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_stage10.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

ff_marker = r'''static void ff_error_text(int code, char *out, size_t out_size)
{'''
if ff_marker not in src:
    raise SystemExit('ff_error_text marker missing')
stage_helper = r'''static uint32_t g_stage_width;
static uint32_t g_stage_height;

static void v7_stage(const char *stage)
{
    char text[768];
    if (g_stage_width == 0 || g_stage_height == 0 || stage == NULL) return;
    snprintf(text, sizeof(text),
        "SPELUNKR360 V7A.10 - LIVE VIDEO FRAME PROBE\nCH 53 - TOONERTIA\n\n%s\n\n"
        "DO NOT PRESS B WHILE THIS STAGE IS RUNNING.", stage);
    (void)present_status(g_stage_width, g_stage_height, text, GOOD_ARGB);
}

'''
src = src.replace(ff_marker, stage_helper + ff_marker, 1)

moov_curl = r'''    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_RANGE, range);'''
moov_curl_new = r'''    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_TIMEOUT_MS, 120000L);
    curl_easy_setopt(remote->curl, CURLOPT_LOW_SPEED_TIME, 30L);
    curl_easy_setopt(remote->curl, CURLOPT_BUFFERSIZE, 131072L);
    v7_stage("STAGE 1/5: DOWNLOADING 17 MB MP4 HEADER...\nTHIS CAN TAKE MORE THAN 30 SECONDS ON XBOX 360.");
    curl_easy_setopt(remote->curl, CURLOPT_RANGE, range);'''
if moov_curl not in src:
    raise SystemExit('moov curl setup marker missing')
src = src.replace(moov_curl, moov_curl_new, 1)

remote_open_call = r'''    if (remote_open(&remote, url) != 0) {
        snprintf(error, error_size, "remote open: %.180s", remote.error);'''
remote_open_new = r'''    v7_stage("STAGE 1/5: OPENING REMOTE MP4 / PREFETCHING HEADER...");
    if (remote_open(&remote, url) != 0) {
        snprintf(error, error_size, "remote open: %.180s", remote.error);'''
if remote_open_call not in src:
    raise SystemExit('remote_open call marker missing')
src = src.replace(remote_open_call, remote_open_new, 1)

open_input_call = r'''        result = avformat_open_input(&format, NULL, mov_input, NULL);
    }
    if (result < 0) {'''
open_input_new = r'''        v7_stage("STAGE 2/5: OPENING MP4 CONTAINER IN FFMPEG...");
        result = avformat_open_input(&format, NULL, mov_input, NULL);
    }
    if (result < 0) {'''
if open_input_call not in src:
    raise SystemExit('avformat_open_input marker missing')
src = src.replace(open_input_call, open_input_new, 1)

stream_info_call = r'''    result = avformat_find_stream_info(format, NULL);
    if (result < 0) {'''
stream_info_new = r'''    v7_stage("STAGE 3/5: READING VIDEO STREAM INFO...");
    result = avformat_find_stream_info(format, NULL);
    if (result < 0) {'''
if stream_info_call not in src:
    raise SystemExit('stream info marker missing')
src = src.replace(stream_info_call, stream_info_new, 1)

seek_call = r'''    result = av_seek_frame(format, video_index, target_ts, AVSEEK_FLAG_BACKWARD);
    if (result < 0) {'''
seek_new = r'''    v7_stage("STAGE 4/5: SEEKING TO LIVE TOONERTIA POSITION...");
    result = av_seek_frame(format, video_index, target_ts, AVSEEK_FLAG_BACKWARD);
    if (result < 0) {'''
if seek_call not in src:
    raise SystemExit('seek marker missing')
src = src.replace(seek_call, seek_new, 1)

decode_loop = r'''    while (!found && decoded < MAX_DECODED_FRAMES && (result = av_read_frame(format, packet)) >= 0) {'''
decode_new = r'''    v7_stage("STAGE 5/5: READING / DECODING H.264 FRAME...");
    while (!found && decoded < MAX_DECODED_FRAMES && (result = av_read_frame(format, packet)) >= 0) {'''
if decode_loop not in src:
    raise SystemExit('decode loop marker missing')
src = src.replace(decode_loop, decode_new, 1)

main_decode_call = r'''    if (decode_picture(now_result.archive_url, now_result.offset_ms, &picture, &media_size, &range_http,
            error, sizeof(error)) != 0) goto fail;'''
main_decode_new = r'''    g_stage_width = width;
    g_stage_height = height;
    if (decode_picture(now_result.archive_url, now_result.offset_ms, &picture, &media_size, &range_http,
            error, sizeof(error)) != 0) goto fail;'''
if main_decode_call not in src:
    raise SystemExit('main decode call marker missing')
src = src.replace(main_decode_call, main_decode_new, 1)

src = src.replace('SPELUNKR360 V7A.9 - LIVE VIDEO FRAME PROBE', 'SPELUNKR360 V7A.10 - LIVE VIDEO FRAME PROBE')
src = src.replace('V7A.9 - B/BACK/START RETURNS TO AURORA', 'V7A.10 - B/BACK/START RETURNS TO AURORA')

for needle in (
    'SPELUNKR360 V7A.10 - LIVE VIDEO FRAME PROBE',
    'STAGE 1/5: DOWNLOADING 17 MB MP4 HEADER',
    'STAGE 2/5: OPENING MP4 CONTAINER IN FFMPEG',
    'STAGE 3/5: READING VIDEO STREAM INFO',
    'STAGE 4/5: SEEKING TO LIVE TOONERTIA POSITION',
    'STAGE 5/5: READING / DECODING H.264 FRAME',
    'CURLOPT_TIMEOUT_MS, 120000L'):
    if needle not in src:
        raise SystemExit(f'V7A.10 marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7A.10 staged playback diagnostics and extended moov timeout")
