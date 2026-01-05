from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from .downloader import DownloadSettings, run_download, summarize_progress
from .utils import format_eta, format_speed


class TkGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("yt-dlp GUI")
        self.geometry("760x640")
        self.queue: queue.Queue = queue.Queue()
        self.cancel_event: threading.Event | None = None
        self.worker: threading.Thread | None = None
        self._build_ui()
        self.after(100, self._process_queue)

    def _build_ui(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="URL(s)").grid(row=0, column=0, sticky="w")
        self.url_text = tk.Text(main, height=4, width=80)
        self.url_text.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(0, 8))

        ttk.Label(main, text="Output folder").grid(row=2, column=0, sticky="w")
        self.output_var = tk.StringVar(value=str(Path.cwd()))
        output_entry = ttk.Entry(main, textvariable=self.output_var, width=60)
        output_entry.grid(row=3, column=0, sticky="ew")
        ttk.Button(main, text="Browse…", command=self._choose_folder).grid(row=3, column=1, padx=(8, 0))

        ttk.Label(main, text="Format").grid(row=4, column=0, sticky="w")
        self.format_var = tk.StringVar(value="Best")
        format_combo = ttk.Combobox(main, textvariable=self.format_var, values=["Best", "Audio", "Custom"], state="readonly")
        format_combo.grid(row=5, column=0, sticky="ew")
        format_combo.bind("<<ComboboxSelected>>", lambda *_: self._sync_format())

        ttk.Label(main, text="Custom format").grid(row=6, column=0, sticky="w")
        self.custom_var = tk.StringVar()
        self.custom_entry = ttk.Entry(main, textvariable=self.custom_var, width=60)
        self.custom_entry.grid(row=7, column=0, columnspan=2, sticky="ew")

        ttk.Label(main, text="Quality cap").grid(row=4, column=1, sticky="w")
        self.quality_var = tk.StringVar(value="Best available")
        quality_combo = ttk.Combobox(
            main,
            textvariable=self.quality_var,
            values=["Best available", "2160p", "1440p", "1080p", "720p", "480p"],
            state="readonly",
        )
        quality_combo.grid(row=5, column=1, sticky="ew")

        self.subtitles_var = tk.BooleanVar(value=False)
        self.metadata_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main, text="Download subtitles", variable=self.subtitles_var).grid(row=8, column=0, sticky="w")
        ttk.Checkbutton(main, text="Embed metadata + thumbnail", variable=self.metadata_var).grid(row=8, column=1, sticky="w")

        ttk.Label(main, text="Advanced options").grid(row=9, column=0, sticky="w", pady=(8, 0))
        self.advanced_text = tk.Text(main, height=3, width=80)
        self.advanced_text.grid(row=10, column=0, columnspan=3, sticky="nsew")

        self.progress = ttk.Progressbar(main, orient="horizontal", length=400, mode="determinate")
        self.progress.grid(row=11, column=0, columnspan=2, pady=8, sticky="ew")
        self.status_label = ttk.Label(main, text="Idle")
        self.status_label.grid(row=11, column=2, sticky="e")

        self.speed_label = ttk.Label(main, text="")
        self.speed_label.grid(row=12, column=0, sticky="w")
        self.eta_label = ttk.Label(main, text="")
        self.eta_label.grid(row=12, column=1, sticky="w")

        controls = ttk.Frame(main)
        controls.grid(row=13, column=0, columnspan=3, pady=8, sticky="ew")
        self.start_btn = ttk.Button(controls, text="Start download", command=self._start_download)
        self.start_btn.pack(side=tk.LEFT)
        self.cancel_btn = ttk.Button(controls, text="Cancel", command=self._cancel_download, state="disabled")
        self.cancel_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.log = tk.Text(main, height=14, width=90, state="disabled")
        self.log.grid(row=14, column=0, columnspan=3, sticky="nsew")

        main.rowconfigure(1, weight=0)
        main.rowconfigure(10, weight=1)
        main.rowconfigure(14, weight=2)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.columnconfigure(2, weight=1)
        self._sync_format()

    def _sync_format(self):
        is_custom = self.format_var.get().startswith("Custom")
        is_audio = self.format_var.get().startswith("Audio")
        self.custom_entry.configure(state="normal" if is_custom else "disabled")
        self.quality_var.set(self.quality_var.get() if not is_audio else "Best available")
        self.advanced_text.configure(height=3)

    def _choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)

    def _append_log(self, text: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert(tk.END, f"[{timestamp}] {text}\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def _start_download(self):
        if self.worker and self.worker.is_alive():
            return
        urls = self.url_text.get("1.0", tk.END).strip()
        if not urls:
            messagebox.showwarning("Missing URL", "Please provide at least one URL to download.")
            return
        settings = DownloadSettings(
            urls=urls,
            output_dir=self.output_var.get().strip(),
            format_choice=self.format_var.get().split()[0].lower(),
            custom_format=self.custom_var.get(),
            quality=self.quality_var.get(),
            subtitles=self.subtitles_var.get(),
            embed_metadata=self.metadata_var.get(),
            advanced_options=self.advanced_text.get("1.0", tk.END).strip().replace("\n", " "),
        )

        self.cancel_event, self.worker = run_download(
            settings,
            log_callback=lambda msg: self.queue.put(("log", msg)),
            progress_callback=lambda info: self.queue.put(("progress", summarize_progress(info))),
            status_callback=lambda msg: self.queue.put(("status", msg)),
            completion_callback=lambda success, msg: self.queue.put(("complete", success, msg)),
        )
        self._set_running(True)

    def _cancel_download(self):
        if self.cancel_event:
            self.cancel_event.set()
            self._append_log("Cancelling download…")

    def _set_running(self, running: bool):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")

    def _process_queue(self):
        try:
            while True:
                item = self.queue.get_nowait()
                self._handle_event(item)
        except queue.Empty:
            pass
        self.after(100, self._process_queue)

    def _handle_event(self, item):
        kind = item[0]
        if kind == "log":
            self._append_log(item[1])
        elif kind == "status":
            self.status_label.configure(text=item[1])
        elif kind == "progress":
            self._update_progress(item[1])
        elif kind == "complete":
            _, success, msg = item
            self._append_log(msg)
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress["value"] = 100 if success else 0
            self._set_running(False)
            if not success:
                self.status_label.configure(text=f"Error: {msg}")
            else:
                self.status_label.configure(text="Completed")
        else:
            self._append_log(str(item))

    def _update_progress(self, data: dict):
        percent = data.get("percent")
        if percent is None:
            self.progress.configure(mode="indeterminate")
            self.progress.start(10)
        else:
            if str(self.progress.cget("mode")) != "determinate":
                self.progress.stop()
                self.progress.configure(mode="determinate")
            self.progress["value"] = percent
        self.speed_label.configure(text=f"Speed: {format_speed(data.get('speed'))}" if data.get("speed") else "")
        self.eta_label.configure(text=f"ETA: {format_eta(data.get('eta'))}" if data.get("eta") else "")
        if data.get("status"):
            self.status_label.configure(text=data["status"].capitalize())


def run_tk():
    app = TkGui()
    app.mainloop()
