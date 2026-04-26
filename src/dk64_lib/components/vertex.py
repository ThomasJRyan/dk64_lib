from dk64_lib.binary_reader import BinaryReader


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
        reader = BinaryReader(vertex_data)
        self.x = reader.read_i16(0)
        self.y = reader.read_i16(2)
        self.z = reader.read_i16(4)
        self.unk = reader.read_u16(6)
        self.texture_cord_u = reader.read_u16(8)
        self.texture_cord_v = reader.read_u16(10)
        self.xr = reader.read_u8(12)
        self.yg = reader.read_u8(13)
        self.zb = reader.read_u8(14)
        self.alpha = reader.read_u8(15)

    def __repr__(self):
        return f"{self.__class__.__qualname__}({self.x}, {self.y}, {self.z})"
