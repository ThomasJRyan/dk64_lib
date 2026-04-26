class BinaryReader:
    """Read big-endian values from an immutable byte buffer."""

    def __init__(self, data: bytes | bytearray | memoryview):
        self._data = memoryview(data)

    def __len__(self) -> int:
        return len(self._data)

    def read_at(self, offset: int, size: int) -> bytes:
        self._validate_range(offset, size)
        return self._data[offset : offset + size].tobytes()

    def slice(self, offset: int, size: int) -> memoryview:
        self._validate_range(offset, size)
        return self._data[offset : offset + size]

    def read_u8(self, offset: int) -> int:
        return self.read_at(offset, 1)[0]

    def read_u16(self, offset: int) -> int:
        return int.from_bytes(self.read_at(offset, 2), "big")

    def read_i16(self, offset: int) -> int:
        return int.from_bytes(self.read_at(offset, 2), "big", signed=True)

    def read_u32(self, offset: int) -> int:
        return int.from_bytes(self.read_at(offset, 4), "big")

    def _validate_range(self, offset: int, size: int) -> None:
        if offset < 0:
            raise ValueError("offset must be non-negative")
        if size < 0:
            raise ValueError("size must be non-negative")
        if offset + size > len(self._data):
            raise ValueError("read exceeds buffer length")
