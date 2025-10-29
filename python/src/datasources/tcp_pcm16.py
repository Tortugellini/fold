import asyncio, numpy as np
from .base import DataSource

class TCPPCM16LE(DataSource):
    """Reads 16-bit PCM from TCP socket."""
    def __init__(self, host="192.168.4.1", port=1234, fs=8000):
        self.host = host
        self.port = port
        self.fs = fs
        self.reader = None
        self.writer = None

    async def start(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

    async def stop(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

    async def read_chunk(self, n: int) -> np.ndarray:
        need = 2 * n
        buf = await self.reader.readexactly(need)
        data = np.frombuffer(buf, dtype='<i2')
        return (data / 32768.0).astype(np.float32)
