import re
import pathlib

from dataclasses import dataclass
from tempfile import TemporaryFile

from numpy import array as numpy_array
from collada import Collada, source, material, geometry, scene

from dk64_lib.data_types.base import BaseData
from dk64_lib.f3dex2.display_list import (
    DisplayList,
    DisplayListChunkData,
    DisplayListExpansion,
    create_display_lists,
)
from dk64_lib.file_io import get_bytes, get_long

POINTER_PATTERN = re.compile(b'\x00[\x00-\xFF]\x08\x00\x00\x00\x00\x00')

class GeometryData(BaseData):
    def __post_init__(self):
        self.data_type = "Geometry"
        self.is_pointer = False
        if POINTER_PATTERN.match(self.raw_data[:8]):
            self.is_pointer = True
        self.points_to = None

        # Use a temporary file to allow us to seek throughout it
        with TemporaryFile() as data_file:
            data_file.write(self.raw_data)
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

    @property
    def pointer(self):
        if self.is_pointer:
            return self.raw_data[1]
        return None

    @property
    def dl_expansions(self) -> list[DisplayListExpansion]:
        """Returns a list of the display list expansion data

        Returns:
            list[DisplayListExpansion]: Display list expansion data
        """
        if self.is_pointer:
            return list()
        ret_list = list()
        with TemporaryFile() as data_file:
            data_file.write(self.raw_data)
            data_file.seek(self.dl_expansion_start)

            expansion_count = get_long(data_file)
            for _ in range(expansion_count):
                ret_list.append(DisplayListExpansion(get_bytes(data_file, 0x10)))

        return ret_list

    @property
    def vertex_chunk_data(self) -> list[DisplayListChunkData]:
        """Returns a list of display list chunk data found in the geometry file

        Returns:
            list[DisplayListChunkData]: Display list chunk data
        """
        if self.is_pointer:
            return list()
        ret_list = list()
        for chunk_num in range(int(self.vert_chunk_length / 52)):
            chunk_start = self.vert_chunk_start + 52 * chunk_num
            chunk_end = self.vert_chunk_start + 52 * (chunk_num + 1)
            ret_list.append(DisplayListChunkData(self.raw_data[chunk_start:chunk_end]))
        return ret_list

    @property
    def display_lists(self) -> list[DisplayList]:
        """Generate and return a list of display lists inside of the geometry data

        Returns:
            list[DisplayList]: A list of display lists
        """
        if self.is_pointer:
            return list()

        raw_dl_data = self.raw_data[self.dl_start : self.vert_start]

        raw_vertex_data = self.raw_data[
            self.vert_start : self.vert_start + self.vert_length
        ]

        return create_display_lists(
            raw_dl_data,
            raw_vertex_data,
            self.vertex_chunk_data,
            expansions=self.dl_expansions,
        )

    def create_obj(self) -> str:
        """Creates an obj file out of the geometry data

        Returns:
            str: Obj file data
        """
        obj_data = str()
        tri_offset = 1

        if self.is_pointer:
            return obj_data

        for dl_num, dl in enumerate(self.display_lists, 1):
            if dl.is_branched:
                continue

            obj_data += f"# Display List {dl_num}, Offset: {dl.offset}\n\n"

            for group_num, (verticies, triangles) in enumerate(
                zip(dl.verticies, dl.triangles), 1
            ):

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

    def create_dae(self) -> Collada:
        """Creates a dae file out of the geometry data

        Returns:
            Collada: dae file
        """
        mesh = Collada()
        
        vertex_data = list()
        vertex_colour_data = list()
        triangle_data = list()
        tri_offset = 0
        
        for dl in self.display_lists:
            if dl.is_branched:
                continue

            for verticies, triangles in zip(dl.verticies, dl.triangles):

                # Write vertecies to file
                for vertex in verticies:
                    vertex_data.extend((vertex.x, vertex.y, vertex.z))
                    vertex_colour_data.extend((vertex.xr / 255, vertex.yg / 255, vertex.zb / 255, vertex.alpha / 255))

                # # Write triangles/faces to file
                for tri in triangles:
                    triangle_data.extend((tri.v1 + tri_offset, tri.v2 + tri_offset, tri.v3 + tri_offset))

                # # The triangle offset is used to globally identify the vertex due to
                # # Display Lists reading them with local positions
                tri_offset += len(verticies)
        
        # Create the vertices and vertex colours
        src_vertices = source.FloatSource("geo-vertices", numpy_array(vertex_data), ('X', 'Y', 'Z'))
        src_vertices_colour = source.FloatSource('vertex-colours', numpy_array(vertex_colour_data), ('R', 'G', 'B', 'A'))
        
        # Create a geometry with the data points
        geom = geometry.Geometry(mesh, "geometry0", "map", [src_vertices, src_vertices_colour])
        mesh.geometries.append(geom)
        
        # Create a triangle set and append it to the geometry
        triset = geom.createTriangleSet(numpy_array(triangle_data), input_list, "vertex-material")
        geom.primitives.append(triset)

        # The input list is used to define the vertices and colours 
        input_list = source.InputList()
        input_list.addInput(0, 'VERTEX', "#geo-vertices")
        input_list.addInput(0, 'COLOR', '#vertex-colours')
        
        # Create the phong effect and material using the vertex colours
        effect = material.Effect('vertex-effect', [], 'phong', diffuse=src_vertices_colour)
        mat = material.Material('vertex-material', 'vertex-material', effect)
        mesh.effects.append(effect)
        mesh.materials.append(mat)
        
        # Create and add the scene
        geomnode = scene.GeometryNode(geom, [])
        node = scene.Node("node0", children=[geomnode])
        myscene = scene.Scene("myscene", [node])
        mesh.scenes.append(myscene)
        mesh.scene = myscene
        
        return mesh
        
    def save_to_dae(self, filename: str, folderpath: str = ".") -> None:
        """Save geometry data to dae format

        Args:
            filename (str): Name of dae file
            folderpath (str, optional): Folder path to save dae to. Defaults to ".".
        """
        filepath = pathlib.Path(folderpath, filename)
        self.create_dae().write(filepath)