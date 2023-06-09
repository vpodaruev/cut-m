#!/usr/bin/python3

import datetime
import logging
import re
import pathlib
import shutil
import sys
import time


def humansize(nbytes):
    """Returns file size in human readable form, e.g. KB, MB, etc."""
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    for s in suffixes:
        if nbytes < 1024 or s == suffixes[-1]:
            n = f"{nbytes:.1f}".removesuffix(".0")
            return f"[{n} {s}]"
        nbytes /= 1024
    raise RuntimeError("unreachable code point")


class Statistics:
    """Statistics base"""

    def __init__(self):
        self.total = 0
        self.ready = 0     # already exists
        self.failed = 0
        self.uploaded = 0
        self.start_time = time.time()

    def elapsed(self):
        dt = time.time() - self.start_time
        return datetime.timedelta(seconds=dt)

    def report(self):
        dt = self.elapsed()
        print()
        print("="*64)
        print()
        if self.total == self.ready + self.uploaded:
            print("[OK] All done! Uploaded!/Готово! Загружено!")
        elif self.failed == 0:
            print("[OK] All done!/Готово!")
        else:
            print("[FAILED] There were errors! See download.log for details..."
                  "/Произошли ошибки! Смотри детали в файле download.log...")
        print()
        print(f"Wall clock time/Время работы: {dt}")
        print()
        print(f"Total/Всего: {self.total} files/файлов")
        print(f"  - Ready on Google Drive: {self.ready} files/загружено ранее")
        print(f"  - Newly uploaded: {self.uploaded} files/загружено сейчас")
        print(f"  - Failed: {self.failed} files/не удалось обработать")
        print()


def application_path():
    return pathlib.Path(sys.argv[0]).parent


log_level = {
    "disable": None,
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


logging.basicConfig(filename="cut-m.log", encoding="utf-8",
                    format="%(asctime)s:%(module)s:%(levelname)s: %(message)s",
                    level=logging.CRITICAL)


def logger():
    return logging.getLogger("cut-massively")


def set_log_level(name):
    level = log_level.get(name, "critical")
    if level is not None:
        logging.disable(logging.NOTSET)
        logger().setLevel(level)
    else:
        logging.disable(logging.CRITICAL)


def as_command(s):
    """Return command `s` as pathlib.Path object
       if available from the command line"""
    cmd = pathlib.Path(s)
    if shutil.which(s) is not None:
        return cmd

    cmd = application_path()/cmd
    if shutil.which(f"{cmd}") is not None:
        return cmd

    raise RuntimeError(f"command not available ({s})")


def checked_path(path):
    """Return `path` as pathlib.Path object if it exists.
       If not, check a relative to application one"""
    p = pathlib.Path(path)
    if p.exists():
        return p
    elif not p.is_absolute():     # try path relative to application
        q = application_path()/p
        if q.exists():
            return q
    raise RuntimeError(f"path doesn't exist ({p})")


def to_hhmmss(seconds, delim=":"):
    """Return hh:mm:ss time string converted from `seconds`"""
    seconds = int(seconds)
    minutes = seconds // 60
    hours = minutes // 60
    return f"{hours:02d}{delim}{minutes - 60*hours:02d}" \
           f"{delim}{seconds - 60*minutes:02d}"


def to_seconds(hhmmss):
    """Return time in seconds converted from hh:mm:ss string"""
    tt = [int(x) if x else 0 for x in re.split(r"[:,.' ]", hhmmss)]
    s = 0
    for x, n in zip(reversed(tt), range(len(tt))):
        s += x * 60**n
    return s


def as_suffix(start, end):
    start, end = start.replace(":", "."), end.replace(":", ".")
    return f"_{start}-{end}"
