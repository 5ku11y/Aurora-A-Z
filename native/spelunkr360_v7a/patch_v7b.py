#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7b.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# The proven V7A.14 source already opens/seeks/decodes the live Archive MP4.
# V7B keeps that path and adds a second persistent decoder path that presents
# sequential H.264 frames for ten seconds, paced from their media timestamps.
src = src.replace('SPELUNKR360 V7A.14 - LIVE VIDEO FRAME PROBE',
                  'SPELUNKR360 V7B - CONTINUOUS VIDEO PROBE')
src = src.replace('V7A.14 - B/BACK/START RETURNS TO AURORA',
                  'V7B - B/BACK/START RETURNS TO AURORA')
src = src.replace('static int decode_picture(',
                  'static __attribute__((unused)) int decode_picture(', 1)

marker = r'''int main(void)
{'''
if marker not in src:
    raise SystemExit('V7B main marker missing')

playback = r'''
#define V7B_PLAY_MS 10000LL
#define V7B_MIN_FRAMES 60u
#define V7B_MAX_DECODED_FRAMES 1800u

static int64_t v7b_wall_ms(void)
{
    uint64_t ticks = 0;
    KeQuerySystemTime(&ticks);
    return (int64_t)(ticks / 10000ULL);
}

static void v7b_sleep_ms(uint32_t milliseconds)
{
    if (milliseconds == 0) return;
    const int64_t interval = -(int64_t)milliseconds * 10000LL;
    (void)KeDelayExecutionThread(USER_MODE, 0, &interval);
}

static int play_video_continuous(const char *url, int64_t target_ms,
    const char *title, const char *year, uint32_t screen_width, uint32_t screen_height,
    int64_t *remote_size, long *range_http, char *error, size_t error_size)
{
    struct remote_file remote;
    AVIOContext *avio = NULL;
    AVFormatContext *format = NULL;
    AVCodecContext *decoder = NULL;
    AVFrame *frame = NULL;
    AVPacket *packet = NULL;
    uint8_t *avio_buffer = NULL;
    const AVCodec *codec = NULL;
    AVStream *stream = NULL;
    VideoRenderer renderer;
    struct decoded_picture picture;
    bool renderer_ready = false;
    int video_index = -1;
    int result = 0;
    int64_t target_ts = 0, start_ts = 0;
    int64_t first_media_ms = -1, last_media_ms = -1, wall_start_ms = -1;
    unsigned decoded_frames = 0, rendered_frames = 0, dropped_frames = 0;
    char fferr[128];
    char overlay[1024];
    char target_text[32], current_text[32];

    memset(&remote, 0, sizeof(remote));
    memset(&renderer, 0, sizeof(renderer));
    memset(&picture, 0, sizeof(picture));
    if (remote_open(&remote, url) != 0) {
        snprintf(error, error_size, "remote open: %.180s", remote.error);
        remote_close(&remote);
        return -1;
    }
    if (remote_size != NULL) *remote_size = remote.size;

    avio_buffer = av_malloc(AVIO_BUFFER_BYTES);
    if (avio_buffer == NULL) {
        snprintf(error, error_size, "V7B AVIO buffer allocation failed");
        goto fail;
    }
    avio = avio_alloc_context(avio_buffer, AVIO_BUFFER_BYTES, 0, &remote,
        avio_remote_read, NULL, avio_remote_seek);
    if (avio == NULL) {
        snprintf(error, error_size, "V7B avio_alloc_context failed");
        av_free(avio_buffer);
        avio_buffer = NULL;
        goto fail;
    }
    avio_buffer = NULL;
    format = avformat_alloc_context();
    if (format == NULL) {
        snprintf(error, error_size, "V7B avformat_alloc_context failed");
        goto fail;
    }
    format->pb = avio;
    format->flags |= AVFMT_FLAG_CUSTOM_IO;
    avio->seekable = 0;
    format->probesize = 24 * 1024 * 1024;
    format->max_analyze_duration = 5LL * AV_TIME_BASE;
    result = avformat_open_input(&format, NULL, NULL, NULL);
    if (result < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size, "V7B MP4 open failed: %s; remote=%.110s", fferr, remote.error);
        goto fail;
    }
    avio->seekable = AVIO_SEEKABLE_NORMAL;
    avio->eof_reached = 0;
    avio->error = 0;
    result = avformat_find_stream_info(format, NULL);
    if (result < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size, "V7B stream info failed: %s", fferr);
        goto fail;
    }
    video_index = av_find_best_stream(format, AVMEDIA_TYPE_VIDEO, -1, -1, NULL, 0);
    if (video_index < 0) {
        ff_error_text(video_index, fferr, sizeof(fferr));
        snprintf(error, error_size, "V7B no video stream: %s", fferr);
        goto fail;
    }
    stream = format->streams[video_index];
    codec = avcodec_find_decoder(stream->codecpar->codec_id);
    if (codec == NULL) {
        snprintf(error, error_size, "V7B codec id %d not enabled", stream->codecpar->codec_id);
        goto fail;
    }
    decoder = avcodec_alloc_context3(codec);
    if (decoder == NULL) {
        snprintf(error, error_size, "V7B decoder allocation failed");
        goto fail;
    }
    if ((result = avcodec_parameters_to_context(decoder, stream->codecpar)) < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size, "V7B decoder parameters failed: %s", fferr);
        goto fail;
    }
    decoder->thread_count = 1;
    decoder->skip_loop_filter = AVDISCARD_ALL;
    if ((result = avcodec_open2(decoder, codec, NULL)) < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size, "V7B decoder open failed: %s", fferr);
        goto fail;
    }
    frame = av_frame_alloc();
    packet = av_packet_alloc();
    if (frame == NULL || packet == NULL) {
        snprintf(error, error_size, "V7B frame/packet allocation failed");
        goto fail;
    }

    start_ts = stream->start_time == AV_NOPTS_VALUE ? 0 : stream->start_time;
    target_ts = start_ts + av_rescale_q(target_ms, (AVRational){ 1, 1000 }, stream->time_base);
    result = av_seek_frame(format, video_index, target_ts, AVSEEK_FLAG_BACKWARD);
    if (result < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size, "V7B media seek failed: %s", fferr);
        goto fail;
    }
    avcodec_flush_buffers(decoder);
    format_hms(target_ms, target_text, sizeof(target_text));

    while (decoded_frames < V7B_MAX_DECODED_FRAMES && !wants_exit() &&
           (result = av_read_frame(format, packet)) >= 0) {
        if (packet->stream_index != video_index) {
            av_packet_unref(packet);
            continue;
        }
        result = avcodec_send_packet(decoder, packet);
        av_packet_unref(packet);
        if (result < 0 && result != AVERROR(EAGAIN)) continue;

        while ((result = avcodec_receive_frame(decoder, frame)) >= 0) {
            int64_t ts = frame->best_effort_timestamp;
            int64_t actual_ms = 0;
            int64_t desired_ms, elapsed_ms, late_ms;
            decoded_frames++;
            if (ts != AV_NOPTS_VALUE)
                actual_ms = av_rescale_q(ts - start_ts, stream->time_base, (AVRational){ 1, 1000 });
            if (actual_ms < 0) actual_ms = 0;
            if (actual_ms + 250 < target_ms) {
                av_frame_unref(frame);
                continue;
            }

            picture.width = frame->width;
            picture.height = frame->height;
            picture.pixel_format = frame->format;
            picture.actual_ms = actual_ms;
            picture.target_ms = target_ms;
            snprintf(picture.codec, sizeof(picture.codec), "%s", codec->name != NULL ? codec->name : "unknown");
            if (frame_to_argb(frame, &picture.argb, error, error_size) != 0)
                goto fail;

            if (!renderer_ready) {
                if (!renderer_open(&renderer, picture.width, picture.height,
                        screen_width, screen_height, error, error_size))
                    goto fail;
                renderer_ready = true;
                first_media_ms = actual_ms;
                wall_start_ms = v7b_wall_ms();
            }

            desired_ms = actual_ms - first_media_ms;
            if (desired_ms < 0) desired_ms = 0;
            for (;;) {
                elapsed_ms = v7b_wall_ms() - wall_start_ms;
                if (elapsed_ms >= desired_ms || wants_exit()) break;
                {
                    int64_t left = desired_ms - elapsed_ms;
                    uint32_t nap = (uint32_t)(left > 10 ? 10 : left);
                    v7b_sleep_ms(nap);
                }
            }
            if (wants_exit()) {
                free(picture.argb);
                picture.argb = NULL;
                goto stopped;
            }
            elapsed_ms = v7b_wall_ms() - wall_start_ms;
            late_ms = elapsed_ms - desired_ms;
            if (late_ms > 250 && rendered_frames > 0) {
                dropped_frames++;
                free(picture.argb);
                picture.argb = NULL;
                av_frame_unref(frame);
                if (desired_ms >= V7B_PLAY_MS) goto stopped;
                continue;
            }

            format_hms(actual_ms, current_text, sizeof(current_text));
            snprintf(overlay, sizeof(overlay),
                "SPELUNKR360 V7B - CONTINUOUS VIDEO PLAYBACK\n"
                "CH 53 TOONERTIA | %s (%s)\n"
                "LIVE TARGET %s | CURRENT %s | FRAME %u | DROP %u | H.264 VIDEO ONLY\n"
                "B/BACK/START: RETURN TO AURORA",
                title, year, target_text, current_text, rendered_frames + 1u, dropped_frames);
            if (!NT_SUCCESS(render_picture(&renderer, &picture, screen_width, screen_height, overlay))) {
                snprintf(error, error_size, "V7B render_picture failed");
                goto fail;
            }
            rendered_frames++;
            last_media_ms = actual_ms;
            free(picture.argb);
            picture.argb = NULL;
            av_frame_unref(frame);

            if (desired_ms >= V7B_PLAY_MS) goto stopped;
        }
    }

stopped:
    if (range_http != NULL) *range_http = remote.last_http;
    if (renderer_ready && rendered_frames >= V7B_MIN_FRAMES &&
        first_media_ms >= 0 && last_media_ms - first_media_ms >= 9000) {
        xsdk_log_write("Spelunkr360 V7B PASS: rendered=%u dropped=%u media_span=%" PRId64
            "ms target=%" PRId64 " HTTP=%ld", rendered_frames, dropped_frames,
            last_media_ms - first_media_ms, target_ms, remote.last_http);
        renderer_close(&renderer);
        av_packet_free(&packet);
        av_frame_free(&frame);
        avcodec_free_context(&decoder);
        avformat_close_input(&format);
        avio_context_free(&avio);
        remote_close(&remote);
        return 0;
    }
    snprintf(error, error_size,
        "V7B playback short: rendered=%u dropped=%u span=%" PRId64 "ms",
        rendered_frames, dropped_frames,
        first_media_ms >= 0 && last_media_ms >= first_media_ms ? last_media_ms - first_media_ms : 0);

fail:
    if (range_http != NULL) *range_http = remote.last_http;
    free(picture.argb);
    if (renderer_ready) renderer_close(&renderer);
    if (packet != NULL) av_packet_free(&packet);
    if (frame != NULL) av_frame_free(&frame);
    if (decoder != NULL) avcodec_free_context(&decoder);
    if (format != NULL) avformat_close_input(&format);
    if (avio != NULL) avio_context_free(&avio);
    else if (avio_buffer != NULL) av_free(avio_buffer);
    remote_close(&remote);
    return -1;
}

'''
src = src.replace(marker, playback + marker, 1)

src = src.replace('    struct decoded_picture picture;\n    VideoRenderer renderer;\n', '')
src = src.replace('    char error[512] = { 0 }, status_text[3400], overlay[1024], target_text[32], actual_text[32];\n',
                  '    char error[512] = { 0 }, status_text[3400], target_text[32];\n')
src = src.replace('    bool curl_ready = false, renderer_ready = false;\n',
                  '    bool curl_ready = false;\n')
src = src.replace('    memset(&picture, 0, sizeof(picture));\n    memset(&renderer, 0, sizeof(renderer));\n', '')

old_success = r'''    if (decode_picture(now_result.archive_url, now_result.offset_ms, &picture, &media_size, &range_http,
            error, sizeof(error)) != 0) goto fail;
    if (!renderer_open(&renderer, picture.width, picture.height, width, height, error, sizeof(error))) goto fail;
    renderer_ready = true;

    format_hms(picture.actual_ms, actual_text, sizeof(actual_text));
    snprintf(overlay, sizeof(overlay),
        "SPELUNKR360 V7A - DECODED ARCHIVE.ORG FRAME - PASS\n"
        "CH 53 TOONERTIA | %s (%s)\n"
        "TARGET %s | DECODED %s | %dx%d | %s | RANGE HTTP %ld\n"
        "B/BACK/START: RETURN TO AURORA",
        now_result.title, now_result.year, target_text, actual_text,
        picture.width, picture.height, picture.codec, range_http);
    xsdk_log_write("Spelunkr360 V7A PASS: title=%s target=%" PRId64 " actual=%" PRId64
        " size=%" PRId64 " dims=%dx%d codec=%s HTTP=%ld url=%s",
        now_result.title, now_result.offset_ms, picture.actual_ms, media_size,
        picture.width, picture.height, picture.codec, range_http, now_result.archive_url);

    for (frame = 0; frame < 1800 && !wants_exit(); frame++) {
        status = render_picture(&renderer, &picture, width, height, overlay);
        if (!NT_SUCCESS(status)) break;
    }

    renderer_close(&renderer);
    free(picture.argb);'''
new_success = r'''    if (play_video_continuous(now_result.archive_url, now_result.offset_ms,
            now_result.title, now_result.year, width, height,
            &media_size, &range_http, error, sizeof(error)) != 0) goto fail;

    snprintf(status_text, sizeof(status_text),
        "SPELUNKR360 V7B - CONTINUOUS VIDEO PLAYBACK\nCH 53 - TOONERTIA\n\n"
        "CONTINUOUS VIDEO TEST: PASS\n"
        "10+ SECONDS OF LIVE H.264 VIDEO RENDERED\n"
        "RANGE HTTP: %ld\nMEDIA SIZE: %" PRId64 " BYTES\n\n"
        "NEXT MILESTONE: AUDIO + A/V SYNC\n\n"
        "B/BACK/START: RETURN TO AURORA",
        range_http, media_size);
    xsdk_log_write("Spelunkr360 V7B PASS: title=%s target=%" PRId64
        " size=%" PRId64 " HTTP=%ld url=%s",
        now_result.title, now_result.offset_ms, media_size, range_http, now_result.archive_url);
    for (frame = 0; frame < 600 && !wants_exit(); frame++)
        (void)present_status(width, height, status_text, GOOD_ARGB);'''
if old_success not in src:
    raise SystemExit('V7B old single-frame success block missing')
src = src.replace(old_success, new_success, 1)

src = src.replace('    if (renderer_ready) renderer_close(&renderer);\n    free(picture.argb);\n', '')
src = src.replace('VIDEO FRAME TEST: FAIL', 'CONTINUOUS VIDEO TEST: FAIL')
src = src.replace('Spelunkr360 V7A FAIL:', 'Spelunkr360 V7B FAIL:')

for needle in (
    'SPELUNKR360 V7B - CONTINUOUS VIDEO PROBE',
    'play_video_continuous',
    'SPELUNKR360 V7B - CONTINUOUS VIDEO PLAYBACK',
    'CONTINUOUS VIDEO TEST: PASS',
    '10+ SECONDS OF LIVE H.264 VIDEO RENDERED',
    'NEXT MILESTONE: AUDIO + A/V SYNC',
    'V7B playback short',
):
    if needle not in src:
        raise SystemExit(f'V7B marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7B persistent 10-second H.264 playback loop")
