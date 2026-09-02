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

master_doc = "index"
language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = []
html_title = f"jnwb {version} Documentation"
