"""
Granger causality connectivity: V1 ↔ PFC
Conditions: omission, stimulus, control shuffle
Sessions: all nwb_ok + sidecar_ok with both V1 and PFC probes

Output:
  outputs/connectivity/granger_v1_pfc_results.csv
  outputs/connectivity/granger_v1_pfc_figure.png

Convention: jrsa(target, driver, metric="granger") → driver → target
  gc_V1_to_PFC  = jrsa(pfc_trace, v1_trace, ...)   # V1 drives PFC
  gc_PFC_to_V1  = jrsa(v1_trace, pfc_trace, ...)   # PFC drives V1
  directionality_index (DI) = gc_V1_to_PFC - gc_PFC_to_V1
  positive DI → net V1→PFC; negative → net PFC→V1
"""

from __future__ import annotations
import os
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

import jnwb as oa
from jnwb.jrsa import jrsa

# ---------------------------------------------------------------------------
# Paths — honour env overrides per AGENTS.md topology
# ---------------------------------------------------------------------------
NWB_DIR    = Path(os.environ.get("OMISSION_NWB_DIR",    "D:/analysis/nwb"))
META_DIR   = Path(os.environ.get("OMISSION_META_DIR",   "D:/workspace/data/metadata"))
READY_CSV  = Path("artifacts/data/session_readiness.csv")
OUT_DIR    = Path("outputs/connectivity")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MAX_LAG      = 10        # lags tested for AIC selection in _granger
N_PERM       = 500       # permutation test iterations
SMOOTHING_MS = 50        # Gaussian smoothing kernel for MUAe (ms)
BIN_MS       = 10        # spike binning resolution (ms)
EPOCH_WINDOW = (0, 531)  # one omission/stim slot in ms (p1→d1)
TARGET_AREAS = {"v1": ["V1", "V1d", "V1a"],
                "pfc": ["PFC", "FrA", "MOs", "PL", "IL"]}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_readiness() -> pd.DataFrame:
    df = pd.read_csv(READY_CSV)
    # Gate: both NWB and sidecar must be ok; TFR not required for spike-based Granger
    return df[df["nwb_ok"].astype(bool) & df["sidecar_ok"].astype(bool)].copy()


def _area_match(location: str, candidates: list[str]) -> bool:
    """Check if a probe location string matches any target area label."""
    # Per AGENTS.md footgun #3: do NOT use split(',')[0]
    loc = str(location).strip()
    return any(c.lower() in loc.lower() for c in candidates)


def _smooth_rates(rates: np.ndarray, bin_ms: int, sigma_ms: int) -> np.ndarray:
    """Gaussian smooth a (n_units, n_bins) firing rate matrix along time axis."""
    from scipy.ndimage import gaussian_filter1d
    sigma_bins = sigma_ms / bin_ms
    return gaussian_filter1d(rates.astype(float), sigma=sigma_bins, axis=1)


def _get_population_trace(
    session, area_labels: list[str], epoch_type: str,
    window_ms: tuple, bin_ms: int, smooth_ms: int,
    shuffle: bool = False
) -> np.ndarray | None:
    """
    Build a mean population firing rate trace for a given area across valid trials.

    Returns shape: (n_valid_trials, n_timebins)
    Returns None if area has no units in this session.
    """
    units_df = session.get_units()

    # Resolve area membership using the 'area' column inside get_units() output
    area_mask = units_df["area"].apply(lambda area: any(a.lower() in str(area).lower() for a in area_labels))
    area_units = units_df[area_mask]
    if len(area_units) == 0:
        return None

    # Get trial epochs
    try:
        epochs = session.get_epochs()
        # Filter correct trials only
        correct_epochs = epochs[epochs["correct"].astype(float) == 1.0]
        
        # Identify trials matching the epoch_type
        # For 'omission' trials, we select trials that have an omission slot (where is_omission == 1)
        # For 'stimulus' (control) trials, we select standard non-omission trials (where no slots are omissions)
        # To avoid confusion, we group epochs by trial_num.
        trial_groups = correct_epochs.groupby("trial_num")
        
        valid_trials = []
        for trial_id, group in trial_groups:
            # Check if this trial has any omission
            has_omission = group["is_omission"].astype(str).str.strip().str.startswith("1").any()
            if epoch_type == "omission" and has_omission:
                valid_trials.append(group)
            elif epoch_type == "stimulus" and not has_omission:
                valid_trials.append(group)
                
        if len(valid_trials) == 0:
            return None
            
        # Reconstruct filtered trials DataFrame by taking the first event (e.g. trial start) of each group
        trials = pd.concat([g.iloc[[0]] for g in valid_trials])
        
    except Exception as e:
        warnings.warn(f"Epoch loading/filtering failed: {e}")
        return None

    if len(trials) == 0:
        return None

    # Build PSTH matrix: (n_trials, n_timebins)
    # Per AGENTS.md footgun #9: use DataFrame index, NOT unit_id column
    n_bins = int((window_ms[1] - window_ms[0]) / bin_ms)
    psth_list = []

    for trial_idx, trial in trials.iterrows():
        t_start = float(trial["start_time"]) + window_ms[0] / 1000.0
        t_end   = float(trial["start_time"]) + window_ms[1] / 1000.0
        bins = np.linspace(t_start, t_end, n_bins + 1)
        unit_counts = []
        for df_row_idx in area_units.index:   # iterate over DataFrame row indices
            try:
                spikes = session.get_spike_times(df_row_idx)  # uses row index
                counts, _ = np.histogram(spikes, bins=bins)
                unit_counts.append(counts.astype(float) / (bin_ms / 1000.0))  # Hz
            except Exception:
                continue
        if len(unit_counts) == 0:
            continue
        # Mean across units → population rate trace
        psth_list.append(np.mean(unit_counts, axis=0))

    if len(psth_list) == 0:
        return None

    traces = np.array(psth_list)  # (n_trials, n_bins)
    traces = _smooth_rates(traces, bin_ms, smooth_ms)

    if shuffle:
        # Control: time-shuffle each trial independently
        rng = np.random.default_rng(42)
        for i in range(traces.shape[0]):
            traces[i] = traces[i, rng.permutation(traces.shape[1])]

    return traces   # (n_trials, n_bins)


def _run_granger_for_session(
    session_row: pd.Series,
    condition: str,
    shuffle: bool = False,
) -> dict | None:
    """
    Load one session, extract V1 and PFC population traces, run bidirectional Granger.
    Returns a result dict or None if session lacks one of the areas.
    """
    nwb_path = NWB_DIR / session_row["filename"] if "filename" in session_row else Path(session_row["nwb_path"])
    if not nwb_path.exists():
        warnings.warn(f"NWB not found: {nwb_path}")
        return None

    try:
        session = oa.read(str(nwb_path))
    except Exception as e:
        warnings.warn(f"Failed to load {nwb_path.name}: {e}")
        return None

    v1_traces  = _get_population_trace(
        session, TARGET_AREAS["v1"],  condition,
        EPOCH_WINDOW, BIN_MS, SMOOTHING_MS, shuffle=shuffle
    )
    pfc_traces = _get_population_trace(
        session, TARGET_AREAS["pfc"], condition,
        EPOCH_WINDOW, BIN_MS, SMOOTHING_MS, shuffle=shuffle
    )

    if v1_traces is None or pfc_traces is None:
        warnings.warn(f"{session_row['session_id']}: missing V1 or PFC units, skipping.")
        return None

    # Align trial counts
    n_trials = min(len(v1_traces), len(pfc_traces))
    v1_traces  = v1_traces[:n_trials]
    pfc_traces = pfc_traces[:n_trials]

    # Concatenate across trials to form one long time-series for Granger
    v1_ts  = v1_traces.ravel()
    pfc_ts = pfc_traces.ravel()

    results = {}
    for direction, (x1_ts, x2_ts) in {
        "V1_to_PFC":  (pfc_ts, v1_ts),   # x2=V1 drives x1=PFC
        "PFC_to_V1":  (v1_ts,  pfc_ts),  # x2=PFC drives x1=V1
    }.items():
        try:
            # We verified n_jobs=4 succeeds on CPU without pickling errors
            r = jrsa(
                x1_ts, x2_ts,
                metric="granger",
                max_lag=MAX_LAG,
                stats=True,
                permutations=N_PERM,
                correction="fdr_bh",
                random_state=42,
                n_jobs=4,
            )
            results[direction] = {
                "f_stat": float(r.value),
                "p_raw":  float(r.p) if r.p is not None else np.nan,
                "q_corr": float(r.q) if r.q is not None else np.nan,
            }
        except Exception as e:
            warnings.warn(f"Granger failed ({direction}, {session_row['session_id']}): {e}")
            results[direction] = {"f_stat": np.nan, "p_raw": np.nan, "q_corr": np.nan}

    di = results.get("V1_to_PFC", {}).get("f_stat", np.nan) - \
         results.get("PFC_to_V1", {}).get("f_stat", np.nan)

    return {
        "session_id":     session_row["session_id"],
        "condition":      condition + ("_shuffle" if shuffle else ""),
        "gc_V1_to_PFC_F": results.get("V1_to_PFC", {}).get("f_stat", np.nan),
        "gc_PFC_to_V1_F": results.get("PFC_to_V1", {}).get("f_stat", np.nan),
        "DI":             di,
        "p_V1_to_PFC":    results.get("V1_to_PFC", {}).get("p_raw",  np.nan),
        "p_PFC_to_V1":    results.get("PFC_to_V1", {}).get("p_raw",  np.nan),
        "q_V1_to_PFC":    results.get("V1_to_PFC", {}).get("q_corr", np.nan),
        "q_PFC_to_V1":    results.get("PFC_to_V1", {}).get("q_corr", np.nan),
        "n_trials":       n_trials,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    readiness = _load_readiness()
    print(f"Sessions eligible: {len(readiness)}")

    rows = []
    for _, sess_row in readiness.iterrows():
        for cond in ["omission", "stimulus"]:
            # Real condition
            r = _run_granger_for_session(sess_row, cond, shuffle=False)
            if r is not None:
                rows.append(r)
            # Control shuffle
            r_sh = _run_granger_for_session(sess_row, cond, shuffle=True)
            if r_sh is not None:
                rows.append(r_sh)

    if len(rows) == 0:
        print("No valid sessions found with both V1 and PFC units.")
        return

    df = pd.DataFrame(rows)
    csv_path = OUT_DIR / "granger_v1_pfc_results.csv"
    df.to_csv(csv_path, index=False)
    print(f"Results saved: {csv_path}")
    print(df.to_string(index=False))

    # --- Figure ----------------------------------------------------------
    _plot_results(df)


def _plot_results(df: pd.DataFrame):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
    except ImportError:
        warnings.warn("matplotlib not available; skipping figure.")
        return

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("Granger Causality: V1 ↔ PFC\n(F-statistic, AIC best-lag selection)",
                 fontsize=13, fontweight="bold")

    conditions_plot = [
        ("omission",          "Omission",          "#E63946"),
        ("stimulus",          "Stimulus",           "#457B9D"),
        ("omission_shuffle",  "Omission (shuffle)", "#A8DADC"),
        ("stimulus_shuffle",  "Stimulus (shuffle)", "#CDB4DB"),
    ]

    # Panel 1: F-stat V1→PFC per condition
    ax = axes[0]
    for i, (cond, label, color) in enumerate(conditions_plot):
        sub = df[df["condition"] == cond]["gc_V1_to_PFC_F"].dropna()
        if len(sub) == 0:
            continue
        ax.bar(i, sub.mean(), yerr=sub.sem(), color=color, width=0.6,
               capsize=4, label=label, alpha=0.85, edgecolor="k", linewidth=0.5)
    ax.set_xticks([])
    ax.set_ylabel("Granger F-statistic")
    ax.set_title("V1 → PFC")
    ax.legend(fontsize=8, loc="upper right")

    # Panel 2: F-stat PFC→V1 per condition
    ax = axes[1]
    for i, (cond, label, color) in enumerate(conditions_plot):
        sub = df[df["condition"] == cond]["gc_PFC_to_V1_F"].dropna()
        if len(sub) == 0:
            continue
        ax.bar(i, sub.mean(), yerr=sub.sem(), color=color, width=0.6,
               capsize=4, label=label, alpha=0.85, edgecolor="k", linewidth=0.5)
    ax.set_xticks([])
    ax.set_ylabel("Granger F-statistic")
    ax.set_title("PFC → V1")
    ax.legend(fontsize=8, loc="upper right")

    # Panel 3: Directionality index (DI = V1→PFC - PFC→V1)
    ax = axes[2]
    for i, (cond, label, color) in enumerate(conditions_plot):
        sub = df[df["condition"] == cond]["DI"].dropna()
        if len(sub) == 0:
            continue
        ax.bar(i, sub.mean(), yerr=sub.sem(), color=color, width=0.6,
               capsize=4, label=label, alpha=0.85, edgecolor="k", linewidth=0.5)
    ax.axhline(0, color="k", linewidth=0.8, linestyle="--")
    ax.set_xticks([])
    ax.set_ylabel("DI = F(V1→PFC) − F(PFC→V1)")
    ax.set_title("Directionality Index")
    ax.legend(fontsize=8, loc="upper right")

    # Annotate significance per session (q < 0.05)
    for ax_idx, col in enumerate(["q_V1_to_PFC", "q_PFC_to_V1", None]):
        if col is None:
            continue
        for i, (cond, _, _) in enumerate(conditions_plot):
            sub = df[df["condition"] == cond]
            n_sig = (sub[col].dropna() < 0.05).sum()
            n_tot = len(sub[col].dropna())
            if n_tot > 0:
                axes[ax_idx].text(i, axes[ax_idx].get_ylim()[1] * 0.95,
                                  f"{n_sig}/{n_tot}", ha="center", fontsize=7, color="k")

    plt.tight_layout()
    fig_path = OUT_DIR / "granger_v1_pfc_figure.png"
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Figure saved: {fig_path}")


if __name__ == "__main__":
    main()
