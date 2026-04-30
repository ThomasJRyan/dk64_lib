import unittest
from types import SimpleNamespace

from dk64_lib.data_types.table_stubs import (
    AnimationData,
    MidiMusicData,
    STUB_TABLE_DATA_TYPES,
    UnknownTable19Data,
)
from dk64_lib.rom import RAW_EXPORT_TABLES, Rom


def _fake_rom() -> Rom:
    rom = Rom.__new__(Rom)
    rom.rom_fh = SimpleNamespace(close=lambda: None)
    return rom


class TableStubTest(unittest.TestCase):
    def test_stub_data_preserves_raw_entry_metadata(self):
        entry = AnimationData(
            raw_data=b"animation",
            offset=0x123456,
            size=9,
            was_compressed=True,
            rom=None,
        )

        self.assertEqual(entry.table_id, 11)
        self.assertEqual(entry.data_type, "Animation")
        self.assertEqual(entry.raw_data, b"animation")
        self.assertEqual(entry.offset, 0x123456)
        self.assertEqual(entry.size, 9)
        self.assertTrue(entry.was_compressed)

    def test_table_19_records_known_entry_labels(self):
        self.assertEqual(UnknownTable19Data.known_entries[4], "DK Rap lyrics")
        self.assertEqual(UnknownTable19Data.known_entries[7], "End sequence credits")

    def test_stub_table_registry_maps_known_tables(self):
        self.assertIs(STUB_TABLE_DATA_TYPES[0], MidiMusicData)
        self.assertIs(STUB_TABLE_DATA_TYPES[11], AnimationData)
        self.assertIs(STUB_TABLE_DATA_TYPES[19], UnknownTable19Data)

    def test_rom_get_stub_table_data_uses_registered_stub_type(self):
        rom = _fake_rom()

        def generate_rom_table_data(tables: list[int]):
            table_id = tables[0]
            yield {
                "raw_data": bytes([table_id]),
                "offset": table_id,
                "size": 1,
                "was_compressed": False,
                "rom": rom,
            }

        rom.generate_rom_table_data = generate_rom_table_data

        entries = Rom.get_animation_data(rom)

        self.assertEqual(len(entries), 1)
        self.assertIsInstance(entries[0], AnimationData)
        self.assertEqual(entries[0].raw_data, b"\x0b")

    def test_rom_get_stub_table_data_rejects_unregistered_tables(self):
        rom = _fake_rom()

        with self.assertRaisesRegex(ValueError, "does not have a stub"):
            Rom.get_stub_table_data(rom, 6)

    def test_default_raw_export_tables_include_named_stub_tables(self):
        self.assertEqual(
            RAW_EXPORT_TABLES,
            (
                0,
                1,
                2,
                3,
                4,
                5,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                21,
                22,
                23,
                24,
                25,
                26,
            ),
        )


if __name__ == "__main__":
    unittest.main()
