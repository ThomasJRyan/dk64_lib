import unittest

from dk64_lib.binary_reader import BinaryReader


class BinaryReaderTest(unittest.TestCase):
    def setUp(self):
        self.reader = BinaryReader(b"\x01\x02\xff\xfe\x10\x20\x30\x40")

    def test_read_bytes_at_offset(self):
        self.assertEqual(self.reader.read_at(1, 3), b"\x02\xff\xfe")

    def test_slice_at_offset(self):
        self.assertEqual(self.reader.slice(4, 2).tobytes(), b"\x10\x20")

    def test_read_big_endian_numbers(self):
        self.assertEqual(self.reader.read_u8(0), 0x01)
        self.assertEqual(self.reader.read_u16(0), 0x0102)
        self.assertEqual(self.reader.read_i16(2), -2)
        self.assertEqual(self.reader.read_u32(4), 0x10203040)

    def test_rejects_negative_offsets_and_sizes(self):
        with self.assertRaises(ValueError):
            self.reader.read_at(-1, 1)
        with self.assertRaises(ValueError):
            self.reader.read_at(0, -1)

    def test_rejects_reads_past_end(self):
        with self.assertRaises(ValueError):
            self.reader.read_at(7, 2)


if __name__ == "__main__":
    unittest.main()
