# CutM
Download a video file and cut fragments out of it

This is the console version at the moment. It is planned to add a web interface for convenience.

The user must provide a `config.json` file with all the necessary data in [JSON5](https://json5.org) format (an example can be found in the repository). The first thing the program needs to know is the video URL (currently from Google Drive). The timing of the fragments will be taken from a Google worksheet. Therefore, you must specify the worksheet URL. For ease of parsing, specify the number of rows of the table header and the row number in that header to find the required columns. The required columns are:
- _slice_ is the column with checkboxes, where the fragments to be cut are marked,
- _start_ is the column with the start time of the fragments,
- _end_ is the column with the end time of the fragments,
- _name_ is the column with fragment names (`fragment` for empty values).

Sometimes it is useful to correct all the fragments by a second or two at the start or end to cut them with some margin. So, you can specify these values (in seconds) in the node _correct_. The values can be negative.

Specify a Google Drive folder for uploading prepared fragments. Set `true` as the `do_upload` value for the actual upload.

There are several advanced settings available. You can specify the relative or absolute path to the temporary directory where the downloaded file and its fragments will be placed, the logging level, the path to the `ffmpeg` utility and the authorization token file.

Note that in order to access Google Drive, you must provide an authorization token file (usually named `token.json`). Follow the first two steps as described [here](https://docs.iterative.ai/PyDrive2/quickstart/#authentication), and then instead of creating credentials, create a service account and save the provided token.

_Inspired by the [Creative Society](https://creativesociety.com) international project!_


## Requirements

Application is written in [Python](https://www.python.org) using:

- [PyDrive2](https://github.com/iterative/PyDrive2)
- [gspread](https://github.com/burnash/gspread)
- [json5](https://github.com/dpranke/pyjson5)
- [pathvalidate](https://github.com/thombashi/pathvalidate)
- [tqdm](https://pypi.org/project/tqdm)

You will also need the [PyInstaller](https://pypi.org/project/pyinstaller) package to create an independent executable.


## Dependencies

- [ffmpeg](https://ffmpeg.org)

Use `config.json` to specify the actual path to the utility. Or just `ffmpeg` if it is in the standard system paths.
