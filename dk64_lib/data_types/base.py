from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass(kw_only=True)
class BaseData(ABC):
    _raw_data: bytes
    offset: int
    size: int
    was_compressed: bool

    data_type: str = None

    def __len__(self):
        return self.size

    def __repr__(self):
        return f"{self.data_type=}, {self.offset=}, {self.size=}"

    @abstractmethod
    def __post_init__(self):
        ...

    def _parse_data(self):
        ...
