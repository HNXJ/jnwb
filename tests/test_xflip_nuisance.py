"""xFLIP's null under nuisance structure: the operating point and the length-4 generator are the
receipt's, the interval is the library's exact Clopper-Pearson, the planted average-reference cell
is referenced to its channel average, and a smoke run on two seeds puts every count inside its
interval."""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import jnwb  # noqa: E402
from scripts import calibrate_xflip as receipt  # noqa: E402
from scripts import xflip_nuisance as nuisance  # noqa: E402

RAW = ROOT / "artifacts" / "benchmarks" / "calibration" / "xflip_calibration_0.2.5_raw.json"


def test_the_operating_point_is_the_receipts():
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    assert nuisance.N_SURROGATES == raw["n_surrogates"]
    assert nuisance.N_SAMPLES == raw["n_samples"]
    assert nuisance.MIN_BLOCK_SIZE == raw["min_block_size"]
    assert nuisance.ALPHA == raw["alpha"]


def test_length_four_draws_the_receipts_smooth_gradient_cell():
    for seed in (0, 7):
        mine = nuisance.toeplitz_null(seed, 4.0)
        theirs, _ = receipt._smooth_spatial_gradient(seed)
        assert mine.shape == (16, nuisance.N_SAMPLES)
        assert np.array_equal(mine, theirs), f"seed {seed}: length 4 must draw the receipt's cell"


def test_clopper_pearson_with_no_successes_has_its_exact_upper_bound():
    low, high = jnwb.clopper_pearson(0, 30, alpha=0.05)
    assert low == 0.0
    assert abs(high - (1.0 - 0.025 ** (1.0 / 30))) < 1e-9


def test_unit_power_scales_a_component_to_unit_mean_power():
    x = nuisance.toeplitz_null(5, 4.0)
    assert abs(float(np.mean(np.var(nuisance._unit_power(x), axis=1))) - 1.0) < 1e-12


def test_the_average_reference_planted_cell_is_referenced_to_its_channel_average():
    data = nuisance.planted_average_reference(3)
    assert data.shape == (16, nuisance.N_SAMPLES)
    assert np.allclose(data.mean(axis=0), 0.0, atol=1e-12)


def test_smoke_path_on_one_null_cell_counts_sit_inside_their_intervals():
    started = time.perf_counter()
    rows = nuisance.run_cell(lambda seed: nuisance.toeplitz_null(seed, 4.0), n_seeds=2,
                             n_surrogates=nuisance.N_SURROGATES)
    elapsed = time.perf_counter() - started
    assert len(rows) == 2, "the cell must run both seeds"
    assert all(np.isfinite(row[key]["p_omnibus"]) for row in rows for key in nuisance.BLOCK_COUNTS)
    for key in nuisance.BLOCK_COUNTS:
        summary = nuisance.null_summary(rows, key)
        for entry in summary.values():
            assert entry["n"] == 2
            low, high = entry["ci"]
            assert low <= entry["k"] / entry["n"] <= high
    assert elapsed < 20, f"the smoke path took {elapsed:.1f} s"
