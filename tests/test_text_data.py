import glob
import os
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from dk64_lib.data_types.text import _Text, _TextLine, _TextLineFragment
from dk64_lib.rom import Rom


def get_rom() -> Rom:
    rom_glob = glob.glob(str(Path(os.path.dirname(__file__)) / "dk64_rom" / "*.*"))
    return [Rom(rom) for rom in rom_glob][0]


class TextDataTest(unittest.TestCase):
    def setUp(self):
        self.rom = get_rom()

    def test_text_lines_preserve_existing_text(self):
        self.assertEqual(
            self.rom.text_tables[0].text_lines[0].text, "WELCOME TO THE BONUS STAGE!"
        )
        self.assertEqual(
            self.rom.text_tables[-1].text_lines[-1].text, "HOW ABOUT ANOTHER GAME?"
        )

    def test_text_records_are_immutable(self):
        text_line = self.rom.text_tables[0].text_lines[0]
        fragment = text_line.sentence_fragments[0]
        text = fragment.text[0]

        self.assertIsInstance(text_line, _TextLine)
        self.assertIsInstance(text_line.sentence_fragments, tuple)
        self.assertIsInstance(fragment, _TextLineFragment)
        self.assertIsInstance(fragment.text, tuple)
        self.assertIsInstance(text, _Text)

        with self.assertRaises(FrozenInstanceError):
            text_line.data_start = "0x00"
        with self.assertRaises(FrozenInstanceError):
            fragment.offset = 0
        with self.assertRaises(FrozenInstanceError):
            text.text = "changed"


if __name__ == "__main__":
    unittest.main()
