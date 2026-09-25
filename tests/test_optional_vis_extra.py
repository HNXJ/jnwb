"""`jnwb.vis` is an optional extra: the core works without Plotly, and `jnwb.vis` says what to install.

CI installs the `vis` extra on the test legs, so no leg runs without Plotly. These tests make
Plotly unimportable inside a subprocess instead (``sys.modules['plotly'] = None``), which is the
state of an environment that installed `jnwb` without `[vis]`.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import jnwb
from jnwb._lazy_exports import OPTIONAL_SUBMODULES, SUBMODULES

PACKAGE_PARENT = str(Path(jnwb.__file__).resolve().parents[1])

_WITHOUT_PLOTLY = textwrap.dedent(
    """
    import sys
    sys.path.insert(0, {parent!r})
    sys.modules["plotly"] = None
    import jnwb
    from pathlib import Path
    assert str(Path(jnwb.__file__).resolve().parents[1]) == {parent!r}, jnwb.__file__
    """
)


def _run_without_plotly(body: str) -> subprocess.CompletedProcess:
    code = _WITHOUT_PLOTLY.format(parent=PACKAGE_PARENT) + textwrap.dedent(body)
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=300
    )


def test_vis_is_the_declared_optional_submodule():
    assert OPTIONAL_SUBMODULES == {"vis": "vis"}
    assert set(OPTIONAL_SUBMODULES) <= SUBMODULES
    assert set(OPTIONAL_SUBMODULES) <= set(jnwb.__all__)


def test_the_core_imports_and_resolves_without_plotly():
    result = _run_without_plotly(
        """
        from jnwb._lazy_exports import OPTIONAL_SUBMODULES
        missing = [n for n in jnwb.__all__ if n not in OPTIONAL_SUBMODULES and not hasattr(jnwb, n)]
        assert not missing, missing
        assert sys.modules["plotly"] is None, "something replaced the blocked plotly"
        print("CORE_OK", len(jnwb.__all__))
        """
    )
    assert result.returncode == 0, result.stderr
    assert "CORE_OK" in result.stdout


@pytest.mark.parametrize(
    "access",
    ["jnwb.vis", "import jnwb.vis", "from jnwb import vis"],
)
def test_vis_without_plotly_names_the_extra(access):
    result = _run_without_plotly(
        f"""
        try:
            exec({access!r})
        except ImportError as exc:
            print("MESSAGE", exc)
        else:
            raise SystemExit("no ImportError from {access}")
        """
    )
    assert result.returncode == 0, result.stderr
    assert "pip install jnwb[vis]" in result.stdout, result.stdout


def test_the_release_gate_export_sweep_passes_without_plotly():
    """The pre-tag check installs the wheel without extras and then sweeps `jnwb.__all__`.
    A sweep by `hasattr` sees only AttributeError, so `jnwb.vis` failed it on every run."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "release_gate.py").read_text(
        encoding="utf-8"
    )
    start = source.index("# 3. Test all exported symbols in __all__")
    sweep = source[start:source.index("# 4. Workflows", start)]
    result = _run_without_plotly(sweep)
    assert result.returncode == 0, result.stderr
    assert "name their extra" in result.stdout, result.stdout


def test_the_api_row_for_vis_is_the_one_an_import_would_render():
    """The generator reads `jnwb.vis`'s row from source so the page does not depend on Plotly.
    With Plotly present, that row must equal the row rendered from the imported module."""
    pytest.importorskip("plotly")
    # `append`, never `insert(0, ...)`: prepending the checkout would shadow an installed jnwb.
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.append(repo_root)
    from scripts import generate_api_md as gen

    static = gen._optional_submodule_cell("vis")
    imported = gen._format_cell(jnwb.vis, gen._object_type_name(jnwb.vis))
    assert static == imported
    assert static != "*"
