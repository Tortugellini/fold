import numpy as np
from .base import DataSource

class TestTone(DataSource):
    """Generates fake audio for testing."""
    def __init__(self, fs=8000):
        self.fs = fs
        self.phase = 0.0

    async def start(self): pass
    async def stop(self): pass

    async def read_chunk(self, n: int) -> np.ndarray:
        t = (np.arange(n) + self.phase) / self.fs
        sig = (
            0.6*np.sin(2*np.pi*440*t)
            + 0.4*np.sin(2*np.pi*880*t + 0.5)
            + 0.05*np.random.randn(n)
        )
        self.phase += n
        return sig.astype(np.float32)
