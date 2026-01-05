from __future__ import annotations

import threading

from gui.downloader import DownloadSettings, build_ydl_options


def test_build_options_with_metadata(tmp_path):
    settings = DownloadSettings(
        urls="https://example.com/video",
        output_dir=str(tmp_path),
        format_choice="audio",
        custom_format="",
        quality="Best available",
        subtitles=True,
        embed_metadata=True,
        advanced_options="--limit-rate 10K",
    )

    parsed_urls, opts = build_ydl_options(
        ["https://example.com/video"],
        settings,
        log_callback=lambda msg: None,
        progress_callback=lambda info: None,
        status_callback=lambda msg: None,
        cancel_event=threading.Event(),
    )

    assert parsed_urls == ["https://example.com/video"]
    assert opts["format"] == "bestaudio/best"
    assert opts["writesubtitles"] is True
    assert opts["ratelimit"] == 10240
    assert opts["paths"]["home"] == str(tmp_path)
    assert any(pp.get("key") == "FFmpegMetadata" for pp in opts.get("postprocessors", []))
