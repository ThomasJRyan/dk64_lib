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

The default export includes textured geometry. Disable texture assets when you
only need legacy OBJ geometry:

.. code-block:: python

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

Geometry exports are written as OBJ files. Textured exports also create MTL and
PNG files.

.. code-block:: python

   rom.export_geometries("dk64_export/geometries")

Export a single geometry table entry:

.. code-block:: python

   geometry = rom.geometry_tables[0]
   geometry.save_to_obj("map_000.obj", "dk64_export/geometries")

By default, OBJ export writes vertex colors, UV coordinates for textured mesh
groups, MTL materials, and decoded PNG textures. See
:doc:`textured-geometry` for the full OBJ, texture, and packed mipmap pipeline.

Next Steps
----------

Use :doc:`asset-types` for a conceptual map of each supported data type. Use
:doc:`exports` for file naming and folder layout details. Use
:doc:`textured-geometry` when working on geometry texture behavior.
