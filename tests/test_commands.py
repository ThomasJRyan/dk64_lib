import unittest

from dk64_lib.f3dex2.commands import G_DL, G_ENDDL, G_TRI1, G_TRI2, G_VTX, get_command


class DisplayListCommandTest(unittest.TestCase):
    def test_vtx_decodes_fields(self):
        command = G_VTX(b"\x01\x00\x40\x10\x06\x00\x12\x34")

        self.assertEqual(command.opcode, b"\x01")
        self.assertEqual(command.vertex_count, 4)
        self.assertEqual(command.buffer_start, 8)
        self.assertEqual(command.segment, b"\x06")
        self.assertEqual(command.address, b"\x00\x12\x34")

    def test_tri1_decodes_vertex_indices(self):
        command = G_TRI1(b"\x05\x02\x04\x06\x00\x00\x00\x00")

        self.assertEqual(command.opcode, b"\x05")
        self.assertEqual((command.v1, command.v2, command.v3), (1, 2, 3))

    def test_tri2_decodes_vertex_indices(self):
        command = G_TRI2(b"\x06\x02\x04\x06\x00\x08\x0a\x0c")

        self.assertEqual(command.opcode, b"\x06")
        self.assertEqual(
            (command.v1, command.v2, command.v3, command.v4, command.v5, command.v6),
            (1, 2, 3, 4, 5, 6),
        )

    def test_dl_decodes_branch_target(self):
        command = G_DL(b"\xde\x00\x00\x00\x07\x00\x01\x20")

        self.assertEqual(command.opcode, b"\xde")
        self.assertTrue(command.store_return_address)
        self.assertEqual(command.segment, b"\x07")
        self.assertEqual(command.address, b"\x00\x01\x20")

    def test_dl_decodes_no_return_address(self):
        command = G_DL(b"\xde\x01\x00\x00\x07\x00\x01\x20")

        self.assertFalse(command.store_return_address)

    def test_enddl_decodes_opcode(self):
        command = G_ENDDL(b"\xdf\x00\x00\x00\x00\x00\x00\x00")

        self.assertEqual(command.opcode, b"\xdf")

    def test_get_command_uses_opcode_registry(self):
        command = get_command(b"\x05\x02\x04\x06\x00\x00\x00\x00")

        self.assertIsInstance(command, G_TRI1)


if __name__ == "__main__":
    unittest.main()
