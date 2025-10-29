import numpy as np
from collections import deque
from typing import Deque

class RollingBuffer:
    """Fixed-length circular buffer for waveform plotting."""
    def __init__(self, capacity: int):
        self.buf: Deque[float] = deque(np.zeros(capacity, dtype=np.float32), maxlen=capacity)

    def extend(self, x: np.ndarray):
        self.buf.extend(x.tolist())

    def np(self) -> np.ndarray:
        return np.fromiter(self.buf, dtype=np.float32, count=len(self.buf))
