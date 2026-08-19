#!/usr/bin/env python3

# === QUARANTINED 2026-08-10 -- do not use as an empirical source ===
# Per artifacts/.lab/agent-harness-audit-20260810.json (Sol/Hamm Handout 2, P0 item 1):
# this script uses invalid (ungrouped/random) cross-validation for omission-identity-style
# decoding on a corpus with real repeated-cycle structure -- same-cycle trials can land in
# both train and test, inflating apparent accuracy. It is preserved as forensic evidence of
# what was tried and why it was superseded, per this project's Conservation doctrine
# (reduction is valid only if prior state remains recoverable) -- NOT deleted.
# tests/test_quarantine_enforcement.py fails if any live (non-historical) script imports from
# this module.
scientific_status = "invalid_for_inference"
superseded_by = None
reason = ['ungrouped_cv', 'no_current_valid_lfp_replacement']
# === END QUARANTINE HEADER ===

r"""
LFP 1D (per-channel scalar, low-frequency <100Hz power) versions of v4's two spike analyses --
closes items (1) and (2) of the storyline for LFP, same design as
scripts/decode_fig04_v4_area_ranking.py, just swapping spike counts for low-freq LFP power on
the same channels the area's units sit on (mapping verified in the v2 LFP control).

PART 1 -- real-stimulus positive control: AAAB vs BBBA, one decode per slot (p2/p3/p4, each its
own narrow ~531ms window, p4's A/B flipped to match the real parent-sequence content), 5-fold CV
+ 100-shuffle permutation null.

PART 2 -- omitted identity, pooled across all 3 slots (corrected mapping): chronological
half-split (both directions) + random half-split, X|R null-stratum check (fraction predicted B).

OUTPUT
    outputs/classification/lfp1d_stim_by_area.csv
    outputs/classification/lfp1d_omission_by_area.csv
"""
from __future__ import annotations

import pathlib
import sys
import time

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import omission as oa  # noqa: E402
from omission.jnwb_ext.omission_identity import OMISSION_IDENTITY_CONDITIONS  # noqa: E402
from jnwb import paths as _P

OUT_DIR = REPO_ROOT / "outputs" / "classification"
NWB_DIR = pathlib.Path(_P.nwb_dir())
TFR_DIR = pathlib.Path(_P.tfr_dir())
AREA_VEC_CSV = REPO_ROOT / "outputs" / "channel_area_vector" / "channel_area_vector.csv"
AREAS = ["FEF", "PFC", "TEO", "V4", "V3", "V2", "V1"]
RANDOM_STATE = 42
LOW_FREQ_HZ = (0.0, 100.0)

TFR_FREQS_HZ = np.arange(3, 201, 2)
TFR_T0_MS, TFR_BIN_MS, TFR_N_TIMES = -1000.0, 10.0, 500

STIM_SLOTS = {
    "p2": {"A": "AAAB", "B": "BBBA", "window_ms": (1031.0, 1562.0)},
    "p3": {"A": "AAAB", "B": "BBBA", "window_ms": (2062.0, 2593.0)},
    "p4": {"A": "BBBA", "B": "AAAB", "window_ms": (3093.0, 3624.0)},
}
OMISSION_WINS = {"p2": (1031.0, 1562.0), "p3": (2062.0, 2593.0), "p4": (3093.0, 3624.0)}


def _band_slice(lo_hz, hi_hz):
    m = np.where((TFR_FREQS_HZ >= lo_hz) & (TFR_FREQS_HZ < hi_hz))[0]
    return (m[0], m[-1] + 1) if len(m) else (0, 0)


def _time_slice(lo_ms, hi_ms):
    i0 = int(round((lo_ms - TFR_T0_MS) / TFR_BIN_MS))
    i1 = int(round((hi_ms - TFR_T0_MS) / TFR_BIN_MS))
    return max(0, i0), min(TFR_N_TIMES, i1)


def channel_map_for_area(session, unit_ids):
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


def lfp_feature(stem, area, cond_code, local_channels_by_probe, win_ms):
    """(n_trials, n_channels) mean low-frequency power, one scalar per channel."""
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
        block = np.asarray(arr[:, chans_ok, f0:f1, t0:t1], dtype=np.float64).mean(axis=(2, 3))
        mats.append(block)
    if not mats:
        return None
    n_trials = min(m.shape[0] for m in mats)
    return np.concatenate([m[:n_trials] for m in mats], axis=1)


def decode_stim_lfp(session, stem, area, local_channels_by_probe):
    rows = []
    for slot_key, cfg in STIM_SLOTS.items():
        Xa = lfp_feature(stem, area, cfg["A"], local_channels_by_probe, cfg["window_ms"])
        Xb = lfp_feature(stem, area, cfg["B"], local_channels_by_probe, cfg["window_ms"])
        if Xa is None or Xb is None or len(Xa) < 6 or len(Xb) < 6:
            rows.append({"session": stem, "area": area, "slot": slot_key, "status": "insufficient_data"})
            continue
        n_min = min(len(Xa), len(Xb))
        rng = np.random.default_rng(RANDOM_STATE)
        ia = rng.choice(len(Xa), n_min, replace=False)
        ib = rng.choice(len(Xb), n_min, replace=False)
        X = np.concatenate([Xa[ia], Xb[ib]], axis=0)
        X = np.nan_to_num(X, nan=np.nanmean(X) if np.isfinite(np.nanmean(X)) else 0.0)
        y = np.array([0] * n_min + [1] * n_min)

        cv = StratifiedKFold(n_splits=min(5, n_min), shuffle=True, random_state=RANDOM_STATE)
        accs = []
        for tr, te in cv.split(X, y):
            p = Pipeline([("sc", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0, random_state=RANDOM_STATE))])
            p.fit(X[tr], y[tr]); accs.append(p.score(X[te], y[te]))
        acc = float(np.mean(accs))

        rng2 = np.random.default_rng(RANDOM_STATE + 1)
        perm_accs = []
        for _ in range(100):
            y_perm = rng2.permutation(y)
            p_accs = []
            for tr, te in cv.split(X, y_perm):
                p = Pipeline([("sc", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0, random_state=RANDOM_STATE))])
                p.fit(X[tr], y_perm[tr]); p_accs.append(p.score(X[te], y_perm[te]))
            perm_accs.append(np.mean(p_accs))
        p_val = float(np.mean(np.array(perm_accs) >= acc))
        p_val = p_val if p_val > 0 else 1.0 / 101
        rows.append({"session": stem, "area": area, "slot": slot_key, "status": "success",
                    "n_channels": X.shape[1], "n_per_class": n_min, "accuracy": acc, "p_val": p_val})
    return rows


def decode_omission_lfp(session, stem, area, local_channels_by_probe):
    cfg2, cfg3, cfg4 = (OMISSION_IDENTITY_CONDITIONS["p2"], OMISSION_IDENTITY_CONDITIONS["p3"],
                        OMISSION_IDENTITY_CONDITIONS["p4"])

    def pooled(cls_key):
        Xs, ts = [], []
        for slot_key, cfg in (("p2", cfg2), ("p3", cfg3), ("p4", cfg4)):
            e = session.get_epochs(phase=2, condition=cfg[cls_key])
            if len(e) == 0:
                continue
            X = lfp_feature(stem, area, cfg[cls_key], local_channels_by_probe, OMISSION_WINS[slot_key])
            if X is None:
                continue
            n = min(len(e), len(X))
            Xs.append(X[:n]); ts.append(e["start_time"].values[:n])
        if not Xs:
            return np.zeros((0, 0)), np.array([])
        n_feat = min(x.shape[1] for x in Xs)
        return np.concatenate([x[:, :n_feat] for x in Xs], axis=0), np.concatenate(ts)

    Xa, ta = pooled("A"); Xb, tb = pooled("B"); Xr, tr_ = pooled("R")
    base = {"session": stem, "area": area, "n_A": len(Xa), "n_B": len(Xb), "n_R": len(Xr)}
    if len(Xa) < 6 or len(Xb) < 6:
        return {**base, "status": "insufficient_data"}
    n_feat = min(Xa.shape[1], Xb.shape[1]) if len(Xb) else Xa.shape[1]
    Xa, Xb = Xa[:, :n_feat], Xb[:, :n_feat]
    Xa = np.nan_to_num(Xa, nan=0.0); Xb = np.nan_to_num(Xb, nan=0.0)
    if len(Xr):
        Xr = np.nan_to_num(Xr[:, :n_feat], nan=0.0)
    X = np.concatenate([Xa, Xb], axis=0)
    y = np.array([0] * len(Xa) + [1] * len(Xb))
    t = np.concatenate([ta, tb])

    def fit_score(train_idx, test_idx):
        p = Pipeline([("sc", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0, random_state=RANDOM_STATE))])
        p.fit(X[train_idx], y[train_idx])
        return p, p.score(X[test_idx], y[test_idx])

    result = {**base, "status": "success"}
    order = np.argsort(t)
    mid = len(order) // 2
    fh, sh = order[:mid], order[mid:]
    if len(set(y[fh])) == 2 and len(set(y[sh])) == 2:
        p_fwd, acc_fwd = fit_score(fh, sh)
        p_bwd, acc_bwd = fit_score(sh, fh)
        result["acc_chrono_mean"] = float(np.mean([acc_fwd, acc_bwd]))
        if len(Xr):
            result["R_frac_pred_B_chrono_fwd"] = float(np.mean(p_fwd.predict(Xr) == 1))
            result["R_frac_pred_B_chrono_bwd"] = float(np.mean(p_bwd.predict(Xr) == 1))
    else:
        result["acc_chrono_mean"] = float("nan")

    cv = StratifiedKFold(n_splits=2, shuffle=True, random_state=RANDOM_STATE)
    accs, r_fracs = [], []
    for tr_idx, te_idx in cv.split(X, y):
        p, acc = fit_score(tr_idx, te_idx)
        accs.append(acc)
        if len(Xr):
            r_fracs.append(float(np.mean(p.predict(Xr) == 1)))
    result["acc_random_mean"] = float(np.mean(accs))
    if r_fracs:
        result["R_frac_pred_B_random_mean"] = float(np.mean(r_fracs))
    return result


def main(limit=None):
    t0 = time.time()
    nwb_files = sorted(NWB_DIR.glob("*.nwb"))
    if limit:
        nwb_files = nwb_files[:limit]
    print(f"Found {len(nwb_files)} NWB files.")

    stim_rows, om_rows = [], []
    for f_idx, nwb_path in enumerate(nwb_files, 1):
        stem = nwb_path.stem.replace("_rec", "")
        print(f"[{f_idx}/{len(nwb_files)}] {stem}")
        session = oa.read(nwb_path)
        for area in AREAS:
            unit_ids = session.get_units(area=area)["unit_id"].tolist()
            local_channels_by_probe = channel_map_for_area(session, unit_ids)
            if not local_channels_by_probe:
                continue
            stim_rows.extend(decode_stim_lfp(session, stem, area, local_channels_by_probe))
            om_rows.append(decode_omission_lfp(session, stem, area, local_channels_by_probe))

    df_stim = pd.DataFrame(stim_rows)
    df_stim.to_csv(OUT_DIR / "lfp1d_stim_by_area.csv", index=False)
    df_om = pd.DataFrame(om_rows)
    df_om.to_csv(OUT_DIR / "lfp1d_omission_by_area.csv", index=False)

    print(f"\nDone in {time.time()-t0:.1f}s.")
    ok_stim = df_stim[df_stim.status == "success"]
    if len(ok_stim):
        print("\n=== LFP STIM positive control, mean accuracy by area ===")
        print(ok_stim.groupby("area").accuracy.agg(["mean", "count"]).sort_values("mean", ascending=False).round(3))
    ok_om = df_om[df_om.status == "success"]
    if len(ok_om):
        print("\n=== LFP OMISSION pooled, mean accuracy by area ===")
        print(ok_om.groupby("area")[["acc_chrono_mean", "acc_random_mean"]].mean().sort_values("acc_chrono_mean", ascending=False).round(3))


if __name__ == "__main__":
    _limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=_limit)
