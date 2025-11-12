import time
import numpy as np
from PyQt6 import QtWidgets, QtCore
import pyqtgraph as pg

from constants import SAMPLE_RATE, ROLLING_SEC, Color, Mode
from stream.buffer import RollingBuffer
from stream.worker import StreamWorker
from widgets.status_led import StatusLED
from ui.sidepanel import Sidepanel
from ui.plot_view import PlotView

WINDOW_SAMPLES = SAMPLE_RATE * ROLLING_SEC


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dev_mode: bool = False):
        super().__init__()
        self.dev_mode = dev_mode
        self.setWindowTitle(f"fold {' [DEV MODE]' if dev_mode else ''}")
        self.resize(1200, 650)

        # Data + threads
        self._buffer = RollingBuffer(WINDOW_SAMPLES)
        self._worker: StreamWorker | None = None
        self._thread: QtCore.QThread | None = None

        # UI metrics
        self._render_frames = 0
        self._last_render_t = time.monotonic()

        # Build UI
        self._build_ui()

        # Render loop
        self._render_timer = QtCore.QTimer(self)
        self._render_timer.timeout.connect(self._render_frame)
        self._render_timer.start(33)

    # =====================================================
    # ---------- UI Composition ----------
    # =====================================================
    def _build_ui(self):
        pg.setConfigOption("background", "k")
        pg.setConfigOption("foreground", "w")

        container = QtWidgets.QWidget()
        self.setCentralWidget(container)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header
        top = QtWidgets.QHBoxLayout()
        self.status_led = StatusLED(14)
        self.status_led.set_color(Color.IDLE)
        self.app_refresh_lbl = QtWidgets.QLabel("Refresh: --- Hz")
        self.app_refresh_lbl.setObjectName("appRefreshLabel")
        top.addWidget(self.status_led)
        top.addSpacing(6)
        top.addWidget(self.app_refresh_lbl)
        top.addStretch(1)
        layout.addLayout(top)

        # Splitter
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # Sidepanel (controls)
        self.sidebar = Sidepanel(self.dev_mode)
        self.sidebar.mode_group.idClicked.connect(self._on_mode_button)
        self.sidebar.start_btn.clicked.connect(self._on_start)
        self.sidebar.stop_btn.clicked.connect(self._on_stop)
        splitter.addWidget(self.sidebar)

        # Plot view (right)
        self.plot_view = PlotView()
        splitter.addWidget(self.plot_view)
        splitter.setSizes([self.sidebar.minimumWidth() + 1, 1000])

        self._apply_mode_visibility(Mode.TEST if self.dev_mode else Mode.SERIAL)

    # =====================================================
    # ---------- Mode handling ----------
    # =====================================================
    def _on_mode_button(self, idx: int):
        modes = (
            [Mode.TEST, Mode.SERIAL, Mode.TCP]
            if self.dev_mode
            else [Mode.SERIAL, Mode.TCP]
        )
        self._apply_mode_visibility(modes[idx])

    def _apply_mode_visibility(self, mode: str):
        self._current_mode_cached = mode
        is_serial = mode == Mode.SERIAL
        is_tcp = mode == Mode.TCP
        for w in (self.sidebar.port_edit, self.sidebar.baud_edit):
            w.setVisible(is_serial)
            w.setEnabled(is_serial)
        for w in (self.sidebar.host_edit, self.sidebar.tcpport_edit):
            w.setVisible(is_tcp)
            w.setEnabled(is_tcp)

    def _current_mode(self) -> str:
        if (
            self.dev_mode
            and getattr(self.sidebar, "test_btn", None)
            and self.sidebar.test_btn.isChecked()
        ):
            return Mode.TEST
        if self.sidebar.serial_btn.isChecked():
            return Mode.SERIAL
        if self.sidebar.tcp_btn.isChecked():
            return Mode.TCP
        return getattr(self, "_current_mode_cached", Mode.SERIAL)

    # =====================================================
    # ---------- Stream control ----------
    # =====================================================
    def _on_start(self):
        if self._thread and self._thread.isRunning():
            return

        mode = self._current_mode()
        params = {
            "port": self.sidebar.port_edit.text(),
            "baud": self.sidebar.baud_edit.text(),
            "host": self.sidebar.host_edit.text(),
            "tcpport": self.sidebar.tcpport_edit.text(),
        }

        self._thread = QtCore.QThread()
        self._worker = StreamWorker(mode, params)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.process)
        self._worker.chunk_ready.connect(self._on_chunk)
        self._worker.status_changed.connect(self._on_status)
        self._worker.finished.connect(self._on_worker_finished)
        self._thread.finished.connect(self._thread.deleteLater)

        self._set_controls_enabled(False)
        self.sidebar.stop_btn.setEnabled(True)
        self.sidebar.start_btn.setEnabled(False)
        self.sidebar.status_lbl.setText("Starting…")
        self.status_led.set_color(Color.WARNING)
        self._thread.start()

    def _on_stop(self):
        if not self._worker:
            return
        self._worker.stop()
        self.sidebar.stop_btn.setEnabled(False)
        self.sidebar.status_lbl.setText("Stopping…")
        self.status_led.set_color(Color.WARNING)

    def _on_worker_finished(self):
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        self._worker = None
        self._thread = None
        self.sidebar.status_lbl.setText("Stopped")
        self.status_led.set_color(Color.IDLE)
        self._set_controls_enabled(True)
        self.sidebar.start_btn.setEnabled(True)
        self.sidebar.stop_btn.setEnabled(False)

    # =====================================================
    # ---------- Data handling ----------
    # =====================================================
    def _on_chunk(self, data: np.ndarray):
        self._buffer.extend(data)
        mean = float(np.mean(data))
        rms = float(np.sqrt(np.mean(np.square(data))))
        self.plot_view.mean_lbl.setText(f"Mean: {mean:+.5f}")
        self.plot_view.rms_lbl.setText(f"RMS: {rms:+.5f}")

        now = time.monotonic()
        if not hasattr(self, "_feed_frames"):
            self._feed_frames = 0
            self._last_feed_t = now
        self._feed_frames += 1
        if now - self._last_feed_t >= 1.0:
            fps = self._feed_frames / (now - self._last_feed_t)
            self.plot_view.fps_lbl.setText(f"Feed: {fps:.1f} Hz")
            self._feed_frames = 0
            self._last_feed_t = now

    @QtCore.pyqtSlot(str)
    def _on_status(self, msg: str):
        if msg == "connecting":
            self.sidebar.status_lbl.setText("Connecting…")
            self.status_led.set_color(Color.WARNING)
        elif msg == "running":
            self.sidebar.status_lbl.setText("Connected")
            self.status_led.set_color(Color.RUNNING)
        elif msg.startswith("error:"):
            self.sidebar.status_lbl.setText(msg)
            self.status_led.set_color(Color.ERROR)

    # =====================================================
    # ---------- Render + utils ----------
    # =====================================================
    def _render_frame(self):
        arr = self._buffer.np()
        if arr.size:
            self.plot_view.curve.setData(arr[-WINDOW_SAMPLES:])
        self._render_frames += 1
        now = time.monotonic()
        if now - self._last_render_t >= 1.0:
            rfps = self._render_frames / (now - self._last_render_t)
            self.app_refresh_lbl.setText(f"Refresh: {rfps:.1f} Hz")
            self._render_frames = 0
            self._last_render_t = now

    def _set_controls_enabled(self, enabled: bool):
        widgets = [
            self.sidebar.serial_btn,
            self.sidebar.tcp_btn,
            self.sidebar.port_edit,
            self.sidebar.baud_edit,
            self.sidebar.host_edit,
            self.sidebar.tcpport_edit,
            self.sidebar.start_btn,
            self.sidebar.stop_btn,
        ]
        if hasattr(self.sidebar, "test_btn"):
            widgets.insert(0, self.sidebar.test_btn)
        for w in widgets:
            w.setEnabled(enabled)

    def closeEvent(self, event):
        if self._worker:
            self._worker.stop()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        event.accept()
