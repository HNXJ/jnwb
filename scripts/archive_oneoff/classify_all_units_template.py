"""
Figure 1 support: multi-session template-correlation classification.

Extends scripts/template_correlation_selection.py to all NWB sessions where
suite_tfr_ready=True (15/17 sessions as of 2026-07-13). For each session, scans
all stable-plus units and assigns a template_label (S+/S-/O+/Null) using the
same 9-epoch binary template method and permutation-test significance gate.

Template rules:
  S+   : [0,1,0,1,0,1,0,1,0] over RRRR epochs (fires WITH stimuli)
  S-   : [1,0,1,0,1,0,1,0,1] over RRRR epochs (fires BETWEEN stimuli)
  O+   : one-hot at omitted slot; requires p<0.05 in at least 1 omission condition
         AND r_mean > best significant S template r (or 0.3 minimum)
  Null : no template reaches p < ALPHA

Priority: O+ > S+/S- (by |r|) > Null.
Only sessions with tfr_r_family_ok=True are eligible for O+ classification.

CRITICAL (footgun #9): get_spike_times() indexes by DataFrame row position (units_df.index),
NOT the unit_id column. This script always passes row_pos to get_spike_times().

Output:
  outputs/classification/grand_template_classifications.csv

Usage:
    python scripts/classify_all_units_template.py
    python scripts/classify_all_units_template.py --max-sessions 3  # smoke test
    python scripts/classify_all_units_template.py --session sub-C31o_ses-230823
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa
from jnwb.sequence_layout import EPOCH_ONSETS_MS

READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
OUT_CSV = REPO_ROOT / "outputs/classification/grand_template_classifications.csv"

OMIT_CONDITIONS = ["RXRR", "RRXR", "RRRX"]
MIN_TRIALS = 40
MIN_MEAN_RATE_HZ = 1.0
N_PERM = 5000
RNG_SEED = 42
ALPHA = 0.05

EPOCH_NAMES = list(EPOCH_ONSETS_MS.keys())  # [fx, p1, d1, p2, d2, p3, d3, p4, d4]
EPOCH_ENDS_MS = list(EPOCH_ONSETS_MS.values())[1:] + [4124.0]

S_PLUS_TEMPLATE = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0], dtype=float)
S_MINUS_TEMPLATE = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1], dtype=float)
OMIT_SLOT_TO_EPOCH = {"RXRR": "p2", "RRXR": "p3", "RRRX": "p4"}


def omission_template(cond: str) -> np.ndarray:
    t = np.zeros(len(EPOCH_NAMES))
    t[EPOCH_NAMES.index(OMIT_SLOT_TO_EPOCH[cond])] = 1.0
    return t


def per_epoch_rate_hz(spike_times: np.ndarray, onsets: np.ndarray) -> np.ndarray:
    """Duration-normalized mean firing rate (Hz) per epoch, averaged across trials."""
    rates = np.zeros((len(onsets), len(EPOCH_NAMES)))
    for ti, onset in enumerate(onsets):
        for ei, (name, t0) in enumerate(EPOCH_ONSETS_MS.items()):
            t1 = EPOCH_ENDS_MS[ei]
            lo = onset + t0 / 1000.0
            hi = onset + t1 / 1000.0
            n_spk = int(np.sum((spike_times >= lo) & (spike_times < hi)))
            rates[ti, ei] = n_spk / ((t1 - t0) / 1000.0)
    return rates.mean(axis=0)


def perm_corr(vec: np.ndarray, template: np.ndarray, n_perm: int,
              rng: np.random.Generator) -> tuple[float, float]:
    """Permutation-test Pearson correlation. Returns (r_obs, p_value)."""
    if vec.std() == 0 or template.std() == 0:
        return 0.0, 1.0
    r_obs = float(np.corrcoef(vec, template)[0, 1])
    n_ge = 0
    for _ in range(n_perm):
        r_perm = float(np.corrcoef(rng.permutation(vec), template)[0, 1])
        if abs(r_perm) >= abs(r_obs):
            n_ge += 1
    return r_obs, (n_ge + 1) / (n_perm + 1)


def assign_label(r_splus: float, p_splus: float,
                 r_sminus: float, p_sminus: float,
                 r_oplus_mean: float, oplus_any_sig: bool) -> str:
    """Priority: O+ (any omit cond sig, beats S templates) > best-r S > Null."""
    best_s_r = max(abs(r_splus) if p_splus < ALPHA else 0.0,
                   abs(r_sminus) if p_sminus < ALPHA else 0.0)
    if oplus_any_sig and r_oplus_mean > max(best_s_r, 0.3):
        return "O+"
    if p_splus < ALPHA and p_sminus < ALPHA:
        return "S+" if abs(r_splus) >= abs(r_sminus) else "S-"
    if p_splus < ALPHA:
        return "S+"
    if p_sminus < ALPHA:
        return "S-"
    return "Null"


def classify_session(sess, session_prefix: str, has_omit: bool,
                     rng: np.random.Generator) -> list[dict]:
    """Run template correlation classification for all qualifying units in one session."""
    try:
        rrrr_epochs = sess.get_epochs(phase=2, condition="RRRR", correct_only=True)
        rrrr_onsets = rrrr_epochs["start_time"].values
    except Exception as e:
        print(f"  [WARN] RRRR epoch query failed: {e}")
        return []

    if len(rrrr_onsets) < MIN_TRIALS:
        print(f"  [SKIP] Only {len(rrrr_onsets)} RRRR trials (need {MIN_TRIALS})")
        return []

    omit_onsets = {}
    if has_omit:
        for cond in OMIT_CONDITIONS:
            try:
                ep = sess.get_epochs(phase=2, condition=cond, correct_only=True)
                omit_onsets[cond] = ep["start_time"].values
            except Exception:
                omit_onsets[cond] = np.array([])
    else:
        for cond in OMIT_CONDITIONS:
            omit_onsets[cond] = np.array([])

    try:
        units_df = sess.get_units(quality="stable_plus")
    except Exception:
        try:
            units_df = sess.get_units()
        except Exception as e:
            print(f"  [WARN] get_units() failed: {e}")
            return []

    if units_df is None or len(units_df) == 0:
        print("  [WARN] No units returned")
        return []

    results = []
    n_skipped = 0

    # Always iterate by row position (index), not unit_id column — footgun #9
    for row_pos in units_df.index:
        uid_col = int(units_df.loc[row_pos, "unit_id"]) if "unit_id" in units_df.columns else row_pos
        spike_times = sess.get_spike_times(row_pos)
        if spike_times is None or len(spike_times) == 0:
            n_skipped += 1
            continue

        area = str(units_df.loc[row_pos, "area"]) if "area" in units_df.columns else "unknown"

        rrrr_vec = per_epoch_rate_hz(spike_times, rrrr_onsets[:MIN_TRIALS])
        if rrrr_vec.mean() < MIN_MEAN_RATE_HZ:
            n_skipped += 1
            continue

        r_splus, p_splus = perm_corr(rrrr_vec, S_PLUS_TEMPLATE, N_PERM, rng)
        r_sminus, p_sminus = perm_corr(rrrr_vec, S_MINUS_TEMPLATE, N_PERM, rng)

        r_oplus: dict[str, float] = {}
        p_oplus: dict[str, float] = {}
        for cond in OMIT_CONDITIONS:
            onsets = omit_onsets.get(cond, np.array([]))
            if len(onsets) >= MIN_TRIALS:
                ovec = per_epoch_rate_hz(spike_times, onsets[:MIN_TRIALS])
                r, p = perm_corr(ovec, omission_template(cond), N_PERM, rng)
            else:
                r, p = 0.0, 1.0
            r_oplus[cond] = r
            p_oplus[cond] = p

        r_oplus_mean = float(np.mean(list(r_oplus.values())))
        oplus_any_sig = any(p_oplus[c] < ALPHA for c in OMIT_CONDITIONS)
        label = assign_label(r_splus, p_splus, r_sminus, p_sminus, r_oplus_mean, oplus_any_sig)

        results.append({
            "session_prefix": session_prefix,
            "unit_row_idx": row_pos,
            "unit_id_col": uid_col,
            "area": area,
            "r_Splus": r_splus,
            "p_Splus": p_splus,
            "r_Sminus": r_sminus,
            "p_Sminus": p_sminus,
            "r_Oplus_RXRR": r_oplus["RXRR"],
            "p_Oplus_RXRR": p_oplus["RXRR"],
            "r_Oplus_RRXR": r_oplus["RRXR"],
            "p_Oplus_RRXR": p_oplus["RRXR"],
            "r_Oplus_RRRX": r_oplus["RRRX"],
            "p_Oplus_RRRX": p_oplus["RRRX"],
            "r_Oplus_mean": r_oplus_mean,
            "Oplus_any_sig": oplus_any_sig,
            "template_label": label,
        })

    print(f"  Classified {len(results)} units; skipped {n_skipped}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-session template-correlation classification (S+/S-/O+/Null)."
    )
    parser.add_argument("--session", default=None,
                        help="Run on one session only (session_prefix). Default: all nwb_ok.")
    parser.add_argument("--max-sessions", type=int, default=None,
                        help="Limit number of sessions processed (smoke test).")
    args = parser.parse_args()

    readiness = pd.read_csv(READINESS_CSV)
    ready = readiness[readiness["nwb_ok"] == True].copy()

    if args.session:
        ready = ready[ready["session_prefix"] == args.session]
        if len(ready) == 0:
            raise SystemExit(f"Session not found in readiness CSV: {args.session}")

    if args.max_sessions:
        ready = ready.head(args.max_sessions)

    print(f"Processing {len(ready)} sessions (N_PERM={N_PERM}, MIN_TRIALS={MIN_TRIALS})...")
    rng = np.random.default_rng(RNG_SEED)
    all_results: list[dict] = []

    for _, sess_row in ready.iterrows():
        prefix = str(sess_row["session_prefix"])
        nwb_path = str(sess_row["nwb_path"])
        has_omit = bool(sess_row.get("tfr_r_family_ok", False))

        print(f"\n[{prefix}]  has_omit={has_omit}")

        if not Path(nwb_path).exists():
            print(f"  [SKIP] NWB file not found: {nwb_path}")
            continue

        try:
            sess = oa.read(nwb_path)
        except Exception as e:
            print(f"  [ERROR] Could not load: {e}")
            continue

        rows = classify_session(sess, prefix, has_omit, rng)
        all_results.extend(rows)

    if not all_results:
        print("\nNo results — nothing written.")
        return

    df = pd.DataFrame(all_results)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nWrote {len(df)} rows -> {OUT_CSV}")
    print("\nLabel distribution:")
    print(df["template_label"].value_counts().to_string())
    print("\nLabel distribution by area:")
    ct = df.groupby(["area", "template_label"]).size().unstack(fill_value=0)
    print(ct.to_string())


if __name__ == "__main__":
    main()
