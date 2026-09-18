"""Executes `examples/quickstart_jnwb.py`, which nothing executed.

The script is named in `AGENTS.md` as the smallest end-to-end script and in
`docs/quickstart.md` as the authoritative smoke test, and both README and that page call it
executable. Nothing in the suite ran it, so it stayed broken across a release: 0.2.x
tightened `permute_labels` to refuse a design with one label per group, which is exactly
the design the permutation panel builds on purpose, and the script died there with a
`ValueError` after writing no figure at all.

`main()` writes into a module-level `OUT` under `examples/figures/`, which is tracked. The
tests redirect that constant at `tmp_path` so running the suite cannot dirty the checkout
with a figure whose bytes differ by matplotlib version.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "examples" / "quickstart_jnwb.py"


@pytest.fixture(scope="module")
def quickstart():
    """Imports the script as a module without executing its `__main__` guard."""
    assert SCRIPT.is_file(), f"{SCRIPT} does not exist; this file tests nothing"
    spec = importlib.util.spec_from_file_location("_quickstart_jnwb_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(spec.name, None)


def test_the_quickstart_script_runs_end_to_end(quickstart, monkeypatch, tmp_path, capsys):
    """The failure this whole file exists for: the script raised instead of finishing."""
    monkeypatch.setattr(quickstart, "OUT", str(tmp_path))
    quickstart.main()

    for ext in ("svg", "png"):
        written = tmp_path / f"jnwb_quickstart.{ext}"
        assert written.is_file() and written.stat().st_size > 0, f"no {ext} was written"

    out = capsys.readouterr().out
    for _, api, _ in quickstart.PANELS:
        assert api in out, f"{api} produced no line, so its panel did not report a result"


def test_every_panel_returns_a_caption(quickstart):
    """Each panel's return value is printed and drawn, so an empty one is a silent hole."""
    assert len(quickstart.PANELS) == 6, "the panel list changed; check the figure layout"
    for title, api, fn in quickstart.PANELS:
        fig, ax = plt.subplots()
        try:
            caption = fn(ax)
        finally:
            plt.close(fig)
        assert isinstance(caption, str) and caption.strip(), f"{title} returned no caption"


def test_the_permutation_panel_draws_the_refusal_instead_of_dying_on_it(quickstart):
    """Non-vacuity: confirms the `except` branch is the one this panel reaches today.

    If `permute_labels` ever accepts a design with one label per group again, the panel
    falls back to its histogram and this assertion fails rather than quietly leaving the
    branch untested.
    """
    fig, ax = plt.subplots()
    try:
        caption = quickstart.panel_permutation(ax)
    finally:
        plt.close(fig)
    assert "refused" in caption, (
        "the panel took the histogram branch, so jnwb no longer refuses a within-group "
        "null over group-constant labels and the refusal this panel teaches is stale"
    )


def test_the_script_says_which_jnwb_it_imported(quickstart, monkeypatch, tmp_path, capsys):
    """Run as documented, `python examples/quickstart_jnwb.py` need not import this tree.

    Python puts the script's own directory on `sys.path`, not the repository root, so
    `import jnwb` resolves to whatever is installed. A stale install therefore renders a
    six-panel figure of a different library while sitting inside this checkout, and every
    panel still says CORRECT. The line is the only thing that distinguishes the two.
    """
    import jnwb

    monkeypatch.setattr(quickstart, "OUT", str(tmp_path))
    quickstart.main()
    out = capsys.readouterr().out.splitlines()[0]
    assert jnwb.__version__ in out and str(Path(jnwb.__file__).parent) in out, (
        f"first line {out!r} does not identify the jnwb that ran"
    )
