import os
import glob
import unittest

from pathlib import Path

from dk64_lib.rom import Rom
from dk64_lib.file_io import get_bytes, get_char, get_long, get_short

def get_rom():
    rom_glob = glob.glob(str(Path(os.path.dirname(__file__)) / "dk64_rom" / "*.*"))
    # TODO: At the moment, we are only testing a single version (US specifically)
    # TODO: This should be updated to test all versions of DK64
    return [Rom(rom) for rom in rom_glob][0]

class RomTest(unittest.TestCase):
    def setUp(self):
        self.rom = get_rom()

    def test_release_or_kiosk(self):
        self.assertIn(self.rom.release_or_kiosk, ['release', 'kiosk'])
        
    def test_region(self):
        self.assertIn(self.rom.region, ['us', 'pal', 'jp', 'kiosk'])
        
    def test_pointer_table_offset(self):
        self.assertIn(self.rom.pointer_table_offset, [0x101C50, 0x1038D0, 0x1039C0, 0x1A7C20])
        
    def test_text_lines(self):
        self.assertEqual(self.rom.text_tables[0].text_lines[0].text, 'WELCOME TO THE BONUS STAGE!')
        self.assertEqual(self.rom.text_tables[-1].text_lines[-1].text, 'HOW ABOUT ANOTHER GAME?')
        
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
        self.assertEqual(get_bytes(self.rom.rom_fh, 10, 0), b'\x807\x12@\x00\x00\x00\x0f\x80\x00')
        self.assertEqual(get_bytes(self.rom.rom_fh, 10, keep_last_pos=True), b'\x04\x00\x00\x00\x14I\xecX\xea\xbf')
        self.assertEqual(get_bytes(self.rom.rom_fh, 10), b'\x04\x00\x00\x00\x14I\xecX\xea\xbf')

if __name__ == '__main__':
    unittest.main()