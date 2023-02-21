from tempfile import TemporaryFile

from dk64_lib.components.vertex import Vertex
from dk64_lib.components.triangle import Triangle

from dk64_lib.f3dex2 import commands
from dk64_lib.f3dex2.commands import get_command, DL_Command

from dk64_lib.file_io import get_bytes, get_long, get_char


class DisplayListExpansion:
    """
        This section of the geometry is currently not fully understood
        As such, there are signficant gaps in the known values
        
        Currently, the only known information is that the third u32 points
        to a display list. This display list uses the entire vertex data
        when calling VTX commands instead of a segmented chunk
    """
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
        """An object representation of the N64 display list

        Args:
            raw_data (bytes): Raw data of the display list
            raw_vertex_data (bytes): Raw data of the verticies associated with this display list
            vertex_pointer (int): The display list's pointer in the vertex data
            offset (int): Localized offset of this display list
            branches (list[DisplayList], optional): The display list's branches. Defaults to None.
            branched (bool, optional): Whether the display list is branched or not. Defaults to False.
        """
        
        
        self._raw_data = raw_data
        self.branches = branches if branches else list()
        self.raw_vertex_data = raw_vertex_data
        self.vertex_pointer = vertex_pointer
        self.offset = offset
        self.is_branched = branched

    def __repr__(self):
        if self.branches:
            return f"DisplayList({self.offset=}, {self.size=}, {self.num_commands=}, branches={len(self.branches)})"
        return f"DisplayList({self.offset=}, {self.size=}, {self.num_commands=})"

    def __eq__(self, obj):
        if isinstance(obj, int):
            return self.offset == obj
        return self == obj

    @property
    def raw_vertex_data(self):
        return self._raw_vertex_data

    @raw_vertex_data.setter
    def raw_vertex_data(self, raw_vertex_data):
        self._raw_vertex_data = raw_vertex_data
        for branch in self.branches:
            branch.raw_vertex_data = raw_vertex_data

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
        for branch_dl in self.branches:
            total_verticies += branch_dl.recursive_vertex_count
        return self.vertex_count + total_verticies

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
                branched_dl = self.get_branch_by_offset(
                    int.from_bytes(cmd.address, "big")
                )
                ret_list.extend(branched_dl.triangles)
                continue

        return ret_list

    @property
    def verticies(self) -> list[list[Vertex]]:
        """Returns a 2d list of Vertex, each sub-list corresponding to an adjacent triangle group

        Returns:
            list[list[Vertex]]: A 2d list of vertex data
        """
        ret_list = list()
        vert_list = list()

        for cmd in self.commands:

            if cmd.opcode == b"\x01":
                vertex_buffer_start = self.vertex_pointer + int.from_bytes(
                    cmd.address, "big"
                )
                vertex_buffer_end = vertex_buffer_start + cmd.vertex_count * 16
                vertex_data = self._raw_vertex_data[
                    vertex_buffer_start:vertex_buffer_end
                ]

                if vertex_buffer_end > len(self._raw_vertex_data):
                    vertex_buffer_start = int.from_bytes(cmd.address, "big")
                    vertex_buffer_end = vertex_buffer_start + cmd.vertex_count * 16
                    vertex_data = self._raw_vertex_data[
                        vertex_buffer_start:vertex_buffer_end
                    ]

                # Vertex data is 16 bytes long
                vert_start = 0
                vert_end = vert_start + 16

                for _ in range(cmd.vertex_count):
                    # Read the raw data and create a Vertex object out of it
                    vert_list.append(Vertex(vertex_data[vert_start:vert_end]))

                    # Move the vertex start and end 16 bytes ahead
                    vert_start = vert_end
                    vert_end = vert_start + 16

                # Append the vert list and reset
                ret_list.append(vert_list)
                vert_list = list()
                continue

            if cmd.opcode == b"\xDE":
                branched_dl = self.get_branch_by_offset(
                    int.from_bytes(cmd.address, "big")
                )
                ret_list.extend(branched_dl.verticies)
                continue

        return ret_list

    @property
    def commands(self) -> list[DL_Command]:
        """Returns the F3DEX2 commands in the display list

        Returns:
            list[DL_Command]: A list of F3DEX2 commands
        """
        ret_list = list()
        for command_pos in range(self.num_commands):
            command_bytes = self._raw_data[command_pos * 8 : command_pos * 8 + 8]
            # Parse each raw command in an object for easy parsing of data
            if command := get_command(command_bytes):
                ret_list.append(command)
        return ret_list

    def get_branch_by_offset(self, offset):
        if offset in self.branches:
            return self.branches[self.branches.index(offset)]
        return None


def create_display_lists(
    display_list_data: bytes,
    vertex_data: bytes,
    display_list_chunk_data: list[DisplayListChunkData],
    expansions: list[DisplayListExpansion] = None,
) -> list[DisplayList]:
    """Create a geometry's display lists given the display list data, vertex data, and display list chunk data

    Args:
        display_list_data (bytes): Display list data
        vertex_data (bytes): Vertex data
        display_list_chunk_data (list[DisplayListChunkData]): List of DisplayListChunkData
        expansions (list[DisplayListExpansion], optional): Any display list expansion data that might exist in the geometry file. Defaults to None.

    Returns:
        list[DisplayList]: A list of DisplayList objects
    """

    def read_display_lists(
        dl_pointer: int = 0, branched: bool = False, inherited_vertex_data: bytes = None
    ) -> list[DisplayList]:
        """Recursively read display lists

        Args:
            _dl_pointer (int, optional): The display list pointer. Defaults to 0.
            _branched (bool, optional): When the display list is branched or not. Defaults to False.
            _vertex_data (bytes, optional): Vertex data to override the standard vertex_data with. Defaults to None.


        Returns:
            list[DisplayList]: A list of DisplayList objects
        """
        nonlocal display_list_data, vertex_data, display_list_chunk_data, expansions
        ret_list = list()
        branches = list()

        # Generate a dict where the key is the dl offset and the value is a tuple containing the start and size of the vertices
        dl_vertex_starts = {
            k: v
            for chunk in display_list_chunk_data
            for k, v in chunk.vertex_start_size.items()
        }

        # Generate a list of offsets inlucded in the expansion data. These display lists will use the entire vertex data instead of a segment
        expansion_offsets = (
            [expansion.display_list_offset for expansion in expansions]
            if expansions
            else []
        )

        # Write the raw data to a temporary file so we can seek and read as necessary
        with TemporaryFile() as data_file:

            data_file.write(display_list_data)
            data_file.seek(dl_pointer)

            raw_data = b""
            vertex_pointer = 0
            old_vertex_start = 0

            branched_dls = dict()

            dl_raw_vertex_data = inherited_vertex_data or vertex_data

            # While we haven't reached the vertex start point, read each 8 byte command
            while command_bytes := get_bytes(data_file, 8):

                # Get the F3DEX2 command class and intantiate it as an object
                cmd = get_command(command_bytes)

                # Write the command bytes. This will become our DisplayList's _raw_data
                raw_data += command_bytes

                # * Handle branching display lists
                if cmd.opcode == b"\xDE":

                    branches.extend(
                        read_display_lists(
                            dl_pointer=int.from_bytes(cmd.address, "big"),
                            branched=True,
                            inherited_vertex_data=dl_raw_vertex_data,
                        )
                    )
                    continue

                # * Once we reach the end of the Display List, create the object and start fresh
                if cmd.opcode == b"\xDF":

                    # TODO: This is a relic of poor understanding of display list vertex data
                    # TODO: There has to be a cleaner method of processing this
                    if dl_vertex_starts.get(dl_pointer):
                        vertex_start, vertex_size = dl_vertex_starts[dl_pointer]
                        if vertex_start != old_vertex_start:
                            vertex_pointer = 0
                            old_vertex_start = vertex_start
                        dl_raw_vertex_data = vertex_data[
                            vertex_start : vertex_start + vertex_size
                        ]

                    # If the display list exists in the expansion array, then it uses the entire vertex data
                    if dl_pointer in expansion_offsets:
                        dl_raw_vertex_data = vertex_data
                        vertex_pointer = 0

                    # Check and see if the display list currently exists in the branches, if it does, add that instead
                    # Otherwise, generate a new one
                    display_list = branched_dls.get(dl_pointer)
                    if not display_list:
                        display_list = DisplayList(
                            raw_data=raw_data,
                            raw_vertex_data=dl_raw_vertex_data,
                            offset=dl_pointer,
                            vertex_pointer=vertex_pointer,
                            branches=branches,
                            branched=branched,
                        )

                    # Update relevant variables
                    ret_list.append(display_list)
                    branched_dls.update({dl.offset: dl for dl in display_list.branches})
                    vertex_pointer += display_list.vertex_count * 16

                    # Update the branches to use the parent vertex data
                    for branch in branches:
                        branch._raw_vertex_data = dl_raw_vertex_data

                    # Reset for the next display list
                    raw_data = b""
                    branches = list()
                    dl_pointer = data_file.tell()

                    # If this is a branched display list, break and return
                    if branched:
                        break
                    continue

        return ret_list

    return read_display_lists()
