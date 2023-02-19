import os
import re
import glob
import unittest

from pathlib import Path

from dk64_lib import MAPS
from dk64_lib.rom import Rom
from dk64_lib.file_io import get_bytes, get_char, get_long, get_short


def get_rom() -> Rom:
    rom_glob = glob.glob(str(Path(os.path.dirname(__file__)) / "dk64_rom" / "*.*"))
    # TODO: At the moment, we are only testing a single version (US specifically)
    # TODO: This should be updated to test all versions of DK64
    return [Rom(rom) for rom in rom_glob][0]

def get_obj_file_str(obj_name: str) -> str:
    file_path = Path(os.path.dirname(__file__)) / 'verified_objs' / obj_name
    with open(file_path) as fil:
        return fil.read()

class ObjTest(unittest.TestCase):
    def setUp(self):
        self.rom = get_rom()

    def test_map_objs(self):
        COMMENT_PATTERN = re.compile(r'#.*\n')
        NEW_LINE_PATTERN = re.compile(r'[^0-9]\n')
        for map_num, map_name in enumerate(MAPS):
            with self.subTest(f'{map_num}.obj, {map_name}'):
                try:
                    obj_data = get_obj_file_str(f'{map_num}.obj')
                except FileNotFoundError:
                    self.skipTest(f'{{map_num}}.obj does not exist... Skipping')
                    
                created_obj = self.rom.geometry_tables[map_num].create_obj()
                
                cleaned_obj_data = NEW_LINE_PATTERN.sub('', COMMENT_PATTERN.sub('', obj_data))
                cleaned_created_obj = NEW_LINE_PATTERN.sub('', COMMENT_PATTERN.sub('', created_obj))
                
                self.assertEqual(cleaned_created_obj, cleaned_obj_data)


if __name__ == "__main__":
    unittest.main()
