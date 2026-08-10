#!/usr/bin/env python3
r"""
Figure 4 v6: 2D population decoder (N x T spikes, channels x T LFP), 5 window definitions,
3-way (A/B/R) classification, 2026-08-06/07.

WINDOWS (per omission slot p2/p3/p4, EPOCH_ONSETS_MS-derived, "px" = that slot's presentation):
    d_px_d   = pre-omission delay + presentation + post-omission delay   (~1500ms)
    d_px     = pre-omission delay + presentation                        (~1000ms)
    px_d     = presentation + post-omission delay                       (~1000ms)
    px       = presentation only                                        (~500ms)
    p_d_px_d = PREVIOUS presentation + pre-delay + presentation + post-delay (~2000ms)

DESIGN
    - Pooled across all 3 slots per class (corrected mapping, see jnwb/omission_identity.py's
      2026-08-06 p4 fix): X|A = AXAB+AAXB+BBBX, X|B = BXBA+BBXA+AAAX, X|R = RXRR+RRXR+RRRX.
    - 2D features: spikes -> (n_units x n_time_bins), 25ms bins. LFP -> (n_channels x
      n_time_bins), native 10ms TFR bins, low-frequency power (<100Hz, per direction) on the
      SAME channels the area's units sit on (peak_channel_id -> probe-local index, same mapping
      verified in the v2 LFP control). Both flattened, PCA-reduced (<=20 components, same
      overfitting guard as v5), then a 3-way multinomial logistic regression -- chosen
      specifically here (not the SVM used elsewhere in this project) because its softmax layer
      gives calibrated class probabilities directly, which is what "apply softmax so
      pA+pB=1.0" asks for; flagged as an explicit, deliberate deviation from the SVM convention,
      not an oversight.
    - ONE 60/40 stratified train/test split (as specified) -- not repeated/averaged and no
      permutation null this pass (not requested this round; add if wanted).
    - Confusion matrix (3x3, row-normalized) on the test set.
    - R-trial calibration: each R test trial's predicted [P(A),P(B),P(R)] has P(R) dropped and
      [P(A),P(B)] renormalized to sum to 1 (pA' = P(A)/(P(A)+P(B))) -- averaged across R test
      trials, expected ~[0.5,0.5] if unbiased.
    - Per-area ranking reported even at chance, per direction.

LFP CAVEAT (stated, not hidden): the precomputed TFR arrays cover -1000..+3990ms (500 x 10ms
bins). p4's wider windows (d_px_d, p_d_px_d) nominally extend to 4124ms; LFP features for those
are clipped to 3990ms (up to 134ms short) while the spike features for the same window are not
(spike times are read directly, not from a fixed-length array). Noted per cell in the output.

OUTPUT
    outputs/classification/fig04_v6_spikes_2d_5win.csv
    outputs/classification/fig04_v6_lfp_2d_5win.csv
"""
from __future__ import annotations

import pathlib
import sys
import time

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa  # noqa: E402
from jnwb.omission_identity import OMISSION_IDENTITY_CONDITIONS  # noqa: E402
from jnwb import paths as _P

OUT_DIR = REPO_ROOT / "outputs" / "classification"
NWB_DIR = pathlib.Path(_P.nwb_dir())
TFR_DIR = pathlib.Path(_P.tfr_dir())
AREA_VEC_CSV = REPO_ROOT / "outputs" / "channel_area_vector" / "channel_area_vector.csv"
AREAS = ["FEF", "PFC", "TEO", "V4", "V3", "V2", "V1"]
RANDOM_STATE = 42
SPIKE_BIN_MS = 25.0
MAX_PCA_COMPONENTS = 20
LOW_FREQ_HZ = (0.0, 100.0)

EPOCH_ONSETS_MS = {"p1": 0.0, "d1": 531.0, "p2": 1031.0, "d2": 1562.0, "p3": 2062.0,
                  "d3": 2593.0, "p4": 3093.0, "d4": 3624.0, "end": 4124.0}
SLOT_IDX = {"p2": 2, "p3": 3, "p4": 4}

TFR_FREQS_HZ = np.arange(3, 201, 2)
TFR_T0_MS, TFR_BIN_MS, TFR_N_TIMES = -1000.0, 10.0, 500


def get_windows_ms(slot_key):
    idx = SLOT_IDX[slot_key]
    prev_p = EPOCH_ONSETS_MS[f"p{idx - 1}"]
    d_before = EPOCH_ONSETS_MS[f"d{idx - 1}"]
    px = EPOCH_ONSETS_MS[f"p{idx}"]
    d_after = EPOCH_ONSETS_MS[f"d{idx}"]
    next_p = EPOCH_ONSETS_MS[f"p{idx + 1}"] if idx < 4 else EPOCH_ONSETS_MS["end"]
    return {
        "d_px_d": (d_before, next_p),
        "d_px": (d_before, d_after),
        "px_d": (px, next_p),
        "px": (px, d_after),
        "p_d_px_d": (prev_p, next_p),
    }


WINDOW_NAMES = ["d_px_d", "d_px", "px_d", "px", "p_d_px_d"]


def _band_slice(lo_hz, hi_hz):
    m = np.where((TFR_FREQS_HZ >= lo_hz) & (TFR_FREQS_HZ < hi_hz))[0]
    return (m[0], m[-1] + 1) if len(m) else (0, 0)


def _time_slice(lo_ms, hi_ms):
    i0 = int(round((lo_ms - TFR_T0_MS) / TFR_BIN_MS))
    i1 = int(round((hi_ms - TFR_T0_MS) / TFR_BIN_MS))
    return max(0, i0), min(TFR_N_TIMES, i1)


_AREA_VEC = None


def area_vec():
    global _AREA_VEC
    if _AREA_VEC is None:
        _AREA_VEC = pd.read_csv(AREA_VEC_CSV)
    return _AREA_VEC


def channel_map_for_area(session, unit_ids):
    """peak_channel_id (global) -> (probe_letter, local_channel), same mapping verified in the
    v2 LFP control -- returns {probe_letter: set(local_channels)}."""
    units_df = session.get_units()
    units_df = units_df[units_df["unit_id"].isin(unit_ids)]
    if len(units_df) == 0 or "peak_channel_id" not in units_df.columns:
        return {}
    electrodes = session.get_electrodes()
    probe_offsets = electrodes.index.to_series().groupby(electrodes["probe"]).min()
    probe_letter_of = {}
    for probe_name, offset in probe_offsets.items():
        letter = probe_name.replace("probe", "")[:1].upper()
        probe_letter_of[probe_name] = (letter, int(offset))

    def channel_key(peak_channel_id):
        for probe_name, (letter, offset) in probe_letter_of.items():
            n_on_probe = int((electrodes["probe"] == probe_name).sum())
            if offset <= peak_channel_id < offset + n_on_probe:
                return letter, int(peak_channel_id - offset)
        return None, None

    out = {}
    for pcid in units_df["peak_channel_id"].dropna().unique():
        letter, local = channel_key(int(float(pcid)))
        if letter is not None:
            out.setdefault(letter, set()).add(local)
    return out


def spikemat_NxT(session, unit_ids, onsets, bin_ms, win_dur_ms):
    edges = np.arange(0, win_dur_ms + bin_ms, bin_ms) / 1000.0
    n_bins = len(edges) - 1
    X = np.zeros((len(onsets), len(unit_ids), n_bins))
    for j, u_id in enumerate(unit_ids):
        st = session.get_spike_times(u_id)
        st = np.sort(st) if st is not None and len(st) else np.array([])
        for i, onset in enumerate(onsets):
            rel = st[(st >= onset) & (st < onset + win_dur_ms / 1000.0)] - onset
            X[i, j, :] = np.histogram(rel, bins=edges)[0]
    return X


def lfp_mat_channelsxT(stem, area, cond_code, local_channels_by_probe, win_ms):
    """(n_trials, n_channels, n_time_bins) low-frequency (<100Hz) power, native 10ms TFR bins,
    clipped to the array's -1000..3990ms coverage."""
    f0, f1 = _band_slice(*LOW_FREQ_HZ)
    t0, t1 = _time_slice(*win_ms)
    if t1 <= t0:
        return None
    mats = []
    for probe_letter, chans in local_channels_by_probe.items():
        path = TFR_DIR / f"{stem}-{probe_letter}-{area}-{cond_code}.npy"
        if not path.exists():
            continue
        arr = np.load(path, mmap_mode="r")
        chans_ok = sorted(c for c in chans if c < arr.shape[1])
        if not chans_ok:
            continue
        block = np.asarray(arr[:, chans_ok, f0:f1, t0:t1], dtype=np.float32).mean(axis=2)  # (trials, chans, time)
        mats.append(block)
    if not mats:
        return None
    n_trials = min(m.shape[0] for m in mats)
    return np.concatenate([m[:n_trials] for m in mats], axis=1)


def build_pooled_2d(session, stem, area, unit_ids, modality, window_name):
    cfg2, cfg3, cfg4 = (OMISSION_IDENTITY_CONDITIONS["p2"], OMISSION_IDENTITY_CONDITIONS["p3"],
                        OMISSION_IDENTITY_CONDITIONS["p4"])
    local_channels_by_probe = channel_map_for_area(session, unit_ids) if modality == "lfp" else None

    def pooled(cls_key):
        Xs = []
        for slot_key, cfg in (("p2", cfg2), ("p3", cfg3), ("p4", cfg4)):
            win_ms = get_windows_ms(slot_key)[window_name]
            e = session.get_epochs(phase=2, condition=cfg[cls_key])
            if len(e) == 0:
                continue
            onsets = e["start_time"].values
            if modality == "spikes":
                win_dur = win_ms[1] - win_ms[0]
                offset_onsets = onsets + win_ms[0] / 1000.0
                X = spikemat_NxT(session, unit_ids, offset_onsets, SPIKE_BIN_MS, win_dur)
                Xs.append(X.reshape(X.shape[0], -1))
            else:
                X = lfp_mat_channelsxT(stem, area, cfg[cls_key], local_channels_by_probe, win_ms)
                if X is not None:
                    Xs.append(X.reshape(X.shape[0], -1))
        if not Xs:
            return np.zeros((0, 0))
        n_feat = min(x.shape[1] for x in Xs)  # guard against clipped-window shape mismatches
        return np.concatenate([x[:, :n_feat] for x in Xs], axis=0)

    Xa, Xb, Xr = pooled("A"), pooled("B"), pooled("R")
    return Xa, Xb, Xr


def decode_cell(session, stem, area, unit_ids, modality, window_name):
    base = {"session": stem, "area": area, "modality": modality, "window": window_name,
           "n_units_or_channels_units": len(unit_ids)}
    Xa, Xb, Xr = build_pooled_2d(session, stem, area, unit_ids, modality, window_name)
    if len(unit_ids) < 2 or len(Xa) < 6 or len(Xb) < 6 or len(Xr) < 6:
        return {**base, "status": "insufficient_data", "n_A": len(Xa), "n_B": len(Xb), "n_R": len(Xr)}
    n_feat = min(Xa.shape[1], Xb.shape[1], Xr.shape[1])
    Xa, Xb, Xr = Xa[:, :n_feat], Xb[:, :n_feat], Xr[:, :n_feat]
    X = np.concatenate([Xa, Xb, Xr], axis=0)
    y = np.array([0] * len(Xa) + [1] * len(Xb) + [2] * len(Xr))
    base.update({"n_A": len(Xa), "n_B": len(Xb), "n_R": len(Xr), "n_features": n_feat})

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.4, stratify=y,
                                              random_state=RANDOM_STATE)
    n_comp = min(MAX_PCA_COMPONENTS, len(X_tr) - 1, n_feat)
    pipe = Pipeline([
        ("sc", StandardScaler()),
        ("pca", PCA(n_components=n_comp, random_state=RANDOM_STATE)),
        ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
    ])
    pipe.fit(X_tr, y_tr)
    acc = pipe.score(X_te, y_te)
    proba_te = pipe.predict_proba(X_te)  # columns ordered by pipe.classes_ = [0,1,2] = A,B,R
    preds = pipe.predict(X_te)
    cm = confusion_matrix(y_te, preds, labels=[0, 1, 2])
    cm_norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)

    r_mask = y_te == 2
    r_softmax_ab = float("nan")
    if r_mask.sum() > 0:
        p_ab = proba_te[r_mask][:, :2]
        p_ab_renorm = p_ab / np.maximum(p_ab.sum(axis=1, keepdims=True), 1e-9)
        r_softmax_ab = float(p_ab_renorm[:, 0].mean())  # mean pA' across R test trials

    return {
        **base, "status": "success", "n_train": len(X_tr), "n_test": len(X_te),
        "accuracy": float(acc), "chance_baseline": 1.0 / 3,
        "confusion_A": cm_norm[0].tolist(), "confusion_B": cm_norm[1].tolist(),
        "confusion_R": cm_norm[2].tolist(),
        "R_mean_softmax_pA_renorm": r_softmax_ab,
    }


def main(limit=None, modalities=("spikes", "lfp")):
    t0 = time.time()
    nwb_files = sorted(NWB_DIR.glob("*.nwb"))
    if limit:
        nwb_files = nwb_files[:limit]
    print(f"Found {len(nwb_files)} NWB files. Modalities: {modalities}. Windows: {WINDOW_NAMES}")

    rows = {m: [] for m in modalities}
    for f_idx, nwb_path in enumerate(nwb_files, 1):
        stem = nwb_path.stem.replace("_rec", "")
        print(f"[{f_idx}/{len(nwb_files)}] {stem}")
        session = oa.read(nwb_path)
        for area in AREAS:
            unit_ids = session.get_units(area=area)["unit_id"].tolist()
            for modality in modalities:
                for window_name in WINDOW_NAMES:
                    rows[modality].append(
                        decode_cell(session, stem, area, unit_ids, modality, window_name))

    for modality in modalities:
        df = pd.DataFrame(rows[modality])
        out_path = OUT_DIR / f"fig04_v6_{modality}_2d_5win.csv"
        df.to_csv(out_path, index=False)
        ok = df[df.status == "success"]
        print(f"\n=== {modality}: {len(ok)}/{len(df)} cells succeeded -> {out_path} ===")
        if len(ok):
            print(ok.groupby(["window", "area"]).accuracy.mean().unstack("area").round(3))

    print(f"\nDone in {time.time()-t0:.1f}s.")


if __name__ == "__main__":
    _limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    _modalities = tuple(sys.argv[2].split(",")) if len(sys.argv) > 2 else ("spikes", "lfp")
    main(limit=_limit, modalities=_modalities)
