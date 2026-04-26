import os
import glob
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from dk64_lib.data_types import CutsceneData
from dk64_lib.rom import Rom, TableEntry
from dk64_lib.file_io import get_bytes, get_char, get_long, get_short


def get_rom() -> Rom:
    rom_glob = glob.glob(str(Path(os.path.dirname(__file__)) / "dk64_rom" / "*.*"))
    # TODO: At the moment, we are only testing a single version (US specifically)
    # TODO: This should be updated to test all versions of DK64
    return [Rom(rom) for rom in rom_glob][0]


class RomTest(unittest.TestCase):
    def setUp(self):
        self.rom = get_rom()

    def test_release_or_kiosk(self):
        self.assertIn(self.rom.release_or_kiosk, ["release", "kiosk"])

    def test_region(self):
        self.assertIn(self.rom.region, ["us", "pal", "jp", "kiosk"])

    def test_pointer_table_offset(self):
        self.assertIn(
            self.rom.pointer_table_offset, [0x101C50, 0x1038D0, 0x1039C0, 0x1A7C20]
        )

    def test_text_lines(self):
        self.assertEqual(
            self.rom.text_tables[0].text_lines[0].text, "WELCOME TO THE BONUS STAGE!"
        )
        self.assertEqual(
            self.rom.text_tables[-1].text_lines[-1].text, "HOW ABOUT ANOTHER GAME?"
        )

    def test_cutscene_data(self):
        cutscene_data = self.rom.get_cutscene_data()

        self.assertEqual(len(cutscene_data), 221)
        self.assertIsInstance(cutscene_data[0], CutsceneData)
        self.assertEqual(cutscene_data[0].data_type, "Cutscene")

    def test_geometry_texture_data_uses_geometry_texture_table(self):
        texture_data = self.rom.get_geometry_texture_data()

        self.assertEqual(len(texture_data), 6011)
        self.assertEqual(texture_data[0].offset, 18429500)

    def test_geometry_data(self):
        self.assertEqual(len(self.rom.geometry_tables), 216)

        geometry_table = self.rom.geometry_tables[0]
        self.assertEqual(geometry_table.offset, 1386148)
        self.assertEqual(geometry_table.size, 930)
        self.assertEqual(len(geometry_table.display_lists), 2)

        geometry_table = self.rom.geometry_tables[20]
        self.assertEqual(geometry_table.offset, 1988678)
        self.assertEqual(geometry_table.size, 31532)
        self.assertEqual(len(geometry_table.display_lists), 33)

        geometry_table = self.rom.geometry_tables[-1]
        self.assertEqual(geometry_table.offset, 4443108)
        self.assertEqual(geometry_table.size, 8)
        self.assertEqual(len(geometry_table.display_lists), 0)

    def test_geometry_table_entries(self):
        table_offset = 1
        table_size = get_long(
            self.rom.rom_fh,
            self.rom.pointer_table_offset + (32 * 4) + (table_offset * 4),
        )
        table_start = self.rom.pointer_table_offset + get_long(
            self.rom.rom_fh, self.rom.pointer_table_offset + (table_offset * 4)
        )
        entries = self.rom._read_table_entries(table_start, table_size)
        nonempty_entries = [entry for entry in entries if not entry.is_empty]

        self.assertEqual(len(entries), 221)
        self.assertEqual(len(nonempty_entries), 216)
        self.assertIsInstance(entries[0], TableEntry)
        self.assertEqual(entries[0].index, 0)
        self.assertEqual(entries[0].start, 1386148)
        self.assertEqual(entries[0].size, 930)
        self.assertEqual(nonempty_entries[-1].start, 4443108)
        self.assertEqual(nonempty_entries[-1].size, 8)

    def test_rom_table_data_can_be_generated_multiple_times(self):
        first_pass = list(self.rom.generate_rom_table_data([1]))
        second_pass = list(self.rom.generate_rom_table_data([1]))

        self.assertEqual(len(first_pass), 216)
        self.assertEqual(len(second_pass), 216)
        self.assertEqual(first_pass[0]["offset"], second_pass[0]["offset"])
        self.assertEqual(first_pass[-1]["offset"], second_pass[-1]["offset"])

    def test_geometry_dae_export(self):
        geometry_table = self.rom.geometry_tables[0]
        dae = geometry_table.create_dae()

        self.assertEqual(len(dae.geometries), 1)
        self.assertEqual(len(dae.geometries[0].primitives), 1)

        with TemporaryDirectory() as temp_dir:
            geometry_table.save_to_dae("0.dae", temp_dir)
            dae_path = Path(temp_dir) / "0.dae"
            self.assertTrue(dae_path.exists())
            self.assertGreater(dae_path.stat().st_size, 0)


class FileIOTest(unittest.TestCase):
    def setUp(self):
        self.rom = get_rom()

    def test_get_char(self):
        self.assertEqual(get_char(self.rom.rom_fh, 0), 128)
        self.assertEqual(get_char(self.rom.rom_fh, keep_last_pos=True), 55)
        self.assertEqual(get_char(self.rom.rom_fh), 55)

    def test_get_short(self):
        self.assertEqual(get_short(self.rom.rom_fh, 0), 32823)
        self.assertEqual(get_short(self.rom.rom_fh, keep_last_pos=True), 4672)
        self.assertEqual(get_short(self.rom.rom_fh), 4672)

    def test_get_long(self):
        self.assertEqual(get_long(self.rom.rom_fh, 0), 2151092800)
        self.assertEqual(get_long(self.rom.rom_fh, keep_last_pos=True), 15)
        self.assertEqual(get_long(self.rom.rom_fh), 15)

    def test_get_bytes(self):
        self.assertEqual(
            get_bytes(self.rom.rom_fh, 10, 0), b"\x807\x12@\x00\x00\x00\x0f\x80\x00"
        )
        self.assertEqual(
            get_bytes(self.rom.rom_fh, 10, keep_last_pos=True),
            b"\x04\x00\x00\x00\x14I\xecX\xea\xbf",
        )
        self.assertEqual(
            get_bytes(self.rom.rom_fh, 10), b"\x04\x00\x00\x00\x14I\xecX\xea\xbf"
        )


if __name__ == "__main__":
    unittest.main()
