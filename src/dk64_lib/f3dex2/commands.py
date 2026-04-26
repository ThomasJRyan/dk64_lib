from typing import Union

from dk64_lib.binary_reader import BinaryReader


def _init_command(command_obj, command: bytes) -> BinaryReader:
    reader = BinaryReader(command)
    command_obj._raw_data = command
    command_obj.opcode = reader.read_at(0, 1)
    return reader


def _word_pair(reader: BinaryReader) -> tuple[int, int]:
    return reader.read_u32(0), reader.read_u32(4)


def _u24(reader: BinaryReader, offset: int) -> int:
    return int.from_bytes(reader.read_at(offset, 3), "big")


def _sign_extend(value: int, bits: int) -> int:
    sign_bit = 1 << (bits - 1)
    return (value ^ sign_bit) - sign_bit


def _vertex_index(reader: BinaryReader, offset: int) -> int:
    return reader.read_u8(offset) // 2


def _packed_coordinate_pair(word: int) -> tuple[int, int]:
    return (word >> 12) & 0xFFF, word & 0xFFF


def _decode_textured_rectangle(reader: BinaryReader) -> tuple[int, int, int, int, int]:
    word0, word1 = _word_pair(reader)
    lrx, lry = _packed_coordinate_pair(word0)
    ulx, uly = _packed_coordinate_pair(word1)
    return lrx, lry, (word1 >> 24) & 0x7, ulx, uly


def _decode_fill_rectangle(reader: BinaryReader) -> tuple[int, int, int, int]:
    word0, word1 = _word_pair(reader)
    lrx, lry = _packed_coordinate_pair(word0)
    ulx, uly = _packed_coordinate_pair(word1)
    return lrx, lry, ulx, uly


def _decode_tile_coordinates(reader: BinaryReader) -> tuple[int, int, int, int, int]:
    word0, word1 = _word_pair(reader)
    uls, ult = _packed_coordinate_pair(word0)
    lrs, lrt = _packed_coordinate_pair(word1)
    return uls, ult, (word1 >> 24) & 0x7, lrs, lrt


def _decode_rgba(reader: BinaryReader) -> tuple[int, int, int, int]:
    return (
        reader.read_u8(4),
        reader.read_u8(5),
        reader.read_u8(6),
        reader.read_u8(7),
    )


def _decode_image(reader: BinaryReader) -> tuple[int, int, int, int]:
    image_type = reader.read_u8(1)
    return (
        (image_type >> 5) & 0x7,
        (image_type >> 3) & 0x3,
        (reader.read_u16(2) & 0x0FFF) + 1,
        reader.read_u32(4),
    )


class _NoPayloadCommand:
    __slots__ = ("_raw_data", "opcode")

    def __init__(self, command: bytes):
        _init_command(self, command)


class G_SPNOOP:
    __slots__ = ("_raw_data", "opcode", "tag")

    def __repr__(self):
        return f"G_SPNOOP(0x{self.tag.hex()})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.tag = reader.read_at(1, 7)


class G_VTX:
    __slots__ = (
        "_raw_data",
        "opcode",
        "vertex_count",
        "buffer_start",
        "segment",
        "address",
    )

    def __repr__(self):
        return f"G_VTX({self.vertex_count}, {self.buffer_start}, {self.address.hex()})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.vertex_count = (reader.read_u16(1) >> 4) & 0xFF
        self.buffer_start = reader.read_u8(3) - self.vertex_count * 2
        self.segment = reader.read_at(4, 1)
        self.address = reader.read_at(5, 3)


class G_MODIFYVTX:
    __slots__ = ("_raw_data", "opcode", "where", "vertex_index", "value")

    def __repr__(self):
        return f"G_MODIFYVTX({self.vertex_index}, 0x{self.where:02x}, 0x{self.value:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.where = reader.read_u8(1)
        self.vertex_index = reader.read_u16(2) // 2
        self.value = reader.read_u32(4)


class G_CULLDL:
    __slots__ = ("_raw_data", "opcode", "vfirst", "vlast")

    def __repr__(self):
        return f"G_CULLDL({self.vfirst}, {self.vlast})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.vfirst = reader.read_u16(2) // 2
        self.vlast = reader.read_u16(6) // 2


class G_BRANCH_Z:
    __slots__ = (
        "_raw_data",
        "opcode",
        "vertex_index_a",
        "vertex_index_b",
        "z_value",
    )

    def __repr__(self):
        return f"G_BRANCH_Z({self.vertex_index_a}, {self.z_value})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        vertex_fields = _u24(reader, 1)
        self.vertex_index_a = ((vertex_fields >> 12) & 0xFFF) // 5
        self.vertex_index_b = (vertex_fields & 0xFFF) // 2
        self.z_value = reader.read_u32(4)


class G_TRI1:
    __slots__ = ("_raw_data", "opcode", "v1", "v2", "v3")

    def __repr__(self):
        return f"G_TRI1({self.v1}, {self.v2}, {self.v3})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.v1 = _vertex_index(reader, 1)
        self.v2 = _vertex_index(reader, 2)
        self.v3 = _vertex_index(reader, 3)


class G_TRI2:
    __slots__ = ("_raw_data", "opcode", "v1", "v2", "v3", "v4", "v5", "v6")

    def __repr__(self):
        return f"G_TRI2(({self.v1}, {self.v2}, {self.v3}), ({self.v4}, {self.v5}, {self.v6}))"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.v1 = _vertex_index(reader, 1)
        self.v2 = _vertex_index(reader, 2)
        self.v3 = _vertex_index(reader, 3)
        self.v4 = _vertex_index(reader, 5)
        self.v5 = _vertex_index(reader, 6)
        self.v6 = _vertex_index(reader, 7)


class G_QUAD:
    __slots__ = (
        "_raw_data",
        "opcode",
        "v1",
        "v2",
        "v3",
        "v4",
        "v1_duplicate",
        "v3_duplicate",
    )

    def __repr__(self):
        return f"G_QUAD({self.v1}, {self.v2}, {self.v3}, {self.v4})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.v1 = _vertex_index(reader, 1)
        self.v2 = _vertex_index(reader, 2)
        self.v3 = _vertex_index(reader, 3)
        self.v1_duplicate = _vertex_index(reader, 5)
        self.v3_duplicate = _vertex_index(reader, 6)
        self.v4 = _vertex_index(reader, 7)


class G_SPECIAL_3(_NoPayloadCommand):
    __slots__ = ()

    def __repr__(self):
        return f"G_SPECIAL_3()"


class G_SPECIAL_2(_NoPayloadCommand):
    __slots__ = ()

    def __repr__(self):
        return f"G_SPECIAL_2()"


class G_SPECIAL_1(_NoPayloadCommand):
    __slots__ = ()

    def __repr__(self):
        return f"G_SPECIAL_1()"


class G_DMA_IO:
    __slots__ = ("_raw_data", "opcode", "flag", "dmem", "dram", "size")

    def __repr__(self):
        return f"G_DMA_IO({self.flag}, {self.dmem}, 0x{self.dram:08x}, {self.size})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        control = _u24(reader, 1)
        dmem_field = (control >> 12) & 0xFFF
        self.flag = (dmem_field >> 11) & 0x1
        self.dmem = ((dmem_field >> 1) & 0x3FF) * 8
        self.size = (control & 0xFFF) + 1
        self.dram = reader.read_u32(4)


class G_TEXTURE:
    __slots__ = ("_raw_data", "opcode", "level", "tile", "on", "scale_s", "scale_t")

    def __repr__(self):
        return f"G_TEXTURE({self.scale_s}, {self.scale_t}, {self.level}, {self.tile}, {self.on})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        parameters = reader.read_u16(2)
        self.level = (parameters >> 11) & 0x7
        self.tile = (parameters >> 8) & 0x7
        self.on = (parameters >> 1) & 0x7F
        self.scale_s = reader.read_u16(4)
        self.scale_t = reader.read_u16(6)


class G_POPMTX:
    __slots__ = ("_raw_data", "opcode", "num_matrices")

    def __repr__(self):
        return f"G_POPMTX({self.num_matrices})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.num_matrices = reader.read_u32(4) // 64


class G_GEOMETRYMODE:
    __slots__ = ("_raw_data", "opcode", "clear_bits", "set_bits")

    def __repr__(self):
        return f"G_GEOMETRYMODE(0x{self.clear_bits:06x}, 0x{self.set_bits:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.clear_bits = (~(reader.read_u32(0) & 0x00FFFFFF)) & 0x00FFFFFF
        self.set_bits = reader.read_u32(4)


class G_MTX:
    __slots__ = ("_raw_data", "opcode", "params", "address")

    def __repr__(self):
        return f"G_MTX(0x{self.address:08x}, 0x{self.params:02x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.params = reader.read_u8(3) ^ 0x1
        self.address = reader.read_u32(4)


class G_MOVEWORD:
    __slots__ = ("_raw_data", "opcode", "index", "offset", "data")

    def __repr__(self):
        return f"G_MOVEWORD(0x{self.index:02x}, 0x{self.offset:04x}, 0x{self.data:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.index = reader.read_u8(1)
        self.offset = reader.read_u16(2)
        self.data = reader.read_u32(4)


class G_MOVEMEM:
    __slots__ = ("_raw_data", "opcode", "size", "offset", "index", "address")

    def __repr__(self):
        return f"G_MOVEMEM({self.size}, 0x{self.index:02x}, {self.offset}, 0x{self.address:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.size = ((reader.read_u8(1) >> 3) + 1) * 8
        self.offset = reader.read_u8(2) * 8
        self.index = reader.read_u8(3)
        self.address = reader.read_u32(4)


class G_LOAD_UCODE:
    __slots__ = ("_raw_data", "opcode", "data_size", "text_start")

    def __repr__(self):
        return f"G_LOAD_UCODE(0x{self.text_start:08x}, {self.data_size})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.data_size = reader.read_u16(2)
        self.text_start = reader.read_u32(4)


class G_DL:
    __slots__ = ("_raw_data", "opcode", "store_return_address", "segment", "address")

    def __repr__(self):
        return f"G_DL({self.store_return_address}, {self.address})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.store_return_address = reader.read_u8(1) == 0
        self.segment = reader.read_at(4, 1)
        self.address = reader.read_at(5, 3)


class G_ENDDL(_NoPayloadCommand):
    __slots__ = ()

    def __repr__(self):
        return f"G_ENDDL()"


class G_NOOP(_NoPayloadCommand):
    __slots__ = ()

    def __repr__(self):
        return f"G_NOOP()"


class G_RDPHALF_1:
    __slots__ = ("_raw_data", "opcode", "word")

    def __repr__(self):
        return f"G_RDPHALF_1(0x{self.word:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.word = reader.read_u32(4)


class G_SetOtherMode_L:
    __slots__ = ("_raw_data", "opcode", "encoded_shift", "shift", "length", "data")

    def __repr__(self):
        return f"G_SetOtherMode_L({self.shift}, {self.length}, 0x{self.data:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.encoded_shift = reader.read_u8(2)
        self.length = reader.read_u8(3) + 1
        self.shift = 32 - self.length - self.encoded_shift
        self.data = reader.read_u32(4)


class G_SetOtherMode_H:
    __slots__ = ("_raw_data", "opcode", "encoded_shift", "shift", "length", "data")

    def __repr__(self):
        return f"G_SetOtherMode_H({self.shift}, {self.length}, 0x{self.data:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.encoded_shift = reader.read_u8(2)
        self.length = reader.read_u8(3) + 1
        self.shift = 32 - self.length - self.encoded_shift
        self.data = reader.read_u32(4)


class G_TEXRECT:
    __slots__ = ("_raw_data", "opcode", "lrx", "lry", "tile", "ulx", "uly")

    def __repr__(self):
        return f"G_TEXRECT({self.ulx}, {self.uly}, {self.lrx}, {self.lry}, {self.tile})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.lrx, self.lry, self.tile, self.ulx, self.uly = (
            _decode_textured_rectangle(reader)
        )


class G_TEXRECTFLIP:
    __slots__ = ("_raw_data", "opcode", "lrx", "lry", "tile", "ulx", "uly")

    def __repr__(self):
        return f"G_TEXRECTFLIP({self.ulx}, {self.uly}, {self.lrx}, {self.lry}, {self.tile})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.lrx, self.lry, self.tile, self.ulx, self.uly = (
            _decode_textured_rectangle(reader)
        )


class G_RDPLOADSYNC(_NoPayloadCommand):
    __slots__ = ()

    def __repr__(self):
        return f"G_RDPLOADSYNC()"


class G_RDPPIPESYNC(_NoPayloadCommand):
    __slots__ = ()

    def __repr__(self):
        return f"G_RDPPIPESYNC()"


class G_RDPTILESYNC(_NoPayloadCommand):
    __slots__ = ()

    def __repr__(self):
        return f"G_RDPTILESYNC()"


class G_RDPFULLSYNC(_NoPayloadCommand):
    __slots__ = ()

    def __repr__(self):
        return f"G_RDPFULLSYNC()"


class G_SETKEYGB:
    __slots__ = (
        "_raw_data",
        "opcode",
        "width_g",
        "width_b",
        "center_g",
        "scale_g",
        "center_b",
        "scale_b",
    )

    def __repr__(self):
        return (
            "G_SETKEYGB("
            f"{self.center_g}, {self.scale_g}, {self.width_g}, "
            f"{self.center_b}, {self.scale_b}, {self.width_b})"
        )

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        word0 = reader.read_u32(0)
        self.width_g = (word0 >> 12) & 0xFFF
        self.width_b = word0 & 0xFFF
        self.center_g = reader.read_u8(4)
        self.scale_g = reader.read_u8(5)
        self.center_b = reader.read_u8(6)
        self.scale_b = reader.read_u8(7)


class G_SETKEYR:
    __slots__ = ("_raw_data", "opcode", "width_r", "center_r", "scale_r")

    def __repr__(self):
        return f"G_SETKEYR({self.center_r}, {self.scale_r}, {self.width_r})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        word1 = reader.read_u32(4)
        self.width_r = (word1 >> 16) & 0xFFF
        self.center_r = reader.read_u8(6)
        self.scale_r = reader.read_u8(7)


class G_SETCONVERT:
    __slots__ = ("_raw_data", "opcode", "k0", "k1", "k2", "k3", "k4", "k5")

    def __repr__(self):
        return f"G_SETCONVERT({self.k0}, {self.k1}, {self.k2}, {self.k3}, {self.k4}, {self.k5})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        word0, word1 = _word_pair(reader)
        self.k0 = _sign_extend((word0 >> 13) & 0x1FF, 9)
        self.k1 = _sign_extend((word0 >> 4) & 0x1FF, 9)
        self.k2 = _sign_extend(((word0 & 0xF) << 5) | ((word1 >> 27) & 0x1F), 9)
        self.k3 = _sign_extend((word1 >> 18) & 0x1FF, 9)
        self.k4 = _sign_extend((word1 >> 9) & 0x1FF, 9)
        self.k5 = _sign_extend(word1 & 0x1FF, 9)


class G_SETSCISSOR:
    __slots__ = ("_raw_data", "opcode", "ulx", "uly", "mode", "lrx", "lry")

    def __repr__(self):
        return f"G_SETSCISSOR({self.mode}, {self.ulx}, {self.uly}, {self.lrx}, {self.lry})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        word0, word1 = _word_pair(reader)
        self.ulx, self.uly = _packed_coordinate_pair(word0)
        self.mode = (word1 >> 24) & 0x3
        self.lrx, self.lry = _packed_coordinate_pair(word1)


class G_SETPRIMDEPTH:
    __slots__ = ("_raw_data", "opcode", "z", "dz")

    def __repr__(self):
        return f"G_SETPRIMDEPTH({self.z}, {self.dz})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.z = reader.read_i16(4)
        self.dz = reader.read_i16(6)


class G_RDPSetOtherMode:
    __slots__ = ("_raw_data", "opcode", "other_mode_h", "other_mode_l")

    def __repr__(self):
        return f"G_RDPSetOtherMode(0x{self.other_mode_h:06x}, 0x{self.other_mode_l:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        word0, self.other_mode_l = _word_pair(reader)
        self.other_mode_h = word0 & 0x00FFFFFF


class G_LOADTLUT:
    __slots__ = ("_raw_data", "opcode", "tile", "count", "color_count")

    def __repr__(self):
        return f"G_LOADTLUT({self.tile}, {self.count})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        word1 = reader.read_u32(4)
        self.tile = (word1 >> 24) & 0x7
        self.count = ((word1 >> 12) & 0xFFF) >> 2
        self.color_count = self.count + 1


class G_RDPHALF_2:
    __slots__ = ("_raw_data", "opcode", "word")

    def __repr__(self):
        return f"G_RDPHALF_2(0x{self.word:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.word = reader.read_u32(4)


class G_SETTILESIZE:
    __slots__ = ("_raw_data", "opcode", "uls", "ult", "tile", "lrs", "lrt")

    def __repr__(self):
        return f"G_SETTILESIZE({self.tile}, {self.uls}, {self.ult}, {self.lrs}, {self.lrt})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.uls, self.ult, self.tile, self.lrs, self.lrt = (
            _decode_tile_coordinates(reader)
        )


class G_LOADBLOCK:
    __slots__ = ("_raw_data", "opcode", "uls", "ult", "tile", "texels", "texel_count", "dxt")

    def __repr__(self):
        return f"G_LOADBLOCK({self.tile}, {self.uls}, {self.ult}, {self.texels}, {self.dxt})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        word0, word1 = _word_pair(reader)
        self.uls, self.ult = _packed_coordinate_pair(word0)
        self.tile = (word1 >> 24) & 0x7
        self.texels = (word1 >> 12) & 0xFFF
        self.texel_count = self.texels + 1
        self.dxt = word1 & 0xFFF


class G_LOADTILE:
    __slots__ = ("_raw_data", "opcode", "uls", "ult", "tile", "lrs", "lrt")

    def __repr__(self):
        return f"G_LOADTILE({self.tile}, {self.uls}, {self.ult}, {self.lrs}, {self.lrt})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.uls, self.ult, self.tile, self.lrs, self.lrt = (
            _decode_tile_coordinates(reader)
        )


class G_SETTILE:
    __slots__ = (
        "_raw_data",
        "opcode",
        "fmt",
        "size",
        "line",
        "tmem",
        "tile",
        "palette",
        "cm_t",
        "mask_t",
        "shift_t",
        "cm_s",
        "mask_s",
        "shift_s",
    )

    def __repr__(self):
        return f"G_SETTILE({self.tile}, {self.fmt}, {self.size}, {self.line}, {self.tmem})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        word0, word1 = _word_pair(reader)
        self.fmt = (word0 >> 21) & 0x7
        self.size = (word0 >> 19) & 0x3
        self.line = (word0 >> 9) & 0x1FF
        self.tmem = word0 & 0x1FF
        self.tile = (word1 >> 24) & 0x7
        self.palette = (word1 >> 20) & 0xF
        self.cm_t = (word1 >> 18) & 0x3
        self.mask_t = (word1 >> 14) & 0xF
        self.shift_t = (word1 >> 10) & 0xF
        self.cm_s = (word1 >> 8) & 0x3
        self.mask_s = (word1 >> 4) & 0xF
        self.shift_s = word1 & 0xF


class G_FILLRECT:
    __slots__ = ("_raw_data", "opcode", "lrx", "lry", "ulx", "uly")

    def __repr__(self):
        return f"G_FILLRECT({self.ulx}, {self.uly}, {self.lrx}, {self.lry})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.lrx, self.lry, self.ulx, self.uly = _decode_fill_rectangle(reader)


class G_SETFILLCOLOR:
    __slots__ = ("_raw_data", "opcode", "color")

    def __repr__(self):
        return f"G_SETFILLCOLOR(0x{self.color:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.color = reader.read_u32(4)


class G_SETFOGCOLOR:
    __slots__ = ("_raw_data", "opcode", "r", "g", "b", "a")

    def __repr__(self):
        return f"G_SETFOGCOLOR({self.r}, {self.g}, {self.b}, {self.a})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.r, self.g, self.b, self.a = _decode_rgba(reader)


class G_SETBLENDCOLOR:
    __slots__ = ("_raw_data", "opcode", "r", "g", "b", "a")

    def __repr__(self):
        return f"G_SETBLENDCOLOR({self.r}, {self.g}, {self.b}, {self.a})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.r, self.g, self.b, self.a = _decode_rgba(reader)


class G_SETPRIMCOLOR:
    __slots__ = (
        "_raw_data",
        "opcode",
        "min_level",
        "lod_fraction",
        "r",
        "g",
        "b",
        "a",
    )

    def __repr__(self):
        return (
            "G_SETPRIMCOLOR("
            f"{self.min_level}, {self.lod_fraction}, {self.r}, "
            f"{self.g}, {self.b}, {self.a})"
        )

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.min_level = reader.read_u8(2)
        self.lod_fraction = reader.read_u8(3)
        self.r, self.g, self.b, self.a = _decode_rgba(reader)


class G_SETENVCOLOR:
    __slots__ = ("_raw_data", "opcode", "r", "g", "b", "a")

    def __repr__(self):
        return f"G_SETENVCOLOR({self.r}, {self.g}, {self.b}, {self.a})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.r, self.g, self.b, self.a = _decode_rgba(reader)


class G_SETCOMBINE:
    __slots__ = (
        "_raw_data",
        "opcode",
        "color_a_0",
        "color_b_0",
        "color_c_0",
        "color_d_0",
        "alpha_a_0",
        "alpha_b_0",
        "alpha_c_0",
        "alpha_d_0",
        "color_a_1",
        "color_b_1",
        "color_c_1",
        "color_d_1",
        "alpha_a_1",
        "alpha_b_1",
        "alpha_c_1",
        "alpha_d_1",
    )

    def __repr__(self):
        return (
            "G_SETCOMBINE("
            f"({self.color_a_0}, {self.color_b_0}, {self.color_c_0}, {self.color_d_0}), "
            f"({self.color_a_1}, {self.color_b_1}, {self.color_c_1}, {self.color_d_1}))"
        )

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        word0, word1 = _word_pair(reader)
        self.color_a_0 = (word0 >> 20) & 0xF
        self.color_c_0 = (word0 >> 15) & 0x1F
        self.alpha_a_0 = (word0 >> 12) & 0x7
        self.alpha_c_0 = (word0 >> 9) & 0x7
        self.color_a_1 = (word0 >> 5) & 0xF
        self.color_c_1 = word0 & 0x1F
        self.color_b_0 = (word1 >> 28) & 0xF
        self.color_b_1 = (word1 >> 24) & 0xF
        self.alpha_a_1 = (word1 >> 21) & 0x7
        self.alpha_c_1 = (word1 >> 18) & 0x7
        self.color_d_0 = (word1 >> 15) & 0x7
        self.alpha_b_0 = (word1 >> 12) & 0x7
        self.alpha_d_0 = (word1 >> 9) & 0x7
        self.color_d_1 = (word1 >> 6) & 0x7
        self.alpha_b_1 = (word1 >> 3) & 0x7
        self.alpha_d_1 = word1 & 0x7


class G_SETTIMG:
    __slots__ = ("_raw_data", "opcode", "fmt", "size", "width", "address")

    def __repr__(self):
        return f"G_SETTIMG({self.fmt}, {self.size}, {self.width}, 0x{self.address:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.fmt, self.size, self.width, self.address = _decode_image(reader)


class G_SETZIMG:
    __slots__ = ("_raw_data", "opcode", "address")

    def __repr__(self):
        return f"G_SETZIMG(0x{self.address:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.address = reader.read_u32(4)


class G_SETCIMG:
    __slots__ = ("_raw_data", "opcode", "fmt", "size", "width", "address")

    def __repr__(self):
        return f"G_SETCIMG({self.fmt}, {self.size}, {self.width}, 0x{self.address:08x})"

    def __init__(self, command: bytes):
        reader = _init_command(self, command)
        self.fmt, self.size, self.width, self.address = _decode_image(reader)


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


def get_command(command_bytes: bytes) -> DL_Command | None:
    command_type = DL_COMMANDS.get(command_bytes[:1])
    if command_type is None:
        return None
    return command_type(command_bytes)
