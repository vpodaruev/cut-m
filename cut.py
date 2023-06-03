#!/usr/bin/env python3

import subprocess as sp

import utils as ut


def make_filename(video, tm_code, outdir):
    time = ut.as_suffix(tm_code.start, tm_code.end)
    ext = video.suffix
    return outdir/f"{tm_code.row:03d}{time}_{tm_code.name}{ext}"


def correct_time_by(time, seconds):
    """Correct `time` in format hh:mm:ss by `seconds`"""
    t = ut.to_seconds(time) + seconds
    return ut.to_hhmmss(t)


ffmpeg = None  # set in main module


def make_fragment(video, start, end, outfile):
    ut.logger().debug(f"cutting {outfile.resolve()}")
    args = [
        f"{ffmpeg}",
        "-ss", start, "-to", end,
        "-i", f"{video}",
        "-c:v", "copy", "-c:a", "copy",
        "-y", f"{outfile.resolve()}",
    ]
    p = sp.run(args, capture_output=True)
    if p.returncode:
        ut.logger().error(ut.decode(p.stderr))
        return False
    return True
