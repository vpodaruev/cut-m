#!/usr/bin/python3

import argparse
import json5 as json
import pathlib
import traceback

import cut
import google_serve as gs
import utils as ut
import version as vrs


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


def get_video_info(args):
    pass


def get_tempdir(args):
    tempdir = pathlib.Path(args["temporary_dir"])

    if not tempdir.exists():
        ut.logger().debug(f"create temporary dir '{tempdir.resolve()}'")
        tempdir.mkdir(parents=True)

    return tempdir


class Main:
    def __init__(self, args):
        self.args = args
        self.auth_token = ut.checked_path(args["auth_token"])
        # service
        self._tempdir = None
        self._video_file = None
        self._tm_codes = None
        self._fragments = None

    def tempdir(self):
        if not self._tempdir:
            self._tempdir = get_tempdir(self.args)
        return self._tempdir

    def video_file(self):
        if self._video_file:
            return self._video_file

        url = self.args["video_url"]
        self._video_file = gs.download_video(gs.as_id(url), self.tempdir(), self.auth_token)
        return self._video_file

    def time_codes(self):
        if self._tm_codes:
            return self._tm_codes

        # extract time codes from google worksheet
        sht = gs.get_sheet(self.auth_token)
        wsht = gs.open_worksheet(sht, self.args["worksheet_url"])
        self._tm_codes = gs.extract_timing(wsht,
                                           self.args["head_row"],
                                           self.args["n_head_rows"],
                                           gs.TabColumns(
                                              self.args["columns"]["slice"],
                                              self.args["columns"]["start"],
                                              self.args["columns"]["end"],
                                              self.args["columns"]["name"],
                                           ))
        return self._tm_codes

    def uploaded_fragments(self):
        # get list of fragments that are done
        outdir_id = gs.as_id(self.args["output_dir_url"])
        return gs.list_videos(outdir_id)

    def fragments(self, stat, callback=None):
        if self._fragments:
            return self._fragments

        # cut fragments by time code
        fragdir = self.tempdir()/"fragments"
        fragdir.mkdir(exist_ok=True)

        tm_codes = self.time_codes()
        uploaded = self.uploaded_fragments()
        video = self.video_file()
        n = len(tm_codes)
        w = len(f"{n}")  # for pretty print
        self._fragments = []
        for tm in tm_codes:
            frag = cut.make_filename(self.video_file(), tm, fragdir)
            stat.total += 1
            print(f"{stat.total:0{w}d}/{n}", end=" ")
            if frag.name in uploaded:
                info = gs.get_meta(uploaded[frag.name])
                print('=', gs.meta_str(*info))
                stat.ready += 1
                continue

            print(">", end=" ", flush=True)
            if not frag.exists():
                s = cut.correct_time_by(tm.start, self.args["correct"]["start_time"])
                e = cut.correct_time_by(tm.end, self.args["correct"]["end_time"])
                ok = cut.make_fragment(video, s, e, frag)
                if not ok:
                    stat.failed += 1
                    print("[FAILED] failed to cut", frag.name, flush=True)
                    continue
                self._fragments.append(frag)
            print(tm.name, flush=True)

        return self._fragments

    def upload(self, stat):
        outdir_id = gs.as_id(self.args["output_dir_url"])
        gd = gs.get_drive(self.auth_token)
        fragments = self.fragments(stat)

        n = len(fragments)
        w = len(f"{n}")  # for pretty print
        for frag in fragments:
            print(f"{stat.total:0{w}d}/{n}", ">", end=" ", flush=True)
            v = gd.CreateFile(metadata={
                "parents": [
                    {"id": outdir_id}
                ],
                "title": frag.name
            })
            v.SetContentFile(f"{frag.resolve()}")
            v.Upload()
            print(gs.meta_str(*gs.get_meta(v)))
            stat.uploaded += 1


def main_console():
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--config", type=pathlib.Path,
                        default=ut.application_path()/"config.json",
                        help="file with slicing settings in JSON5 format"
                             " [default: %(default)s]")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {vrs.get_version()}")

    args = parse_args(parser)
    cut.ffmpeg = ut.as_command(args["ffmpeg"])
    ut.set_log_level(args["log_level"])
    ut.logger().debug(f"version is '{vrs.get_version()}'")
    ut.logger().debug(f"arguments - {args}")

    stat = ut.Statistics()
    m = Main(args)
    m.video_file()
    m.time_codes()
    m.fragments(stat)
    if args["do_upload"]:
        m.upload(stat)

    stat.report()


if __name__ == "__main__":
    try:
        main_console()
    except Exception:
        exc = traceback.format_exc()
        ut.logger().critical(exc)
        print(exc)

    input("Press Enter to exit...")
