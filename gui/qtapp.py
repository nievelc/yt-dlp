from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from yt_dlp.utils import DownloadCancelled

from .downloader import DownloadSettings, execute_download, summarize_progress
from .utils import format_eta, format_speed


class DownloadThread(QThread):
    log = Signal(str)
    progress = Signal(dict)
    status = Signal(str)
    completed = Signal(bool, str)

    def __init__(self, settings: DownloadSettings):
        super().__init__()
        self.settings = settings
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            execute_download(
                self.settings,
                log_callback=self.log.emit,
                progress_callback=lambda status: self.progress.emit(summarize_progress(status)),
                status_callback=self.status.emit,
                cancel_event=self.cancel_event,
            )
            self.completed.emit(True, "Completed")
        except DownloadCancelled:
            self.completed.emit(False, "Cancelled")
        except Exception as exc:  # noqa: BLE001
            self.completed.emit(False, str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("yt-dlp GUI")
        self._thread: DownloadThread | None = None
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        form = QFormLayout()
        layout.addLayout(form)

        self.url_input = QPlainTextEdit()
        self.url_input.setPlaceholderText("Enter one URL per line")
        self.url_input.setFixedHeight(60)
        form.addRow("URL(s)", self.url_input)

        path_row = QHBoxLayout()
        self.output_input = QLineEdit()
        self.output_input.setText(str(Path.cwd()))
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.clicked.connect(self._choose_folder)
        path_row.addWidget(self.output_input)
        path_row.addWidget(self.browse_btn)
        form.addRow("Output folder", path_row)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["Best", "Audio only", "Custom"])
        self.format_combo.currentIndexChanged.connect(self._on_format_change)
        form.addRow("Format", self.format_combo)

        self.custom_format_input = QLineEdit()
        self.custom_format_input.setPlaceholderText("e.g. bestvideo[height<=1080]+bestaudio/best")
        self.custom_format_input.setEnabled(False)
        form.addRow("Custom format", self.custom_format_input)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Best available", "2160p", "1440p", "1080p", "720p", "480p"])
        form.addRow("Quality cap", self.quality_combo)

        toggles = QHBoxLayout()
        self.subtitles_check = QCheckBox("Download subtitles")
        self.metadata_check = QCheckBox("Embed metadata + thumbnail")
        toggles.addWidget(self.subtitles_check)
        toggles.addWidget(self.metadata_check)
        form.addRow("Options", toggles)

        self.advanced_input = QPlainTextEdit()
        self.advanced_input.setPlaceholderText("Advanced yt-dlp CLI options (one line)")
        self.advanced_input.setFixedHeight(60)
        form.addRow("Advanced options", self.advanced_input)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_row.addWidget(self.progress_bar)

        self.status_label = QLabel("Idle")
        progress_row.addWidget(self.status_label)
        layout.addLayout(progress_row)

        speed_row = QHBoxLayout()
        self.speed_label = QLabel("")
        self.eta_label = QLabel("")
        speed_row.addWidget(self.speed_label)
        speed_row.addWidget(self.eta_label)
        layout.addLayout(speed_row)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start download")
        self.start_btn.clicked.connect(self._start_download)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_download)
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_output.setPlaceholderText("Log output will appear here")
        layout.addWidget(self.log_output)

    def _choose_folder(self):
        directory = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if directory:
            self.output_input.setText(directory)

    def _on_format_change(self, index: int):
        self.custom_format_input.setEnabled(self.format_combo.currentText() == "Custom")
        self.quality_combo.setEnabled(self.format_combo.currentText() != "Audio only")

    def _append_log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_output.appendPlainText(f"[{timestamp}] {message}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def _start_download(self):
        if self._thread is not None:
            return
        urls = self.url_input.toPlainText().strip()
        if not urls:
            self._append_log("Please enter at least one URL.")
            return

        settings = DownloadSettings(
            urls=urls,
            output_dir=self.output_input.text().strip(),
            format_choice=self.format_combo.currentText().split()[0].lower(),
            custom_format=self.custom_format_input.text(),
            quality=self.quality_combo.currentText(),
            subtitles=self.subtitles_check.isChecked(),
            embed_metadata=self.metadata_check.isChecked(),
            advanced_options=self.advanced_input.toPlainText().strip().replace("\n", " "),
        )

        self._thread = DownloadThread(settings)
        self._thread.log.connect(self._append_log)
        self._thread.progress.connect(self._update_progress)
        self._thread.status.connect(self._update_status)
        self._thread.completed.connect(self._download_done)
        self._set_running(True)
        self._thread.start()

    def _cancel_download(self):
        if self._thread:
            self._append_log("Cancelling download…")
            self._thread.cancel()

    def _set_running(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.url_input.setEnabled(not running)

    def _update_status(self, text: str):
        self.status_label.setText(text)

    def _update_progress(self, data: dict):
        if data.get("status") == "finished":
            self.progress_bar.setValue(100)
            self.status_label.setText("Post-processing")
            return

        percent = data.get("percent")
        if percent is None:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(percent))

        speed_text = format_speed(data.get("speed"))
        eta_text = format_eta(data.get("eta"))
        self.speed_label.setText(f"Speed: {speed_text}" if speed_text else "")
        self.eta_label.setText(f"ETA: {eta_text}" if eta_text else "")
        if data.get("status"):
            self.status_label.setText(data["status"].capitalize())

    def _download_done(self, success: bool, message: str):
        self._append_log(message)
        self._set_running(False)
        self.progress_bar.setRange(0, 100)
        if not success:
            self.status_label.setText(f"Error: {message}")
        else:
            self.status_label.setText("Completed")
        if self._thread:
            self._thread.wait(500)
        self._thread = None


def run_qt():
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.resize(720, 640)
    window.show()
    return app.exec()
