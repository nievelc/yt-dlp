from __future__ import annotations

import sys


def main():
    try:
        from . import qtapp

        return qtapp.run_qt()
    except Exception as exc:  # noqa: BLE001
        print(f"Falling back to Tkinter GUI: {exc}", file=sys.stderr)
        from . import tkapp

        return tkapp.run_tk()


if __name__ == "__main__":
    raise SystemExit(main())
