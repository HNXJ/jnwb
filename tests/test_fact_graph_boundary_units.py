"""Fact I3 past named units: quantity, rate, frame and base changes with no suffix.

Each case builds a small stand-in module under a scratch tree and runs the scan entry
point on it; the live case runs the same entry point on this tree. A name that spells
nothing is not read: a missing or non-literal default never reports.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

from scripts import build_fact_graph  # noqa: E402


def planted(tmp_path, body):
    pkg = tmp_path / "jnwb"
    pkg.mkdir(exist_ok=True)
    (pkg / "planted.py").write_text(body, encoding="utf-8")
    return build_fact_graph.boundary_unit_scan(tmp_path, ["jnwb/planted.py"])


def test_a_value_in_samples_reaching_a_parameter_in_seconds_is_reported(tmp_path):
    examined, found = planted(tmp_path,
        "def to_seconds(t_s):\n"
        "    return t_s\n"
        "\n"
        "def f(n_samples):\n"
        "    return to_seconds(n_samples)\n")
    assert examined == {"edges": 1, "excused": 0}, "the quantity edge is examined"
    assert found == [["jnwb/planted.py:5",
                       "n_samples (samples) reaches to_seconds(t_s) (time)"]]


def test_an_fs_of_one_rate_reaching_a_callee_of_another_is_reported(tmp_path):
    examined, found = planted(tmp_path,
        "def callee(fs=1000.0):\n"
        "    return fs\n"
        "\n"
        "def caller(fs=30000.0):\n"
        "    return callee(fs)\n")
    assert examined == {"edges": 1, "excused": 0}, "the rate edge is examined"
    assert found == [["jnwb/planted.py:5",
                       "fs (rate 30000.0) reaches callee(fs) (rate 1000.0)"]]


def test_a_zero_based_index_reaching_a_one_based_parameter_is_reported(tmp_path):
    examined, found = planted(tmp_path,
        "def callee(index_base=1):\n"
        "    return index_base\n"
        "\n"
        "def caller(index_base=0):\n"
        "    return callee(index_base)\n")
    assert examined == {"edges": 1, "excused": 0}, "the base edge is examined"
    assert found == [["jnwb/planted.py:5",
                       "index_base (base 0) reaches callee(index_base) (base 1)"]]


def test_a_frame_word_reaching_another_frame_by_position_is_reported(tmp_path):
    examined, found = planted(tmp_path,
        "def callee(coordinate_frame='samples'):\n"
        "    return coordinate_frame\n"
        "\n"
        "def caller(coordinate_frame='rows'):\n"
        "    return callee(coordinate_frame)\n")
    assert examined == {"edges": 1, "excused": 0}, "the frame edge is examined"
    assert found == [["jnwb/planted.py:5",
                       "coordinate_frame (frame 'rows') reaches "
                       "callee(coordinate_frame) (frame 'samples')"]]


def test_matching_rate_defaults_are_examined_and_not_a_finding(tmp_path):
    examined, found = planted(tmp_path,
        "def callee(fs=1000.0):\n"
        "    return fs\n"
        "\n"
        "def caller(fs=1000.0):\n"
        "    return callee(fs)\n")
    assert examined == {"edges": 1, "excused": 0}, "the agreeing edge is examined"
    assert found == []


def test_a_quantity_break_stated_at_the_site_is_excused_and_counted(tmp_path):
    examined, found = planted(tmp_path,
        "def to_seconds(t_s):\n"
        "    return t_s\n"
        "\n"
        "def f(n_samples):\n"
        "    return to_seconds(n_samples)  # INTENTIONAL BREAK: samples counted as seconds\n")
    assert examined == {"edges": 1, "excused": 1}
    assert found == []


def test_an_expression_between_the_names_is_the_conversion(tmp_path):
    examined, found = planted(tmp_path,
        "def to_seconds(t_s):\n"
        "    return t_s\n"
        "\n"
        "def f(n_samples):\n"
        "    return to_seconds(n_samples / 1000.0)\n")
    assert examined == {"edges": 0, "excused": 0}
    assert found == []


def test_a_missing_default_spells_nothing_and_is_not_examined(tmp_path):
    examined, found = planted(tmp_path,
        "def callee(fs):\n"
        "    return fs\n"
        "\n"
        "def caller(fs=30000.0):\n"
        "    return callee(fs)\n")
    assert examined == {"edges": 0, "excused": 0}
    assert found == []


def test_the_live_tree_reports_no_unsuffixed_boundary_finding():
    python = build_fact_graph._tracked_python(REPO_ROOT)
    examined, found = build_fact_graph.boundary_unit_scan(REPO_ROOT, python)
    assert examined["edges"] > 0, "the tree holds boundary edges to examine"
    assert found == [], found
