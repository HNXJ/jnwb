"""Sphinx documentation configuration for jnwb."""

import os
import sys
import pathlib

# Add repository root to path for autodoc
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import jnwb

project = "jnwb"
copyright = "2026, Hamed Nejat"
author = "Hamed Nejat"
version = jnwb.__version__
release = jnwb.__version__

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.mathjax",
    "myst_parser",
]

# MyST Markdown Parser options
myst_enable_extensions = [
    "amsmath",
    "dollarmath",
    "colon_fence",
    "fieldlist",
]
myst_heading_anchors = 3

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "README.md"]

suppress_warnings = ["misc.highlighting_failure", "toc.not_included"]

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 3,
    "includehidden": True,
    "titles_only": False,
}
html_static_path = ["_static"]
html_css_files = [
    "custom.css",
]
html_title = f"jnwb {version} Documentation"
