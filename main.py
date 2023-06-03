#!/usr/bin/python3

import argparse
import json5 as json
import pathlib

import cut
import google_serve as gs
import utils as ut


# program version
version = "1.0-dev"

description = """
Download video from Google Drive and slice it into fragments
using timing from Google Spreadsheet.

Written in Python and powered by FFMPEG tool,
PyDrive2 and gspread Python modules.

Inspired by the Creative Society international project (creativesociety.com)
"""


def read_json(file):
    with file.open("r", encoding="utf-8") as f:
        buf = f.read()
    return json.loads(buf)


def parse_args(parser):
    args = parser.parse_args()
    args = vars(args)
    args.update(read_json(args["config"]))
    return args


if __name__ == "__main__":
    mime_type_all = {"video"}

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--config", type=pathlib.Path,
                        default=ut.application_path()/"config.json",
                        help="file with slicing settings in JSON5 format"
                             " [default: %(default)s]")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {version}")

    args = parse_args(parser)
    cut.ffmpeg = ut.as_command(args["ffmpeg"])
    ut.set_log_level(args["log_level"])
    ut.logger().debug(f"version is '{version}'")
    ut.logger().debug(f"arguments - {args}")

    auth_token = ut.checked_path(args["auth_token"])
    gd = gs.get_drive(auth_token)
    tempdir = pathlib.Path(args["temporary_dir"])

    ut.logger().debug(f"create temporary dir '{tempdir.resolve()}'")
    tempdir.mkdir(parents=True, exist_ok=True)

    video = gs.download_video(gs.as_id(args["video_url"]), tempdir)

    # extract time codes from google worksheet
    wsht = gs.open_worksheet(gs.get_sheet(auth_token), args["worksheet_url"])
    tm_codes = gs.extract_timing(wsht,
                                 args["head_row"],
                                 args["n_head_rows"],
                                 gs.TabColumns(
                                    args["columns"]["slice"],
                                    args["columns"]["start"],
                                    args["columns"]["end"],
                                    args["columns"]["name"],
                                 ))
    n_tm_codes = len(tm_codes)
    print(f"Extracted {n_tm_codes} time code(s)")

    # get videos that are done
    outdir_id = gs.as_id(args["output_dir_url"])
    ready_videos = gs.list_videos(outdir_id)

    # cut fragments by time code
    fragdir = tempdir/"fragments"
    fragdir.mkdir(exist_ok=True)

    stat = ut.Statistics()
    w = len(f"{n_tm_codes}")  # for pretty print
    for tm in tm_codes:
        frag = cut.make_filename(video, tm, fragdir)
        stat.total += 1
        print(f"{stat.total:0{w}d}/{n_tm_codes}", end=" ")
        if frag.name in ready_videos:
            info = gs.get_meta(ready_videos[frag.name])
            print('=', gs.meta_str(*info))
            stat.ready += 1
            continue

        print(">", end=" ", flush=True)
        if not frag.exists():
            s = cut.correct_time_by(tm.start, args["correct"]["start_time"])
            e = cut.correct_time_by(tm.end, args["correct"]["end_time"])
            ok = cut.make_fragment(video, s, e, frag)
            if not ok:
                stat.failed += 1
                print("[FAILED] failed to cut", frag.name)
                continue

        v = gd.CreateFile(metadata={
            "parents": [
                {"id": outdir_id}
            ],
            "title": frag.name
        })
        if args["do_upload"]:
            v.SetContentFile(f"{frag.resolve()}")
            v.Upload()
            print(gs.meta_str(*gs.get_meta(v)))
            stat.uploaded += 1
        else:
            print(tm.name, flush=True)

    stat.report()
