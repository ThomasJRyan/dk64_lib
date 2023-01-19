import pathlib

from dataclasses import dataclass
from tempfile import TemporaryFile

from dk64_lib.data_types.base import BaseData
from dk64_lib.f3dex2.commands import DL_COMMANDS
from dk64_lib.f3dex2.display_list import DisplayList
from dk64_lib.file_io import get_bytes, get_long


@dataclass(repr=False)
class GeometryData(BaseData):
    data_type: str = "Geometry"

    def __post_init__(self):
        # Use a temporary file to allow us to seek throughout it
        with TemporaryFile() as data_file:
            data_file.write(self._raw_data)
            data_file.seek(0)

            # Get the display list and vertex starts
            self._dl_start = get_long(data_file, 0x34)
            self._vert_start = get_long(data_file, 0x38)

    @property
    def display_lists(self) -> list[DisplayList]:
        """Generate and return a list of display lists inside of the geometry data

        Returns:
            list[DisplayList]: A list of display lists
        """
        ret_list = list()
        dl_start, vert_start = self._dl_start, self._vert_start

        # Write the raw data to a temporary file so we can seek and read as necessary
        with TemporaryFile() as data_file:
            data_file.write(self._raw_data)
            data_file.seek(dl_start)
            raw_data, raw_vert_data = b"", b""

            # While we haven't reached the vertex start point, read each 8 byte command
            while data_file.tell() != self._vert_start:
                command_bytes = get_bytes(data_file, 8)

                # * This if-statement likely isn't necessary (and could potentially be harmful)
                # * But for the time being it's effective to alleviate any errors that *might* come up
                # Get the F3DEX2 command class and intantiate it as an object
                if cls := DL_COMMANDS.get(command_bytes[:1]):
                    cmd = cls(command_bytes)
                else:
                    continue

                # Write the command bytes. This will become our DisplayList's _raw_data
                raw_data += command_bytes

                # If we encounter a G_VTX opcode, use it to obtain the associated vertex data
                # This will be stored in the DisplayList's _raw_vertex_data
                if cmd.opcode == b"\x01":
                    raw_vert_data += get_bytes(
                        data_file, cmd.vertex_count * 16, vert_start, keep_last_pos=True
                    )
                    vert_start += cmd.vertex_count * 16

                # Once we reach the end of the Display List, create the object and start fresh
                if cmd.opcode == b"\xDF":
                    ret_list.append(
                        DisplayList(
                            raw_data=raw_data,
                            raw_vertex_data=raw_vert_data,
                            offset=dl_start,
                        )
                    )
                    raw_data, raw_vert_data = b"", b""
                    dl_start = data_file.tell()

        return ret_list

    def save_to_obj(self, filename: str, folderpath: str = ".") -> None:
        """Save geometry data to obj format

        Args:
            filename (str): Name of obj file
            folderpath (str, optional): Folder path to save obj to. Defaults to ".".
        """
        tri_offset = 1
        filepath = pathlib.Path(folderpath, filename)

        with open(filepath, "w") as obj_file:
            for dl in self.display_lists:
                for verticies, triangles in zip(dl.verticies, dl.triangles):
                    # Write vertecies to file
                    for vertex in verticies:
                        obj_line = f"v {vertex.x} {vertex.y} {vertex.z}\n"
                        obj_file.write(obj_line)
                    obj_file.write("\n")

                    # Write triangles/faces to file
                    for tri in triangles:
                        obj_line = f"f {tri.v1 + tri_offset} {tri.v2 + tri_offset} {tri.v3 + tri_offset}\n"
                        obj_file.write(obj_line)
                    obj_file.write("\n")

                    # The triangle offset is used to globally identify the vertex due to
                    # Display Lists reading them with local positions
                    tri_offset += len(verticies)
