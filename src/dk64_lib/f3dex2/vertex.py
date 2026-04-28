from dataclasses import dataclass

from dk64_lib.binary_reader import BinaryReader


@dataclass(frozen=True, slots=True)
class Vertex:
    x: int
    y: int
    z: int
    unk: int
    texture_cord_u: int
    texture_cord_v: int
    xr: int
    yg: int
    zb: int
    alpha: int

    @classmethod
    def from_bytes(cls, vertex_data: bytes) -> "Vertex":
        reader = BinaryReader(vertex_data)
        return cls(
            x=reader.read_i16(0),
            y=reader.read_i16(2),
            z=reader.read_i16(4),
            unk=reader.read_u16(6),
            texture_cord_u=reader.read_u16(8),
            texture_cord_v=reader.read_u16(10),
            xr=reader.read_u8(12),
            yg=reader.read_u8(13),
            zb=reader.read_u8(14),
            alpha=reader.read_u8(15),
        )

    def __repr__(self):
        return f"{self.__class__.__qualname__}({self.x}, {self.y}, {self.z})"

    def to_obj_line(self, include_color: bool = True) -> str:
        """Format this vertex as an OBJ vertex line."""
        position = f"v {self.x} {self.y} {self.z}"
        if not include_color:
            return position
        return (
            f"{position} "
            f"{self.xr / 255:.6f} "
            f"{self.yg / 255:.6f} "
            f"{self.zb / 255:.6f}"
        )
