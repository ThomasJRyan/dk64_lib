from io import FileIO
from typing import Union
from dataclasses import dataclass
from tempfile import TemporaryFile
from abc import ABC, abstractmethod

from dk64_lib.tables.base import BaseDataTable
from dk64_lib import RELEASE_SPRITES, KIOSK_SPRITES
from dk64_lib.file_io import get_bytes, get_char, get_long, get_short


@dataclass(repr=False)
class TextureDataTable(BaseDataTable):
    data_type: str = "Texture"

    def __post_init__(self):
        self._parse_data()

    def _parse_data(self):
        return super()._parse_data()
