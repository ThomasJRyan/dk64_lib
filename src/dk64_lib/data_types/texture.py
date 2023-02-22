from io import FileIO
from typing import Union
from dataclasses import dataclass
from tempfile import TemporaryFile

from dk64_lib.data_types.base import BaseData
from dk64_lib.constants import RELEASE_SPRITES, KIOSK_SPRITES
from dk64_lib.file_io import get_bytes, get_char, get_long, get_short


class TextureData(BaseData):
    def __post_init__(self):
        self.data_type = "Texture"
