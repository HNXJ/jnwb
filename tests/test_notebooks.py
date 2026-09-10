"""Every notebook under examples/notebooks/ must run top to bottom against this working tree.

A notebook nobody executes rots on the first API change; this one caught it when
cross_area_coherence started requiring freq_bands.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")

NOTEBOOK_DIR = Path(__file__).resolve().parent.parent / "examples" / "notebooks"
NOTEBOOKS = sorted(NOTEBOOK_DIR.glob("*.ipynb"))


def test_there_is_a_notebook_to_run():
    assert NOTEBOOKS, f"no notebooks in {NOTEBOOK_DIR}"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_executes(path, tmp_path, monkeypatch):
    import os

    from jupyter_client.manager import KernelManager

    nb = nbformat.read(path, as_version=4)
    repo_root = str(NOTEBOOK_DIR.parent.parent)
    # The kernel inherits this environment and runs in tmp_path, so without the repo root on
    # PYTHONPATH it would import whatever jnwb is installed for this interpreter instead of
    # the tree under test.
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join([repo_root, os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep),
    )
    # The installed "python3" kernelspec launches whichever `python` is on PATH, which on a
    # machine with several interpreters is a different jnwb than the one under test.
    km = KernelManager(kernel_name="python3")
    km.kernel_spec.argv[0] = sys.executable
    client = nbclient.NotebookClient(
        nb, timeout=120, km=km, resources={"metadata": {"path": str(tmp_path)}}
    )
    client.execute()
