import binascii
import math
import pathlib
import struct
import zlib

from dataclasses import dataclass
from typing import Iterable

from dk64_lib.components.triangle import Triangle
from dk64_lib.components.vertex import Vertex
from dk64_lib.f3dex2 import commands


TMEM_WORD_BYTES = 8


@dataclass(frozen=True, slots=True)
class TextureImageFile:
    filename: str
    data: bytes


@dataclass(frozen=True, slots=True)
class TexturedObjExport:
    obj_data: str
    mtl_data: str
    images: tuple[TextureImageFile, ...]


@dataclass(frozen=True, slots=True)
class _ImageSource:
    index: int
    fmt: int
    size: int


@dataclass(frozen=True, slots=True)
class _TileDescriptor:
    fmt: int
    size: int
    line: int
    tmem: int
    palette: int


@dataclass(frozen=True, slots=True)
class _MipLevel:
    level: int
    fmt: int
    size: int
    width: int
    height: int
    data_offset: int


@dataclass(frozen=True, slots=True)
class _TextureKey:
    image_index: int
    palette_index: int | None
    fmt: int
    size: int
    width: int
    height: int
    data_offset: int = 0
    mip_levels: tuple[_MipLevel, ...] = tuple()

    @property
    def material_name(self) -> str:
        palette = "none" if self.palette_index is None else str(self.palette_index)
        name = (
            f"tex_{self.image_index}_pal_{palette}_"
            f"f{self.fmt}_s{self.size}_{self.width}x{self.height}"
        )
        if self.data_offset:
            name = f"{name}_off_{self.data_offset}"
        return name

    @property
    def image_filename(self) -> str:
        return f"{self.material_name}.png"

    def mip_image_filename(self, mip_level: _MipLevel) -> str:
        return (
            f"{self.material_name}_mip{mip_level.level}_"
            f"{mip_level.width}x{mip_level.height}.png"
        )


@dataclass(frozen=True, slots=True)
class _MeshGroup:
    vertices: tuple[Vertex, ...]
    triangles: tuple[Triangle, ...]
    texture: _TextureKey | None
    display_list_offset: int


class _TextureState:
    def __init__(self):
        self._pending_image: _ImageSource | None = None
        self._loaded_images: dict[int, _ImageSource] = {}
        self._tile_descriptors: dict[int, _TileDescriptor] = {}
        self._tile_sizes: dict[int, tuple[int, int]] = {}
        self._last_loaded_tile: int | None = None
        self._last_palette: _ImageSource | None = None
        self._active_tile: int | None = None
        self._texture_level = 0

    def clone(self) -> "_TextureState":
        state = _TextureState()
        state._pending_image = self._pending_image
        state._loaded_images = dict(self._loaded_images)
        state._tile_descriptors = dict(self._tile_descriptors)
        state._tile_sizes = dict(self._tile_sizes)
        state._last_loaded_tile = self._last_loaded_tile
        state._last_palette = self._last_palette
        state._active_tile = self._active_tile
        state._texture_level = self._texture_level
        return state

    def apply(self, command: commands.DL_Command) -> None:
        if isinstance(command, commands.G_SETTIMG):
            self._pending_image = _ImageSource(
                index=command.address,
                fmt=command.fmt,
                size=command.size,
            )
            return

        if isinstance(command, (commands.G_LOADBLOCK, commands.G_LOADTILE)):
            if self._pending_image is not None:
                self._loaded_images[command.tile] = self._pending_image
                self._last_loaded_tile = command.tile
            return

        if isinstance(command, commands.G_LOADTLUT):
            if self._pending_image is not None:
                self._last_palette = self._pending_image
            return

        if isinstance(command, commands.G_SETTILE):
            self._tile_descriptors[command.tile] = _TileDescriptor(
                fmt=command.fmt,
                size=command.size,
                line=command.line,
                tmem=command.tmem,
                palette=command.palette,
            )
            return

        if isinstance(command, commands.G_SETTILESIZE):
            if self._active_tile is None:
                self._active_tile = command.tile
            self._tile_sizes[command.tile] = _tile_dimensions(command)
            return

        if isinstance(command, commands.G_TEXTURE):
            if command.on:
                self._active_tile = command.tile
                self._texture_level = command.level
            else:
                self._active_tile = None
                self._texture_level = 0

    @property
    def active_texture(self) -> _TextureKey | None:
        if self._active_tile is None:
            return None

        descriptor = self._tile_descriptors.get(self._active_tile)
        dimensions = self._tile_sizes.get(self._active_tile)
        if descriptor is None or dimensions is None:
            return None

        source = self._loaded_images.get(self._active_tile)
        if source is None and self._last_loaded_tile is not None:
            source = self._loaded_images.get(self._last_loaded_tile)
        if source is None:
            return None

        palette_index = None
        if descriptor.fmt == 2 and self._last_palette is not None:
            palette_index = self._last_palette.index

        mip_levels = tuple(self._mip_levels(self._active_tile))

        return _TextureKey(
            image_index=source.index,
            palette_index=palette_index,
            fmt=descriptor.fmt,
            size=descriptor.size,
            width=dimensions[0],
            height=dimensions[1],
            data_offset=descriptor.tmem * TMEM_WORD_BYTES,
            mip_levels=mip_levels,
        )

    def _mip_levels(self, base_tile: int) -> Iterable[_MipLevel]:
        if self._texture_level <= 0:
            return

        for level in range(1, self._texture_level + 1):
            tile = base_tile + level
            descriptor = self._tile_descriptors.get(tile)
            dimensions = self._tile_sizes.get(tile)
            if descriptor is None or dimensions is None:
                continue
            yield _MipLevel(
                level=level,
                fmt=descriptor.fmt,
                size=descriptor.size,
                width=dimensions[0],
                height=dimensions[1],
                data_offset=descriptor.tmem * TMEM_WORD_BYTES,
            )


class TexturedObjExporter:
    def __init__(self, texture_data: Iterable[object]):
        self._texture_data = tuple(texture_data)

    def export(
        self,
        display_lists: Iterable[object],
        mtl_filename: str,
        texture_folder: str = "textures",
    ) -> TexturedObjExport:
        groups = tuple(self._iter_mesh_groups(display_lists))
        textures = _unique_textures(group.texture for group in groups)
        images = tuple(
            image
            for texture in textures
            for image in self._texture_images(texture, texture_folder)
        )
        return TexturedObjExport(
            obj_data=self._obj_data(groups, mtl_filename),
            mtl_data=self._mtl_data(textures, texture_folder),
            images=images,
        )

    def _iter_mesh_groups(
        self,
        display_lists: Iterable[object],
    ) -> Iterable[_MeshGroup]:
        for display_list in display_lists:
            if display_list.is_branched:
                continue
            yield from self._iter_display_list_groups(display_list, _TextureState())

    def _iter_display_list_groups(
        self,
        display_list: object,
        state: _TextureState,
    ) -> Iterable[_MeshGroup]:
        vertices: tuple[Vertex, ...] = tuple()
        triangles: list[Triangle] = []
        current_texture: _TextureKey | None = None

        for command in display_list.commands:
            if isinstance(command, commands.G_VTX):
                if vertices and triangles:
                    yield _MeshGroup(
                        vertices=vertices,
                        triangles=tuple(triangles),
                        texture=current_texture,
                        display_list_offset=display_list.offset,
                    )
                vertices = tuple(_vertices_for_command(display_list, command))
                triangles = []
                current_texture = state.active_texture
                continue

            if isinstance(command, commands.G_TRI1):
                active_texture = state.active_texture
                if triangles and active_texture != current_texture:
                    yield _MeshGroup(
                        vertices=vertices,
                        triangles=tuple(triangles),
                        texture=current_texture,
                        display_list_offset=display_list.offset,
                    )
                    triangles = []
                current_texture = active_texture
                triangles.append(Triangle.from_tri1(command))
                continue

            if isinstance(command, commands.G_TRI2):
                active_texture = state.active_texture
                if triangles and active_texture != current_texture:
                    yield _MeshGroup(
                        vertices=vertices,
                        triangles=tuple(triangles),
                        texture=current_texture,
                        display_list_offset=display_list.offset,
                    )
                    triangles = []
                current_texture = active_texture
                tri1, tri2 = Triangle.from_tri2(command)
                triangles.extend((tri1, tri2))
                continue

            if isinstance(command, commands.G_DL):
                branch = display_list.get_branch_by_offset(
                    int.from_bytes(command.address, "big")
                )
                if branch is not None:
                    yield from self._iter_display_list_groups(branch, state.clone())
                continue

            state.apply(command)

        if vertices and triangles:
            yield _MeshGroup(
                vertices=vertices,
                triangles=tuple(triangles),
                texture=current_texture,
                display_list_offset=display_list.offset,
            )

    def _obj_data(self, groups: tuple[_MeshGroup, ...], mtl_filename: str) -> str:
        lines = [f"mtllib {mtl_filename}", ""]
        vertex_offset = 1
        texture_offset = 1

        for group_num, group in enumerate(groups, 1):
            lines.append(
                f"# Mesh Group {group_num}, "
                f"Display List Offset: {group.display_list_offset}"
            )
            for vertex in group.vertices:
                lines.append(vertex.to_obj_line())

            if group.texture is not None:
                for vertex in group.vertices:
                    u, v = _uv_for_vertex(vertex, group.texture)
                    lines.append(f"vt {u:.8f} {v:.8f}")
                lines.append(f"usemtl {group.texture.material_name}")
                for triangle in group.triangles:
                    lines.append(
                        "f "
                        f"{triangle.v1 + vertex_offset}/{triangle.v1 + texture_offset} "
                        f"{triangle.v2 + vertex_offset}/{triangle.v2 + texture_offset} "
                        f"{triangle.v3 + vertex_offset}/{triangle.v3 + texture_offset}"
                    )
                texture_offset += len(group.vertices)
            else:
                for triangle in group.triangles:
                    lines.append(
                        "f "
                        f"{triangle.v1 + vertex_offset} "
                        f"{triangle.v2 + vertex_offset} "
                        f"{triangle.v3 + vertex_offset}"
                    )

            vertex_offset += len(group.vertices)
            lines.append("")

        return "\n".join(lines)

    def _mtl_data(self, textures: tuple[_TextureKey, ...], texture_folder: str) -> str:
        lines: list[str] = []
        for texture in textures:
            lines.extend(
                (
                    f"newmtl {texture.material_name}",
                    "Ka 1.000000 1.000000 1.000000",
                    "Kd 1.000000 1.000000 1.000000",
                    "Ks 0.000000 0.000000 0.000000",
                    "d 1.000000",
                    "illum 1",
                    f"map_Kd {texture_folder}/{texture.image_filename}",
                    *(
                        f"# mip{level.level}_map_Kd "
                        f"{texture_folder}/{texture.mip_image_filename(level)}"
                        for level in texture.mip_levels
                    ),
                    "",
                )
            )
        return "\n".join(lines)

    def _texture_images(
        self,
        texture: _TextureKey,
        texture_folder: str,
    ) -> Iterable[TextureImageFile]:
        yield TextureImageFile(
            filename=f"{texture_folder}/{texture.image_filename}",
            data=self._texture_png(
                texture,
                fmt=texture.fmt,
                size=texture.size,
                width=texture.width,
                height=texture.height,
                data_offset=texture.data_offset,
            ),
        )
        for mip_level in texture.mip_levels:
            yield TextureImageFile(
                filename=f"{texture_folder}/{texture.mip_image_filename(mip_level)}",
                data=self._texture_png(
                    texture,
                    fmt=mip_level.fmt,
                    size=mip_level.size,
                    width=mip_level.width,
                    height=mip_level.height,
                    data_offset=mip_level.data_offset,
                ),
            )

    def _texture_png(
        self,
        texture: _TextureKey,
        fmt: int,
        size: int,
        width: int,
        height: int,
        data_offset: int = 0,
    ) -> bytes:
        raw_texture = self._raw_texture(texture.image_index)
        raw_palette = (
            self._raw_texture(texture.palette_index)
            if texture.palette_index is not None
            else None
        )
        rgba = decode_texture(
            raw_texture[data_offset:] if raw_texture else raw_texture,
            fmt=fmt,
            size=size,
            width=width,
            height=height,
            palette_data=raw_palette,
        )
        return rgba_to_png(width, height, rgba)

    def _raw_texture(self, index: int | None) -> bytes | None:
        if index is None or index < 0 or index >= len(self._texture_data):
            return None
        texture = self._texture_data[index]
        return getattr(texture, "raw_data", None)


def _unique_textures(textures: Iterable[_TextureKey | None]) -> tuple[_TextureKey, ...]:
    by_material_name: dict[str, _TextureKey] = {}
    for texture in textures:
        if texture is None:
            continue
        existing = by_material_name.get(texture.material_name)
        if existing is None or len(texture.mip_levels) > len(existing.mip_levels):
            by_material_name[texture.material_name] = texture
    return tuple(by_material_name.values())


def decode_texture(
    data: bytes | None,
    fmt: int,
    size: int,
    width: int,
    height: int,
    palette_data: bytes | None = None,
) -> bytes:
    if not data or width <= 0 or height <= 0:
        return _placeholder_rgba(width, height)

    if fmt == 0 and size == 2:
        return _decode_rgba16(data, width, height)
    if fmt == 0 and size == 3:
        return _decode_rgba32(data, width, height)
    if fmt == 2 and size in (0, 1):
        return _decode_ci(data, palette_data, width, height, size)
    if fmt == 3:
        return _decode_ia(data, width, height, size)
    if fmt == 4:
        return _decode_i(data, width, height, size)
    return _placeholder_rgba(width, height)


def rgba_to_png(width: int, height: int, rgba: bytes) -> bytes:
    rows = bytearray()
    row_size = width * 4
    for row in range(height):
        rows.append(0)
        start = row * row_size
        rows.extend(rgba[start : start + row_size])

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = binascii.crc32(chunk_type)
        crc = binascii.crc32(data, crc)
        return (
            struct.pack(">I", len(data))
            + chunk_type
            + data
            + struct.pack(">I", crc & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )


def save_textured_obj_export(
    export: TexturedObjExport,
    obj_filename: str,
    folderpath: str = ".",
) -> list[pathlib.Path]:
    folder = pathlib.Path(folderpath)
    obj_path = folder / obj_filename
    obj_path.parent.mkdir(parents=True, exist_ok=True)
    obj_path.write_text(export.obj_data)
    mtl_path = obj_path.with_suffix(".mtl")
    mtl_path.write_text(export.mtl_data)
    written_paths = [obj_path, mtl_path]

    for image in export.images:
        image_path = folder / image.filename
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image.data)
        written_paths.append(image_path)

    return written_paths


def test_mipmap_export(
    texture_source: object,
    folderpath: str | pathlib.Path = "mipmap_test",
    texture_index: int = 0,
    palette_index: int | None = 1,
    fmt: int = 2,
    size: int = 0,
    width: int = 32,
    height: int = 64,
) -> list[pathlib.Path]:
    """Export DK64 packed mipmap candidates for quick visual iteration."""
    texture_data = _geometry_texture_table(texture_source)
    raw_texture = _raw_texture_data(texture_data, texture_index)
    raw_palette = _raw_texture_data(texture_data, palette_index)

    source_rgba = decode_texture(
        raw_texture,
        fmt=fmt,
        size=size,
        width=width,
        height=height,
        palette_data=raw_palette,
    )
    palette_name = "none" if palette_index is None else str(palette_index)

    mip_levels = (
        (
            1,
            width,
            max(1, height // 2),
            _stitch_rows_rgba(
                source_rgba,
                source_width=width,
                target_width=width,
                target_height=max(1, height // 2),
                start_row=0,
            ),
        ),
        (
            2,
            max(1, width // 2),
            max(1, height // 4),
            _stitch_rows_rgba(
                source_rgba,
                source_width=width,
                target_width=max(1, width // 2),
                target_height=max(1, height // 4),
                start_row=1,
            ),
        ),
    )

    filepaths = list()
    for level, mip_width, mip_height, rgba in mip_levels:
        filename = (
            f"tex_{texture_index}_pal_{palette_name}_f{fmt}_s{size}_"
            f"{width}x{height}_mip{level}_{mip_width}x{mip_height}.png"
        )
        filepath = pathlib.Path(folderpath) / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(rgba_to_png(mip_width, mip_height, rgba))
        filepaths.append(filepath)
    return filepaths


test_mipmap_export.__test__ = False


def _geometry_texture_table(texture_source: object) -> tuple[object, ...]:
    if hasattr(texture_source, "get_geometry_texture_data"):
        return tuple(texture_source.get_geometry_texture_data())
    return tuple(texture_source)


def _raw_texture_data(texture_data: tuple[object, ...], index: int | None) -> bytes | None:
    if index is None or index < 0 or index >= len(texture_data):
        return None
    return getattr(texture_data[index], "raw_data", None)


def _stitch_rows_rgba(
    source_rgba: bytes,
    source_width: int,
    target_width: int,
    target_height: int,
    start_row: int,
) -> bytes:
    source_row_size = source_width * 4
    target_row_size = target_width * 4
    mip_rgba = bytearray()
    for mip_row in range(target_height):
        source_row_start = (start_row + (mip_row * 2)) * source_row_size
        mip_rgba.extend(
            source_rgba[source_row_start : source_row_start + target_row_size]
        )
    return bytes(mip_rgba)


def _vertices_for_command(display_list: object, command: commands.G_VTX) -> list[Vertex]:
    vertex_address = int.from_bytes(command.address, "big")
    vertex_buffer_start = display_list.vertex_pointer + vertex_address
    vertex_buffer_end = vertex_buffer_start + command.vertex_count * 16
    vertex_data = display_list.raw_vertex_data[vertex_buffer_start:vertex_buffer_end]

    if vertex_buffer_end > len(display_list.raw_vertex_data):
        vertex_buffer_start = vertex_address
        vertex_buffer_end = vertex_buffer_start + command.vertex_count * 16
        vertex_data = display_list.raw_vertex_data[vertex_buffer_start:vertex_buffer_end]

    return [
        Vertex.from_bytes(vertex_data[index : index + 16])
        for index in range(0, len(vertex_data), 16)
    ]


def _tile_dimensions(command: commands.G_SETTILESIZE) -> tuple[int, int]:
    width = max(1, abs(command.lrs - command.uls) // 4 + 1)
    height = max(1, abs(command.lrt - command.ult) // 4 + 1)
    return width, height


def _uv_for_vertex(vertex: Vertex, texture: _TextureKey) -> tuple[float, float]:
    u = _signed_16(vertex.texture_cord_u) / 32 / texture.width
    v = 1 - (_signed_16(vertex.texture_cord_v) / 32 / texture.height)
    return u, v


def _signed_16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def _decode_rgba16(data: bytes, width: int, height: int) -> bytes:
    pixels = bytearray()
    for index in range(width * height):
        raw = _read_u16_or_zero(data, index * 2)
        pixels.extend(_rgba16_pixel(raw))
    return bytes(pixels)


def _decode_rgba32(data: bytes, width: int, height: int) -> bytes:
    expected = width * height * 4
    return (data[:expected] + b"\x00" * expected)[:expected]


def _decode_ci(
    data: bytes,
    palette_data: bytes | None,
    width: int,
    height: int,
    size: int,
) -> bytes:
    palette = _decode_palette(palette_data)
    pixels = bytearray()
    total_pixels = width * height

    if size == 0:
        for index in range(math.ceil(total_pixels / 2)):
            raw = data[index] if index < len(data) else 0
            pixels.extend(palette[(raw >> 4) & 0xF])
            if len(pixels) // 4 < total_pixels:
                pixels.extend(palette[raw & 0xF])
        return bytes(pixels[: total_pixels * 4])

    for index in range(total_pixels):
        palette_index = data[index] if index < len(data) else 0
        pixels.extend(palette[palette_index])
    return bytes(pixels)


def _decode_ia(data: bytes, width: int, height: int, size: int) -> bytes:
    pixels = bytearray()
    total_pixels = width * height

    if size == 0:
        for index in range(math.ceil(total_pixels / 2)):
            raw = data[index] if index < len(data) else 0
            for nibble in ((raw >> 4) & 0xF, raw & 0xF):
                intensity = ((nibble >> 1) & 0x7) * 255 // 7
                alpha = 255 if nibble & 0x1 else 0
                pixels.extend((intensity, intensity, intensity, alpha))
                if len(pixels) // 4 >= total_pixels:
                    break
        return bytes(pixels)

    if size == 1:
        for index in range(total_pixels):
            raw = data[index] if index < len(data) else 0
            intensity = ((raw >> 4) & 0xF) * 17
            alpha = (raw & 0xF) * 17
            pixels.extend((intensity, intensity, intensity, alpha))
        return bytes(pixels)

    for index in range(total_pixels):
        raw = _read_u16_or_zero(data, index * 2)
        intensity = (raw >> 8) & 0xFF
        alpha = raw & 0xFF
        pixels.extend((intensity, intensity, intensity, alpha))
    return bytes(pixels)


def _decode_i(data: bytes, width: int, height: int, size: int) -> bytes:
    pixels = bytearray()
    total_pixels = width * height

    if size == 0:
        for index in range(math.ceil(total_pixels / 2)):
            raw = data[index] if index < len(data) else 0
            for nibble in ((raw >> 4) & 0xF, raw & 0xF):
                intensity = nibble * 17
                pixels.extend((intensity, intensity, intensity, 255))
                if len(pixels) // 4 >= total_pixels:
                    break
        return bytes(pixels)

    if size == 1:
        for index in range(total_pixels):
            intensity = data[index] if index < len(data) else 0
            pixels.extend((intensity, intensity, intensity, 255))
        return bytes(pixels)

    for index in range(total_pixels):
        intensity = data[index * 2] if index * 2 < len(data) else 0
        pixels.extend((intensity, intensity, intensity, 255))
    return bytes(pixels)


def _decode_palette(data: bytes | None) -> tuple[tuple[int, int, int, int], ...]:
    return tuple(
        _rgba16_pixel(_read_u16_or_zero(data or b"", index * 2))
        for index in range(256)
    )


def _rgba16_pixel(raw: int) -> tuple[int, int, int, int]:
    red = ((raw >> 11) & 0x1F) * 255 // 31
    green = ((raw >> 6) & 0x1F) * 255 // 31
    blue = ((raw >> 1) & 0x1F) * 255 // 31
    alpha = 255 if raw & 0x1 else 0
    return red, green, blue, alpha


def _read_u16_or_zero(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        return 0
    return int.from_bytes(data[offset : offset + 2], "big")


def _placeholder_rgba(width: int, height: int) -> bytes:
    width = max(1, width)
    height = max(1, height)
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            if (x // 8 + y // 8) % 2:
                pixels.extend((255, 0, 255, 255))
            else:
                pixels.extend((0, 0, 0, 255))
    return bytes(pixels)
