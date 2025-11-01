import numpy as np


class RollingBuffer:
    """Efficient fixed-length rolling buffer for float32 samples."""

    def __init__(self, maxlen: int):
        self._n = maxlen
        self._buf = np.zeros(maxlen, dtype=np.float32)

    def extend(self, x: np.ndarray):
        x = np.asarray(x, dtype=np.float32)
        n = len(x)
        if n >= self._n:
            self._buf[:] = x[-self._n :]
        else:
            self._buf[:-n] = self._buf[n:]
            self._buf[-n:] = x

    def np(self) -> np.ndarray:
        return self._buf
