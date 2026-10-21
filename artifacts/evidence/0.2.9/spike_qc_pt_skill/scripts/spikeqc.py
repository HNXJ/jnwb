"""Single-unit QC and peak-to-trough (PT) classification for the GLO / fourGLO NWB corpus, on jnwb.

Python port of the MATLAB pipeline (steps A, C, D). jnwb reads the files, measures what it has
a measure for, plots, and records provenance; the corpus rules jnwb does not hold (deepest-trough
channel, the `frac` sharpness index, the ramp PT and the selection) live here.

    import sys; sys.path.insert(0, "<this skill>/scripts")
    import spikeqc as sq
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio
from scipy.signal import find_peaks

import jnwb

FS_HZ = 30000.0


# ---------------------------------------------------------------- step A: collect
def load_channel_map(chan_map_file) -> np.ndarray:
    """0-based depth order of the waveform_mean rows (e.g. DBCONE128.mat, variable channel_map).

    Use this, not jnwb.probe_geometry: in this corpus waveform_mean rows are in acquisition
    order while the electrodes table is already in depth order, so the electrode geometry does
    not say how to reorder the waveforms.
    """
    return np.asarray(sio.loadmat(str(chan_map_file))["channel_map"]).ravel().astype(int)


def collect_units(nwb_paths, chan_map_file, *, allow_missing=("session_description",)):
    """All units of all sessions as one table plus a waveform array.

    Returns (units, waveforms): `units` is one row per unit with every nwb.units column except
    the ragged ones, plus session_id, probe and local_peak_channel; `waveforms` is
    (n_units, n_channels, n_samples) in channel-map (depth) order at 30 kHz.
    `allow_missing` is jnwb's waiver for the fourGLO files, which lack session_description.
    """
    chmap = load_channel_map(chan_map_file)
    tables, waves = [], []
    for path in nwb_paths:
        path = Path(path)
        with jnwb.nwb_read_io(str(path), allow_missing=allow_missing) as io:
            nwb = io.read()
            u = nwb.units.to_dataframe()
            e = nwb.electrodes.to_dataframe()
        n_probe = e.groupby("probe").size()
        if (n_probe != chmap.size).any():
            raise ValueError(f"{path.name}: probes have {n_probe.to_dict()} channels; "
                             f"the channel map has {chmap.size}")
        wf = np.stack([np.asarray(w, dtype=float) for w in u["waveform_mean"]])
        waves.append(wf[:, chmap, :])
        pk = u["peak_channel_id"].to_numpy().astype(int)
        t = u.drop(columns=["spike_times", "waveform_mean", "spike_amplitudes"], errors="ignore").copy()
        t["spread"] = t["spread"] / 1e6                       # stored as m*1e6 -> um, as in step A
        t["session_id"] = path.stem
        t["probe"] = e["probe"].to_numpy()[pk]
        t["local_peak_channel"] = pk - np.searchsorted(e["probe"].to_numpy(), t["probe"].to_numpy())
        t["spike_times"] = list(u["spike_times"])
        tables.append(t.reset_index())
    return pd.concat(tables, ignore_index=True), np.concatenate(waves)


# ---------------------------------------------------------------- step C: peak waveforms, frac
def peak_waveforms(waveforms) -> dict:
    """Deepest-trough and largest-peak channel traces, polarity and the frac sharpness index.

    waveforms: (n_units, n_channels, n_samples). Channel order does not matter here.
    neg_pk / pos_pk: (n_units, n_samples); cell_dir 1 = negative-going, 2 = positive-going;
    frac = max range of the first difference / max range of the trace, over the two traces.
    """
    w = np.asarray(waveforms, dtype=float)
    n = np.arange(w.shape[0])
    neg_chan = w.min(axis=2).argmin(axis=1)
    pos_chan = w.max(axis=2).argmax(axis=1)
    neg_pk, pos_pk = w[n, neg_chan], w[n, pos_chan]
    cell_dir = np.where((-neg_pk).max(axis=1) >= pos_pk.max(axis=1), 1, 2)
    rng = lambda x: x.max(axis=1) - x.min(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):   # all-zero units give NaN, as in MATLAB
        frac = (np.maximum(rng(np.diff(neg_pk, axis=1)), rng(np.diff(pos_pk, axis=1)))
                / np.maximum(rng(neg_pk), rng(pos_pk)))
    return dict(neg_pk=neg_pk, pos_pk=pos_pk, neg_chan=neg_chan, pos_chan=pos_chan,
                cell_dir=cell_dir, frac=frac)


# ---------------------------------------------------------------- step C: selection
def select_units(units, W, good_manual, bad_by_eye=(), *, min_frac=0.25, min_presence=0.8,
                 neg_only=True):
    """Final selection: manual Yes AND frac > min_frac AND nwb quality AND presence_ratio >
    min_presence AND negative-going, minus bad_by_eye (0-based unit rows).

    Returns (good_idx, report): sorted 0-based rows, and the per-criterion attrition table.
    `quality` is read as nonzero = good, as MATLAB's logical() reads it.
    """
    frac = np.asarray(W["frac"])
    crit = [("manual Yes", np.asarray(good_manual).ravel().astype(bool)),
            (f"frac > {min_frac:.2f}", (frac > min_frac) & ~np.isnan(frac)),
            ("nwb quality != 0", np.asarray(units["quality"]).ravel() != 0),
            (f"presence_ratio > {min_presence:.2f}",
             np.asarray(units["presence_ratio"]).ravel() > min_presence)]
    if neg_only:
        crit.append(("negative-going (cell_dir == 1)", np.asarray(W["cell_dir"]) == 1))
    keep = np.ones(frac.size, bool)
    rows = []
    for name, ok in crit:
        rows.append((name, int((~ok).sum()), int((keep & ~ok).sum())))
        keep &= ok
        rows[-1] += (int(keep.sum()),)
    bad = np.asarray(bad_by_eye, dtype=int)
    good_idx = np.setdiff1d(np.flatnonzero(keep), bad)
    rows.append(("not in bad_by_eye list", int(np.isin(np.arange(frac.size), bad).sum()),
                 int(keep.sum() - good_idx.size), int(good_idx.size)))
    report = pd.DataFrame(rows, columns=["criterion", "fail_alone", "removed_cumulative", "remaining"])
    return good_idx, report


# ---------------------------------------------------------------- step D: PT
def compute_pt(neg_pk, *, fs=FS_HZ, pre=15, post=55, legacy=False):
    """Ramp-corrected trough-to-peak duration in ms of each deepest-trough trace.

    Range-normalise; cut pre..post samples around the trough; subtract a ramp 0 -> 1 over the
    post+1 samples from the trough on; the first local maximum (left edge of a plateau, as
    MATLAB findpeaks) is the repolarization peak. NaN when the window leaves the trace or there
    is no local maximum. legacy=True adds the original script's 2-sample offset to reproduce
    saved PT values. Returns (pt_ms, aligned, peak_idx), peak_idx into `aligned`.
    """
    x = np.asarray(neg_pk, dtype=float)
    x = x / (x.max(axis=1, keepdims=True) - x.min(axis=1, keepdims=True))
    trough = x.argmin(axis=1)
    ramp = np.linspace(0.0, 1.0, post + 1)
    n = x.shape[0]
    aligned = np.full((n, pre + post + 1), np.nan)
    peak_idx = np.full(n, np.nan)
    pt = np.full(n, np.nan)
    for c in range(n):
        a, b = trough[c] - pre, trough[c] + post
        if a < 0 or b >= x.shape[1]:
            continue
        aligned[c] = x[c, a:b + 1]
        k, props = find_peaks(aligned[c, pre:] - ramp, plateau_size=1)
        if k.size == 0:
            continue
        k0 = int(props["left_edges"][0])
        peak_idx[c] = pre + k0
        pt[c] = (k0 + 2 if legacy else k0) * 1000.0 / fs
    return pt, aligned, peak_idx


def classify_pt(pt_ms, threshold_ms, *, legacy_scale=True):
    """'narrow' (putative inhibitory) / 'broad' (putative excitatory) / 'undefined' (NaN PT).

    threshold_ms is on the legacy scale by default (the paper's 0.34); narrow = PT < threshold.
    Pass legacy-scale PT with legacy_scale=True, corrected PT with legacy_scale=False (the
    threshold is then shifted by the 2-sample offset so both give the same split). The
    comparison is in whole samples, so a threshold on the sample grid (0.4 ms = 12 samples)
    splits both scales the same way.
    """
    pt = np.asarray(pt_ms, dtype=float)
    n_legacy = np.round(pt * FS_HZ / 1000.0) + (0 if legacy_scale else 2)
    out = np.where(n_legacy < threshold_ms * FS_HZ / 1000.0 - 1e-6, "narrow", "broad").astype(object)
    out[np.isnan(pt)] = "undefined"
    return out


# ---------------------------------------------------------------- jnwb measures and record
def jnwb_features(waveforms, fs=FS_HZ) -> pd.DataFrame:
    """jnwb.waveform_features per unit: largest-amplitude channel, amplitude, Siegle et al.
    (2021) trough-to-peak, peak-trough ratio, polarity. Its duration is a different definition
    from compute_pt (no normalisation or ramp, plain first maximum after the trough); report
    which one a number is."""
    return pd.DataFrame([jnwb.waveform_features(w, fs) for w in np.asarray(waveforms)])


def record(statistics, parameters, source_id, operation):
    """A jnwb.Result carrying what ran, with which parameters, on what."""
    q = jnwb.Question(hypothesis="units pass the stated curation criteria", signals=["waveform_mean"],
                      contrast="none", inference_unit="unit")
    return jnwb.Result(
        question=q, statistics=statistics,
        provenance=jnwb.Provenance(software_version=jnwb.__version__, backend="numpy",
                                   parameters=parameters),
        lineage=jnwb.Lineage(source_type="nwb_units", source_id=source_id, operation=operation))
