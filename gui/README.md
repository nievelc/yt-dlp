# yt-dlp desktop GUI

This subproject provides a lightweight desktop application for running yt-dlp without using the command line. The GUI prefers **PySide6/Qt** and falls back to **Tkinter** automatically when Qt is unavailable.

## Running

```bash
python -m gui
```

### Features

- URL input (multiple URLs separated by newlines or commas)
- Output folder picker
- Format selector: best, audio-only, or custom format string
- Optional quality cap (2160p/1440p/1080p/720p/480p)
- Subtitles and metadata embedding toggles
- Advanced options text box that accepts raw yt-dlp CLI flags
- Live progress (status, percent, speed, ETA) and log output
- Cancel the active download cleanly

## Dependencies

- Python 3.10+
- `PySide6` (for the Qt UI). If it is not installed or fails to load, the Tkinter UI is used automatically.

Optional extras for development/builds can be installed with:

```bash
python -m pip install .[gui]
```

## Building executables with PyInstaller

1. Install the build requirements (PyInstaller and PySide6):

   ```bash
   python -m pip install .[gui]
   ```

2. Run the build helper. The default produces a windowed, onedir bundle named `yt-dlp-gui`:

   ```bash
   python gui/build.py
   ```

   For a single-file bundle:

   ```bash
   python gui/build.py --onefile
   ```

### Platform notes

- **Windows:** The default build uses `--windowed` to suppress the console. Run `python gui/build.py --onefile` for a single EXE.
- **macOS:** PyInstaller builds an app bundle inside `dist/yt-dlp-gui`. Launch it directly or run the generated binary in `dist/yt-dlp-gui/yt-dlp-gui`.
- **Linux:** The default onedir build works on the current distribution. For broader compatibility, build on the oldest distribution you target.

## Development

- A basic option-parsing test is available and can be run with `python -m pytest test/test_gui_options.py`.
- The GUI itself can be started with `python -m gui` from the repository root.
