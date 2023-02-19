from io import FileIO

from dk64_lib.components.vertex import Vertex
from dk64_lib.components.triangle import Triangle

from dk64_lib.f3dex2 import commands
from dk64_lib.f3dex2.commands import DL_COMMANDS, DL_Command

from tempfile import TemporaryFile

from dk64_lib.file_io import get_bytes, get_long, get_char


class DisplayListExpansion:
    def __init__(self, raw_data: bytes):
        self._raw_data = raw_data
        self._parse_data()

    def _parse_data(self):
        with TemporaryFile() as data_file:
            data_file.write(self._raw_data)
            data_file.seek(0)

            self.unknown_1 = get_long(data_file)
            self.unknown_2 = get_long(data_file)
            self.display_list_offset = get_long(data_file)
            self.unknown_4 = get_long(data_file)


class DisplayListChunkData:
    def __init__(self, raw_data: bytes):
        self._raw_data = raw_data
        self._parse_data()

    def _parse_data(self):
        with TemporaryFile() as data_file:
            data_file.write(self._raw_data)
            data_file.seek(0)

            self.r = get_char(data_file)
            self.g = get_char(data_file)
            self.b = get_char(data_file)
            self.unknown_char = get_char(data_file)
            self.mips_instruction = get_bytes(data_file, 4)
            self.unknown_flag = get_long(data_file)
            self.dl_1_start = get_long(data_file)
            self.dl_1_size = get_long(data_file)
            self.dl_2_start = get_long(data_file)
            self.dl_2_size = get_long(data_file)
            self.dl_3_start = get_long(data_file)
            self.dl_3_size = get_long(data_file)
            self.dl_4_start = get_long(data_file)
            self.dl_4_size = get_long(data_file)
            self.vertex_start = get_long(data_file)
            self.vertex_size = get_long(data_file)

    @property
    def vertex_start_size(self) -> dict[int, int]:
        return {
            self.dl_1_start: (self.vertex_start, self.vertex_size),
            self.dl_2_start: (self.vertex_start, self.vertex_size),
            self.dl_3_start: (self.vertex_start, self.vertex_size),
            self.dl_4_start: (self.vertex_start, self.vertex_size),
        }


class DisplayList:
    def __init__(
        self,
        raw_data: bytes,
        raw_vertex_data: bytes,
        vertex_pointer: int,
        offset: int,
        branches: list["DisplayList"] = None,
        branched: bool = False,
    ):
        """And object representation of the N64 display list

        Args:
            raw_data (bytes): Raw data of the display list
            raw_vertex_data (bytes): Raw data of the verticies associated with this display list
            offset (int): Localized offset of this display list
        """
        self._raw_data = raw_data
        self._raw_vertex_data = raw_vertex_data
        self.vertex_pointer = vertex_pointer
        self.offset = offset
        self.branches = branches if branches else list()
        self.is_branched = branched

    def __repr__(self):
        if self.branches:
            return f"DisplayList({self.offset=}, {self.size=}, {self.num_commands=}, branches={len(self.branches)})"
        return f"DisplayList({self.offset=}, {self.size=}, {self.num_commands=})"

    @property
    def size(self) -> int:
        """Returns size of display list raw data

        Returns:
            int: Size of display list raw data
        """
        return len(self._raw_data)

    @property
    def num_commands(self) -> int:
        """Returns number of commands in the display list

        Returns:
            int: Number of commands
        """
        return int(self.size / 8)

    @property
    def vertex_buffers(self) -> list[commands.G_VTX]:
        """Returns a list of G_VTX objects

        Returns:
            list[commands.G_VTX]: A list of vertex buffer objects
        """
        return [cmd for cmd in self.commands if cmd.opcode == b"\x01"]

    @property
    def vertex_count(self) -> int:
        return sum([vtx.vertex_count for vtx in self.vertex_buffers])

    @property
    def recursive_vertex_count(self) -> int:
        total_verticies = 0
        for branch_dl in self.branches.values():
            total_verticies += branch_dl.recursive_vertex_count
        return self.vertex_count + total_verticies

    @property
    def branches(self) -> dict[str, "DisplayList"]:
        return self._branches

    @branches.setter
    def branches(self, branched_dls: list["DisplayList"]):
        branch_dict = dict()
        for branch in branched_dls:
            branch_dict[branch.offset] = branch
        self._branches = branch_dict

    @property
    def triangles(self) -> list[list[Triangle]]:
        """Returns a 2d list of triangle data in the display list, each sub-list corresponding to an adjacent vertex group

        Returns:
            list[list[commands.G_TRI1]]: A 2d list of triangle data
        """
        ret_list = list()
        tri_list = list()
        for cmd in self.commands:

            # Read vertex buffer and create new triangle list
            if cmd.opcode == b"\x01":
                tri_list = list()
                ret_list.append(tri_list)
                continue

            # Read triangle data and add it to the triangle list
            if cmd.opcode == b"\x05":
                tri = Triangle.from_tri1(cmd)
                tri_list.append(tri)
                continue

            # Read dual triangle data and add it to the triangle list
            if cmd.opcode == b"\x06":
                tri1, tri2 = Triangle.from_tri2(cmd)
                tri_list.append(tri1)
                tri_list.append(tri2)
                continue

            if cmd.opcode == b"\xDE":
                branched_dl = self.branches.get(int.from_bytes(cmd.address, "big"))
                ret_list.extend(branched_dl.triangles)
                continue

        return ret_list

    def _get_verticies(self, parent_vertex_data: bytes = None):
        ret_list = list()
        vert_list = list()

        for cmd in self.commands:

            if cmd.opcode == b"\x01":
                vertex_buffer_start = self.vertex_pointer + int.from_bytes(
                    cmd.address, "big"
                )
                vertex_buffer_end = vertex_buffer_start + cmd.vertex_count * 16
                vertex_data = parent_vertex_data[vertex_buffer_start:vertex_buffer_end]

                if vertex_buffer_end > len(parent_vertex_data):
                    vertex_buffer_start = int.from_bytes(cmd.address, "big")
                    vertex_buffer_end = vertex_buffer_start + cmd.vertex_count * 16
                    vertex_data = parent_vertex_data[
                        vertex_buffer_start:vertex_buffer_end
                    ]

                # Vertex data is 16 bytes long
                vert_start = 0
                vert_end = vert_start + 16

                for _ in range(cmd.vertex_count):
                    # Read the raw data and create a Vertex object out of it
                    vertex_bytes = vertex_data[vert_start:vert_end]
                    vertex = Vertex(vertex_bytes)
                    vert_list.append(vertex)

                    # Move the vertex start and end 16 bytes ahead
                    vert_start = vert_end
                    vert_end = vert_start + 16

                # Append the vert list and reset
                ret_list.append(vert_list)
                vert_list = list()

            if cmd.opcode == b"\xDE":
                branched_dl = self.branches.get(int.from_bytes(cmd.address, "big"))
                ret_list.extend(branched_dl._get_verticies(parent_vertex_data))

        return ret_list

    @property
    def verticies(self) -> list[list[Vertex]]:
        """Returns a 2d list of Vertex, each sub-list corresponding to an adjacent triangle group

        Returns:
            list[list[Vertex]]: A 2d list of vertex data
        """
        return self._get_verticies(self._raw_vertex_data)

    @property
    def commands(self) -> list[DL_Command]:
        """Returns the F3DEX2 commands in the display list

        Returns:
            list[DL_Command]: A list of F3DEX2 commands
        """
        ret_list = list()
        for command_pos in range(self.num_commands):
            command = self._raw_data[command_pos * 8 : command_pos * 8 + 8]
            # Parse each raw command in an object for easy parsing of data
            if cls := DL_COMMANDS.get(command[:1]):
                ret_list.append(cls(command))
        return ret_list


def create_display_lists(
    display_list_data: bytes,
    vertex_data: bytes,
    display_list_meta: list[DisplayListChunkData],
    /,
    _dl_pointer: int = 0,
    _branched: bool = False,
    _vertex_data: bytes = None,
    _expansions: list[DisplayListExpansion] = None,
) -> list[DisplayList]:
    ret_list = list()
    branches = list()

    increase_vertex_pointer = True

    dl_vertex_starts = dict()
    for chunk in display_list_meta:
        dl_vertex_starts.update(chunk.vertex_start_size)

    expansion_offsets = list()
    if _expansions:
        expansion_offsets = [expansion.display_list_offset for expansion in _expansions]

    # Write the raw data to a temporary file so we can seek and read as necessary
    with TemporaryFile() as data_file:

        data_file.write(display_list_data)
        data_file.seek(_dl_pointer)

        raw_data = b""
        vertex_pointer = 0
        dl_pointer = _dl_pointer
        old_vertex_start = 0

        branched_dls = dict()

        dl_raw_vertex_data = _vertex_data or vertex_data

        # While we haven't reached the vertex start point, read each 8 byte command
        while command_bytes := get_bytes(data_file, 8):

            # Get the F3DEX2 command class and intantiate it as an object
            cmd = DL_COMMANDS.get(command_bytes[:1])(command_bytes)

            # Write the command bytes. This will become our DisplayList's _raw_data
            raw_data += command_bytes

            if cmd.opcode == b"\xDE":

                if vertex_start_size := dl_vertex_starts.get(dl_pointer):
                    vertex_start, vertex_size = vertex_start_size
                    # if vertex_start != old_vertex_start:
                    vertex_pointer = 0
                    # old_vertex_start = vertex_start
                    dl_raw_vertex_data = vertex_data[
                        vertex_start : vertex_start + vertex_size
                    ]

                branched_display_lists = create_display_lists(
                    display_list_data,
                    vertex_data,
                    display_list_meta,
                    _dl_pointer=int.from_bytes(cmd.address, "big"),
                    _branched=True,
                    _vertex_data=dl_raw_vertex_data,
                    _expansions=_expansions,
                )
                branches.extend(branched_display_lists)

            # Once we reach the end of the Display List, create the object and start fresh
            if cmd.opcode == b"\xDF":
                try:
                    if vertex_size == vertex_pointer:
                        dl_raw_vertex_data = vertex_data
                        vertex_pointer = 0
                        increase_vertex_pointer = False
                except Exception:
                    pass

                if vertex_start_size := dl_vertex_starts.get(dl_pointer):
                    vertex_start, vertex_size = vertex_start_size
                    if vertex_start != old_vertex_start:
                        vertex_pointer = 0
                        old_vertex_start = vertex_start
                        increase_vertex_pointer = True
                    dl_raw_vertex_data = vertex_data[
                        vertex_start : vertex_start + vertex_size
                    ]

                if dl_pointer in expansion_offsets:
                    dl_raw_vertex_data = vertex_data
                    vertex_pointer = 0
                    increase_vertex_pointer = True

                if not (display_list := branched_dls.get(dl_pointer)):
                    display_list = DisplayList(
                        raw_data=raw_data,
                        raw_vertex_data=dl_raw_vertex_data,
                        offset=dl_pointer,
                        vertex_pointer=vertex_pointer,
                        branches=branches,
                        branched=_branched,
                    )

                ret_list.append(display_list)

                branched_dls.update(display_list.branches)

                if increase_vertex_pointer:
                    vertex_pointer += display_list.vertex_count * 16

                raw_data = b""
                dl_pointer = data_file.tell()

                branches.clear()

                if _branched:
                    break

    return ret_list
