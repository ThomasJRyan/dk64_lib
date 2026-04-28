"""Sphinx configuration for dk64_lib documentation."""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

project = "dk64_lib"
author = "dk64_lib contributors"
copyright = "2026, dk64_lib contributors"

try:
    release = package_version("dk64_lib")
except PackageNotFoundError:
    release = "0.1.0"
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

autosummary_generate = True
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autoclass_content = "both"
napoleon_google_docstring = True
napoleon_numpy_docstring = True

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
html_title = "dk64_lib"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_show_sourcelink = True
html_theme_options = {
    "description": "Donkey Kong 64 ROM data extraction tools",
    "fixed_sidebar": True,
    "page_width": "1120px",
    "sidebar_width": "260px",
    "show_powered_by": False,
}

pygments_style = "friendly"
