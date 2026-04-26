import unittest

from dk64_lib.f3dex2 import commands


def _words(word0: int, word1: int) -> bytes:
    return word0.to_bytes(4, "big") + word1.to_bytes(4, "big")


def _signed_9(value: int) -> int:
    return value & 0x1FF


class DisplayListCommandTest(unittest.TestCase):
    def test_vtx_decodes_fields(self):
        command = commands.G_VTX(b"\x01\x00\x40\x10\x06\x00\x12\x34")

        self.assertEqual(command.opcode, b"\x01")
        self.assertEqual(command.vertex_count, 4)
        self.assertEqual(command.buffer_start, 8)
        self.assertEqual(command.segment, b"\x06")
        self.assertEqual(command.address, b"\x00\x12\x34")

    def test_modifyvtx_decodes_fields(self):
        command = commands.G_MODIFYVTX(b"\x02\x14\x00\x08\x11\x22\x33\x44")

        self.assertEqual(command.where, 0x14)
        self.assertEqual(command.vertex_index, 4)
        self.assertEqual(command.value, 0x11223344)

    def test_culldl_decodes_vertex_range(self):
        command = commands.G_CULLDL(b"\x03\x00\x00\x04\x00\x00\x00\x0a")

        self.assertEqual(command.vfirst, 2)
        self.assertEqual(command.vlast, 5)

    def test_branch_z_decodes_vertex_fields_and_depth(self):
        command = commands.G_BRANCH_Z(b"\x04\x02\x30\x0e\x00\x01\x00\x00")

        self.assertEqual(command.vertex_index_a, 7)
        self.assertEqual(command.vertex_index_b, 7)
        self.assertEqual(command.z_value, 0x00010000)

    def test_tri1_decodes_vertex_indices(self):
        command = commands.G_TRI1(b"\x05\x02\x04\x06\x00\x00\x00\x00")

        self.assertEqual(command.opcode, b"\x05")
        self.assertEqual((command.v1, command.v2, command.v3), (1, 2, 3))

    def test_tri2_decodes_vertex_indices(self):
        command = commands.G_TRI2(b"\x06\x02\x04\x06\x00\x08\x0a\x0c")

        self.assertEqual(command.opcode, b"\x06")
        self.assertEqual(
            (command.v1, command.v2, command.v3, command.v4, command.v5, command.v6),
            (1, 2, 3, 4, 5, 6),
        )

    def test_quad_decodes_vertex_indices(self):
        command = commands.G_QUAD(b"\x07\x02\x04\x06\x00\x02\x06\x08")

        self.assertEqual(
            (
                command.v1,
                command.v2,
                command.v3,
                command.v4,
                command.v1_duplicate,
                command.v3_duplicate,
            ),
            (1, 2, 3, 4, 1, 3),
        )

    def test_dma_io_decodes_transfer_fields(self):
        command = commands.G_DMA_IO(_words(0xD6848023, 0x12345678))

        self.assertEqual(command.flag, 1)
        self.assertEqual(command.dmem, 0x120)
        self.assertEqual(command.size, 0x24)
        self.assertEqual(command.dram, 0x12345678)

    def test_texture_decodes_descriptor_fields(self):
        command = commands.G_TEXTURE(b"\xd7\x00\x2b\x02\x80\x00\x40\x00")

        self.assertEqual(command.level, 5)
        self.assertEqual(command.tile, 3)
        self.assertEqual(command.on, 1)
        self.assertEqual(command.scale_s, 0x8000)
        self.assertEqual(command.scale_t, 0x4000)

    def test_popmtx_decodes_matrix_count(self):
        command = commands.G_POPMTX(_words(0xD8380002, 0x000000C0))

        self.assertEqual(command.num_matrices, 3)

    def test_geometrymode_decodes_clear_and_set_bits(self):
        command = commands.G_GEOMETRYMODE(_words(0xD9FFFFFC, 0x00002000))

        self.assertEqual(command.clear_bits, 0x000003)
        self.assertEqual(command.set_bits, 0x00002000)

    def test_mtx_decodes_params_and_address(self):
        command = commands.G_MTX(_words(0xDA380004, 0x06001234))

        self.assertEqual(command.params, 0x05)
        self.assertEqual(command.address, 0x06001234)

    def test_moveword_decodes_index_offset_and_data(self):
        command = commands.G_MOVEWORD(_words(0xDB060002, 0x80000000))

        self.assertEqual(command.index, 0x06)
        self.assertEqual(command.offset, 0x0002)
        self.assertEqual(command.data, 0x80000000)

    def test_movemem_decodes_size_offset_index_and_address(self):
        command = commands.G_MOVEMEM(_words(0xDC10040A, 0x12345678))

        self.assertEqual(command.size, 24)
        self.assertEqual(command.offset, 32)
        self.assertEqual(command.index, 0x0A)
        self.assertEqual(command.address, 0x12345678)

    def test_load_ucode_decodes_size_and_text_start(self):
        command = commands.G_LOAD_UCODE(_words(0xDD000180, 0x80200000))

        self.assertEqual(command.data_size, 0x0180)
        self.assertEqual(command.text_start, 0x80200000)

    def test_dl_decodes_branch_target(self):
        command = commands.G_DL(b"\xde\x00\x00\x00\x07\x00\x01\x20")

        self.assertEqual(command.opcode, b"\xde")
        self.assertTrue(command.store_return_address)
        self.assertEqual(command.segment, b"\x07")
        self.assertEqual(command.address, b"\x00\x01\x20")

    def test_dl_decodes_no_return_address(self):
        command = commands.G_DL(b"\xde\x01\x00\x00\x07\x00\x01\x20")

        self.assertFalse(command.store_return_address)

    def test_enddl_decodes_opcode(self):
        command = commands.G_ENDDL(b"\xdf\x00\x00\x00\x00\x00\x00\x00")

        self.assertEqual(command.opcode, b"\xdf")

    def test_rdphalf_commands_decode_words(self):
        command_1 = commands.G_RDPHALF_1(_words(0xE1000000, 0x11223344))
        command_2 = commands.G_RDPHALF_2(_words(0xF1000000, 0x55667788))

        self.assertEqual(command_1.word, 0x11223344)
        self.assertEqual(command_2.word, 0x55667788)

    def test_other_mode_commands_decode_shift_length_and_data(self):
        command_l = commands.G_SetOtherMode_L(_words(0xE2001804, 0x00000018))
        command_h = commands.G_SetOtherMode_H(_words(0xE3000A01, 0x00300000))

        self.assertEqual(command_l.encoded_shift, 24)
        self.assertEqual(command_l.shift, 3)
        self.assertEqual(command_l.length, 5)
        self.assertEqual(command_l.data, 0x00000018)
        self.assertEqual(command_h.encoded_shift, 10)
        self.assertEqual(command_h.shift, 20)
        self.assertEqual(command_h.length, 2)
        self.assertEqual(command_h.data, 0x00300000)

    def test_texture_rectangles_decode_coordinates(self):
        command = commands.G_TEXRECT(_words(0xE4123456, 0x0507809A))
        flipped = commands.G_TEXRECTFLIP(_words(0xE5123456, 0x0507809A))

        for parsed in (command, flipped):
            self.assertEqual(parsed.lrx, 0x123)
            self.assertEqual(parsed.lry, 0x456)
            self.assertEqual(parsed.tile, 5)
            self.assertEqual(parsed.ulx, 0x078)
            self.assertEqual(parsed.uly, 0x09A)

    def test_key_commands_decode_chroma_key_fields(self):
        command_gb = commands.G_SETKEYGB(_words(0xEA123456, 0x10203040))
        command_r = commands.G_SETKEYR(_words(0xEB000000, 0x0ABC3456))

        self.assertEqual(command_gb.width_g, 0x123)
        self.assertEqual(command_gb.width_b, 0x456)
        self.assertEqual(command_gb.center_g, 0x10)
        self.assertEqual(command_gb.scale_g, 0x20)
        self.assertEqual(command_gb.center_b, 0x30)
        self.assertEqual(command_gb.scale_b, 0x40)
        self.assertEqual(command_r.width_r, 0xABC)
        self.assertEqual(command_r.center_r, 0x34)
        self.assertEqual(command_r.scale_r, 0x56)

    def test_setconvert_decodes_signed_terms(self):
        fields = [1, -1, 255, -256, 0, 128]
        packed = (
            (0xEC << 56)
            | (_signed_9(fields[0]) << 45)
            | (_signed_9(fields[1]) << 36)
            | (_signed_9(fields[2]) << 27)
            | (_signed_9(fields[3]) << 18)
            | (_signed_9(fields[4]) << 9)
            | _signed_9(fields[5])
        )
        command = commands.G_SETCONVERT(packed.to_bytes(8, "big"))

        self.assertEqual(
            (command.k0, command.k1, command.k2, command.k3, command.k4, command.k5),
            tuple(fields),
        )

    def test_setscissor_decodes_mode_and_coordinates(self):
        command = commands.G_SETSCISSOR(_words(0xED010020, 0x02300400))

        self.assertEqual(command.ulx, 0x010)
        self.assertEqual(command.uly, 0x020)
        self.assertEqual(command.mode, 2)
        self.assertEqual(command.lrx, 0x300)
        self.assertEqual(command.lry, 0x400)

    def test_primdepth_and_rdp_other_mode_decode_fields(self):
        depth = commands.G_SETPRIMDEPTH(b"\xee\x00\x00\x00\xff\xfe\x00\x04")
        other_mode = commands.G_RDPSetOtherMode(_words(0xEF123456, 0x89ABCDEF))

        self.assertEqual(depth.z, -2)
        self.assertEqual(depth.dz, 4)
        self.assertEqual(other_mode.other_mode_h, 0x123456)
        self.assertEqual(other_mode.other_mode_l, 0x89ABCDEF)

    def test_texture_load_commands_decode_tile_fields(self):
        tlut = commands.G_LOADTLUT(_words(0xF0000000, 0x03044000))
        tile_size = commands.G_SETTILESIZE(_words(0xF2011022, 0x04033044))
        load_block = commands.G_LOADBLOCK(_words(0xF3001002, 0x06100080))
        load_tile = commands.G_LOADTILE(_words(0xF4011022, 0x04033044))

        self.assertEqual(tlut.tile, 3)
        self.assertEqual(tlut.count, 17)
        self.assertEqual(tlut.color_count, 18)
        self.assertEqual(
            (tile_size.uls, tile_size.ult, tile_size.tile, tile_size.lrs, tile_size.lrt),
            (0x011, 0x022, 4, 0x033, 0x044),
        )
        self.assertEqual(
            (
                load_block.uls,
                load_block.ult,
                load_block.tile,
                load_block.texels,
                load_block.texel_count,
                load_block.dxt,
            ),
            (0x001, 0x002, 6, 0x100, 0x101, 0x080),
        )
        self.assertEqual(
            (load_tile.uls, load_tile.ult, load_tile.tile, load_tile.lrs, load_tile.lrt),
            (0x011, 0x022, 4, 0x033, 0x044),
        )

    def test_settile_decodes_descriptor_fields(self):
        command = commands.G_SETTILE(_words(0xF590AAAA, 0x0569E19A))

        self.assertEqual(command.fmt, 4)
        self.assertEqual(command.size, 2)
        self.assertEqual(command.line, 0x55)
        self.assertEqual(command.tmem, 0xAA)
        self.assertEqual(command.tile, 5)
        self.assertEqual(command.palette, 6)
        self.assertEqual(command.cm_t, 2)
        self.assertEqual(command.mask_t, 7)
        self.assertEqual(command.shift_t, 8)
        self.assertEqual(command.cm_s, 1)
        self.assertEqual(command.mask_s, 9)
        self.assertEqual(command.shift_s, 0xA)

    def test_fillrect_and_fillcolor_decode_fields(self):
        rect = commands.G_FILLRECT(_words(0xF6123456, 0x0007809A))
        color = commands.G_SETFILLCOLOR(_words(0xF7000000, 0xDEADBEEF))

        self.assertEqual((rect.lrx, rect.lry, rect.ulx, rect.uly), (0x123, 0x456, 0x078, 0x09A))
        self.assertEqual(color.color, 0xDEADBEEF)

    def test_color_commands_decode_rgba_fields(self):
        fog = commands.G_SETFOGCOLOR(b"\xf8\x00\x00\x00\x10\x20\x30\x40")
        blend = commands.G_SETBLENDCOLOR(b"\xf9\x00\x00\x00\x50\x60\x70\x80")
        prim = commands.G_SETPRIMCOLOR(b"\xfa\x00\x01\x02\x90\xa0\xb0\xc0")
        env = commands.G_SETENVCOLOR(b"\xfb\x00\x00\x00\xd0\xe0\xf0\xff")

        self.assertEqual((fog.r, fog.g, fog.b, fog.a), (0x10, 0x20, 0x30, 0x40))
        self.assertEqual((blend.r, blend.g, blend.b, blend.a), (0x50, 0x60, 0x70, 0x80))
        self.assertEqual(prim.min_level, 1)
        self.assertEqual(prim.lod_fraction, 2)
        self.assertEqual((prim.r, prim.g, prim.b, prim.a), (0x90, 0xA0, 0xB0, 0xC0))
        self.assertEqual((env.r, env.g, env.b, env.a), (0xD0, 0xE0, 0xF0, 0xFF))

    def test_setcombine_decodes_combiner_fields(self):
        word0 = (
            0xFC000000
            | (1 << 20)
            | (2 << 15)
            | (3 << 12)
            | (4 << 9)
            | (5 << 5)
            | 5
        )
        word1 = (
            (7 << 28)
            | (8 << 24)
            | (1 << 21)
            | (2 << 18)
            | (3 << 15)
            | (4 << 12)
            | (5 << 9)
            | (6 << 6)
            | (7 << 3)
        )
        command = commands.G_SETCOMBINE(_words(word0, word1))

        self.assertEqual(
            (
                command.color_a_0,
                command.color_b_0,
                command.color_c_0,
                command.color_d_0,
                command.alpha_a_0,
                command.alpha_b_0,
                command.alpha_c_0,
                command.alpha_d_0,
            ),
            (1, 7, 2, 3, 3, 4, 4, 5),
        )
        self.assertEqual(
            (
                command.color_a_1,
                command.color_b_1,
                command.color_c_1,
                command.color_d_1,
                command.alpha_a_1,
                command.alpha_b_1,
                command.alpha_c_1,
                command.alpha_d_1,
            ),
            (5, 8, 5, 6, 1, 7, 2, 0),
        )

    def test_image_commands_decode_format_size_width_and_address(self):
        texture = commands.G_SETTIMG(_words(0xFD580100, 0x06001234))
        depth = commands.G_SETZIMG(_words(0xFE000000, 0x80300000))
        color = commands.G_SETCIMG(_words(0xFF70027F, 0x80400000))

        self.assertEqual((texture.fmt, texture.size, texture.width), (2, 3, 257))
        self.assertEqual(texture.address, 0x06001234)
        self.assertEqual(depth.address, 0x80300000)
        self.assertEqual((color.fmt, color.size, color.width), (3, 2, 640))
        self.assertEqual(color.address, 0x80400000)

    def test_get_command_uses_opcode_registry(self):
        command = commands.get_command(b"\x05\x02\x04\x06\x00\x00\x00\x00")

        self.assertIsInstance(command, commands.G_TRI1)

    def test_registered_commands_parse_minimal_buffers(self):
        for opcode, command_type in commands.DL_COMMANDS.items():
            with self.subTest(opcode=opcode.hex()):
                command = commands.get_command(opcode + bytes(7))

                self.assertIsInstance(command, command_type)


if __name__ == "__main__":
    unittest.main()
