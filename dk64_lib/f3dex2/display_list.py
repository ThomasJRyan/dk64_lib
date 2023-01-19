from dk64_lib.components.vertex import Vertex
from dk64_lib.f3dex2.commands import DL_COMMANDS, G_TRI1, G_VTX


class DisplayList:
    def __init__(self, raw_data: bytes, raw_vertex_data: bytes, offset: int):
        self._raw_data = raw_data
        self._raw_vertex_data = raw_vertex_data
        self.offset = offset

    def __repr__(self):
        return f"DisplayList({self.offset=}, {self.size=}, {self.num_commands=})"

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
            
            if cmd.opcode == b"\x01":
                tri_list = list()
                ret_list.append(tri_list)
                continue
            
            if cmd.opcode == b"\x05":
                tri_list.append(cmd)
                continue
        else:
            ret_list.append(tri_list)
        return ret_list
    
    @property
    def verticies(self):
        ret_list = list()
        vert_list = list()
        for vtx in self.vertex_buffers:
            vertex_buffer_start = int.from_bytes(vtx.start_address[1:], 'big')
            vertex_buffer_end = vertex_buffer_start + vtx.vertex_count * 16
            vertex_data = self._raw_vertex_data[vertex_buffer_start:vertex_buffer_end]
            
            vert_start = 0
            vert_end = vert_start + 16
            
            for _ in range(vtx.vertex_count):
                vertex_bytes = vertex_data[vert_start:vert_end]
                try:
                    vertex = Vertex(vertex_bytes)
                except:
                    # import pudb; pu.db
                    ...
                vert_list.append(vertex)
                vert_start = vert_end
                vert_end = vert_start + 16
                
            ret_list.append(vert_list)
            vert_list = list()
        return ret_list

    @property
    def commands(self):
        ret_list = list()
        for command_pos in range(self.num_commands):
            command = self._raw_data[command_pos * 8 : command_pos * 8 + 8]
            if cls := DL_COMMANDS.get(command[:1]):
                ret_list.append(cls(command))
        return ret_list
