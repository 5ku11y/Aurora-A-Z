#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7c.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7C: first native audio + A/V sync proof.
# The proven V7B.3 path already streams, seeks, decodes and renders H.264.
# Add AAC decoding and feed float PCM to xsdk's native 48 kHz audio driver.
# Audio is the master clock; video waits/drops relative to samples actually played.

if '#include <libavutil/samplefmt.h>' not in src:
    src = src.replace('#include <libavutil/mem.h>\n', '#include <libavutil/mem.h>\n#include <libavutil/samplefmt.h>\n', 1)
if '#include "xsdk/audio.h"' not in src:
    src = src.replace('#include "schedule_core.h"\n', '#include "schedule_core.h"\n#include "xsdk/audio.h"\n', 1)

src = src.replace('SPELUNKR360 V7B.3 - STREAM-SAFE VIDEO PROBE',
                  'SPELUNKR360 V7C - AUDIO + A/V SYNC PROBE')
src = src.replace('SPELUNKR360 V7B.3 - STREAM-SAFE VIDEO PLAYBACK',
                  'SPELUNKR360 V7C - AUDIO + A/V SYNC PLAYBACK')
src = src.replace('V7B.3 - B/BACK/START RETURNS TO AURORA',
                  'V7C - B/BACK/START RETURNS TO AURORA')
src = src.replace('CONTINUOUS VIDEO TEST: PASS', 'A/V SYNC TEST: PASS')
src = src.replace('CONTINUOUS VIDEO TEST: FAIL', 'A/V SYNC TEST: FAIL')
src = src.replace('10+ SECONDS STREAM-SAFE H.264 VIDEO RENDERED',
                  '10+ SECONDS H.264 + AAC PLAYED IN SYNC')
src = src.replace('NEXT MILESTONE: AUDIO + A/V SYNC',
                  'NEXT MILESTONE: PLAYBACK QUALITY + LONG-RUN STABILITY')

start = src.find('static int play_video_continuous(')
end = src.find('\nint main(void)\n{', start)
if start < 0 or end < 0:
    raise SystemExit('V7C could not locate V7B playback function')

playback = r'''#define V7C_PLAY_MS 12000LL
#define V7C_MIN_VIDEO_FRAMES 60u
#define V7C_MAX_PACKETS 6000u
#define V7C_AUDIO_WAIT_MS 500u

struct v7c_audio_out {
    bool open;
    unsigned fill;
    float left[XSDK_AUDIO_FRAME_SAMPLES];
    float right[XSDK_AUDIO_FRAME_SAMPLES];
    uint64_t submitted_samples;
    uint64_t rate_remainder;
    int64_t first_media_ms;
    unsigned decoded_frames;
    int source_rate;
    int source_channels;
    enum AVSampleFormat source_format;
};

static float v7c_clip(float x)
{
    if (x > 1.0f) return 1.0f;
    if (x < -1.0f) return -1.0f;
    return x;
}

static int v7c_channels(const AVFrame *frame)
{
    if (frame == NULL) return 0;
    if (frame->ch_layout.nb_channels > 0) return frame->ch_layout.nb_channels;
    return 0;
}

static int v7c_audio_sample(const AVFrame *frame, int channel, int index, float *value)
{
    const int channels = v7c_channels(frame);
    if (frame == NULL || value == NULL || channels <= 0 || channel < 0 || channel >= channels ||
        index < 0 || index >= frame->nb_samples)
        return -1;
    switch ((enum AVSampleFormat)frame->format) {
        case AV_SAMPLE_FMT_FLTP:
            *value = ((const float *)frame->extended_data[channel])[index];
            return 0;
        case AV_SAMPLE_FMT_FLT:
            *value = ((const float *)frame->data[0])[index * channels + channel];
            return 0;
        case AV_SAMPLE_FMT_S16P:
            *value = ((const int16_t *)frame->extended_data[channel])[index] / 32768.0f;
            return 0;
        case AV_SAMPLE_FMT_S16:
            *value = ((const int16_t *)frame->data[0])[index * channels + channel] / 32768.0f;
            return 0;
        default:
            return -1;
    }
}

static int v7c_queue_audio_frame(struct v7c_audio_out *audio, char *error, size_t error_size)
{
    float *frame = NULL;
    NTSTATUS status;
    if (audio == NULL || audio->fill != XSDK_AUDIO_FRAME_SAMPLES) return -1;
    if (!audio->open) {
        status = xsdk_audio_open(0);
        if (!NT_SUCCESS(status)) {
            snprintf(error, error_size, "V7C xsdk_audio_open failed 0x%08X", (unsigned)status);
            return -1;
        }
        audio->open = true;
    }
    status = xsdk_audio_next_frame(V7C_AUDIO_WAIT_MS, &frame);
    if (!NT_SUCCESS(status) || frame == NULL) {
        snprintf(error, error_size, "V7C audio slot failed 0x%08X", (unsigned)status);
        return -1;
    }
    for (unsigned i = 0; i < XSDK_AUDIO_FRAME_FLOATS; i++) frame[i] = 0.0f;
    for (unsigned i = 0; i < XSDK_AUDIO_FRAME_SAMPLES; i++) {
        frame[XSDK_AUDIO_FRONT_LEFT * XSDK_AUDIO_FRAME_SAMPLES + i] = audio->left[i];
        frame[XSDK_AUDIO_FRONT_RIGHT * XSDK_AUDIO_FRAME_SAMPLES + i] = audio->right[i];
    }
    xsdk_audio_queue_frame();
    audio->submitted_samples += XSDK_AUDIO_FRAME_SAMPLES;
    audio->fill = 0;
    return 0;
}

static int v7c_push_audio(AVFrame *frame, AVStream *stream, int64_t target_ms,
    struct v7c_audio_out *audio, char *error, size_t error_size)
{
    int64_t ts, frame_ms, frame_end_ms;
    int rate, channels, skip = 0, usable;
    uint64_t scaled;
    unsigned out_samples;
    if (frame == NULL || stream == NULL || audio == NULL) return -1;
    rate = frame->sample_rate;
    if (rate <= 0) {
        snprintf(error, error_size, "V7C audio frame has no sample rate");
        return -1;
    }
    channels = v7c_channels(frame);
    if (channels <= 0 || channels > 8) {
        snprintf(error, error_size, "V7C unsupported audio channels=%d", channels);
        return -1;
    }
    if (frame->format != AV_SAMPLE_FMT_FLTP && frame->format != AV_SAMPLE_FMT_FLT &&
        frame->format != AV_SAMPLE_FMT_S16P && frame->format != AV_SAMPLE_FMT_S16) {
        snprintf(error, error_size, "V7C unsupported sample fmt=%d", frame->format);
        return -1;
    }
    ts = frame->best_effort_timestamp;
    if (ts == AV_NOPTS_VALUE) return 0;
    frame_ms = av_rescale_q(ts - (stream->start_time == AV_NOPTS_VALUE ? 0 : stream->start_time),
        stream->time_base, (AVRational){1, 1000});
    if (frame_ms < 0) frame_ms = 0;
    frame_end_ms = frame_ms + ((int64_t)frame->nb_samples * 1000LL) / rate;
    if (frame_end_ms + 20 < target_ms) return 0;
    if (frame_ms < target_ms) {
        int64_t delta = target_ms - frame_ms;
        skip = (int)((delta * rate) / 1000LL);
        if (skip >= frame->nb_samples) return 0;
    }
    usable = frame->nb_samples - skip;
    if (audio->first_media_ms < 0)
        audio->first_media_ms = frame_ms + ((int64_t)skip * 1000LL) / rate;
    audio->source_rate = rate;
    audio->source_channels = channels;
    audio->source_format = (enum AVSampleFormat)frame->format;
    audio->decoded_frames++;

    scaled = (uint64_t)usable * XSDK_AUDIO_RATE_HZ + audio->rate_remainder;
    out_samples = (unsigned)(scaled / (uint64_t)rate);
    audio->rate_remainder = scaled % (uint64_t)rate;
    if (out_samples == 0) return 0;

    for (unsigned o = 0; o < out_samples; o++) {
        unsigned rel = (unsigned)(((uint64_t)o * (uint64_t)rate) / XSDK_AUDIO_RATE_HZ);
        int in_index = skip + (int)rel;
        float left = 0.0f, right = 0.0f;
        if (in_index >= frame->nb_samples) in_index = frame->nb_samples - 1;
        if (v7c_audio_sample(frame, 0, in_index, &left) != 0) {
            snprintf(error, error_size, "V7C audio sample conversion failed");
            return -1;
        }
        if (channels > 1) {
            if (v7c_audio_sample(frame, 1, in_index, &right) != 0) {
                snprintf(error, error_size, "V7C right audio conversion failed");
                return -1;
            }
        } else {
            right = left;
        }
        audio->left[audio->fill] = v7c_clip(left);
        audio->right[audio->fill] = v7c_clip(right);
        audio->fill++;
        if (audio->fill == XSDK_AUDIO_FRAME_SAMPLES &&
            v7c_queue_audio_frame(audio, error, error_size) != 0)
            return -1;
    }
    return 0;
}

static int64_t v7c_audio_clock_ms(const struct v7c_audio_out *audio, XsdkAudioStats *stats)
{
    XsdkAudioStats local = {0};
    if (audio == NULL || !audio->open || audio->first_media_ms < 0) return -1;
    xsdk_audio_stats(&local);
    if (stats != NULL) *stats = local;
    return audio->first_media_ms +
        ((int64_t)local.played * XSDK_AUDIO_FRAME_SAMPLES * 1000LL) / XSDK_AUDIO_RATE_HZ;
}

static void v7c_sleep_ms(uint32_t milliseconds)
{
    if (milliseconds == 0) return;
    const int64_t interval = -(int64_t)milliseconds * 10000LL;
    (void)KeDelayExecutionThread(USER_MODE, 0, &interval);
}

static int play_av_continuous(const char *url, int64_t target_ms,
    const char *title, const char *year, uint32_t screen_width, uint32_t screen_height,
    int64_t *remote_size, long *range_http, char *error, size_t error_size)
{
    struct remote_file remote;
    AVIOContext *avio = NULL;
    AVFormatContext *format = NULL;
    AVCodecContext *video_decoder = NULL, *audio_decoder = NULL;
    AVFrame *video_frame = NULL, *audio_frame = NULL;
    AVPacket *packet = NULL;
    uint8_t *avio_buffer = NULL;
    const AVCodec *video_codec = NULL, *audio_codec = NULL;
    AVStream *video_stream = NULL, *audio_stream = NULL;
    VideoRenderer renderer;
    struct decoded_picture picture;
    struct v7c_audio_out audio;
    bool renderer_ready = false;
    int video_index = -1, audio_index = -1;
    int result = 0;
    int64_t video_start_ts = 0, target_ts = 0;
    int64_t first_video_ms = -1, last_video_ms = -1;
    unsigned rendered_frames = 0, dropped_frames = 0, packets = 0;
    char fferr[128], overlay[1200], target_text[32], current_text[32];
    XsdkAudioStats audio_stats = {0};

    memset(&remote, 0, sizeof(remote));
    memset(&renderer, 0, sizeof(renderer));
    memset(&picture, 0, sizeof(picture));
    memset(&audio, 0, sizeof(audio));
    audio.first_media_ms = -1;

    if (remote_open(&remote, url) != 0) {
        snprintf(error, error_size, "remote open: %.180s", remote.error);
        remote_close(&remote);
        return -1;
    }
    if (remote_size != NULL) *remote_size = remote.size;

    avio_buffer = av_malloc(AVIO_BUFFER_BYTES);
    if (avio_buffer == NULL) { snprintf(error, error_size, "V7C AVIO allocation failed"); goto fail; }
    avio = avio_alloc_context(avio_buffer, AVIO_BUFFER_BYTES, 0, &remote,
        avio_remote_read, NULL, avio_remote_seek);
    if (avio == NULL) { snprintf(error, error_size, "V7C avio_alloc_context failed"); av_free(avio_buffer); avio_buffer = NULL; goto fail; }
    avio_buffer = NULL;
    format = avformat_alloc_context();
    if (format == NULL) { snprintf(error, error_size, "V7C format allocation failed"); goto fail; }
    format->pb = avio;
    format->flags |= AVFMT_FLAG_CUSTOM_IO;
    avio->seekable = 0;
    format->probesize = 24 * 1024 * 1024;
    format->max_analyze_duration = 5LL * AV_TIME_BASE;
    result = avformat_open_input(&format, NULL, NULL, NULL);
    if (result < 0) { ff_error_text(result, fferr, sizeof(fferr)); snprintf(error, error_size, "V7C MP4 open failed: %s", fferr); goto fail; }
    avio->seekable = AVIO_SEEKABLE_NORMAL;
    avio->eof_reached = 0;
    avio->error = 0;
    result = avformat_find_stream_info(format, NULL);
    if (result < 0) { ff_error_text(result, fferr, sizeof(fferr)); snprintf(error, error_size, "V7C stream info failed: %s", fferr); goto fail; }

    video_index = av_find_best_stream(format, AVMEDIA_TYPE_VIDEO, -1, -1, NULL, 0);
    audio_index = av_find_best_stream(format, AVMEDIA_TYPE_AUDIO, -1, video_index, NULL, 0);
    if (video_index < 0 || audio_index < 0) {
        snprintf(error, error_size, "V7C streams missing video=%d audio=%d", video_index, audio_index);
        goto fail;
    }
    video_stream = format->streams[video_index];
    audio_stream = format->streams[audio_index];
    video_codec = avcodec_find_decoder(video_stream->codecpar->codec_id);
    audio_codec = avcodec_find_decoder(audio_stream->codecpar->codec_id);
    if (video_codec == NULL || audio_codec == NULL) {
        snprintf(error, error_size, "V7C decoder missing video=%d audio=%d",
            video_stream->codecpar->codec_id, audio_stream->codecpar->codec_id);
        goto fail;
    }
    video_decoder = avcodec_alloc_context3(video_codec);
    audio_decoder = avcodec_alloc_context3(audio_codec);
    if (video_decoder == NULL || audio_decoder == NULL) { snprintf(error, error_size, "V7C decoder allocation failed"); goto fail; }
    if ((result = avcodec_parameters_to_context(video_decoder, video_stream->codecpar)) < 0 ||
        (result = avcodec_parameters_to_context(audio_decoder, audio_stream->codecpar)) < 0) {
        ff_error_text(result, fferr, sizeof(fferr)); snprintf(error, error_size, "V7C decoder parameters failed: %s", fferr); goto fail;
    }
    video_decoder->thread_count = 1;
    video_decoder->skip_loop_filter = AVDISCARD_ALL;
    if ((result = avcodec_open2(video_decoder, video_codec, NULL)) < 0) {
        ff_error_text(result, fferr, sizeof(fferr)); snprintf(error, error_size, "V7C video decoder open failed: %s", fferr); goto fail;
    }
    if ((result = avcodec_open2(audio_decoder, audio_codec, NULL)) < 0) {
        ff_error_text(result, fferr, sizeof(fferr)); snprintf(error, error_size, "V7C audio decoder open failed: %s", fferr); goto fail;
    }
    video_frame = av_frame_alloc();
    audio_frame = av_frame_alloc();
    packet = av_packet_alloc();
    if (video_frame == NULL || audio_frame == NULL || packet == NULL) { snprintf(error, error_size, "V7C frame/packet allocation failed"); goto fail; }

    video_start_ts = video_stream->start_time == AV_NOPTS_VALUE ? 0 : video_stream->start_time;
    target_ts = video_start_ts + av_rescale_q(target_ms, (AVRational){1, 1000}, video_stream->time_base);
    {
        size_t capacity = 16u * 1024u * 1024u;
        if (remote.size > 0 && remote.size < (int64_t)capacity) capacity = (size_t)remote.size;
        if (remote.cache_capacity < capacity) {
            uint8_t *grown = realloc(remote.cache, capacity);
            if (grown == NULL) { snprintf(error, error_size, "V7C 16 MB cache allocation failed"); goto fail; }
            remote.cache = grown;
            remote.cache_capacity = capacity;
        }
        remote.range_chunk = 4u * 1024u * 1024u;
    }
    result = av_seek_frame(format, video_index, target_ts, AVSEEK_FLAG_BACKWARD);
    if (result < 0) { ff_error_text(result, fferr, sizeof(fferr)); snprintf(error, error_size, "V7C seek failed: %s remote=%.90s", fferr, remote.error); goto fail; }
    avio->eof_reached = 0;
    avio->error = 0;
    avcodec_flush_buffers(video_decoder);
    avcodec_flush_buffers(audio_decoder);
    format_hms(target_ms, target_text, sizeof(target_text));

    while (!wants_exit() && packets++ < V7C_MAX_PACKETS && (result = av_read_frame(format, packet)) >= 0) {
        if (packet->stream_index == audio_index) {
            int send = avcodec_send_packet(audio_decoder, packet);
            av_packet_unref(packet);
            if (send < 0 && send != AVERROR(EAGAIN)) continue;
            while ((send = avcodec_receive_frame(audio_decoder, audio_frame)) >= 0) {
                if (v7c_push_audio(audio_frame, audio_stream, target_ms, &audio, error, error_size) != 0) goto fail;
                av_frame_unref(audio_frame);
            }
        } else if (packet->stream_index == video_index) {
            int send = avcodec_send_packet(video_decoder, packet);
            av_packet_unref(packet);
            if (send < 0 && send != AVERROR(EAGAIN)) continue;
            while ((send = avcodec_receive_frame(video_decoder, video_frame)) >= 0) {
                int64_t ts = video_frame->best_effort_timestamp;
                int64_t actual_ms = 0, audio_clock, sync_ms;
                if (ts != AV_NOPTS_VALUE)
                    actual_ms = av_rescale_q(ts - video_start_ts, video_stream->time_base, (AVRational){1, 1000});
                if (actual_ms < 0) actual_ms = 0;
                if (actual_ms + 250 < target_ms || !audio.open || audio.first_media_ms < 0) {
                    av_frame_unref(video_frame);
                    continue;
                }
                audio_clock = v7c_audio_clock_ms(&audio, &audio_stats);
                while (audio_clock >= 0 && actual_ms > audio_clock + 35 && !wants_exit()) {
                    v7c_sleep_ms(2);
                    audio_clock = v7c_audio_clock_ms(&audio, &audio_stats);
                }
                sync_ms = audio_clock >= 0 ? actual_ms - audio_clock : 0;
                if (audio_clock >= 0 && actual_ms + 180 < audio_clock && rendered_frames > 0) {
                    dropped_frames++;
                    av_frame_unref(video_frame);
                    continue;
                }

                picture.width = video_frame->width;
                picture.height = video_frame->height;
                picture.pixel_format = video_frame->format;
                picture.actual_ms = actual_ms;
                picture.target_ms = target_ms;
                snprintf(picture.codec, sizeof(picture.codec), "%s", video_codec->name ? video_codec->name : "h264");
                if (frame_to_argb(video_frame, &picture.argb, error, error_size) != 0) goto fail;
                if (!renderer_ready) {
                    if (!renderer_open(&renderer, picture.width, picture.height, screen_width, screen_height, error, error_size)) goto fail;
                    renderer_ready = true;
                    first_video_ms = actual_ms;
                }
                format_hms(actual_ms, current_text, sizeof(current_text));
                snprintf(overlay, sizeof(overlay),
                    "SPELUNKR360 V7C - AUDIO + A/V SYNC PLAYBACK\n"
                    "CH 53 TOONERTIA | %s (%s)\n"
                    "TARGET %s | VIDEO %s | FRAME %u DROP %u | A/V %+" PRId64 "ms\n"
                    "AUDIO %s %dHz %dch | PLAYED %u SILENT %u | RANGE HTTP %ld\n"
                    "B/BACK/START: RETURN TO AURORA",
                    title, year, target_text, current_text, rendered_frames + 1u, dropped_frames, sync_ms,
                    audio_codec->name ? audio_codec->name : "audio", audio.source_rate, audio.source_channels,
                    audio_stats.played, audio_stats.silent, remote.last_http);
                if (!NT_SUCCESS(render_picture(&renderer, &picture, screen_width, screen_height, overlay))) {
                    snprintf(error, error_size, "V7C render_picture failed");
                    goto fail;
                }
                rendered_frames++;
                last_video_ms = actual_ms;
                free(picture.argb);
                picture.argb = NULL;
                av_frame_unref(video_frame);

                if (audio_clock >= audio.first_media_ms + V7C_PLAY_MS) goto stopped;
            }
        } else {
            av_packet_unref(packet);
        }
    }

stopped:
    if (range_http != NULL) *range_http = remote.last_http;
    if (audio.open) xsdk_audio_stats(&audio_stats);
    {
        int64_t audio_span = ((int64_t)audio_stats.played * XSDK_AUDIO_FRAME_SAMPLES * 1000LL) / XSDK_AUDIO_RATE_HZ;
        int64_t video_span = first_video_ms >= 0 && last_video_ms >= first_video_ms ? last_video_ms - first_video_ms : 0;
        if (renderer_ready && audio.open && rendered_frames >= V7C_MIN_VIDEO_FRAMES &&
            audio_span >= 9000 && video_span >= 8500) {
            xsdk_log_write("Spelunkr360 V7C PASS: video=%u drop=%u vspan=%" PRId64
                " audio_frames=%u silence=%u aspan=%" PRId64 " rate=%d ch=%d HTTP=%ld",
                rendered_frames, dropped_frames, video_span, audio_stats.played, audio_stats.silent,
                audio_span, audio.source_rate, audio.source_channels, remote.last_http);
            if (audio.open) (void)xsdk_audio_close();
            renderer_close(&renderer);
            av_packet_free(&packet);
            av_frame_free(&video_frame);
            av_frame_free(&audio_frame);
            avcodec_free_context(&video_decoder);
            avcodec_free_context(&audio_decoder);
            avformat_close_input(&format);
            avio_context_free(&avio);
            remote_close(&remote);
            return 0;
        }
        snprintf(error, error_size,
            "V7C playback short: video=%u drop=%u vspan=%" PRId64
            " audio=%u silent=%u aspan=%" PRId64 "ms",
            rendered_frames, dropped_frames, video_span,
            audio_stats.played, audio_stats.silent, audio_span);
    }

fail:
    if (range_http != NULL) *range_http = remote.last_http;
    free(picture.argb);
    if (audio.open) (void)xsdk_audio_close();
    if (renderer_ready) renderer_close(&renderer);
    if (packet != NULL) av_packet_free(&packet);
    if (video_frame != NULL) av_frame_free(&video_frame);
    if (audio_frame != NULL) av_frame_free(&audio_frame);
    if (video_decoder != NULL) avcodec_free_context(&video_decoder);
    if (audio_decoder != NULL) avcodec_free_context(&audio_decoder);
    if (format != NULL) avformat_close_input(&format);
    if (avio != NULL) avio_context_free(&avio);
    else if (avio_buffer != NULL) av_free(avio_buffer);
    remote_close(&remote);
    return -1;
}

'''

src = src[:start] + playback + src[end + 1:]
src = src.replace('play_video_continuous(', 'play_av_continuous(')

for needle in (
    'SPELUNKR360 V7C - AUDIO + A/V SYNC PROBE',
    'SPELUNKR360 V7C - AUDIO + A/V SYNC PLAYBACK',
    'xsdk_audio_open(0)',
    'xsdk_audio_next_frame',
    'AVMEDIA_TYPE_AUDIO',
    'v7c_audio_clock_ms',
    'A/V SYNC TEST: PASS',
):
    if needle not in src:
        raise SystemExit(f'V7C marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7C AAC decode, xsdk PCM output, and audio-master A/V sync")
