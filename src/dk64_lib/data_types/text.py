from io import FileIO
from typing import Union
from dataclasses import dataclass
from tempfile import TemporaryFile

from dk64_lib.data_types.base import BaseData
from dk64_lib.constants import RELEASE_SPRITES, KIOSK_SPRITES
from dk64_lib.file_io import get_bytes, get_char, get_long, get_short


@dataclass
class _Sprite:
    position: int
    data: bytes
    sprite: str
    data_type: str = "sprite"

    def __repr__(self):
        return self.sprite


@dataclass
class _Text:
    start: int
    size: int
    data_type: str = "normal"
    text: str | None = None

    def __repr__(self):
        return self.text


@dataclass
class _TextLineFragment:
    block_start: str
    section2count: int
    section3count: int
    offset: int
    text: list[Union["_Text", "_Sprite"]]


@dataclass
class _TextLine:
    arr: bytes
    sentence_fragments: list["_TextLineFragment"]
    section1count: int
    section2count: int
    section3count: int
    data_start: str

    @property
    def text(self):
        segments = list()
        for fragment in self.sentence_fragments:
            segments.append(" ".join([str(text) for text in fragment.text]))
        return " ".join(segments)

    def __repr__(self) -> str:
        return f"_TextLine({self.data_start=}, {self.text=})"


@dataclass(kw_only=True)
class TextData(BaseData):
    _release_or_kiosk: str
    data_type: str = "Text"

    _data: list[Union["_Text", "_Sprite"]] | None = None

    def __post_init__(self):
        """Run byte processing on raw_data after init"""
        self._SPRITE_LIST = (
            RELEASE_SPRITES if self._release_or_kiosk == "release" else KIOSK_SPRITES
        )
        self._data = list()

        # Use a temporary file to allow us to seek throughout it
        with TemporaryFile() as data_file:
            data_file.write(self._raw_data)
            data_file.seek(0)
            self._parse_data(data_file)

    def __repr__(self):
        return f"TextDataTable({self.offset=}, {self.size=}, # of lines={len(self.text_lines)})"

    def _generate_text(
        self,
        fh: FileIO,
        sec3ct: int,
        data_start: int,
        block_start: int,
        offset: int,
        bit_shift: int,
        is_text: bool,
    ) -> list[Union["_Text", "_Sprite"]]:
        """Object method - Generates a list of Texts and Sprites, used to form the various sentences in the game

        Returns:
            list[Union['TextData._Text', 'TextData._Sprite']]: The text and sprite information pulled from the game
        """
        ret_list = list()
        for pos in range(sec3ct):
            data_block = block_start + 2 + offset + (bit_shift * pos) - 1
            if is_text:
                text_start = get_short(fh, data_start + data_block + 3)
                text_size = get_short(fh, data_start + data_block + 5)
                data_object = _Text(start=text_start, size=text_size)
            else:
                sprite_pos = get_short(fh, data_start + data_block)
                sprite_data = get_long(fh, data_start + data_block)
                sprite_index = (sprite_data >> 8) & 0xFF
                sprite = self._SPRITE_LIST.get(
                    str(sprite_index), f"unk{hex(sprite_index)}"
                )
                data_object = _Sprite(
                    position=sprite_pos, data=sprite_data, sprite=sprite
                )
            ret_list.append(data_object)
        return ret_list

    def _generate_blocks(
        self, fh: FileIO, section_count: int, data_start: int
    ) -> tuple[int, list["_TextLineFragment"]]:
        """Object method - Generates a list of Blocks, each containing a line of text and sprites

        Returns:
            tuple[int, list['TextData.Block']]: The text block start along with the
                                                list of blocks containing said data
        """
        ret_list = list()
        block_start = 1
        for _ in range(section_count):
            sec2ct = get_char(fh, data_start + block_start)
            offset = 4 if (sec2ct & 4) != 0 else 0
            sec3ct = get_char(fh, data_start + block_start + offset + 1)

            bit_shift, is_text = 8, True
            if (sec2ct & 1) == 0 and (sec2ct & 2) != 0:
                bit_shift, is_text = 4, False

            text_blocks = self._generate_text(
                fh, sec3ct, data_start, block_start, offset, bit_shift, is_text
            )

            ret_list.append(
                _TextLineFragment(
                    block_start=hex(block_start + data_start),
                    section2count=sec2ct,
                    section3count=sec3ct,
                    offset=offset,
                    text=text_blocks,
                )
            )
            block_start = block_start + 2 + offset + (bit_shift * sec3ct) + 4

        return block_start, ret_list

    def _generate_block_data(self, fh: FileIO) -> tuple[int, list["_TextLine"]]:
        """Object method - Generates a list of BlockData objects containing the various blocks of text

        Returns:
            tuple[int, list['TextData.BlockData']]: The text data start along with the
                                                    list of blocks containing said data
        """
        ret_list = list()

        data_count = get_char(fh)
        data_start = 0x01

        # For each block of data, get the necessary information and create a BlockData object for it
        for _ in range(data_count):
            fh.seek(data_start)

            sec_1_count = get_char(fh)

            # ! As far as I can tell, these two variables are totally unused and can likely be removed
            # ! from here and every dataclass that interacts with them
            sec_2_count = get_char(fh)
            sec_3_count = get_char(fh)

            fh.seek(data_start + 5)
            block_start, block_list = self._generate_blocks(fh, sec_1_count, data_start)

            fh.seek(data_start)
            info = (
                b""
                if block_start < data_start
                else get_bytes(fh, block_start - data_start)
            )

            ret_list.append(
                _TextLine(
                    arr=info,
                    sentence_fragments=block_list,
                    section1count=sec_1_count,
                    section2count=sec_2_count,
                    section3count=sec_3_count,
                    data_start=hex(data_start),
                )
            )

            # Start off at the end of our current section for the next iteration
            data_start += block_start

        return data_start, ret_list

    def _parse_text(
        self, fh: FileIO, data_start: int, text_list: list[Union["_Text", "_Sprite"]]
    ):
        """Object method - Parse the texts

        Args:
            fh (FileIO): The temporary file handler
            data_start (int): Where the text data begins
            block_data_list (list[TextData.BlockData]): List of texts and sprites
        """
        for item in text_list:
            if isinstance(item, _Text):
                item_offset = item.start + data_start + 2
                item.text = get_bytes(fh, item.size, item_offset).decode()
            self._data.append(item)

    def _parse_blocks(
        self, fh: FileIO, data_start: int, block_list: list["_TextLineFragment"]
    ):
        """Object method - Parse the blocks

        Args:
            fh (FileIO): The temporary file handler
            data_start (int): Where the text data begins
            block_data_list (list[TextData.BlockData]): List of blocks
        """
        for block in block_list:
            self._parse_text(fh, data_start, block.text)

    def _parse_block_data(
        self, fh: FileIO, data_start: int, block_data_list: list["_TextLine"]
    ):
        """Object method - Parse the block data

        Args:
            fh (FileIO): The temporary file handler
            data_start (int): Where the text data begins
            block_data_list (list[TextData.BlockData]): List of block datas
        """
        for block_data in block_data_list:
            self._parse_blocks(fh, data_start, block_data.sentence_fragments)

    def _parse_data(self, fh: FileIO):
        """Object method - Runs the methods to generate and parse the block data

        Args:
            fh (FileIO): The temporary file handler
        """
        data_start, block_data_list = self._generate_block_data(fh)
        self._parse_block_data(fh, data_start, block_data_list)
        self.text_lines = block_data_list
