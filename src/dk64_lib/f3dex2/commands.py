import re

from typing import Union


class G_SPNOOP:
    __slots__ = ("_raw_data", "opcode", "tag")
    parse_pattern = re.compile(b"(?P<opcode>\x00)(?P<tag>[\x00-\xFF]{7})")

    def __repr__(self):
        return f"G_SPNOOP(0x{self.tag.hex()})"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self._raw_data = command
        self.opcode = group["opcode"]
        self.tag = group["tag"]


class G_VTX:
    __slots__ = (
        "_raw_data",
        "opcode",
        "vertex_count",
        "buffer_start",
        "segment",
        "address",
    )
    parse_pattern = re.compile(
        b"(?P<opcode>\x01)(?P<v_count>[\x00-\xFF]{2})(?P<b_start>[\x00-\xFF])(?P<segment>[\x00-\xFF])(?P<address>[\x00-\xFF]{3})"
    )

    def __repr__(self):
        return f"G_VTX({self.vertex_count}, {self.buffer_start}, {self.address.hex()})"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self._raw_data = command
        self.opcode = group["opcode"]
        self.vertex_count = int(
            "{:16b}".format(int(group["v_count"].hex(), 16)).replace(" ", "0")[4:12], 2
        )
        self.buffer_start = (
            int.from_bytes(group["b_start"], "big") - self.vertex_count * 2
        )
        self.segment = group["segment"]
        self.address = group["address"]


class G_MODIFYVTX:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\x02)")

    def __repr__(self):
        return f"G_MODIFYVTX()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_CULLDL:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\x03)")

    def __repr__(self):
        return f"G_CULLDL()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_BRANCH_Z:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\x04)")

    def __repr__(self):
        return f"G_BRANCH_Z()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_TRI1:
    __slots__ = ("_raw_data", "opcode", "v1", "v2", "v3")
    parse_pattern = re.compile(
        b"(?P<opcode>\x05)(?P<v1>[\x00-\xFF])(?P<v2>[\x00-\xFF])(?P<v3>[\x00-\xFF])\x00\x00\x00\x00"
    )

    def __repr__(self):
        return f"G_TRI1({self.v1}, {self.v2}, {self.v3})"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command
        self.v1 = int(int.from_bytes(group["v1"], "big") / 2)
        self.v2 = int(int.from_bytes(group["v2"], "big") / 2)
        self.v3 = int(int.from_bytes(group["v3"], "big") / 2)


class G_TRI2:
    __slots__ = ("_raw_data", "opcode", "v1", "v2", "v3", "v4", "v5", "v6")
    parse_pattern = re.compile(
        b"(?P<opcode>\x06)(?P<v1>[\x00-\xFF])(?P<v2>[\x00-\xFF])(?P<v3>[\x00-\xFF])\x00(?P<v4>[\x00-\xFF])(?P<v5>[\x00-\xFF])(?P<v6>[\x00-\xFF])"
    )

    def __repr__(self):
        return f"G_TRI2(({self.v1}, {self.v2}, {self.v3}), ({self.v4}, {self.v5}, {self.v6}))"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command
        self.v1 = int(int.from_bytes(group["v1"], "big") / 2)
        self.v2 = int(int.from_bytes(group["v2"], "big") / 2)
        self.v3 = int(int.from_bytes(group["v3"], "big") / 2)
        self.v4 = int(int.from_bytes(group["v4"], "big") / 2)
        self.v5 = int(int.from_bytes(group["v5"], "big") / 2)
        self.v6 = int(int.from_bytes(group["v6"], "big") / 2)


class G_QUAD:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\x07)")

    def __repr__(self):
        return f"G_QUAD()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SPECIAL_3:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xD3)")

    def __repr__(self):
        return f"G_SPECIAL_3()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SPECIAL_2:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xD4)")

    def __repr__(self):
        return f"G_SPECIAL_2()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SPECIAL_1:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xD5)")

    def __repr__(self):
        return f"G_SPECIAL_1()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_DMA_IO:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xD6)")

    def __repr__(self):
        return f"G_DMA_IO()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_TEXTURE:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xD7)")

    def __repr__(self):
        return f"G_TEXTURE()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_POPMTX:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xD8)")

    def __repr__(self):
        return f"G_POPMTX()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_GEOMETRYMODE:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xD9)")

    def __repr__(self):
        return f"G_GEOMETRYMODE()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_MTX:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xDA)")

    def __repr__(self):
        return f"G_MTX()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_MOVEWORD:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xDB)")

    def __repr__(self):
        return f"G_MOVEWORD()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_MOVEMEM:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xDC)")

    def __repr__(self):
        return f"G_MOVEMEM()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_LOAD_UCODE:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xDD)")

    def __repr__(self):
        return f"G_LOAD_UCODE()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_DL:
    __slots__ = ("_raw_data", "opcode", "store_return_address", "segment", "address")
    parse_pattern = re.compile(
        b"(?P<opcode>\xDE)(?P<store_return_address>(\x00|\x01))\x00{2}(?P<segment>[\x00-\xFF])(?P<address>[\x00-\xFF]{3})"
    )

    def __repr__(self):
        return f"G_DL({self.store_return_address}, {self.address})"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command
        self.store_return_address = (
            True if group["store_return_address"] == b"\x00" else False
        )
        self.segment = group["segment"]
        self.address = group["address"]


class G_ENDDL:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xDF)")

    def __repr__(self):
        return f"G_ENDDL()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_NOOP:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xE0)")

    def __repr__(self):
        return f"G_NOOP()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_RDPHALF_1:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xE1)")

    def __repr__(self):
        return f"G_RDPHALF_1()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SetOtherMode_L:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xE2)")

    def __repr__(self):
        return f"G_SetOtherMode_L()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SetOtherMode_H:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xE3)")

    def __repr__(self):
        return f"G_SetOtherMode_H()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_TEXRECT:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xE4)")

    def __repr__(self):
        return f"G_TEXRECT()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_TEXRECTFLIP:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xE5)")

    def __repr__(self):
        return f"G_TEXRECTFLIP()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_RDPLOADSYNC:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xE6)")

    def __repr__(self):
        return f"G_RDPLOADSYNC()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_RDPPIPESYNC:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xE7)")

    def __repr__(self):
        return f"G_RDPPIPESYNC()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_RDPTILESYNC:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xE8)")

    def __repr__(self):
        return f"G_RDPTILESYNC()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_RDPFULLSYNC:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xE9)")

    def __repr__(self):
        return f"G_RDPFULLSYNC()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETKEYGB:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xEA)")

    def __repr__(self):
        return f"G_SETKEYGB()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETKEYR:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xEB)")

    def __repr__(self):
        return f"G_SETKEYR()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETCONVERT:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xEC)")

    def __repr__(self):
        return f"G_SETCONVERT()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETSCISSOR:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xED)")

    def __repr__(self):
        return f"G_SETSCISSOR()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETPRIMDEPTH:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xEE)")

    def __repr__(self):
        return f"G_SETPRIMDEPTH()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_RDPSetOtherMode:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xEF)")

    def __repr__(self):
        return f"G_RDPSetOtherMode()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_LOADTLUT:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xF0)")

    def __repr__(self):
        return f"G_LOADTLUT()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_RDPHALF_2:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xF1)")

    def __repr__(self):
        return f"G_RDPHALF_2()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETTILESIZE:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xF2)")

    def __repr__(self):
        return f"G_SETTILESIZE()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_LOADBLOCK:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xF3)")

    def __repr__(self):
        return f"G_LOADBLOCK()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_LOADTILE:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xF4)")

    def __repr__(self):
        return f"G_LOADTILE()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETTILE:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xF5)")

    def __repr__(self):
        return f"G_SETTILE()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_FILLRECT:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xF6)")

    def __repr__(self):
        return f"G_FILLRECT()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETFILLCOLOR:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xF7)")

    def __repr__(self):
        return f"G_SETFILLCOLOR()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETFOGCOLOR:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xF8)")

    def __repr__(self):
        return f"G_SETFOGCOLOR()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETBLENDCOLOR:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xF9)")

    def __repr__(self):
        return f"G_SETBLENDCOLOR()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETPRIMCOLOR:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xFA)")

    def __repr__(self):
        return f"G_SETPRIMCOLOR()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETENVCOLOR:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xFB)")

    def __repr__(self):
        return f"G_SETENVCOLOR()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETCOMBINE:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xFC)")

    def __repr__(self):
        return f"G_SETCOMBINE()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETTIMG:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xFD)")

    def __repr__(self):
        return f"G_SETTIMG()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETZIMG:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xFE)")

    def __repr__(self):
        return f"G_SETZIMG()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


class G_SETCIMG:
    __slots__ = ("_raw_data", "opcode")
    parse_pattern = re.compile(b"(?P<opcode>\xFF)")

    def __repr__(self):
        return f"G_SETCIMG()"

    def __init__(self, command: bytes):
        group = self.parse_pattern.match(command)
        self.opcode = group["opcode"]
        self._raw_data = command


DL_COMMANDS = {
    b"\x00": G_SPNOOP,
    b"\x01": G_VTX,
    b"\x02": G_MODIFYVTX,
    b"\x03": G_CULLDL,
    b"\x04": G_BRANCH_Z,
    b"\x05": G_TRI1,
    b"\x06": G_TRI2,
    b"\x07": G_QUAD,
    b"\xD3": G_SPECIAL_3,
    b"\xD4": G_SPECIAL_2,
    b"\xD5": G_SPECIAL_1,
    b"\xD6": G_DMA_IO,
    b"\xD7": G_TEXTURE,
    b"\xD8": G_POPMTX,
    b"\xD9": G_GEOMETRYMODE,
    b"\xDA": G_MTX,
    b"\xDB": G_MOVEWORD,
    b"\xDC": G_MOVEMEM,
    b"\xDD": G_LOAD_UCODE,
    b"\xDE": G_DL,
    b"\xDF": G_ENDDL,
    b"\xE0": G_NOOP,
    b"\xE1": G_RDPHALF_1,
    b"\xE2": G_SetOtherMode_L,
    b"\xE3": G_SetOtherMode_H,
    b"\xE4": G_TEXRECT,
    b"\xE5": G_TEXRECTFLIP,
    b"\xE6": G_RDPLOADSYNC,
    b"\xE7": G_RDPPIPESYNC,
    b"\xE8": G_RDPTILESYNC,
    b"\xE9": G_RDPFULLSYNC,
    b"\xEA": G_SETKEYGB,
    b"\xEB": G_SETKEYR,
    b"\xEC": G_SETCONVERT,
    b"\xED": G_SETSCISSOR,
    b"\xEE": G_SETPRIMDEPTH,
    b"\xEF": G_RDPSetOtherMode,
    b"\xF0": G_LOADTLUT,
    b"\xF1": G_RDPHALF_2,
    b"\xF2": G_SETTILESIZE,
    b"\xF3": G_LOADBLOCK,
    b"\xF4": G_LOADTILE,
    b"\xF5": G_SETTILE,
    b"\xF6": G_FILLRECT,
    b"\xF7": G_SETFILLCOLOR,
    b"\xF8": G_SETFOGCOLOR,
    b"\xF9": G_SETBLENDCOLOR,
    b"\xFA": G_SETPRIMCOLOR,
    b"\xFB": G_SETENVCOLOR,
    b"\xFC": G_SETCOMBINE,
    b"\xFD": G_SETTIMG,
    b"\xFE": G_SETZIMG,
    b"\xFF": G_SETCIMG,
}

DL_Command = Union[
    G_SPNOOP,
    G_VTX,
    G_MODIFYVTX,
    G_CULLDL,
    G_BRANCH_Z,
    G_TRI1,
    G_TRI2,
    G_QUAD,
    G_SPECIAL_3,
    G_SPECIAL_2,
    G_SPECIAL_1,
    G_DMA_IO,
    G_TEXTURE,
    G_POPMTX,
    G_GEOMETRYMODE,
    G_MTX,
    G_MOVEWORD,
    G_MOVEMEM,
    G_LOAD_UCODE,
    G_DL,
    G_ENDDL,
    G_NOOP,
    G_RDPHALF_1,
    G_SetOtherMode_L,
    G_SetOtherMode_H,
    G_TEXRECT,
    G_TEXRECTFLIP,
    G_RDPLOADSYNC,
    G_RDPPIPESYNC,
    G_RDPTILESYNC,
    G_RDPFULLSYNC,
    G_SETKEYGB,
    G_SETKEYR,
    G_SETCONVERT,
    G_SETSCISSOR,
    G_SETPRIMDEPTH,
    G_RDPSetOtherMode,
    G_LOADTLUT,
    G_RDPHALF_2,
    G_SETTILESIZE,
    G_LOADBLOCK,
    G_LOADTILE,
    G_SETTILE,
    G_FILLRECT,
    G_SETFILLCOLOR,
    G_SETFOGCOLOR,
    G_SETBLENDCOLOR,
    G_SETPRIMCOLOR,
    G_SETENVCOLOR,
    G_SETCOMBINE,
    G_SETTIMG,
    G_SETZIMG,
    G_SETCIMG,
]

def get_command(command_bytes):
    return DL_COMMANDS.get(command_bytes[:1])(command_bytes)