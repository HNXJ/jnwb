"""MkDocs hook: derive the documented version from the package, never duplicate it.

A version literal written into mkdocs.yml or a Markdown page is correct only until the next
release, and nothing notices when it stops being -- the same failure class as a hardcoded symbol
count. This hook reads the single source of truth (``jnwb.__version__``) at build time and
substitutes it wherever a page writes the ``{{ jnwb_version }}`` placeholder.

The version is parsed from ``jnwb/__init__.py`` textually rather than by importing ``jnwb``:
the documentation build may run on a different interpreter than the one the package supports
(the package requires >=3.12, with no upper pin -- gate 8 of ``scripts/harness_gate.py``
fails the build on any ``<`` in that specifier), and a docs build must not depend on the
library being importable under it.

``scripts/harness_gate.py`` gate 10 verifies the resulting invariant: every version the docs
state equals the package's.
"""
from __future__ import annotations

import re
from pathlib import Path

PLACEHOLDER = "{{ jnwb_version }}"
_VERSION_RE = re.compile(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def _package_version() -> str:
    init = Path(__file__).resolve().parent.parent / "jnwb" / "__init__.py"
    match = _VERSION_RE.search(init.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError(f"could not parse __version__ from {init}")
    return match.group(1)


def on_config(config):
    config["extra"] = dict(config.get("extra") or {})
    config["extra"]["jnwb_version"] = _package_version()
    return config


def on_page_markdown(markdown, page, config, files):
    return markdown.replace(PLACEHOLDER, config["extra"]["jnwb_version"])
