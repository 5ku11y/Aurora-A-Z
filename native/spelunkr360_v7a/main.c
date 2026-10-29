/* Spelunkr360 V7A - live Archive.org H.264 first-frame playback proof. */
#include <curl/curl.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/avutil.h>
#include <libavutil/error.h>
#include <libavutil/mem.h>

#include "schedule_core.h"
#include "Spelunkr360V7A_shaders.h"
#include "xsdk/gpu.h"
#include "xsdk/kernel.h"
#include "xsdk/log.h"
#include "xsdk/present.h"
#include "xsdk/shader.h"
#include "xsdk/text.h"
#include "xsdk/texture.h"

#define BODY_BYTES (1024u * 1024u)
#define REMOTE_CACHE_BYTES (256u * 1024u)
#define AVIO_BUFFER_BYTES (64u * 1024u)
#define MAX_DECODED_FRAMES 900

enum {
    BUFFERS = 2,
    SWAP_INTERVAL = 1,
    BEGIN_TIMEOUT_MS = 5000,
    BACKGROUND_ARGB = 0xFF000000,
    TEXT_ARGB = 0xFFF0F0E8,
    GOOD_ARGB = 0xFF8FE388,
    BAD_ARGB = 0xFFFF8070,
    QUAD_VERTICES = 6,
    VERTEX_FLOATS = 6,
    VERTEX_BYTES = VERTEX_FLOATS * 4,
    QUAD_BYTES = QUAD_VERTICES * VERTEX_BYTES,
    UV_OFFSET_BYTES = 16,
};

static const char *const BUCKET_URL =
    "https://jbuopkuluyfjwgsrigry.supabase.co/storage/v1/object/public/broadcast/";
static const char *const LINEUP_URL =
    "https://jbuopkuluyfjwgsrigry.supabase.co/storage/v1/object/public/broadcast/lineup.json";
static const char *const CA_FILE = "cacert.pem";

struct response_buffer {
    char *data;
    size_t capacity;
    size_t size;
    bool overflow;
};

struct http_result {
    CURLcode curl_code;
    long http_code;
    size_t bytes;
    char error[CURL_ERROR_SIZE];
    char date_header[96];
    int64_t server_ms;
};

struct remote_file {
    char url[SP_URL_BYTES];
    CURL *curl;
    uint8_t *cache;
    size_t cache_capacity;
    size_t cache_length;
    int64_t cache_start;
    int64_t position;
    int64_t size;
    long last_http;
    char curl_error[CURL_ERROR_SIZE];
    char error[256];
};

struct decoded_picture {
    uint32_t *argb;
    int width;
    int height;
    int pixel_format;
    int64_t actual_ms;
    int64_t target_ms;
    char codec[48];
};

typedef struct {
    XsdkShader vertex;
    XsdkShader pixel;
    XsdkTexture texture;
    XsdkSamplerState sampler;
    volatile uint32_t *vertices;
} VideoRenderer;

static const XsdkVertexElement video_layout[] = {
    { .usage = XSDK_USAGE_POSITION, .usage_index = 0, .format = XSDK_VERTEX_FLOAT4, .offset_bytes = 0 },
    { .usage = XSDK_USAGE_TEXCOORD, .usage_index = 0, .format = XSDK_VERTEX_FLOAT2, .offset_bytes = UV_OFFSET_BYTES },
};

static size_t on_body(char *data, size_t size, size_t count, void *user)
{
    struct response_buffer *body = user;
    const size_t length = size * count;
    if (body == NULL || body->data == NULL || body->capacity == 0)
        return 0;
    if (body->size >= body->capacity - 1u || length > body->capacity - 1u - body->size) {
        body->overflow = true;
        return 0;
    }
    memcpy(body->data + body->size, data, length);
    body->size += length;
    body->data[body->size] = '\0';
    return length;
}

static unsigned char ascii_lower(unsigned char c)
{
    return (c >= 'A' && c <= 'Z') ? (unsigned char)(c + ('a' - 'A')) : c;
}

static size_t on_header(char *data, size_t size, size_t count, void *user)
{
    struct http_result *result = user;
    const size_t length = size * count;
    size_t begin, end, copy;
    if (result == NULL || data == NULL || length < 5u)
        return length;
    if (ascii_lower((unsigned char)data[0]) != 'd' ||
        ascii_lower((unsigned char)data[1]) != 'a' ||
        ascii_lower((unsigned char)data[2]) != 't' ||
        ascii_lower((unsigned char)data[3]) != 'e' || data[4] != ':')
        return length;
    begin = 5u;
    while (begin < length && (data[begin] == ' ' || data[begin] == '\t')) begin++;
    end = length;
    while (end > begin && (data[end - 1u] == '\r' || data[end - 1u] == '\n' ||
           data[end - 1u] == ' ' || data[end - 1u] == '\t')) end--;
    copy = end - begin;
    if (copy >= sizeof(result->date_header)) copy = sizeof(result->date_header) - 1u;
    memcpy(result->date_header, data + begin, copy);
    result->date_header[copy] = '\0';
    return length;
}

static void set_common_curl(CURL *curl, const char *url)
{
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_CAINFO, CA_FILE);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 15000L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 45000L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, 1L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 15L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "Spelunkr360/0.7.0 (Xbox 360 homebrew)");
}

static struct http_result fetch_url(const char *url, struct response_buffer *body)
{
    struct http_result result;
    CURL *curl = NULL;
    time_t server_time;
    memset(&result, 0, sizeof(result));
    result.curl_code = CURLE_FAILED_INIT;
    result.server_ms = -1;
    body->size = 0;
    body->overflow = false;
    body->data[0] = '\0';
    curl = curl_easy_init();
    if (curl == NULL) {
        snprintf(result.error, sizeof(result.error), "curl_easy_init failed");
        return result;
    }
    set_common_curl(curl, url);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, on_body);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, body);
    curl_easy_setopt(curl, CURLOPT_HEADERFUNCTION, on_header);
    curl_easy_setopt(curl, CURLOPT_HEADERDATA, &result);
    curl_easy_setopt(curl, CURLOPT_ERRORBUFFER, result.error);
    curl_easy_setopt(curl, CURLOPT_FAILONERROR, 1L);
    result.curl_code = curl_easy_perform(curl);
    (void)curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &result.http_code);
    result.bytes = body->size;
    if (body->overflow && result.error[0] == '\0')
        snprintf(result.error, sizeof(result.error), "response exceeded %u bytes", BODY_BYTES);
    if (result.date_header[0] != '\0') {
        server_time = curl_getdate(result.date_header, NULL);
        if (server_time != (time_t)-1)
            result.server_ms = (int64_t)server_time * 1000LL;
    }
    curl_easy_cleanup(curl);
    return result;
}

static void adapt_platform_schema_marker(char *json)
{
    char *key, *value;
    if (json == NULL) return;
    key = strstr(json, "\"engine\"");
    if (key == NULL) return;
    value = strchr(key, ':');
    if (value == NULL) return;
    value++;
    while (*value == ' ' || *value == '\t' || *value == '\r' || *value == '\n') value++;
    if (*value == '1') *value = '5';
}

static int64_t kernel_realtime_ms(void)
{
    static const int64_t NT_UNIX_EPOCH_100NS = 116444736000000000LL;
    uint64_t nt_time = 0;
    int64_t unix_ticks;
    KeQuerySystemTime(&nt_time);
    unix_ticks = (int64_t)nt_time - NT_UNIX_EPOCH_100NS;
    return unix_ticks >= 0 ? unix_ticks / 10000LL : -1;
}

static int64_t best_time_ms(const struct http_result *a, const struct http_result *b, const struct http_result *c)
{
    if (a != NULL && a->server_ms >= 0) return a->server_ms;
    if (b != NULL && b->server_ms >= 0) return b->server_ms;
    if (c != NULL && c->server_ms >= 0) return c->server_ms;
    return kernel_realtime_ms();
}

static bool wants_exit(void)
{
    INPUT_STATE input = { 0 };
    if (XamInputGetState(0, 0, &input) != ERROR_SUCCESS) return false;
    return (input.gamepad.buttons & (INPUT_GAMEPAD_B | INPUT_GAMEPAD_BACK | INPUT_GAMEPAD_START)) != 0;
}

static NTSTATUS present_status(uint32_t width, uint32_t height, const char *text, uint32_t color)
{
    uint32_t address = 0;
    NTSTATUS status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
    if (!NT_SUCCESS(status)) return status;
    xsdk_gpu_set_target(width, height);
    xsdk_text_draw(36, 28, 2, TEXT_ARGB, text);
    xsdk_text_draw(36, 684, 1, color, "V7A - B/BACK/START RETURNS TO AURORA");
    xsdk_gpu_resolve(address, width, height, BACKGROUND_ARGB);
    xsdk_present_end();
    return STATUS_SUCCESS;
}

static void ff_error_text(int code, char *out, size_t out_size)
{
    if (av_strerror(code, out, out_size) < 0)
        snprintf(out, out_size, "FFmpeg error %d", code);
}

static size_t remote_write(char *data, size_t size, size_t count, void *user)
{
    struct remote_file *remote = user;
    const size_t length = size * count;
    if (remote == NULL || remote->cache == NULL || length > remote->cache_capacity - remote->cache_length)
        return 0;
    memcpy(remote->cache + remote->cache_length, data, length);
    remote->cache_length += length;
    return length;
}

static int remote_fill(struct remote_file *remote, int64_t start)
{
    char range[96];
    CURLcode result;
    long http = 0;
    int64_t end;
    if (remote == NULL || remote->curl == NULL || start < 0 || start >= remote->size)
        return -1;
    end = start + (int64_t)remote->cache_capacity - 1;
    if (end >= remote->size) end = remote->size - 1;
    snprintf(range, sizeof(range), "%" PRId64 "-%" PRId64, start, end);
    remote->cache_length = 0;
    remote->curl_error[0] = '\0';
    curl_easy_reset(remote->curl);
    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_RANGE, range);
    curl_easy_setopt(remote->curl, CURLOPT_WRITEFUNCTION, remote_write);
    curl_easy_setopt(remote->curl, CURLOPT_WRITEDATA, remote);
    curl_easy_setopt(remote->curl, CURLOPT_ERRORBUFFER, remote->curl_error);
    result = curl_easy_perform(remote->curl);
    (void)curl_easy_getinfo(remote->curl, CURLINFO_RESPONSE_CODE, &http);
    remote->last_http = http;
    if (result != CURLE_OK) {
        snprintf(remote->error, sizeof(remote->error), "range curl=%d HTTP=%ld %.120s",
            (int)result, http, remote->curl_error);
        return -1;
    }
    if (http != 206 && !(http == 200 && start == 0)) {
        snprintf(remote->error, sizeof(remote->error), "server ignored range at %" PRId64 " (HTTP %ld)", start, http);
        return -1;
    }
    if (remote->cache_length == 0) {
        snprintf(remote->error, sizeof(remote->error), "empty range at %" PRId64, start);
        return -1;
    }
    remote->cache_start = start;
    return 0;
}

static int remote_open(struct remote_file *remote, const char *url)
{
    CURLcode result;
    long http = 0;
    curl_off_t length = -1;
    memset(remote, 0, sizeof(*remote));
    remote->size = -1;
    remote->cache_start = -1;
    if (snprintf(remote->url, sizeof(remote->url), "%s", url) >= (int)sizeof(remote->url)) {
        snprintf(remote->error, sizeof(remote->error), "media URL too long");
        return -1;
    }
    remote->cache_capacity = REMOTE_CACHE_BYTES;
    remote->cache = malloc(remote->cache_capacity);
    remote->curl = curl_easy_init();
    if (remote->cache == NULL || remote->curl == NULL) {
        snprintf(remote->error, sizeof(remote->error), "remote allocation failed");
        return -1;
    }
    set_common_curl(remote->curl, remote->url);
    curl_easy_setopt(remote->curl, CURLOPT_NOBODY, 1L);
    curl_easy_setopt(remote->curl, CURLOPT_ERRORBUFFER, remote->curl_error);
    result = curl_easy_perform(remote->curl);
    (void)curl_easy_getinfo(remote->curl, CURLINFO_RESPONSE_CODE, &http);
    if (result != CURLE_OK || http < 200 || http >= 400) {
        snprintf(remote->error, sizeof(remote->error), "media HEAD curl=%d HTTP=%ld %.120s",
            (int)result, http, remote->curl_error);
        return -1;
    }
    if (curl_easy_getinfo(remote->curl, CURLINFO_CONTENT_LENGTH_DOWNLOAD_T, &length) != CURLE_OK || length <= 0) {
        snprintf(remote->error, sizeof(remote->error), "media size unavailable");
        return -1;
    }
    remote->size = (int64_t)length;
    remote->position = 0;
    remote->last_http = http;
    return 0;
}

static void remote_close(struct remote_file *remote)
{
    if (remote == NULL) return;
    if (remote->curl != NULL) curl_easy_cleanup(remote->curl);
    free(remote->cache);
    memset(remote, 0, sizeof(*remote));
}

static int avio_remote_read(void *opaque, uint8_t *buffer, int buffer_size)
{
    struct remote_file *remote = opaque;
    int copied = 0;
    if (remote == NULL || buffer == NULL || buffer_size <= 0) return AVERROR(EINVAL);
    while (copied < buffer_size && remote->position < remote->size) {
        int64_t cache_end = remote->cache_start + (int64_t)remote->cache_length;
        if (remote->cache_start < 0 || remote->position < remote->cache_start || remote->position >= cache_end) {
            if (remote_fill(remote, remote->position) != 0)
                return copied > 0 ? copied : AVERROR(EIO);
            cache_end = remote->cache_start + (int64_t)remote->cache_length;
        }
        {
            const size_t offset = (size_t)(remote->position - remote->cache_start);
            size_t available = remote->cache_length - offset;
            size_t wanted = (size_t)(buffer_size - copied);
            if (available > wanted) available = wanted;
            memcpy(buffer + copied, remote->cache + offset, available);
            copied += (int)available;
            remote->position += (int64_t)available;
        }
    }
    return copied > 0 ? copied : AVERROR_EOF;
}

static int64_t avio_remote_seek(void *opaque, int64_t offset, int whence)
{
    struct remote_file *remote = opaque;
    int base = whence & ~AVSEEK_FORCE;
    int64_t target;
    if (remote == NULL) return AVERROR(EINVAL);
    if (base == AVSEEK_SIZE) return remote->size;
    if (base == SEEK_SET) target = offset;
    else if (base == SEEK_CUR) target = remote->position + offset;
    else if (base == SEEK_END) target = remote->size + offset;
    else return AVERROR(EINVAL);
    if (target < 0 || target > remote->size) return AVERROR(EINVAL);
    remote->position = target;
    return target;
}

static int clamp8(int value)
{
    if (value < 0) return 0;
    if (value > 255) return 255;
    return value;
}

static int frame_to_argb(const AVFrame *frame, uint32_t **out, char *error, size_t error_size)
{
    uint32_t *pixels;
    int x, y;
    const bool full = frame->color_range == AVCOL_RANGE_JPEG;
    if (frame->format != AV_PIX_FMT_YUV420P && frame->format != AV_PIX_FMT_YUVJ420P) {
        snprintf(error, error_size, "unsupported pixel format %d (need YUV420P)", frame->format);
        return -1;
    }
    if (frame->width <= 0 || frame->height <= 0 || frame->width > 1920 || frame->height > 1080) {
        snprintf(error, error_size, "unsupported frame size %dx%d", frame->width, frame->height);
        return -1;
    }
    pixels = malloc((size_t)frame->width * (size_t)frame->height * sizeof(uint32_t));
    if (pixels == NULL) {
        snprintf(error, error_size, "ARGB allocation failed");
        return -1;
    }
    for (y = 0; y < frame->height; y++) {
        const uint8_t *yp = frame->data[0] + y * frame->linesize[0];
        const uint8_t *up = frame->data[1] + (y / 2) * frame->linesize[1];
        const uint8_t *vp = frame->data[2] + (y / 2) * frame->linesize[2];
        uint32_t *dst = pixels + (size_t)y * (size_t)frame->width;
        for (x = 0; x < frame->width; x++) {
            int yy = yp[x];
            const int u = (int)up[x / 2] - 128;
            const int v = (int)vp[x / 2] - 128;
            int r, g, b;
            if (full) {
                r = yy + ((359 * v) >> 8);
                g = yy - ((88 * u + 183 * v) >> 8);
                b = yy + ((454 * u) >> 8);
            } else {
                int c = yy - 16;
                if (c < 0) c = 0;
                r = (298 * c + 409 * v + 128) >> 8;
                g = (298 * c - 100 * u - 208 * v + 128) >> 8;
                b = (298 * c + 516 * u + 128) >> 8;
            }
            dst[x] = 0xFF000000u | (uint32_t)clamp8(r) << 16 |
                     (uint32_t)clamp8(g) << 8 | (uint32_t)clamp8(b);
        }
    }
    *out = pixels;
    return 0;
}

static int decode_picture(const char *url, int64_t target_ms, struct decoded_picture *picture,
    int64_t *remote_size, long *range_http, char *error, size_t error_size)
{
    struct remote_file remote;
    AVIOContext *avio = NULL;
    AVFormatContext *format = NULL;
    AVCodecContext *decoder = NULL;
    AVFrame *frame = NULL;
    AVPacket *packet = NULL;
    uint8_t *avio_buffer = NULL;
    const AVCodec *codec;
    AVStream *stream;
    int video_index, result, decoded = 0;
    int64_t target_ts, start_ts;
    bool found = false;
    char fferr[128];

    memset(&remote, 0, sizeof(remote));
    memset(picture, 0, sizeof(*picture));
    picture->actual_ms = -1;
    picture->target_ms = target_ms;
    if (remote_open(&remote, url) != 0) {
        snprintf(error, error_size, "remote open: %.180s", remote.error);
        remote_close(&remote);
        return -1;
    }
    *remote_size = remote.size;

    avio_buffer = av_malloc(AVIO_BUFFER_BYTES);
    if (avio_buffer == NULL) {
        snprintf(error, error_size, "AVIO buffer allocation failed");
        goto fail;
    }
    avio = avio_alloc_context(avio_buffer, AVIO_BUFFER_BYTES, 0, &remote,
        avio_remote_read, NULL, avio_remote_seek);
    if (avio == NULL) {
        snprintf(error, error_size, "avio_alloc_context failed");
        av_free(avio_buffer);
        avio_buffer = NULL;
        goto fail;
    }
    avio_buffer = NULL;
    format = avformat_alloc_context();
    if (format == NULL) {
        snprintf(error, error_size, "avformat_alloc_context failed");
        goto fail;
    }
    format->pb = avio;
    format->flags |= AVFMT_FLAG_CUSTOM_IO;
    format->probesize = 2 * 1024 * 1024;
    format->max_analyze_duration = 5LL * AV_TIME_BASE;
    result = avformat_open_input(&format, NULL, NULL, NULL);
    if (result < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size, "MP4 open failed: %s; remote=%.120s", fferr, remote.error);
        goto fail;
    }
    result = avformat_find_stream_info(format, NULL);
    if (result < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size, "stream info failed: %s", fferr);
        goto fail;
    }
    video_index = av_find_best_stream(format, AVMEDIA_TYPE_VIDEO, -1, -1, NULL, 0);
    if (video_index < 0) {
        ff_error_text(video_index, fferr, sizeof(fferr));
        snprintf(error, error_size, "no video stream: %s", fferr);
        goto fail;
    }
    stream = format->streams[video_index];
    codec = avcodec_find_decoder(stream->codecpar->codec_id);
    if (codec == NULL) {
        snprintf(error, error_size, "video codec id %d not enabled", stream->codecpar->codec_id);
        goto fail;
    }
    snprintf(picture->codec, sizeof(picture->codec), "%s", codec->name != NULL ? codec->name : "unknown");
    decoder = avcodec_alloc_context3(codec);
    if (decoder == NULL) {
        snprintf(error, error_size, "decoder allocation failed");
        goto fail;
    }
    if ((result = avcodec_parameters_to_context(decoder, stream->codecpar)) < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size, "decoder parameters failed: %s", fferr);
        goto fail;
    }
    decoder->thread_count = 1;
    decoder->skip_loop_filter = AVDISCARD_ALL;
    if ((result = avcodec_open2(decoder, codec, NULL)) < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size, "decoder open failed: %s", fferr);
        goto fail;
    }
    frame = av_frame_alloc();
    packet = av_packet_alloc();
    if (frame == NULL || packet == NULL) {
        snprintf(error, error_size, "frame/packet allocation failed");
        goto fail;
    }

    start_ts = stream->start_time == AV_NOPTS_VALUE ? 0 : stream->start_time;
    target_ts = start_ts + av_rescale_q(target_ms, (AVRational){ 1, 1000 }, stream->time_base);
    result = av_seek_frame(format, video_index, target_ts, AVSEEK_FLAG_BACKWARD);
    if (result < 0) {
        ff_error_text(result, fferr, sizeof(fferr));
        snprintf(error, error_size, "media seek failed: %s", fferr);
        goto fail;
    }
    avcodec_flush_buffers(decoder);

    while (!found && decoded < MAX_DECODED_FRAMES && (result = av_read_frame(format, packet)) >= 0) {
        if (packet->stream_index == video_index) {
            result = avcodec_send_packet(decoder, packet);
            if (result >= 0) {
                while ((result = avcodec_receive_frame(decoder, frame)) >= 0) {
                    int64_t ts = frame->best_effort_timestamp;
                    int64_t actual_ms = 0;
                    decoded++;
                    if (ts != AV_NOPTS_VALUE)
                        actual_ms = av_rescale_q(ts - start_ts, stream->time_base, (AVRational){ 1, 1000 });
                    if (actual_ms < 0) actual_ms = 0;
                    if (actual_ms + 250 < target_ms && decoded < MAX_DECODED_FRAMES)
                        continue;
                    picture->width = frame->width;
                    picture->height = frame->height;
                    picture->pixel_format = frame->format;
                    picture->actual_ms = actual_ms;
                    if (frame_to_argb(frame, &picture->argb, error, error_size) != 0)
                        goto fail;
                    found = true;
                    break;
                }
            }
        }
        av_packet_unref(packet);
    }
    av_packet_unref(packet);
    if (!found) {
        snprintf(error, error_size, "no decoded frame near target after %d frames", decoded);
        goto fail;
    }

    *range_http = remote.last_http;
    av_packet_free(&packet);
    av_frame_free(&frame);
    avcodec_free_context(&decoder);
    avformat_close_input(&format);
    avio_context_free(&avio);
    remote_close(&remote);
    return 0;

fail:
    if (range_http != NULL) *range_http = remote.last_http;
    if (packet != NULL) av_packet_free(&packet);
    if (frame != NULL) av_frame_free(&frame);
    if (decoder != NULL) avcodec_free_context(&decoder);
    if (format != NULL) avformat_close_input(&format);
    if (avio != NULL) avio_context_free(&avio);
    else if (avio_buffer != NULL) av_free(avio_buffer);
    remote_close(&remote);
    return -1;
}

static void write_gpu(volatile uint32_t *memory, const void *data, uint32_t size_bytes)
{
    uint32_t i;
    for (i = 0; i < size_bytes / 4u; i++) {
        uint32_t word;
        memcpy(&word, (const uint8_t *)data + i * 4u, 4u);
        memory[i] = word;
    }
    __asm__ volatile("sync" ::: "memory");
    xsdk_gpu_invalidate(xsdk_gpu_address(memory), size_bytes);
}

static bool renderer_open(VideoRenderer *renderer, int video_width, int video_height, uint32_t screen_width,
    uint32_t screen_height, char *error, size_t error_size)
{
    NTSTATUS status;
    float xscale = 1.0f, yscale = 1.0f;
    const float video_aspect = (float)video_width / (float)video_height;
    const float screen_aspect = (float)screen_width / (float)screen_height;
    float quad[QUAD_VERTICES][VERTEX_FLOATS];
    const XsdkSampler sampler = {
        .mag_filter = XSDK_FILTER_LINEAR,
        .min_filter = XSDK_FILTER_LINEAR,
        .mip_filter = XSDK_FILTER_POINT,
        .address_u = XSDK_ADDRESS_CLAMP,
        .address_v = XSDK_ADDRESS_CLAMP,
    };
    memset(renderer, 0, sizeof(*renderer));
    status = xsdk_shader_load(&renderer->vertex, frame_vert.container, frame_vert.container_bytes);
    if (NT_SUCCESS(status)) status = xsdk_shader_load(&renderer->pixel, frame_frag.container, frame_frag.container_bytes);
    if (NT_SUCCESS(status)) status = xsdk_shader_set_vertex_layout(&renderer->vertex, video_layout,
        sizeof(video_layout) / sizeof(video_layout[0]), (const uint32_t[]){ VERTEX_BYTES });
    if (!NT_SUCCESS(status)) {
        snprintf(error, error_size, "video shaders failed 0x%08X", (unsigned)status);
        return false;
    }
    status = xsdk_texture_create(&renderer->texture, XSDK_FORMAT_A8R8G8B8,
        (uint32_t)video_width, (uint32_t)video_height, 1, true);
    if (!NT_SUCCESS(status)) {
        snprintf(error, error_size, "video texture failed 0x%08X", (unsigned)status);
        return false;
    }
    xsdk_texture_sampler_state(&renderer->sampler, &sampler);
    if (video_aspect < screen_aspect) xscale = video_aspect / screen_aspect;
    else if (video_aspect > screen_aspect) yscale = screen_aspect / video_aspect;
    {
        const float q[QUAD_VERTICES][VERTEX_FLOATS] = {
            { -xscale,  yscale, 0, 1, 0, 0 },
            {  xscale,  yscale, 0, 1, 1, 0 },
            { -xscale, -yscale, 0, 1, 0, 1 },
            { -xscale, -yscale, 0, 1, 0, 1 },
            {  xscale,  yscale, 0, 1, 1, 0 },
            {  xscale, -yscale, 0, 1, 1, 1 },
        };
        memcpy(quad, q, sizeof(quad));
    }
    renderer->vertices = xsdk_gpu_alloc(QUAD_BYTES);
    if (renderer->vertices == NULL) {
        snprintf(error, error_size, "video vertex allocation failed");
        return false;
    }
    write_gpu(renderer->vertices, quad, QUAD_BYTES);
    return true;
}

static void renderer_close(VideoRenderer *renderer)
{
    if (renderer == NULL) return;
    if (renderer->vertices != NULL) xsdk_gpu_free(renderer->vertices);
    xsdk_texture_free(&renderer->texture);
    xsdk_shader_free(&renderer->pixel);
    xsdk_shader_free(&renderer->vertex);
    memset(renderer, 0, sizeof(*renderer));
}

static NTSTATUS render_picture(VideoRenderer *renderer, const struct decoded_picture *picture,
    uint32_t width, uint32_t height, const char *overlay)
{
    uint32_t address = 0;
    NTSTATUS status;
    xsdk_texture_upload(&renderer->texture, 0, picture->argb, (uint32_t)picture->width * 4u);
    xsdk_gpu_invalidate(renderer->texture.address, renderer->texture.size_bytes);
    status = xsdk_present_begin(&address, BEGIN_TIMEOUT_MS);
    if (!NT_SUCCESS(status)) return status;
    xsdk_gpu_set_target(width, height);
    xsdk_gpu_set_shaders(&renderer->vertex, &renderer->pixel);
    xsdk_built_shader_set_literals(&frame_vert);
    xsdk_built_shader_set_literals(&frame_frag);
    xsdk_gpu_set_texture(0, &renderer->texture, &renderer->sampler);
    xsdk_gpu_set_vertices(0, xsdk_gpu_address(renderer->vertices), QUAD_BYTES);
    xsdk_gpu_draw(XSDK_PRIMITIVE_TRIANGLE_LIST, QUAD_VERTICES);
    xsdk_text_draw(28, 24, 1, TEXT_ARGB, overlay);
    xsdk_gpu_resolve(address, width, height, BACKGROUND_ARGB);
    xsdk_present_end();
    return STATUS_SUCCESS;
}

static void format_hms(int64_t ms, char *out, size_t out_size)
{
    int64_t s, h, m;
    if (ms < 0) ms = 0;
    s = ms / 1000LL;
    h = s / 3600LL;
    m = (s % 3600LL) / 60LL;
    s %= 60LL;
    snprintf(out, out_size, "%02" PRId64 ":%02" PRId64 ":%02" PRId64, h, m, s);
}

int main(void)
{
    struct response_buffer body = { 0 };
    struct sp_schedule *schedule = NULL;
    struct sp_pointer pointer;
    struct sp_now now_result;
    struct http_result lineup_http = { 0 }, manifest_http = { 0 }, platform_http = { 0 };
    struct decoded_picture picture;
    VideoRenderer renderer;
    char channel_name[64] = { 0 }, channel_id[64] = { 0 };
    char manifest_url[SP_URL_BYTES] = { 0 }, platform_url[SP_URL_BYTES] = { 0 };
    char error[512] = { 0 }, status_text[3400], overlay[1024], target_text[32], actual_text[32];
    int64_t selected_ms, final_ms, media_size = -1;
    long range_http = 0;
    bool curl_ready = false, renderer_ready = false;
    NTSTATUS status;
    uint32_t width = 0, height = 0;
    unsigned frame;

    memset(&pointer, 0, sizeof(pointer));
    memset(&now_result, 0, sizeof(now_result));
    memset(&picture, 0, sizeof(picture));
    memset(&renderer, 0, sizeof(renderer));
    xsdk_log_write("Spelunkr360 V7A: live first-frame decode proof start");

    status = xsdk_gpu_open();
    if (!NT_SUCCESS(status)) return 2;
    status = xsdk_present_open(XSDK_DISPLAY_720P, BUFFERS, SWAP_INTERVAL, &width, &height);
    if (!NT_SUCCESS(status)) { (void)xsdk_gpu_close(); return 3; }
    status = xsdk_text_open();
    if (!NT_SUCCESS(status)) { xsdk_present_close(); (void)xsdk_gpu_close(); return 4; }

    (void)present_status(width, height,
        "SPELUNKR360 V7A - LIVE VIDEO FRAME PROBE\nCH 53 - TOONERTIA\n\n"
        "FETCHING LIVE SCHEDULE...\nLOCATING CURRENT ARCHIVE MEDIA...\nOPENING MP4 WITH HTTP RANGE IO...",
        GOOD_ARGB);

    body.data = malloc(BODY_BYTES);
    schedule = calloc(1, sizeof(*schedule));
    if (body.data == NULL || schedule == NULL) { snprintf(error, sizeof(error), "memory allocation failed"); goto fail; }
    body.capacity = BODY_BYTES;
    if (curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) { snprintf(error, sizeof(error), "curl_global_init failed"); goto fail; }
    curl_ready = true;

    lineup_http = fetch_url(LINEUP_URL, &body);
    selected_ms = best_time_ms(&lineup_http, NULL, NULL);
    if (lineup_http.curl_code != CURLE_OK || lineup_http.http_code != 200 || selected_ms < 0) {
        snprintf(error, sizeof(error), "lineup/time failed curl=%d HTTP=%ld", (int)lineup_http.curl_code, lineup_http.http_code); goto fail;
    }
    if (sp_parse_lineup_53(body.data, body.size, selected_ms, &pointer, channel_name, sizeof(channel_name),
            channel_id, sizeof(channel_id), error, sizeof(error)) != 0) goto fail;
    if (strcmp(channel_name, "TOONERTIA") != 0 || strcmp(channel_id, "toonertia") != 0) {
        snprintf(error, sizeof(error), "channel 53 identity mismatch"); goto fail;
    }
    if (snprintf(manifest_url, sizeof(manifest_url), "%s%s", BUCKET_URL, pointer.manifest) >= (int)sizeof(manifest_url)) {
        snprintf(error, sizeof(error), "manifest URL too long"); goto fail;
    }
    manifest_http = fetch_url(manifest_url, &body);
    if (manifest_http.curl_code != CURLE_OK || manifest_http.http_code != 200) {
        snprintf(error, sizeof(error), "manifest failed curl=%d HTTP=%ld", (int)manifest_http.curl_code, manifest_http.http_code); goto fail;
    }
    if (sp_parse_manifest(body.data, body.size, schedule, error, sizeof(error)) != 0) goto fail;
    if (schedule->platform_path[0] == '\0' || snprintf(platform_url, sizeof(platform_url), "%s%s", BUCKET_URL,
            schedule->platform_path) >= (int)sizeof(platform_url)) {
        snprintf(error, sizeof(error), "platform URL invalid"); goto fail;
    }
    platform_http = fetch_url(platform_url, &body);
    if (platform_http.curl_code != CURLE_OK || platform_http.http_code != 200) {
        snprintf(error, sizeof(error), "platform failed curl=%d HTTP=%ld", (int)platform_http.curl_code, platform_http.http_code); goto fail;
    }
    adapt_platform_schema_marker(body.data);
    if (sp_parse_platform(body.data, body.size, schedule, error, sizeof(error)) != 0) goto fail;
    final_ms = best_time_ms(&platform_http, &manifest_http, &lineup_http);
    if (final_ms < 0 || sp_find_now(schedule, &pointer, final_ms, &now_result, error, sizeof(error)) != 0 || !now_result.ok)
        goto fail;

    if (now_result.kind == SP_SEGMENT_BUMP) {
        const int64_t after_bump = final_ms + now_result.remaining_ms + 250;
        if (sp_find_now(schedule, &pointer, after_bump, &now_result, error, sizeof(error)) != 0 ||
            !now_result.ok || now_result.kind != SP_SEGMENT_SHOW) {
            snprintf(error, sizeof(error), "current bump did not lead directly to a show"); goto fail;
        }
    }
    if (now_result.kind != SP_SEGMENT_SHOW || now_result.archive_url[0] == '\0') {
        snprintf(error, sizeof(error), "no playable show URL at current schedule point"); goto fail;
    }

    format_hms(now_result.offset_ms, target_text, sizeof(target_text));
    snprintf(status_text, sizeof(status_text),
        "SPELUNKR360 V7A - LIVE VIDEO FRAME PROBE\nCH 53 - TOONERTIA\n\n"
        "NOW PLAYING: %s\nTARGET POSITION: %s\nARCHIVE ID: %s\n\n"
        "SCHEDULE: PASS\nMEDIA URL: FOUND\n\nOPENING REMOTE MP4 / SEEKING / DECODING H.264...",
        now_result.title, target_text, now_result.id);
    (void)present_status(width, height, status_text, GOOD_ARGB);

    if (decode_picture(now_result.archive_url, now_result.offset_ms, &picture, &media_size, &range_http,
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
    free(picture.argb);
    if (curl_ready) curl_global_cleanup();
    free(schedule);
    free(body.data);
    xsdk_text_close();
    xsdk_present_close();
    (void)xsdk_gpu_close();
    return 0;

fail:
    snprintf(status_text, sizeof(status_text),
        "SPELUNKR360 V7A - LIVE VIDEO FRAME PROBE\nCH 53 - TOONERTIA\n\n"
        "VIDEO FRAME TEST: FAIL\nERROR: %.420s\n\n"
        "LINEUP HTTP: %ld  MANIFEST HTTP: %ld  PLATFORM HTTP: %ld  RANGE HTTP: %ld\n\n"
        "B/BACK/START: RETURN TO AURORA",
        error[0] ? error : "unknown", lineup_http.http_code, manifest_http.http_code,
        platform_http.http_code, range_http);
    xsdk_log_write("Spelunkr360 V7A FAIL: %s", error[0] ? error : "unknown");
    for (frame = 0; frame < 1200 && !wants_exit(); frame++)
        (void)present_status(width, height, status_text, BAD_ARGB);
    if (renderer_ready) renderer_close(&renderer);
    free(picture.argb);
    if (curl_ready) curl_global_cleanup();
    free(schedule);
    free(body.data);
    xsdk_text_close();
    xsdk_present_close();
    (void)xsdk_gpu_close();
    return 1;
}
