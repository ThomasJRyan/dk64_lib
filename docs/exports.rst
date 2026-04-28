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

Set ``include_assets=False`` to skip raw asset table exports. Set
``include_textures=False`` to write legacy geometry-only OBJ files.

Geometry
--------

.. code-block:: python

   paths = rom.export_geometries("dk64_export/geometries")

Textured geometry export writes:

* ``###_<map_name>.obj``
* ``###_<map_name>.mtl``
* ``textures/<material_name>.png``
* ``textures/<material_name>_mip<level>_<width>x<height>.png`` when packed
  mipmap levels are decoded

Pointer entries are written as:

.. code-block:: text

   ###_<map_name>.pointer.txt

The pointer file contains the target geometry table index.

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

Texture table entries are exported as decompressed binary files grouped by
source table:

.. code-block:: text

   table_07/000000_offset_00123456.bin
   table_14/000000_offset_00123456.bin
   table_25/000000_offset_00123456.bin

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
