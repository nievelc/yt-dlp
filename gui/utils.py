from __future__ import annotations


def format_speed(speed: float | None) -> str:
    if not speed:
        return ""
    units = ["B/s", "KiB/s", "MiB/s", "GiB/s"]
    idx = 0
    value = float(speed)
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    return f"{value:.2f} {units[idx]}"


def format_eta(eta: float | int | None) -> str:
    if eta in (None, 0):
        return ""
    eta = int(eta)
    mins, secs = divmod(eta, 60)
    hours, mins = divmod(mins, 60)
    if hours:
        return f"{hours:d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"
