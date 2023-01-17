
# TODO: Comment everything
# TODO: Clean up code
import pathlib

from io import FileIO
from typing import Union
from dataclasses import dataclass
from tempfile import TemporaryFile

from dk64_lib.data_types.base import BaseData
from dk64_lib.f3dex2.commands import DL_COMMANDS, G_TRI1, G_VTX
from dk64_lib.file_io import get_bytes, get_char, get_long, get_short


@dataclass
class _Vertex():
    x: int
    y: int
    z: int
    unk: int
    texture_cord_u: int
    texture_cord_v: int
    xr: int
    yg: int
    zb: int
    alpha: int
    
@dataclass
class _DisplayList():
    _raw_data: bytes
    start: int
    
    def __post_init__(self):
        ...
    
    def __repr__(self):
        return f'DisplayList({self.start=}, {self.size=}, {self.num_commands=})'
    
    @property
    def size(self):
        return len(self._raw_data)
    
    @property
    def num_commands(self):
        return int(self.size / 8)
    
    @property
    def vertex_buffers(self):
        return [cmd for cmd in self.commands if isinstance(cmd, G_VTX)]
    
    @property
    def triangles(self):
        ret_list = list()
        tri_list = list()
        for cmd in self.commands:
            if cmd.opcode == b'\x01' and tri_list:
                ret_list.append(tri_list)
                tri_list = list()
                continue
            if cmd.opcode == b'\x05':
                tri_list.append(cmd)
                continue
        else:
            ret_list.append(tri_list)
        return ret_list
    
    @property
    def commands(self):
        ret_list = list()
        for command_pos in range(self.num_commands):
            command = self._raw_data[command_pos * 8 : command_pos * 8 + 8]
            if (func := DL_COMMANDS.get(command[:1])):
                ret_list.append(func(command))
        return ret_list

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
    def display_lists(self) -> list[_DisplayList]:
        ret_list = list()
        dl_start = self._dl_start
        with TemporaryFile() as data_file:
            data_file.write(self._raw_data)
            data_file.seek(dl_start)
            raw_data = b''
            while data_file.tell() != self._vert_start:
                command = get_bytes(data_file, 8)
                raw_data += command
                if command == b'\xDF\x00\x00\x00\x00\x00\x00\x00':
                    ret_list.append(_DisplayList(_raw_data = raw_data, start=dl_start))
                    raw_data = b''
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
            vertex = _Vertex(
                x = int.from_bytes(vertex_bytes[0:2], "big"),
                y = int.from_bytes(vertex_bytes[2:4], "big"),
                z = int.from_bytes(vertex_bytes[4:6], "big"),
                unk = int.from_bytes(vertex_bytes[6:8], "big"),
                texture_cord_u = int.from_bytes(vertex_bytes[8:10], "big"),
                texture_cord_v = int.from_bytes(vertex_bytes[10:12], "big"),
                xr = vertex_bytes[12],
                yg = vertex_bytes[13],
                zb = vertex_bytes[14],
                alpha = vertex_bytes[15],
            )
            ret_list.append(vertex)
            vert_start = vert_end
            vert_end = vert_start + 16
        return ret_list
        
    def _parse_data(self, fh: FileIO):
        self._dl_start = get_long(fh, 0x34)
        self._vert_start = get_long(fh, 0x38)
        self._dl_size = self._vert_start - self._dl_start
    
    def save_to_obj(self, filename: str, folderpath: str = '.'):
        filepath = pathlib.Path(folderpath, filename)
        face_offset = 1
        vert_start = self._vert_start
        with open(filepath, 'w') as obj_file:
            for display_list in self.display_lists:
                for v_buff_num, vertex_buffer in enumerate(display_list.vertex_buffers):
                    buffer_size = vertex_buffer.vertex_count * 16
                    for vertex in self._parse_verticies(self._raw_data[vert_start:vert_start + buffer_size], vertex_buffer):
                        obj_line = f'v {vertex.x} {vertex.y} {vertex.z}\n'
                        obj_file.write(obj_line)
                    vert_start += buffer_size
                    for tri in display_list.triangles[v_buff_num]:
                        obj_file.write(f'f {tri.v1 + face_offset} {tri.v2 + face_offset} {tri.v3 + face_offset}\n')
                    face_offset += vertex_buffer.vertex_count