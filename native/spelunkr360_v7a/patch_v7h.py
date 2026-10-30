#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v7h.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

# V7H hardware follow-up:
# V7G cut the long mid-stream pause to roughly three seconds by moving the
# Archive.org prefetch worker onto another physical core at +1 priority.  The
# remaining pause comes from waiting for pthread_join() to finish the ENTIRE
# 4 MiB range even when most of that range has already arrived.  V7H publishes
# the worker's received byte count atomically and lets AVIO stage/consume the
# already-downloaded prefix while curl continues filling the rest.

src = src.replace('SPELUNKR360 V7G - DEDICATED PREFETCH THREAD + STABILITY',
                  'SPELUNKR360 V7H - PROGRESSIVE PREFETCH + STABILITY')
src = src.replace('SPELUNKR360 V7G - DEDICATED PREFETCH THREAD PLAYBACK',
                  'SPELUNKR360 V7H - PROGRESSIVE PREFETCH PLAYBACK')
src = src.replace('V7G - B/BACK/START RETURNS TO AURORA',
                  'V7H - B/BACK/START RETURNS TO AURORA')
src = src.replace('V7G soak failed', 'V7H soak failed')
src = src.replace('Spelunkr360 V7G PASS:', 'Spelunkr360 V7H PASS:')
src = src.replace('V7G async partial salvaged', 'V7H async partial salvaged')
src = src.replace('V7G foreground partial salvaged', 'V7H foreground partial salvaged')
src = src.replace('V7G prefetch thread: creator_ht=', 'V7H prefetch thread: creator_ht=')

old_fields = '''    uint32_t prefetch_hw_thread;
    NTSTATUS prefetch_place_status;
    NTSTATUS prefetch_priority_status;
    char prefetch_error[128];'''
new_fields = '''    uint32_t prefetch_hw_thread;
    NTSTATUS prefetch_place_status;
    NTSTATUS prefetch_priority_status;
    unsigned prefetch_stream_hits;
    unsigned prefetch_stream_waits;
    char prefetch_error[128];'''
if old_fields not in src:
    raise SystemExit('V7H counter field marker missing')
src = src.replace(old_fields, new_fields, 1)

old_write = '''static size_t v7e_prefetch_write(char *data, size_t size, size_t count, void *user)
{
    struct remote_file *remote = user;
    const size_t length = size * count;
    if (remote == NULL || remote->prefetch_cache == NULL ||
        length > remote->prefetch_capacity - remote->prefetch_length)
        return 0;
    memcpy(remote->prefetch_cache + remote->prefetch_length, data, length);
    remote->prefetch_length += length;
    return length;
}'''
new_write = '''static size_t v7e_prefetch_write(char *data, size_t size, size_t count, void *user)
{
    struct remote_file *remote = user;
    const size_t length = size * count;
    size_t used;
    if (remote == NULL || remote->prefetch_cache == NULL) return 0;
    used = __atomic_load_n(&remote->prefetch_length, __ATOMIC_RELAXED);
    if (used > remote->prefetch_capacity || length > remote->prefetch_capacity - used)
        return 0;
    memcpy(remote->prefetch_cache + used, data, length);
    /* Publish only after the payload bytes are fully copied. */
    __atomic_store_n(&remote->prefetch_length, used + length, __ATOMIC_RELEASE);
    return length;
}'''
if old_write not in src:
    raise SystemExit('V7H prefetch write marker missing')
src = src.replace(old_write, new_write, 1)

promote_marker = '/* 1 = promoted prefetched bytes, 0 = no matching prefetch, -1 = prefetch failed. */\nstatic int v7e_prefetch_promote'
if promote_marker not in src:
    raise SystemExit('V7H promote insertion marker missing')

helper = r'''/*
 * Stage whatever contiguous prefix the async worker has ALREADY received.
 * The worker publishes prefetch_length with release semantics after memcpy;
 * the playback thread acquires it before copying.  This removes the old hard
 * boundary where AVIO waited for the whole 4 MiB request to complete.
 *
 *  1 = staged bytes into the foreground cache
 *  0 = this prefetch cannot currently satisfy position
 * -1 = completed prefetch failed without usable bytes
 */
static int v7h_prefetch_stage(struct remote_file *remote, int64_t position)
{
    size_t total, offset, available, copy;
    bool done;
    if (remote == NULL || !remote->prefetch_active || position < remote->prefetch_start)
        return 0;

    for (;;) {
        total = __atomic_load_n(&remote->prefetch_length, __ATOMIC_ACQUIRE);
        offset = (size_t)(position - remote->prefetch_start);
        if (offset < total) break;
        done = __atomic_load_n(&remote->prefetch_done, __ATOMIC_ACQUIRE);
        if (done) {
            (void)pthread_join(remote->prefetch_thread, NULL);
            remote->prefetch_active = false;
            if (remote->prefetch_status != 0 && total == 0) return -1;
            return 0;
        }
        /* We have caught the network producer.  Wait only for the NEXT curl
         * write callback, not for the complete range transaction. */
        remote->prefetch_stream_waits++;
        (void)xsdk_thread_sleep(1);
    }

    available = total - offset;
    copy = available;
    if (copy > remote->cache_capacity) copy = remote->cache_capacity;
    if (copy == 0) return 0;
    memcpy(remote->cache, remote->prefetch_cache + offset, copy);
    remote->cache_start = position;
    remote->cache_length = copy;
    remote->prefetch_stream_hits++;

    done = __atomic_load_n(&remote->prefetch_done, __ATOMIC_ACQUIRE);
    if (done) {
        (void)pthread_join(remote->prefetch_thread, NULL);
        remote->prefetch_active = false;
        if (remote->prefetch_http != 0) remote->last_http = remote->prefetch_http;
        /* The completed range is now safely copied into the foreground cache;
         * immediately launch the following range while these bytes are used. */
        (void)v7e_prefetch_start(remote);
    }
    return 1;
}

'''
src = src.replace(promote_marker, helper + promote_marker, 1)

old_read = '''        if (remote->cache_start < 0 || remote->position < remote->cache_start || remote->position >= cache_end) {
            int promoted = v7e_prefetch_promote(remote, remote->position);
            if (promoted <= 0) {
                if (promoted < 0) remote->prefetch_fallbacks++;
                if (remote_fill(remote, remote->position) != 0)
                    return copied > 0 ? copied : AVERROR(EIO);
                (void)v7e_prefetch_start(remote);
            }
            cache_end = remote->cache_start + (int64_t)remote->cache_length;
        }'''
new_read = '''        if (remote->cache_start < 0 || remote->position < remote->cache_start || remote->position >= cache_end) {
            int staged = v7h_prefetch_stage(remote, remote->position);
            if (staged <= 0) {
                int promoted;
                if (staged < 0) remote->prefetch_fallbacks++;
                promoted = v7e_prefetch_promote(remote, remote->position);
                if (promoted <= 0) {
                    if (promoted < 0) remote->prefetch_fallbacks++;
                    if (remote_fill(remote, remote->position) != 0)
                        return copied > 0 ? copied : AVERROR(EIO);
                    (void)v7e_prefetch_start(remote);
                }
            }
            cache_end = remote->cache_start + (int64_t)remote->cache_length;
        }'''
if old_read not in src:
    raise SystemExit('V7H AVIO refill marker missing')
src = src.replace(old_read, new_read, 1)

old_overlay = '                    "PF H%u W%u F%u P%u | FG P%u | HT%u\\n"\n'
new_overlay = '                    "PF H%u W%u F%u P%u | STR H%u W%u | HT%u\\n"\n'
if old_overlay not in src:
    raise SystemExit('V7H overlay marker missing')
src = src.replace(old_overlay, new_overlay, 1)

old_overlay_args = '''                    remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
                    remote.prefetch_partials, remote.foreground_partials, remote.prefetch_hw_thread);'''
new_overlay_args = '''                    remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
                    remote.prefetch_partials, remote.prefetch_stream_hits, remote.prefetch_stream_waits,
                    remote.prefetch_hw_thread);'''
if old_overlay_args not in src:
    raise SystemExit('V7H overlay args marker missing')
src = src.replace(old_overlay_args, new_overlay_args, 1)

old_fail_format = '            "SYNCMAX %" PRId64 "ms HTTP %ld\\nPF H%u W%u F%u P%u | FG P%u | HT%u",'
new_fail_format = '            "SYNCMAX %" PRId64 "ms HTTP %ld\\nPF H%u W%u F%u P%u | STR H%u W%u | HT%u",'
if old_fail_format not in src:
    raise SystemExit('V7H fail format marker missing')
src = src.replace(old_fail_format, new_fail_format, 1)

old_fail_args = '''            remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
            remote.prefetch_partials, remote.foreground_partials, remote.prefetch_hw_thread);'''
new_fail_args = '''            remote.prefetch_hits, remote.prefetch_waits, remote.prefetch_fallbacks,
            remote.prefetch_partials, remote.prefetch_stream_hits, remote.prefetch_stream_waits,
            remote.prefetch_hw_thread);'''
if old_fail_args not in src:
    raise SystemExit('V7H fail args marker missing')
src = src.replace(old_fail_args, new_fail_args, 1)

for needle in (
    'SPELUNKR360 V7H - PROGRESSIVE PREFETCH + STABILITY',
    'SPELUNKR360 V7H - PROGRESSIVE PREFETCH PLAYBACK',
    'v7h_prefetch_stage',
    '__atomic_store_n(&remote->prefetch_length, used + length, __ATOMIC_RELEASE)',
    'prefetch_stream_hits',
    'STR H%u W%u',
    'V7H soak failed',
):
    if needle not in src:
        raise SystemExit(f'V7H marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7H progressive consumption of in-flight prefetch bytes")
