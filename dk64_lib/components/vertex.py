from ctypes import c_int16


class Vertex:
    __slots__ = (
        "x",
        "y",
        "z",
        "unk",
        "texture_cord_u",
        "texture_cord_v",
        "xr",
        "yg",
        "zb",
        "alpha",
    )

    def __init__(self, vertex_data: bytes):
        self.x = c_int16(int.from_bytes(vertex_data[0:2], "big")).value
        self.y = c_int16(int.from_bytes(vertex_data[2:4], "big")).value
        self.z = c_int16(int.from_bytes(vertex_data[4:6], "big")).value
        self.unk = int.from_bytes(vertex_data[6:8], "big")
        self.texture_cord_u = int.from_bytes(vertex_data[8:10], "big")
        self.texture_cord_v = int.from_bytes(vertex_data[10:12], "big")
        self.xr = vertex_data[12]
        self.yg = vertex_data[13]
        self.zb = vertex_data[14]
        self.alpha = vertex_data[15]

    def __repr__(self):
        return f"{self.__class__.__qualname__}({self.x}, {self.y}, {self.z})"
