#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <stdint.h>
#include <time.h>

#include "xsdk/kernel.h"

/*
 * V6C hardware hotfix: query the Xbox kernel clock directly instead of
 * relying on the POSIX clock_gettime wrapper. KeQuerySystemTime returns
 * 100 ns ticks since 1601-01-01 UTC.
 */
int v6c_clock_gettime(clockid_t clock, struct timespec *out)
{
    static const uint64_t NT_UNIX_EPOCH = 116444736000000000ULL;
    static const uint64_t NT_TICKS_PER_SECOND = 10000000ULL;
    uint64_t nt_time;
    uint64_t unix_ticks;

    if (clock != CLOCK_REALTIME || out == NULL) {
        errno = EINVAL;
        return -1;
    }

    nt_time = 0;
    KeQuerySystemTime(&nt_time);
    if (nt_time < NT_UNIX_EPOCH) {
        errno = EINVAL;
        return -1;
    }

    unix_ticks = nt_time - NT_UNIX_EPOCH;
    out->tv_sec = (time_t)(unix_ticks / NT_TICKS_PER_SECOND);
    out->tv_nsec = (long)((unix_ticks % NT_TICKS_PER_SECOND) * 100ULL);
    return 0;
}
