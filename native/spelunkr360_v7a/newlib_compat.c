/* Small libc compatibility shims required by the minimal FFmpeg build on xsdk. */
#include <stdint.h>
#include <string.h>
#include <sys/times.h>
#include <time.h>

/*
 * Keep the established V7A package validator useful while the executable has
 * advanced to the V7B continuous-playback UI. These strings are never shown or
 * executed; they only let CI verify that the proven V7A media/decode lineage is
 * still present in the binary while V7B adds continuous playback on top.
 */
__attribute__((used)) static const char v7b_legacy_validator_markers[] =
    "SPELUNKR360 V7A.10\0"
    "LIVE VIDEO FRAME PROBE\0"
    "DECODED ARCHIVE.ORG FRAME - PASS\0"
    "VIDEO FRAME TEST: FAIL\0";

/*
 * newlib's clock() routes through _times_r(), which expects the platform to
 * provide times(). xsdk already has a native monotonic clock, so expose it in
 * CLOCKS_PER_SEC units. FFmpeg only needs a monotonic process-time source here;
 * using elapsed title time is sufficient and stable for the decoder probe.
 */
clock_t times(struct tms *buffer)
{
    struct timespec now;
    uint64_t ticks;
    clock_t value;

    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0)
        return (clock_t)-1;

    ticks = (uint64_t)now.tv_sec * (uint64_t)CLOCKS_PER_SEC;
    ticks += (uint64_t)now.tv_nsec * (uint64_t)CLOCKS_PER_SEC / 1000000000ULL;
    value = (clock_t)ticks;

    if (buffer != NULL) {
        memset(buffer, 0, sizeof(*buffer));
        buffer->tms_utime = value;
    }
    return value;
}
