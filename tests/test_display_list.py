import os
import re
import glob
import unittest

from pathlib import Path

from dk64_lib.rom import Rom
from dk64_lib.constants import MAPS
from dk64_lib.file_io import get_bytes, get_char, get_long, get_short


def get_rom() -> Rom:
    rom_glob = glob.glob(str(Path(os.path.dirname(__file__)) / "dk64_rom" / "*.*"))
    # TODO: At the moment, we are only testing a single version (US specifically)
    # TODO: This should be updated to test all versions of DK64
    return [Rom(rom) for rom in rom_glob][0]


def get_obj_file_str(obj_name: str) -> str:
    file_path = Path(os.path.dirname(__file__)) / "verified_objs" / obj_name
    with open(file_path) as fil:
        return fil.read()


class ObjTest(unittest.TestCase):
    def setUp(self):
        self.rom = get_rom()

    def test_map_objs(self):
        COMMENT_PATTERN = re.compile(r"#.*\n")
        NEW_LINE_PATTERN = re.compile(r"[^0-9]\n")
        for map_num, geometry_table in enumerate(self.rom.geometry_tables):
            with self.subTest(f"{map_num}.obj, {MAPS[map_num]}"):
                try:
                    obj_data = get_obj_file_str(f"{map_num}.obj")
                except FileNotFoundError:
                    self.skipTest(f"{map_num}.obj does not exist... Skipping")

                created_obj = geometry_table.create_obj()

                cleaned_obj_data = NEW_LINE_PATTERN.sub(
                    "", COMMENT_PATTERN.sub("", obj_data)
                )
                cleaned_created_obj = NEW_LINE_PATTERN.sub(
                    "", COMMENT_PATTERN.sub("", created_obj)
                )
                self.assertEqual(cleaned_created_obj, cleaned_obj_data)

class DisplayListTest(unittest.TestCase):
    def setUp(self):
        self.rom = get_rom()
        
    def test_command_count(self):
        
        command_counts = {
            0: [3, 96], 
            1: [1861, 219, 63, 54], 
            2: [], 
            3: [233, 306, 199, 340, 233, 270, 37, 37, 39], 
            4: [2, 11, 832, 199, 383, 196, 304, 314, 150, 273, 293, 189, 31, 27, 27, 27, 27, 17, 31, 751, 102, 291, 274, 53, 269, 353, 324, 127, 39, 31, 27, 27], 
            5: [1016, 110, 183, 245, 245, 186, 94, 97, 88, 67, 51, 27, 17, 40, 48, 29, 35, 60, 76], 
            6: [773, 656, 589, 456, 53, 973, 257, 62, 437, 371, 373, 382, 599, 64, 342, 335, 69, 322, 577, 562, 264, 417, 542, 613, 328, 74, 376, 464, 281, 362, 324, 211, 152, 208, 193, 129, 412, 477, 726, 780, 66, 64, 309, 25], 
            7: [513, 277, 591, 47, 473, 71, 16, 386, 318, 106, 139, 442, 184, 188, 475, 330, 7, 193, 138, 213, 276, 192, 263, 269, 16, 3, 43, 54, 60, 93, 48, 57, 74, 3, 7, 3, 3, 3, 3, 53, 72, 152, 16, 3, 3, 3, 3, 36, 3, 3, 3, 3, 7, 3, 3, 3, 3, 3, 34, 3, 279, 266, 176, 33, 1150, 103, 232, 136, 250, 133, 35, 214, 77, 195, 276, 95, 750, 109, 196, 385, 31, 387, 35, 121, 96, 121, 108, 23, 21, 20], 
            8: [48, 174, 192, 173, 168, 151, 140, 37, 87, 95, 89, 95, 99, 91], 
            9: [], 
            10: [2, 1085], 
            11: [424, 367, 249, 333, 474, 350, 239, 233, 337, 37, 37, 37, 39], 
            12: [761, 137, 332, 50, 147, 400, 50, 147, 450, 91], 
            13: [612, 65, 17, 37], 
            14: [4, 347, 8, 783, 603, 507, 1050, 960, 8, 83, 36, 32, 28, 94, 355, 422, 127, 13, 450, 327, 922, 394, 322, 623, 427, 538, 692, 727, 13, 32, 3, 3, 28, 3, 51, 28, 32, 53, 89, 455, 286, 355, 127, 11, 1109, 352, 416, 738, 272, 417, 699, 514, 11, 32, 3, 3, 44, 3, 28, 40, 73, 347], 
            15: [223, 186, 62, 38, 122, 187, 175, 48, 160, 48, 201, 98, 48, 40, 102, 203, 87, 101, 121, 62, 48, 218, 87, 40, 115, 108, 48, 40, 38, 210, 3, 48, 186, 157, 48, 160, 189, 87, 42, 73, 48, 68, 3, 62, 6, 3, 3, 3, 7, 3, 3, 3, 3, 7, 3, 3, 3, 3, 8, 3, 3, 3, 3, 3, 10, 3, 3, 3, 3, 3, 3, 3, 5, 3, 3, 6, 3, 3, 3, 8, 3, 3, 3, 3, 3, 36], 
            16: [2, 5, 1571, 239, 85, 412, 463, 115, 69, 348, 218, 485], 
            17: [515, 271, 249, 205, 116, 206, 144, 25, 136, 131, 30, 39, 47, 240, 157, 728, 231, 199, 81, 81, 208, 81, 81, 64, 228, 228, 39, 39, 168, 91, 58, 58, 25, 45, 312, 89, 89, 260, 274, 120, 73, 208, 122, 220, 169, 215, 158, 105, 211, 130, 146, 148, 146, 103, 107, 146, 117, 236, 148, 173, 39, 39, 54, 460, 119, 79, 79, 266, 81, 48, 39, 382, 79, 79, 119, 316, 81, 48, 39, 338, 119, 79, 79, 316, 81, 48, 39, 382, 79, 79, 119, 316, 81, 48, 39, 378, 119, 79, 79, 316, 81, 48, 39, 130, 713, 152, 152, 87, 168, 81, 161, 129, 95, 95, 95, 27, 60, 25, 591, 123, 617, 221, 152, 152, 135, 164, 746, 140, 140, 123, 207, 124, 241, 163, 257, 157, 235, 157, 239, 79, 119, 313, 74], 
            18: [358, 26], 
            19: [575, 425, 19, 35, 732, 497, 576], 
            20: [109, 370, 269, 197, 267, 267, 265, 184, 246, 387, 385, 197, 212, 45, 41, 45, 35, 35, 59, 67, 32, 32, 142, 146, 366, 144, 266, 79, 187, 525, 529, 520, 297], 
            21: [575, 425, 19, 35, 732, 497, 576], 
            22: [417, 513, 497, 19, 35, 469, 306, 478, 482, 559, 560, 354, 363], 
            23: [1181, 19, 35, 1002, 482, 559, 560], 
            24: [417, 513, 497, 19, 35, 448, 306, 457, 446, 503, 448, 715, 715, 422, 306, 422, 381], 
            25: [5, 1966, 50, 212, 2, 321, 2, 16, 2, 30], 
            26: [950, 377, 215, 141, 44, 410, 295, 440, 165, 154, 306, 468, 429, 80, 90, 127, 198, 110, 167, 201, 127, 269, 192, 8, 55, 223, 155, 64, 119, 80, 117, 236, 143, 122, 102, 118, 90, 215, 210, 151, 131, 131, 519, 398, 215, 145, 119, 128, 128, 147, 137, 128, 137, 15, 45, 3, 4, 3, 3, 4, 3, 3, 8, 3, 3, 3, 4, 3, 3, 9, 3, 4, 3, 4, 3, 3, 3, 3, 8, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 801, 98, 1011, 618, 742, 98, 713, 436, 27, 1017, 696, 343, 576, 312, 36, 370, 215, 310, 500, 217, 145, 242, 305, 395, 324, 562, 12, 28, 3, 3, 4, 3, 3, 3, 3, 3, 3, 3, 28, 771, 792, 754, 291, 337, 229, 311, 311, 253, 702, 269, 230, 266, 68, 93, 240, 68, 269, 68, 487, 68, 68, 171, 39, 35, 35, 39, 35, 34, 35, 34, 35, 35, 1074, 992, 542, 654, 482, 31, 434, 117, 1038], 
            27: [287, 382, 51, 146, 379, 257, 186, 164, 171, 51, 435, 383, 67, 380, 380, 51, 380, 380, 383, 233, 381, 380, 51, 388, 402, 39, 27, 382, 382, 456, 51, 426, 235, 234, 257, 169, 134, 383, 325, 51, 385, 384, 385, 380, 462, 51, 382, 382, 306, 382, 383, 322, 379, 383, 51, 382, 382, 331, 449, 376, 379, 51, 383, 380, 382, 51, 455, 382, 51, 382, 382], 
            28: [], 
            29: [2, 412], 
            30: [360, 320, 358, 384, 50, 256, 1286, 67, 1275, 230, 92, 454, 488, 54, 307, 127, 196, 639, 158, 163, 778, 570, 115, 105, 231, 115, 197, 275, 233, 429, 124, 392, 63, 157, 127, 661, 111, 51, 93, 143, 370, 54, 39, 333, 297, 129, 90, 145, 484, 308, 616, 837], 
            31: [10, 403, 396, 80, 670, 567, 45, 753, 124], 
            32: [3, 332, 260, 2, 56], 
            33: [440, 131, 17, 35, 256, 174, 257, 213, 99, 99, 154, 53, 37, 38], 
            34: [2, 27, 55, 390, 191, 408, 280, 207, 406, 107, 317, 137, 246, 70, 72, 55, 107, 206, 55, 65, 45, 45, 85, 109, 56, 74, 71, 168, 51, 440, 912, 204, 151, 85, 131, 211, 90, 131, 763, 127, 405, 84, 109, 58, 53, 910, 39, 76], 
            35: [75, 112, 112, 112], 
            36: [445], 
            37: [2, 14, 2, 14, 37, 21, 19, 19, 19, 19, 15, 18, 19, 15, 18, 18, 18, 18, 18, 18, 37, 38, 48, 24, 24, 38, 24, 48, 24, 48, 24, 24, 24, 24], 
            38: [2, 8, 2, 45, 2, 8, 2, 29, 2, 15, 2, 36, 2, 19, 2, 99, 810, 436, 62, 809, 33, 416, 870, 216, 685, 330, 51, 422, 701, 674, 34, 634, 414, 328, 208, 17, 184, 216, 5, 121, 548, 8, 117, 370, 123, 442, 271, 131, 165, 201, 183, 225, 267, 220, 176, 223, 353, 17, 3, 3, 5, 3, 3, 8, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 34, 3, 3, 3, 38, 38], 
            39: [1301, 221, 344, 413, 43, 455, 43, 414, 43, 414, 36, 455, 413, 326, 50], 
            40: [362], 
            41: [37, 21, 19, 19, 19, 19, 15, 18, 19, 15, 18, 18, 18, 18, 18, 18, 26, 34, 44, 24, 24, 44, 24, 34, 24, 24, 30, 34], 
            42: [794, 100, 112], 
            43: [144, 170, 17, 31, 486, 175, 175, 39, 81, 81, 80, 462, 102, 121, 199, 121, 52, 81, 42, 17, 31, 593, 136, 115, 194, 63, 63, 81, 39, 39, 39, 117, 156, 167, 17, 31], 
            44: [17, 192, 153, 117, 142, 152, 111, 108, 163, 168, 131, 107, 135, 43, 98, 59, 24, 17, 38, 32, 28, 25, 35, 32, 28], 
            45: [3, 1062, 2, 156], 
            46: [104, 108, 43, 35, 322, 129, 279, 317, 313, 146, 82, 329, 336, 195, 154, 330, 174, 76, 167, 125, 125, 163, 167, 113, 113, 603, 274, 500, 84, 178, 59, 25, 31, 35, 32, 34, 38, 225, 108, 121, 35, 31], 
            47: [581, 53, 63, 267, 185, 162, 292, 79, 17, 31, 565, 472, 74, 59, 367, 703, 600, 134, 50, 85, 68, 31, 17, 31, 211, 242, 244, 211, 45, 53, 53, 45], 
            48: [249, 140, 153, 288, 351, 197, 147, 158, 151, 176, 220, 148, 120, 328, 167, 102, 111, 102, 33, 36, 107, 157, 136, 49, 737, 384, 94, 411, 260, 339, 55, 126, 102, 61, 214, 87, 472, 190, 74, 611, 904, 340, 222, 54, 262, 196, 51, 125, 554, 260, 229, 206, 92, 722, 233, 116, 66, 104, 220, 376, 390, 299, 413, 57, 61, 70, 170, 354, 143, 952, 537, 596, 393, 389, 152, 286, 253, 27, 27], 
            49: [201, 535, 100, 324, 98, 240, 131, 127, 125, 212, 133, 214, 119, 58, 40], 
            50: [], 
            51: [217, 583, 229, 229, 154, 229, 229, 154, 142, 182], 
            52: [107, 144, 144, 144, 144, 144, 53, 53, 53, 53, 53, 21, 39], 
            53: [187, 85, 31, 23], 
            54: [2, 10, 2, 10, 50, 15, 24, 19, 19, 15, 19, 138, 124, 19, 158, 19, 15, 15, 17, 18, 18, 108, 18, 18, 70, 37, 40, 39, 24, 24, 23, 49, 50, 44, 24, 24, 23, 24, 62, 34, 24], 
            55: [187, 305, 78, 39, 666, 110, 269, 31, 252, 694, 216, 143, 41, 488, 1007, 147, 241, 366, 134, 1124, 193, 208, 73, 698, 410, 59, 31, 975, 136, 1199, 409, 287, 943, 143, 656, 1035, 343, 31, 802, 262, 65, 1242, 168, 1079, 61, 161, 926, 881, 101, 688, 31, 593, 114, 853, 753, 69, 1077, 107, 1615, 31, 534, 117], 
            56: [220, 308, 197, 308, 240, 123, 121, 81, 91, 93, 123, 101], 
            57: [1129, 154], 
            58: [863, 125], 
            59: [665, 271, 257, 213, 161, 109, 109, 109, 109, 134, 86, 192, 100, 330, 31, 78], 
            60: [313, 136, 87, 87, 87, 87, 87, 87, 87, 87, 154], 
            61: [608, 200, 185, 253, 260, 247, 124, 111, 107, 75, 65, 228, 43, 62, 42, 32], 
            62: [449, 200, 196, 253, 387, 301, 124, 111, 135, 87, 75, 187, 62, 43, 77, 33, 42, 32], 
            63: [295, 178, 53], 
            64: [313, 311, 331, 528, 445, 474, 402, 283, 170, 88, 95, 21, 18, 18, 18, 18, 39, 33, 33, 33, 33], 
            65: [], 
            66: [], 
            67: [323, 199, 323, 249, 256, 269, 37, 37, 37, 39], 
            68: [], 
            69: [], 
            70: [], 
            71: [], 
            72: [480, 210, 238, 262, 101, 247, 204, 305, 252, 212, 173, 106, 27, 323, 475, 104, 282, 93, 143, 132, 472, 101, 139, 466, 204, 285, 159, 284, 122, 244, 242, 100, 172, 115, 159, 235, 135, 233, 230, 41, 115, 261, 176, 237, 37, 25, 35, 25, 25, 52, 25, 46, 44, 29, 46, 54, 375, 183, 216, 430, 185, 374, 93, 525, 120, 250, 102, 206, 93, 106, 167, 116, 80, 37, 34, 34, 35, 27, 469, 385, 193, 561, 105, 105, 70, 70, 70, 166, 296, 186, 256, 242, 166, 70, 54, 33, 304, 120, 172, 125, 72, 237, 212, 60, 110, 123, 115, 45, 37, 123, 123, 102, 161, 303, 251, 312, 228, 45, 25, 149, 309, 133, 454, 120, 105, 281, 191, 206, 24, 33, 237, 136, 105, 269, 93, 43, 45, 676, 147, 349, 369, 341, 368, 61], 
            73: [], 
            74: [], 
            75: [], 
            76: [], 
            77: [64, 249], 
            78: [445], 
            79: [], 
            80: [669, 149], 
            81: [3, 96], 
            82: [496, 175, 44, 31, 378, 432, 62, 68, 55, 66, 31, 39, 317, 55, 55, 31, 442, 120, 378, 432, 62, 68, 55, 66, 31, 39, 317, 56, 55, 31, 367, 258, 236, 339, 64, 274, 56, 341, 64, 869, 96, 267, 495, 162, 162, 105, 378, 64, 470, 81, 462, 117, 429, 80, 55, 31, 794, 289, 106, 272, 56, 603, 72, 154, 464, 260, 235, 121, 110, 73, 64, 704, 96, 249, 496, 260, 235, 162, 162, 39, 107, 98, 498, 74, 66, 39, 317, 55, 55, 31, 515, 175, 44, 31], 
            83: [69, 53, 248, 147], 
            84: [536, 47], 
            85: [1201, 60], 
            86: [820, 59], 
            87: [149, 402, 173, 400, 205, 231, 392, 272, 297, 136, 185, 206, 144, 137, 290, 478, 505, 97, 92, 60, 115, 70, 154, 348, 152, 155, 291, 242, 189, 141, 325, 117, 84, 111, 111, 102, 96, 98, 109, 85, 85, 41, 85, 102, 89, 94, 397, 447, 273, 111, 183, 81, 257, 70, 63, 143, 359, 109, 194, 78, 445, 125, 458, 260, 261, 243, 35, 318, 195, 384, 226, 84, 96, 214, 96, 273, 351, 122], 
            88: [472, 39, 407, 31, 196, 336, 336, 336, 192, 193, 56, 192, 381, 36, 36, 55, 36], 
            89: [10, 17, 15, 16, 32, 16, 16], 
            90: [566, 183, 199, 183, 199, 179, 199, 185, 192, 183, 145], 
            91: [1229, 31], 
            92: [1065, 165], 
            93: [1128, 82], 
            94: [1194, 116], 
            95: [301, 47], 
            96: [216, 168, 168, 168], 
            97: [679, 125, 33], 
            98: [807, 51], 
            99: [73, 252, 168, 168], 
            100: [301, 47], 
            101: [], 
            102: [], 
            103: [], 
            104: [328], 
            105: [450, 16], 
            106: [710, 26, 818, 59, 648, 42, 412, 64, 816, 686, 453, 414, 449, 587, 42, 683, 46, 629, 45, 493, 42, 719, 24, 491, 385, 285, 247, 247, 247, 247, 247, 247, 247, 247, 271, 216, 570, 45, 570, 43, 422, 42, 611, 49, 455, 41, 482, 24, 589, 42, 491, 668, 45, 346, 305, 387, 388, 505, 42, 620, 80, 614, 71, 731, 95, 585, 60, 393, 440, 447, 31], 
            107: [5, 195, 16, 16, 2, 84, 2, 30], 
            108: [2, 12, 2, 28, 2, 27, 2, 19, 2, 22, 2, 14, 2, 11, 315, 544, 454, 450, 467, 41, 325, 408, 249, 449, 40], 
            109: [68, 299, 143, 101, 115, 152, 67, 3, 3, 3, 3, 3, 243, 233, 246, 227, 89, 89], 
            110: [223, 303, 303, 287, 197, 230, 228], 
            111: [152, 97], 
            112: [2, 36, 2, 11, 2, 25, 2, 12, 2, 13, 2, 16, 2, 49, 2, 13, 2, 13, 2, 55, 2, 56, 542, 279, 480, 266, 266, 358, 823, 33, 275, 69, 255, 830, 504, 823, 266], 
            113: [414, 299, 284, 27, 578, 1190, 524, 25, 72, 35], 
            114: [444, 301, 341, 27, 751, 357, 27, 453, 47, 19, 35], 
            115: [], 
            116: [], 
            117: [], 
            118: [], 
            119: [], 
            120: [], 
            121: [], 
            122: [], 
            123: [], 
            124: [], 
            125: [], 
            126: [], 
            127: [], 
            128: [], 
            129: [], 
            130: [], 
            131: [], 
            132: [], 
            133: [], 
            134: [], 
            135: [], 
            136: [], 
            137: [], 
            138: [], 
            139: [], 
            140: [], 
            141: [], 
            142: [], 
            143: [], 
            144: [381, 26], 
            145: [], 
            146: [], 
            147: [], 
            148: [], 
            149: [], 
            150: [], 
            151: [2, 5, 2, 26, 2, 16, 2, 13, 2, 5, 2, 18, 2, 5, 2, 33, 2, 22, 2, 12, 438, 95, 234, 233, 259, 365, 390, 336, 95], 
            152: [], 
            153: [], 
            154: [16, 84, 109, 74, 64, 39, 39, 39, 39], 
            155: [], 
            156: [], 
            157: [], 
            158: [], 
            159: [], 
            160: [], 
            161: [], 
            162: [], 
            163: [2, 10, 2, 22, 2, 12, 2, 12, 2, 22, 2, 10, 170, 140, 343, 85, 551, 123, 948, 461, 124, 656, 490, 125, 888, 95], 
            164: [335, 206, 212, 103, 168, 261, 235, 207, 205, 286, 138, 119, 132, 207, 227, 161, 258, 265, 21, 39], 
            165: [], 
            166: [909, 68], 
            167: [730, 19, 35], 
            168: [936, 17, 33, 31], 
            169: [648, 285, 18, 33], 
            170: [352, 125, 123, 398, 411, 106, 106, 224, 225, 75, 93, 17, 63], 
            171: [5, 1482, 149, 880, 25, 5, 208, 79, 49, 24], 
            172: [47, 113, 61, 234], 
            173: [294, 129, 116, 116, 76, 76, 205, 117, 128, 128, 195, 31, 31, 31, 31, 31, 52, 33, 60, 18, 33, 167, 60], 
            174: [92, 171, 173, 289, 272, 326, 223, 158, 221, 159, 17, 37, 511, 41], 
            175: [1246, 18, 33], 
            176: [2, 25, 420, 38, 103, 103, 70, 80, 142, 135, 280, 95, 221, 257, 133, 163, 499, 159, 180, 93, 75, 33, 33, 101, 33, 62, 77, 62, 33, 79, 395, 41, 234, 243, 148, 39, 277, 159, 159, 159, 189, 31, 31, 31, 17, 31, 780, 113, 170], 
            177: [], 
            178: [485, 89, 156, 226, 254, 111, 75, 97, 43, 44, 60], 
            179: [417, 216, 21, 39, 16], 
            180: [], 
            181: [], 
            182: [], 
            183: [2, 9, 2, 28, 2, 30, 2, 35, 2, 29, 2, 24, 296, 235, 752, 778, 29, 277, 271], 
            184: [568, 214, 35, 35, 17], 
            185: [362, 284, 304, 189, 144, 237, 448, 410, 428, 448, 25, 792, 549], 
            186: [103, 155, 155, 77, 76, 211, 334, 217, 287, 273, 173], 
            187: [2, 16, 273, 136], 
            188: [2, 14, 50, 62, 58, 27, 39, 56, 27, 39, 23, 74, 89, 57, 27, 254, 23, 39, 23, 23, 24, 39, 39, 39, 39, 37, 24, 24, 48, 38, 34, 24, 24, 34, 24], 
            189: [2, 10, 347, 193, 191, 360, 116, 317, 116, 317, 116, 317, 116, 317, 122, 21, 48, 282], 
            190: [111, 99, 83, 83, 83, 83, 220, 212, 220, 137, 72, 72, 59, 31, 110, 110, 124, 31, 124, 110, 110, 31, 110, 110, 123, 215], 
            191: [246, 95, 95, 95, 95, 202, 68, 142, 143, 142, 135, 217, 37], 
            192: [678, 18], 
            193: [784, 92, 594, 118], 
            194: [701, 69, 82, 69, 82, 69, 82, 105, 132, 169, 158, 303, 18, 33, 208, 51, 228, 73], 
            195: [296, 171, 18, 33], 
            196: [151, 182, 227, 272, 140, 64, 64, 217, 64, 120, 213, 1218, 119, 31], 
            197: [87, 173, 81], 
            198: [], 
            199: [1058, 98, 198, 49], 
            200: [279, 451, 362, 443, 338, 323, 323, 323, 81], 
            201: [], 
            202: [], 
            203: [769, 112, 166, 86, 147, 85, 332, 71, 85, 65, 86, 89, 29, 27, 27, 27, 606, 64, 31, 115], 
            204: [], 
            205: [], 
            206: [], 
            207: [450, 112, 166, 86, 147, 85, 332, 71, 85, 65, 86, 89, 29, 27, 27, 27, 606, 64, 31, 115], 
            208: [122, 15, 15], 
            209: [], 
            210: [], 
            211: [], 
            212: [], 
            213: [], 
            214: [2, 18, 426, 182], 
            215: []
        }
            
        for geometry_pos, geometry in enumerate(self.rom.geometry_tables):
            with self.subTest(f"Geometry {geometry_pos}"):
                self.assertEqual(command_counts.get(geometry_pos), [dl.num_commands for dl in geometry.display_lists])
            
        
if __name__ == "__main__":
    unittest.main()
