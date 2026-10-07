"""Every notebook under examples/notebooks/ must run top to bottom against this working tree.

A notebook nobody executes rots on the first API change; this one caught it when
cross_area_coherence started requiring freq_bands.
"""
from __future__ import annotations

import atexit
import sys
import threading
import time
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")

NOTEBOOK_DIR = Path(__file__).resolve().parent.parent / "examples" / "notebooks"
NOTEBOOKS = sorted(NOTEBOOK_DIR.glob("*.ipynb"))


def test_there_is_a_notebook_to_run():
    assert NOTEBOOKS, f"no notebooks in {NOTEBOOK_DIR}"


# Seconds. The bounds sum to the longest a notebook may hold the suite.
KERNEL_START_TIMEOUT_S = 180  # a kernel under 24 busy processes needed over 60 s to answer
CELL_TIMEOUT_S = 300  # per cell; the first import cell took 120 s under 24 busy processes
KERNEL_SHUTDOWN_TIMEOUT_S = 15  # graceful stop, then the manager kills the process


_LAST_RUN = {}  # the manager and budget of the latest _execute, for the tests below


def _execute(path, tmp_path, monkeypatch, kernel_argv=None):
    """Run the notebook top to bottom in a kernel on this tree; return it with its outputs."""
    import os

    from jupyter_client.manager import AsyncKernelManager

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
    # The async manager keeps nbclient's event loop free: with a blocking KernelManager a busy
    # kernel stops the cell timeout from ever firing and the run never returns.
    km = AsyncKernelManager(kernel_name="python3")
    km.kernel_spec.argv[0] = sys.executable
    if kernel_argv is not None:
        km.kernel_spec.argv = list(kernel_argv)
    km.shutdown_wait_time = KERNEL_SHUTDOWN_TIMEOUT_S
    client = nbclient.NotebookClient(
        nb,
        timeout=CELL_TIMEOUT_S,
        startup_timeout=KERNEL_START_TIMEOUT_S,
        km=km,
        resources={"metadata": {"path": str(tmp_path)}},
    )
    # Backstop for a stall the bounds above do not reach: the run goes to a worker thread, and a
    # kernel that outlives the summed bounds is killed and fails this test by name.
    budget = KERNEL_START_TIMEOUT_S + CELL_TIMEOUT_S * len(nb.cells) + KERNEL_SHUTDOWN_TIMEOUT_S
    _LAST_RUN.update(km=km, budget=budget)
    outcome = {}

    def run():
        try:
            outcome["nb"] = client.execute()
        except BaseException as exc:
            outcome["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(budget)
    # A failed start leaves nbclient's exit hook behind, which then asserts on a dead manager.
    # The hook is a private attribute of nbclient 0.11; without it there is nothing to remove.
    hook = getattr(client, "_cleanup_kernel", None)
    if hook is not None:
        atexit.unregister(hook)
    if worker.is_alive():
        try:
            km.provisioner.process.kill()
        except Exception:
            pass
        pytest.fail(f"{path.name}: kernel did not finish within {budget} s", pytrace=False)
    if "error" in outcome:
        raise outcome["error"]
    return outcome["nb"]


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


def _stalled_notebook(tmp_path, cells=1):
    nb = nbformat.v4.new_notebook(
        cells=[nbformat.v4.new_code_cell("import time; time.sleep(1000)") for _ in range(cells)]
    )
    path = tmp_path / "stalled.ipynb"
    nbformat.write(nb, path)
    return path


def _shrink_bounds(monkeypatch, start, cell, shutdown):
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "KERNEL_START_TIMEOUT_S", start)
    monkeypatch.setattr(module, "CELL_TIMEOUT_S", cell)
    monkeypatch.setattr(module, "KERNEL_SHUTDOWN_TIMEOUT_S", shutdown)


def test_stalled_cell_fails_within_the_cell_bound(tmp_path, monkeypatch):
    # The start bound is generous because a loaded machine starts a real kernel slowly; the
    # stalled cell sleeps 1000 s, so any bound far under that still shows the cell bound works.
    _shrink_bounds(monkeypatch, start=120, cell=3, shutdown=2)
    path = _stalled_notebook(tmp_path)
    began = time.monotonic()
    with pytest.raises(nbclient.exceptions.CellTimeoutError, match="timed out"):
        _execute(path, tmp_path, monkeypatch)
    assert time.monotonic() - began < 120 + 3 + 2 + 30


def _silent_kernel_argv(tmp_path):
    """A kernel process that never answers and ignores the stop request."""
    stub = tmp_path / "silent_kernel.py"
    stub.write_text("import time\ntime.sleep(10_000)\n")
    return [sys.executable, str(stub), "{connection_file}"]


def test_kernel_that_never_starts_fails_within_the_start_bound(tmp_path, monkeypatch):
    _shrink_bounds(monkeypatch, start=4, cell=60, shutdown=1)
    path = _stalled_notebook(tmp_path)
    import jupyter_client.manager  # noqa: F401  the cold import stays out of the timed window
    began = time.monotonic()
    with pytest.raises(RuntimeError, match="Kernel didn't respond"):
        _execute(path, tmp_path, monkeypatch, kernel_argv=_silent_kernel_argv(tmp_path))
    # Under nbclient's own 60 s default, so a dropped start bound shows.
    assert time.monotonic() - began < 30
    assert _LAST_RUN["km"].shutdown_wait_time == 1


def test_bounds_stay_finite_and_small():
    bounds = (KERNEL_START_TIMEOUT_S, CELL_TIMEOUT_S, KERNEL_SHUTDOWN_TIMEOUT_S)
    assert all(0 < b for b in bounds)
    assert sum(bounds) <= 600  # one cell; each further cell adds CELL_TIMEOUT_S


def test_run_that_outlives_the_bounds_fails_by_name_and_counts_every_cell(tmp_path, monkeypatch):
    _shrink_bounds(monkeypatch, start=1, cell=1, shutdown=1)
    monkeypatch.setattr(nbclient.NotebookClient, "execute", lambda self, **kw: time.sleep(60))
    path = _stalled_notebook(tmp_path, cells=3)
    began = time.monotonic()
    # 1 start + 3 cells of 1 + 1 shutdown
    with pytest.raises(pytest.fail.Exception, match="stalled.ipynb: kernel did not finish within 5 s"):
        _execute(path, tmp_path, monkeypatch)
    assert time.monotonic() - began < 5 + 15


def test_run_that_outlives_the_bounds_kills_its_kernel(tmp_path, monkeypatch):
    # The kernel process starts, then the client never finishes starting; start 15 s covers a
    # slow spawn on a loaded machine before the join gives up.
    _shrink_bounds(monkeypatch, start=15, cell=1, shutdown=1)

    async def never(self):
        import asyncio

        await asyncio.sleep(3600)

    monkeypatch.setattr(nbclient.NotebookClient, "async_start_new_kernel_client", never)
    path = _stalled_notebook(tmp_path)
    try:
        with pytest.raises(pytest.fail.Exception, match="kernel did not finish"):
            _execute(path, tmp_path, monkeypatch, kernel_argv=_silent_kernel_argv(tmp_path))
        process = _LAST_RUN["km"].provisioner.process
        assert process.wait(timeout=10) is not None  # raises TimeoutExpired if still running
    finally:
        provisioner = getattr(_LAST_RUN["km"], "provisioner", None)
        if provisioner is not None and provisioner.process.poll() is None:
            provisioner.process.kill()


def test_exit_hook_is_not_left_registered(tmp_path, monkeypatch):
    registered, removed = [], []
    real_register, real_unregister = atexit.register, atexit.unregister
    monkeypatch.setattr(atexit, "register", lambda f, *a, **k: (registered.append(f), real_register(f, *a, **k))[1])
    monkeypatch.setattr(atexit, "unregister", lambda f: (removed.append(f), real_unregister(f))[1])
    _shrink_bounds(monkeypatch, start=4, cell=60, shutdown=1)
    path = _stalled_notebook(tmp_path)
    with pytest.raises(RuntimeError):
        _execute(path, tmp_path, monkeypatch, kernel_argv=_silent_kernel_argv(tmp_path))
    own = [f for f in registered if getattr(f, "__self__", None).__class__ is nbclient.NotebookClient]
    assert all(f in removed for f in own)

