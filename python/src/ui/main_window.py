import time
import numpy as np
import pyqtgraph as pg

from loguru import logger
from PyQt6 import QtWidgets, QtCore

from constants import WINDOW_SAMPLES, Color, Mode
from stream.buffer import RollingBuffer
from stream.stream_handler import StreamHandler
from stream.audio_player import AudioPlayer
from widgets.status_led import StatusLED
from ui.sidepanel import Sidepanel
from ui.plot_view import PlotView

# Logger created here because this is where all the action takes place.
logger.add("/home/maste/esp/fold/python/src/fold.log")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dev_mode: bool = False):
        """
        Initializes the main window of the application with or without developer fidelity
        depending on whether the flag '--dev' is passed.
        ---
        Parameters:
            dev_mode, bool: The flag mentioned above. Passed as a CLI argument to Python.
        """

        super().__init__()
        self.dev_mode = dev_mode
        self.setWindowTitle(f"fold {' [DEV MODE]' if dev_mode else ''}")
        self.resize(1200, 650)

        # Data + threads
        self._buffer = RollingBuffer(WINDOW_SAMPLES)
        self._stream_worker: StreamHandler | None = None
        self._audio_player: AudioPlayer | None = None
        self._stream_thread: QtCore.QThread | None = None
        self._audio_thread: QtCore.QThread | None = None

        # UI metrics
        self._feed_frames = 0
        self._render_frames = 0
        self._last_render_t = time.monotonic()

        # Build UI
        self._build_ui()

        # Render loop
        self._render_timer = QtCore.QTimer(self)
        self._render_timer.timeout.connect(self._render_frame)
        self._render_timer.start(33)

    def _build_ui(self):
        """
        Builds all the UI functionality of the application.
        """

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
        self.sidepanel = Sidepanel(self.dev_mode)
        self.sidepanel.setMinimumWidth(
            120
        )  # Starts the sidepanel at a full URI length.
        self.sidepanel.mode_group.idClicked.connect(self._on_mode_button)
        self.sidepanel.listen_btn.clicked.connect(self._on_listen)
        self.sidepanel.stop_btn.clicked.connect(self._on_stop)
        self.sidepanel.host_edit.hide()
        self.sidepanel.udpport_edit.hide()
        splitter.addWidget(self.sidepanel)

        # Plot view (right)
        self.plot_view = PlotView()
        splitter.addWidget(self.plot_view)
        splitter.setSizes([self.sidepanel.minimumWidth() + 1, 1000])

    def _on_mode_button(self, idx: int):
        """
        Determines what buttons are shown on the UI.
        """

        modes = [Mode.TEST, Mode.UDP] if self.dev_mode else [Mode.UDP]
        self._apply_mode_visibility(modes[idx])

    def _apply_mode_visibility(self, mode: str):
        self._current_mode_cached = mode
        logger.info(f"Switcing to {mode}")
        is_udp = mode == Mode.UDP
        for w in (self.sidepanel.host_edit, self.sidepanel.udpport_edit):
            w.setVisible(is_udp)
            w.setEnabled(is_udp)

    def _current_mode(self) -> str:
        if (
            self.dev_mode
            # and getattr(self.sidepanel, "test_btn", None)
            and self.sidepanel.test_btn.isChecked()
        ):
            # logger.info("Testing things out.")
            return Mode.TEST
        if self.sidepanel.udp_btn.isChecked():
            # logger.info("Listening to the stream.")
            return Mode.UDP

    def _on_listen(self):
        """
        Determines what happens when 'Listen' is pushed.
        """

        if self._stream_thread and self._stream_thread.isRunning():
            return

        logger.info("Listening to the stream.")

        self._stream_thread = QtCore.QThread()
        self._audio_thread = QtCore.QThread()

        self._stream_worker = StreamHandler(
            self._current_mode(),
            {
                "host": self.sidepanel.host_edit.text(),
                "udpport": self.sidepanel.udpport_edit.text(),
            },
        )
        self._stream_worker.moveToThread(self._stream_thread)
        self._stream_thread.started.connect(self._stream_worker.process)
        self._stream_worker.chunk_ready.connect(self._on_chunk)
        self._stream_worker.status_changed.connect(self._on_status)
        self._stream_worker.finished.connect(self._on_worker_finished)
        self._stream_thread.finished.connect(self._stream_thread.deleteLater)

        self._audio_player = AudioPlayer(self._current_mode(), self._buffer)
        self._audio_player.moveToThread(self._audio_thread)
        self._audio_thread.started.connect(self._audio_player.play_sounds)

        self._set_controls_enabled(False)
        self.sidepanel.stop_btn.setEnabled(True)
        self.sidepanel.listen_btn.setEnabled(False)
        self.sidepanel.status_lbl.setText("Starting…")
        self.status_led.set_color(Color.WARNING)
        self._stream_thread.start()

    def _on_stop(self):
        """
        Determines what happens when 'Stop' is pushed.
        """

        if not self._stream_worker:
            return
        self._stream_worker.stop()
        self.sidepanel.stop_btn.setEnabled(False)
        self.sidepanel.status_lbl.setText("Stopping…")
        logger.info("Stopping the stream.")
        self.status_led.set_color(Color.WARNING)

    def _on_worker_finished(self):
        if self._stream_thread and self._stream_thread.isRunning():
            self._stream_thread.quit()
            self._stream_thread.wait()
        self._stream_worker = None
        self._stream_thread = None
        self.sidepanel.status_lbl.setText("Stopped")
        self.status_led.set_color(Color.IDLE)
        self._set_controls_enabled(True)
        self.sidepanel.listen_btn.setEnabled(True)
        self.sidepanel.stop_btn.setEnabled(False)

    def _on_chunk(self, data: np.ndarray):
        self._buffer.extend(data)
        mean = float(np.mean(data))
        rms = float(np.sqrt(np.mean(np.square(data))))
        self.plot_view.mean_lbl.setText(f"Mean: {mean:+.5f}")
        self.plot_view.rms_lbl.setText(f"RMS: {rms:+.5f}")

        now = time.monotonic()
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
            self.sidepanel.status_lbl.setText("Connecting…")
            self.status_led.set_color(Color.WARNING)
        elif msg == "running":
            self.sidepanel.status_lbl.setText("Connected")
            self.status_led.set_color(Color.RUNNING)
        elif msg.startswith("error:"):
            self.sidepanel.status_lbl.setText(msg)
            self.status_led.set_color(Color.ERROR)

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
            self.sidepanel.udp_btn,
            self.sidepanel.host_edit,
            self.sidepanel.udpport_edit,
            self.sidepanel.listen_btn,
            self.sidepanel.stop_btn,
        ]
        if self.dev_mode:
            widgets.insert(0, self.sidepanel.test_btn)
        for w in widgets:
            w.setEnabled(enabled)

    def closeEvent(self, event):
        logger.info("Closing the app.")
        if self._stream_worker:
            self._stream_worker.stop()
        if self._stream_thread and self._stream_thread.isRunning():
            self._stream_thread.quit()
            self._stream_thread.wait()
        event.accept()
