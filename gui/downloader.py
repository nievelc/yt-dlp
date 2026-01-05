from __future__ import annotations

import contextlib
import io
import shlex
import threading
from dataclasses import dataclass
from typing import Callable, List, Sequence

from yt_dlp import YoutubeDL, parse_options
from yt_dlp.utils import DownloadCancelled


ProgressCallback = Callable[[dict], None]
LogCallback = Callable[[str], None]
StatusCallback = Callable[[str], None]
CompletionCallback = Callable[[bool, str], None]


QUALITY_FORMATS = {
    "Best available": None,
    "2160p": "bv*[height<=2160]+ba/b[height<=2160]",
    "1440p": "bv*[height<=1440]+ba/b[height<=1440]",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
    "720p": "bv*[height<=720]+ba/b[height<=720]",
    "480p": "bv*[height<=480]+ba/b[height<=480]",
}


@dataclass
class DownloadSettings:
    urls: str
    output_dir: str
    format_choice: str
    custom_format: str
    quality: str
    subtitles: bool
    embed_metadata: bool
    advanced_options: str


class UILogger:
    def __init__(self, callback: LogCallback):
        self._callback = callback

    def debug(self, msg):
        if msg is not None:
            self._callback(str(msg))

    def info(self, msg):
        self.debug(msg)

    def warning(self, msg):
        self._callback(f"WARNING: {msg}")

    def error(self, msg):
        self._callback(f"ERROR: {msg}")


def _build_format(settings: DownloadSettings) -> str | None:
    if settings.format_choice == "audio":
        return "bestaudio/best"
    if settings.format_choice == "custom":
        return settings.custom_format.strip() or None

    quality_fmt = QUALITY_FORMATS.get(settings.quality)
    return quality_fmt or "bv*+ba/best"


def summarize_progress(status: dict) -> dict:
    total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
    downloaded = status.get("downloaded_bytes") or 0
    percent = None
    if total:
        percent = max(0.0, min(100.0, downloaded / total * 100))

    return {
        "status": status.get("status"),
        "filename": status.get("filename") or status.get("info_dict", {}).get("title"),
        "percent": percent,
        "speed": status.get("speed"),
        "eta": status.get("eta"),
    }


def _parse_cli_args(urls: Sequence[str], settings: DownloadSettings) -> tuple[List[str], List[str]]:
    args: List[str] = []
    if settings.output_dir:
        args.extend(["-P", settings.output_dir])

    fmt = _build_format(settings)
    if fmt:
        args.extend(["-f", fmt])

    if settings.subtitles:
        args.extend(["--write-subs", "--sub-langs", "all"])

    if settings.embed_metadata:
        args.extend(["--add-metadata", "--embed-thumbnail"])

    if settings.advanced_options:
        try:
            args.extend(shlex.split(settings.advanced_options))
        except ValueError as err:
            raise ValueError(f"Advanced options error: {err}") from err

    parsed_urls = [url for url in urls if url]
    if not parsed_urls:
        raise ValueError("At least one URL is required.")

    return args, parsed_urls


def build_ydl_options(
    urls: Sequence[str],
    settings: DownloadSettings,
    log_callback: LogCallback,
    progress_callback: ProgressCallback,
    status_callback: StatusCallback,
    cancel_event: threading.Event,
):
    args, parsed_urls = _parse_cli_args(urls, settings)
    cli_output = io.StringIO()
    try:
        with contextlib.redirect_stdout(cli_output), contextlib.redirect_stderr(cli_output):
            _, _, parsed_urls, ydl_opts = parse_options([*args, *parsed_urls])
    except SystemExit as exc:
        raise ValueError(cli_output.getvalue().strip() or str(exc)) from exc
    except Exception as exc:
        raise ValueError(f"Unable to parse options: {exc}") from exc

    def hook(status):
        if cancel_event.is_set():
            raise DownloadCancelled("Cancelled")
        progress_callback(status)

    ydl_opts["logger"] = UILogger(log_callback)
    ydl_opts["progress_hooks"] = [hook]
    ydl_opts["progress_with_newline"] = True
    ydl_opts["quiet"] = False
    ydl_opts["no_warnings"] = False

    status_callback("Preparing download…")
    return parsed_urls, ydl_opts


def execute_download(
    settings: DownloadSettings,
    log_callback: LogCallback,
    progress_callback: ProgressCallback,
    status_callback: StatusCallback,
    cancel_event: threading.Event,
):
    urls = [u.strip() for u in settings.urls.replace(",", "\n").splitlines() if u.strip()]
    parsed_urls, ydl_opts = build_ydl_options(urls, settings, log_callback, progress_callback, status_callback, cancel_event)
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download(parsed_urls)


def run_download(
    settings: DownloadSettings,
    log_callback: LogCallback,
    progress_callback: ProgressCallback,
    status_callback: StatusCallback,
    completion_callback: CompletionCallback,
):
    cancel_event = threading.Event()

    def _thread():
        try:
            execute_download(settings, log_callback, progress_callback, status_callback, cancel_event)
            completion_callback(True, "Completed")
        except DownloadCancelled:
            completion_callback(False, "Cancelled")
        except Exception as exc:  # noqa: BLE001
            completion_callback(False, str(exc))

    thread = threading.Thread(target=_thread, daemon=True)
    thread.start()
    return cancel_event, thread
