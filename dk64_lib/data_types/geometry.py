import pathlib

from io import FileIO

from dataclasses import dataclass
from tempfile import TemporaryFile

from dk64_lib.data_types.base import BaseData
from dk64_lib.f3dex2.commands import DL_COMMANDS
from dk64_lib.f3dex2.display_list import DisplayList, DisplayListMeta, DisplayListExpansion, create_display_lists
from dk64_lib.file_io import get_bytes, get_long
   

@dataclass(repr=False)
class GeometryData(BaseData):
    data_type: str = "Geometry"

    def __post_init__(self):
        self.is_pointer = len(self._raw_data) <= 8
            
        # Use a temporary file to allow us to seek throughout it
        with TemporaryFile() as data_file:
            data_file.write(self._raw_data)
            data_file.seek(0)

            # Get the display list and vertex starts
            self.dl_start = get_long(data_file, 0x34)
            self.vert_start = get_long(data_file, 0x38)
            
            # ! I don't know what this is pointing to, but it signifies the end of the
            # ! vertex data which is importent
            _unknown_start = get_long(data_file, 0x40)
            self.vert_length = _unknown_start - self.vert_start
            
            self.vert_chunk_start = get_long(data_file, 0x68)
            
            # ! I don't know what this is pointing to, but it signifies the end of the
            # ! vertex chunk data which is importent
            _unknown_start = get_long(data_file, 0x6C)
            self.vert_chunk_length = _unknown_start - self.vert_chunk_start
            
            self.dl_expansion_start = get_long(data_file, 0x70)
            
               
    # def _read_display_list(self, fh: FileIO, dl_pointer: int = None, vertex_pointer: int = None, branched: bool = False):
    #     raw_data = b""
        
    #     if not dl_pointer:
    #         dl_pointer = fh.tell()
            
    #     fh.seek(dl_pointer)
        
    #     branches = list()
        
    #     while True:
    #         command_bytes = get_bytes(fh, 8)
            
    #         cmd =  DL_COMMANDS.get(command_bytes[:1])(command_bytes)

    #         raw_data += command_bytes
            
    #         if cmd.opcode == b"\xDE":
    #             branched_display_list, _, _ = self._read_display_list(fh, int.from_bytes(cmd.address, 'big') + self.dl_start, vertex_pointer, True)
    #             fh.seek(dl_pointer + len(raw_data))
    #             branches.append(branched_display_list)
            
    #         if cmd.opcode == b"\xDF":
    #             display_list = DisplayList(
    #                     raw_data=raw_data,
    #                     file_offset=dl_pointer,
    #                     vertex_pointer=vertex_pointer,
    #                     parent=self,
    #                     branches=branches,
    #                     branched=branched,
    #                 )
                
    #             return display_list, vertex_pointer + display_list.recursive_vertex_count * 16, display_list.dl_offset + display_list.size
                    
                # ret_list.append(
                #     display_list
                # )
                    
                # vert_start += display_list.vertex_count * 16
             
    @property
    def dl_expansions(self) -> list[DisplayListExpansion]:
        ret_list = list()
        with TemporaryFile() as data_file:
            data_file.write(self._raw_data)
            data_file.seek(self.dl_expansion_start)
            
            expansion_count = get_long(data_file)
            for _ in range(expansion_count):
                ret_list.append(
                    DisplayListExpansion(get_bytes(data_file, 0x10))
                )
                
        return ret_list
            
                
    @property
    def vertex_chunk_data(self) -> list[DisplayListMeta]:
        ret_list = list()
        for chunk_num in range(int(self.vert_chunk_length / 52)):
            chunk_start = self.vert_chunk_start + 52 * chunk_num
            chunk_end = self.vert_chunk_start + 52 * (chunk_num + 1)
            ret_list.append(
                DisplayListMeta(self._raw_data[chunk_start : chunk_end])
            )
        return ret_list
                
    @property
    def display_lists(self) -> list[DisplayList]:
        """Generate and return a list of display lists inside of the geometry data

        Returns:
            list[DisplayList]: A list of display lists
        """
        # ret_list = list()
        
        raw_dl_data = self._raw_data[self.dl_start : self.vert_start]
        
        raw_vertex_data = self._raw_data[self.vert_start : self.vert_start + self.vert_length]
        
        return create_display_lists(raw_dl_data, raw_vertex_data, self.vertex_chunk_data, _expansions=self.dl_expansions)
        
        # import pudb; pu.db
        
        # for dl_meta in self.display_list_meta:
        #     vertex_data_start = dl_meta.vertex_start + self.vert_start
        #     vertex_data_end = dl_meta.vertex_start + dl_meta.vertex_size + self.vert_start
        #     raw_vertex_data = self._raw_data[vertex_data_start: vertex_data_end]
        #     ret_list.extend(dl_meta.create_display_lists(raw_dl_data, raw_vertex_data))
        
        dl_data = b""
        dl_pointer = 0
        
        with TemporaryFile() as dl_data_file:
            dl_data_file.write(raw_dl_data)
            dl_data_file.seek(0)
            
            while True:
                if not (command_bytes := get_bytes(dl_data_file, 8)):
                    break
                
                # Get the F3DEX2 command class and intantiate it as an object
                cmd =  DL_COMMANDS.get(command_bytes[:1])(command_bytes)
                
                # Write the command bytes. This will become our DisplayList's _raw_data
                dl_data += command_bytes
                
                # Once we reach the end of the Display List, create the object and start fresh
                if cmd.opcode == b"\xDF":
                    display_list = DisplayList(
                        raw_data=raw_data,
                        raw_vertex_data=raw_vertex_data,
                        offset=dl_pointer,
                        vertex_pointer=vertex_pointer,
                        branches=branches,
                        # branched=branched,
                    )
                    
                    ret_list.append(
                        display_list
                    )
                    
                    dl_pointer = dl_data_file.tell()
                    
                    raw_data = b""
        
        return ret_list
        
        # ret_list = list()
        # dl_start = self.dl_start
        # vert_start = self.vert_start
        
        # dl_vertex_starts = dict()
        # for chunk in self.display_list_meta:
        #     dl_vertex_starts.update(chunk.vertex_starts)

        # import pudb; pu.db

        # # Write the raw data to a temporary file so we can seek and read as necessary
        # with TemporaryFile() as data_file:
        #     data_file.write(self._raw_data)
        #     data_file.seek(dl_start)
        #     # raw_data = b""
        #     vertex_pointer = 0
        #     dl_pointer = 0
            
        #     branched_dls = dict()

        #     # While we haven't reached the vertex start point, read each 8 byte command
        #     while data_file.tell() < self.vert_start:
        #         display_list, new_vertex_pointer, dl_pointer = self._read_display_list(data_file, vertex_pointer=dl_vertex_starts[dl_pointer])
        #         branched_dls |= display_list.branches
        #         if (existing_dl := branched_dls.get(display_list.dl_offset)):
        #             display_list = existing_dl
        #         else:
        #             vertex_pointer = new_vertex_pointer
        #         ret_list.append(display_list)
                
                
                # if (existing_dl := [dl for dl in ret_list if dl.file_offset == display_list.file_offset]):
                #     display_list = existing_dl[0]
                # command_bytes = get_bytes(data_file, 8)

                # # Get the F3DEX2 command class and intantiate it as an object
                # cmd =  DL_COMMANDS.get(command_bytes[:1])(command_bytes)

                # # Write the command bytes. This will become our DisplayList's _raw_data
                # raw_data += command_bytes

                # # Once we reach the end of the Display List, create the object and start fresh
                # if cmd.opcode == b"\xDF":
                #     display_list = DisplayList(
                #             raw_data=raw_data,
                #             file_offset=dl_start,
                #             vert_start=vert_start,
                #             parent=self,
                #         )
                    
                #     ret_list.append(
                #         display_list
                #     )
                    
                #     vert_start += display_list.vertex_count * 16
                    
                #     raw_data = b""
                #     dl_start = data_file.tell()

        return ret_list
    
    def create_obj(self) -> str:
        """Creates an obj file out of the geometry data

        Returns:
            str: Obj file data
        """
        obj_data = str()
        tri_offset = 1
        # import pudb; pu.db
        
        if self.is_pointer:
            return obj_data
        
        for dl_num, dl in enumerate(self.display_lists, 1):
            if dl.is_branched:
                continue
            
            obj_data += f"# Display List {dl_num}, Offset: {dl.offset}\n\n"
            
            # verticies, triangles = dl.verticies, dl.triangles
            # assert len(verticies) == len(triangles), 'Display List does not have the same amount of verticies and triangles, something went wrong'
            for group_num, (verticies, triangles) in enumerate(zip(dl.verticies, dl.triangles), 1):
                
                obj_data += f"# Vertex Group {group_num}\n\n"
                
                # Write vertecies to file
                for vertex in verticies:
                    obj_line = f"v {vertex.x} {vertex.y} {vertex.z}\n"
                    obj_data += obj_line
                obj_data += "\n"
                
                obj_data += f"# Triangle Group {group_num}\n\n"

                # Write triangles/faces to file
                for tri in triangles:
                    obj_line = f"f {tri.v1 + tri_offset} {tri.v2 + tri_offset} {tri.v3 + tri_offset}\n"
                    obj_data += obj_line
                obj_data += "\n"

                # The triangle offset is used to globally identify the vertex due to
                # Display Lists reading them with local positions
                tri_offset += len(verticies)
        return obj_data

    def save_to_obj(self, filename: str, folderpath: str = ".") -> None:
        """Save geometry data to obj format

        Args:
            filename (str): Name of obj file
            folderpath (str, optional): Folder path to save obj to. Defaults to ".".
        """
        filepath = pathlib.Path(folderpath, filename)
        with open(filepath, "w") as obj_file:
            obj_file.write(self.create_obj())
