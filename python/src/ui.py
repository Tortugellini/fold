import time
import numpy as np
from PyQt6 import QtWidgets, QtCore
import pyqtgraph as pg

from constants import SAMPLE_RATE, CHUNK, ROLLING_SEC, Color, Mode
from stream.buffer import RollingBuffer
from stream.worker import StreamWorker
from widgets.status_led import StatusLED

WINDOW_SAMPLES = SAMPLE_RATE * ROLLING_SEC


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dev_mode: bool = False):
        super().__init__()
        self.dev_mode = dev_mode
        self.setWindowTitle(f"fold {' [DEV MODE]' if dev_mode else ''}")
        self.resize(1200, 650)

        self._buffer = RollingBuffer(WINDOW_SAMPLES)
        self._worker: StreamWorker | None = None
        self._thread: QtCore.QThread | None = None

        self._render_frames = 0
        self._last_render_t = time.monotonic()

        self._build_ui()

        self._render_timer = QtCore.QTimer(self)
        self._render_timer.timeout.connect(self._render_frame)
        self._render_timer.start(33)

    # ---------- UI ----------
    def _build_ui(self):
        pg.setConfigOption("background", "k")
        pg.setConfigOption("foreground", "w")

        container = QtWidgets.QWidget()
        self.setCentralWidget(container)
        vlayout = QtWidgets.QVBoxLayout(container)
        vlayout.setContentsMargins(8, 8, 8, 8)
        vlayout.setSpacing(4)

        # Top row
        top_row = QtWidgets.QHBoxLayout()
        self.status_led = StatusLED(14)
        self.status_led.set_color(Color.IDLE)
        self.app_refresh_lbl = QtWidgets.QLabel("Refresh: --- Hz")
        self.app_refresh_lbl.setStyleSheet(
            "color:black; font-size:12px; font-weight:bold;"
        )
        top_row.addWidget(self.status_led)
        top_row.addSpacing(6)
        top_row.addWidget(self.app_refresh_lbl)
        top_row.addStretch(1)
        vlayout.addLayout(top_row)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        vlayout.addWidget(splitter, stretch=1)

        # Sidebar
        sidebar = QtWidgets.QFrame()
        sidebar.setMinimumWidth(200)
        sidebar.setStyleSheet(
            "QFrame{background-color:#1e1e1e;border-right:1px solid #333;}"
            "QLabel{color:#ddd;}"
        )
        side = QtWidgets.QVBoxLayout(sidebar)
        side.setContentsMargins(12, 12, 12, 12)
        side.setSpacing(10)

        self.mode_group = QtWidgets.QButtonGroup(self)
        button_style = (
            "QPushButton{border:1px solid #555;border-radius:4px;"
            "padding:6px 0;background-color:#333;color:white;}"
            "QPushButton:checked{background-color:#00e676;color:black;}"
        )
        buttons = []
        if self.dev_mode:
            self.test_btn = QtWidgets.QPushButton("Test")
            buttons.append(self.test_btn)
        self.serial_btn = QtWidgets.QPushButton("Serial")
        self.tcp_btn = QtWidgets.QPushButton("TCP")
        buttons.extend([self.serial_btn, self.tcp_btn])
        for i, b in enumerate(buttons):
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setStyleSheet(button_style)
            self.mode_group.addButton(b, i)
            side.addWidget(b)
        buttons[0].setChecked(True)
        self.mode_group.idClicked.connect(self._on_mode_button)

        side.addSpacing(8)
        side.addWidget(QtWidgets.QLabel("Connection"))
        self.port_edit = QtWidgets.QLineEdit(placeholderText="COM5 / ttyUSB0")
        self.baud_edit = QtWidgets.QLineEdit(placeholderText="115200")
        self.host_edit = QtWidgets.QLineEdit(placeholderText="192.168.4.1")
        self.tcpport_edit = QtWidgets.QLineEdit(placeholderText="1234")
        for w in (self.port_edit, self.baud_edit, self.host_edit, self.tcpport_edit):
            w.setStyleSheet(
                "background:#222;color:#eee;border:1px solid #444;padding:4px;"
            )
            side.addWidget(w)

        side.addSpacing(8)
        self.start_btn = QtWidgets.QPushButton("Start")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        for b in (self.start_btn, self.stop_btn):
            b.setStyleSheet("padding:6px;background-color:#555;color:white;")
            side.addWidget(b)
        side.addStretch(1)
        self.status_lbl = QtWidgets.QLabel("Idle")
        self.status_lbl.setStyleSheet("color:#aaa;")
        side.addWidget(self.status_lbl)

        splitter.addWidget(sidebar)

        # Right panel (plot + metrics)
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.plot = pg.PlotWidget()
        self.plot.setYRange(-1.1, 1.1)
        self.plot.setLabel("left", "Amplitude")
        self.plot.setLabel("bottom", "Samples")
        self.curve = self.plot.plot(pen=pg.mkPen(Color.RUNNING, width=2))
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        right_layout.addWidget(self.plot, stretch=1)

        metrics = QtWidgets.QHBoxLayout()
        mono = "font-family:'Courier New', monospace;"
        self.mean_lbl = QtWidgets.QLabel("Mean: ---")
        self.rms_lbl = QtWidgets.QLabel("RMS: ---")
        self.fps_lbl = QtWidgets.QLabel("Feed: --- Hz")
        for lbl in (self.mean_lbl, self.rms_lbl, self.fps_lbl):
            lbl.setStyleSheet(f"color:black;font-size:13px;{mono}")
            metrics.addWidget(lbl)
            metrics.addSpacing(20)
        metrics.addStretch(1)
        right_layout.addLayout(metrics)
        splitter.addWidget(right_panel)

        splitter.setSizes([sidebar.minimumWidth() + 1, 1000])

        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)
        self._apply_mode_visibility(Mode.TEST if self.dev_mode else Mode.SERIAL)

    def _render_frame(self):
        arr = self._buffer.np()
        if arr.size:
            self.curve.setData(arr[-WINDOW_SAMPLES:])
        self._render_frames += 1
        now = time.monotonic()
        if now - self._last_render_t >= 1.0:
            rfps = self._render_frames / (now - self._last_render_t)
            self.app_refresh_lbl.setText(f"Refresh: {rfps:.1f} Hz")
            self._render_frames = 0
            self._last_render_t = now

    def _set_controls_enabled(self, enabled: bool):
        widgets = [
            self.serial_btn,
            self.tcp_btn,
            self.port_edit,
            self.baud_edit,
            self.host_edit,
            self.tcpport_edit,
            self.start_btn,
            self.stop_btn,
        ]
        if hasattr(self, "test_btn"):
            widgets.insert(0, self.test_btn)
        for w in widgets:
            w.setEnabled(enabled)

    # ---------- Mode handling ----------
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
        for w in (self.port_edit, self.baud_edit):
            w.setVisible(is_serial)
            w.setEnabled(is_serial)
        for w in (self.host_edit, self.tcpport_edit):
            w.setVisible(is_tcp)
            w.setEnabled(is_tcp)

    def _current_mode(self) -> str:
        if (
            self.dev_mode
            and getattr(self, "test_btn", None)
            and self.test_btn.isChecked()
        ):
            return Mode.TEST
        if self.serial_btn.isChecked():
            return Mode.SERIAL
        if self.tcp_btn.isChecked():
            return Mode.TCP
        return getattr(self, "_current_mode_cached", Mode.SERIAL)

    # ---------- Stream control ----------
    def _on_start(self):
        if self._thread and self._thread.isRunning():
            return

        mode = self._current_mode()
        params = {
            "port": self.port_edit.text(),
            "baud": self.baud_edit.text(),
            "host": self.host_edit.text(),
            "tcpport": self.tcpport_edit.text(),
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
        self.stop_btn.setEnabled(True)
        self.start_btn.setEnabled(False)
        self.status_lbl.setText("Starting…")
        self.status_led.set_color(Color.WARNING)
        self._thread.start()

    def _on_stop(self):
        if not self._worker:
            return
        self._worker.stop()
        self.stop_btn.setEnabled(False)
        self.status_lbl.setText("Stopping…")
        self.status_led.set_color(Color.WARNING)

    def _on_worker_finished(self):
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        self._worker = None
        self._thread = None
        self.status_lbl.setText("Stopped")
        self.status_led.set_color(Color.IDLE)
        self._set_controls_enabled(True)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    # ---------- Data handling ----------
    def _on_chunk(self, data: np.ndarray):
        self._buffer.extend(data)
        mean = float(np.mean(data))
        rms = float(np.sqrt(np.mean(np.square(data))))
        self.mean_lbl.setText(f"Mean: {mean:+.5f}")
        self.rms_lbl.setText(f"RMS: {rms:+.5f}")
        now = time.monotonic()
        if not hasattr(self, "_feed_frames"):
            self._feed_frames = 0
            self._last_feed_t = now
        self._feed_frames += 1
        if now - self._last_feed_t >= 1.0:
            fps = self._feed_frames / (now - self._last_feed_t)
            self.fps_lbl.setText(f"Feed: {fps:.1f} Hz")
            self._feed_frames = 0
            self._last_feed_t = now

    @QtCore.pyqtSlot(str)
    def _on_status(self, msg: str):
        if msg == "connecting":
            self.status_lbl.setText("Connecting…")
            self.status_led.set_color(Color.WARNING)
        elif msg == "running":
            self.status_lbl.setText("Connected")
            self.status_led.set_color(Color.RUNNING)
        elif msg.startswith("error:"):
            self.status_lbl.setText(msg)
            self.status_led.set
