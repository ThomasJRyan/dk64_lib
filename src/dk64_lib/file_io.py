from io import FileIO


def get_bytes(
    fh: FileIO, byte_count: int, position: int | None = None, keep_last_pos=False
):
    """Reads bytes and returns them

    Args:
        fh (FileIO): File IO retrieve bytes from
        byte_count (int): Number of bytes to read
        position (int | None, optional): Position to seek to and read. Defaults to None.
        keep_last_pos (bool, optional): Whether or not to return to the last position before seeking. Defaults to False.

    Returns:
        bytes: Read bytes
    """
    if keep_last_pos:
        last_pos = fh.tell()
    if isinstance(position, int):
        fh.seek(position)
    _bytes = fh.read(byte_count)
    if keep_last_pos:
        fh.seek(last_pos)
    return _bytes


def get_char(fh: FileIO, position: int | None = None, keep_last_pos=False) -> int:
    """Reads one byte and returns it as an integer

    Args:
        fh (FileIO): File IO retrieve bytes from
        position (int | None, optional): Position to seek to and read. Defaults to None.
        keep_last_pos (bool, optional): Whether or not to return to the last position before seeking. Defaults to False.

    Returns:
        int: Bytes as integer
    """
    return int.from_bytes(get_bytes(fh, 1, position, keep_last_pos), "big")


def get_short(fh: FileIO, position: int | None = None, keep_last_pos=False) -> int:
    """Reads two bytes and returns them as an integer

    Args:
        fh (FileIO): File IO retrieve bytes from
        position (int | None, optional): Position to seek to and read. Defaults to None.
        keep_last_pos (bool, optional): Whether or not to return to the last position before seeking. Defaults to False.

    Returns:
        int: Bytes as integer
    """
    return int.from_bytes(get_bytes(fh, 2, position, keep_last_pos), "big")


def get_long(fh: FileIO, position: int | None = None, keep_last_pos=False) -> int:
    """Reads four bytes and returns them as an integer

    Args:
        fh (FileIO): File IO retrieve bytes from
        position (int | None, optional): Position to seek to and read. Defaults to None.
        keep_last_pos (bool, optional): Whether or not to return to the last position before seeking. Defaults to False.

    Returns:
        int: Bytes as integer
    """
    return int.from_bytes(get_bytes(fh, 4, position, keep_last_pos), "big")
