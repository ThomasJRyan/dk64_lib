import binascii
import json
import math
import pathlib
import struct
import zlib

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from collada import Collada
from collada import geometry as collada_geometry
from collada import material as collada_material
from collada import scene, source
from collada.common import E, tag
from dk64_lib.f3dex2 import commands
from dk64_lib.f3dex2.triangle import Triangle
from dk64_lib.f3dex2.vertex import Vertex
from numpy import array as numpy_array


@dataclass(frozen=True, slots=True)
class TextureImageFile:
    filename: str
    data: bytes


@dataclass(frozen=True, slots=True)
class TexturedObjSupportFile:
    filename: str
    data: str


@dataclass(frozen=True, slots=True)
class TexturedDaeSupportFile:
    filename: str
    data: str


@dataclass(frozen=True, slots=True)
class TexturedObjExport:
    obj_data: str
    mtl_data: str
    images: tuple[TextureImageFile, ...]
    support_files: tuple[TexturedObjSupportFile, ...] = tuple()


@dataclass(frozen=True, slots=True)
class TexturedDaeExport:
    dae: Collada
    images: tuple[TextureImageFile, ...]
    support_files: tuple[TexturedDaeSupportFile, ...] = tuple()


@dataclass(frozen=True, slots=True)
class TexturedGltfExport:
    gltf_data: str
    binary_filename: str
    binary_data: bytes
    images: tuple[TextureImageFile, ...]


@dataclass(frozen=True, slots=True)
class TexturedGlbExport:
    data: bytes


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
    clamp_s: bool
    clamp_t: bool


@dataclass(frozen=True, slots=True)
class _TextureKey:
    image_index: int
    palette_index: int | None
    fmt: int
    size: int
    width: int
    height: int
    clamp_s: bool = False
    clamp_t: bool = False

    @property
    def material_name(self) -> str:
        palette = "none" if self.palette_index is None else str(self.palette_index)
        name = (
            f"tex_{self.image_index}_pal_{palette}_"
            f"f{self.fmt}_s{self.size}_{self.width}x{self.height}"
        )
        if self.clamp_s and self.clamp_t:
            return f"{name}_clamp_st"
        if self.clamp_s:
            return f"{name}_clamp_s"
        if self.clamp_t:
            return f"{name}_clamp_t"
        return name

    @property
    def image_filename(self) -> str:
        return f"{self.material_name}.png"


@dataclass(frozen=True, slots=True)
class _DecodedTextureLevel:
    level: int | None
    width: int
    height: int
    rgba: bytes


@dataclass(frozen=True, slots=True)
class _TextureExportPlan:
    texture: _TextureKey
    levels: tuple[_DecodedTextureLevel, ...]


@dataclass(frozen=True, slots=True)
class _TextureAnimationFrame:
    image_index: int
    palette_index: int | None


@dataclass(frozen=True, slots=True)
class _TextureAnimationPlan:
    texture: _TextureKey
    frames: tuple[_TextureAnimationFrame, ...]
    frame_duration: int
    atlas_level: _DecodedTextureLevel

    @property
    def frame_count(self) -> int:
        return len(self.frames)


@dataclass(frozen=True, slots=True)
class _MeshGroup:
    vertices: tuple[Vertex, ...]
    triangles: tuple[Triangle, ...]
    texture: _TextureKey | None
    display_list_offset: int


TextureAnimationFrameRef = int | tuple[int, int | None]
TextureAnimationFrames = Mapping[int, Sequence[TextureAnimationFrameRef]]


class _TextureState:
    def __init__(self):
        self._pending_image: _ImageSource | None = None
        self._loaded_images: dict[int, _ImageSource] = {}
        self._tile_descriptors: dict[int, _TileDescriptor] = {}
        self._tile_sizes: dict[int, tuple[int, int]] = {}
        self._last_loaded_tile: int | None = None
        self._last_palette: _ImageSource | None = None
        self._active_tile: int | None = None

    def clone(self) -> "_TextureState":
        state = _TextureState()
        state._pending_image = self._pending_image
        state._loaded_images = dict(self._loaded_images)
        state._tile_descriptors = dict(self._tile_descriptors)
        state._tile_sizes = dict(self._tile_sizes)
        state._last_loaded_tile = self._last_loaded_tile
        state._last_palette = self._last_palette
        state._active_tile = self._active_tile
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
                clamp_s=bool(command.cm_s & 0x2),
                clamp_t=bool(command.cm_t & 0x2),
            )
            return

        if isinstance(command, commands.G_SETTILESIZE):
            if self._active_tile is None:
                self._active_tile = command.tile
            self._tile_sizes[command.tile] = _tile_dimensions(command)
            return

        if isinstance(command, commands.G_TEXTURE):
            self._active_tile = command.tile if command.on else None

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

        return _TextureKey(
            image_index=source.index,
            palette_index=palette_index,
            fmt=descriptor.fmt,
            size=descriptor.size,
            width=dimensions[0],
            height=dimensions[1],
            clamp_s=descriptor.clamp_s,
            clamp_t=descriptor.clamp_t,
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
        texture_plans = self._texture_plans_for_groups(groups)
        images = self._texture_images_for_plans(texture_plans, texture_folder)
        transparent_textures = tuple(
            texture_plan.texture
            for texture_plan in texture_plans
            if _texture_level_has_transparency(texture_plan.levels[0])
        )
        return TexturedObjExport(
            obj_data=self._obj_data(groups, mtl_filename),
            mtl_data=self._mtl_data(texture_plans, texture_folder),
            images=images,
            support_files=_blender_material_setup_support_files(
                mtl_filename,
                transparent_textures,
            ),
        )

    def export_texture_images(
        self,
        display_lists: Iterable[object],
        texture_folder: str = "textures",
    ) -> tuple[TextureImageFile, ...]:
        """Export PNG files for textures identified by F3DEX2 display lists."""
        groups = tuple(self._iter_mesh_groups(display_lists))
        texture_plans = self._texture_plans_for_groups(groups)
        return self._texture_images_for_plans(texture_plans, texture_folder)

    def _texture_plans_for_groups(
        self,
        groups: tuple[_MeshGroup, ...],
    ) -> tuple[_TextureExportPlan, ...]:
        textures = tuple(
            texture
            for texture in dict.fromkeys(group.texture for group in groups)
            if texture
        )
        return tuple(
            _TextureExportPlan(texture, self._decoded_texture_levels(texture))
            for texture in textures
        )

    def _texture_images_for_plans(
        self,
        texture_plans: tuple[_TextureExportPlan, ...],
        texture_folder: str,
    ) -> tuple[TextureImageFile, ...]:
        return tuple(
            image
            for texture_plan in texture_plans
            for image in self._texture_images(texture_plan, texture_folder)
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

    def _mtl_data(
        self,
        texture_plans: tuple[_TextureExportPlan, ...],
        texture_folder: str,
    ) -> str:
        lines: list[str] = []
        for texture_plan in texture_plans:
            texture = texture_plan.texture
            has_transparency = _texture_level_has_transparency(texture_plan.levels[0])
            lines.extend(
                (
                    f"newmtl {texture.material_name}",
                    "Ka 1.000000 1.000000 1.000000",
                    "Kd 1.000000 1.000000 1.000000",
                    "Ks 0.000000 0.000000 0.000000",
                    "d 1.000000",
                    "illum 4" if has_transparency else "illum 1",
                    _mtl_texture_map_statement("map_Kd", texture, texture_folder),
                )
            )
            if has_transparency:
                lines.append(f"map_d {texture_folder}/{_alpha_mask_filename(texture)}")
            lines.append("")
        return "\n".join(lines)

    def _texture_images(
        self,
        texture_plan: _TextureExportPlan,
        texture_folder: str,
    ) -> tuple[TextureImageFile, ...]:
        return self._texture_level_images(
            texture_plan,
            texture_folder,
        ) + self._alpha_mask_image(texture_plan, texture_folder)

    def _texture_level_images(
        self,
        texture_plan: _TextureExportPlan,
        texture_folder: str,
    ) -> tuple[TextureImageFile, ...]:
        texture = texture_plan.texture
        return tuple(
            TextureImageFile(
                filename=_texture_asset_filename(
                    texture_folder,
                    _texture_level_filename(texture, level),
                ),
                data=rgba_to_png(level.width, level.height, level.rgba),
            )
            for level in texture_plan.levels
        )

    def _alpha_mask_image(
        self,
        texture_plan: _TextureExportPlan,
        texture_folder: str,
    ) -> tuple[TextureImageFile, ...]:
        base_level = texture_plan.levels[0]
        if not _texture_level_has_transparency(base_level):
            return tuple()
        return (
            TextureImageFile(
                filename=_texture_asset_filename(
                    texture_folder,
                    _alpha_mask_filename(texture_plan.texture),
                ),
                data=rgba_to_png(
                    base_level.width,
                    base_level.height,
                    _alpha_mask_rgba(base_level.rgba),
                ),
            ),
        )

    def _decoded_texture_levels(
        self,
        texture: _TextureKey,
    ) -> tuple[_DecodedTextureLevel, ...]:
        raw_texture = self._raw_texture(texture.image_index)
        raw_palette = (
            self._raw_texture(texture.palette_index)
            if texture.palette_index is not None
            else None
        )
        mip_levels = _decode_packed_mipmap_levels(texture, raw_texture, raw_palette)
        if mip_levels:
            return mip_levels

        rgba = decode_texture(
            raw_texture,
            fmt=texture.fmt,
            size=texture.size,
            width=texture.width,
            height=texture.height,
            palette_data=raw_palette,
        )
        return (_DecodedTextureLevel(None, texture.width, texture.height, rgba),)

    def _raw_texture(self, index: int | None) -> bytes | None:
        if index is None or index < 0 or index >= len(self._texture_data):
            return None
        texture = self._texture_data[index]
        return getattr(texture, "raw_data", None)


class TexturedDaeExporter(TexturedObjExporter):
    def export(
        self,
        display_lists: Iterable[object],
        texture_folder: str = "textures",
        animated_texture_frames: TextureAnimationFrames | None = None,
        animation_frame_duration: int = 4,
    ) -> TexturedDaeExport:
        groups = tuple(self._iter_mesh_groups(display_lists))
        textures = tuple(
            texture
            for texture in dict.fromkeys(group.texture for group in groups)
            if texture
        )
        texture_plans = tuple(
            _TextureExportPlan(texture, self._decoded_texture_levels(texture))
            for texture in textures
        )
        animation_plans = tuple(
            animation_plan
            for texture_plan in texture_plans
            if (
                animation_plan := self._animation_plan(
                    texture_plan,
                    animated_texture_frames,
                    animation_frame_duration,
                )
            )
        )
        animation_plans_by_texture = {
            animation_plan.texture: animation_plan
            for animation_plan in animation_plans
        }
        images = tuple(
            image
            for texture_plan in texture_plans
            for image in self._dae_texture_images(
                texture_plan,
                texture_folder,
                animation_plans_by_texture.get(texture_plan.texture),
            )
        )
        return TexturedDaeExport(
            dae=_dae_mesh(
                groups,
                texture_plans,
                texture_folder,
                animation_plans_by_texture,
            ),
            images=images,
            support_files=_dae_animation_support_files(
                animation_plans,
                texture_folder,
            ),
        )

    def _animation_plan(
        self,
        texture_plan: _TextureExportPlan,
        animated_texture_frames: TextureAnimationFrames | None,
        animation_frame_duration: int,
    ) -> _TextureAnimationPlan | None:
        frames = _animation_frames_for_texture(
            texture_plan.texture,
            animated_texture_frames,
        )
        if not frames:
            return None
        frame_levels = tuple(
            self._decoded_animation_frame(texture_plan.texture, frame)
            for frame in frames
        )
        return _TextureAnimationPlan(
            texture=texture_plan.texture,
            frames=frames,
            frame_duration=max(1, animation_frame_duration),
            atlas_level=_horizontal_texture_atlas(frame_levels),
        )

    def _decoded_animation_frame(
        self,
        texture: _TextureKey,
        frame: _TextureAnimationFrame,
    ) -> _DecodedTextureLevel:
        frame_texture = _TextureKey(
            image_index=frame.image_index,
            palette_index=frame.palette_index,
            fmt=texture.fmt,
            size=texture.size,
            width=texture.width,
            height=texture.height,
            clamp_s=texture.clamp_s,
            clamp_t=texture.clamp_t,
        )
        return self._decoded_texture_levels(frame_texture)[0]

    def _dae_texture_images(
        self,
        texture_plan: _TextureExportPlan,
        texture_folder: str,
        animation_plan: _TextureAnimationPlan | None,
    ) -> tuple[TextureImageFile, ...]:
        if animation_plan is None:
            return self._texture_images(texture_plan, texture_folder)

        atlas_level = animation_plan.atlas_level
        images = [
            TextureImageFile(
                filename=_texture_asset_filename(
                    texture_folder,
                    _animation_atlas_filename(animation_plan),
                ),
                data=rgba_to_png(
                    atlas_level.width,
                    atlas_level.height,
                    atlas_level.rgba,
                ),
            )
        ]
        if _texture_level_has_transparency(atlas_level):
            images.append(
                TextureImageFile(
                    filename=_texture_asset_filename(
                        texture_folder,
                        _animation_alpha_mask_filename(animation_plan),
                    ),
                    data=rgba_to_png(
                        atlas_level.width,
                        atlas_level.height,
                        _alpha_mask_rgba(atlas_level.rgba),
                    ),
                )
            )
        return tuple(images)


class TexturedGltfExporter(TexturedObjExporter):
    def export(
        self,
        display_lists: Iterable[object],
        binary_filename: str = "geometry.bin",
        texture_folder: str = "textures",
        include_textures: bool = True,
    ) -> TexturedGltfExport:
        groups, texture_plans = self._groups_and_texture_plans(
            display_lists,
            include_textures,
        )
        images = tuple(
            image
            for texture_plan in texture_plans
            for image in self._texture_level_images(texture_plan, texture_folder)
        )
        gltf, binary_data = _gltf_mesh(
            groups,
            texture_plans,
            binary_filename,
            texture_folder,
            embedded_images=tuple(),
        )
        return TexturedGltfExport(
            gltf_data=_gltf_json(gltf),
            binary_filename=binary_filename,
            binary_data=binary_data,
            images=images,
        )

    def export_glb(
        self,
        display_lists: Iterable[object],
        include_textures: bool = True,
    ) -> TexturedGlbExport:
        groups, texture_plans = self._groups_and_texture_plans(
            display_lists,
            include_textures,
        )
        embedded_images = tuple(
            image
            for texture_plan in texture_plans
            for image in self._texture_level_images(texture_plan, "")
            if "_mip" not in image.filename
        )
        gltf, binary_data = _gltf_mesh(
            groups,
            texture_plans,
            binary_filename=None,
            texture_folder="",
            embedded_images=embedded_images,
        )
        return TexturedGlbExport(data=_glb_data(gltf, binary_data))

    def _groups_and_texture_plans(
        self,
        display_lists: Iterable[object],
        include_textures: bool,
    ) -> tuple[tuple[_MeshGroup, ...], tuple[_TextureExportPlan, ...]]:
        groups = tuple(self._iter_mesh_groups(display_lists))
        if not include_textures:
            return tuple(
                _MeshGroup(
                    group.vertices,
                    group.triangles,
                    None,
                    group.display_list_offset,
                )
                for group in groups
            ), tuple()

        textures = tuple(
            texture
            for texture in dict.fromkeys(group.texture for group in groups)
            if texture
        )
        texture_plans = tuple(
            _TextureExportPlan(texture, self._decoded_texture_levels(texture))
            for texture in textures
        )
        return groups, texture_plans


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

    for support_file in export.support_files:
        support_path = folder / support_file.filename
        support_path.parent.mkdir(parents=True, exist_ok=True)
        support_path.write_text(support_file.data)
        written_paths.append(support_path)

    return written_paths


def save_textured_dae_export(
    export: TexturedDaeExport,
    dae_filename: str,
    folderpath: str = ".",
) -> list[pathlib.Path]:
    folder = pathlib.Path(folderpath)
    dae_path = folder / dae_filename
    dae_path.parent.mkdir(parents=True, exist_ok=True)
    export.dae.write(dae_path)
    written_paths = [dae_path]

    for image in export.images:
        image_path = folder / image.filename
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image.data)
        written_paths.append(image_path)

    for support_file in export.support_files:
        support_path = folder / support_file.filename
        support_path.parent.mkdir(parents=True, exist_ok=True)
        support_path.write_text(support_file.data)
        written_paths.append(support_path)

    return written_paths


def save_textured_gltf_export(
    export: TexturedGltfExport,
    gltf_filename: str,
    folderpath: str = ".",
) -> list[pathlib.Path]:
    folder = pathlib.Path(folderpath)
    gltf_path = folder / gltf_filename
    gltf_path.parent.mkdir(parents=True, exist_ok=True)
    gltf_path.write_text(export.gltf_data)

    bin_path = gltf_path.parent / export.binary_filename
    bin_path.write_bytes(export.binary_data)
    written_paths = [gltf_path, bin_path]

    for image in export.images:
        image_path = folder / image.filename
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image.data)
        written_paths.append(image_path)

    return written_paths


def save_textured_glb_export(
    export: TexturedGlbExport,
    glb_filename: str,
    folderpath: str = ".",
) -> list[pathlib.Path]:
    folder = pathlib.Path(folderpath)
    glb_path = folder / glb_filename
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    glb_path.write_bytes(export.data)
    return [glb_path]


def _texture_level_filename(
    texture: _TextureKey,
    level: _DecodedTextureLevel,
) -> str:
    if level.level is None:
        return texture.image_filename
    return f"{texture.material_name}_mip{level.level}_{level.width}x{level.height}.png"


def _texture_asset_filename(texture_folder: str, filename: str) -> str:
    if not texture_folder:
        return filename
    return pathlib.PurePosixPath(texture_folder, filename).as_posix()


def _alpha_mask_filename(texture: _TextureKey) -> str:
    return f"{texture.material_name}_alpha.png"


def _texture_level_has_transparency(level: _DecodedTextureLevel) -> bool:
    return any(alpha < 255 for alpha in level.rgba[3::4])


def _alpha_mask_rgba(source_rgba: bytes) -> bytes:
    mask = bytearray()
    for alpha in source_rgba[3::4]:
        mask.extend((alpha, alpha, alpha, alpha))
    return bytes(mask)


def _mtl_texture_map_statement(
    map_name: str,
    texture: _TextureKey,
    texture_folder: str,
) -> str:
    options = " -clamp on" if texture.clamp_s or texture.clamp_t else ""
    return f"{map_name}{options} {texture_folder}/{texture.image_filename}"


def _blender_material_setup_support_files(
    mtl_filename: str,
    transparent_textures: tuple[_TextureKey, ...],
) -> tuple[TexturedObjSupportFile, ...]:
    if not transparent_textures:
        return tuple()
    filename = pathlib.Path(mtl_filename).with_suffix(".blender.py").name
    material_names = tuple(texture.material_name for texture in transparent_textures)
    return (
        TexturedObjSupportFile(
            filename=filename,
            data=_blender_material_setup_script(material_names),
        ),
    )


def _blender_material_setup_script(material_names: tuple[str, ...]) -> str:
    material_lines = "\n".join(f"    {material_name!r}," for material_name in material_names)
    return f"""\
\"\"\"Apply Blender-specific material settings for a dk64_lib OBJ import.

Run this after importing the matching OBJ file. It switches transparent DK64
materials to Blender's Blended render method, which OBJ/MTL cannot express.
\"\"\"

import bpy


TRANSPARENT_MATERIALS = (
{material_lines}
)


def _try_set(material, attribute, value):
    if not hasattr(material, attribute):
        return
    try:
        setattr(material, attribute, value)
    except Exception as exc:
        print(f\"Could not set {{material.name}}.{{attribute}}: {{exc}}\")


for material_name in TRANSPARENT_MATERIALS:
    material = bpy.data.materials.get(material_name)
    if material is None:
        print(f\"Missing material: {{material_name}}\")
        continue

    _try_set(material, \"surface_render_method\", \"BLENDED\")
    _try_set(material, \"blend_method\", \"BLEND\")
    _try_set(material, \"use_transparency_overlap\", False)
    _try_set(material, \"show_transparent_back\", False)

print(f\"Configured {{len(TRANSPARENT_MATERIALS)}} transparent DK64 material(s).\")
"""


def _animation_frames_for_texture(
    texture: _TextureKey,
    animated_texture_frames: TextureAnimationFrames | None,
) -> tuple[_TextureAnimationFrame, ...]:
    if not animated_texture_frames:
        return tuple()

    frame_refs = animated_texture_frames.get(texture.image_index)
    if not frame_refs or len(frame_refs) < 2:
        return tuple()

    return tuple(
        _normalise_animation_frame_ref(frame_ref, texture.palette_index)
        for frame_ref in frame_refs
    )


def _normalise_animation_frame_ref(
    frame_ref: TextureAnimationFrameRef,
    default_palette_index: int | None,
) -> _TextureAnimationFrame:
    if isinstance(frame_ref, tuple):
        return _TextureAnimationFrame(
            image_index=int(frame_ref[0]),
            palette_index=frame_ref[1],
        )
    return _TextureAnimationFrame(
        image_index=int(frame_ref),
        palette_index=default_palette_index,
    )


def _horizontal_texture_atlas(
    levels: tuple[_DecodedTextureLevel, ...],
) -> _DecodedTextureLevel:
    if not levels:
        raise ValueError("animated texture sequence must include at least one frame")

    frame_width = levels[0].width
    frame_height = levels[0].height
    atlas_width = frame_width * len(levels)
    atlas = bytearray(atlas_width * frame_height * 4)
    for frame_index, level in enumerate(levels):
        if level.width != frame_width or level.height != frame_height:
            raise ValueError("animated texture frames must share one size")
        for row in range(frame_height):
            source_start = row * frame_width * 4
            source_finish = source_start + frame_width * 4
            dest_start = (row * atlas_width + frame_index * frame_width) * 4
            atlas[dest_start : dest_start + frame_width * 4] = level.rgba[
                source_start:source_finish
            ]
    return _DecodedTextureLevel(
        level=None,
        width=atlas_width,
        height=frame_height,
        rgba=bytes(atlas),
    )


def _animation_atlas_filename(animation_plan: _TextureAnimationPlan) -> str:
    return f"{animation_plan.texture.material_name}_anim_{animation_plan.frame_count}frames.png"


def _animation_alpha_mask_filename(animation_plan: _TextureAnimationPlan) -> str:
    return (
        f"{animation_plan.texture.material_name}_anim_"
        f"{animation_plan.frame_count}frames_alpha.png"
    )


def _dae_animation_support_files(
    animation_plans: tuple[_TextureAnimationPlan, ...],
    texture_folder: str,
) -> tuple[TexturedDaeSupportFile, ...]:
    if not animation_plans:
        return tuple()
    return (
        TexturedDaeSupportFile(
            filename="animated_textures.blender.py",
            data=_dae_animation_blender_script(animation_plans, texture_folder),
        ),
    )


def _dae_animation_blender_script(
    animation_plans: tuple[_TextureAnimationPlan, ...],
    texture_folder: str,
) -> str:
    entries = []
    max_frame = 1
    for animation_plan in animation_plans:
        atlas_filename = _texture_asset_filename(
            texture_folder,
            _animation_atlas_filename(animation_plan),
        )
        has_alpha = _texture_level_has_transparency(animation_plan.atlas_level)
        max_frame = max(
            max_frame,
            1 + animation_plan.frame_count * animation_plan.frame_duration,
        )
        entries.append(
            "    "
            f"{animation_plan.texture.material_name!r}: "
            "{"
            f"'image_path': {atlas_filename!r}, "
            f"'frame_count': {animation_plan.frame_count}, "
            f"'frame_duration': {animation_plan.frame_duration}, "
            f"'has_alpha': {has_alpha!r}"
            "},"
        )
    animation_entries = "\n".join(entries)
    return f"""\
\"\"\"Animate dk64_lib DAE texture atlases in Blender.

Run this after importing the matching DAE file. The DAE itself references the
stitched atlas and shows frame 0; this script adds constant-stepped UV offsets
so Blender can preview the supplied texture frame sequence.
\"\"\"

from pathlib import Path

import bpy


ANIMATED_TEXTURES = {{
{animation_entries}
}}


def _try_set(material, attribute, value):
    if not hasattr(material, attribute):
        return
    try:
        setattr(material, attribute, value)
    except Exception as exc:
        print(f\"Could not set {{material.name}}.{{attribute}}: {{exc}}\")


def _input(node, name):
    return node.inputs.get(name)


def _output(node, name):
    return node.outputs.get(name)


root = Path(__file__).resolve().parent
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = max(scene.frame_end, {max_frame})

for material_name, config in ANIMATED_TEXTURES.items():
    material = bpy.data.materials.get(material_name)
    if material is None:
        print(f\"Missing material: {{material_name}}\")
        continue

    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new(\"ShaderNodeOutputMaterial\")
    shader = nodes.new(\"ShaderNodeBsdfPrincipled\")
    texcoord = nodes.new(\"ShaderNodeTexCoord\")
    mapping = nodes.new(\"ShaderNodeMapping\")
    image_node = nodes.new(\"ShaderNodeTexImage\")

    image_path = root / config[\"image_path\"]
    image_node.image = bpy.data.images.load(str(image_path), check_existing=True)

    uv_output = _output(texcoord, \"UV\")
    mapping_input = _input(mapping, \"Vector\")
    mapping_output = _output(mapping, \"Vector\")
    image_input = _input(image_node, \"Vector\")
    color_output = _output(image_node, \"Color\")
    alpha_output = _output(image_node, \"Alpha\")
    base_color_input = _input(shader, \"Base Color\")
    alpha_input = _input(shader, \"Alpha\")
    shader_output = _output(shader, \"BSDF\")
    surface_input = _input(output, \"Surface\")

    if uv_output and mapping_input:
        links.new(uv_output, mapping_input)
    if mapping_output and image_input:
        links.new(mapping_output, image_input)
    if color_output and base_color_input:
        links.new(color_output, base_color_input)
    if alpha_output and alpha_input:
        links.new(alpha_output, alpha_input)
    if shader_output and surface_input:
        links.new(shader_output, surface_input)

    if config[\"has_alpha\"]:
        _try_set(material, \"surface_render_method\", \"BLENDED\")
        _try_set(material, \"blend_method\", \"BLEND\")
        _try_set(material, \"use_transparency_overlap\", False)
        _try_set(material, \"show_transparent_back\", False)

    location = mapping.inputs.get(\"Location\")
    if location is None:
        print(f\"Mapping node has no Location input for {{material_name}}\")
        continue

    frame_count = config[\"frame_count\"]
    frame_duration = config[\"frame_duration\"]
    for frame_index in range(frame_count + 1):
        location.default_value[0] = (frame_index % frame_count) / frame_count
        location.keyframe_insert(\"default_value\", frame=1 + frame_index * frame_duration)

    action = getattr(mapping.animation_data, \"action\", None)
    if action:
        for curve in action.fcurves:
            for keyframe in curve.keyframe_points:
                keyframe.interpolation = \"CONSTANT\"

print(f\"Configured {{len(ANIMATED_TEXTURES)}} animated DK64 texture material(s).\")
"""


def _dae_mesh(
    groups: tuple[_MeshGroup, ...],
    texture_plans: tuple[_TextureExportPlan, ...],
    texture_folder: str,
    animation_plans_by_texture: Mapping[_TextureKey, _TextureAnimationPlan] | None = None,
) -> Collada:
    mesh = Collada()
    animation_plans_by_texture = animation_plans_by_texture or {}
    materials_by_symbol = _dae_materials_by_symbol(
        mesh,
        texture_plans,
        texture_folder,
        animation_plans_by_texture,
    )
    geometry_nodes = list()

    for group_index, group in enumerate(groups):
        if not group.vertices or not group.triangles:
            continue
        animation_plan = (
            animation_plans_by_texture.get(group.texture) if group.texture else None
        )
        geom = _dae_geometry_for_group(mesh, group, group_index, animation_plan)
        mesh.geometries.append(geom)
        material_symbol = _dae_material_symbol(group.texture)
        material_inputs = [("TEX0", "TEXCOORD", "0")] if group.texture else []
        material_node = scene.MaterialNode(
            material_symbol,
            materials_by_symbol[material_symbol],
            material_inputs,
        )
        geometry_nodes.append(scene.GeometryNode(geom, [material_node]))

    node = scene.Node("node0", children=geometry_nodes)
    dae_scene = scene.Scene("myscene", [node])
    mesh.scenes.append(dae_scene)
    mesh.scene = dae_scene
    return mesh


def _dae_materials_by_symbol(
    mesh: Collada,
    texture_plans: tuple[_TextureExportPlan, ...],
    texture_folder: str,
    animation_plans_by_texture: Mapping[_TextureKey, _TextureAnimationPlan],
) -> dict[str, collada_material.Material]:
    materials = {"vertex-material": _dae_vertex_material(mesh)}
    for texture_plan in texture_plans:
        symbol = texture_plan.texture.material_name
        materials[symbol] = _dae_texture_material(
            mesh,
            texture_plan,
            texture_folder,
            animation_plans_by_texture.get(texture_plan.texture),
        )
    return materials


def _dae_vertex_material(mesh: Collada) -> collada_material.Material:
    effect = collada_material.Effect(
        "vertex-effect",
        [],
        "phong",
        diffuse=(1.0, 1.0, 1.0, 1.0),
        specular=(0.0, 0.0, 0.0, 1.0),
    )
    effect.transparent = None
    effect.transparency = None
    mat = collada_material.Material("vertex-material", "vertex-material", effect)
    mesh.effects.append(effect)
    mesh.materials.append(mat)
    return mat


def _dae_texture_material(
    mesh: Collada,
    texture_plan: _TextureExportPlan,
    texture_folder: str,
    animation_plan: _TextureAnimationPlan | None = None,
) -> collada_material.Material:
    texture = texture_plan.texture
    texture_filename = (
        _animation_atlas_filename(animation_plan)
        if animation_plan is not None
        else texture.image_filename
    )
    alpha_filename = (
        _animation_alpha_mask_filename(animation_plan)
        if animation_plan is not None
        else _alpha_mask_filename(texture)
    )
    transparency_level = (
        animation_plan.atlas_level
        if animation_plan is not None
        else texture_plan.levels[0]
    )
    color_map, params = _dae_texture_map(
        mesh,
        texture.material_name,
        _dae_texture_path(texture_folder, texture_filename),
        texture,
    )
    has_transparency = _texture_level_has_transparency(transparency_level)
    transparent = None
    transparency = None
    if has_transparency:
        alpha_map, alpha_params = _dae_texture_map(
            mesh,
            f"{texture.material_name}-alpha",
            _dae_texture_path(texture_folder, alpha_filename),
            texture,
        )
        params.extend(alpha_params)
        transparent = alpha_map
        transparency = 1.0

    effect = collada_material.Effect(
        f"{texture.material_name}-effect",
        params,
        "phong",
        diffuse=color_map,
        specular=(0.0, 0.0, 0.0, 1.0),
        transparent=transparent,
        transparency=transparency,
    )
    if not has_transparency:
        # pycollada defaults to writing a transparency value; omit it for
        # opaque textures so importers do not infer unintended alpha behavior.
        effect.transparent = None
        effect.transparency = None
    mat = collada_material.Material(
        texture.material_name,
        texture.material_name,
        effect,
    )
    mesh.effects.append(effect)
    mesh.materials.append(mat)
    return mat


def _dae_texture_map(
    mesh: Collada,
    name: str,
    path: str,
    texture: _TextureKey,
) -> tuple[collada_material.Map, list[object]]:
    image = collada_material.CImage(f"{name}-image", path)
    mesh.images.append(image)
    surface = collada_material.Surface(f"{name}-surface", image)
    sampler = collada_material.Sampler2D(f"{name}-sampler", surface)
    _dae_set_sampler_wrap(sampler, texture)
    return collada_material.Map(sampler, "TEX0"), [surface, sampler]


def _dae_set_sampler_wrap(
    sampler: collada_material.Sampler2D,
    texture: _TextureKey,
) -> None:
    sampler_node = sampler.xmlnode.find(tag("sampler2D"))
    if sampler_node is None:
        return
    sampler_node.append(E.wrap_s("CLAMP" if texture.clamp_s else "WRAP"))
    sampler_node.append(E.wrap_t("CLAMP" if texture.clamp_t else "WRAP"))


def _dae_texture_path(texture_folder: str, filename: str) -> str:
    return pathlib.PurePosixPath(texture_folder, filename).as_posix()


def _dae_geometry_for_group(
    mesh: Collada,
    group: _MeshGroup,
    group_index: int,
    animation_plan: _TextureAnimationPlan | None = None,
) -> collada_geometry.Geometry:
    geom_id = f"geometry{group_index}"
    vertices = list()
    colors = list()
    texcoords = list()
    triangles = list()

    for vertex in group.vertices:
        vertices.extend((vertex.x, vertex.y, vertex.z))
        colors.extend(
            (
                vertex.xr / 255,
                vertex.yg / 255,
                vertex.zb / 255,
                vertex.alpha / 255,
            )
        )
        if group.texture is not None:
            u, v = _uv_for_vertex(vertex, group.texture)
            if animation_plan is not None:
                u /= animation_plan.frame_count
            texcoords.extend((u, v))

    for tri in group.triangles:
        triangles.extend((tri.v1, tri.v2, tri.v3))

    src_vertices = source.FloatSource(
        f"{geom_id}-vertices",
        numpy_array(vertices),
        ("X", "Y", "Z"),
    )
    src_colors = source.FloatSource(
        f"{geom_id}-colors",
        numpy_array(colors),
        ("R", "G", "B", "A"),
    )
    sources = [src_vertices, src_colors]
    input_list = source.InputList()
    input_list.addInput(0, "VERTEX", f"#{geom_id}-vertices")
    input_list.addInput(0, "COLOR", f"#{geom_id}-colors")

    if group.texture is not None:
        src_texcoords = source.FloatSource(
            f"{geom_id}-texcoords",
            numpy_array(texcoords),
            ("S", "T"),
        )
        sources.append(src_texcoords)
        input_list.addInput(0, "TEXCOORD", f"#{geom_id}-texcoords", set="0")

    geom = collada_geometry.Geometry(mesh, geom_id, geom_id, sources)
    triset = geom.createTriangleSet(
        numpy_array(triangles),
        input_list,
        _dae_material_symbol(group.texture),
    )
    geom.primitives.append(triset)
    return geom


def _dae_material_symbol(texture: _TextureKey | None) -> str:
    if texture is None:
        return "vertex-material"
    return texture.material_name


_GLTF_ARRAY_BUFFER = 34962
_GLTF_ELEMENT_ARRAY_BUFFER = 34963
_GLTF_FLOAT = 5126
_GLTF_UNSIGNED_SHORT = 5123
_GLTF_UNSIGNED_INT = 5125
_GLTF_TRIANGLES = 4
_GLTF_REPEAT = 10497
_GLTF_CLAMP_TO_EDGE = 33071


class _GltfBinaryBuilder:
    def __init__(self):
        self.data = bytearray()
        self.buffer_views: list[dict[str, object]] = []

    def add_view(self, payload: bytes, target: int | None = None) -> int:
        _pad_bytearray(self.data)
        view = {
            "buffer": 0,
            "byteOffset": len(self.data),
            "byteLength": len(payload),
        }
        if target is not None:
            view["target"] = target
        self.data.extend(payload)
        self.buffer_views.append(view)
        return len(self.buffer_views) - 1

    def to_bytes(self) -> bytes:
        _pad_bytearray(self.data)
        return bytes(self.data)


def _gltf_mesh(
    groups: tuple[_MeshGroup, ...],
    texture_plans: tuple[_TextureExportPlan, ...],
    binary_filename: str | None,
    texture_folder: str,
    embedded_images: tuple[TextureImageFile, ...],
) -> tuple[dict[str, object], bytes]:
    binary = _GltfBinaryBuilder()
    gltf: dict[str, object] = {
        "asset": {
            "version": "2.0",
            "generator": "dk64_lib",
        },
        "extensionsUsed": ["KHR_materials_unlit"],
        "scene": 0,
        "scenes": [{"nodes": []}],
        "nodes": [],
        "meshes": [],
        "materials": [_gltf_vertex_material()],
    }
    material_indices: dict[_TextureKey | None, int] = {None: 0}
    _gltf_add_texture_materials(
        gltf,
        binary,
        texture_plans,
        texture_folder,
        embedded_images,
        material_indices,
    )

    for group_index, group in enumerate(groups):
        if not group.vertices or not group.triangles:
            continue
        material_index = material_indices.get(group.texture, 0)
        mesh_index = _gltf_add_mesh(gltf, binary, group, group_index, material_index)
        node_index = _gltf_append(
            gltf,
            "nodes",
            {
                "name": f"mesh_group_{group_index}",
                "mesh": mesh_index,
            },
        )
        gltf["scenes"][0]["nodes"].append(node_index)

    binary_data = binary.to_bytes()
    gltf["buffers"] = [{"byteLength": len(binary_data)}]
    if binary_filename is not None:
        gltf["buffers"][0]["uri"] = pathlib.PurePosixPath(binary_filename).as_posix()
    if binary.buffer_views:
        gltf["bufferViews"] = binary.buffer_views
    return gltf, binary_data


def _gltf_vertex_material() -> dict[str, object]:
    return {
        "name": "vertex-material",
        "doubleSided": True,
        "pbrMetallicRoughness": {
            "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
            "metallicFactor": 0.0,
            "roughnessFactor": 1.0,
        },
        "extensions": {"KHR_materials_unlit": {}},
    }


def _gltf_add_texture_materials(
    gltf: dict[str, object],
    binary: _GltfBinaryBuilder,
    texture_plans: tuple[_TextureExportPlan, ...],
    texture_folder: str,
    embedded_images: tuple[TextureImageFile, ...],
    material_indices: dict[_TextureKey | None, int],
) -> None:
    embedded_images_by_name = {
        pathlib.PurePosixPath(image.filename).name: image for image in embedded_images
    }
    for texture_plan in texture_plans:
        texture = texture_plan.texture
        image_index = _gltf_add_image(
            gltf,
            binary,
            texture,
            texture_folder,
            embedded_images_by_name,
        )
        sampler_index = _gltf_append(gltf, "samplers", _gltf_sampler(texture))
        texture_index = _gltf_append(
            gltf,
            "textures",
            {
                "name": texture.material_name,
                "source": image_index,
                "sampler": sampler_index,
            },
        )
        material_indices[texture] = _gltf_append(
            gltf,
            "materials",
            _gltf_texture_material(texture_plan, texture_index),
        )


def _gltf_add_image(
    gltf: dict[str, object],
    binary: _GltfBinaryBuilder,
    texture: _TextureKey,
    texture_folder: str,
    embedded_images_by_name: dict[str, TextureImageFile],
) -> int:
    image = {
        "name": texture.material_name,
    }
    embedded_image = embedded_images_by_name.get(texture.image_filename)
    if embedded_image is None:
        image["uri"] = _texture_asset_filename(texture_folder, texture.image_filename)
    else:
        image["bufferView"] = binary.add_view(embedded_image.data)
        image["mimeType"] = "image/png"
    return _gltf_append(gltf, "images", image)


def _gltf_sampler(texture: _TextureKey) -> dict[str, int]:
    return {
        "wrapS": _GLTF_CLAMP_TO_EDGE if texture.clamp_s else _GLTF_REPEAT,
        "wrapT": _GLTF_CLAMP_TO_EDGE if texture.clamp_t else _GLTF_REPEAT,
    }


def _gltf_texture_material(
    texture_plan: _TextureExportPlan,
    texture_index: int,
) -> dict[str, object]:
    material: dict[str, object] = {
        "name": texture_plan.texture.material_name,
        "doubleSided": True,
        "pbrMetallicRoughness": {
            "baseColorTexture": {
                "index": texture_index,
                "texCoord": 0,
            },
            "metallicFactor": 0.0,
            "roughnessFactor": 1.0,
        },
        "extensions": {"KHR_materials_unlit": {}},
    }
    if _texture_level_has_transparency(texture_plan.levels[0]):
        material["alphaMode"] = "BLEND"
    return material


def _gltf_add_mesh(
    gltf: dict[str, object],
    binary: _GltfBinaryBuilder,
    group: _MeshGroup,
    group_index: int,
    material_index: int,
) -> int:
    attributes = {
        "POSITION": _gltf_add_position_accessor(gltf, binary, group.vertices),
        "COLOR_0": _gltf_add_color_accessor(gltf, binary, group.vertices),
    }
    if group.texture is not None:
        attributes["TEXCOORD_0"] = _gltf_add_texcoord_accessor(
            gltf,
            binary,
            group.vertices,
            group.texture,
        )

    mesh = {
        "name": f"mesh_group_{group_index}",
        "primitives": [
            {
                "attributes": attributes,
                "indices": _gltf_add_index_accessor(
                    gltf,
                    binary,
                    group.vertices,
                    group.triangles,
                ),
                "material": material_index,
                "mode": _GLTF_TRIANGLES,
            }
        ],
    }
    return _gltf_append(gltf, "meshes", mesh)


def _gltf_add_position_accessor(
    gltf: dict[str, object],
    binary: _GltfBinaryBuilder,
    vertices: tuple[Vertex, ...],
) -> int:
    payload = b"".join(struct.pack("<fff", vertex.x, vertex.y, vertex.z) for vertex in vertices)
    return _gltf_add_accessor(
        gltf,
        binary,
        payload,
        count=len(vertices),
        component_type=_GLTF_FLOAT,
        accessor_type="VEC3",
        target=_GLTF_ARRAY_BUFFER,
        minimum=[
            float(min(vertex.x for vertex in vertices)),
            float(min(vertex.y for vertex in vertices)),
            float(min(vertex.z for vertex in vertices)),
        ],
        maximum=[
            float(max(vertex.x for vertex in vertices)),
            float(max(vertex.y for vertex in vertices)),
            float(max(vertex.z for vertex in vertices)),
        ],
    )


def _gltf_add_color_accessor(
    gltf: dict[str, object],
    binary: _GltfBinaryBuilder,
    vertices: tuple[Vertex, ...],
) -> int:
    payload = b"".join(
        struct.pack(
            "<ffff",
            vertex.xr / 255,
            vertex.yg / 255,
            vertex.zb / 255,
            vertex.alpha / 255,
        )
        for vertex in vertices
    )
    return _gltf_add_accessor(
        gltf,
        binary,
        payload,
        count=len(vertices),
        component_type=_GLTF_FLOAT,
        accessor_type="VEC4",
        target=_GLTF_ARRAY_BUFFER,
    )


def _gltf_add_texcoord_accessor(
    gltf: dict[str, object],
    binary: _GltfBinaryBuilder,
    vertices: tuple[Vertex, ...],
    texture: _TextureKey,
) -> int:
    payload = b"".join(
        struct.pack("<ff", *_gltf_uv_for_vertex(vertex, texture))
        for vertex in vertices
    )
    return _gltf_add_accessor(
        gltf,
        binary,
        payload,
        count=len(vertices),
        component_type=_GLTF_FLOAT,
        accessor_type="VEC2",
        target=_GLTF_ARRAY_BUFFER,
    )


def _gltf_add_index_accessor(
    gltf: dict[str, object],
    binary: _GltfBinaryBuilder,
    vertices: tuple[Vertex, ...],
    triangles: tuple[Triangle, ...],
) -> int:
    use_unsigned_int = len(vertices) > 0xFFFF
    component_type = _GLTF_UNSIGNED_INT if use_unsigned_int else _GLTF_UNSIGNED_SHORT
    pack_format = "<I" if use_unsigned_int else "<H"
    indices = tuple(
        index for triangle in triangles for index in (triangle.v1, triangle.v2, triangle.v3)
    )
    payload = b"".join(struct.pack(pack_format, index) for index in indices)
    return _gltf_add_accessor(
        gltf,
        binary,
        payload,
        count=len(indices),
        component_type=component_type,
        accessor_type="SCALAR",
        target=_GLTF_ELEMENT_ARRAY_BUFFER,
        minimum=[min(indices)],
        maximum=[max(indices)],
    )


def _gltf_add_accessor(
    gltf: dict[str, object],
    binary: _GltfBinaryBuilder,
    payload: bytes,
    count: int,
    component_type: int,
    accessor_type: str,
    target: int,
    minimum: list[float | int] | None = None,
    maximum: list[float | int] | None = None,
) -> int:
    accessor = {
        "bufferView": binary.add_view(payload, target),
        "byteOffset": 0,
        "componentType": component_type,
        "count": count,
        "type": accessor_type,
    }
    if minimum is not None:
        accessor["min"] = minimum
    if maximum is not None:
        accessor["max"] = maximum
    return _gltf_append(gltf, "accessors", accessor)


def _gltf_append(gltf: dict[str, object], key: str, value: object) -> int:
    values = gltf.setdefault(key, [])
    values.append(value)
    return len(values) - 1


def _gltf_json(gltf: dict[str, object]) -> str:
    return json.dumps(gltf, indent=2) + "\n"


def _glb_data(gltf: dict[str, object], binary_data: bytes) -> bytes:
    json_chunk = _pad_bytes(_gltf_json(gltf).encode("utf-8"), b" ")
    bin_chunk = _pad_bytes(binary_data, b"\x00")
    total_length = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    return b"".join(
        (
            struct.pack("<III", 0x46546C67, 2, total_length),
            struct.pack("<I4s", len(json_chunk), b"JSON"),
            json_chunk,
            struct.pack("<I4s", len(bin_chunk), b"BIN\x00"),
            bin_chunk,
        )
    )


def _pad_bytearray(data: bytearray) -> None:
    data.extend(b"\x00" * (-len(data) % 4))


def _pad_bytes(data: bytes, padding: bytes) -> bytes:
    return data + (padding * (-len(data) % 4))


def _decode_packed_mipmap_levels(
    texture: _TextureKey,
    raw_texture: bytes | None,
    raw_palette: bytes | None,
) -> tuple[_DecodedTextureLevel, ...]:
    if (
        texture.fmt == 2
        and texture.size == 0
        and texture.width == 64
        and texture.height == 32
        and _has_packed_mipmap_storage(
            raw_texture,
            texture.size,
            _packed_ci4_64x32_mipmap_storage_pixels(texture.width, texture.height),
        )
    ):
        return _decode_packed_ci4_64x32_mipmap_levels(
            texture,
            raw_texture,
            raw_palette,
        )

    if (
        texture.fmt == 2
        and texture.size == 0
        and texture.width == 32
        and texture.height == 64
        and _has_packed_mipmap_storage(
            raw_texture,
            texture.size,
            _packed_ci4_mipmap_storage_pixels(texture.width, texture.height),
        )
    ):
        return _decode_packed_ci4_mipmap_levels(texture, raw_texture, raw_palette)

    if (
        texture.fmt == 2
        and texture.size in (0, 1)
        and texture.width == 32
        and texture.height == 32
        and _has_packed_mipmap_storage(
            raw_texture,
            texture.size,
            _standard_mipmap_storage_pixels(
                texture.width,
                texture.height,
                texture.size,
            ),
        )
    ):
        return _decode_standard_indexed_mipmap_levels(
            texture,
            raw_texture,
            raw_palette,
        )

    if (
        texture.fmt == 0
        and texture.size == 2
        and texture.width == 32
        and texture.height == 32
        and _has_packed_mipmap_storage(
            raw_texture,
            texture.size,
            _packed_rgba_mipmap_storage_pixels(texture.width, texture.height),
        )
    ):
        return _decode_packed_rgba_mipmap_levels(texture, raw_texture, raw_palette)

    return tuple()


def _decode_packed_ci4_mipmap_levels(
    texture: _TextureKey,
    raw_texture: bytes | None,
    raw_palette: bytes | None,
) -> tuple[_DecodedTextureLevel, ...]:
    base_width, base_height = _raw_texture_dimensions(
        raw_texture,
        texture.size,
        texture.width,
    )
    base_rgba = decode_texture(
        raw_texture,
        fmt=texture.fmt,
        size=texture.size,
        width=base_width,
        height=base_height,
        palette_data=raw_palette,
    )
    return _packed_ci4_mipmap_levels(texture.width, texture.height, base_rgba)


def _decode_packed_ci4_64x32_mipmap_levels(
    texture: _TextureKey,
    raw_texture: bytes | None,
    raw_palette: bytes | None,
) -> tuple[_DecodedTextureLevel, ...]:
    base_width, base_height = _raw_texture_dimensions(
        raw_texture,
        texture.size,
        texture.width,
    )
    base_rgba = decode_texture(
        raw_texture,
        fmt=texture.fmt,
        size=texture.size,
        width=base_width,
        height=base_height,
        palette_data=raw_palette,
    )
    return _packed_ci4_64x32_mipmap_levels(texture.width, texture.height, base_rgba)


def _decode_standard_indexed_mipmap_levels(
    texture: _TextureKey,
    raw_texture: bytes | None,
    raw_palette: bytes | None,
) -> tuple[_DecodedTextureLevel, ...]:
    base_width, base_height = _raw_texture_dimensions(
        raw_texture,
        texture.size,
        texture.width,
    )
    base_rgba = decode_texture(
        raw_texture,
        fmt=texture.fmt,
        size=texture.size,
        width=base_width,
        height=base_height,
        palette_data=raw_palette,
    )
    return _standard_mipmap_levels(
        texture.width,
        texture.height,
        base_rgba,
        level0_swap_group_pixels=_standard_indexed_level0_swap_group_pixels(
            texture.size
        ),
        level1_swap_group_pixels=_standard_indexed_level1_swap_group_pixels(
            texture.size
        ),
        level2_swap_group_pixels=_standard_indexed_level2_swap_group_pixels(
            texture.size
        ),
        level3_row_offsets=_standard_indexed_level3_row_offsets(texture.size),
    )


def _decode_packed_rgba_mipmap_levels(
    texture: _TextureKey,
    raw_texture: bytes | None,
    raw_palette: bytes | None,
) -> tuple[_DecodedTextureLevel, ...]:
    base_width, base_height = _raw_texture_dimensions(
        raw_texture,
        texture.size,
        texture.width,
    )
    base_rgba = decode_texture(
        raw_texture,
        fmt=texture.fmt,
        size=texture.size,
        width=base_width,
        height=base_height,
        palette_data=raw_palette,
    )
    return _packed_rgba_mipmap_levels(texture.width, texture.height, base_rgba)


def _packed_ci4_mipmap_levels(
    width: int,
    height: int,
    base_rgba: bytes,
) -> tuple[_DecodedTextureLevel, ...]:
    level0_width, level0_height = width, height
    level1_width, level1_height = max(1, width // 2), max(1, height // 2)
    level2_width, level2_height = max(1, width // 4), max(1, height // 4)
    level3_width, level3_height = max(1, width // 8), max(1, height // 8)
    level0_pixels = level0_width * level0_height
    level1_pixels = level1_width * level1_height
    level2_storage_pixels = width * math.ceil(level2_height / 2)
    level2_start_pixel = level0_pixels + level1_pixels
    level3_start_pixel = level2_start_pixel + level2_storage_pixels

    level_specs = (
        (None, level0_width, level0_height, 0),
        (1, level1_width, level1_height, level0_pixels),
        (2, level2_width, level2_height, level2_start_pixel),
        (3, level3_width, level3_height, level3_start_pixel),
    )
    levels = list()

    for level, output_width, output_height, start_pixel in level_specs:
        if level in (2, 3):
            skipped_pixels = width // 2 if level == 2 else width - (output_width * 3)
            rgba = _slice_sparse_paired_rows_rgba(
                base_rgba,
                start_pixel=start_pixel,
                output_width=output_width,
                output_height=output_height,
                source_group_pixels=width,
                skipped_pixels=skipped_pixels,
            )
        else:
            rgba = _slice_flat_rgba(base_rgba, start_pixel, output_width, output_height)
        if level in (None, 1):
            rgba = _swap_odd_rows_rgba(
                rgba,
                source_width=output_width,
                group_pixels=16,
            )
        levels.append(_DecodedTextureLevel(level, output_width, output_height, rgba))

    return tuple(levels)


def _packed_ci4_64x32_mipmap_levels(
    width: int,
    height: int,
    base_rgba: bytes,
) -> tuple[_DecodedTextureLevel, ...]:
    level1_width, level1_height = max(1, width // 2), max(1, height // 2)
    level2_width, level2_height = max(1, width // 4), max(1, height // 4)
    level3_width, level3_height = max(1, width // 8), max(1, height // 8)
    level1_start_pixel = width * height
    level2_start_pixel = level1_start_pixel + width * math.ceil(level1_height / 2)
    level3_start_pixel = level2_start_pixel + width * math.ceil(level2_height / 4)

    return (
        _DecodedTextureLevel(
            None,
            width,
            height,
            _swap_odd_rows_rgba(
                _slice_flat_rgba(base_rgba, 0, width, height),
                source_width=width,
                group_pixels=16,
            ),
        ),
        _DecodedTextureLevel(
            1,
            level1_width,
            level1_height,
            _slice_sparse_paired_rows_rgba(
                base_rgba,
                start_pixel=level1_start_pixel,
                output_width=level1_width,
                output_height=level1_height,
                source_group_pixels=width,
                skipped_pixels=0,
                swap_second_row_group_pixels=16,
            ),
        ),
        _DecodedTextureLevel(
            2,
            level2_width,
            level2_height,
            _slice_segmented_rows_rgba(
                base_rgba,
                start_pixel=level2_start_pixel,
                output_width=level2_width,
                output_height=level2_height,
                source_group_pixels=width,
                swap_group_pixels=16,
            ),
        ),
        _DecodedTextureLevel(
            3,
            level3_width,
            level3_height,
            _slice_offset_rows_rgba(
                base_rgba,
                start_pixel=level3_start_pixel,
                output_width=level3_width,
                output_height=level3_height,
                source_group_pixels=width,
                row_offsets=(0, 24, 32, 56),
            ),
        ),
    )


def _standard_mipmap_levels(
    width: int,
    height: int,
    base_rgba: bytes,
    level0_swap_group_pixels: int = 16,
    level1_swap_group_pixels: int | None = None,
    level2_swap_group_pixels: int | None = None,
    level3_row_offsets: tuple[int, ...] | None = None,
) -> tuple[_DecodedTextureLevel, ...]:
    level0_width, level0_height = width, height
    level1_width, level1_height = max(1, width // 2), max(1, height // 2)
    level2_width, level2_height = max(1, width // 4), max(1, height // 4)
    level3_width, level3_height = max(1, width // 8), max(1, height // 8)
    level0_pixels = level0_width * level0_height
    level1_pixels = level1_width * level1_height
    level2_storage_pixels = _standard_level2_storage_pixels(
        width,
        level2_width,
        level2_height,
        level2_swap_group_pixels,
    )
    level2_start_pixel = level0_pixels + level1_pixels
    level3_start_pixel = level2_start_pixel + level2_storage_pixels

    return (
        _DecodedTextureLevel(
            None,
            level0_width,
            level0_height,
            _swap_odd_rows_rgba(
                _slice_flat_rgba(base_rgba, 0, level0_width, level0_height),
                source_width=level0_width,
                group_pixels=level0_swap_group_pixels,
            ),
        ),
        _DecodedTextureLevel(
            1,
            level1_width,
            level1_height,
            _standard_level1_rgba(
                base_rgba,
                start_pixel=level0_pixels,
                width=level1_width,
                height=level1_height,
                swap_group_pixels=level1_swap_group_pixels,
            ),
        ),
        _DecodedTextureLevel(
            2,
            level2_width,
            level2_height,
            _standard_level2_rgba(
                base_rgba,
                start_pixel=level2_start_pixel,
                output_width=level2_width,
                output_height=level2_height,
                source_width=width,
                swap_group_pixels=level2_swap_group_pixels,
            ),
        ),
        _DecodedTextureLevel(
            3,
            level3_width,
            level3_height,
            _standard_level3_rgba(
                base_rgba,
                start_pixel=level3_start_pixel,
                output_width=level3_width,
                output_height=level3_height,
                source_width=width,
                row_offsets=level3_row_offsets,
            ),
        ),
    )


def _standard_indexed_level0_swap_group_pixels(size: int) -> int:
    return 8 if size == 1 else 16


def _standard_indexed_level1_swap_group_pixels(size: int) -> int | None:
    return 8 if size == 1 else None


def _standard_indexed_level2_swap_group_pixels(size: int) -> int | None:
    return 8 if size == 1 else None


def _standard_indexed_level3_row_offsets(size: int) -> tuple[int, ...] | None:
    return (0, 12, 16, 28) if size == 1 else None


def _standard_level1_rgba(
    base_rgba: bytes,
    start_pixel: int,
    width: int,
    height: int,
    swap_group_pixels: int | None,
) -> bytes:
    rgba = _slice_flat_rgba(base_rgba, start_pixel, width, height)
    if swap_group_pixels is None:
        return rgba
    return _swap_odd_rows_rgba(
        rgba,
        source_width=width,
        group_pixels=swap_group_pixels,
    )


def _standard_level2_rgba(
    base_rgba: bytes,
    start_pixel: int,
    output_width: int,
    output_height: int,
    source_width: int,
    swap_group_pixels: int | None,
) -> bytes:
    if swap_group_pixels is None:
        return _slice_sparse_paired_rows_rgba(
            base_rgba,
            start_pixel=start_pixel,
            output_width=output_width,
            output_height=output_height,
            source_group_pixels=source_width,
            skipped_pixels=source_width - (output_width * 2),
        )
    return _slice_segmented_rows_rgba(
        base_rgba,
        start_pixel=start_pixel,
        output_width=output_width,
        output_height=output_height,
        source_group_pixels=source_width,
        swap_group_pixels=swap_group_pixels,
    )


def _standard_level2_storage_pixels(
    source_width: int,
    output_width: int,
    output_height: int,
    swap_group_pixels: int | None,
) -> int:
    if swap_group_pixels is None:
        return source_width * math.ceil(output_height / 2)
    return source_width * math.ceil(output_height / max(1, source_width // output_width))


def _standard_level3_rgba(
    base_rgba: bytes,
    start_pixel: int,
    output_width: int,
    output_height: int,
    source_width: int,
    row_offsets: tuple[int, ...] | None,
) -> bytes:
    if row_offsets is None:
        return _slice_sparse_paired_rows_rgba(
            base_rgba,
            start_pixel=start_pixel,
            output_width=output_width,
            output_height=output_height,
            source_group_pixels=source_width,
            skipped_pixels=source_width - (output_width * 3),
        )
    return _slice_offset_rows_rgba(
        base_rgba,
        start_pixel=start_pixel,
        output_width=output_width,
        output_height=output_height,
        source_group_pixels=source_width,
        row_offsets=row_offsets,
    )


def _standard_level3_storage_pixels(
    source_width: int,
    output_height: int,
    row_offsets: tuple[int, ...] | None,
) -> int:
    if row_offsets is None:
        return source_width * math.ceil(output_height / 2)
    return source_width * math.ceil(output_height / max(1, len(row_offsets)))


def _packed_rgba_mipmap_levels(
    width: int,
    height: int,
    base_rgba: bytes,
) -> tuple[_DecodedTextureLevel, ...]:
    level0_width, level0_height = width, height
    level1_width, level1_height = max(1, width // 2), max(1, height // 2)
    level2_width, level2_height = max(1, width // 4), max(1, height // 4)
    level3_width, level3_height = max(1, width // 8), max(1, height // 8)
    level0_pixels = level0_width * level0_height
    level1_storage_pixels = width * math.ceil(level1_height / 2)
    level2_storage_pixels = width * math.ceil(level2_height / 4)
    level2_start_pixel = level0_pixels + level1_storage_pixels
    level3_start_pixel = level2_start_pixel + level2_storage_pixels

    return (
        _DecodedTextureLevel(
            None,
            level0_width,
            level0_height,
            _swap_odd_rows_rgba(
                _slice_flat_rgba(base_rgba, 0, level0_width, level0_height),
                source_width=level0_width,
                group_pixels=4,
            ),
        ),
        _DecodedTextureLevel(
            1,
            level1_width,
            level1_height,
            _slice_sparse_paired_rows_rgba(
                base_rgba,
                start_pixel=level0_pixels,
                output_width=level1_width,
                output_height=level1_height,
                source_group_pixels=width,
                skipped_pixels=0,
                swap_second_row_group_pixels=4,
            ),
        ),
        _DecodedTextureLevel(
            2,
            level2_width,
            level2_height,
            _slice_segmented_rows_rgba(
                base_rgba,
                start_pixel=level2_start_pixel,
                output_width=level2_width,
                output_height=level2_height,
                source_group_pixels=width,
                swap_group_pixels=4,
            ),
        ),
        _DecodedTextureLevel(
            3,
            level3_width,
            level3_height,
            _slice_segmented_rows_rgba(
                base_rgba,
                start_pixel=level3_start_pixel,
                output_width=level3_width,
                output_height=level3_height,
                source_group_pixels=level3_width * 4,
                swap_group_pixels=4,
            ),
        ),
    )


def _packed_ci4_mipmap_storage_pixels(width: int, height: int) -> int:
    level0_width, level0_height = width, height
    level1_width, level1_height = max(1, width // 2), max(1, height // 2)
    level2_height = max(1, height // 4)
    level3_height = max(1, height // 8)
    return (
        (level0_width * level0_height)
        + (level1_width * level1_height)
        + (width * math.ceil(level2_height / 2))
        + (width * math.ceil(level3_height / 2))
    )


def _standard_mipmap_storage_pixels(width: int, height: int, size: int) -> int:
    level2_width = max(1, width // 4)
    level2_height = max(1, height // 4)
    level3_height = max(1, height // 8)
    level3_row_offsets = _standard_indexed_level3_row_offsets(size)
    return (
        (width * height)
        + (max(1, width // 2) * max(1, height // 2))
        + _standard_level2_storage_pixels(
            width,
            level2_width,
            level2_height,
            _standard_indexed_level2_swap_group_pixels(size),
        )
        + _standard_level3_storage_pixels(width, level3_height, level3_row_offsets)
    )


def _packed_ci4_64x32_mipmap_storage_pixels(width: int, height: int) -> int:
    level1_height = max(1, height // 2)
    level2_height = max(1, height // 4)
    level3_height = max(1, height // 8)
    return (
        (width * height)
        + (width * math.ceil(level1_height / 2))
        + (width * math.ceil(level2_height / 4))
        + (width * math.ceil(level3_height / 4))
    )


def _packed_rgba_mipmap_storage_pixels(width: int, height: int) -> int:
    level0_width, level0_height = width, height
    level1_height = max(1, height // 2)
    level2_height = max(1, height // 4)
    level3_width, level3_height = max(1, width // 8), max(1, height // 8)
    return (
        (level0_width * level0_height)
        + (width * math.ceil(level1_height / 2))
        + (width * math.ceil(level2_height / 4))
        + ((level3_width * 4) * math.ceil(level3_height / 4))
    )


def _has_packed_mipmap_storage(
    raw_texture: bytes | None,
    size: int,
    required_pixels: int,
) -> bool:
    return _raw_texture_pixel_count(raw_texture, size) >= required_pixels


_CI4_64X32_MIPMAP_TEST_SPEC = (208, 209, 2, 0, 64, 32)
_STANDARD_INDEXED_MIPMAP_TEST_SPECS = (
    (158, 159, 2, 1, 32, 32),
    (1272, 1273, 2, 0, 32, 32),
)


def test_mipmap_export(
    texture_source: object,
    folderpath: str | pathlib.Path = "mipmap_test",
    texture_index: int = 2,
    palette_index: int | None = None,
    fmt: int = 0,
    size: int = 2,
    width: int = 32,
    height: int = 32,
    include_ci4_reference: bool = True,
    include_base_references: bool = True,
) -> list[pathlib.Path]:
    """Export DK64 packed mipmap candidates for quick visual iteration."""
    texture_data = _geometry_texture_table(texture_source)
    filepaths = list()
    specs = [(texture_index, palette_index, fmt, size, width, height)]
    ci4_reference = (0, 1, 2, 0, 32, 64)
    if include_ci4_reference and ci4_reference not in specs:
        specs.append(ci4_reference)
    if include_base_references:
        for reference in (
            _CI4_64X32_MIPMAP_TEST_SPEC,
            *_STANDARD_INDEXED_MIPMAP_TEST_SPECS,
        ):
            if reference not in specs and _raw_texture_data(texture_data, reference[0]):
                specs.append(reference)

    for spec in specs:
        filepaths.extend(
            _test_mipmap_export_for_texture(
                texture_data,
                pathlib.Path(folderpath),
                texture_index=spec[0],
                palette_index=spec[1],
                fmt=spec[2],
                size=spec[3],
                width=spec[4],
                height=spec[5],
            )
        )
    return filepaths


def _test_mipmap_export_for_texture(
    texture_data: tuple[object, ...],
    folderpath: pathlib.Path,
    texture_index: int,
    palette_index: int | None,
    fmt: int,
    size: int,
    width: int,
    height: int,
) -> list[pathlib.Path]:
    raw_texture = _raw_texture_data(texture_data, texture_index)
    raw_palette = _raw_texture_data(texture_data, palette_index)
    base_width, base_height = _raw_texture_dimensions(raw_texture, size, width)
    base_rgba = decode_texture(
        raw_texture,
        fmt=fmt,
        size=size,
        width=base_width,
        height=base_height,
        palette_data=raw_palette,
    )
    if (
        texture_index,
        palette_index,
        fmt,
        size,
        width,
        height,
    ) in _STANDARD_INDEXED_MIPMAP_TEST_SPECS:
        return _test_standard_mipmap_export_for_texture(
            folderpath,
            texture_index,
            palette_index,
            fmt,
            size,
            width,
            height,
            base_width,
            base_height,
            base_rgba,
        )
    if (
        texture_index,
        palette_index,
        fmt,
        size,
        width,
        height,
    ) == _CI4_64X32_MIPMAP_TEST_SPEC:
        return _test_ci4_64x32_mipmap_export_for_texture(
            folderpath,
            texture_index,
            palette_index,
            fmt,
            size,
            width,
            height,
            base_width,
            base_height,
            base_rgba,
        )
    if (texture_index, palette_index, fmt, size, width, height) == (0, 1, 2, 0, 32, 64):
        return _test_packed_mipmap_export_for_texture(
            folderpath,
            texture_index,
            palette_index,
            fmt,
            size,
            width,
            height,
            base_width,
            base_height,
            base_rgba,
        )
    if (texture_index, palette_index, fmt, size, width, height) == (
        2,
        None,
        0,
        2,
        32,
        32,
    ):
        return _test_packed_rgba_mipmap_export_for_texture(
            folderpath,
            texture_index,
            palette_index,
            fmt,
            size,
            width,
            height,
            base_width,
            base_height,
            base_rgba,
        )

    source_rgba = decode_texture(
        raw_texture,
        fmt=fmt,
        size=size,
        width=width,
        height=height,
        palette_data=raw_palette,
    )
    texture_rgba = source_rgba
    if (texture_index, palette_index, fmt, size) == (2, None, 0, 2):
        texture_rgba = _swap_odd_rows_rgba(
            source_rgba,
            source_width=width,
            group_pixels=4,
        )

    outputs = (
        ("base", base_width, base_height, base_rgba),
        (None, width, height, texture_rgba),
        (
            1,
            width,
            max(1, height // 2),
            _stitch_alternating_swapped_rows_rgba(
                source_rgba,
                source_width=width,
                target_height=max(1, height // 2),
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
    for level, output_width, output_height, rgba in outputs:
        filename = _test_mipmap_filename(
            texture_index,
            palette_index,
            fmt,
            size,
            width,
            height,
            level,
            output_width,
            output_height,
        )
        filepath = pathlib.Path(folderpath) / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(rgba_to_png(output_width, output_height, rgba))
        filepaths.append(filepath)
    return filepaths


def _test_standard_mipmap_export_for_texture(
    folderpath: pathlib.Path,
    texture_index: int,
    palette_index: int | None,
    fmt: int,
    size: int,
    width: int,
    height: int,
    base_width: int,
    base_height: int,
    base_rgba: bytes,
) -> list[pathlib.Path]:
    outputs = [("base", base_width, base_height, base_rgba)]
    outputs.extend(
        (level.level, level.width, level.height, level.rgba)
        for level in _standard_mipmap_levels(
            width,
            height,
            base_rgba,
            level0_swap_group_pixels=_standard_indexed_level0_swap_group_pixels(size),
            level1_swap_group_pixels=_standard_indexed_level1_swap_group_pixels(size),
            level2_swap_group_pixels=_standard_indexed_level2_swap_group_pixels(size),
            level3_row_offsets=_standard_indexed_level3_row_offsets(size),
        )
    )
    return _write_test_mipmap_outputs(
        folderpath,
        texture_index,
        palette_index,
        fmt,
        size,
        width,
        height,
        tuple(outputs),
    )


def _test_ci4_64x32_mipmap_export_for_texture(
    folderpath: pathlib.Path,
    texture_index: int,
    palette_index: int | None,
    fmt: int,
    size: int,
    width: int,
    height: int,
    base_width: int,
    base_height: int,
    base_rgba: bytes,
) -> list[pathlib.Path]:
    outputs = [("base", base_width, base_height, base_rgba)]
    outputs.extend(
        (level.level, level.width, level.height, level.rgba)
        for level in _packed_ci4_64x32_mipmap_levels(width, height, base_rgba)
    )
    return _write_test_mipmap_outputs(
        folderpath,
        texture_index,
        palette_index,
        fmt,
        size,
        width,
        height,
        tuple(outputs),
    )


def _test_packed_mipmap_export_for_texture(
    folderpath: pathlib.Path,
    texture_index: int,
    palette_index: int | None,
    fmt: int,
    size: int,
    width: int,
    height: int,
    base_width: int,
    base_height: int,
    base_rgba: bytes,
) -> list[pathlib.Path]:
    outputs = [("base", base_width, base_height, base_rgba)]
    outputs.extend(
        (level.level, level.width, level.height, level.rgba)
        for level in _packed_ci4_mipmap_levels(width, height, base_rgba)
    )

    return _write_test_mipmap_outputs(
        folderpath,
        texture_index,
        palette_index,
        fmt,
        size,
        width,
        height,
        tuple(outputs),
    )


def _test_packed_rgba_mipmap_export_for_texture(
    folderpath: pathlib.Path,
    texture_index: int,
    palette_index: int | None,
    fmt: int,
    size: int,
    width: int,
    height: int,
    base_width: int,
    base_height: int,
    base_rgba: bytes,
) -> list[pathlib.Path]:
    outputs = [("base", base_width, base_height, base_rgba)]
    outputs.extend(
        (level.level, level.width, level.height, level.rgba)
        for level in _packed_rgba_mipmap_levels(width, height, base_rgba)
    )

    return _write_test_mipmap_outputs(
        folderpath,
        texture_index,
        palette_index,
        fmt,
        size,
        width,
        height,
        tuple(outputs),
    )


def _write_test_mipmap_outputs(
    folderpath: pathlib.Path,
    texture_index: int,
    palette_index: int | None,
    fmt: int,
    size: int,
    width: int,
    height: int,
    outputs: tuple[tuple[int | str | None, int, int, bytes], ...],
) -> list[pathlib.Path]:
    filepaths = list()
    for level, output_width, output_height, rgba in outputs:
        filename = _test_mipmap_filename(
            texture_index,
            palette_index,
            fmt,
            size,
            width,
            height,
            level,
            output_width,
            output_height,
        )
        filepath = pathlib.Path(folderpath) / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(rgba_to_png(output_width, output_height, rgba))
        filepaths.append(filepath)
    return filepaths


def _test_mipmap_filename(
    texture_index: int,
    palette_index: int | None,
    fmt: int,
    size: int,
    width: int,
    height: int,
    level: int | str | None,
    output_width: int,
    output_height: int,
) -> str:
    palette_name = "none" if palette_index is None else str(palette_index)
    base = (
        f"tex_{texture_index}_pal_{palette_name}_f{fmt}_s{size}_"
        f"{width}x{height}"
    )
    if level == "base":
        return f"{base}_base_{output_width}x{output_height}.png"
    if level is None:
        return f"{base}.png"
    return f"{base}_mip{level}_{output_width}x{output_height}.png"


test_mipmap_export.__test__ = False


def _geometry_texture_table(texture_source: object) -> tuple[object, ...]:
    if hasattr(texture_source, "get_geometry_texture_data"):
        return tuple(texture_source.get_geometry_texture_data())
    return tuple(texture_source)


def _raw_texture_data(texture_data: tuple[object, ...], index: int | None) -> bytes | None:
    if index is None or index < 0 or index >= len(texture_data):
        return None
    return getattr(texture_data[index], "raw_data", None)


def _raw_texture_dimensions(
    raw_texture: bytes | None,
    size: int,
    width: int,
) -> tuple[int, int]:
    pixel_count = _raw_texture_pixel_count(raw_texture, size)
    width = max(1, width)
    height = max(1, math.ceil(pixel_count / width))
    return width, height


def _raw_texture_pixel_count(raw_texture: bytes | None, size: int) -> int:
    if not raw_texture:
        return 0
    bits_per_texel = {0: 4, 1: 8, 2: 16, 3: 32}.get(size)
    if not bits_per_texel:
        return 0
    return len(raw_texture) * 8 // bits_per_texel


def _slice_flat_rgba(
    source_rgba: bytes,
    start_pixel: int,
    width: int,
    height: int,
) -> bytes:
    start = start_pixel * 4
    expected = width * height * 4
    return (source_rgba[start : start + expected] + b"\x00" * expected)[:expected]


def _slice_sparse_paired_rows_rgba(
    source_rgba: bytes,
    start_pixel: int,
    output_width: int,
    output_height: int,
    source_group_pixels: int,
    skipped_pixels: int,
    swap_second_row_group_pixels: int | None = None,
) -> bytes:
    output_row_size = output_width * 4
    source_group_size = source_group_pixels * 4
    skipped_size = skipped_pixels * 4
    source_start = start_pixel * 4
    paired = bytearray()

    for row_pair in range(math.ceil(output_height / 2)):
        group_start = source_start + (row_pair * source_group_size)
        first_row = source_rgba[group_start : group_start + output_row_size]
        second_row_start = group_start + output_row_size + skipped_size
        second_row = source_rgba[
            second_row_start : second_row_start + output_row_size
        ]
        paired.extend((first_row + b"\x00" * output_row_size)[:output_row_size])
        if (row_pair * 2) + 1 < output_height:
            second_row = (second_row + b"\x00" * output_row_size)[:output_row_size]
            if swap_second_row_group_pixels:
                second_row = _swap_pixel_group_halves_rgba(
                    second_row,
                    swap_second_row_group_pixels,
                )
            paired.extend(second_row)

    expected = output_width * output_height * 4
    return bytes(paired[:expected])


def _slice_segmented_rows_rgba(
    source_rgba: bytes,
    start_pixel: int,
    output_width: int,
    output_height: int,
    source_group_pixels: int,
    swap_group_pixels: int,
) -> bytes:
    output_row_size = output_width * 4
    source_group_size = source_group_pixels * 4
    rows_per_group = max(1, source_group_pixels // output_width)
    source_start = start_pixel * 4
    segmented = bytearray()

    for output_row in range(output_height):
        group_index = output_row // rows_per_group
        row_in_group = output_row % rows_per_group
        row_start = (
            source_start
            + (group_index * source_group_size)
            + (row_in_group * output_row_size)
        )
        row_rgba = (
            source_rgba[row_start : row_start + output_row_size]
            + b"\x00" * output_row_size
        )[:output_row_size]
        if row_in_group % 2:
            row_rgba = _swap_pixel_group_halves_rgba(row_rgba, swap_group_pixels)
        segmented.extend(row_rgba)

    return bytes(segmented)


def _slice_offset_rows_rgba(
    source_rgba: bytes,
    start_pixel: int,
    output_width: int,
    output_height: int,
    source_group_pixels: int,
    row_offsets: tuple[int, ...],
) -> bytes:
    output_row_size = output_width * 4
    source_group_size = source_group_pixels * 4
    source_start = start_pixel * 4
    rows_per_group = max(1, len(row_offsets))
    rows = bytearray()

    for output_row in range(output_height):
        group_index = output_row // rows_per_group
        row_in_group = output_row % rows_per_group
        row_start = (
            source_start
            + (group_index * source_group_size)
            + (row_offsets[row_in_group] * 4)
        )
        rows.extend(
            (
                source_rgba[row_start : row_start + output_row_size]
                + b"\x00" * output_row_size
            )[:output_row_size]
        )

    return bytes(rows)


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


def _stitch_alternating_swapped_rows_rgba(
    source_rgba: bytes,
    source_width: int,
    target_height: int,
) -> bytes:
    row_size = source_width * 4
    mip_rgba = bytearray()
    for mip_row in range(target_height):
        source_row_start = mip_row * row_size
        source_row = source_rgba[source_row_start : source_row_start + row_size]
        if mip_row % 2:
            source_row = _swap_four_pixel_groups_rgba(source_row)
        mip_rgba.extend(source_row)
    return bytes(mip_rgba)


def _swap_four_pixel_groups_rgba(row_rgba: bytes) -> bytes:
    return _swap_pixel_group_halves_rgba(row_rgba, group_pixels=4)


def _swap_odd_rows_rgba(
    source_rgba: bytes,
    source_width: int,
    group_pixels: int,
) -> bytes:
    row_size = source_width * 4
    if row_size <= 0:
        return source_rgba

    swapped = bytearray()
    for row_start in range(0, len(source_rgba), row_size):
        row_index = row_start // row_size
        row_rgba = source_rgba[row_start : row_start + row_size]
        if row_index % 2:
            row_rgba = _swap_pixel_group_halves_rgba(row_rgba, group_pixels)
        swapped.extend(row_rgba)
    return bytes(swapped)


def _swap_pixel_group_halves_rgba(row_rgba: bytes, group_pixels: int) -> bytes:
    group_size = group_pixels * 4
    half_group_size = group_size // 2
    swapped = bytearray()
    for offset in range(0, len(row_rgba), group_size):
        group = row_rgba[offset : offset + group_size]
        if len(group) == group_size:
            swapped.extend(group[half_group_size:])
            swapped.extend(group[:half_group_size])
        else:
            swapped.extend(group)
    return bytes(swapped)


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
    if texture.clamp_s:
        u = _clamp_unit(u)
    if texture.clamp_t:
        v = _clamp_unit(v)
    return u, v


def _gltf_uv_for_vertex(vertex: Vertex, texture: _TextureKey) -> tuple[float, float]:
    u = _signed_16(vertex.texture_cord_u) / 32 / texture.width
    v = _signed_16(vertex.texture_cord_v) / 32 / texture.height
    if texture.clamp_s:
        u = _clamp_unit(u)
    if texture.clamp_t:
        v = _clamp_unit(v)
    return u, v


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


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
