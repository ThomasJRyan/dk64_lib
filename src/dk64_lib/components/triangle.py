from dk64_lib.f3dex2 import commands


class Triangle:
    __slots__ = ("v1", "v2", "v3")

    def __init__(self, v1: int, v2: int, v3: int):
        self.v1 = v1
        self.v2 = v2
        self.v3 = v3

    def __repr__(self):
        return f"{self.__class__.__qualname__}({self.v1}, {self.v2}, {self.v3})"

    @classmethod
    def from_tri1(cls, cmd: commands.G_TRI1):
        assert cmd.opcode == b"\x05", "Must be an instance of G_TRI1"
        return cls(cmd.v1, cmd.v2, cmd.v3)

    @classmethod
    def from_tri2(cls, cmd: commands.G_TRI2):
        assert cmd.opcode == b"\x06", "Must be an instance of G_TRI2"
        return cls(cmd.v1, cmd.v2, cmd.v3), cls(cmd.v4, cmd.v5, cmd.v6)
