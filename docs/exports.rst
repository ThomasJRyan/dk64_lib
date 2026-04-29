Export Reference
================

All high-level exporters return the paths they write. This makes them easy to
use from scripts and tests.

Export All
----------

.. code-block:: python

   exported = rom.export_all("dk64_export")

Default output:

.. code-block:: text

   dk64_export/
     geometries/
     textures/
     text/
     cutscenes/
     assets/

Set ``include_assets=False`` to skip raw asset table exports. Geometry export
uses single-file binary glTF by default. Set ``geometry_format="gltf"`` for
separate glTF JSON/binary/PNG assets, ``"obj"`` for legacy OBJ/MTL files, or
``"dae"`` for legacy COLLADA files. Set ``include_textures=False`` to write
geometry without texture materials.

Geometry
--------

.. code-block:: python

   paths = rom.export_geometries("dk64_export/geometries")

Textured GLB geometry export writes by default:

* ``###_<map_name>.glb``

The default call is:

.. code-block:: python

   paths = rom.export_geometries("dk64_export/geometries")

Textured OBJ geometry export is selected with ``geometry_format="obj"``. It
writes:

* ``###_<map_name>.obj``
* ``###_<map_name>.mtl``
* ``textures/<material_name>.png``
* ``textures/<material_name>_mip<level>_<width>x<height>.png`` when packed
  mipmap levels are decoded

Textured glTF geometry export is selected with:

.. code-block:: python

   paths = rom.export_geometries(
       "dk64_export/geometries",
       geometry_format="gltf",
   )

It writes:

* ``###_<map_name>.gltf``
* ``###_<map_name>.bin``
* ``textures/<material_name>.png``
* ``textures/<material_name>_mip<level>_<width>x<height>.png`` when packed
  mipmap levels are decoded

Textured DAE geometry export is selected with:

.. code-block:: python

   paths = rom.export_geometries(
       "dk64_export/geometries",
       geometry_format="dae",
   )

It writes:

* ``###_<map_name>.dae``
* ``textures/<material_name>.png``
* ``textures/<material_name>_alpha.png`` when the highest-resolution texture
  contains transparent pixels
* ``textures/<material_name>_mip<level>_<width>x<height>.png`` when packed
  mipmap levels are decoded

DAE export can also build a Blender preview for caller-supplied animated texture
frames:

.. code-block:: python

   paths = rom.export_geometries(
       "dk64_export/geometries",
       geometry_format="dae",
       animated_texture_frames={31: range(31, 39)},
       animation_frame_duration=4,
   )

For those materials, the exporter writes
``textures/<material_name>_anim_<count>frames.png`` and an
``animated_textures.blender.py`` helper. The DAE references frame 0 in the atlas;
run the helper script in Blender after importing the DAE to keyframe the atlas
offset across the supplied frames.

Pointer entries are written as:

.. code-block:: text

   ###_<map_name>.pointer.txt

The pointer file contains the target geometry table index.

OBJ exports include RGB vertex colors on ``v`` lines. GLB, glTF, and DAE
exports include RGBA vertex colors. Textured groups include UV coordinates and
material bindings. OBJ writes ``usemtl`` statements and MTL ``map_Kd`` entries;
GLB and glTF write glTF PBR materials with ``KHR_materials_unlit`` and diffuse
texture references; DAE writes material effects with diffuse texture references.
Textures with transparent pixels also get dedicated ``*_alpha.png`` opacity
masks for OBJ and DAE. OBJ references those masks with ``map_d``; DAE references
them from the material ``transparent`` channel. GLB and glTF use the PNG color
texture's alpha channel directly and set transparent materials to
``alphaMode="BLEND"``. GLB and glTF also set ``alphaMode="BLEND"`` when a mesh
group uses vertex alpha below full opacity, creating a separate
``*_vertex_alpha`` material variant when only some groups using an opaque
texture need blending. Textures using clamped DK64 tile state get clamped UVs.
OBJ also emits ``-clamp on`` MTL texture map hints. DAE emits ``wrap_s`` and
``wrap_t`` sampler hints, while GLB and glTF emit glTF sampler ``wrapS`` and
``wrapT`` values.
For OBJ exports, if any exported material is transparent, the exporter also writes
``<obj_stem>.blender.py``. Run that script after importing the OBJ in Blender to
switch those transparent materials to Blender's Blended render method.
When a known DK64 packed mipmap layout is decoded, the MTL points at the
highest-resolution PNG while the additional mip levels are written beside it.
GLB, glTF, and DAE follow the same highest-resolution material binding.
The production exporter does not write raw ``*_base_*`` mipmap reference images.
For the full pipeline and mipmap layout notes, see :doc:`textured-geometry`.

Text
----

.. code-block:: python

   paths = rom.export_text("dk64_export/text")

Text exports use one file per text table:

.. code-block:: text

   text_000.txt
   text_001.txt

Each line is prefixed with a zero-padded line index:

.. code-block:: text

   0000: WELCOME TO THE BONUS STAGE!

Textures
--------

.. code-block:: python

   paths = rom.export_textures("dk64_export/textures")

Texture export writes PNG files from two metadata sources. Geometry-referenced
table 25 textures use F3DEX2 display-list state, which provides the format,
size, palette, width, and height:

.. code-block:: text

   table_25/tex_0_pal_1_f2_s0_32x64.png
   table_25/tex_2_pal_none_f0_s2_32x32.png
   table_25/tex_158_pal_159_f2_s1_32x32_mip1_16x16.png

Table 7, table 14, and unreferenced table 25 entries use a best-effort size
guess based on decompressed byte length. The current guess table treats these
sizes as RGBA5551: ``0x1000`` as ``32x64``, ``0x800`` as ``32x32``,
``0xfc0`` as ``48x42``, ``0xaa0`` as ``32x44``, and ``0xf20`` as ``44x44``.
Guessed files include ``guess`` in their filenames:

.. code-block:: text

   table_07/000000_offset_00123456_guess_f0_s2_32x32.png
   table_14/000000_offset_00123456_guess_f0_s2_32x64.png

Use ``Rom.export_assets()`` or ``Rom.export_raw_tables()`` when you need exact
decompressed ``.bin`` records for analysis.

Cutscenes
---------

.. code-block:: python

   paths = rom.export_cutscenes("dk64_export/cutscenes")

Cutscene table entries are exported as raw binary files:

.. code-block:: text

   cutscene_000_offset_00123456.bin

Raw Tables
----------

.. code-block:: python

   paths = rom.export_assets("dk64_export/assets", tables=(1, 7, 8, 12, 14, 25))

Raw asset exports use the same table folder and offset naming convention as
texture exports.
