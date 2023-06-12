#!/usr/bin/env python3

import gspread
import pathvalidate as pv
import re
import tqdm

from collections import namedtuple
from pydrive2.files import ApiRequestError, FileNotUploadedError
from urllib.parse import urlparse

import utils as ut


_credentials = None
_gd = None
_gc = None


def get_credentials(auth_token):
    global _credentials
    if _credentials is not None:
        return _credentials

    from google.oauth2.service_account import Credentials
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    _credentials = Credentials.from_service_account_file(
        auth_token.as_posix(),
        scopes=scopes
    )
    return _credentials


def get_drive(auth_token):
    global _gd
    if _gd is not None:
        return _gd

    from pydrive2.auth import GoogleAuth
    from pydrive2.drive import GoogleDrive
    from oauth2client.service_account import ServiceAccountCredentials
    scope = [
        "https://www.googleapis.com/auth/drive"
    ]
    gauth = GoogleAuth()
    gauth.auth_method = "service"
    sac = ServiceAccountCredentials
    token = auth_token.as_posix()
    gauth.credentials = sac.from_json_keyfile_name(token, scope)
    _gd = GoogleDrive(gauth)
    return _gd


def get_sheet(auth_token):
    """Return client by `auth_token` to get access to Google spreadsheets"""
    global _gc
    if _gc is not None:
        return _gc

    credentials = get_credentials(auth_token)
    _gc = gspread.authorize(credentials)
    return _gc


_gid_pat = re.compile(r"[-\w]{25,}")


def as_id(url):
    """Return ID from Google Drive URL"""
    if _gid_pat.fullmatch(url):  # has ID instead of URL
        return url

    path = urlparse(url).path
    if m := _gid_pat.search(path):
        return m.group(0)

    raise RuntimeError(f"failed to extract ID from URL ({url})")


def is_video(file):
    """Return true if Google disk `file` is video"""
    return file["mimeType"].startswith("video")


def is_folder(id):
    """Return true if Google disk resource with `id` is folder"""
    r = _gd.CreateFile({"id": id})
    return r["mimeType"].endswith("folder")


def get_meta(file):
    mime = file["mimeType"]
    title = file["title"]
    ut.logger().debug(f"try file '{mime} - {title}'")
    size = int(file["fileSize"])
    return mime, title, size


def meta_str(mime, title, size):
    return f"{ut.humansize(size)} {mime} - {title}"


def download_video(id, path, auth_token, indent=""):
    """Access a Google Drive file and download it on disk at path location"""
    ut.logger().debug(f"resource id is '{id}'")
    file = get_drive(auth_token).CreateFile({"id": id})
    if not is_video(file):
        raise RuntimeError("not a video file (id={id})")

    mime, title, size = get_meta(file)
    print('>', meta_str(mime, title, size))
    target = path / pv.sanitize_filename(title)
    if not target.exists() or size != target.stat().st_size:
        ut.logger().debug(f"{ut.humansize(size)} {mime} - '{title}'")
        ut.logger().debug("downloading...")
        try:
            progress_bar = tqdm.tqdm(total=size, unit='B', unit_scale=True)

            def download_progress(current_size, total_size):
                progress_bar.update(current_size - progress_bar.n)

            file.GetContentFile(target.as_posix(), callback=download_progress)
            progress_bar.close()
        except (ApiRequestError, FileNotUploadedError) as e:
            ut.logger().exception(f"failed to download file '{title}', '{e}'")
            raise
    else:
        ut.logger().debug("skip")
    return target


def list_videos(id):
    """Return video files list of Google Drive folder with `id`"""
    videos = {}
    query = f"'{id}' in parents and trashed=false" \
            " and mimeType contains 'video'"
    for file in _gd.ListFile({'q': query}).GetList():
        title = file["title"]
        ut.logger().debug(f"try file '{title}'")
        size = int(file["fileSize"])
        ut.logger().debug(f"file size '{size}'")
        videos.update({f"{title}": file})
    return videos


_gid_frag_pat = re.compile(r"gid=([\d]+)")


def open_worksheet(gc, url):
    """Return worksheet by `url` using client `gc`"""
    gid = 0
    sht = gc.open_by_url(url)
    if m := _gid_frag_pat.search(urlparse(url).fragment):
        gid = int(m.group(1))

    return sht.get_worksheet_by_id(gid)


TmCode = namedtuple("TmCode", ["row", "start", "end", "name"])
_timing_pat = re.compile(r"\d*([:,.' ][0-5]?\d?){0,2}")


def is_valid_time(tm_code):
    return _timing_pat.fullmatch(tm_code) is not None


def as_video_name(s):
    """Make string `s` appropriate for future use as video name"""
    s = s.split("/", maxsplit=1)[0]
    s = pv.sanitize_filename(s)
    s = s.strip().rstrip(".,")
    return s if len(s) else "fragment"


TabColumns = namedtuple("TabColumns", ["slice", "start", "end", "name"])


def clean_whitespace(str_list):
    """Return list of strings `str_list`, in which all spaces from the end are removed
       and all spaces inside are replaced with a single space"""
    return [re.sub(r"\s+", " ", item.strip()) for item in str_list]


def column_index(header, cols):
    ut.logger().debug(f"table header {header}")
    ut.logger().debug(f"{cols}")
    header, cols = (clean_whitespace(item) for item in (header, cols))
    idx = TabColumns(*[header.index(item) for item in cols])
    ut.logger().debug(f"{idx}")
    return idx


def load_table(worksheet, ihead, n_head_rows):
    vals = worksheet.get_all_values()
    header = vals[ihead-1]
    rows = vals[n_head_rows:]
    return header, rows


def filter_rows(header, rows, cols):
    idx = column_index(header, cols)
    rows = [TmCode(i, *[row[j] for j in idx[1:]])
            for i, row in zip(range(len(rows)), rows)
            if row[idx.slice].lower() == "true"]
    return rows


def extract_timing(wsht, ihead, n_head_rows, cols):
    header, rows = load_table(wsht, ihead, n_head_rows)
    rows = filter_rows(header, rows, cols)
    tm_codes = []
    for r in rows:
        s, e, name = r.start, r.end, r.name
        if not is_valid_time(s) or not is_valid_time(e):
            continue
        s, e = ut.to_seconds(s), ut.to_seconds(e)
        name = as_video_name(name)
        if e - s > 0.:
            tm_codes.append(TmCode(n_head_rows + r.row + 1,
                                   ut.to_hhmmss(s),
                                   ut.to_hhmmss(e),
                                   name))
    return tm_codes
