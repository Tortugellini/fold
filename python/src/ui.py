from __future__ import annotations

import time, asyncio, threading, numpy as np
from PyQt6 import QtCore, QtWidgets, QtGui
import pyqtgraph as pg

from utils.buffer import RollingBuffer
from datasources.test_tone import TestTone
from datasources.serial_pcm16 import SerialPCM16LE
from datasources.tcp_pcm16 import TCPPCM16LE


SAMPLE_RATE = 8000
CHUNK = 256
ROLLING_SEC = 5
WINDOW_SAMPLES = SAMPLE_RATE * ROLLING_SEC


# ---------------- Worker Thread ----------------
class StreamWorker(QtCore.QThread):
    chunk_ready = QtCore.pyqtSignal(object)
    status_changed = QtCore.pyqtSignal(str)

    def __init__(
        self, source, chunk_size: int, stop_flag: threading.Event, parent=None
    ):
        super().__init__(parent)
        self._source, self._chunk_size, self._stop_flag = source, chunk_size, stop_flag

    def run(self):
        asyncio.run(self._main())

    async def _main(self):
        try:
            self.status_changed.emit("connecting")
            await self._source.start()
            self.status_changed.emit("connected")
            while not self._stop_flag.is_set():
                data = await self._source.read_chunk(self._chunk_size)
                self.chunk_ready.emit(np.asarray(data, np.float32))
                await asyncio.sleep(0)
        except Exception as e:
            self.status_changed.emit(f"error:{e}")
        finally:
            try:
                await self._source.stop()
            except Exception:
                pass
            self.status_changed.emit("stopped")


# ---------------- Factory ----------------
class DataSourceFactory:
    def __init__(self, sample_rate=SAMPLE_RATE):
        self.sample_rate = sample_rate

    def make(self, mode, port, baud, host, tcp_port):
        if mode == "Serial":
            return SerialPCM16LE(port or "COM5", baud or 115200, self.sample_rate)
        if mode == "TCP":
            return TCPPCM16LE(host or "192.168.4.1", tcp_port or 1234, self.sample_rate)
        return TestTone(self.sample_rate)


class StatusLED(QtWidgets.QLabel):
    """A small colored LED indicator drawn with QPainter."""

    def __init__(self, diameter=12, parent=None):
        super().__init__(parent)
        self._diameter = diameter
        self._color = "#444"  # default gray (idle)
        self._update_pixmap()

    def set_color(self, color: str):
        """Change LED color (hex string or color name)."""
        self._color = color
        self._update_pixmap()

    def _update_pixmap(self):
        pixmap = QtGui.QPixmap(self._diameter, self._diameter)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setBrush(QtGui.QColor(self._color))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self._diameter, self._diameter)
        painter.end()
        self.setPixmap(pixmap)


# ---------------- Main Window ----------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Monitor")
        self.resize(1200, 650)

        self._factory = DataSourceFactory()
        self._buffer = RollingBuffer(WINDOW_SAMPLES)
        self._stop_flag, self._worker = threading.Event(), None
        self._frames, self._last_fps_t = 0, time.monotonic()
        self._render_frames, self._last_render_t = 0, time.monotonic()

        self._build_ui()

        self._render_timer = QtCore.QTimer(self)
        self._render_timer.timeout.connect(self._render_frame)
        self._render_timer.start(33)  # 30 Hz refresh

    # ---------------- UI ----------------
    def _build_ui(self):
        pg.setConfigOption("background", "k")
        pg.setConfigOption("foreground", "w")

        container = QtWidgets.QWidget()
        self.setCentralWidget(container)
        vlayout = QtWidgets.QVBoxLayout(container)
        vlayout.setContentsMargins(8, 8, 8, 8)
        vlayout.setSpacing(4)

        # ---- Top row: LED + Refresh label ----
        top_row = QtWidgets.QHBoxLayout()
        self.status_led = StatusLED(14)
        self.status_led.set_color("#444")  # idle gray
        self.app_refresh_lbl = QtWidgets.QLabel("Refresh: --- Hz")
        self.app_refresh_lbl.setStyleSheet(
            "color: black; font-size: 12px; font-weight: bold;"
        )

        top_row.addWidget(self.status_led)
        top_row.addSpacing(6)
        top_row.addWidget(self.app_refresh_lbl)
        top_row.addStretch(1)
        vlayout.addLayout(top_row)

        # ---- QSplitter for sidebar + main panel ----
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        vlayout.addWidget(splitter, stretch=1)

        # ----- Left sidebar -----
        sidebar = QtWidgets.QFrame()
        sidebar.setMinimumWidth(200)
        sidebar.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        sidebar.setStyleSheet(
            """
            QFrame {
                background-color: #1e1e1e;
                border-right: 1px solid #333;
            }
            QLabel { color: #ddd; }
        """
        )
        side = QtWidgets.QVBoxLayout(sidebar)
        side.setContentsMargins(12, 12, 12, 12)
        side.setSpacing(10)

        # Mode buttons
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.test_btn, self.serial_btn, self.tcp_btn = (
            QtWidgets.QPushButton("Test"),
            QtWidgets.QPushButton("Serial"),
            QtWidgets.QPushButton("TCP"),
        )
        for i, b in enumerate([self.test_btn, self.serial_btn, self.tcp_btn]):
            b.setCheckable(True)
            b.setAutoExclusive(True)
            self.mode_group.addButton(b, i)
        self.test_btn.setChecked(True)
        self.mode_group.idClicked.connect(self._on_mode_button)

        button_style = """
            QPushButton {
                border: 1px solid #555; border-radius: 4px;
                padding: 6px 0; background-color: #333; color: white;
            }
            QPushButton:checked { background-color: #00e676; color: black; }
        """
        for b in [self.test_btn, self.serial_btn, self.tcp_btn]:
            b.setStyleSheet(button_style)
            side.addWidget(b)

        side.addSpacing(8)
        side.addWidget(QtWidgets.QLabel("Connection"))
        self.port_edit = QtWidgets.QLineEdit(placeholderText="COM5 / ttyUSB0")
        self.baud_edit = QtWidgets.QLineEdit(placeholderText="115200")
        self.host_edit = QtWidgets.QLineEdit(placeholderText="192.168.4.1")
        self.tcpport_edit = QtWidgets.QLineEdit(placeholderText="1234")
        for w in [self.port_edit, self.baud_edit, self.host_edit, self.tcpport_edit]:
            w.setStyleSheet(
                "background:#222; color:#eee; border:1px solid #444; padding:4px;"
            )
            side.addWidget(w)

        side.addSpacing(8)
        self.start_btn = QtWidgets.QPushButton("Start")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        for b in [self.start_btn, self.stop_btn]:
            b.setStyleSheet("padding:6px; background-color:#555; color:white;")
            side.addWidget(b)

        side.addStretch(1)
        self.status_lbl = QtWidgets.QLabel("Idle")
        self.status_lbl.setStyleSheet("color:#aaa;")
        side.addWidget(self.status_lbl)

        # Add sidebar to splitter
        splitter.addWidget(sidebar)

        # ----- Right: Plot + metrics -----
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.plot = pg.PlotWidget()
        self.plot.scene().sigMouseClicked.connect(self._on_plot_click)
        self.plot.setMouseEnabled(x=False, y=False)  # disable drag-panning
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.enableAutoRange("y", False)
        self.plot.setRange(xRange=[0, WINDOW_SAMPLES], yRange=[-1.1, 1.1])

        # Enable rectangular zoom with left mouse drag
        view_box = self.plot.getViewBox()
        view_box.setMouseMode(pg.ViewBox.RectMode)

        self.plot.setYRange(-1.1, 1.1)
        self.plot.setLabel("left", "Amplitude")
        self.plot.setLabel("bottom", "Samples")
        self.curve = self.plot.plot(pen=pg.mkPen("#00e676", width=2))
        right_layout.addWidget(self.plot, stretch=1)

        metrics = QtWidgets.QHBoxLayout()
        self.mean_lbl = QtWidgets.QLabel("Mean: ---")
        self.rms_lbl = QtWidgets.QLabel("RMS: ---")
        self.fps_lbl = QtWidgets.QLabel("Feed: --- Hz")
        for lbl in [self.mean_lbl, self.rms_lbl, self.fps_lbl]:
            lbl.setStyleSheet("color:black; font-size:13px;")
            metrics.addWidget(lbl)
            metrics.addSpacing(20)
        metrics.addStretch(1)
        right_layout.addLayout(metrics)

        splitter.addWidget(right_panel)

        # ---- Ratio + Limits ----
        splitter.setSizes(
            [sidebar.minimumWidth() + 1, 1000]
        )  # sidebar starts minimal but visible
        splitter.setCollapsible(0, True)  # allow collapse of sidebar
        splitter.setCollapsible(1, False)  # plot can't collapse
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.setMinimumSize(900, 500)

        # Wire events
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)
        self._apply_mode_visibility("Test")

    def _on_plot_click(self, event):
        """Double-click handler to reset plot view."""
        if event.double():
            self.plot.enableAutoRange("x", True)
            self.plot.enableAutoRange("y", True)
            self.plot.setRange(yRange=[-1.1, 1.1])

    def _on_mode_button(self, idx: int):
        """Handles mode toggle clicks."""
        modes = ["Test", "Serial", "TCP"]
        self._apply_mode_visibility(modes[idx])

    def _apply_mode_visibility(self, mode: str):
        """Show or hide connection fields depending on selected mode."""
        is_serial = mode == "Serial"
        is_tcp = mode == "TCP"

        for w in (self.port_edit, self.baud_edit):
            w.setVisible(is_serial)
            w.setEnabled(is_serial)

        for w in (self.host_edit, self.tcpport_edit):
            w.setVisible(is_tcp)
            w.setEnabled(is_tcp)

    def _on_start(self):
        """Starts data streaming."""
        if self._worker and self._worker.isRunning():
            return

        self._set_controls_enabled(False)
        self._stop_flag.clear()

        # Determine mode
        mode = "Test"
        if self.serial_btn.isChecked():
            mode = "Serial"
        elif self.tcp_btn.isChecked():
            mode = "TCP"

        src = self._factory.make(
            mode,
            self.port_edit.text().strip() or None,
            self._safe_int(self.baud_edit.text()),
            self.host_edit.text().strip() or None,
            self._safe_int(self.tcpport_edit.text()),
        )

        # Reset buffers and counters
        self._buffer = RollingBuffer(WINDOW_SAMPLES)
        self._frames = 0
        self._last_fps_t = time.monotonic()

        # Spawn worker thread
        self._worker = StreamWorker(src, CHUNK, self._stop_flag, parent=self)
        self._worker.chunk_ready.connect(
            self._on_chunk, QtCore.Qt.ConnectionType.QueuedConnection
        )
        self._worker.status_changed.connect(
            self._on_status, QtCore.Qt.ConnectionType.QueuedConnection
        )
        self._worker.start()
        self.status_lbl.setText("Starting…")

    def _on_stop(self):
        self._stop_worker()
        self._set_controls_enabled(True)
        self.status_lbl.setText("Stopped")

    def _stop_worker(self):
        if self._worker and self._worker.isRunning():
            self._stop_flag.set()
            self._worker.wait(1500)
        self._worker = None

    def closeEvent(self, e):
        self._stop_worker()
        super().closeEvent(e)

    # ---------------- Data/Render ----------------
    @QtCore.pyqtSlot(object)
    def _on_chunk(self, data: np.ndarray):
        self._buffer.extend(data)
        mean, rms = float(np.mean(data)), float(np.sqrt(np.mean(data**2)))
        self.mean_lbl.setText(f"Mean: {mean:+.5f}")
        self.rms_lbl.setText(f"RMS: {rms:+.5f}")
        monospace = "font-family: 'Courier New', monospace;"
        for lbl in [self.mean_lbl, self.rms_lbl, self.fps_lbl]:
            lbl.setStyleSheet(f"color:black; font-size:13px; {monospace}")

        self._frames += 1
        now = time.monotonic()
        if now - self._last_fps_t >= 1.0:
            fps = self._frames / (now - self._last_fps_t)
            self.fps_lbl.setText(f"Feed: {fps:.1f} Hz")
            self._frames, self._last_fps_t = 0, now

    @QtCore.pyqtSlot(str)
    def _on_status(self, msg: str):
        if msg == "connecting":
            self.status_lbl.setText("Connecting…")
            self.status_led.set_color("#ffcc00")  # yellow
        elif msg == "connected":
            self.status_lbl.setText("Connected")
            self.status_led.set_color("#00e676")  # green
        elif msg.startswith("error:"):
            self.status_lbl.setText("Error")
            self.status_led.set_color("#cc0000")  # red
        elif msg == "stopped":
            self.status_lbl.setText("Stopped")
            self.status_led.set_color("#444")  # gray (idle)
            self._set_controls_enabled(True)

    def _render_frame(self):
        arr = self._buffer.np()
        if arr.size:
            self.curve.setData(arr[-WINDOW_SAMPLES:])

        # Refresh rate calculation (UI frame rate)
        self._render_frames += 1
        now = time.monotonic()
        if now - self._last_render_t >= 1.0:
            render_fps = self._render_frames / (now - self._last_render_t)
            self.app_refresh_lbl.setText(f"Refresh: {render_fps:.1f} Hz")
            self._render_frames, self._last_render_t = 0, now

    # ---------------- Utils ----------------
    def _set_controls_enabled(self, en: bool):
        for w in [
            self.port_edit,
            self.baud_edit,
            self.host_edit,
            self.tcpport_edit,
            self.start_btn,
            self.test_btn,
            self.serial_btn,
            self.tcp_btn,
        ]:
            w.setEnabled(en)
        self.stop_btn.setEnabled(True)

    @staticmethod
    def _safe_int(s: str | None):
        try:
            return int(s) if s else None
        except ValueError:
            return None
