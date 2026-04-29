Getting Started
===============

Prerequisites
-------------

``dk64_lib`` expects a legally obtained, big-endian Donkey Kong 64 ROM. The
ROM constructor checks the first byte and raises an assertion if the file is a
little-endian image.

Install the package in editable mode while working on the repository:

.. code-block:: console

   python -m pip install -e .

Open a ROM
----------

The primary entry point is :class:`dk64_lib.rom.Rom`.

.. code-block:: python

   from dk64_lib.rom import Rom

   rom = Rom("Donkey Kong 64 (USA).z64")

   print(rom.region)
   print(rom.release_or_kiosk)

Export Everything
-----------------

Use :meth:`dk64_lib.rom.Rom.export_all` when you want every currently supported
export grouped into a single folder.

.. code-block:: python

   from dk64_lib.rom import Rom

   rom = Rom("Donkey Kong 64 (USA).z64")
   exported = rom.export_all("dk64_export")

   for group, paths in exported.items():
       print(group, len(paths))

The default export includes textured GLB geometry. Use ``geometry_format="gltf"``
when you want inspectable JSON, a sidecar binary buffer, and PNG files. Use
``geometry_format="obj"`` for legacy OBJ/MTL geometry. Disable texture assets
when you only need geometry without texture materials:

.. code-block:: python

   rom.export_all("dk64_export", geometry_format="gltf")
   rom.export_all("dk64_export", geometry_format="obj")
   rom.export_all("dk64_export", include_textures=False)

Read Text Lines
---------------

Parsed text tables are available through :attr:`dk64_lib.rom.Rom.text_tables`.
Each line exposes a combined ``text`` property.

.. code-block:: python

   for text_line in rom.text_tables[0].text_lines:
       print(text_line.text)

Export Geometry
---------------

Geometry exports are written as GLB files by default. This is the preferred
Blender-friendly textured geometry container.

.. code-block:: python

   rom.export_geometries("dk64_export/geometries")

Use glTF when you want separate inspectable JSON, binary, and PNG files. Use OBJ
when you need the legacy Wavefront output:

.. code-block:: python

   rom.export_geometries("dk64_export/geometries", geometry_format="gltf")
   rom.export_geometries("dk64_export/geometries", geometry_format="obj")

COLLADA export remains available for tools that still accept DAE:

.. code-block:: python

   rom.export_geometries("dk64_export/geometries", geometry_format="dae")

Export a single geometry table entry:

.. code-block:: python

   geometry = rom.geometry_tables[0]
   geometry.save_to_obj("map_000.obj", "dk64_export/geometries")
   geometry.save_to_glb("map_000.glb", "dk64_export/geometries")
   geometry.save_to_gltf("map_000.gltf", "dk64_export/geometries")
   geometry.save_to_dae("map_000.dae", "dk64_export/geometries")

By default, OBJ export writes RGB vertex colors, UV coordinates for textured
mesh groups, MTL materials, and decoded PNG textures. GLB and glTF write RGBA
vertex colors, UV coordinates, unlit materials, PNG texture references or
embedded PNG texture data, alpha blend hints, and sampler clamp hints. DAE
export also writes textured geometry for legacy COLLADA workflows. See
:doc:`textured-geometry` for the full geometry, texture, and packed mipmap
pipeline.

Next Steps
----------

Use :doc:`asset-types` for a conceptual map of each supported data type. Use
:doc:`exports` for file naming and folder layout details. Use
:doc:`textured-geometry` when working on geometry texture behavior.
