#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_open13.py INPUT OUTPUT")

src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])

old_seekable = r'''    format->pb = avio;
    format->flags |= AVFMT_FLAG_CUSTOM_IO;
    avio->seekable = AVIO_SEEKABLE_NORMAL;
    format->probesize = 24 * 1024 * 1024;'''
new_seekable = r'''    format->pb = avio;
    format->flags |= AVFMT_FLAG_CUSTOM_IO;
    /*
     * The 360 build path cannot safely return a >2 GiB AVSEEK_SIZE value
     * through FFmpeg's custom AVIO callback.  This progressive MP4 has its
     * complete moov atom at the front, so open it as a stream first and
     * re-enable random access immediately after mov_read_header succeeds.
     */
    avio->seekable = 0;
    xsdk_log_write("V7A.13 OPEN MODE: FRONT-MOOV STREAM (NO AVSEEK_SIZE)");
    format->probesize = 24 * 1024 * 1024;'''
if old_seekable not in src:
    raise SystemExit('V7A.12 seekable-open marker missing')
src = src.replace(old_seekable, new_seekable, 1)

old_after_open = r'''        goto fail;
    }
    v7_stage("STAGE 3/5: READING VIDEO STREAM INFO...");
    result = avformat_find_stream_info(format, NULL);'''
new_after_open = r'''        goto fail;
    }

    /* Header parse is complete.  The sample tables from the front moov are
     * now resident, so restore random access for stream-info and live seek. */
    avio->seekable = AVIO_SEEKABLE_NORMAL;
    avio->eof_reached = 0;
    avio->error = 0;
    xsdk_log_write("V7A.13 MP4 OPEN PASS; RANDOM ACCESS RE-ENABLED");
    v7_stage("STAGE 2/5: MP4 CONTAINER OPEN - PASS\nRANDOM ACCESS RE-ENABLED FOR LIVE SEEK.");

    v7_stage("STAGE 3/5: READING VIDEO STREAM INFO...");
    result = avformat_find_stream_info(format, NULL);'''
if old_after_open not in src:
    raise SystemExit('V7A.12 post-open marker missing')
src = src.replace(old_after_open, new_after_open, 1)

src = src.replace('SPELUNKR360 V7A.12 - LIVE VIDEO FRAME PROBE', 'SPELUNKR360 V7A.13 - LIVE VIDEO FRAME PROBE')
src = src.replace('V7A.12 - B/BACK/START RETURNS TO AURORA', 'V7A.13 - B/BACK/START RETURNS TO AURORA')

for needle in (
    'SPELUNKR360 V7A.13 - LIVE VIDEO FRAME PROBE',
    'V7A.13 OPEN MODE: FRONT-MOOV STREAM (NO AVSEEK_SIZE)',
    'avio->seekable = 0',
    'V7A.13 MP4 OPEN PASS; RANDOM ACCESS RE-ENABLED',
    'STAGE 2/5: MP4 CONTAINER OPEN - PASS',
    'avio->seekable = AVIO_SEEKABLE_NORMAL',
    'STAGE 3/5: READING VIDEO STREAM INFO',
):
    if needle not in src:
        raise SystemExit(f'V7A.13 marker missing: {needle}')

out.write_text(src)
print(f"generated {out} with V7A.13 front-moov nonseekable-open workaround")
