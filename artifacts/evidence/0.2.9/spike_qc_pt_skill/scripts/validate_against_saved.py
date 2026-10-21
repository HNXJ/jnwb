"""Regression check: spikeqc.py must reproduce a dataset's saved MATLAB outputs exactly.

python validate_against_saved.py --processed <dir> --nwb-dir <dir> --chan-map <DBCONE128.mat> --bad-by-eye <file>

<dir> holds AllUnits_metrics.mat, a good_cells_manual*.mat, final_good_cells_idx.mat and
GoodUnits_metrics.mat; --bad-by-eye is a text file of the 1-based by-eye rejections, whitespace
or comma separated. Needs jnwb importable.
"""
import argparse
import sys
from pathlib import Path

import h5py
import numpy as np
import scipy.io as sio

sys.path.insert(0, str(Path(__file__).parent))
import spikeqc as sq

ap = argparse.ArgumentParser()
ap.add_argument("--processed", type=Path, required=True)
ap.add_argument("--nwb-dir", type=Path, required=True)
ap.add_argument("--chan-map", type=Path, required=True)
ap.add_argument("--bad-by-eye", type=Path, required=True)
ap.add_argument("--manual", default="good_cells_manual*.mat")
args = ap.parse_args()
D = args.processed
bad_1b = np.array(args.bad_by_eye.read_text().replace(",", " ").split(), dtype=int)

f = h5py.File(D / "AllUnits_metrics.mat", "r")
A = f["AllUnits"]
wf = np.transpose(A["waveformMean"][()], (2, 0, 1))          # (units, channels, samples)
units = {k: A[k][()].ravel() for k in ("quality", "presence_ratio")}
good_manual = sio.loadmat(sorted(D.glob(args.manual))[-1])["good_manual"].ravel()
saved_idx = sio.loadmat(D / "final_good_cells_idx.mat")["good_cells_final"].ravel() - 1
saved_pt = sio.loadmat(D / "GoodUnits_metrics.mat", variable_names=["PT"])["PT"].ravel()

W = sq.peak_waveforms(wf)
good, report = sq.select_units(units, W, good_manual, bad_1b - 1)
print(report.to_string(index=False))
print(f"SELECTION MATCH: {np.array_equal(good, saved_idx)}  ({good.size} vs saved {saved_idx.size})")

pt_leg, _, _ = sq.compute_pt(W["neg_pk"][saved_idx], legacy=True)
pt_cor, _, _ = sq.compute_pt(W["neg_pk"][saved_idx])
print(f"PT LEGACY MATCH: max abs diff = {np.nanmax(np.abs(pt_leg - saved_pt)):.2e}, NaNs = {np.isnan(pt_leg).sum()}")
print(f"PT median: corrected {np.nanmedian(pt_cor):.3f} ms, legacy {np.nanmedian(pt_leg):.3f} ms")
for thr in (0.34, 0.4):
    a = sq.classify_pt(pt_leg, thr)
    b = sq.classify_pt(pt_cor, thr, legacy_scale=False)
    print(f"legacy threshold {thr}: narrow {np.sum(a == 'narrow')} / broad {np.sum(a == 'broad')}; "
          f"corrected-scale split identical: {np.array_equal(a, b)}")

jf = sq.jnwb_features(wf[saved_idx])
print(f"jnwb.waveform_features trough_to_peak_ms (Siegle definition) median {jf.trough_to_peak_ms.median():.3f} ms; "
      f"equals the ramp PT for {np.mean(np.isclose(jf.trough_to_peak_ms, pt_cor)):.0%} of units")

# step A on the first session: NWB through jnwb must give the saved waveforms and metrics
sess = np.array(["".join(map(chr, f[r][()].ravel())) for r in A["session"][0]])
name = sess[0]
t, w1 = sq.collect_units([args.nwb_dir / f"{name}.nwb"], args.chan_map)
rows = np.flatnonzero(sess == name)
ok_w = np.allclose(w1, wf[rows])
ok_m = all(np.allclose(t[k].to_numpy(float), A[k][()].ravel()[rows], equal_nan=True)
           for k in ("presence_ratio", "quality", "snr", "spread", "firing_rate"))
print(f"COLLECT MATCH ({name}, {rows.size} units): waveforms {ok_w}, metrics {ok_m}")
