import tempfile
import unittest

from inspect import signature
from pathlib import Path
from types import SimpleNamespace

from dk64_lib.data_types.geometry import GeometryData
from dk64_lib.f3dex2.display_list import DisplayList
from dk64_lib.rom import Rom


def _fake_rom() -> Rom:
    rom = Rom.__new__(Rom)
    rom.rom_fh = SimpleNamespace(close=lambda: None)
    return rom


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


def _vertex(x: int, y: int, z: int, u: int, v: int) -> bytes:
    return (
        x.to_bytes(2, "big", signed=True)
        + y.to_bytes(2, "big", signed=True)
        + z.to_bytes(2, "big", signed=True)
        + b"\x00\x00"
        + u.to_bytes(2, "big", signed=True)
        + v.to_bytes(2, "big", signed=True)
        + b"\xff\xff\xff\xff"
    )


def _textured_triangle_display_list() -> DisplayList:
    return DisplayList(
        raw_data=b"".join(
            (
                _words(0xD7001802, 0xFFFFFFFF),
                _words(0xFD100000, 0x00000000),
                _words(0xF5100000, 0x07000000),
                _words(0xF3000000, 0x07000000),
                _words(0xF5100000, 0x00000000),
                _words(0xF2000000, 0x00004004),
                b"\x01\x00\x30\x06\x00\x00\x00\x00",
                b"\x05\x00\x02\x04\x00\x00\x00\x00",
                b"\xdf\x00\x00\x00\x00\x00\x00\x00",
            )
        ),
        raw_vertex_data=(
            _vertex(0, 0, 0, 0, 0)
            + _vertex(1, 0, 0, 64, 0)
            + _vertex(0, 1, 0, 0, 64)
        ),
        vertex_pointer=0,
        offset=0,
    )


class _FakeGeometry:
    is_pointer = False

    def __init__(self):
        self.save_call = None

    def save_to_obj(
        self,
        filename: str,
        folderpath: str = ".",
        include_textures: bool = True,
        texture_folder: str = "textures",
    ) -> list[Path]:
        self.save_call = {
            "filename": filename,
            "folderpath": folderpath,
            "include_textures": include_textures,
            "texture_folder": texture_folder,
        }
        folder = Path(folderpath)
        obj_path = folder / filename
        obj_path.parent.mkdir(parents=True, exist_ok=True)
        obj_path.write_text("obj")
        if not include_textures:
            return [obj_path]

        mtl_path = obj_path.with_suffix(".mtl")
        texture_path = folder / texture_folder / "texture.png"
        mtl_path.write_text("mtl")
        texture_path.parent.mkdir(parents=True, exist_ok=True)
        texture_path.write_bytes(b"png")
        return [obj_path, mtl_path, texture_path]

    def save_to_dae(
        self,
        filename: str,
        folderpath: str = ".",
        include_textures: bool = True,
        texture_folder: str = "textures",
    ) -> list[Path]:
        self.save_call = {
            "filename": filename,
            "folderpath": folderpath,
            "include_textures": include_textures,
            "texture_folder": texture_folder,
        }
        folder = Path(folderpath)
        dae_path = folder / filename
        dae_path.parent.mkdir(parents=True, exist_ok=True)
        dae_path.write_text("dae")
        if not include_textures:
            return [dae_path]

        texture_path = folder / texture_folder / "texture.png"
        texture_path.parent.mkdir(parents=True, exist_ok=True)
        texture_path.write_bytes(b"png")
        return [dae_path, texture_path]

    def save_to_gltf(
        self,
        filename: str,
        folderpath: str = ".",
        include_textures: bool = True,
        texture_folder: str = "textures",
    ) -> list[Path]:
        self.save_call = {
            "filename": filename,
            "folderpath": folderpath,
            "include_textures": include_textures,
            "texture_folder": texture_folder,
        }
        folder = Path(folderpath)
        gltf_path = folder / filename
        bin_path = gltf_path.with_suffix(".bin")
        gltf_path.parent.mkdir(parents=True, exist_ok=True)
        gltf_path.write_text("gltf")
        bin_path.write_bytes(b"bin")
        if not include_textures:
            return [gltf_path, bin_path]

        texture_path = folder / texture_folder / "texture.png"
        texture_path.parent.mkdir(parents=True, exist_ok=True)
        texture_path.write_bytes(b"png")
        return [gltf_path, bin_path, texture_path]

    def save_to_glb(
        self,
        filename: str,
        folderpath: str = ".",
        include_textures: bool = True,
    ) -> list[Path]:
        self.save_call = {
            "filename": filename,
            "folderpath": folderpath,
            "include_textures": include_textures,
        }
        folder = Path(folderpath)
        glb_path = folder / filename
        glb_path.parent.mkdir(parents=True, exist_ok=True)
        glb_path.write_bytes(b"glb")
        return [glb_path]


class RomExportTest(unittest.TestCase):
    def test_export_defaults_include_textures(self):
        self.assertIs(
            signature(GeometryData.save_to_obj)
            .parameters["include_textures"]
            .default,
            True,
        )
        self.assertIs(
            signature(GeometryData.save_to_dae)
            .parameters["include_textures"]
            .default,
            True,
        )
        self.assertIs(
            signature(GeometryData.save_to_gltf)
            .parameters["include_textures"]
            .default,
            True,
        )
        self.assertIs(
            signature(GeometryData.save_to_glb)
            .parameters["include_textures"]
            .default,
            True,
        )
        self.assertIs(
            signature(Rom.export_geometries)
            .parameters["include_textures"]
            .default,
            True,
        )
        self.assertIs(
            signature(Rom.export_all).parameters["include_textures"].default,
            True,
        )
        self.assertEqual(
            signature(Rom.export_geometries)
            .parameters["geometry_format"]
            .default,
            "glb",
        )
        self.assertEqual(
            signature(Rom.export_all)
            .parameters["geometry_format"]
            .default,
            "glb",
        )

    def test_safe_filename(self):
        self.assertEqual(
            Rom._safe_filename("K. Rool Barrel: Lanky's Maze"),
            "K._Rool_Barrel_Lanky_s_Maze",
        )
        self.assertEqual(Rom._safe_filename("..."), "asset")

    def test_export_geometries_writes_glbs_by_default_and_pointer_files(self):
        rom = _fake_rom()
        geometry = _FakeGeometry()
        rom.geometry_tables = [
            geometry,
            SimpleNamespace(is_pointer=True, pointer=0),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = Rom.export_geometries(rom, tmpdir)
            root = Path(tmpdir)

            glb_path = root / "000_Test_Map.glb"
            pointer_path = root / "001_Funky_s_Store.pointer.txt"

            self.assertEqual(geometry.save_call["filename"], glb_path.name)
            self.assertEqual(geometry.save_call["include_textures"], True)
            self.assertEqual(paths, [glb_path, pointer_path])
            self.assertTrue(glb_path.exists())
            self.assertEqual(pointer_path.read_text(), "points_to=0\n")

    def test_export_geometries_can_skip_textures(self):
        rom = _fake_rom()
        geometry = _FakeGeometry()
        rom.geometry_tables = [geometry]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = Rom.export_geometries(rom, tmpdir, include_textures=False)
            root = Path(tmpdir)

            self.assertEqual(paths, [root / "000_Test_Map.glb"])
            self.assertEqual(geometry.save_call["include_textures"], False)
            self.assertFalse((root / "000_Test_Map.mtl").exists())

    def test_export_geometries_can_write_obj(self):
        rom = _fake_rom()
        geometry = _FakeGeometry()
        rom.geometry_tables = [geometry]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = Rom.export_geometries(rom, tmpdir, geometry_format="obj")
            root = Path(tmpdir)

            obj_path = root / "000_Test_Map.obj"
            mtl_path = root / "000_Test_Map.mtl"
            texture_path = root / "textures" / "texture.png"
            self.assertEqual(paths, [obj_path, mtl_path, texture_path])
            self.assertEqual(geometry.save_call["filename"], obj_path.name)
            self.assertEqual(geometry.save_call["include_textures"], True)
            self.assertTrue(obj_path.exists())
            self.assertTrue(mtl_path.exists())
            self.assertTrue(texture_path.exists())

    def test_export_geometries_can_write_dae(self):
        rom = _fake_rom()
        geometry = _FakeGeometry()
        rom.geometry_tables = [geometry]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = Rom.export_geometries(rom, tmpdir, geometry_format="dae")
            root = Path(tmpdir)

            dae_path = root / "000_Test_Map.dae"
            texture_path = root / "textures" / "texture.png"
            self.assertEqual(paths, [dae_path, texture_path])
            self.assertEqual(geometry.save_call["filename"], dae_path.name)
            self.assertEqual(geometry.save_call["include_textures"], True)
            self.assertTrue(dae_path.exists())
            self.assertTrue(texture_path.exists())

    def test_export_geometries_can_write_gltf(self):
        rom = _fake_rom()
        geometry = _FakeGeometry()
        rom.geometry_tables = [geometry]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = Rom.export_geometries(rom, tmpdir, geometry_format="gltf")
            root = Path(tmpdir)

            gltf_path = root / "000_Test_Map.gltf"
            bin_path = root / "000_Test_Map.bin"
            texture_path = root / "textures" / "texture.png"
            self.assertEqual(paths, [gltf_path, bin_path, texture_path])
            self.assertEqual(geometry.save_call["filename"], gltf_path.name)
            self.assertEqual(geometry.save_call["include_textures"], True)
            self.assertTrue(gltf_path.exists())
            self.assertTrue(bin_path.exists())
            self.assertTrue(texture_path.exists())

    def test_export_geometries_can_write_glb(self):
        rom = _fake_rom()
        geometry = _FakeGeometry()
        rom.geometry_tables = [geometry]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = Rom.export_geometries(rom, tmpdir, geometry_format="glb")
            root = Path(tmpdir)

            glb_path = root / "000_Test_Map.glb"
            self.assertEqual(paths, [glb_path])
            self.assertEqual(geometry.save_call["filename"], glb_path.name)
            self.assertEqual(geometry.save_call["include_textures"], True)
            self.assertTrue(glb_path.exists())

    def test_export_geometries_rejects_unknown_format(self):
        rom = _fake_rom()
        rom.geometry_tables = []

        with self.assertRaisesRegex(ValueError, "geometry_format"):
            Rom.export_geometries(rom, geometry_format="fbx")

    def test_export_text(self):
        rom = _fake_rom()
        rom.get_text_data = lambda: [
            SimpleNamespace(
                text_lines=[
                    SimpleNamespace(text="HELLO"),
                    SimpleNamespace(text="WORLD"),
                ]
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = Rom.export_text(rom, tmpdir)
            text_path = Path(tmpdir) / "text_000.txt"

            self.assertEqual(paths, [text_path])
            self.assertEqual(text_path.read_text(), "0000: HELLO\n0001: WORLD")

    def test_export_cutscenes(self):
        rom = _fake_rom()
        rom.get_cutscene_data = lambda: [
            SimpleNamespace(offset=0x1234, raw_data=b"cutscene")
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = Rom.export_cutscenes(rom, tmpdir)
            cutscene_path = Path(tmpdir) / "cutscene_000_offset_00001234.bin"

            self.assertEqual(paths, [cutscene_path])
            self.assertEqual(cutscene_path.read_bytes(), b"cutscene")

    def test_export_textures_writes_geometry_pngs(self):
        rom = _fake_rom()
        rom.geometry_tables = [
            SimpleNamespace(
                is_pointer=False,
                display_lists=[_textured_triangle_display_list()],
            )
        ]
        rom.get_geometry_texture_data = lambda: [
            SimpleNamespace(
                raw_data=(
                    _rgba16(255, 0, 0)
                    + _rgba16(0, 255, 0)
                    + _rgba16(0, 0, 255)
                    + _rgba16(255, 255, 255)
                )
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            texture_paths = Rom.export_textures(rom, root / "textures")
            texture_path = (
                root
                / "textures"
                / "table_25"
                / "tex_0_pal_none_f0_s2_2x2.png"
            )

            self.assertEqual(texture_paths, [texture_path])
            self.assertTrue(texture_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(list((root / "textures").rglob("*.bin")), [])

    def test_export_assets_write_raw_table_entries(self):
        rom = _fake_rom()

        def generate_rom_table_data(tables: list[int]):
            table_id = tables[0]
            yield {"offset": table_id, "raw_data": table_id.to_bytes(1, "big")}

        rom.generate_rom_table_data = generate_rom_table_data

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            asset_paths = Rom.export_assets(rom, root / "assets", tables=(1, 8))

            self.assertEqual(
                asset_paths,
                [
                    root / "assets" / "table_01" / "000000_offset_00000001.bin",
                    root / "assets" / "table_08" / "000000_offset_00000008.bin",
                ],
            )
            self.assertEqual(asset_paths[-1].read_bytes(), b"\x08")

    def test_export_all_combines_supported_exports(self):
        rom = _fake_rom()
        rom.export_geometries = (
            lambda folderpath, include_textures=True, geometry_format="glb": [
                Path(folderpath) / f"textures_{include_textures}.{geometry_format}"
            ]
        )
        rom.export_textures = lambda folderpath: [Path(folderpath) / "texture.png"]
        rom.export_text = lambda folderpath: [Path(folderpath) / "text.txt"]
        rom.export_cutscenes = lambda folderpath: [Path(folderpath) / "cutscene.bin"]
        rom.export_assets = lambda folderpath: [Path(folderpath) / "asset.bin"]

        with tempfile.TemporaryDirectory() as tmpdir:
            exported = Rom.export_all(
                rom,
                tmpdir,
                include_textures=False,
                geometry_format="dae",
            )
            root = Path(tmpdir)

            self.assertEqual(
                exported,
                {
                    "geometries": [root / "geometries" / "textures_False.dae"],
                    "textures": [root / "textures" / "texture.png"],
                    "text": [root / "text" / "text.txt"],
                    "cutscenes": [root / "cutscenes" / "cutscene.bin"],
                    "assets": [root / "assets" / "asset.bin"],
                },
            )

            exported_without_assets = Rom.export_all(rom, tmpdir, include_assets=False)
            self.assertNotIn("assets", exported_without_assets)


if __name__ == "__main__":
    unittest.main()
