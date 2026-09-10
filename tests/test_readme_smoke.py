"""Executable closure probes for the root README quickstart blocks."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"


def test_readme_quickstart_blocks_execute():
    rng = np.random.default_rng(42)
    spikes = np.sort(rng.uniform(0.0, 10.0, 300))
    events = np.array([1.0, 3.0, 5.0, 7.0])

    time_bins, rate_hz, _ = jnwb.raster_psth(
        spikes, events, win_ms=(-100.0, 400.0), bin_ms=10.0,
    )
    smooth_hz = jnwb.causal_exp_smooth(rate_hz, bin_ms=10.0, tau_ms=25.0)
    fit = jnwb.fit_exponential_onset(time_bins, smooth_hz, t0_bounds=(0.0, 250.0))
    assert "t0" in fit and "bound_status" in fit

    fs = 1000.0
    lfp = rng.normal(size=1000)
    tfr = jnwb.complex_tfr(lfp, fs=fs, freqs=np.linspace(10.0, 60.0, 10))
    beta = jnwb.band_power(
        lfp, fs=fs, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False,
    )
    assert tfr.shape[-1] == 1000
    assert beta >= 0.0


def test_readme_capability_table_symbols_exist():
    text = README.read_text(encoding="utf-8")
    table_section = text.split("## Capabilities", 1)[1].split("## Installation", 1)[0]
    symbols = re.findall(r"`([a-zA-Z_][a-zA-Z0-9_]*)`", table_section)
    for symbol in symbols:
        assert hasattr(jnwb, symbol), f"README capability table references missing jnwb.{symbol}"


def test_readme_does_not_hardcode_public_symbol_count():
    text = README.read_text(encoding="utf-8")
    assert not re.search(r"\b\d{2,4}\s+public\s+symbols\b", text, re.I)


def test_readme_python_version_matches_policy():
    text = README.read_text(encoding="utf-8")
    assert "3.12" in text
    assert "3.14" in text
