import os
import zlib

from pathlib import Path
from dataclasses import dataclass
from tempfile import TemporaryFile

from typing import Literal, Generator

from dk64_lib.data_types import TextureData, TextData, CutsceneData, GeometryData
from dk64_lib.file_io import get_bytes, get_char, get_long, get_short


class Rom:
    REGIONS_AND_POINTER_TABLE_OFFSETS = {
        0x45: ("us", 0x101C50),
        0x50: ("pal", 0x1038D0),
        0x4A: ("jp", 0x1039C0),
    }

    def __init__(self, rom_path: str):
        """Class representation of a DK64 ROM

        Args:
            rom_path (str): Path to ROM file
        """
        self.rom_path = Path(rom_path).resolve()

        # Copy ROM data to a temporary file
        with open(rom_path, "rb") as rom_file:
            self.rom_fh = TemporaryFile()
            self.rom_fh.write(rom_file.read())
            self.rom_fh.seek(0)

        endianness = int.from_bytes(self.rom_fh.read(1), "big")
        assert (
            endianness == 0x80
        ), "ROM is little endian. Convert to big endian and re-run"

    def __del__(self):
        """Closes the file on deletion"""
        self.rom_fh.close()

    @property
    def release_or_kiosk(self) -> Literal["release", "kiosk"]:
        """Read the release/kiosk flag to check game version

        Returns:
            Literal['release', 'kiosk']: release or kiosk
        """
        release_or_kiosk = get_char(self.rom_fh, 0x3D, keep_last_pos=True)
        if release_or_kiosk == 0x50:
            return "kiosk"
        return "release"

    @property
    def region(self) -> Literal["us", "pal", "jp", "kiosk"]:
        """Read the region flag and return which region the ROM is

        Raises:
            KeyError: Raised when an unidentified region is found

        Returns:
            Literal['us', 'pal', 'jp', 'kiosk']: Game's region
        """
        region = get_char(self.rom_fh, 0x3E, keep_last_pos=True)
        if self.release_or_kiosk == "kiosk":
            return "kiosk"
        try:
            return self.REGIONS_AND_POINTER_TABLE_OFFSETS[region][0]
        except KeyError:
            raise KeyError(f"This region ({region}) is invalid")

    @property
    def pointer_table_offset(self) -> Literal[0x101C50, 0x1038D0, 0x1039C0, 0x1A7C20]:
        """Gets the pointer table offset for the ROM

        Returns:
            Literal[0x101C50, 0x1038D0, 0x1039C0, 0x1A7C20]: Pointer offset
        """
        region = get_char(self.rom_fh, 0x3E, keep_last_pos=True)
        if self.release_or_kiosk == "kiosk":
            return 0x1A7C20
        return self.REGIONS_AND_POINTER_TABLE_OFFSETS[region][1]

    @property
    def text_tables(self) -> list[TextData]:
        """Returns a list of all text data

        Returns:
            list[TextData]: The game's text data
        """
        return [text_data for text_data in self.generate_text_data()]

    @property
    def geometry_tables(self):
        return [geometry_data for geometry_data in self.generate_geometry_data()]

    def _extract_table_data(self, start: int, size: int) -> Generator[dict, None, None]:
        """An internal generator for extracting the data that a table points to

        Args:
            start (int): Starting offset of the table
            size (int): Size of the table

        Yields:
            Generator[dict, None, None]: The data the table entry points to
        """
        for entry in range(size):
            entry_start = self.pointer_table_offset + (
                get_long(self.rom_fh, start + (entry * 4)) & 0x7FFFFFFF
            )
            entry_finish = self.pointer_table_offset + (
                get_long(
                    self.rom_fh,
                )
                & 0x7FFFFFFF
            )
            entry_size = entry_finish - entry_start
            if not entry_size:
                continue
            indic = get_short(self.rom_fh, entry_start)
            table_data = get_bytes(self.rom_fh, entry_size, entry_start)
            if indic == 0x1F8B:
                table_data = zlib.decompress(table_data, (15 + 32))
            if not table_data:
                continue
            yield dict(
                _raw_data=table_data,
                offset=entry_start,
                size=entry_size,
                was_compressed=True if indic == 0x1F8B else False,
            )

    def generate_rom_table_data(self, tables: list[int]) -> Generator[dict, None, None]:
        """A generator that iterates through the various table data in the ROM

        Args:
            tables (list[int]): Which tables to iterate through

        Yields:
            Generator[dict, None, None]: The table data in bytes
        """
        for table_offset in tables:
            if self.release_or_kiosk == "kiosk":
                table_offset -= 1
            table_size = get_long(
                self.rom_fh, self.pointer_table_offset + (32 * 4) + (table_offset * 4)
            )
            table_start = self.pointer_table_offset + get_long(
                self.rom_fh, self.pointer_table_offset + (table_offset * 4)
            )
            for data in self._extract_table_data(table_start, table_size):
                yield data

    def generate_texture_data(self) -> Generator[TextureData, None, None]:
        """A generator for fetching the texture data

        Yields:
            Generator[TextureData, None, None]: A single piece of texture data
        """
        for table_data in self.generate_rom_table_data([7, 14, 25]):
            yield TextureData(**table_data)

    def generate_text_data(self) -> Generator[TextData, None, None]:
        """A generator for fetching the text data

        Yields:
            Generator[TextData, None, None]: A single piece of texture data
        """
        for table_data in self.generate_rom_table_data([12]):
            yield TextData(**table_data, _release_or_kiosk=self.release_or_kiosk)

    def generate_cutscene_data(self) -> Generator[CutsceneData, None, None]:
        """A generator for fetching the cutscene data

        Yields:
            Generator[CutsceneData, None, None]: A single piece of texture data
        """
        for table_data in self.generate_rom_table_data([8]):
            yield CutsceneData(**table_data)

    def generate_geometry_data(self) -> Generator[GeometryData, None, None]:
        """A generator for fetching the cutscene data

        Yields:
            Generator[GeometryData, None, None]: A single piece of texture data
        """
        for table_data in self.generate_rom_table_data([1]):
            yield GeometryData(**table_data)
