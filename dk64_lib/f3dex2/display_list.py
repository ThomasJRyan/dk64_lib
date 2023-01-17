from dk64_lib.f3dex2.commands import DL_COMMANDS, G_TRI1, G_VTX

class DisplayList():
    _raw_data: bytes
    offset: int
    
    def __init__(self, raw_data: bytes, start: int):
        self._raw_data = raw_data
        self.offset = start
    
    def __repr__(self):
        return f'DisplayList({self.offset=}, {self.size=}, {self.num_commands=})'
    
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