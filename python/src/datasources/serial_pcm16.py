import asyncio, contextlib
import numpy as np
import serial
from .base import DataSource

class SerialPCM16LE(DataSource):
    """Reads 16-bit PCM from serial."""
    def __init__(self, port="COM5", baud=115200, fs=8000):
        self.port = port
        self.baud = baud
        self.fs = fs
        self.ser = None

    async def start(self):
        self.ser = serial.Serial(self.port, self.baud, timeout=0)
        await asyncio.sleep(0.1)

    async def stop(self):
        with contextlib.suppress(Exception):
            if self.ser and self.ser.is_open:
                self.ser.close()
        self.ser = None

    async def read_chunk(self, n: int) -> np.ndarray:
        if not self.ser:
            return np.zeros(n, dtype=np.float32)
        need = 2*n
        buf = bytearray()
        while len(buf) < need:
            await asyncio.sleep(0)
            data = self.ser.read(need - len(buf))
            if data:
                buf.extend(data)
        int16 = np.frombuffer(buf, dtype='<i2')
        return (int16 / 32768.0).astype(np.float32)
