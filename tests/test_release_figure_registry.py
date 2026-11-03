"""The release gate requires every figure to be rendered by the released version.

Between releases a registry entry keeps the version that rendered it; at a release each entry
names the declared version, so the published figures are that version's.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

from scripts import release_gate  # noqa: E402
from scripts.release_gate import figure_registry_violation  # noqa: E402

_INIT = '__version__ = "4.1.0"\n'


def _entry(version: str) -> str:
    return f'code_sha256 = "abc"\njnwb_version = "{version}"\n'


@pytest.fixture
def files(monkeypatch):
    held = {}
    monkeypatch.setattr(release_gate, "_text_at", lambda root, rev, path: held.get(path))
    return held


def test_every_figure_rendered_by_the_declared_version_passes(files):
    files[release_gate.VERSION_PATH] = _INIT
    files[release_gate.FIGURE_REGISTRY_PATH] = "[figA]\n" + _entry("4.1.0") + "[figB]\n" + _entry("4.1.0")
    assert figure_registry_violation(REPO_ROOT) is None


def test_a_figure_rendered_by_an_earlier_version_is_named(files):
    files[release_gate.VERSION_PATH] = _INIT
    files[release_gate.FIGURE_REGISTRY_PATH] = "[figA]\n" + _entry("4.1.0") + "[figB]\n" + _entry("4.0.9")
    problem = figure_registry_violation(REPO_ROOT)
    assert problem is not None and "1 figure(s)" in problem and "figB" in problem
    assert "figA" not in problem


@pytest.mark.parametrize("registry", [None, "", "not = [toml"])
def test_a_missing_or_unreadable_registry_fails(files, registry):
    files[release_gate.VERSION_PATH] = _INIT
    if registry is not None:
        files[release_gate.FIGURE_REGISTRY_PATH] = registry
    problem = figure_registry_violation(REPO_ROOT)
    assert problem is not None and release_gate.FIGURE_REGISTRY_PATH in problem


def test_no_declared_version_fails(files):
    files[release_gate.FIGURE_REGISTRY_PATH] = "[figA]\n" + _entry("4.1.0")
    assert "declares no __version__" in figure_registry_violation(REPO_ROOT)


def test_the_live_registry_parses_and_every_entry_names_a_version():
    problem = figure_registry_violation(REPO_ROOT)
    assert problem is None or "rendered by another jnwb" in problem
