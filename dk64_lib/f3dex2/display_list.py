from dk64_lib.components.vertex import Vertex
from dk64_lib.components.triangle import Triangle

from dk64_lib.f3dex2 import commands
from dk64_lib.f3dex2.commands import DL_COMMANDS, DL_Command

from tempfile import TemporaryFile

from dk64_lib.file_io import get_bytes, get_long, get_char

class DisplayListMeta():
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
    def vertex_starts(self) -> dict[int, int]:
        return {
            self.dl_1_start: self.vertex_start,
            self.dl_2_start: self.vertex_start,
            self.dl_3_start: self.vertex_start,
            self.dl_4_start: self.vertex_start,
        }

class DisplayList:
    def __init__(self, raw_data: bytes, file_offset: int, vertex_pointer: int, parent: object, branches: list['DisplayList'] = None, branched: bool = False):
        """And object representation of the N64 display list

        Args:
            raw_data (bytes): Raw data of the display list
            offset (int): Localized offset of this display list
        """
        self._raw_data = raw_data
        self.file_offset = file_offset
        self.vertex_pointer = vertex_pointer
        self.parent = parent
        self.branches = branches if branches else list()
        self.is_branched = branched

    def __repr__(self):
        return f"DisplayList({self.file_offset=}, {self.size=}, {self.num_commands=})"

    @property
    def dl_offset(self) -> int:
        return self.file_offset - self.parent.dl_start
    
    @property
    def branches(self) -> dict[str, 'DisplayList']:
        return self._branches
    
    @branches.setter
    def branches(self, branched_dls: list['DisplayList']):
        branch_dict = dict()
        for branch in branched_dls:
            branch_dict[branch.file_offset - self.parent.dl_start] = branch
        self._branches = branch_dict

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
    def recursive_vertex_count(self) -> int:
        total_verticies = 0
        for branch_dl in self.branches.values():
            total_verticies += branch_dl.recursive_vertex_count
        return self.vertex_count + total_verticies
    
    @property
    def vertex_count(self) -> int:
        return sum([vtx.vertex_count for vtx in self.vertex_buffers])

    @property
    def branch_dls(self) -> list['DisplayList']:
        ret_dict = dict()
        branch_addresses = [int.from_bytes(cmd.address, "big") for cmd in self.commands if cmd.opcode == b"\xDE"]
        for dl in self.parent.display_lists:
            if dl.dl_offset in branch_addresses:
                ret_dict[dl.dl_offset] = dl
        return ret_dict
    
    @property
    def vertex_data(self) -> bytes:
        vert_data_start = self.parent.vert_start + self.vertex_pointer
        vert_data_end = vert_data_start + self.recursive_vertex_count * 16
        return self.parent._raw_data[vert_data_start:vert_data_end]

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
                branched_dl = self.branches.get(int.from_bytes(cmd.address, 'big'))
                ret_list.extend(branched_dl.triangles)
                continue

        return ret_list
    
    def _get_verticies(self, parent_vertex_data: bytes = None):
        ret_list = list()
        vert_list = list()
                
        for cmd in self.commands:
            
            if cmd.opcode == b"\x01":
                vertex_buffer_start = int.from_bytes(cmd.address, "big")
                vertex_buffer_end = vertex_buffer_start + cmd.vertex_count * 16
                vertex_data = parent_vertex_data[vertex_buffer_start:vertex_buffer_end]

                # Vertex data is 16 bytes long
                vert_start = 0
                vert_end = vert_start + 16

                for _ in range(cmd.vertex_count):
                    # Read the raw data and create a Vertex object out of it
                    vertex_bytes = vertex_data[vert_start:vert_end]
                    try:
                        vertex = Vertex(vertex_bytes)
                        # if vertex.x == 0 and vertex.y == 0 and vertex.z == 0:
                        #     import pudb; pu.db
                    except:
                        # vertex = Vertex(b'\x00'*16)
                        # import pudb; pu.db
                        raise
                        continue
                    vert_list.append(vertex)

                    # Move the vertex start and end 16 bytes ahead
                    vert_start = vert_end
                    vert_end = vert_start + 16

                # Append the vert list and reset
                ret_list.append(vert_list)
                vert_list = list()
                
            if cmd.opcode == b"\xDE":
                branched_dl = self.branches.get(int.from_bytes(cmd.address, 'big'))
                ret_list.extend(branched_dl._get_verticies(parent_vertex_data))
        
        return ret_list
        

    @property
    def verticies(self) -> list[list[Vertex]]:
        """Returns a 2d list of Vertex, each sub-list corresponding to an adjacent triangle group

        Returns:
            list[list[Vertex]]: A 2d list of vertex data
        """
        return self._get_verticies(self.vertex_data)
        
        # vert_data_start = self.vert_start
        # vert_data_end = vert_data_start + self.recursive_vertex_count * 16
        
        # vert_data = self.parent._raw_data[vert_data_start:vert_data_end]
        
        # vert_data = b""
        
        # for branch_dl in self.branch_dls:
        #     vert_data += branch_dl.vertex_data
            
        # vert_data += self.vertex_data
        
        # for cmd in self.commands:
        #     if cmd.opcode == b"\x01":
        #         vert_data += self.
        
        
        # for vtx in self.vertex_buffers:
        #     # Figure out where in the vertex data these verticies lie, and grab the raw data
        #     vertex_buffer_start = int.from_bytes(vtx.start_address[1:], "big")
        #     vertex_buffer_end = vertex_buffer_start + vtx.vertex_count * 16
        #     vertex_data = self._raw_vertex_data[vertex_buffer_start:vertex_buffer_end]

        #     # Vertex data is 16 bytes long
        #     vert_start = 0
        #     vert_end = vert_start + 16

        #     for _ in range(vtx.vertex_count):
        #         # Read the raw data and create a Vertex object out of it
        #         vertex_bytes = vertex_data[vert_start:vert_end]
        #         vertex = Vertex(vertex_bytes)
        #         vert_list.append(vertex)

        #         # Move the vertex start and end 16 bytes ahead
        #         vert_start = vert_end
        #         vert_end = vert_start + 16

        #     # Append the vert list and reset
        #     ret_list.append(vert_list)
        #     vert_list = list()
        # return ret_list

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
