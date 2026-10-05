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


def _execute(path, tmp_path, monkeypatch):
    """Run the notebook top to bottom in a kernel on this tree; return it with its outputs."""
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
    return client.execute()


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_executes(path, tmp_path, monkeypatch):
    _execute(path, tmp_path, monkeypatch)


def test_unit_quality_notebook_reaches_each_outcome(tmp_path, monkeypatch):
    """The four outcomes are printed by the notebook, not only reachable by its code."""
    nb = _execute(NOTEBOOK_DIR / "unit_quality.ipynb", tmp_path, monkeypatch)
    text = "\n".join(
        "".join(o.get("text", "")) for c in nb.cells if c.cell_type == "code" for o in c.outputs
    )
    assert "request the probe geometry: spatial_derivative_sharpness" in text
    assert "contaminated unit: nan" in text
    assert "snr of one spike: nan" in text
    assert "isi_cv of two spikes: nan" in text
    assert "Declined" in text
