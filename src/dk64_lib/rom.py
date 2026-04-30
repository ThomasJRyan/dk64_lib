import zlib

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryFile
from functools import cache, cached_property
from re import sub

from typing import Literal, Generator

from dk64_lib.data_types import (
    ActorGeometryData,
    AnimationCodeData,
    AnimationData,
    AutowalkData,
    CritterData,
    CutsceneData,
    DKTVInputData,
    ExitData,
    FloorCollisionData,
    GeometryData,
    InstanceScriptData,
    MidiMusicData,
    ModelTwoGeometryData,
    PathData,
    RaceCheckpointData,
    SetupData,
    SpawnerData,
    StubTableData,
    TextData,
    TextureData,
    TriggerData,
    UnknownTable19Data,
    UncompressedFileSizeData,
)
from dk64_lib.data_types.table_stubs import STUB_TABLE_DATA_TYPES
from dk64_lib.f3dex2.texture_export import (
    TextureAnimationFrames,
    TextureImageFile,
    TexturedObjExporter,
    decode_texture,
    rgba_to_png,
)
from dk64_lib.constants import MAPS
from dk64_lib.file_io import get_bytes, get_char, get_long, get_short


RAW_EXPORT_TABLES = (
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
)
GUESSED_TEXTURE_TABLES = (7, 14, 25)
# Size guesses adapted from dk64-hacking-scripts' texture_size_guesser.py.
TEXTURE_SIZE_GUESSES = {
    0x1000: (32, 64),
    0x800: (32, 32),
    0xFC0: (48, 42),
    0xAA0: (32, 44),
    0xF20: (44, 44),
}


@dataclass(frozen=True)
class TableEntry:
    index: int
    start: int
    finish: int

    @property
    def size(self) -> int:
        return self.finish - self.start

    @property
    def is_empty(self) -> bool:
        return self.size == 0


class Rom:
    REGIONS_AND_POINTER_TABLE_OFFSETS = {
        0x45: ("us", 0x101C50),
        0x50: ("pal", 0x1038D0),
        0x4A: ("jp", 0x1039C0),
    }

    def __init__(self, rom_path: str):
        """Class representation of a DK64 ROM

        Args:
            rom_path (str): Path to ROM file
        """
        self.rom_path = Path(rom_path).resolve()

        # Copy ROM data to a temporary file
        with open(rom_path, "rb") as rom_file:
            self.rom_fh = TemporaryFile()
            self.rom_fh.write(rom_file.read())
            self.rom_fh.seek(0)

        endianness = int.from_bytes(self.rom_fh.read(1), "big")
        assert (
            endianness == 0x80
        ), "ROM is little endian. Convert to big endian and re-run"

    def __del__(self):
        """Closes the file on deletion"""
        self.rom_fh.close()

    @staticmethod
    def _safe_filename(name: str) -> str:
        safe_name = sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
        return safe_name or "asset"

    @staticmethod
    def _write_bytes(path: Path, data: bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    @staticmethod
    def _write_text(path: Path, data: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
        return path

    @cached_property
    def release_or_kiosk(self) -> Literal["release", "kiosk"]:
        """Read the release/kiosk flag to check game version

        Returns:
            Literal['release', 'kiosk']: release or kiosk
        """
        release_or_kiosk = get_char(self.rom_fh, 0x3D, keep_last_pos=True)
        if release_or_kiosk == 0x50:
            return "kiosk"
        return "release"

    @cached_property
    def region(self) -> Literal["us", "pal", "jp", "kiosk"]:
        """Read the region flag and return which region the ROM is

        Raises:
            KeyError: Raised when an unidentified region is found

        Returns:
            Literal['us', 'pal', 'jp', 'kiosk']: Game's region
        """
        region = get_char(self.rom_fh, 0x3E, keep_last_pos=True)
        if self.release_or_kiosk == "kiosk":
            return "kiosk"
        try:
            return self.REGIONS_AND_POINTER_TABLE_OFFSETS[region][0]
        except KeyError:
            raise KeyError(f"This region ({region}) is invalid")

    @cached_property
    def pointer_table_offset(self) -> Literal[0x101C50, 0x1038D0, 0x1039C0, 0x1A7C20]:
        """Gets the pointer table offset for the ROM

        Returns:
            Literal[0x101C50, 0x1038D0, 0x1039C0, 0x1A7C20]: Pointer offset
        """
        region = get_char(self.rom_fh, 0x3E, keep_last_pos=True)
        if self.release_or_kiosk == "kiosk":
            return 0x1A7C20
        return self.REGIONS_AND_POINTER_TABLE_OFFSETS[region][1]

    @cached_property
    def text_tables(self) -> list[TextData]:
        """Returns a list of all text data

        Returns:
            list[TextData]: The game's text data
        """
        return [text_data for text_data in self.get_text_data()]

    @cached_property
    def geometry_tables(self):
        return [geometry_data for geometry_data in self.get_geometry_data()]

    def export_textures(
        self,
        folderpath: str | Path = "exports/textures",
        include_guessed: bool = True,
    ) -> list[Path]:
        """Export decoded geometry textures as PNG images."""
        root = Path(folderpath)
        return [
            self._write_bytes(root / image.filename, image.data)
            for image in self.create_texture_images(
                texture_folder="table_25",
                include_guessed=include_guessed,
            )
        ]

    def create_texture_images(
        self,
        texture_folder: str = "table_25",
        include_guessed: bool = True,
    ) -> tuple[TextureImageFile, ...]:
        """Create PNG images for texture entries with known or guessed metadata."""
        display_lists = tuple(
            display_list
            for geometry_data in self.geometry_tables
            if not geometry_data.is_pointer
            for display_list in geometry_data.display_lists
        )
        exporter = TexturedObjExporter(self.get_geometry_texture_data())
        referenced_geometry_texture_indices = exporter.texture_image_indices(
            display_lists
        )
        images = list(
            exporter.export_texture_images(
                display_lists,
                texture_folder=texture_folder,
            )
        )
        if include_guessed:
            images.extend(
                self._guessed_texture_images(
                    referenced_geometry_texture_indices=set(
                        referenced_geometry_texture_indices
                    ),
                )
            )
        return tuple(images)

    def _guessed_texture_images(
        self,
        referenced_geometry_texture_indices: set[int],
    ) -> tuple[TextureImageFile, ...]:
        images = list()
        for table_id in GUESSED_TEXTURE_TABLES:
            table_folder = f"table_{table_id:02d}"
            for texture_index, table_data in enumerate(
                self.generate_rom_table_data([table_id])
            ):
                if (
                    table_id == 25
                    and texture_index in referenced_geometry_texture_indices
                ):
                    continue
                raw_data = table_data["raw_data"]
                dimensions = TEXTURE_SIZE_GUESSES.get(len(raw_data))
                if dimensions is None:
                    continue

                width, height = dimensions
                rgba = decode_texture(
                    raw_data,
                    fmt=0,
                    size=2,
                    width=width,
                    height=height,
                )
                images.append(
                    TextureImageFile(
                        filename=(
                            f"{table_folder}/"
                            f"{texture_index:06d}_"
                            f"offset_{table_data['offset']:08x}_"
                            f"guess_f0_s2_{width}x{height}.png"
                        ),
                        data=rgba_to_png(width, height, rgba),
                    )
                )
        return tuple(images)

    def export_text(self, folderpath: str | Path = "exports/text") -> list[Path]:
        """Export parsed text tables as UTF-8 text files."""
        exported_paths = list()
        root = Path(folderpath)
        for table_index, text_data in enumerate(self.get_text_data()):
            lines = [
                f"{line_index:04d}: {line.text}"
                for line_index, line in enumerate(text_data.text_lines)
            ]
            filename = f"text_{table_index:03d}.txt"
            exported_paths.append(self._write_text(root / filename, "\n".join(lines)))
        return exported_paths

    def export_cutscenes(
        self,
        folderpath: str | Path = "exports/cutscenes",
    ) -> list[Path]:
        """Export raw cutscene table entries."""
        exported_paths = list()
        root = Path(folderpath)
        for cutscene_index, cutscene_data in enumerate(self.get_cutscene_data()):
            filename = (
                f"cutscene_{cutscene_index:03d}_"
                f"offset_{cutscene_data.offset:08x}.bin"
            )
            exported_paths.append(
                self._write_bytes(root / filename, cutscene_data.raw_data)
            )
        return exported_paths

    def export_geometries(
        self,
        folderpath: str | Path = "exports/geometries",
        include_textures: bool = True,
        geometry_format: Literal["obj", "dae", "gltf", "glb"] = "glb",
        animated_texture_frames: TextureAnimationFrames | None = None,
        animation_frame_duration: int = 4,
    ) -> list[Path]:
        """Export geometry tables as GLB, OBJ, DAE, or glTF files."""
        geometry_saver_names = {
            "obj": "save_to_obj",
            "dae": "save_to_dae",
            "gltf": "save_to_gltf",
            "glb": "save_to_glb",
        }
        try:
            save_geometry_name = geometry_saver_names[geometry_format]
        except KeyError:
            raise ValueError("geometry_format must be 'obj', 'dae', 'gltf', or 'glb'")

        exported_paths = list()
        root = Path(folderpath)
        root.mkdir(parents=True, exist_ok=True)

        for geometry_index, geometry_data in enumerate(self.geometry_tables):
            map_name = MAPS[geometry_index] if geometry_index < len(MAPS) else "unknown"
            filename_stem = self._safe_filename(f"{geometry_index:03d}_{map_name}")

            if geometry_data.is_pointer:
                pointer_path = root / f"{filename_stem}.pointer.txt"
                exported_paths.append(
                    self._write_text(pointer_path, f"points_to={geometry_data.pointer}\n")
                )
                continue

            geometry_path = root / f"{filename_stem}.{geometry_format}"
            save_geometry = getattr(geometry_data, save_geometry_name)
            save_kwargs = {"include_textures": include_textures}
            if geometry_format == "dae" and animated_texture_frames is not None:
                save_kwargs.update(
                    {
                        "animated_texture_frames": animated_texture_frames,
                        "animation_frame_duration": animation_frame_duration,
                    }
                )
            written_paths = save_geometry(
                geometry_path.name,
                str(root),
                **save_kwargs,
            )
            exported_paths.extend(written_paths)

        return exported_paths

    def export_assets(
        self,
        folderpath: str | Path = "exports/assets",
        tables: tuple[int, ...] = RAW_EXPORT_TABLES,
    ) -> list[Path]:
        """Export raw entries from supported pointer tables."""
        exported_paths = list()
        root = Path(folderpath)
        for table_id in tables:
            table_folder = root / f"table_{table_id:02d}"
            for entry_index, table_data in enumerate(
                self.generate_rom_table_data([table_id])
            ):
                filename = (
                    f"{entry_index:06d}_"
                    f"offset_{table_data['offset']:08x}.bin"
                )
                exported_paths.append(
                    self._write_bytes(table_folder / filename, table_data["raw_data"])
                )
        return exported_paths

    def export_raw_tables(
        self,
        folderpath: str | Path = "exports/raw_tables",
        tables: tuple[int, ...] = RAW_EXPORT_TABLES,
    ) -> list[Path]:
        """Export raw entries from supported pointer tables."""
        return self.export_assets(folderpath, tables)

    def export_all(
        self,
        folderpath: str | Path = "exports",
        include_textures: bool = True,
        include_assets: bool = True,
        geometry_format: Literal["obj", "dae", "gltf", "glb"] = "glb",
        animated_texture_frames: TextureAnimationFrames | None = None,
        animation_frame_duration: int = 4,
    ) -> dict[str, list[Path]]:
        """Export all currently supported ROM data to organized folders."""
        root = Path(folderpath)
        geometry_kwargs = {
            "include_textures": include_textures,
            "geometry_format": geometry_format,
        }
        if animated_texture_frames is not None:
            geometry_kwargs.update(
                {
                    "animated_texture_frames": animated_texture_frames,
                    "animation_frame_duration": animation_frame_duration,
                }
            )
        exported = {
            "geometries": self.export_geometries(
                root / "geometries",
                **geometry_kwargs,
            ),
            "textures": self.export_textures(root / "textures"),
            "text": self.export_text(root / "text"),
            "cutscenes": self.export_cutscenes(root / "cutscenes"),
        }
        if include_assets:
            exported["assets"] = self.export_assets(root / "assets")
        return exported

    @cache
    def _read_table_entries(self, start: int, size: int) -> tuple[TableEntry, ...]:
        """Read all pointer entries for a table."""
        entries = list()
        for entry_index in range(size):
            pointer_offset = start + (entry_index * 4)
            entry_start = self.pointer_table_offset + (
                get_long(self.rom_fh, pointer_offset) & 0x7FFFFFFF
            )
            entry_finish = self.pointer_table_offset + (
                get_long(self.rom_fh, pointer_offset + 4) & 0x7FFFFFFF
            )
            entries.append(TableEntry(entry_index, entry_start, entry_finish))
        return tuple(entries)

    def _extract_table_data(self, start: int, size: int) -> Generator[dict, None, None]:
        """An internal generator for extracting the data that a table points to

        Args:
            start (int): Starting offset of the table
            size (int): Size of the table

        Yields:
            Generator[dict, None, None]: The data the table entry points to
        """
        for entry in self._read_table_entries(start, size):
            if entry.is_empty:
                continue
            indic = get_short(self.rom_fh, entry.start)
            table_data = get_bytes(self.rom_fh, entry.size, entry.start)
            if indic == 0x1F8B:
                table_data = zlib.decompress(table_data, (15 + 32))
            if not table_data:
                continue
            yield dict(
                raw_data=table_data,
                offset=entry.start,
                size=entry.size,
                was_compressed=True if indic == 0x1F8B else False,
                rom=self,
            )

    def generate_rom_table_data(self, tables: list[int]) -> Generator[dict, None, None]:
        """A generator that iterates through the various table data in the ROM

        Args:
            tables (list[int]): Which tables to iterate through

        Yields:
            Generator[dict, None, None]: The table data in bytes
        """
        for table_offset in tables:
            if self.release_or_kiosk == "kiosk":
                table_offset -= 1
            table_size = get_long(
                self.rom_fh, self.pointer_table_offset + (32 * 4) + (table_offset * 4)
            )
            table_start = self.pointer_table_offset + get_long(
                self.rom_fh, self.pointer_table_offset + (table_offset * 4)
            )
            for data in self._extract_table_data(table_start, table_size):
                yield data

    @cache
    def get_texture_data(self) -> list[TextureData]:
        """A function for fetching the texture data

        Yields:
            list[TextureData]: A list of texture data
        """
        texture_data = list()
        for table_data in self.generate_rom_table_data([7, 14, 25]):
            texture_data.append(TextureData(**table_data))
        return texture_data

    @cache
    def get_stub_table_data(self, table_id: int) -> list[StubTableData]:
        """Fetch provisional raw data wrappers for a named but unparsed table."""
        try:
            data_class = STUB_TABLE_DATA_TYPES[table_id]
        except KeyError:
            raise ValueError(f"Table {table_id} does not have a stub data type")
        return [
            data_class(**table_data)
            for table_data in self.generate_rom_table_data([table_id])
        ]

    def get_midi_music_data(self) -> list[MidiMusicData]:
        return self.get_stub_table_data(0)

    def get_wall_collision_data(self) -> list[WallCollisionData]:
        return self.get_stub_table_data(2)

    def get_floor_collision_data(self) -> list[FloorCollisionData]:
        return self.get_stub_table_data(3)

    def get_model_two_geometry_data(self) -> list[ModelTwoGeometryData]:
        return self.get_stub_table_data(4)

    def get_actor_geometry_data(self) -> list[ActorGeometryData]:
        return self.get_stub_table_data(5)

    def get_setup_data(self) -> list[SetupData]:
        return self.get_stub_table_data(9)

    def get_instance_script_data(self) -> list[InstanceScriptData]:
        return self.get_stub_table_data(10)

    def get_animation_data(self) -> list[AnimationData]:
        return self.get_stub_table_data(11)

    def get_animation_code_data(self) -> list[AnimationCodeData]:
        return self.get_stub_table_data(13)

    def get_path_data(self) -> list[PathData]:
        return self.get_stub_table_data(15)

    def get_spawner_data(self) -> list[SpawnerData]:
        return self.get_stub_table_data(16)

    def get_dktv_input_data(self) -> list[DKTVInputData]:
        return self.get_stub_table_data(17)

    def get_trigger_data(self) -> list[TriggerData]:
        return self.get_stub_table_data(18)

    def get_unknown_table_19_data(self) -> list[UnknownTable19Data]:
        return self.get_stub_table_data(19)

    def get_autowalk_data(self) -> list[AutowalkData]:
        return self.get_stub_table_data(21)

    def get_critter_data(self) -> list[CritterData]:
        return self.get_stub_table_data(22)

    def get_exit_data(self) -> list[ExitData]:
        return self.get_stub_table_data(23)

    def get_race_checkpoint_data(self) -> list[RaceCheckpointData]:
        return self.get_stub_table_data(24)

    def get_uncompressed_file_size_data(self) -> list[UncompressedFileSizeData]:
        return self.get_stub_table_data(26)

    @cache
    def get_geometry_texture_data(self) -> list[TextureData]:
        """Fetch texture data referenced by map geometry display lists."""
        return [
            TextureData(**table_data)
            for table_data in self.generate_rom_table_data([25])
        ]

    @cache
    def get_text_data(self) -> list[TextData]:
        """A function for fetching the text data

        Yields:
            list[TextData]: A list of texture data
        """
        text_data = list()
        for table_data in self.generate_rom_table_data([12]):
            text_data.append(TextData(**table_data, release_or_kiosk=self.release_or_kiosk))
        return text_data

    @cache
    def get_cutscene_data(self) -> list[CutsceneData]:
        """A function for fetching the cutscene data

        Yields:
            list[CutsceneData]: A list of texture data
        """
        cutscene_data = list()
        for table_data in self.generate_rom_table_data([8]):
            cutscene_data.append(CutsceneData(**table_data))
        return cutscene_data

    @cache
    def get_geometry_data(self) -> list[GeometryData]:
        """A function for fetching the cutscene data

        Yields:
            list[GeometryData]: A list of texture data
        """
        geometry_data = list()
        for table_data in self.generate_rom_table_data([1]):
            geometry_table = GeometryData(**table_data)
            geometry_data.append(geometry_table)
            if geometry_table.is_pointer:
                geometry_table.points_to = geometry_data[geometry_table.pointer]
        return geometry_data
