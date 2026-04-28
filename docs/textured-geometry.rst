Textured Geometry Pipeline
==========================

This page documents how ``dk64_lib`` turns DK64 geometry display lists into
OBJ, MTL, and PNG files. It is intended to be a human-readable map of the
current implementation rather than a replacement for the API reference.

The relevant implementation lives primarily in:

* ``dk64_lib.data_types.geometry.GeometryData``
* ``dk64_lib.f3dex2.texture_export.TexturedObjExporter``
* ``dk64_lib.f3dex2.texture_export.decode_texture``
* ``dk64_lib.f3dex2.commands``
* ``dk64_lib.components.vertex.Vertex``

High-Level Export Flow
----------------------

Textured geometry export starts at one of the high-level helpers:

* ``Rom.export_all()``
* ``Rom.export_geometries()``
* ``GeometryData.save_to_obj()``
* ``GeometryData.save_to_textured_obj()``
* ``GeometryData.create_textured_obj()``

Geometry OBJ export includes textures by default. ``GeometryData.save_to_obj()``
has ``include_textures=True`` as its default, and ``Rom.export_geometries()`` and
``Rom.export_all()`` pass that default through unless the caller disables it.

The export flow is:

1. ``GeometryData`` parses a geometry table entry into display lists, vertex
   data, display-list chunk metadata, and expansion display lists.
2. ``GeometryData.create_textured_obj()`` fetches the geometry texture table
   through ``rom.get_geometry_texture_data()``.
3. ``TexturedObjExporter`` walks the geometry display lists, tracks the active
   F3DEX2 texture state, and groups triangles by the texture that was active
   when those triangles were emitted.
4. The exporter writes OBJ text, MTL text, and in-memory PNG files.
5. ``save_textured_obj_export()`` writes the OBJ, MTL, and PNG files to disk.

The production geometry export does not write packed mipmap base/reference
images. Those base images are only written by ``test_mipmap_export()``, which is
a temporary visual debugging helper.

Display-List Texture State
--------------------------

F3DEX2 display lists are stateful. A triangle does not directly say which image
it uses. Instead, the exporter watches texture-related commands and reconstructs
the texture state that is active when a triangle command is encountered.

The current state tracker pays attention to these commands:

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Command
     - How export uses it
   * - ``G_SETTIMG``
     - Records the pending image index plus the image ``fmt`` and ``size``.
       In DK64 geometry exports this index refers into the geometry texture
       table, not a filesystem path.
   * - ``G_LOADBLOCK`` and ``G_LOADTILE``
     - Associate the pending image with the command's tile number. The most
       recently loaded tile is also remembered as a fallback.
   * - ``G_LOADTLUT``
     - Treats the pending image as a palette image. Color-indexed textures use
       this palette when decoded.
   * - ``G_SETTILE``
     - Records a tile descriptor: ``fmt``, ``size``, line stride, TMEM address,
       palette number, clamp/mirror bits, masks, and shifts. The exporter
       currently uses the format, size, tile, and palette information.
   * - ``G_SETTILESIZE``
     - Records the tile dimensions. F3DEX2 tile coordinates are quarter-texel
       values, so export computes ``width = abs(lrs - uls) / 4 + 1`` and the
       equivalent value for height.
   * - ``G_TEXTURE``
     - Selects the active tile when texturing is on. If texturing is disabled,
       subsequent faces are exported without texture coordinates or a material.
   * - ``G_DL``
     - Recurses into a branch display list with a cloned texture state, so
       branch-local changes do not unexpectedly mutate the parent traversal.

When the exporter has an active tile, a tile descriptor, tile dimensions, and a
loaded image source, it can build a texture key:

.. code-block:: text

   tex_<image_index>_pal_<palette_index|none>_f<fmt>_s<size>_<width>x<height>

For example:

.. code-block:: text

   tex_158_pal_159_f2_s1_32x32

That material name is used consistently in the OBJ, MTL, and texture filenames.

Mesh Grouping
-------------

OBJ files are easier to import when faces that share a material are grouped
together. ``TexturedObjExporter`` therefore creates internal mesh groups while
walking each display list.

Groups are split when:

* a new ``G_VTX`` command loads a different vertex buffer;
* triangle output switches to a different active texture;
* a branched display list yields its own groups.

The current triangle path handles ``G_TRI1`` and ``G_TRI2``. ``G_TRI2`` expands
to two triangles. Faces emitted while no texture is active are still exported,
but they do not receive ``vt`` coordinates or a ``usemtl`` statement.

Vertex Output and Vertex Colors
-------------------------------

DK64 vertices are 16 bytes:

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Byte range
     - Field
     - Export use
   * - ``0..1``
     - ``x``
     - OBJ vertex position.
   * - ``2..3``
     - ``y``
     - OBJ vertex position.
   * - ``4..5``
     - ``z``
     - OBJ vertex position.
   * - ``6..7``
     - ``unk``
     - Parsed and preserved in ``Vertex`` but not written to OBJ.
   * - ``8..9``
     - ``texture_cord_u``
     - Used to compute OBJ ``vt`` ``u``.
   * - ``10..11``
     - ``texture_cord_v``
     - Used to compute OBJ ``vt`` ``v``.
   * - ``12``
     - ``xr``
     - Red vertex color channel.
   * - ``13``
     - ``yg``
     - Green vertex color channel.
   * - ``14``
     - ``zb``
     - Blue vertex color channel.
   * - ``15``
     - ``alpha``
     - Parsed and preserved. OBJ export currently omits alpha.

OBJ vertex color is written using the common extended OBJ form:

.. code-block:: text

   v <x> <y> <z> <red> <green> <blue>

The color channels are normalized from ``0..255`` to ``0.000000..1.000000``.
For example, a vertex with red ``255``, green ``0``, and blue ``128`` exports as:

.. code-block:: text

   v 0 0 0 1.000000 0.000000 0.501961

This is useful in tools such as Blender, which can read vertex colors from OBJ
files even though color support is not part of the oldest Wavefront OBJ
specification. Alpha is available in the parsed ``Vertex`` object and in DAE
export, but OBJ export writes RGB only.

UV Mapping
----------

F3DEX2 stores per-vertex texture coordinates as signed 16-bit fixed-point
values. The current exporter interprets them with 5 fractional bits, so one
texel is ``32`` units.

The OBJ UV conversion is:

.. code-block:: text

   u = signed_16(texture_cord_u) / 32 / texture_width
   v = 1 - (signed_16(texture_cord_v) / 32 / texture_height)

Important details:

* Coordinates are not clamped. Values outside ``0..1`` are preserved so normal
  texture wrapping/repeating can still work in import tools.
* OBJ's vertical texture axis is inverted relative to the convention used by
  the source data, so the exporter writes ``1 - v``.
* Texture width and height come from the active ``G_SETTILESIZE`` command, not
  from the raw byte count.
* ``G_TEXTURE`` scale values are parsed by the command class but are not applied
  by OBJ export today.

If a vertex has ``texture_cord_u = texture_width * 32`` then it maps to
``u = 1.0``. If it has ``texture_cord_v = texture_height * 32`` then it maps to
``v = 0.0`` after the OBJ vertical-axis flip.

OBJ and MTL Structure
---------------------

Every textured OBJ starts with an MTL reference:

.. code-block:: text

   mtllib geometry.mtl

Each mesh group writes:

* a comment identifying the mesh group and display-list offset;
* ``v`` lines for all vertices, including RGB vertex colors;
* ``vt`` lines when the group has an active texture;
* ``usemtl`` before textured faces;
* ``f`` lines using ``vertex_index/texture_index`` pairs for textured faces;
* plain ``f`` lines for untextured faces.

The MTL file creates one material per unique texture key:

.. code-block:: text

   newmtl tex_158_pal_159_f2_s1_32x32
   Ka 1.000000 1.000000 1.000000
   Kd 1.000000 1.000000 1.000000
   Ks 0.000000 0.000000 0.000000
   d 1.000000
   illum 1
   map_Kd textures/tex_158_pal_159_f2_s1_32x32.png

When a packed mipmap texture is detected, the exporter writes all decoded mip
levels as PNG files, but ``map_Kd`` points at the highest-resolution level. For
example, the files may include:

.. code-block:: text

   textures/tex_158_pal_159_f2_s1_32x32.png
   textures/tex_158_pal_159_f2_s1_32x32_mip1_16x16.png
   textures/tex_158_pal_159_f2_s1_32x32_mip2_8x8.png
   textures/tex_158_pal_159_f2_s1_32x32_mip3_4x4.png

Only the first file is referenced by the MTL.

Texture Decoding
----------------

``decode_texture()`` converts raw texture bytes into RGBA pixels before the PNG
writer runs. The decoder currently supports these N64 format/size combinations:

.. list-table::
   :header-rows: 1
   :widths: 18 18 64

   * - ``fmt``
     - ``size``
     - Meaning
   * - ``0``
     - ``2``
     - RGBA16.
   * - ``0``
     - ``3``
     - RGBA32.
   * - ``2``
     - ``0``
     - CI4, using a palette decoded as RGBA16 entries.
   * - ``2``
     - ``1``
     - CI8, using a palette decoded as RGBA16 entries.
   * - ``3``
     - ``0``
     - IA4.
   * - ``3``
     - ``1``
     - IA8.
   * - ``3``
     - ``2`` or higher
     - IA16-style intensity/alpha pairs.
   * - ``4``
     - ``0``
     - I4.
   * - ``4``
     - ``1``
     - I8.
   * - ``4``
     - ``2`` or higher
     - 16-bit storage where the high byte is used as intensity.

Unsupported or incomplete texture data decodes to a black and magenta
checkerboard placeholder. That keeps full ROM export robust: one unsupported
texture does not abort every geometry export.

Palette Handling
----------------

Color-indexed textures use ``G_LOADTLUT`` to identify the palette source. The
palette is decoded as up to 256 RGBA16 entries. CI4 textures use the high nibble
then the low nibble from each byte. CI8 textures use each byte as one palette
index.

The material name includes the palette index because the same texture bytes can
produce different colors with a different palette:

.. code-block:: text

   tex_896_pal_897_f2_s0_64x64.png

Packed Mipmap Detection
-----------------------

Some DK64 texture table entries contain several mipmap levels packed into one
raw texture blob. The display list usually describes the highest-resolution
tile, but the raw byte count is larger than that tile alone. The exporter uses
that extra storage to decide whether a known packed layout is present.

Detection happens before normal texture decoding. A packed decoder is used only
when:

* the active texture's ``fmt``, ``size``, width, and height match a known
  layout;
* the raw texture has enough texels for that layout;
* any required palette data can be fetched, or placeholder palette entries can
  be tolerated.

If those checks fail, export falls back to a single decoded PNG.

The production exporter writes decoded mip levels, not the raw packed base
image. The raw base image is useful for reverse engineering and is available
through ``test_mipmap_export()``.

Packed Mipmap Layouts
---------------------

The packed mipmap code works in decoded RGBA pixels, but the storage math is
based on source texels. The descriptions below use "pixel" to mean one decoded
texel after CI/RGBA conversion.

Half-swap means that a fixed-width group is split into two equal halves and the
halves are swapped. For example, a 16-pixel group:

.. code-block:: text

   00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15

becomes:

.. code-block:: text

   08 09 10 11 12 13 14 15 00 01 02 03 04 05 06 07

Smaller groups use the same rule. An 8-pixel group swaps two 4-pixel halves.
A 4-pixel group swaps two 2-pixel halves.

RGBA16 32x32
~~~~~~~~~~~~

Example texture: ``tex_2_pal_none_f0_s2_32x32``.

Raw packed dimensions are normally interpreted as ``32x43`` pixels. Exported
levels are:

.. code-block:: text

   32x32
   16x16
   8x8
   4x4

Layout:

* Level 0 is the first ``32 * 32`` pixels. Odd rows are half-swapped in
  4-pixel groups.
* Level 1 starts after level 0. Each 32-pixel storage row contains two 16-pixel
  output rows. The second row is half-swapped in 4-pixel groups.
* Level 2 stores four 8-pixel output rows in each 32-pixel storage row. Odd
  output rows are half-swapped in 4-pixel groups.
* Level 3 uses four 4-pixel rows per 16-pixel storage group. Odd output rows
  are half-swapped in 4-pixel groups.

CI4 32x64
~~~~~~~~~

Example texture: ``tex_0_pal_1_f2_s0_32x64``.

Raw packed dimensions are normally interpreted as ``32x92`` pixels. Exported
levels are:

.. code-block:: text

   32x64
   16x32
   8x16
   4x8

Layout:

* Level 0 is the first ``32 * 64`` pixels. Odd rows are half-swapped in
  16-pixel groups.
* Level 1 starts after level 0 and is stored as a flat 16x32 image. Odd rows
  are half-swapped in 16-pixel groups.
* Level 2 starts after level 1. Each 32-pixel storage row contributes two
  8-pixel output rows: the first 8 pixels, then skip 16 pixels, then the next
  8 pixels.
* Level 3 starts after level 2. Each 32-pixel storage row contributes two
  4-pixel output rows: the first 4 pixels, then skip 20 pixels, then the next
  4 pixels.

CI4 64x32
~~~~~~~~~

Example texture: ``tex_208_pal_209_f2_s0_64x32``.

Raw packed dimensions are normally interpreted as ``64x43`` pixels. Exported
levels are:

.. code-block:: text

   64x32
   32x16
   16x8
   8x4

Layout:

* Level 0 is the first ``64 * 32`` pixels. Odd rows are half-swapped in
  16-pixel groups.
* Level 1 starts after level 0. Each 64-pixel storage row contains two
  32-pixel output rows. The second row is half-swapped in 16-pixel groups.
* Level 2 stores four 16-pixel output rows in each 64-pixel storage row. Rows
  1 and 3 are each half-swapped as one 16-pixel group.
* Level 3 uses row offsets ``0``, ``24``, ``32``, and ``56`` inside each
  64-pixel storage row. This means it reads 8 pixels, skips 16, reads 8,
  reads 8, skips 16, and reads 8.

CI4 32x32
~~~~~~~~~

Example texture: ``tex_1272_pal_1273_f2_s0_32x32``.

Raw packed dimensions are normally interpreted as ``32x46`` pixels. Exported
levels are:

.. code-block:: text

   32x32
   16x16
   8x8
   4x4

Layout:

* Level 0 is the first ``32 * 32`` pixels. Odd rows are half-swapped in
  16-pixel groups.
* Level 1 starts after level 0 and is stored as a flat 16x16 image with no
  additional row swapping.
* Level 2 starts after level 1. Each 32-pixel storage row contributes two
  8-pixel output rows: read 8, skip 16, read 8.
* Level 3 starts after level 2. Each 32-pixel storage row contributes two
  4-pixel output rows: read 4, skip 20, read 4.

CI8 32x32
~~~~~~~~~

Example texture: ``tex_158_pal_159_f2_s1_32x32``.

Raw packed dimensions are normally interpreted as ``32x43`` pixels. Exported
levels are:

.. code-block:: text

   32x32
   16x16
   8x8
   4x4

Layout:

* Level 0 is the first ``32 * 32`` pixels. Odd rows are half-swapped in
  8-pixel groups. In practice that means each odd row is split into four
  8-pixel groups, and each group swaps its 4-pixel halves.
* Level 1 starts after level 0 and is stored as a flat 16x16 image. Odd rows
  are half-swapped in 8-pixel groups.
* Level 2 starts after level 1. Each 32-pixel storage row contains four
  8-pixel output rows. Rows 0 and 2 are read as-is. Rows 1 and 3 are
  half-swapped in 8-pixel groups.
* Level 3 starts after level 2. Each 32-pixel storage row uses row offsets
  ``0``, ``12``, ``16``, and ``28``. This corresponds to: read 4 pixels, skip
  8, read 4, read 4, skip 8, read 4. There is no swapping at this level.

Test Mipmap Export Helper
-------------------------

``test_mipmap_export()`` is a visual reverse-engineering helper. It is not used
by normal OBJ export.

It writes:

* a raw base/reference PNG named ``*_base_<width>x<height>.png``;
* the decoded highest-resolution PNG;
* decoded ``mip1``, ``mip2``, and ``mip3`` PNGs for known layouts;
* optional reference textures that have been useful while researching DK64
  mipmap packing.

This helper intentionally remains in the library for now because the mipmap
decoding work is still being validated against real assets. The long-term plan
is to remove the ad hoc helper once the remaining reverse-engineering cases are
covered by normal unit tests and production code.

Full ROM Export
---------------

``Rom.export_all()`` writes all currently supported outputs into sibling
folders:

.. code-block:: text

   exports/
     geometries/
     textures/
     text/
     cutscenes/
     assets/

Geometry exports use textured OBJ output by default. Texture table exports are
different: ``Rom.export_textures()`` writes decompressed raw table entries from
the known texture tables. Those raw texture exports are useful for analysis, but
they are not the same PNG files written beside an OBJ. OBJ texture PNGs are
decoded from the geometry texture table as display lists reference them.

Testing Coverage
----------------

The texture and OBJ behavior is covered in ``tests/test_texture_export.py``.
Important coverage includes:

* textured OBJ material and PNG output;
* OBJ vertex colors;
* UV generation from vertex texture coordinates;
* material grouping by active texture state;
* palette-based CI4 and CI8 decoding;
* RGBA, IA, and I texture decoding;
* packed mipmap exports for RGBA16 32x32, CI4 32x64, CI4 64x32, CI4 32x32,
  and CI8 32x32;
* ensuring production OBJ export does not write raw ``*_base_*`` mipmap images;
* ensuring ``test_mipmap_export()`` does write base/reference images.

Run the focused texture tests with:

.. code-block:: console

   python -m pytest tests/test_texture_export.py -q

Run the whole suite with:

.. code-block:: console

   python -m pytest -q

Known Limitations
-----------------

The current exporter is intentionally conservative:

* It supports the packed mipmap layouts that have been identified so far, not
  every possible N64 layout.
* It does not write or reference mipmap chains in the MTL. The MTL references
  the highest-resolution decoded PNG because that is what normal OBJ importers
  expect.
* It parses ``G_TEXTURE`` scale fields but does not currently apply them to OBJ
  UVs.
* It writes RGB vertex colors to OBJ but does not write vertex alpha.
* Texture clamp, mirror, mask, and shift fields are parsed in ``G_SETTILE`` but
  are not currently translated into OBJ/MTL behavior.
* Unsupported formats fall back to a placeholder image instead of failing the
  export.

These limitations are good candidates for future refactors, especially before
the eventual Rust rewrite. The current tests should be treated as behavioral
documentation for the layouts and export decisions described on this page.
