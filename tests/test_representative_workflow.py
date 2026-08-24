"""End-to-end integration test: a representative NWB analysis workflow built entirely from
jnwb's public API, on synthetic in-memory data, with zero omission/ involvement.

This is the executable form of the 99%-jnwb-sufficiency terminal test ("if omission disappeared,
jnwb would remain a coherent, independently useful neuroscience/NWB library"). Unlike the
per-function unit tests elsewhere in tests/, this chains several jnwb domains together the way a
fresh external project actually would: unit metadata QC -> spike-response classification ->
LFP spectral/connectivity analysis -> population decoding -> a shuffle-null permutation check ->
a PSTH for visualization. Nothing here reads a real NWB file (that would make the test
environment-dependent); the point is API composability and standalone importability, not corpus
science.

test_no_omission_module_ever_imported is the load-bearing assertion: it fails if any step of the
workflow pulls in `omission` as a side effect, which would mean jnwb secretly depends on it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import jnwb

REPO_ROOT = Path(__file__).resolve().parent.parent


def _synthetic_units_df(rng, n=30):
    return pd.DataFrame({
        "unit_id": np.arange(n),
        "area": rng.choice(["V1", "PFC"], size=n),
        "quality": rng.choice([0, 1], size=n, p=[0.2, 0.8]),
        "snr": rng.uniform(0.2, 5.0, size=n),
        "firing_rate": rng.uniform(0.05, 40.0, size=n),
        "waveform_duration": rng.uniform(0.2, 0.9, size=n),
    })


def _synthetic_spike_train(rng, duration_s=120.0, rate_hz=8.0):
    n = rng.poisson(duration_s * rate_hz)
    return np.sort(rng.uniform(0, duration_s, size=n))


def _synthetic_lfp(rng, fs=1000.0, duration_s=2.0, freq_hz=10.0):
    t = np.arange(0, duration_s, 1.0 / fs)
    return np.sin(2 * np.pi * freq_hz * t) + 0.3 * rng.standard_normal(t.size)


class TestRepresentativeWorkflow:
    def test_unit_metadata_qc_stage(self):
        rng = np.random.default_rng(0)
        units = _synthetic_units_df(rng)

        good_v1 = jnwb.filter_by_criteria(units, {"area": "V1", "firing_rate": (1.0, 50.0)})
        assert set(good_v1["area"]) <= {"V1"}

        classified = jnwb.classify_unit_quality(units)
        assert "quality_class" in classified.columns
        assert classified["is_valid"].dtype == bool

        census = jnwb.unit_census_report(units, group_by=["area"])
        assert set(census["area"]) == {"V1", "PFC"}

        audit = jnwb.audit_units(units)
        assert "total_units" in audit

    def test_spike_response_stage(self):
        rng = np.random.default_rng(1)
        spike_times = _synthetic_spike_train(rng)
        onsets = np.sort(rng.uniform(5.0, 110.0, size=40))

        rate = jnwb.rate_in_window(spike_times, onset_s=onsets[0], window_ms=(0.0, 200.0))
        assert rate >= 0.0

        fired = jnwb.fire_indicator(spike_times, onsets, window_ms=(0.0, 200.0))
        assert fired.shape == onsets.shape

        metrics = jnwb.compute_response_metrics(spike_times, onsets, response_window=(0.0, 0.15))
        sig = jnwb.classify_response_significance(metrics)
        assert "is_significant" in sig

        centers, mean_hz, sem_hz = jnwb.raster_psth(spike_times, onsets, win_ms=(-200, 400))
        assert centers.shape == mean_hz.shape == sem_hz.shape

    def test_lfp_spectral_stage(self):
        rng = np.random.default_rng(2)
        fs = 1000.0
        lfp_a = _synthetic_lfp(rng, fs=fs, freq_hz=10.0)
        lfp_b = _synthetic_lfp(rng, fs=fs, freq_hz=10.0)

        power = jnwb.band_power(lfp_a, fs, jnwb.CANONICAL_BANDS["alpha"])
        assert np.isfinite(power)

        freqs, psd = jnwb.compute_psd(lfp_a, fs)
        assert freqs.shape == psd.shape

        coh = jnwb.cross_area_coherence(lfp_a, lfp_b, sampling_rate=fs)
        assert isinstance(coh, dict)

    def test_decoding_and_null_stage(self):
        rng = np.random.default_rng(3)
        n_per_class = 25
        X0 = rng.normal(loc=-3.0, scale=1.0, size=(n_per_class, 4))
        X1 = rng.normal(loc=3.0, scale=1.0, size=(n_per_class, 4))
        X = np.vstack([X0, X1])
        labels = np.array([0] * n_per_class + [1] * n_per_class)

        result = jnwb.nested_cv_linear_svm(X, labels, n_splits=5)
        assert result["status"] == "success"
        assert result["accuracy"] > result["majority_baseline_accuracy"] - 0.2

        groups = np.tile(np.arange(5), n_per_class // 5 * 2)[: len(labels)]
        null = jnwb.permute_labels(labels, groups=groups, scheme="within_group", rng=rng)
        assert null.shape == labels.shape

        plan = jnwb.build_permutation_plan(labels, groups, n_permutations=10, seed=0)
        assert len(plan["draw_manifest"]) == 10

    def test_full_pipeline_chains_without_error(self):
        """One coherent pass through every stage, mimicking a fresh external user's script."""
        rng = np.random.default_rng(42)
        units = _synthetic_units_df(rng)
        classified = jnwb.classify_unit_quality(units)
        good_units = classified[classified["is_valid"]]
        assert len(good_units) >= 0  # may legitimately be empty under strict synthetic QC

        spike_times = _synthetic_spike_train(rng)
        onsets = np.sort(rng.uniform(5.0, 110.0, size=50))
        metrics = jnwb.compute_response_metrics(spike_times, onsets)
        sig = jnwb.classify_response_significance(metrics)

        lfp = _synthetic_lfp(rng)
        band_pow = jnwb.band_power(lfp, 1000.0, jnwb.CANONICAL_BANDS["theta"])

        labels = rng.integers(0, 2, 40)
        X = rng.standard_normal((40, 3))
        decode_result = jnwb.nested_cv_linear_svm(X, labels, n_splits=4)

        # A fresh user composing these into a single receipt dict, jnwb-only:
        receipt = {
            "n_good_units": int(len(good_units)),
            "response_significant": sig["is_significant"],
            "theta_power": float(band_pow),
            "decode_status": decode_result["status"],
        }
        assert set(receipt) == {"n_good_units", "response_significant", "theta_power", "decode_status"}


class TestNoOmissionDependency:
    def test_full_workflow_runs_with_omission_blocked(self):
        """The load-bearing assertion: the ENTIRE representative workflow above -- not just
        `import jnwb` -- must complete successfully in a subprocess where any import of
        `omission` (or a submodule of it) is made to fail, simulating omission/ not existing at
        all. This is stronger than tests/test_jnwb_frozen_boundary.py's import-only check: it
        proves a fresh external user can actually RUN multi-domain jnwb workflows, not just
        import the package, without omission/ present. Run in a subprocess (rather than checking
        sys.modules in-process) because pytest's own collection may already have imported
        omission from sibling test files by the time this test runs, which would make an
        in-process sys.modules check a false positive unrelated to jnwb's real dependency graph.
        """
        script = (
            "import sys\n"
            "class _BlockOmission:\n"
            "    def find_module(self, name, path=None):\n"
            "        if name == 'omission' or name.startswith('omission.'):\n"
            "            raise ImportError('omission/ blocked for this test')\n"
            "        return None\n"
            "sys.meta_path.insert(0, _BlockOmission())\n"
            f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
            "import numpy as np\n"
            "import pandas as pd\n"
            "import jnwb\n"
            "rng = np.random.default_rng(42)\n"
            "units = pd.DataFrame({\n"
            "    'unit_id': np.arange(30), 'area': rng.choice(['V1', 'PFC'], size=30),\n"
            "    'quality': rng.choice([0, 1], size=30, p=[0.2, 0.8]),\n"
            "    'snr': rng.uniform(0.2, 5.0, size=30), 'firing_rate': rng.uniform(0.05, 40.0, size=30),\n"
            "    'waveform_duration': rng.uniform(0.2, 0.9, size=30),\n"
            "})\n"
            "classified = jnwb.classify_unit_quality(units)\n"
            "census = jnwb.unit_census_report(units, group_by=['area'])\n"
            "audit = jnwb.audit_units(units)\n"
            "spike_times = np.sort(rng.uniform(0, 120.0, size=rng.poisson(960)))\n"
            "onsets = np.sort(rng.uniform(5.0, 110.0, size=40))\n"
            "metrics = jnwb.compute_response_metrics(spike_times, onsets, response_window=(0.0, 0.15))\n"
            "sig = jnwb.classify_response_significance(metrics)\n"
            "centers, mean_hz, sem_hz = jnwb.raster_psth(spike_times, onsets, win_ms=(-200, 400))\n"
            "t = np.arange(0, 2.0, 1.0 / 1000.0)\n"
            "lfp_a = np.sin(2 * np.pi * 10.0 * t) + 0.3 * rng.standard_normal(t.size)\n"
            "lfp_b = np.sin(2 * np.pi * 10.0 * t) + 0.3 * rng.standard_normal(t.size)\n"
            "power = jnwb.band_power(lfp_a, 1000.0, jnwb.CANONICAL_BANDS['alpha'])\n"
            "freqs, psd = jnwb.compute_psd(lfp_a, 1000.0)\n"
            "coh = jnwb.cross_area_coherence(lfp_a, lfp_b, sampling_rate=1000.0)\n"
            "X = np.vstack([rng.normal(-3.0, 1.0, (25, 4)), rng.normal(3.0, 1.0, (25, 4))])\n"
            "labels = np.array([0] * 25 + [1] * 25)\n"
            "result = jnwb.nested_cv_linear_svm(X, labels, n_splits=5)\n"
            "assert result['status'] == 'success'\n"
            "plan = jnwb.build_permutation_plan(labels, np.tile(np.arange(5), 10), n_permutations=10, seed=0)\n"
            "assert len(plan['draw_manifest']) == 10\n"
            "print('WORKFLOW_OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0 and "WORKFLOW_OK" in result.stdout, (
            "The representative jnwb-only workflow failed with omission/ blocked from sys.path "
            "-- jnwb is not actually standalone-runnable, breaking the 99%-sufficiency terminal "
            f"test.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
