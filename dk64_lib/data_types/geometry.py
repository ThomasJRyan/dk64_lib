# TODO: Comment everything
# TODO: Clean up code
import pathlib

from io import FileIO
from typing import Union
from dataclasses import dataclass
from tempfile import TemporaryFile

from dk64_lib.components.vertex import Vertex
from dk64_lib.data_types.base import BaseData
from dk64_lib.f3dex2.commands import DL_COMMANDS, G_TRI1, G_VTX
from dk64_lib.f3dex2.display_list import DisplayList
from dk64_lib.file_io import get_bytes, get_char, get_long, get_short


@dataclass(repr=False)
class GeometryData(BaseData):
    data_type: str = "Geometry"

    def __post_init__(self):
        # Use a temporary file to allow us to seek throughout it
        with TemporaryFile() as data_file:
            data_file.write(self._raw_data)
            data_file.seek(0)
            self._parse_data(data_file)

    @property
    def display_lists(self) -> list[DisplayList]:
        ret_list = list()
        dl_start = self._dl_start
        with TemporaryFile() as data_file:
            data_file.write(self._raw_data)
            data_file.seek(dl_start)
            raw_data = b""
            while data_file.tell() != self._vert_start:
                command = get_bytes(data_file, 8)
                raw_data += command
                if command == b"\xDF\x00\x00\x00\x00\x00\x00\x00":
                    ret_list.append(DisplayList(raw_data=raw_data, start=dl_start))
                    raw_data = b""
                    dl_start = data_file.tell()
        return ret_list

    @property
    def triangles(self):
        ret_list = list()
        for dl in self.display_lists:
            ret_list.extend(dl.triangles)
        return ret_list

    def _parse_verticies(self, vertex_data: bytes, vertex_buffer: G_VTX):
        ret_list = list()
        vert_start = 0
        vert_end = vert_start + 16
        for _ in range(vertex_buffer.vertex_count):
            vertex_bytes = vertex_data[vert_start:vert_end]
            vertex = Vertex(vertex_bytes)
            ret_list.append(vertex)
            vert_start = vert_end
            vert_end = vert_start + 16
        return ret_list

    def _parse_data(self, fh: FileIO):
        self._dl_start = get_long(fh, 0x34)
        self._vert_start = get_long(fh, 0x38)
        self._dl_size = self._vert_start - self._dl_start

    def save_to_obj(self, filename: str, folderpath: str = "."):
        filepath = pathlib.Path(folderpath, filename)
        face_offset = 1
        vert_start = self._vert_start
        with open(filepath, "w") as obj_file:
            for display_list in self.display_lists:
                for v_buff_num, vertex_buffer in enumerate(display_list.vertex_buffers):
                    buffer_size = vertex_buffer.vertex_count * 16
                    for vertex in self._parse_verticies(
                        self._raw_data[vert_start : vert_start + buffer_size],
                        vertex_buffer,
                    ):
                        obj_line = f"v {vertex.x} {vertex.y} {vertex.z}\n"
                        obj_file.write(obj_line)
                    vert_start += buffer_size
                    for tri in display_list.triangles[v_buff_num]:
                        obj_file.write(
                            f"f {tri.v1 + face_offset} {tri.v2 + face_offset} {tri.v3 + face_offset}\n"
                        )
                    face_offset += vertex_buffer.vertex_count
