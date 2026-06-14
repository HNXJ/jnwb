"""Lint jnwb example notebooks for import-only discipline."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import jnwb
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

JNWB_NOTEBOOKS = [
    REPO_ROOT / "notebooks" / "00_jnwb_discovery_and_addressing.ipynb",
    REPO_ROOT / "notebooks" / "01_jnwb_epoch_artifacts.ipynb",
    REPO_ROOT / "notebooks" / "02_f005_from_artifacts.ipynb",
    REPO_ROOT / "notebooks" / "03_jnwb_visual_qc.ipynb",
]

FORBIDDEN_PRIVATE_IMPORTS = (
    "_omission_run_common",
    "notebooks._omission_run_common",
)

CORE_JNWB_API_BY_NOTEBOOK: dict[str, list[str]] = {
    "00_jnwb_discovery_and_addressing.ipynb": [
        "list_nwb_files",
        "inspect_nwb",
        "build_session_manifest",
        "address_events",
        "address_signals",
    ],
    "01_jnwb_epoch_artifacts.ipynb": [
        "load_epochs",
        "save_epoch_artifact",
        "load_epoch_artifact",
    ],
    "02_f005_from_artifacts.ipynb": [
        "load_epoch_artifact",
    ],
    "03_jnwb_visual_qc.ipynb": [
        "run_visual_qc",
    ],
}

CORE_JNWB_API = [
    "list_nwb_files",
    "inspect_nwb",
    "build_session_manifest",
    "address_events",
    "address_signals",
    "load_epochs",
    "save_epoch_artifact",
    "load_epoch_artifact",
]


def _load_notebook(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _code_cells(nb: dict) -> list[str]:
    return [
        "".join(cell.get("source", []))
        for cell in nb.get("cells", [])
        if cell.get("cell_type") == "code"
    ]


def _notebook_source(nb: dict) -> str:
    return "\n\n".join(_code_cells(nb))


def _find_local_defs(source: str) -> list[str]:
    tree = ast.parse(source)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            offenders.append(f"{type(node).__name__}:{node.name}")
    return offenders


@pytest.mark.parametrize("notebook_path", JNWB_NOTEBOOKS, ids=[p.name for p in JNWB_NOTEBOOKS])
def test_notebook_exists(notebook_path: Path):
    assert notebook_path.exists(), f"Missing notebook: {notebook_path}"


@pytest.mark.parametrize("notebook_path", JNWB_NOTEBOOKS, ids=[p.name for p in JNWB_NOTEBOOKS])
def test_notebook_no_local_functions_or_classes(notebook_path: Path):
    nb = _load_notebook(notebook_path)
    offenders = _find_local_defs(_notebook_source(nb))
    assert not offenders, f"{notebook_path.name} defines reusable code: {offenders}"


@pytest.mark.parametrize("notebook_path", JNWB_NOTEBOOKS, ids=[p.name for p in JNWB_NOTEBOOKS])
def test_notebook_no_private_helper_imports(notebook_path: Path):
    nb = _load_notebook(notebook_path)
    source = _notebook_source(nb)
    for token in FORBIDDEN_PRIVATE_IMPORTS:
        assert token not in source, f"{notebook_path.name} imports private helper {token!r}"


@pytest.mark.parametrize("notebook_path", JNWB_NOTEBOOKS, ids=[p.name for p in JNWB_NOTEBOOKS])
def test_notebook_imports_jnwb(notebook_path: Path):
    nb = _load_notebook(notebook_path)
    source = _notebook_source(nb)
    assert "import jnwb" in source, f"{notebook_path.name} must import jnwb"


@pytest.mark.parametrize("notebook_path", JNWB_NOTEBOOKS, ids=[p.name for p in JNWB_NOTEBOOKS])
def test_notebook_mentions_required_apis(notebook_path: Path):
    nb = _load_notebook(notebook_path)
    source = _notebook_source(nb)
    required = CORE_JNWB_API_BY_NOTEBOOK[notebook_path.name]
    missing = [api for api in required if api not in source]
    assert not missing, f"{notebook_path.name} missing API references: {missing}"


def test_notebook_02_mentions_f005_visualization():
    path = REPO_ROOT / "notebooks" / "02_f005_from_artifacts.ipynb"
    source = _notebook_source(_load_notebook(path))
    assert "run_f005_figure" in source or "f005_unit_psth_categories" in source


def test_core_jnwb_api_covered_by_notebooks():
    coverage: dict[str, list[str]] = {api: [] for api in CORE_JNWB_API}
    for notebook_path in JNWB_NOTEBOOKS:
        source = _notebook_source(_load_notebook(notebook_path))
        for api in CORE_JNWB_API:
            if api in source:
                coverage[api].append(notebook_path.name)
    missing = [api for api, refs in coverage.items() if not refs]
    assert not missing, f"Core jnwb APIs not referenced in notebooks: {missing}"


def test_public_jnwb_all_subset_of_package():
    for name in CORE_JNWB_API:
        assert hasattr(jnwb, name), f"jnwb missing public API: {name}"
        assert name in jnwb.__all__
