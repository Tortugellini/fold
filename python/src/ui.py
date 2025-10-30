from __future__ import annotations

import time
import asyncio
import threading
from dataclasses import dataclass
from typing import Optional, Callable

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

from utils.buffer import RollingBuffer
from datasources.test_tone import TestTone
from datasources.serial_pcm16 import SerialPCM16LE
from datasources.tcp_pcm16 import TCPPCM16LE


# --------------------------- Configuration ---------------------------

@dataclass(frozen=True)
class Config:
    sample_rate: int = 8_000
    chunk: int = 256
    rolling_seconds: int = 5
    gui_fps: int = 30        # UI redraw rate (Hz)

CFG = Config()
WINDOW_SAMPLES = CFG.sample_rate * CFG.rolling_seconds


# ---------------------- Data source factory (DI) ---------------------

class DataSourceFactory:
    """Creates concrete data sources without leaking UI concerns into them."""
    def __init__(self,
                 default_serial_port: str = "COM5",
                 default_baud: int = 115200,
                 default_host: str = "192.168.4.1",
                 default_tcp_port: int = 1234,
                 sample_rate: int = CFG.sample_rate) -> None:
        self.default_serial_port = default_serial_port
        self.default_baud = default_baud
        self.default_host = default_host
        self.default_tcp_port = default_tcp_port
        self.sample_rate = sample_rate

    def make(self,
             mode: str,
             port: Optional[str],
             baud: Optional[int],
             host: Optional[str],
             tcp_port: Optional[int]):
        if mode == "Serial":
            return SerialPCM16LE(
                port or self.default_serial_port,
                int(baud or self.default_baud),
                self.sample_rate,
            )
        if mode == "TCP":
            return TCPPCM16LE(
                host or self.default_host,
                int(tcp_port or self.default_tcp_port),
                self.sample_rate,
            )
        return TestTone(self.sample_rate)


# --------------------------- Worker thread ---------------------------

class StreamWorker(QtCore.QThread):
    """
    Background worker that owns a persistent asyncio loop.
    Emits numpy float32 chunks into the GUI thread via signals.
    """
    chunk_ready = QtCore.pyqtSignal(object)   # np.ndarray
    status_changed = QtCore.pyqtSignal(str)   # 'connecting' | 'connected' | 'stopped' | 'error:...'

    def __init__(self, source, chunk_size: int, stop_flag: threading.Event, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._source = source
        self._chunk_size = chunk_size
        self._stop_flag = stop_flag

    def run(self) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        try:
            self.status_changed.emit("connecting")
            await self._source.start()
            self.status_changed.emit("connected")

            # Tight loop; cooperative yield keeps the loop responsive.
            while not self._stop_flag.is_set():
                data = await self._source.read_chunk(self._chunk_size)
                arr = np.asarray(data, dtype=np.float32)
                self.chunk_ready.emit(arr)
                await asyncio.sleep(0)  # cooperative yield
        except Exception as e:
            self.status_changed.emit(f"error:{e}")
        finally:
            try:
                await self._source.stop()
            except Exception:
                pass
            self.status_changed.emit("stopped")


# ------------------------------ Main UI -----------------------------

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Audio Monitor")
        self.resize(1024, 600)

        # State (owned by the window; no globals)
        self._buffer = RollingBuffer(WINDOW_SAMPLES)
        self._factory = DataSourceFactory(sample_rate=CFG.sample_rate)
        self._worker: Optional[StreamWorker] = None
        self._stop_flag = threading.Event()
        self._frames = 0
        self._last_fps_stamp = time.monotonic()

        # UI
        self._build_ui()

        # Rendering timer — decoupled from input rate
        self._render_timer = QtCore.QTimer(self)
        self._render_timer.timeout.connect(self._render_frame)
        self._render_timer.start(int(1000 / CFG.gui_fps))

    # -------------------------- UI Construction --------------------------

    def _build_ui(self) -> None:
        pg.setConfigOption("background", "k")
        pg.setConfigOption("foreground", "w")

        container = QtWidgets.QWidget(self)
        self.setCentralWidget(container)
        layout = QtWidgets.QVBoxLayout(container)

        # Controls row
        controls = QtWidgets.QHBoxLayout()
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(["Test", "Serial", "TCP"])
        self.mode.activated.connect(self._on_mode_activated)

        self.port_edit = QtWidgets.QLineEdit()
        self.port_edit.setPlaceholderText("COM5 or /dev/ttyUSB0")
        self.baud_edit = QtWidgets.QLineEdit()
        self.baud_edit.setPlaceholderText("115200")

        self.host_edit = QtWidgets.QLineEdit()
        self.host_edit.setPlaceholderText("192.168.4.1")
        self.tcpport_edit = QtWidgets.QLineEdit()
        self.tcpport_edit.setPlaceholderText("1234")

        self.start_btn = QtWidgets.QPushButton("Start")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.status_lbl = QtWidgets.QLabel("Idle")

        # assemble controls
        controls.addWidget(QtWidgets.QLabel("Mode:"))
        controls.addWidget(self.mode)
        controls.addSpacing(12)
        controls.addWidget(QtWidgets.QLabel("Port:"))
        controls.addWidget(self.port_edit)
        controls.addWidget(QtWidgets.QLabel("Baud:"))
        controls.addWidget(self.baud_edit)
        controls.addSpacing(12)
        controls.addWidget(QtWidgets.QLabel("Host:"))
        controls.addWidget(self.host_edit)
        controls.addWidget(QtWidgets.QLabel("Port:"))
        controls.addWidget(self.tcpport_edit)
        controls.addStretch(1)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        controls.addSpacing(12)
        controls.addWidget(self.status_lbl)

        layout.addLayout(controls)

        # Plot
        self.plot = pg.PlotWidget()
        self.plot.setYRange(-1.1, 1.1)
        self.plot.setLabel("left", "Amplitude")
        self.plot.setLabel("bottom", "Samples")
        self.curve = self.plot.plot(pen=pg.mkPen("#00e676", width=2))
        layout.addWidget(self.plot)

        # Metrics row
        metrics = QtWidgets.QHBoxLayout()
        self.mean_lbl = QtWidgets.QLabel("Mean: ---")
        self.rms_lbl = QtWidgets.QLabel("RMS: ---")
        self.fps_lbl = QtWidgets.QLabel("Feed: --- Hz")
        metrics.addWidget(self.mean_lbl)
        metrics.addSpacing(24)
        metrics.addWidget(self.rms_lbl)
        metrics.addSpacing(24)
        metrics.addWidget(self.fps_lbl)
        metrics.addStretch(1)
        layout.addLayout(metrics)

        # Wire up buttons
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)

        # initial control visibility
        self._apply_mode_visibility(self.mode.currentText())

    # ---------------------------- UI Behavior ----------------------------

    def _on_mode_activated(self, idx: int) -> None:
        """Triggered when the user picks an item from the dropdown."""
        # Remember the selected mode but don't touch layout yet
        selected_mode = self.mode.itemText(idx)
        # Close popup immediately to avoid dangling menus
        self.mode.hidePopup()
        # Schedule the layout change after Qt has repainted
        QtCore.QTimer.singleShot(50, lambda: self._update_mode(selected_mode))

    def _update_mode(self, mode: str) -> None:
        """Actually apply layout changes once the combo interaction is finished."""
        self._apply_mode_visibility(mode)
        self.mode.setCurrentText(mode)

    def _apply_mode_visibility(self, mode: str) -> None:
        serial_on = (mode == "Serial")
        tcp_on = (mode == "TCP")

        for w in (self.port_edit, self.baud_edit):
            w.setVisible(serial_on)
            w.setEnabled(serial_on)

        for w in (self.host_edit, self.tcpport_edit):
            w.setVisible(tcp_on)
            w.setEnabled(tcp_on)

    # -------------------------- Lifecycle control ------------------------

    def _on_start(self) -> None:
        if self._worker and self._worker.isRunning():
            return  # already running

        # prevent mode edits while running (avoids accidental rebuilds)
        self._set_controls_enabled(False, include_mode=True)

        self._stop_flag.clear()
        source = self._factory.make(
            self.mode.currentText(),
            port=self.port_edit.text().strip() or None,
            baud=self._safe_int(self.baud_edit.text()),
            host=self.host_edit.text().strip() or None,
            tcp_port=self._safe_int(self.tcpport_edit.text()),
        )

        self._buffer = RollingBuffer(WINDOW_SAMPLES)
        self._frames = 0
        self._last_fps_stamp = time.monotonic()

        self._worker = StreamWorker(source, CFG.chunk, self._stop_flag, parent=self)
        self._worker.setObjectName("StreamWorker")
        # QueuedConnection ensures thread-safe delivery to the GUI thread
        self._worker.chunk_ready.connect(self._on_chunk, QtCore.Qt.ConnectionType.QueuedConnection)
        self._worker.status_changed.connect(self._on_status, QtCore.Qt.ConnectionType.QueuedConnection)
        self._worker.start()
        self.status_lbl.setText("Starting...")

    def _on_stop(self) -> None:
        self._stop_worker()
        self._set_controls_enabled(True, include_mode=True)
        self.status_lbl.setText("Stopped")

    def closeEvent(self, event) -> None:
        self._stop_worker()
        super().closeEvent(event)

    def _stop_worker(self) -> None:
        if self._worker and self._worker.isRunning():
            self._stop_flag.set()
            self._worker.wait(1500)
        self._worker = None

    def _set_controls_enabled(self, enabled: bool, *, include_mode: bool) -> None:
        self.port_edit.setEnabled(enabled)
        self.baud_edit.setEnabled(enabled)
        self.host_edit.setEnabled(enabled)
        self.tcpport_edit.setEnabled(enabled)
        self.start_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(True)  # allow stop anytime
        if include_mode:
            self.mode.setEnabled(enabled)

    # ----------------------------- Slots ---------------------------------

    @QtCore.pyqtSlot(object)
    def _on_chunk(self, data: np.ndarray) -> None:
        """Fast, bounded work: extend buffer and update metrics counters."""
        self._buffer.extend(data)
        # Cheap per-chunk metrics on incoming data (not full window)
        mean = float(np.mean(data))
        rms = float(np.sqrt(np.mean(data ** 2)))
        self.mean_lbl.setText(f"Mean: {mean:+.4f}")
        self.rms_lbl.setText(f"RMS: {rms:+.4f}")

        self._frames += 1
        now = time.monotonic()
        if now - self._last_fps_stamp >= 1.0:
            fps = self._frames / (now - self._last_fps_stamp)
            self.fps_lbl.setText(f"Feed: {fps:.1f} Hz")
            self._frames = 0
            self._last_fps_stamp = now

    @QtCore.pyqtSlot(str)
    def _on_status(self, s: str) -> None:
        # Keep status text short; avoid spamming the UI thread
        if s == "connecting":
            self.status_lbl.setText("Connecting…")
        elif s == "connected":
            self.status_lbl.setText("Connected")
        elif s.startswith("error:"):
            self.status_lbl.setText("Error")
            # Optional: log s somewhere
        elif s == "stopped":
            self.status_lbl.setText("Stopped")
            self._set_controls_enabled(True, include_mode=True)

    # --------------------------- Rendering -------------------------------

    def _render_frame(self) -> None:
        """Decoupled, steady GUI refresh."""
        arr = self._buffer.np()
        if arr.size == 0:
            return
        tail = arr[-WINDOW_SAMPLES:]
        # x is implicit; pyqtgraph handles indices
        self.curve.setData(tail)

    # ---------------------------- Utilities ------------------------------

    @staticmethod
    def _safe_int(s: str | None) -> Optional[int]:
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            return None
