import numpy as np


class RollingBuffer:
    """Efficient fixed-length rolling buffer for float32 samples."""

    def __init__(self, maxlen: int):
        self._len = maxlen
        self._buf = np.zeros(maxlen, dtype=np.float32)

    def extend(self, incoming_data: np.ndarray):
        incoming_data = np.asarray(incoming_data, dtype=np.float32)
        n = len(incoming_data)
        if n >= self._len:
            self._buf[:] = incoming_data[-self._len :]
        else:
            self._buf[:-n] = self._buf[n:]
            self._buf[-n:] = incoming_data

    def np(self) -> np.ndarray:
        return self._buf
