"""vFLIP2's bin-width dependence, pinned to the analytic term of its omega.

The port computes omega = log(ps_dist * band_dist * |G| * ch_span * f_span), with
f_span = deep.size * sup.size * binsize**2 (jnwb/laminar/_vflip2.py, the omega line of the
best-window search).

Scale the frequency axis by r and keep the PSD columns. When the bands select the same columns,
with their edges scaled by r, deep.size and sup.size do not change. ps_dist, band_dist, |G| and
ch_span depend only on column values, row indices and those columns, so they do not change
either. Then

    omega(r) - omega(1) = log(f_span(r) / f_span(1))
                        = 2 log r + log(n_low(r) / n_low(1)) + log(n_high(r) / n_high(1)),

where n = (top edge - bottom edge) / binsize + 1 for each band, read from the returned edges.
The test asserts the same columns, so the count terms are zero here, and it asserts that
instead of assuming it.

The scale is 1.005. The power example's bands are (5, 45) Hz and (46, 149) Hz. Scales from 1 up
to 150/149 keep the high band's columns; scales below 1 let its top edge pass 149 Hz and change
the selection (observed for 0.99 and 0.95 when this test was written).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from jnwb.laminar import vflip2

DOC = json.loads((Path(__file__).resolve().parent / "fixtures"
                  / "vflip2_matlab_reference.json").read_text(encoding="utf-8"))
CASE = next(c for c in DOC["cases"] if c["name"] == "power_example")
OMEGA_CUT = DOC["omega_cut"]
SPACING_UM = CASE["intdist"] * 1000.0
SCALE = 1.005


def _psd():
    return np.array([[np.nan if v is None else v for v in row] for row in CASE["psd"]],
                    dtype=float)


def _freqs(scale):
    n = len(CASE["psd"][0])
    return scale * CASE["freqbinsize"] * np.arange(1, n + 1, dtype=float)


def _bins(edges, binsize):
    """Columns in a contiguous band from its first to its last frequency."""
    return round((edges[1] - edges[0]) / binsize) + 1


def test_fixture_is_accepted_at_its_own_bin_width():
    result = vflip2(_psd(), _freqs(1.0), contact_spacing=SPACING_UM)
    assert result.accepted and result.omega > OMEGA_CUT, "the power example must be accepted"
    np.testing.assert_allclose(result.omega, CASE["matlab"]["omega"], rtol=1e-9)


def test_bin_width_shift_is_the_analytic_term():
    base = vflip2(_psd(), _freqs(1.0), contact_spacing=SPACING_UM)
    wide = vflip2(_psd(), _freqs(SCALE), contact_spacing=SPACING_UM)
    # Precondition: the same window, peaks, crossover and orientation; the bands are the same
    # columns, with edges SCALE times the base edges.
    assert base.accepted and wide.accepted, "both runs must be accepted"
    for name in ("orientation", "proximal_channel", "distal_channel", "low_peak_channel",
                 "high_peak_channel", "crossover_channel"):
        assert getattr(wide, name) == getattr(base, name), name
    np.testing.assert_allclose(wide.low_band_hz, SCALE * np.array(base.low_band_hz),
                               rtol=1e-12, atol=0)
    np.testing.assert_allclose(wide.high_band_hz, SCALE * np.array(base.high_band_hz),
                               rtol=1e-12, atol=0)
    n_low, n_high = _bins(base.low_band_hz, 1.0), _bins(base.high_band_hz, 1.0)
    n_low_w, n_high_w = _bins(wide.low_band_hz, SCALE), _bins(wide.high_band_hz, SCALE)
    assert (n_low_w, n_high_w) == (n_low, n_high), "the band column counts must be unchanged"
    expected = 2.0 * np.log(SCALE) + np.log(n_low_w / n_low) + np.log(n_high_w / n_high)
    assert abs(expected) > 1e-3, "the scale must move omega"
    # omega is near 13, so its rounding is about 2e-15; 1e-12 absolute is far below the shift.
    np.testing.assert_allclose(wide.omega - base.omega, expected, rtol=0, atol=1e-12)


def test_the_evidence_table_matches_the_script_on_the_power_example():
    """Every Dryad row of the committed evidence file is what scripts/vflip2_sensitivity.py
    computes now, so the file cannot go stale while vflip2 changes."""
    import sys

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.append(str(root))  # needed: the installed-wheel run clears pythonpath
    from scripts import vflip2_sensitivity as sens

    psd, freqs, spacing, _ = sens.load_power_example()
    computed = sens.probe_all(psd, freqs, spacing)
    rows = sens.EVIDENCE.read_text(encoding="utf-8").split("## Dryad power example")[1]
    rows = rows.split("\n## ")[0]
    for variant in sens.VARIANTS:
        group, value = sens.label(variant)
        expected = f"| {group} | {value} | {sens.fmt(computed[variant]['omega'])} |"
        assert expected in rows, expected
    assert len(sens.VARIANTS) >= 16, "every variant of the evidence file must be checked"
