Repository Guide
================

This repository uses a small ``src`` layout package with tests and generated
fixtures kept outside the library code.

Top-Level Layout
----------------

``src/dk64_lib/``
    Library source code.

``tests/``
    Unit tests and ROM-dependent integration tests.

``tests/verified_objs/``
    Known OBJ output fixtures used by geometry tests.

``tests/dk64_rom/``
    Local ROM placement folder for tests that need a ROM. ROM files are ignored
    by git.

``docs/``
    Sphinx documentation source and generated documentation build output.
    ``docs/textured-geometry.rst`` is the primary narrative reference for OBJ,
    glTF/GLB, DAE, UV, texture, and packed mipmap export behavior.

Library Modules
---------------

``dk64_lib.rom``
    Main ROM facade, pointer table traversal, and high-level exporters.

``dk64_lib.data_types``
    Parsed ROM data wrappers. These classes share common raw-data metadata from
    ``BaseData`` and add format-specific parsing where available.

``dk64_lib.f3dex2``
    F3DEX2 display-list command parsing plus textured OBJ, glTF/GLB, and DAE
    export helpers, including geometry value objects such as vertices and
    triangles.

``dk64_lib.constants``
    Generated or maintained lookup tables for map names and sprite names.

``dk64_lib.binary_reader`` and ``dk64_lib.file_io``
    Byte-reading utilities used by parsers.

Development Notes
-----------------

The library currently favors explicit parser objects over broad abstractions.
When adding a new ROM data type, first decide whether it belongs behind the
``Rom`` facade as a high-level table reader or whether it is a lower-level
helper used by an existing parser.

Tests use fake ROM objects for exporter behavior where possible. ROM-dependent
tests look in ``tests/dk64_rom/``.
