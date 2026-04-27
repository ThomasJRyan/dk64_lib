import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace

from dk64_lib.f3dex2.display_list import DisplayList
from dk64_lib.f3dex2.texture_export import (
    TexturedObjExporter,
    decode_texture,
    rgba_to_png,
    save_textured_obj_export,
)


def _words(word0: int, word1: int) -> bytes:
    return word0.to_bytes(4, "big") + word1.to_bytes(4, "big")


def _rgba16(red: int, green: int, blue: int, alpha: int = 255) -> bytes:
    raw = (
        ((red * 31 // 255) << 11)
        | ((green * 31 // 255) << 6)
        | ((blue * 31 // 255) << 1)
        | (1 if alpha else 0)
    )
    return raw.to_bytes(2, "big")


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

    def test_exporter_uses_texture_command_tile_for_mipmapped_textures(self):
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
            _vertex(0, 0, 0, 0, 0)
            + _vertex(1, 0, 0, 32, 0)
            + _vertex(0, 1, 0, 0, 32)
        )
        commands = b"".join(
            (
                _words(0xD7000002, 0xFFFFFFFF),
                _words(0xFD100000, 0x00000000),
                _words(0xF5100000, 0x07000000),
                _words(0xF3000000, 0x07000000),
                _words(0xF5100000, 0x00000000),
                _words(0xF2000000, 0x00004004),
                _words(0xF5100000, 0x01000000),
                _words(0xF2000000, 0x01000000),
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
        self.assertEqual(
            export.images[0].filename,
            "textures/tex_0_pal_none_f0_s2_2x2.png",
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
