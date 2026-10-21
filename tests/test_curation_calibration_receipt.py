"""The curation calibration receipt must describe the estimator that ships.

``scripts/calibrate_curation.py`` writes the receipt and a SHA-256 over the code that
``curate_and_label`` reaches, by the rule of ``scripts/calibrate_xflip.py``. Changing that code
without rerunning the script fails here; a docstring or comment edit does not.

``JNWB_CURATION_RECEIPT_DIR`` points these tests at another receipt written by the same script.
By default they read ``artifacts/benchmarks/calibration``.
"""

import importlib.util
import inspect
import json
import os
import pathlib
import statistics
import types

import pytest

import jnwb
from jnwb.laminar_curation import curate_and_label

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "calibrate_curation.py"
RECEIPT_DIR = pathlib.Path(
    os.environ.get("JNWB_CURATION_RECEIPT_DIR") or ROOT / "artifacts" / "benchmarks" / "calibration"
)
STEM = "curation_calibration_0.2.13"
RAW = RECEIPT_DIR / f"{STEM}_raw.json"
REPORT = RECEIPT_DIR / f"{STEM}.md"
ANCHOR_LINE = "    anchor = c_v if np.isfinite(c_v) else c_m"


def _refuse_constant(token):
    raise ValueError(f"{token} is not JSON; the record must be strict")


def strict_loads(text):
    """``json.loads`` that refuses NaN, Infinity and -Infinity tokens."""
    return json.loads(text, parse_constant=_refuse_constant)


def _raw():
    return strict_loads(RAW.read_text(encoding="utf-8"))


def _generator():
    spec = importlib.util.spec_from_file_location("calibrate_curation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_receipt_and_generator_exist():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert RAW.is_file() and REPORT.is_file(), f"no receipt in {RECEIPT_DIR}; run the script"


def test_the_raw_record_is_strict_json_and_names_its_release():
    raw = _raw()
    assert raw["release"] == "0.2.13"
    assert raw["declared_version"] == jnwb.__version__, (
        "the receipt was generated under another declared version; rerun the script"
    )
    assert raw["trials"], "the record holds no trial"
    assert raw["flagged"] == [name for name in raw["params"] if raw["summary"][name]["flagged"]]


def test_receipt_was_generated_from_the_current_estimator():
    assert _raw()["estimator_sha256"] == _generator().estimator_sha256(), (
        "the code curate_and_label reaches changed since the receipt was generated; "
        "rerun `python scripts/calibrate_curation.py`"
    )


def test_the_receipt_lists_the_functions_its_hash_covers():
    names = [name for name, _ in _generator().estimator_sources()]
    assert {"curate_and_label", "fuse_laminar_anchors", "_distance_to_anchor"} <= set(names)
    assert _raw()["estimator_functions"] == names


def _with_prose_edited(source):
    """``source`` with text added inside every docstring and a comment on every def line."""
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    lines = source.splitlines(keepends=True)

    def char_col(lineno, byte_col):
        return len(lines[lineno - 1].encode("utf-8")[:byte_col].decode("utf-8"))

    edits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            col = char_col(node.lineno, node.col_offset)
            text = lines[node.lineno - 1]
            quote = col
            while text[quote] not in "'\"":
                quote += 1
            width = 3 if text[quote:quote + 3] in ('"""', "'''") else 1
            edits.append((node.lineno, quote + width, "Edited. "))
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            line = lines[node.lineno - 1]
            edits.append((node.lineno, len(line.rstrip("\r\n")), "  # edited"))
    for lineno, col, text in sorted(edits, reverse=True):
        line = lines[lineno - 1]
        lines[lineno - 1] = line[:col] + text + line[col:]
    return "".join(lines)


def test_a_docstring_or_comment_edit_leaves_the_receipt_current(monkeypatch):
    generator = _generator()
    before = generator.estimator_sha256()
    real = inspect.getsource
    home = inspect.getmodule(curate_and_label)
    assert "Edited. " in _with_prose_edited(real(home))  # the edit is not vacuous

    monkeypatch.setattr(inspect, "getsource", lambda obj: _with_prose_edited(real(obj)))
    assert generator.estimator_sha256() == before, (
        "editing only docstrings and comments changed the receipt hash"
    )


def test_a_code_edit_changes_the_receipt(monkeypatch):
    generator = _generator()
    before = generator.estimator_sha256()
    real = inspect.getsource
    assert ANCHOR_LINE in real(inspect.getmodule(curate_and_label))  # the edit is not vacuous

    def mutated(obj):
        source = real(obj)
        assert source.count(ANCHOR_LINE) <= 1
        return source.replace(ANCHOR_LINE, "    anchor = c_m if np.isfinite(c_m) else c_v")

    monkeypatch.setattr(inspect, "getsource", mutated)
    assert generator.estimator_sha256() != before


def test_the_probes_come_from_the_laminar_motif_generator():
    raw = _raw()
    assert raw["fixed"]["generator"] == "jnwb.testing.synth_laminar_motif"
    # the planted SNR is the recoverable-alternative SNR of scripts/calibrate_vflip.py (ALT_SNR)
    assert raw["fixed"]["snr_planted"] == 20.0, "the planted SNR is not 20"
    assert raw["fixed"]["snr_null"] == 0.0
    method = REPORT.read_text(encoding="utf-8").split("## Method")[1].split("## Held inputs")[0]
    assert "`jnwb.testing.synth_laminar_motif`" in method, "the Method section does not name the generator"
    assert "`snr=20`" in method, "the Method section does not state the planted SNR"
    assert "`ALT_SNR`" in method and "vflip_calibration_0.2.4.md" in method, (
        "the Method section does not cite vFLIP's calibrated error at the planted SNR"
    )


def test_each_planted_trial_states_its_truth_in_the_anchor_frame():
    raw = _raw()
    measured = [t for t in raw["trials"] if t["planted"] and t["refused"] is None]
    assert measured, "no planted trial was measured, so the truth frame is untested"
    low, high = raw["fixed"]["z0_range"]
    for t in measured:
        assert t["truth_um"] == t["crossover_depth_um"], "the truth is not the generator receipt's depth"
        assert t["crossover_depth_um"] == raw["fixed"]["pitch_um"] * t["crossover_contact"]
        assert t["crossover_contact"] == t["z0"]
        assert low <= t["z0"] <= high
        near = t["anchor_um"] is not None and (
            abs(t["anchor_um"] - t["truth_um"]) <= raw["recovery_tolerance_um"])
        assert t["recovered"] == near


def test_the_null_probes_share_the_planted_draws():
    trials = _raw()["trials"]
    planted = {(t["param"], t["value"], t["seed"]): t["z0"] for t in trials if t["planted"]}
    null = {(t["param"], t["value"], t["seed"]): t["z0"] for t in trials if not t["planted"]}
    assert planted, "no planted trial, so the pairing is untested"
    assert planted.keys() == null.keys()
    assert all(planted[key] == null[key] for key in planted)


def test_the_receipt_defaults_are_the_live_defaults():
    raw = _raw()
    parameters = inspect.signature(curate_and_label).parameters
    assert raw["params"], "the receipt sweeps no parameter"
    for name in raw["params"]:
        assert raw["defaults"][name] == parameters[name].default


def test_intervals_are_exact_bracket_the_rate_and_close_at_the_ends():
    mod = _generator()
    for k in (0, 7, 24):
        low, high = mod.interval(k, 24)
        assert low <= k / 24 <= high
    assert mod.interval(0, 24)[0] == pytest.approx(0.0, abs=1e-12)
    assert mod.interval(24, 24)[1] == pytest.approx(1.0, abs=1e-12)


def test_an_int_default_rounds_ties_to_even_and_is_held_at_least_one():
    mod = _generator()
    assert 6 * 0.75 == 4.5 and round(4.5) == 4  # precondition: a tie, rounded to the even integer
    assert (0.75, 4) in mod.sweep_points("bad_zone_contacts", 6)
    assert (0.5, 2) in mod.sweep_points("min_ok_windows", 3)  # 1.5 rounds to 2
    assert round(1 * 0.5) == 0  # precondition: the unclamped value is 0
    assert all(value >= 1 for _, value in mod.sweep_points("n_windows", 1))


def test_a_fraction_is_clipped_and_a_repeated_value_keeps_its_first_factor():
    mod = _generator()
    assert 0.75 * 1.5 > 1.0  # precondition: the factor pushes the fraction past 1
    points = mod.sweep_points("consistency_a", 0.75)
    assert [value for _, value in points].count(1.0) == 1
    assert (1.5, 1.0) in points
    assert (0.5, 2) in mod.sweep_points("max_interpolate_run", 3)
    assert (0.75, 2) not in mod.sweep_points("max_interpolate_run", 3)


def test_a_default_outside_the_stable_range_is_flagged():
    mod = _generator()
    default_ci, best_ci = mod.interval(0, 24), mod.interval(24, 24)
    assert not mod._overlap(default_ci, best_ci)  # precondition: the recovery intervals are disjoint
    rows = [
        {"value": 4, "factor": 1.0, "is_default": True, "refusals": [], "k_recovered": 0,
         "recovery_ci": default_ci, "acceptance_ci": mod.interval(0, 24)},
        {"value": 8, "factor": 2.0, "is_default": False, "refusals": [], "k_recovered": 24,
         "recovery_ci": best_ci, "acceptance_ci": mod.interval(0, 24)},
    ]
    result = mod.stable_range(rows)
    assert result["flagged"] is True and result["stable_values"] == [8]
    swapped = [dict(rows[0], k_recovered=24, recovery_ci=best_ci),
               dict(rows[1], k_recovered=0, recovery_ci=default_ci)]
    assert mod.stable_range(swapped)["flagged"] is False


def test_the_report_names_the_release_the_hash_and_every_parameter():
    raw = _raw()
    report = REPORT.read_text(encoding="utf-8")
    assert "Qualifies release 0.2.13" in report
    assert raw["estimator_sha256"][:16] in report
    assert raw["params"], "the receipt sweeps no parameter"
    for name in raw["params"]:
        assert f"### `{name}`" in report


def test_the_recovery_column_counts_grades_a_to_d_only(monkeypatch):
    mod = _generator()
    contact, truth, _ = mod._probe(0, True)
    assert truth == mod.PITCH_UM * contact  # precondition: the truth is one pitch per contact
    for grade, expected in (("F", False), ("D", True)):
        fake = types.SimpleNamespace(anchor_um=truth, anchor_source="motif", grade=grade)
        monkeypatch.setattr(mod, "curate_and_label", lambda *args, _fake=fake, **kwargs: _fake)
        res = mod._run_one((None, None, 0, True))
        assert res["recovered"] is True, "precondition: the anchor lies at the truth"
        assert res["recovered_ad"] is expected, f"grade {grade} at the truth, second column"


def test_the_offset_distribution_counts_and_quantiles():
    mod = _generator()
    trials = [
        {"planted": True, "refused": None, "anchor_um": 1000.0, "truth_um": 1000.0, "grade": "A"},
        {"planted": True, "refused": None, "anchor_um": 1150.0, "truth_um": 1000.0, "grade": "C"},
        {"planted": True, "refused": None, "anchor_um": 900.0, "truth_um": 1000.0, "grade": "B"},
        {"planted": True, "refused": None, "anchor_um": 1050.0, "truth_um": 1000.0, "grade": "F"},
        {"planted": True, "refused": None, "anchor_um": None, "truth_um": 1000.0, "grade": "F"},
        {"planted": True, "refused": "refused in the test", "anchor_um": None,
         "truth_um": None, "grade": None},
        {"planted": False, "refused": None, "anchor_um": 500.0, "truth_um": None, "grade": "F"},
    ]
    d = mod.offset_distribution(trials)
    assert d["n_planted"] == 5 and d["n_anchor"] == 4, "precondition: four anchors, five probes"
    assert d["n_recovered"] == 3  # offsets 0, -100 and 50 um lie within 100 um
    assert d["n_recovered_ad"] == 2  # the 50 um anchor is grade F
    assert (d["n_positive"], d["n_negative"], d["n_grade_f"]) == (2, 1, 1)
    assert d["mean_um"] == pytest.approx(25.0)
    assert d["median_um"] == pytest.approx(25.0)
    assert d["min_um"] == pytest.approx(-100.0)
    assert d["max_um"] == pytest.approx(150.0)


def test_the_receipt_recounts_its_second_column_and_offsets_from_its_trials():
    raw = _raw()
    probes = [t for t in raw["trials"]
              if t["param"] is None and t["planted"] and t["refused"] is None]
    anchored = [t for t in probes if t["anchor_um"] is not None]
    assert anchored, "no planted default probe gave an anchor, so the offsets are untested"
    within = [t for t in anchored
              if abs(t["anchor_um"] - t["truth_um"]) <= raw["recovery_tolerance_um"]]
    offsets = [t["anchor_um"] - t["truth_um"] for t in anchored]
    block = raw["offsets"]
    assert block["n_planted"] == len(probes)
    assert block["n_anchor"] == len(anchored)
    assert block["n_recovered"] == len(within)
    assert block["n_recovered_ad"] == sum(1 for t in within if t["grade"] in raw["recovery_grades"])
    assert block["mean_um"] == pytest.approx(sum(offsets) / len(offsets))
    assert block["median_um"] == pytest.approx(statistics.median(offsets))
    name = raw["params"][0]
    default = next(row for row in raw["summary"][name]["rows"] if row["is_default"])
    assert default["k_recovered_ad"] == sum(1 for t in probes if t["recovered_ad"])


def test_the_report_states_the_second_column_and_the_offsets():
    report = REPORT.read_text(encoding="utf-8")
    assert "grades A to D" in report, "the report does not state the second recovery column"
    assert "## Offsets of planted anchors at defaults" in report


def test_smoke_prints_and_writes_no_receipt(monkeypatch, tmp_path):
    mod = _generator()
    monkeypatch.setattr(mod, "run", lambda n_seeds, n_jobs, params: {
        "trials": [], "estimator_sha256": "0" * 64, "flagged": []})
    monkeypatch.setattr(mod, "render", lambda data: "")
    assert mod.main(["--smoke", "--n-jobs", "1", "--out", str(tmp_path)]) == 0
    assert list(tmp_path.iterdir()) == [], "the smoke run wrote files"
