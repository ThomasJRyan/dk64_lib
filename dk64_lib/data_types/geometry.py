# TODO: Comment everything
# TODO: Clean up code
import pathlib

from io import FileIO
from dataclasses import dataclass
from tempfile import TemporaryFile

from dk64_lib.data_types.base import BaseData
from dk64_lib.f3dex2.commands import DL_COMMANDS
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
        dl_start, vert_start = self._dl_start, self._vert_start
        with TemporaryFile() as data_file:
            data_file.write(self._raw_data)
            data_file.seek(dl_start)
            raw_data, raw_vert_data = b"", b""
            
            while data_file.tell() != self._vert_start:
                command_bytes = get_bytes(data_file, 8)
                
                if (cls := DL_COMMANDS.get(command_bytes[:1])):
                    cmd = cls(command_bytes)
                else:
                    continue
                
                raw_data += command_bytes
                
                if cmd.opcode == b"\x01":
                    raw_vert_data += get_bytes(data_file, cmd.vertex_count * 16, vert_start, keep_last_pos=True)
                    vert_start += cmd.vertex_count * 16
                
                if cmd.opcode == b"\xDF":
                    ret_list.append(DisplayList(raw_data=raw_data, raw_vertex_data=raw_vert_data, offset=dl_start))
                    raw_data, raw_vert_data = b"", b""
                    dl_start = data_file.tell()
        return ret_list

    @property
    def triangles(self):
        ret_list = list()
        for dl in self.display_lists:
            ret_list.extend(dl.triangles)
        return ret_list

    def _parse_data(self, fh: FileIO):
        self._dl_start = get_long(fh, 0x34)
        self._vert_start = get_long(fh, 0x38)
        self._dl_size = self._vert_start - self._dl_start

    def save_to_obj(self, filename: str, folderpath: str = "."):
        """Save geometry data to obj format

        Args:
            filename (str): Name of obj file
            folderpath (str, optional): Folder path to save obj to. Defaults to ".".
        """
        tri_offset = 1
        filepath = pathlib.Path(folderpath, filename)
        
        with open(filepath, "w") as obj_file:
            for dl in self.display_lists:
                # if len(dl.verticies) != len(dl.triangles):
                #     continue
                for verticies, triangles in zip(dl.verticies, dl.triangles):
                    for vertex in verticies:
                        obj_line = f"v {vertex.x} {vertex.y} {vertex.z}\n"
                        obj_file.write(obj_line)
                        
                    for tri in triangles:
                        obj_line = f"f {tri.v1 + tri_offset} {tri.v2 + tri_offset} {tri.v3 + tri_offset}\n"
                        obj_file.write(obj_line)
                        
                    tri_offset += len(verticies)