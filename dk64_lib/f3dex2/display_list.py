from dk64_lib.components.vertex import Vertex
from dk64_lib.f3dex2 import commands
from dk64_lib.f3dex2.commands import DL_COMMANDS, DL_Command


class DisplayList:
    def __init__(self, raw_data: bytes, raw_vertex_data: bytes, offset: int):
        """And object representation of the N64 display list

        Args:
            raw_data (bytes): Raw data of the display list
            raw_vertex_data (bytes): Raw data of the verticies associated with this display list
            offset (int): Localized offset of this display list
        """
        self._raw_data = raw_data
        self._raw_vertex_data = raw_vertex_data
        self.offset = offset

    def __repr__(self):
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
    def triangles(self) -> list[list[commands.G_TRI1]]:
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
                tri_list.append(cmd)
                continue

        # Add the last triangle list
        ret_list.append(tri_list)

        return ret_list

    @property
    def verticies(self) -> list[list[Vertex]]:
        """Returns a 2d list of Vertex, each sub-list corresponding to an adjacent triangle group

        Returns:
            list[list[Vertex]]: A 2d list of vertex data
        """
        ret_list = list()
        vert_list = list()
        for vtx in self.vertex_buffers:
            # Figure out where in the vertex data these verticies lie, and grab the raw data
            vertex_buffer_start = int.from_bytes(vtx.start_address[1:], "big")
            vertex_buffer_end = vertex_buffer_start + vtx.vertex_count * 16
            vertex_data = self._raw_vertex_data[vertex_buffer_start:vertex_buffer_end]

            # Vertex data is 16 bytes long
            vert_start = 0
            vert_end = vert_start + 16

            for _ in range(vtx.vertex_count):
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
        return ret_list

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
