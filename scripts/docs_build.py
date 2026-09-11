"""Canonical strict MkDocs build for this repository.

Always invokes MkDocs with ``sys.executable`` so the docs build uses the same
interpreter as pytest and ``pip install ".[docs]"``. Bare ``mkdocs`` on PATH may
belong to a different Python and produce interpreter-dependent PASS/FAIL.

Usage::

    python scripts/docs_build.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict"],
        cwd=root,
    )
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
