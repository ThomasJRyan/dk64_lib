import unittest
from dataclasses import FrozenInstanceError

from dk64_lib.f3dex2.display_list import DisplayListChunkData, DisplayListExpansion


def u32(value: int) -> bytes:
    return value.to_bytes(4, "big")


class DisplayListExpansionTest(unittest.TestCase):
    def test_from_bytes(self):
        expansion = DisplayListExpansion.from_bytes(
            u32(0x01020304) + u32(0x11121314) + u32(0x00000080) + u32(0x21222324)
        )

        self.assertEqual(expansion.unknown_1, 0x01020304)
        self.assertEqual(expansion.unknown_2, 0x11121314)
        self.assertEqual(expansion.display_list_offset, 0x80)
        self.assertEqual(expansion.unknown_4, 0x21222324)

    def test_is_frozen(self):
        expansion = DisplayListExpansion.from_bytes(bytes(0x10))

        with self.assertRaises(FrozenInstanceError):
            expansion.display_list_offset = 1


class DisplayListChunkDataTest(unittest.TestCase):
    def test_from_bytes(self):
        chunk = DisplayListChunkData.from_bytes(
            bytes((0x11, 0x22, 0x33, 0x44))
            + b"\xaa\xbb\xcc\xdd"
            + b"".join(
                u32(value)
                for value in (
                    0x01020304,
                    0x10,
                    0x20,
                    0x30,
                    0x40,
                    0x50,
                    0x60,
                    0x70,
                    0x80,
                    0x90,
                    0xA0,
                )
            )
        )

        self.assertEqual(chunk.r, 0x11)
        self.assertEqual(chunk.g, 0x22)
        self.assertEqual(chunk.b, 0x33)
        self.assertEqual(chunk.unknown_char, 0x44)
        self.assertEqual(chunk.mips_instruction, b"\xaa\xbb\xcc\xdd")
        self.assertEqual(chunk.unknown_flag, 0x01020304)
        self.assertEqual(chunk.dl_1_start, 0x10)
        self.assertEqual(chunk.dl_1_size, 0x20)
        self.assertEqual(chunk.dl_2_start, 0x30)
        self.assertEqual(chunk.dl_2_size, 0x40)
        self.assertEqual(chunk.dl_3_start, 0x50)
        self.assertEqual(chunk.dl_3_size, 0x60)
        self.assertEqual(chunk.dl_4_start, 0x70)
        self.assertEqual(chunk.dl_4_size, 0x80)
        self.assertEqual(chunk.vertex_start, 0x90)
        self.assertEqual(chunk.vertex_size, 0xA0)

    def test_vertex_start_size(self):
        chunk = DisplayListChunkData(
            r=0,
            g=0,
            b=0,
            unknown_char=0,
            mips_instruction=b"\x00\x00\x00\x00",
            unknown_flag=0,
            dl_1_start=0x10,
            dl_1_size=0,
            dl_2_start=0x20,
            dl_2_size=0,
            dl_3_start=0x30,
            dl_3_size=0,
            dl_4_start=0x40,
            dl_4_size=0,
            vertex_start=0x100,
            vertex_size=0x200,
        )

        self.assertEqual(
            chunk.vertex_start_size,
            {
                0x10: (0x100, 0x200),
                0x20: (0x100, 0x200),
                0x30: (0x100, 0x200),
                0x40: (0x100, 0x200),
            },
        )

    def test_is_frozen(self):
        chunk = DisplayListChunkData.from_bytes(bytes(52))

        with self.assertRaises(FrozenInstanceError):
            chunk.vertex_size = 1


if __name__ == "__main__":
    unittest.main()
