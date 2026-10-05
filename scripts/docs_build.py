"""Canonical strict MkDocs build for this repository.

Always invokes MkDocs with ``sys.executable`` so the docs build uses the same
interpreter as pytest and ``pip install ".[docs]"``. Bare ``mkdocs`` on PATH may
belong to a different Python and produce interpreter-dependent PASS/FAIL.

The site is written to a temporary directory that is removed afterwards, so a build leaves
nothing in the working tree. ``--keep DIR`` writes the site to ``DIR`` instead.

Usage::

    python scripts/docs_build.py
    python scripts/docs_build.py --keep /path/to/site
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def build(root: Path, site_dir: Path) -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(site_dir)],
        cwd=root,
    )
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(__file__).resolve().parent.parent
    if args[:1] == ["--keep"] and len(args) == 2:
        return build(root, Path(args[1]).resolve())
    if args:
        print("usage: docs_build.py [--keep DIR]", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="jnwb-site-") as tmp:
        return build(root, Path(tmp) / "site")


if __name__ == "__main__":
    raise SystemExit(main())
