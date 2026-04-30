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
   * - ``0``
     - MIDI music
     - Stubbed as raw MIDI-style music sequence data.
   * - ``1``
     - Geometry
     - Parsed into map geometry objects and exported as OBJ/MTL/PNG,
       glTF/PNG, GLB, or DAE/PNG files.
   * - ``2``
     - Wall collision
     - Stubbed as raw wall collision records.
   * - ``3``
     - Floor collision
     - Stubbed as raw floor collision records.
   * - ``4``
     - Model two geometry
     - Stubbed as raw model two geometry records. The exact meaning of
       "model two" still needs to be decoded.
   * - ``5``
     - Actor geometry
     - Stubbed as raw actor geometry records, likely including bones and
       texture references.
   * - ``7``
     - Textures
     - Exported as guessed PNGs when byte size matches a known RGBA5551 size.
   * - ``8``
     - Cutscenes
     - Wrapped as raw cutscene records and exported as binary files.
   * - ``9``
     - Setups
     - Stubbed as raw setup records. The exact setup format is not decoded yet.
   * - ``10``
     - Instance scripts
     - Stubbed as raw instance script records.
   * - ``11``
     - Animation
     - Stubbed as raw animation records. It is not yet known whether entries
       target textures, models, or both.
   * - ``12``
     - Text
     - Parsed into text lines, fragments, normal text records, and sprite tokens.
   * - ``13``
     - Animation code
     - Stubbed as raw animation code records.
   * - ``14``
     - Textures
     - Exported as guessed PNGs when byte size matches a known RGBA5551 size.
   * - ``15``
     - Paths
     - Stubbed as raw path records.
   * - ``16``
     - Spawners
     - Stubbed as raw spawner records.
   * - ``17``
     - DKTV inputs
     - Stubbed as raw DKTV input records.
   * - ``18``
     - Triggers
     - Stubbed as raw trigger records.
   * - ``19``
     - Unknown
     - Stubbed as an unknown raw table. Known entries include index ``4`` as
       DK Rap lyrics and index ``7`` as end sequence credits.
   * - ``21``
     - Autowalks
     - Stubbed as raw autowalk records.
   * - ``22``
     - Critter data
     - Stubbed as raw critter records.
   * - ``23``
     - Exits
     - Stubbed as raw map exit records.
   * - ``24``
     - Race checkpoints
     - Stubbed as raw race checkpoint records.
   * - ``25``
     - Geometry textures
     - Decoded to PNG from display-list metadata, or guessed by size when
       unreferenced.
   * - ``26``
     - Uncompressed file sizes
     - Stubbed as raw uncompressed file size records.

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
lists provide enough format, size, palette, and tile information. For table 7,
table 14, and unreferenced table 25 entries, ``Rom.export_textures()`` also
writes best-effort RGBA5551 PNGs when the decompressed byte length matches a
known size guess.

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

Stubbed Table Data
------------------

:class:`dk64_lib.data_types.table_stubs.StubTableData` is used for tables with
provisional names but no decoded binary layout yet. These classes intentionally
preserve raw bytes and pointer metadata only. They give future reverse
engineering work stable API names without implying that the table format is
understood.

Use :meth:`dk64_lib.rom.Rom.get_stub_table_data` for a specific table ID, or
one of the named convenience methods such as ``get_animation_data()`` or
``get_actor_geometry_data()``. Tables ``6`` and ``20`` are still unlabeled in
the library.

Raw Assets
----------

``Rom.export_assets()`` and ``Rom.export_raw_tables()`` export raw entries from
known, parsed, and stubbed pointer tables. Use these when a table is not parsed
yet or when you need exact decompressed bytes for research.
