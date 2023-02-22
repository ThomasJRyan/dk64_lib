from abc import ABC, abstractmethod

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from dk64_lib.rom import Rom

class BaseData(ABC):
    def __init__(self, raw_data: bytes, offset: int, size: int, was_compressed: bool, rom: 'Rom', data_type: str = None, *args, **kwargs):
        self.raw_data = raw_data
        self.offset = offset
        self.size = size
        self.was_compressed = was_compressed
        self.rom = rom
        self.data_type = data_type
        self.__post_init__(*args, **kwargs)

    def __len__(self):
        return self.size

    def __repr__(self):
        return f"{self.data_type=}, {self.offset=}, {self.size=}"

    @abstractmethod
    def __post_init__(self, *args, **kwargs):
        ...
