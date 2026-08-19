"""
Population sliding-window decoder for STIMULUS IDENTITY (A vs B) -- signed, time-resolved.

Unlike decode_omission_onset_sliding_window.py (present-vs-omitted, location/identity-agnostic),
this decodes WHICH identity (A or B) at each time bin, as a signed index rather than a balanced
accuracy: +1 = population activity leans toward label "A", -1 = leans toward "B", 0 = chance
(indistinguishable from the permutation null). Concretely, per bin and per cell:

    curve_A(t) = mean over out-of-fold TRUE-label-A test trials of sign(decision_score(t))
    curve_B(t) = mean over out-of-fold TRUE-label-B test trials of sign(decision_score(t))

curve_A should rise toward +1 once A is reliably decodable; curve_B should fall toward -1 once B
is reliably decodable; both hover near an empirical (permutation) chance level -- not exactly 0,
since finite-sample sign-imbalance biases it -- until then.

Three analyses, all sessions x all areas x all units, reusing omission.jnwb_ext.structured_identity's generic
per-session trial ontology (NOT omission.jnwb_ext.structured_identity_m2a's frozen 5-session Milestone 2A
design, which stays untouched and out of scope here):

  1. ab_positive_control -- presented identity (A vs B) at p1 (AAAB/BBBA trials, always a real
     stimulus, never omitted). Answers plain "A vs B" decodability over time.
  2. expected_pooled -- expected (omitted) identity X at the omission slot (p2/p3/p4, eligible
     A/B-family correct trials), pooled over preceding identity. Answers "X vs baseline" over
     time, i.e. is the omitted stimulus's identity represented in population activity at all.
  3. reversal_generalization -- train on p2+p3 (where preceding==expected), test on p4 (where
     preceding==reverse(expected)), scored against expected identity. Naive within-slot
     preceding-identity conditioning (precA vs precB at a fixed slot_key) is degenerate --
     confirmed on-corpus: expected identity is deterministically recoverable from preceding
     identity within a fixed position (Milestone 1 finding, docs/handout_3_..._reversal_design.md
     Sec 1), so every within-position preceding=X subset is single-class and undecodable. p4 is
     the only place preceding and expected genuinely diverge, so this train-p2p3/test-p4
     generalization decode is the only non-degenerate way to answer "X|A vs X|B" -- it is the
     time-resolved extension of the signed-off Milestone 2A reversal contrast, replicated
     per-session (not restricted to the frozen 5-session design) via the same
     `cross_position_cycle` rule (omission.jnwb_ext.omission_identity.detect_trial_cycles on each session's own
     combined p2/p3/p4 eligible timestamps).

CV grouping uses each session's own `cycle` field (omission.jnwb_ext.omission_identity.detect_trial_cycles via
build_canonical_trial_table) -- a generic per-session chronological grouping, not the Milestone
2A reversal design's frozen cross-position fold geometry. Regularization, permutation-null
construction (grouped, within_group, exchangeability-matched), and primal-form ridge solve reuse
the exact machinery validated in decode_omission_onset_sliding_window.py, including the
OPENBLAS_NUM_THREADS=1 fix for this machine's OpenBLAS thread-pool pathology.

Output: one .npz per successful (session, area, analysis) cell (bin_centers_ms, obs_A, obs_B,
null_A, null_B, n_folds, n_class_a, n_class_b) under OUT_DIR, plus an incrementally-written
manifest CSV. aggregate_identity_clusters.py combines cells within an area into group-level
signed traces with a cluster-based permutation test (restricted to bins >= 0 for the
omission-locked analyses, since decodability of an omission's identity cannot be causally prior
to that slot's own onset -- see the FEF -12.5ms false-positive fix in
aggregate_omission_onset_clusters.py, 2026-08-13) and a bootstrap CI on onset latency.
"""
from __future__ import annotations

import sys
import os
import time
import traceback
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import omission as oa
from jnwb import paths as _P
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS
from jnwb.permutation import permute_labels
from omission.jnwb_ext.omission_identity import detect_trial_cycles
from omission.jnwb_ext.structured_identity import build_canonical_trial_table, MAIN_ANALYSIS, POSITIVE_CONTROL
from omission.jnwb_ext.structured_identity_m2a import (
    build_outer_folds, _select_c, _has_both_classes, C_GRID,
)

NWB_DIR = _P.nwb_dir()
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
OUT_DIR = REPO_ROOT / "outputs/classification/identity_sliding_window"
MANIFEST_CSV = OUT_DIR / "cell_manifest.csv"

WIN_MS = (-100.0, 600.0)
BIN_MS = 25.0
MIN_UNITS = 3
MIN_GROUPS_WITH_BOTH_CLASSES = 3
N_PERMUTATIONS = 500
SEED = 4300  # distinct namespace from decode_omission_onset_sliding_window's SEED=42

ANALYSES = ("ab_positive_control", "expected_pooled", "reversal_generalization")


def _edges():
    edges = np.arange(WIN_MS[0], WIN_MS[1] + BIN_MS, BIN_MS)
    ctr = (edges[:-1] + edges[1:]) / 2.0
    return edges, ctr


def load_session(prefix: str):
    return oa.read(str(_P.resolve_nwb_path(prefix)))


def build_instance_tables(sess) -> dict[str, pd.DataFrame]:
    """Returns {analysis_name: DataFrame} for the three non-degenerate analyses.

    ab_positive_control / expected_pooled: [trial_id, onset_s, label, group] -- label: 1=A, 0=B;
    group: session-local `cycle` (CV grouping unit).

    reversal_generalization: same columns plus `is_test` (True for p4 rows). NAIVE within-slot
    preceding-identity conditioning (precA vs precB at a fixed slot_key) is degenerate -- expected
    identity is deterministically recoverable from preceding identity within a fixed position (the
    Milestone 1 design finding, docs/handout_3_..._reversal_design.md Sec 1), confirmed on-corpus:
    every within-position preceding=X subset is single-class. The only place preceding and expected
    genuinely diverge is p4 (preceding_previous != expected there), so "X|A vs X|B" is only
    answerable as a train-on-p2+p3/test-on-p4 GENERALIZATION decode, scored against expected
    identity at p4 -- the time-resolved extension of the signed-off Milestone 2A reversal contrast,
    replicated here per-session via the same `cross_position_cycle` rule
    (omission.jnwb_ext.omission_identity.detect_trial_cycles on each session's own combined p2/p3/p4 eligible
    timestamps) rather than the frozen 5-session design/eligibility artifacts, so it generalizes to
    the full corpus. build_outer_folds's train_mask/test_mask does the p2+p3-vs-p4 split; C-selection
    and inner CV are otherwise identical to the grouped analyses.
    """
    table = build_canonical_trial_table(sess, slot_keys=("p2", "p3", "p4"))
    out: dict[str, pd.DataFrame] = {}
    if table.empty:
        return out

    pc = table[(table["analysis"] == POSITIVE_CONTROL) & table["eligible"]].copy()
    if not pc.empty:
        pc["label"] = (pc["presented_identity"] == "A").astype(int)
        pc["onset_s"] = pc["start_time"].astype(float) + EPOCH_ONSETS_MS["p1"] / 1000.0
        pc["group"] = pc["cycle"].astype(int)
        out["ab_positive_control"] = pc[["trial_id", "onset_s", "label", "group"]].reset_index(drop=True)

    main = table[(table["analysis"] == MAIN_ANALYSIS) & table["eligible"]].copy()
    if not main.empty:
        main["label"] = (main["expected_identity"] == "A").astype(int)
        slot_num = main["slot_key"].astype(str).str.replace("p", "", regex=False).astype(int)
        main["onset_s"] = main["start_time"].astype(float) + slot_num.map(
            lambda s: EPOCH_ONSETS_MS[f"p{s}"]
        ) / 1000.0
        main["group"] = main["cycle"].astype(int)
        out["expected_pooled"] = main[["trial_id", "onset_s", "label", "group"]].reset_index(drop=True)

        rev = main.drop(columns=["group"]).sort_values("start_time").reset_index(drop=True)
        rev["group"] = detect_trial_cycles(rev[["start_time"]])
        rev["is_test"] = rev["slot_key"].eq("p4")
        out["reversal_generalization"] = rev[
            ["trial_id", "onset_s", "label", "group", "is_test"]
        ].reset_index(drop=True)
    return out


def build_raster_from_onsets(sess, area: str, onsets_s: np.ndarray, bin_ms: float, win_ms: tuple):
    units = sess.get_units(area=area)
    row_indices = list(units.index)
    if len(row_indices) < MIN_UNITS:
        return None, row_indices
    edges, ctr = _edges()
    n_bins = len(ctr)
    n = len(onsets_s)
    X = np.zeros((n, len(row_indices), n_bins), dtype=np.float64)
    lo_s, hi_s = win_ms[0] / 1000.0, win_ms[1] / 1000.0
    edges_s = edges / 1000.0
    for col, row_index in enumerate(row_indices):
        spikes = sess.get_spike_times(row_index)
        if spikes is None or len(spikes) == 0:
            continue
        spikes = np.sort(np.asarray(spikes, dtype=float))
        for r, onset in enumerate(onsets_s):
            X[r, col], _ = np.histogram(
                spikes[(spikes >= onset + lo_s) & (spikes < onset + hi_s)] - onset, bins=edges_s
            )
    X = X / (bin_ms / 1000.0)
    return X, row_indices


def decode_cell_signed(
    X: np.ndarray, labels: np.ndarray, groups: np.ndarray, seed: int,
    train_mask: np.ndarray | None = None, test_mask: np.ndarray | None = None,
):
    """Returns (obs_A, obs_B, null_A[N_PERM,n_bins], null_B[N_PERM,n_bins], n_folds) or None.

    Same fold/C-freezing/permutation-vectorization/primal-ridge conventions as
    decode_omission_onset_sliding_window.decode_cell; the only change is the per-bin statistic:
    instead of balanced accuracy, the signed prediction (+1/-1) is averaged separately within
    true-label-A and true-label-B test trials. Null curves use the SAME bookkeeping convention as
    the omission-onset script's null (group membership defined by that permutation draw's OWN
    label assignment, not the true one) so the null is a legitimate null of "if this bin carried
    no A/B information, what would this signed average look like."

    train_mask/test_mask (both None by default, meaning the ordinary symmetric grouped fold):
    forwarded to build_outer_folds for the reversal_generalization analysis, where train
    (p2+p3 rows) and test (p4 rows) are disjoint row subsets of the same combined instance array,
    not an arbitrary partition of one homogeneous set.
    """
    n, n_units, n_bins = X.shape
    folds = build_outer_folds(groups, labels, train_mask=train_mask, test_mask=test_mask, min_train_groups=2)
    if len(folds) < 2:
        return None

    X_mean = X.mean(axis=2)
    selected_C = {}
    for fs in folds:
        try:
            C, _, n_inner = _select_c(
                X_mean, labels, groups, fs.train_idx, fs.inner_groups, seed=seed + fs.fold * 1000, c_grid=C_GRID
            )
        except ValueError:
            return None
        if n_inner == 0:
            return None
        selected_C[fs.fold] = C

    rng = np.random.default_rng(seed + 777)
    perm_labels = np.stack(
        [permute_labels(labels, groups=groups, scheme="within_group", rng=rng) for _ in range(N_PERMUTATIONS)],
        axis=1,
    )  # (n, N_PERMUTATIONS)
    mask1_p = perm_labels == 1
    mask0_p = perm_labels == 0

    obs_a = np.full(n_bins, np.nan)
    obs_b = np.full(n_bins, np.nan)
    null_a = np.full((N_PERMUTATIONS, n_bins), np.nan)
    null_b = np.full((N_PERMUTATIONS, n_bins), np.nan)

    for b in range(n_bins):
        Xb = X[:, :, b]
        real_sign = np.full(n, np.nan)
        perm_sign = np.full((n, N_PERMUTATIONS), np.nan)
        for fs in folds:
            train_idx, test_idx = fs.train_idx, fs.test_idx
            X_train = Xb[train_idx]
            mean = X_train.mean(axis=0)
            scale = X_train.std(axis=0)
            scale[scale == 0.0] = 1.0
            Xtr = (X_train - mean) / scale
            Xte = (Xb[test_idx] - mean) / scale

            train_base = labels[train_idx]
            counts = np.bincount(train_base, minlength=2).astype(float)
            weights = np.sqrt(len(train_base) / (2.0 * counts[train_base]))
            weighted_train = Xtr * weights[:, None]

            A = weighted_train.T @ weighted_train
            A.flat[:: len(A) + 1] += 1.0 / float(selected_C[fs.fold])

            y_real = 2.0 * labels[train_idx] - 1.0
            y_perm = 2.0 * perm_labels[train_idx][:, :] - 1.0
            rhs_y = np.concatenate([y_real[:, None], y_perm], axis=1) * weights[:, None]
            rhs = weighted_train.T @ rhs_y
            coeffs = np.linalg.solve(A, rhs)
            scores = Xte @ coeffs  # (n_test, 1+N_PERM)
            sgn = np.sign(scores)
            sgn[sgn == 0.0] = 1.0
            real_sign[test_idx] = sgn[:, 0]
            perm_sign[test_idx] = sgn[:, 1:]

        cov = ~np.isnan(real_sign)
        m1, m0 = labels == 1, labels == 0
        if (cov & m1).any():
            obs_a[b] = np.nanmean(real_sign[cov & m1])
        if (cov & m0).any():
            obs_b[b] = np.nanmean(real_sign[cov & m0])

        covp = ~np.isnan(perm_sign[:, 0])
        sel1 = mask1_p & covp[:, None]
        sel0 = mask0_p & covp[:, None]
        cnt1 = sel1.sum(axis=0)
        cnt0 = sel0.sum(axis=0)
        sum1 = np.where(sel1, perm_sign, 0.0).sum(axis=0)
        sum0 = np.where(sel0, perm_sign, 0.0).sum(axis=0)
        null_a[:, b] = np.divide(sum1, cnt1, out=np.full(N_PERMUTATIONS, np.nan), where=cnt1 > 0)
        null_b[:, b] = np.divide(sum0, cnt0, out=np.full(N_PERMUTATIONS, np.nan), where=cnt0 > 0)

    return obs_a, obs_b, null_a, null_b, len(folds)


def main():
    import argparse
    global WIN_MS, OUT_DIR, MANIFEST_CSV
    parser = argparse.ArgumentParser()
    parser.add_argument("--win-lo", type=float, default=WIN_MS[0])
    parser.add_argument("--win-hi", type=float, default=WIN_MS[1])
    parser.add_argument("--out-dir", type=str, default=None)
    args = parser.parse_args()
    WIN_MS = (args.win_lo, args.win_hi)
    if args.out_dir:
        OUT_DIR = Path(args.out_dir)
        MANIFEST_CSV = OUT_DIR / "cell_manifest.csv"
    print(f"WIN_MS={WIN_MS} OUT_DIR={OUT_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    readiness = pd.read_csv(READINESS_CSV)
    ready = readiness[readiness["nwb_ok"] == True].copy()
    _, ctr = _edges()

    manifest_rows = []
    if MANIFEST_CSV.exists():
        manifest_rows = pd.read_csv(MANIFEST_CSV).to_dict("records")
    done_cells = {(r["session"], r["area"], r["analysis"]) for r in manifest_rows}

    t_start = time.time()
    for _, row in ready.iterrows():
        prefix = row["session_prefix"]
        try:
            sess = load_session(prefix)
        except Exception as e:
            print(f"[{prefix}] load failed: {e}")
            continue
        tables = build_instance_tables(sess)
        if not tables:
            print(f"[{prefix}] no eligible instances for any analysis")
            continue
        areas = sorted(sess.get_units()["area"].dropna().unique().tolist())
        subject = prefix.split("sub-")[1].split("_ses-")[0] if "sub-" in prefix else prefix

        for analysis, inst in tables.items():
            labels = inst["label"].to_numpy()
            groups = inst["group"].to_numpy()
            is_reversal = analysis == "reversal_generalization"
            if is_reversal:
                test_mask = inst["is_test"].to_numpy()
                train_mask = ~test_mask
                n_groups_ok = min(
                    len(np.unique(groups[train_mask])), len(np.unique(groups[test_mask]))
                )
            else:
                train_mask = test_mask = None
                n_groups_ok = sum(
                    _has_both_classes(labels, np.flatnonzero(groups == g)) for g in np.unique(groups)
                )
            if n_groups_ok < MIN_GROUPS_WITH_BOTH_CLASSES:
                continue
            onsets_s = inst["onset_s"].to_numpy()
            for area in areas:
                key = (prefix, area, analysis)
                if key in done_cells:
                    continue
                try:
                    X, row_indices = build_raster_from_onsets(sess, area, onsets_s, BIN_MS, WIN_MS)
                    if X is None:
                        continue
                    result = decode_cell_signed(
                        X, labels, groups, seed=SEED, train_mask=train_mask, test_mask=test_mask
                    )
                    if result is None:
                        continue
                    obs_a, obs_b, null_a, null_b, n_folds = result
                except Exception:
                    print(f"[{prefix}/{area}/{analysis}] FAILED:\n{traceback.format_exc()}")
                    continue

                npz_path = OUT_DIR / f"{prefix}__{area}__{analysis}.npz"
                np.savez(
                    npz_path, obs_a=obs_a, obs_b=obs_b, null_a=null_a, null_b=null_b, bin_centers_ms=ctr
                )
                manifest_rows.append({
                    "session": prefix, "subject": subject, "area": area, "analysis": analysis,
                    "n_units": len(row_indices), "n_instances": len(inst),
                    "n_class_a": int(labels.sum()), "n_class_b": int((labels == 0).sum()),
                    "n_folds": n_folds, "npz": str(npz_path),
                })
                pd.DataFrame(manifest_rows).to_csv(MANIFEST_CSV, index=False)
                print(
                    f"[{prefix}/{area}/{analysis}] units={len(row_indices)} n={len(inst)} "
                    f"folds={n_folds} peakA={np.nanmax(obs_a):.2f} peakB={np.nanmin(obs_b):.2f} "
                    f"elapsed={time.time()-t_start:.0f}s"
                )

    print("DONE. cells:", len(manifest_rows))


if __name__ == "__main__":
    main()
