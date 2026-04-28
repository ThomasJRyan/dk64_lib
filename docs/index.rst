DK64 Lib Documentation
======================

.. raw:: html

   <section class="hero">
     <p class="hero-kicker">Python tooling for Donkey Kong 64 ROM data</p>
     <h1>Extract DK64 text, geometry, display lists, textures, and raw assets.</h1>
     <p class="hero-copy">
       dk64_lib reads big-endian DK64 ROMs, walks the pointer tables, parses the
       asset types that are currently understood, and exports useful files for
       analysis and tooling.
     </p>
     <div class="hero-actions">
       <a class="button primary" href="getting-started.html">Get started</a>
       <a class="button secondary" href="asset-types.html">Browse asset types</a>
     </div>
   </section>

.. raw:: html

   <section class="card-grid" aria-label="Documentation sections">
     <a class="doc-card" href="getting-started.html">
       <span class="card-label">Start</span>
       <strong>Getting Started</strong>
       <span>Install the package, open a ROM, and run the common export workflows.</span>
     </a>
     <a class="doc-card" href="asset-types.html">
       <span class="card-label">Data</span>
       <strong>Asset Types</strong>
       <span>Understand text tables, geometry, textures, cutscenes, and raw table exports.</span>
     </a>
     <a class="doc-card" href="exports.html">
       <span class="card-label">Output</span>
       <strong>Export Reference</strong>
       <span>See which files are produced by each exporter and how they are named.</span>
     </a>
     <a class="doc-card" href="textured-geometry.html">
       <span class="card-label">Pipeline</span>
       <strong>Textured Geometry</strong>
       <span>Follow OBJ/DAE export, UV mapping, vertex colors, texture decoding, and DK64 mipmaps.</span>
     </a>
     <a class="doc-card" href="api/index.html">
       <span class="card-label">API</span>
       <strong>Python Reference</strong>
       <span>Jump into autodoc pages for Rom, data objects, display lists, and utilities.</span>
     </a>
   </section>

What dk64_lib Handles
---------------------

``dk64_lib`` focuses on the asset tables exposed by the DK64 ROM pointer table.
The current library surface covers:

* ROM metadata and pointer table traversal through :class:`dk64_lib.rom.Rom`.
* Text parsing into immutable text line and fragment records.
* Geometry parsing into display lists, vertices, and triangles.
* Textured OBJ/DAE export with companion material data and PNG textures.
* Raw exports for known texture, cutscene, text, geometry, and asset tables.

The documentation is intentionally structured around ROM concepts first and API
details second. Start with :doc:`getting-started`, then use
:doc:`asset-types` as the data model map while extending the library.

.. toctree::
   :maxdepth: 2
   :hidden:

   getting-started
   repository-guide
   asset-types
   exports
   textured-geometry
   api/index
