Asset Types
===========

``dk64_lib`` models ROM data as table entries. Every parsed object carries raw
metadata from :class:`dk64_lib.data_types.base.BaseData`: ``raw_data``,
``offset``, ``size``, ``was_compressed``, and the source ``rom``.

Pointer Tables
--------------

The high-level ROM facade currently knows these table families:

.. list-table::
   :header-rows: 1
   :widths: 12 24 64

   * - Table
     - Data
     - Current support
   * - ``1``
     - Geometry
     - Parsed into map geometry objects and exported as OBJ/MTL/PNG,
       glTF/PNG, GLB, or DAE/PNG files.
   * - ``7``
     - Textures
     - Available through raw asset export.
   * - ``8``
     - Cutscenes
     - Wrapped as raw cutscene records and exported as binary files.
   * - ``12``
     - Text
     - Parsed into text lines, fragments, normal text records, and sprite tokens.
   * - ``14``
     - Textures
     - Available through raw asset export.
   * - ``25``
     - Geometry textures
     - Decoded to PNG when referenced by geometry display lists.

Text Data
---------

:class:`dk64_lib.data_types.text.TextData` parses text table entries into
immutable records:

* ``text_lines`` is a tuple of parsed line records.
* Each line can contain one or more fragments.
* Fragments contain normal text records or sprite tokens.
* ``text_line.text`` joins those fragments into a readable string.

Sprite tokens are resolved against release or kiosk sprite lookup tables,
depending on the ROM type.

Geometry Data
-------------

:class:`dk64_lib.data_types.geometry.GeometryData` parses map geometry table
entries. A geometry entry can also be a pointer record that references another
geometry table entry.

Parsed geometry exposes:

* ``display_lists`` as :class:`dk64_lib.f3dex2.display_list.DisplayList`
  objects.
* ``vertex_chunk_data`` as 52-byte display-list chunk metadata records.
* ``dl_expansions`` for expansion records that point at additional display
  lists.
* ``save_to_obj()`` for OBJ export, textured by default.
* ``save_to_gltf()`` for separate glTF JSON, binary, and PNG export.
* ``save_to_glb()`` for single-file binary glTF export.
* ``save_to_dae()`` for COLLADA export, textured by default.

Display lists are decoded into F3DEX2 commands, vertices, and triangles. The
textured OBJ, glTF/GLB, and DAE exporters follow texture state commands to
group mesh faces by material.

Texture Data
------------

:class:`dk64_lib.data_types.texture.TextureData` currently wraps raw texture
table entries. ``Rom.export_textures()`` and the textured geometry export path
decode referenced table 25 texture bytes into PNG images when geometry display
lists provide enough format, size, palette, and tile information.

Supported texture decoding includes:

* RGBA16
* RGBA32
* CI4 and CI8 with palette data
* IA formats
* I formats
* A few packed mipmap layouts used by DK64 assets

Unknown or unsupported texture combinations produce placeholder RGBA data
instead of failing the full export.

For the detailed geometry texture pipeline, including OBJ, glTF/GLB, and DAE
materials, UV conversion, vertex colors, palette handling, and the currently
decoded packed mipmap layouts, see :doc:`textured-geometry`.

Cutscene Data
-------------

:class:`dk64_lib.data_types.cutscene.CutsceneData` currently stores cutscene
table entries as raw binary records. The high-level exporter writes those bytes
to ``cutscene_###_offset_########.bin`` files.

Raw Assets
----------

``Rom.export_assets()`` and ``Rom.export_raw_tables()`` export raw entries from
supported pointer tables. Use these when a table is not parsed yet or when you
need exact decompressed bytes for research.
