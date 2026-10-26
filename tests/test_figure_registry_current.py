"""The figure registry is the generator's record of each figure, and it is current.

Each entry carries the hash of the code and the jnwb version of the run that wrote it, and the
panels the interactive converter cannot draw. This test draws every figure and holds each of those
to the live code, so a stale registry, or a panel the converter cannot draw that is not listed,
fails.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURE_SCRIPTS = REPO_ROOT / "scripts" / "figures"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, FIGURE_SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


registry = _load("figure_registry")
ENTRIES = registry.loads(registry.REGISTRY.read_text(encoding="utf-8"))
generator = _load("generate_figures")


def test_the_registry_has_one_entry_per_figure():
    assert sorted(ENTRIES) == sorted(generator.FIGURES), "registry and FIGURES disagree"


def test_the_registry_is_current_with_the_code_and_the_jnwb_version():
    assert ENTRIES, "the registry is empty"
    for name, entry in ENTRIES.items():
        assert entry["code_sha256"] == registry.code_sha256(), f"{name} is stale: rerun the generator"
        assert entry["jnwb_version"] == jnwb.__version__, f"{name} was written by another jnwb"


@pytest.mark.parametrize("name", sorted(ENTRIES))
def test_the_named_panels_and_the_sample_are_the_live_ones(name):
    converted, _, sample_size = generator.convert_figure(name)
    assert converted.reasons == ENTRIES[name]["unconvertible"], (
        f"{name}: the converter now reports {converted.reasons}; list them with --write-registry")
    assert sample_size == (ENTRIES[name]["n"], ENTRIES[name]["n_unit"]), (
        f"{name}: the figure now records {sample_size}; rerun the generator with --write-registry")
