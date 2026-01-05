from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def build(onefile: bool = False, name: str = "yt-dlp-gui"):
    if shutil.which("pyinstaller") is None:
        raise SystemExit("PyInstaller is required. Install with `python -m pip install pyinstaller`.")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        name,
        "--windowed",
        "-m",
        "gui",
    ]
    if onefile:
        cmd.append("--onefile")

    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)
    dist_dir = Path("dist") / name
    print(f"Build finished in {dist_dir.resolve()}")


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Build a standalone yt-dlp GUI bundle with PyInstaller.")
    parser.add_argument("--onefile", action="store_true", help="Build a single-file executable")
    parser.add_argument("--name", default="yt-dlp-gui", help="Executable/bundle name")
    args = parser.parse_args(argv)
    build(onefile=args.onefile, name=args.name)


if __name__ == "__main__":
    main()
