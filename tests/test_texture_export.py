import tempfile
import unittest
import zlib

from pathlib import Path
from types import SimpleNamespace

from dk64_lib.f3dex2.display_list import DisplayList
from dk64_lib.f3dex2.texture_export import (
    TexturedObjExporter,
    decode_texture,
    rgba_to_png,
    save_textured_obj_export,
    test_mipmap_export as export_test_mipmap,
)


def _words(word0: int, word1: int) -> bytes:
    return word0.to_bytes(4, "big") + word1.to_bytes(4, "big")


def _g_texture(level: int, tile: int = 0, on: int = 1) -> bytes:
    return _words(
        0xD7000000 | (level << 11) | (tile << 8) | (on << 1),
        0xFFFFFFFF,
    )


def _settile(fmt: int, size: int, tile: int, tmem: int = 0) -> bytes:
    return _words(0xF5000000 | (fmt << 21) | (size << 19) | tmem, tile << 24)


def _settilesize(tile: int, width: int, height: int) -> bytes:
    lrs = (width - 1) * 4
    lrt = (height - 1) * 4
    return _words(0xF2000000, (tile << 24) | (lrs << 12) | lrt)


def _rgba16(red: int, green: int, blue: int, alpha: int = 255) -> bytes:
    raw = (
        ((red * 31 // 255) << 11)
        | ((green * 31 // 255) << 6)
        | ((blue * 31 // 255) << 1)
        | (1 if alpha else 0)
    )
    return raw.to_bytes(2, "big")


def _indexed_rgba(*indices: int) -> bytes:
    colors = (
        (0, 0, 0, 255),
        (255, 0, 0, 255),
        (0, 255, 0, 255),
        (0, 0, 255, 255),
        (255, 255, 255, 255),
    )
    return bytes(component for index in indices for component in colors[index])


def _indexed_rgba16(*indices: int) -> bytes:
    colors = (
        (0, 0, 0),
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 255),
    )
    return b"".join(_rgba16(*colors[index]) for index in indices)


def _ci4_indices(*indices: int) -> bytes:
    if len(indices) % 2:
        indices = (*indices, 0)
    return bytes(
        ((indices[index] & 0xF) << 4) | (indices[index + 1] & 0xF)
        for index in range(0, len(indices), 2)
    )


def _vertex(
    x: int,
    y: int,
    z: int,
    u: int,
    v: int,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> bytes:
    return (
        x.to_bytes(2, "big", signed=True)
        + y.to_bytes(2, "big", signed=True)
        + z.to_bytes(2, "big", signed=True)
        + b"\x00\x00"
        + u.to_bytes(2, "big", signed=True)
        + v.to_bytes(2, "big", signed=True)
        + bytes(color)
    )


def _png_rgba(data: bytes) -> tuple[tuple[int, int], bytes]:
    width = height = 0
    idat = bytearray()
    cursor = 8
    while cursor < len(data):
        chunk_size = int.from_bytes(data[cursor : cursor + 4], "big")
        chunk_type = data[cursor + 4 : cursor + 8]
        chunk_data = data[cursor + 8 : cursor + 8 + chunk_size]
        cursor += chunk_size + 12
        if chunk_type == b"IHDR":
            width = int.from_bytes(chunk_data[0:4], "big")
            height = int.from_bytes(chunk_data[4:8], "big")
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    rows = zlib.decompress(bytes(idat))
    row_size = 1 + width * 4
    pixels = bytearray()
    for row in range(height):
        row_start = row * row_size
        pixels.extend(rows[row_start + 1 : row_start + row_size])
    return (width, height), bytes(pixels)


class TextureExportTest(unittest.TestCase):
    def test_decode_rgba16_texture(self):
        rgba = decode_texture(
            _rgba16(255, 0, 0) + _rgba16(0, 255, 0),
            fmt=0,
            size=2,
            width=2,
            height=1,
        )

        self.assertEqual(rgba, bytes((255, 0, 0, 255, 0, 255, 0, 255)))

    def test_png_writer_outputs_png_data(self):
        png = rgba_to_png(1, 1, bytes((255, 0, 0, 255)))

        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(b"IHDR", png)
        self.assertIn(b"IDAT", png)

    def test_exporter_writes_textured_obj_material_and_image(self):
        texture_data = [
            SimpleNamespace(
                raw_data=(
                    _rgba16(255, 0, 0)
                    + _rgba16(0, 255, 0)
                    + _rgba16(0, 0, 255)
                    + _rgba16(255, 255, 255)
                )
            )
        ]
        vertex_data = (
            _vertex(0, 0, 0, 0, 0, color=(255, 0, 128, 255))
            + _vertex(1, 0, 0, 64, 0)
            + _vertex(0, 1, 0, 0, 64)
        )
        commands = b"".join(
            (
                _words(0xFD100000, 0x00000000),
                _words(0xF3000000, 0x07000000),
                _words(0xF5100000, 0x00000000),
                _words(0xF2000000, 0x00004004),
                b"\x01\x00\x30\x06\x00\x00\x00\x00",
                b"\x05\x00\x02\x04\x00\x00\x00\x00",
                b"\xdf\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        display_list = DisplayList(
            raw_data=commands,
            raw_vertex_data=vertex_data,
            vertex_pointer=0,
            offset=0,
        )

        export = TexturedObjExporter(texture_data).export([display_list], "model.mtl")

        self.assertIn("mtllib model.mtl", export.obj_data)
        self.assertIn("v 0 0 0 1.000000 0.000000 0.501961", export.obj_data)
        self.assertIn("vt 0.00000000 1.00000000", export.obj_data)
        self.assertIn("usemtl tex_0_pal_none_f0_s2_2x2", export.obj_data)
        self.assertIn("f 1/1 2/2 3/3", export.obj_data)
        self.assertIn("map_Kd textures/tex_0_pal_none_f0_s2_2x2.png", export.mtl_data)
        self.assertEqual(len(export.images), 1)
        self.assertTrue(export.images[0].data.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_exporter_uses_texture_command_tile_without_exporting_mip_levels(self):
        texture_data = [
            SimpleNamespace(
                raw_data=(
                    _rgba16(255, 0, 0)
                    + _rgba16(0, 255, 0)
                    + _rgba16(0, 0, 255)
                    + _rgba16(255, 255, 255)
                    + _rgba16(255, 255, 0)
                )
            )
        ]
        vertex_data = (
            _vertex(0, 0, 0, 0, 0)
            + _vertex(1, 0, 0, 32, 0)
            + _vertex(0, 1, 0, 0, 32)
        )
        commands = b"".join(
            (
                _g_texture(level=1),
                _words(0xFD100000, 0x00000000),
                _settile(fmt=0, size=2, tile=7),
                _words(0xF3000000, 0x07000000),
                _settile(fmt=0, size=2, tile=0),
                _settilesize(tile=0, width=2, height=2),
                _settile(fmt=0, size=2, tile=1, tmem=1),
                _settilesize(tile=1, width=1, height=1),
                b"\x01\x00\x30\x06\x00\x00\x00\x00",
                b"\x05\x00\x02\x04\x00\x00\x00\x00",
                b"\xdf\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        display_list = DisplayList(
            raw_data=commands,
            raw_vertex_data=vertex_data,
            vertex_pointer=0,
            offset=0,
        )

        export = TexturedObjExporter(texture_data).export([display_list], "model.mtl")

        self.assertIn("usemtl tex_0_pal_none_f0_s2_2x2", export.obj_data)
        self.assertIn("map_Kd textures/tex_0_pal_none_f0_s2_2x2.png", export.mtl_data)
        self.assertNotIn("mip", export.mtl_data)
        self.assertEqual(
            [image.filename for image in export.images],
            ["textures/tex_0_pal_none_f0_s2_2x2.png"],
        )
        self.assertEqual(_png_rgba(export.images[0].data)[0], (2, 2))

    def test_exporter_writes_full_ci4_texture_without_mip_levels(self):
        palette = b"".join(
            (
                _rgba16(0, 0, 0),
                _rgba16(255, 0, 0),
                _rgba16(0, 255, 0),
                _rgba16(0, 0, 255),
                _rgba16(255, 255, 255),
            )
        )
        texture_data = [
            SimpleNamespace(raw_data=b"\x01\x23" + (b"\x00" * 6) + b"\x40"),
            SimpleNamespace(raw_data=palette),
        ]
        vertex_data = (
            _vertex(0, 0, 0, 0, 0)
            + _vertex(1, 0, 0, 32, 0)
            + _vertex(0, 1, 0, 0, 32)
        )
        commands = b"".join(
            (
                _g_texture(level=1),
                _words(0xFD400000, 0x00000000),
                _settile(fmt=2, size=0, tile=7),
                _words(0xF3000000, 0x07000000),
                _settile(fmt=2, size=0, tile=0),
                _settilesize(tile=0, width=2, height=2),
                _settile(fmt=2, size=0, tile=1, tmem=1),
                _settilesize(tile=1, width=1, height=1),
                _words(0xFD100000, 0x00000001),
                _words(0xF0000000, 0x0703C000),
                b"\x01\x00\x30\x06\x00\x00\x00\x00",
                b"\x05\x00\x02\x04\x00\x00\x00\x00",
                b"\xdf\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        display_list = DisplayList(
            raw_data=commands,
            raw_vertex_data=vertex_data,
            vertex_pointer=0,
            offset=0,
        )

        export = TexturedObjExporter(texture_data).export([display_list], "model.mtl")

        self.assertEqual(
            [image.filename for image in export.images],
            ["textures/tex_0_pal_1_f2_s0_2x2.png"],
        )
        self.assertNotIn("mip", export.mtl_data)
        self.assertEqual(_png_rgba(export.images[0].data)[0], (2, 2))

    def test_test_mipmap_export_stitches_rows_for_test_textures(self):
        palette = b"".join(
            _rgba16(value, value, value)
            for value in range(0, 256, 17)
        )
        ci4_pixels = []
        for row in range(64):
            ci4_pixels.extend(tuple(range(16)) * 2)
        for row in range(32):
            ci4_pixels.extend(tuple(range(16)))
        ci4_pixels.extend([2] * (8 * 16))
        ci4_pixels.extend([3] * (4 * 8))
        ci4_pixels.extend([0] * (2944 - len(ci4_pixels)))
        texture_data = [
            SimpleNamespace(raw_data=_ci4_indices(*ci4_pixels)),
            SimpleNamespace(raw_data=palette),
            SimpleNamespace(
                raw_data=_indexed_rgba16(
                    1,
                    2,
                    3,
                    4,
                    4,
                    3,
                    2,
                    1,
                    2,
                    1,
                    4,
                    3,
                    3,
                    4,
                    1,
                    2,
                    1,
                    1,
                    2,
                    2,
                    0,
                    0,
                    0,
                    0,
                    4,
                    4,
                    3,
                    3,
                    0,
                    0,
                    0,
                    0,
                )
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            filepaths = export_test_mipmap(
                texture_data,
                folderpath=tmpdir,
                width=4,
                height=8,
            )

            self.assertEqual(
                [filepath.name for filepath in filepaths],
                [
                    "tex_2_pal_none_f0_s2_4x8_base_4x8.png",
                    "tex_2_pal_none_f0_s2_4x8.png",
                    "tex_2_pal_none_f0_s2_4x8_mip1_4x4.png",
                    "tex_2_pal_none_f0_s2_4x8_mip2_2x2.png",
                    "tex_0_pal_1_f2_s0_32x64_base_32x92.png",
                    "tex_0_pal_1_f2_s0_32x64.png",
                    "tex_0_pal_1_f2_s0_32x64_mip1_16x32.png",
                    "tex_0_pal_1_f2_s0_32x64_mip2_8x16.png",
                    "tex_0_pal_1_f2_s0_32x64_mip3_4x8.png",
                ],
            )
            self.assertEqual(_png_rgba(filepaths[0].read_bytes())[0], (4, 8))
            self.assertEqual(
                _png_rgba(filepaths[2].read_bytes()),
                (
                    (4, 4),
                    _indexed_rgba(
                        1,
                        2,
                        3,
                        4,
                        2,
                        1,
                        4,
                        3,
                        2,
                        1,
                        4,
                        3,
                        1,
                        2,
                        3,
                        4,
                    ),
                ),
            )
            self.assertEqual(
                _png_rgba(filepaths[3].read_bytes()),
                (
                    (2, 2),
                    _indexed_rgba(4, 3, 3, 4),
                ),
            )
            self.assertEqual(_png_rgba(filepaths[4].read_bytes())[0], (32, 92))
            tex0_size, tex0_pixels = _png_rgba(filepaths[5].read_bytes())
            self.assertEqual(tex0_size, (32, 64))
            tex0_mip1_size, tex0_mip1_pixels = _png_rgba(filepaths[6].read_bytes())
            self.assertEqual(tex0_mip1_size, (16, 32))
            self.assertEqual(_png_rgba(filepaths[7].read_bytes())[0], (8, 16))
            self.assertEqual(_png_rgba(filepaths[8].read_bytes())[0], (4, 8))
            expected_row0 = decode_texture(
                _ci4_indices(*(tuple(range(16)) * 2)),
                fmt=2,
                size=0,
                width=32,
                height=1,
                palette_data=palette,
            )
            expected_row1 = decode_texture(
                _ci4_indices(
                    *(
                        tuple(range(8, 16))
                        + tuple(range(8))
                        + tuple(range(8, 16))
                        + tuple(range(8))
                    )
                ),
                fmt=2,
                size=0,
                width=32,
                height=1,
                palette_data=palette,
            )
            self.assertEqual(tex0_pixels[: 32 * 4], expected_row0)
            self.assertEqual(tex0_pixels[32 * 4 : 64 * 4], expected_row1)
            expected_mip1_row0 = decode_texture(
                _ci4_indices(*tuple(range(16))),
                fmt=2,
                size=0,
                width=16,
                height=1,
                palette_data=palette,
            )
            expected_mip1_row1 = decode_texture(
                _ci4_indices(*(tuple(range(8, 16)) + tuple(range(8)))),
                fmt=2,
                size=0,
                width=16,
                height=1,
                palette_data=palette,
            )
            self.assertEqual(tex0_mip1_pixels[: 16 * 4], expected_mip1_row0)
            self.assertEqual(
                tex0_mip1_pixels[16 * 4 : 32 * 4],
                expected_mip1_row1,
            )

    def test_save_textured_obj_export_writes_assets(self):
        texture_data = [SimpleNamespace(raw_data=_rgba16(255, 0, 0))]
        commands = b"".join(
            (
                _words(0xFD100000, 0x00000000),
                _words(0xF3000000, 0x07000000),
                _words(0xF5100000, 0x00000000),
                _words(0xF2000000, 0x00000000),
                b"\x01\x00\x30\x06\x00\x00\x00\x00",
                b"\x05\x00\x02\x04\x00\x00\x00\x00",
                b"\xdf\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        display_list = DisplayList(
            raw_data=commands,
            raw_vertex_data=_vertex(0, 0, 0, 0, 0) * 3,
            vertex_pointer=0,
            offset=0,
        )
        export = TexturedObjExporter(texture_data).export([display_list], "model.mtl")

        with tempfile.TemporaryDirectory() as tmpdir:
            export_folder = Path(tmpdir) / "nested"
            written_paths = save_textured_obj_export(
                export,
                "model.obj",
                export_folder,
            )

            self.assertEqual(
                written_paths,
                [
                    export_folder / "model.obj",
                    export_folder / "model.mtl",
                    export_folder
                    / "textures"
                    / "tex_0_pal_none_f0_s2_1x1.png",
                ],
            )
            self.assertTrue((export_folder / "model.obj").exists())
            self.assertTrue((export_folder / "model.mtl").exists())
            self.assertTrue(written_paths[-1].exists())


if __name__ == "__main__":
    unittest.main()
