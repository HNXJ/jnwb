"""Deprecated shim — use scripts/run_notebook_local.py instead.

This module used to be a standalone duplicate notebook-cell executor. It is
now a thin wrapper around run_notebook_local.run_notebook(), kept only for
backward-compatible imports/CLI calls. New code should import
scripts.run_notebook_local directly.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_notebook_local import run_notebook as _run_notebook_local


def run_notebook(path):
    warnings.warn(
        "scripts.run_notebook_remote.run_notebook is deprecated; "
        "use scripts.run_notebook_local.run_notebook instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _run_notebook_local(Path(path))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_notebook_remote.py <notebook_path>")
        sys.exit(1)
    ok = run_notebook(sys.argv[1])
    sys.exit(0 if ok else 1)
