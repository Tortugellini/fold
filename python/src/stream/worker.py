import time
import socket
import threading
import numpy as np
from io import BytesIO
from PyQt6 import QtCore

from constants import SAMPLE_RATE, CHUNK, READ_TIMEOUT_S, MAX_BACKLOG_BYTES


class StreamWorker(QtCore.QObject):
    """Background stream handler for Test, Serial, or TCP sources."""

    chunk_ready = QtCore.pyqtSignal(object)
    status_changed = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, mode: str, params: dict[str, str]):
        super().__init__()
        self._stop = threading.Event()
        self.mode = mode
        self.params = params

    def stop(self):
        self._stop.set()

    @QtCore.pyqtSlot()
    def process(self):
        try:
            self.status_changed.emit("connecting")
            time.sleep(0.03)
            if self.mode == "Test":
                self._run_test()
            elif self.mode == "Serial":
                self._run_serial()
            elif self.mode == "TCP":
                self._run_tcp()
            else:
                self.status_changed.emit("error:unknown mode")
        finally:
            self.status_changed.emit("stopped")
            self.finished.emit()

    # ---------- helpers ----------
    def _emit_chunk(self, arr: np.ndarray):
        if arr.size:
            self.chunk_ready.emit(arr.astype(np.float32, copy=False))

    def _decode_bytes_to_samples(self, b: bytes) -> np.ndarray:
        """Try PCM16 → fallback text floats."""
        if len(b) >= 2 and len(b) % 2 == 0:
            try:
                return np.frombuffer(b, dtype="<i2").astype(np.float32) / 32768.0
            except Exception:
                pass
        try:
            txt = b.decode("utf-8", errors="ignore").replace(",", " ")
            parts = txt.split()
            if parts:
                return np.array([float(p) for p in parts], dtype=np.float32)
        except Exception:
            pass
        return np.empty(0, dtype=np.float32)

    # ---------- modes ----------
    def _run_test(self):
        self.status_changed.emit("running")
        phase = 0.0
        freq = 440.0
        w = 2 * np.pi * freq / SAMPLE_RATE
        while not self._stop.is_set():
            idx = np.arange(CHUNK, dtype=np.float32)
            chunk = np.sin(phase + w * idx)
            phase = (phase + w * CHUNK) % (2 * np.pi)
            self._emit_chunk(chunk)
            QtCore.QThread.msleep(int(CHUNK / SAMPLE_RATE * 1000 * 0.75))

    def _run_serial(self):
        try:
            import serial
        except ImportError:
            self.status_changed.emit("error:pyserial not installed")
            return

        port = self.params.get("port", "").strip()
        baud = int(self.params.get("baud") or "115200")
        if not port:
            self.status_changed.emit("error:missing serial port")
            return

        try:
            ser = serial.Serial(port, baudrate=baud, timeout=READ_TIMEOUT_S)
        except Exception as e:
            self.status_changed.emit(f"error:{type(e).__name__}: {e}")
            return

        self.status_changed.emit("running")
        buf = BytesIO()
        try:
            while not self._stop.is_set():
                data = ser.read(4096)
                if data:
                    if buf.tell() > MAX_BACKLOG_BYTES:
                        buf.seek(0)
                        buf.truncate(0)
                    buf.write(data)
                    while buf.tell() >= CHUNK * 2:
                        raw = buf.getvalue()
                        frame, remainder = raw[: CHUNK * 2], raw[CHUNK * 2 :]
                        buf.seek(0)
                        buf.truncate(0)
                        buf.write(remainder)
                        self._emit_chunk(self._decode_bytes_to_samples(frame))
                QtCore.QThread.msleep(int(READ_TIMEOUT_S * 1000))
        finally:
            ser.close()

    def _run_tcp(self):
        host = self.params.get("host", "").strip()
        port_str = self.params.get("tcpport", "").strip()
        if not host or not port_str:
            self.status_changed.emit("error:missing tcp host/port")
            return
        try:
            port = int(port_str)
        except ValueError:
            self.status_changed.emit("error:tcp port must be int")
            return

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(2.0)
            s.connect((host, port))
            s.settimeout(READ_TIMEOUT_S)
            self.status_changed.emit("running")

            buf = BytesIO()
            while not self._stop.is_set():
                try:
                    data = s.recv(4096)
                except socket.timeout:
                    data = b""
                if not data:
                    QtCore.QThread.msleep(int(READ_TIMEOUT_S * 1000))
                    continue
                if buf.tell() > MAX_BACKLOG_BYTES:
                    buf.seek(0)
                    buf.truncate(0)
                buf.write(data)
                while buf.tell() >= CHUNK * 2:
                    raw = buf.getvalue()
                    frame, remainder = raw[: CHUNK * 2], raw[CHUNK * 2 :]
                    buf.seek(0)
                    buf.truncate(0)
                    buf.write(remainder)
                    self._emit_chunk(self._decode_bytes_to_samples(frame))
        except Exception as e:
            self.status_changed.emit(f"error:{type(e).__name__}: {e}")
        finally:
            s.close()
