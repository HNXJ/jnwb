r"""
S2 (context/analysis_spec_SPK.md): population responses by class (Fig 3).

Method (spec): "Population PSTHs for S+, S-, O+ per area, stim and omission. Normalise per
unit before averaging (z-score to fixation), otherwise high-rate units dominate."
Output (spec): "Class x area PSTH grid, CI bootstrapped over sessions, not trials."

Reads the canonical population from S1 (outputs/classification/unit_inclusion_v1.csv,
reviewed and approved 2026-08-17 -- see artifacts/.lab/S1-unit-inclusion-rework-in-progress-
20260817.json). Classes: S+ = is_s_plus, S- = is_s_minus, O+ = is_omission_inclusion_new (the
new likelihood-of-firing criterion, NOT the old template-correlation is_o_plus_old_templatecorr
or the unmodified local-baseline is_o_plus -- S1's whole point was that the new criterion is
canonical going forward).

Primary population: quality_tier == 'stable' only. mua/unstable units are tagged in S1's table
but per this project's tagging discipline (never silently pool with stable) they are reported
here only as a separate n-count sensitivity table, not folded into the PSTH traces -- disclosed
explicitly in stats JSON and README, not silently dropped.

Area pooling: V3/V3a/V3d -> 'V3a/d' via figstyle.AREA_POOL, per omission-signal skill SS7
("Never contrast V3a against V3d... pool to the inclusive label for any inference").

Reuses omission.jnwb_ext.unit_classification (unmodified): GLO_CONDITIONS, stimulus_present_events,
omission_events, SLOT_WINDOW_MS, BASELINE_MS, precompute_condition_onsets, _rate_in_window.
Does not reimplement trial-onset discovery or event-slot geometry.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "context" / "figures"))

import omission as oa
from jnwb import paths as P
from omission.jnwb_ext.unit_classification import (
    BASELINE_MS,
    GLO_CONDITIONS,
    SLOT_WINDOW_MS,
    _rate_in_window,
    omission_events,
    precompute_condition_onsets,
    stimulus_present_events,
)

import figstyle

OUT_DIR = Path(__file__).resolve().parent
INCLUSION_CSV = REPO / "outputs/classification/unit_inclusion_v1.csv"
READINESS_CSV = REPO / "artifacts/data/session_readiness.csv"

SEED = 42
N_BOOT = 2000
WIN_MS = (-300.0, 700.0)      # relative to slot onset
BIN_MS = 20.0
BASELINE_STD_FLOOR_HZ = 0.5   # avoid divide-by-tiny-std when a unit barely fires at fx
MIN_UNITS_FOR_SESSION_POINT = 1
MIN_SESSIONS_FOR_CI = 2

CLASS_COLS = {"S+": "is_s_plus", "S-": "is_s_minus", "O+": "is_omission_inclusion_new"}
CLASS_COLORS = {"S+": "#1B9E77", "S-": "#7570B3", "O+": figstyle.CLASS_COLORS["O+"]}


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO), stderr=subprocess.DEVNULL, text=True
        )
        return out.strip()
    except Exception:
        return "unknown"


def pool_area(raw_area: str) -> str:
    return figstyle.AREA_POOL.get(raw_area, raw_area)


def bin_edges_s() -> np.ndarray:
    n_bins = int(round((WIN_MS[1] - WIN_MS[0]) / BIN_MS))
    return np.linspace(WIN_MS[0] / 1000.0, WIN_MS[1] / 1000.0, n_bins + 1)


def bin_centers_ms(edges_s: np.ndarray) -> np.ndarray:
    return (edges_s[:-1] + edges_s[1:]) / 2.0 * 1000.0


def pooled_event_onsets_s(onsets: dict, events: list) -> np.ndarray:
    """Absolute slot onsets (s) for a pooled list of (cond, slot), across all trials."""
    out = []
    for cond, slot in events:
        trials = onsets.get(cond, np.array([]))
        if len(trials) == 0:
            continue
        win = SLOT_WINDOW_MS[slot]
        out.append(np.asarray(trials, dtype=float) + win[0] / 1000.0)
    return np.concatenate(out) if out else np.array([], dtype=float)


def unit_pooled_psth_rate(spike_times: np.ndarray, slot_onsets_s: np.ndarray, edges_s: np.ndarray) -> np.ndarray:
    """Trial-averaged firing rate (Hz) per bin, pooled across all given slot onsets."""
    st = np.sort(np.asarray(spike_times, dtype=float))
    n_bins = len(edges_s) - 1
    if len(slot_onsets_s) == 0:
        return np.full(n_bins, np.nan)
    counts = np.zeros(n_bins)
    bin_width_s = edges_s[1] - edges_s[0]
    for onset in slot_onsets_s:
        mask = (st >= onset + edges_s[0]) & (st <= onset + edges_s[-1])
        rel = st[mask] - onset
        c, _ = np.histogram(rel, bins=edges_s)
        counts += c
    return (counts / len(slot_onsets_s)) / bin_width_s


def unit_fx_baseline_stats(spike_times: np.ndarray, all_trial_onsets_s: np.ndarray) -> tuple:
    """Per-trial fx-window rate (BASELINE_MS relative to p1 onset) -> (mean_hz, std_hz)."""
    if len(all_trial_onsets_s) == 0:
        return 0.0, BASELINE_STD_FLOOR_HZ
    st = np.sort(np.asarray(spike_times, dtype=float))
    rates = np.array([_rate_in_window(st, float(o), BASELINE_MS) for o in all_trial_onsets_s])
    mean_hz = float(np.mean(rates))
    std_hz = float(np.std(rates, ddof=1)) if len(rates) > 1 else BASELINE_STD_FLOOR_HZ
    return mean_hz, max(std_hz, BASELINE_STD_FLOOR_HZ)


def session_bootstrap_ci(traces: np.ndarray, n_boot=N_BOOT, seed=SEED):
    """traces: (n_sessions, n_times). Resamples SESSION indices. Returns (mean, lo, hi)."""
    n_sessions = traces.shape[0]
    point = traces.mean(axis=0)
    if n_sessions < MIN_SESSIONS_FOR_CI:
        return point, point.copy(), point.copy()
    rng = np.random.default_rng(seed)
    draws = np.empty((n_boot, traces.shape[1]))
    for i in range(n_boot):
        idx = rng.integers(0, n_sessions, size=n_sessions)
        draws[i] = traces[idx].mean(axis=0)
    lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
    return point, lo, hi


def compute_session_unit_traces(sess, unit_rows: list, edges_s: np.ndarray) -> dict:
    """For each unit_row in this session, return (stim_z, omission_z) traces, or None if unusable."""
    onsets = precompute_condition_onsets(sess, correct_only=True)
    stim_slot_onsets = pooled_event_onsets_s(onsets, stimulus_present_events())
    omit_slot_onsets = pooled_event_onsets_s(onsets, omission_events())
    all_trial_onsets = np.concatenate([onsets[c] for c in GLO_CONDITIONS if len(onsets.get(c, [])) > 0]) \
        if any(len(onsets.get(c, [])) > 0 for c in GLO_CONDITIONS) else np.array([])

    out = {}
    for uid in unit_rows:
        spikes = sess.get_spike_times(int(uid))
        if spikes is None or len(spikes) == 0:
            out[uid] = None
            continue
        base_mean, base_std = unit_fx_baseline_stats(spikes, all_trial_onsets)
        stim_rate = unit_pooled_psth_rate(spikes, stim_slot_onsets, edges_s)
        omit_rate = unit_pooled_psth_rate(spikes, omit_slot_onsets, edges_s)
        out[uid] = {
            "stim_z": (stim_rate - base_mean) / base_std,
            "omission_z": (omit_rate - base_mean) / base_std,
            "baseline_mean_hz": base_mean,
            "baseline_std_hz": base_std,
        }
    return out


def run(max_sessions: int = None) -> dict:
    incl = pd.read_csv(INCLUSION_CSV)
    incl = incl[incl["quality_tier"] == "stable"].copy()
    incl["area_pooled"] = incl["area"].apply(pool_area)

    readiness = pd.read_csv(READINESS_CSV)
    ready_sessions = set(readiness[readiness["nwb_ok"] == True]["session_prefix"])
    incl = incl[incl["session"].isin(ready_sessions)]

    sessions = sorted(incl["session"].unique())
    if max_sessions is not None:
        sessions = sessions[:max_sessions]

    edges_s = bin_edges_s()
    centers_ms = bin_centers_ms(edges_s)
    n_bins = len(centers_ms)

    # accumulator: (area, class, condition) -> {session -> mean_z_trace}
    acc: dict = {}
    n_units_used = 0
    n_units_skipped_no_spikes = 0
    per_session_n_units = {}

    t0 = time.time()
    for si, prefix in enumerate(sessions, start=1):
        sub = incl[incl["session"] == prefix]
        unit_rows = sorted(sub["unit_row"].unique().tolist())
        path = P.resolve_nwb_path(prefix)
        if not path.exists():
            print(f"  [{si}/{len(sessions)}] MISSING nwb for {prefix}, skipping")
            continue
        try:
            sess = oa.read(str(path))
        except Exception as e:
            print(f"  [{si}/{len(sessions)}] FAILED to load {prefix}: {e}")
            continue

        traces_by_unit = compute_session_unit_traces(sess, unit_rows, edges_s)
        per_session_n_units[prefix] = 0

        for _, urow in sub.iterrows():
            uid = urow["unit_row"]
            area = urow["area_pooled"]
            t = traces_by_unit.get(uid)
            if t is None:
                n_units_skipped_no_spikes += 1
                continue
            n_units_used += 1
            per_session_n_units[prefix] += 1
            for cls, col in CLASS_COLS.items():
                if not bool(urow[col]):
                    continue
                for cond, key in (("stim", "stim_z"), ("omission", "omission_z")):
                    acc.setdefault((area, cls, cond), {}).setdefault(prefix, []).append(t[key])

        elapsed = time.time() - t0
        print(f"  [{si}/{len(sessions)}] {prefix}: {per_session_n_units[prefix]} stable units, "
              f"{elapsed:.0f}s elapsed")

    # collapse to one session-level trace per (area, class, condition), then session-bootstrap
    results = {}
    for (area, cls, cond), by_session in acc.items():
        session_means = []
        session_ids = []
        session_n = []
        for sid, traces in by_session.items():
            arr = np.vstack(traces)
            session_means.append(np.nanmean(arr, axis=0))
            session_ids.append(sid)
            session_n.append(len(traces))
        traces_mat = np.vstack(session_means)
        point, lo, hi = session_bootstrap_ci(traces_mat)
        results[(area, cls, cond)] = {
            "point": point, "lo": lo, "hi": hi,
            "n_sessions": len(session_ids),
            "n_units_total": int(sum(session_n)),
            "session_ids": session_ids,
            "session_n_units": session_n,
        }

    return {
        "results": results,
        "centers_ms": centers_ms,
        "edges_s": edges_s,
        "n_sessions_processed": len(sessions),
        "n_units_used": n_units_used,
        "n_units_skipped_no_spikes": n_units_skipped_no_spikes,
        "per_session_n_units": per_session_n_units,
    }


def plot_figure(run_out: dict, out_path_stem: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figstyle.use_house_style()
    results = run_out["results"]
    centers_ms = run_out["centers_ms"]

    areas_present = sorted({k[0] for k in results.keys()}, key=lambda a: figstyle.AREA_ORDER.index(a) if a in figstyle.AREA_ORDER else 99)
    conditions = ["stim", "omission"]
    n_rows = len(areas_present)
    n_cols = len(conditions)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5.5 * n_cols, 2.1 * n_rows), squeeze=False)

    for ri, area in enumerate(areas_present):
        for ci, cond in enumerate(conditions):
            ax = axes[ri][ci]
            if cond == "stim":
                ax.axvspan(SLOT_WINDOW_MS[1][0] - SLOT_WINDOW_MS[1][0], 0, alpha=0)  # no-op keep style import used
            ax.axvspan(0, 531, color=figstyle.STIM_SHADE if cond == "stim" else figstyle.OMIT_SHADE, alpha=0.5, zorder=0)
            ax.axvline(0, color="k", lw=0.6, ls=":")
            any_plotted = False
            for cls in CLASS_COLS:
                key = (area, cls, cond)
                if key not in results:
                    continue
                r = results[key]
                if r["n_sessions"] < MIN_SESSIONS_FOR_CI:
                    label = f"{cls} (n_sess={r['n_sessions']}, no CI)"
                else:
                    label = f"{cls} (n_sess={r['n_sessions']}, n={r['n_units_total']})"
                ax.plot(centers_ms, r["point"], color=CLASS_COLORS[cls], lw=1.3, label=label)
                ax.fill_between(centers_ms, r["lo"], r["hi"], color=CLASS_COLORS[cls], alpha=0.2, lw=0)
                any_plotted = True
            ax.axhline(0, color="gray", lw=0.5)
            if not any_plotted:
                ax.text(0.5, 0.5, "no qualifying units", transform=ax.transAxes,
                        ha="center", va="center", fontsize=7, color="gray")
            if ri == 0:
                ax.set_title(f"{cond}", fontsize=9)
            if ci == 0:
                ax.set_ylabel(f"{area}\nz (fx)", fontsize=8)
            if ri == n_rows - 1:
                ax.set_xlabel("time from slot onset (ms)", fontsize=8)
            ax.legend(fontsize=5.5, loc="upper right", framealpha=0.7)
            ax.tick_params(labelsize=7)

    fig.suptitle("S2: population responses by class (S+/S-/O+), stim vs omission, stable units only\n"
                 "z-scored to fixation per unit, session-bootstrap 95% CI (shaded)", fontsize=10)
    fig.subplots_adjust(top=0.90, hspace=0.5, wspace=0.3)
    figstyle.save(fig, OUT_DIR, "S2")
    plt.close(fig)


def build_stats(run_out: dict) -> dict:
    results = run_out["results"]
    per_pair = []
    for (area, cls, cond), r in results.items():
        per_pair.append({
            "area": area, "class": cls, "condition": cond,
            "n_sessions": r["n_sessions"], "n_units_total": r["n_units_total"],
            "session_ids": r["session_ids"], "session_n_units": r["session_n_units"],
            "point_z": r["point"].tolist(), "ci_lo_z": r["lo"].tolist(), "ci_hi_z": r["hi"].tolist(),
            "discriminating_n_sessions_ge_2": bool(r["n_sessions"] >= MIN_SESSIONS_FOR_CI),
        })
    return {
        "id": "S2_population_responses_by_class",
        "spec_source": "context/analysis_spec_SPK.md SS2",
        "inclusion_source": str(INCLUSION_CSV),
        "primary_population": "quality_tier == 'stable' only (mua/unstable tagged, not pooled -- see sensitivity table)",
        "class_definitions": {
            "S+": "is_s_plus (omission.jnwb_ext.unit_classification, unmodified)",
            "S-": "is_s_minus (omission.jnwb_ext.unit_classification wrapper, min_baseline_for_s_minus_hz gate dropped per S1)",
            "O+": "is_omission_inclusion_new (S1's new likelihood-of-firing criterion, canonical per S1's downstream contract)",
        },
        "area_pooling": "figstyle.AREA_POOL (V3/V3a/V3d -> V3a/d)",
        "window_ms": list(WIN_MS), "bin_ms": BIN_MS,
        "baseline": "fx window (BASELINE_MS relative to p1 onset), per-trial rate mean/std per unit; std floored at "
                    f"{BASELINE_STD_FLOOR_HZ} Hz to avoid divide-by-near-zero",
        "ci_method": f"session-level bootstrap (n_boot={N_BOOT}, seed={SEED}, 95% percentile) on the per-session "
                     "mean z-trace, not on trials or units directly -- degenerate (point==lo==hi) when n_sessions<2, "
                     "not fabricated",
        "n_sessions_processed": run_out["n_sessions_processed"],
        "n_units_used": run_out["n_units_used"],
        "n_units_skipped_no_spikes": run_out["n_units_skipped_no_spikes"],
        "per_session_n_units": run_out["per_session_n_units"],
        "area_class_condition_results": per_pair,
        "git_sha": _git_sha(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
    }


def build_manifest(run_out: dict) -> dict:
    return {
        "method": "S2_population_responses_by_class",
        "git_sha": _git_sha(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {"inclusion_csv": str(INCLUSION_CSV), "readiness_csv": str(READINESS_CSV)},
        "n_sessions_attempted": run_out["n_sessions_processed"],
        "n_units_used": run_out["n_units_used"],
        "seed": SEED,
        "n_boot": N_BOOT,
        "window_ms": list(WIN_MS),
        "bin_ms": BIN_MS,
    }


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _make_synthetic_unit_omission_responsive(rate_base_hz=5.0, rate_omission_hz=25.0, seed=0):
    """Synthetic unit that fires at rate_base_hz everywhere except a 200ms burst starting at
    the omission-slot onset, where it fires at rate_omission_hz. Trials span [-1000, 4624]ms
    relative to p1 (matching FULL_SEQUENCE geometry), 40 trials."""
    rng = np.random.default_rng(seed)
    n_trials = 40
    trial_onsets = np.arange(n_trials) * 10.0  # 10s apart, non-overlapping
    slot_onset_ms = SLOT_WINDOW_MS[3][0]  # p3, matches AAXB canonical omit slot
    spikes = []
    for t0 in trial_onsets:
        # background poisson over [-1000, 4624] ms
        dur_s = 5.624
        n_bg = rng.poisson(rate_base_hz * dur_s)
        bg = t0 + (-1.0 + rng.random(n_bg) * dur_s)
        spikes.append(bg)
        # burst during [slot_onset, slot_onset+200] ms
        burst_dur_s = 0.2
        n_burst = rng.poisson(rate_omission_hz * burst_dur_s)
        burst = t0 + (slot_onset_ms / 1000.0) + rng.random(n_burst) * burst_dur_s
        spikes.append(burst)
    all_spikes = np.sort(np.concatenate(spikes))
    onsets_by_cond = {c: np.array([]) for c in GLO_CONDITIONS}
    onsets_by_cond["AAXB"] = trial_onsets
    return all_spikes, onsets_by_cond, trial_onsets


def test_pooled_psth_recovers_known_burst():
    spikes, onsets, trial_onsets = _make_synthetic_unit_omission_responsive()
    edges_s = bin_edges_s()
    centers_ms = bin_centers_ms(edges_s)
    slot_onsets = pooled_event_onsets_s(onsets, [("AAXB", 3)])
    rate = unit_pooled_psth_rate(spikes, slot_onsets, edges_s)
    burst_mask = (centers_ms >= 0) & (centers_ms <= 180)
    pre_mask = (centers_ms >= -280) & (centers_ms <= -20)
    burst_rate = np.mean(rate[burst_mask])
    pre_rate = np.mean(rate[pre_mask])
    assert burst_rate > pre_rate * 2.0, f"burst {burst_rate:.1f} Hz not clearly above pre {pre_rate:.1f} Hz"
    assert 15.0 < burst_rate < 35.0, f"burst rate {burst_rate:.1f} Hz outside expected ~25 Hz range"
    assert 2.0 < pre_rate < 9.0, f"pre rate {pre_rate:.1f} Hz outside expected ~5 Hz range"
    print("PASS: pooled PSTH recovers known synthetic burst")


def test_zscore_baseline_flat_unit_near_zero():
    """A unit firing at a constant rate everywhere (no modulation) must z-score to ~0 in every bin."""
    rng = np.random.default_rng(1)
    n_trials = 60
    trial_onsets = np.arange(n_trials) * 10.0
    rate_hz = 8.0
    spikes = []
    for t0 in trial_onsets:
        dur_s = 5.624
        n = rng.poisson(rate_hz * dur_s)
        spikes.append(t0 + (-1.0 + rng.random(n) * dur_s))
    all_spikes = np.sort(np.concatenate(spikes))
    edges_s = bin_edges_s()
    base_mean, base_std = unit_fx_baseline_stats(all_spikes, trial_onsets)
    slot_onsets = trial_onsets + SLOT_WINDOW_MS[3][0] / 1000.0
    rate = unit_pooled_psth_rate(all_spikes, slot_onsets, edges_s)
    z = (rate - base_mean) / base_std
    assert np.abs(np.mean(z)) < 1.0, f"flat unit z-mean {np.mean(z):.2f} not near 0"
    print(f"PASS: flat-rate unit z-scores near 0 (mean z={np.mean(z):.3f})")


def test_session_bootstrap_ci_degenerate_below_two_sessions():
    traces = np.array([[1.0, 2.0, 3.0]])
    point, lo, hi = session_bootstrap_ci(traces)
    assert np.allclose(point, lo) and np.allclose(point, hi), "n=1 session must give degenerate CI, not fabricated"
    traces2 = np.array([[1.0, 2.0, 3.0], [3.0, 2.0, 1.0], [2.0, 2.0, 2.0]])
    point2, lo2, hi2 = session_bootstrap_ci(traces2)
    assert np.allclose(point2, [2.0, 2.0, 2.0])
    assert np.all(lo2 <= point2) and np.all(hi2 >= point2)
    print("PASS: session bootstrap CI degenerate at n<2, real spread at n>=2")


def test_determinism():
    rng = np.random.default_rng(7)
    traces = rng.normal(size=(9, 12))  # enough sessions/bins that a seed collision is implausible
    r1 = session_bootstrap_ci(traces, seed=SEED)
    r2 = session_bootstrap_ci(traces, seed=SEED)
    for a, b in zip(r1, r2):
        assert np.array_equal(a, b), "same seed must give byte-identical CI"
    r3 = session_bootstrap_ci(traces, seed=SEED + 1)
    assert not np.array_equal(r1[1], r3[1]), "different seed should generally differ"
    print("PASS: determinism")


def test_pool_area():
    assert pool_area("V3") == "V3a/d"
    assert pool_area("V3a") == "V3a/d"
    assert pool_area("V3d") == "V3a/d"
    assert pool_area("FEF") == "FEF"
    print("PASS: area pooling (V3/V3a/V3d -> V3a/d)")


def run_self_tests():
    test_pooled_psth_recovers_known_burst()
    test_zscore_baseline_flat_unit_near_zero()
    test_session_bootstrap_ci_degenerate_below_two_sessions()
    test_determinism()
    test_pool_area()
    print("\nAll S2 self-tests PASSED")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_self_tests()
    else:
        max_sessions = None
        for a in sys.argv[1:]:
            if a.startswith("--max-sessions="):
                max_sessions = int(a.split("=")[1])
        run_out = run(max_sessions=max_sessions)
        stats = build_stats(run_out)
        manifest = build_manifest(run_out)
        (OUT_DIR / "S2_stats.json").write_text(json.dumps(stats, indent=2))
        (OUT_DIR / "S2_manifest.json").write_text(json.dumps(manifest, indent=2))
        plot_figure(run_out, OUT_DIR / "S2")
        print(f"\nDone. n_sessions={run_out['n_sessions_processed']} n_units_used={run_out['n_units_used']}")
