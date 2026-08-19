r"""
S5 (context/analysis_spec_SPK.md): cross-area spiking onset latency [THESIS FALSIFIER].

Method (spec): forward smoothing only (acausal smoothing manufactures spurious early onsets --
"the single most likely way to get the wrong FF/FB answer"). Fit exponential onset slope per
area. Bootstrap onset CI over sessions.
Output: onset +/- CI per area ordered by hierarchy level; pairwise onset-difference matrix
with CIs.
Discriminates: H1 low->high (feedforward) / H2 high->low (feedback) / H3 simultaneous.
Acceptance: if pairwise CIs overlap zero, set discriminating:false and say so -- a legitimate
reportable outcome that promotes CSD (LFP L4) to primary evidence.

Reuses omission.jnwb_ext.onset_fitting (causal_exp_smooth, fit_exponential_onset) UNCHANGED -- this is the
same causality-bounded exponential-onset machinery already built and self-tested for LFP L5
(context/figures/L5_onset_latency_hierarchy), applied here to spiking population rate instead of
LFP band envelope. Reuses S2's pooled-event-onset and binning helpers
(context/figures/S2_population_responses_by_class) for the spike-extraction side, rather than
re-deriving trial/slot geometry a second time.

Class parameterized via CLASS_COL so this same module is reused unchanged by S6 (S+/S-
directionality controls) -- see S6_directionality_controls_spk.py, which imports and calls
`run(class_col=...)` directly.
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
sys.path.insert(0, str(REPO / "context" / "figures" / "S2_population_responses_by_class"))

import omission as oa
from jnwb import paths as P
from omission.jnwb_ext.onset_fitting import causal_exp_smooth, fit_exponential_onset
from omission.jnwb_ext.unit_classification import omission_events, precompute_condition_onsets

import figstyle
from S2_population_responses_by_class import pool_area, pooled_event_onsets_s

OUT_DIR = Path(__file__).resolve().parent
INCLUSION_CSV = REPO / "outputs/classification/unit_inclusion_v1.csv"
READINESS_CSV = REPO / "artifacts/data/session_readiness.csv"

SEED = 42
N_BOOT = 2000
FIT_WIN_MS = (-300.0, 700.0)         # relative to omission-slot onset
BASELINE_WIN_MS = (-280.0, -20.0)
BIN_MS = 10.0
T0_BOUNDS_MS = (0.0, 650.0)
SMOOTH_TAU_MS = 30.0
MIN_UNITS_PER_AREA_SESSION = 1
MIN_SESSIONS_FOR_CI = 2
CLASS_COL_DEFAULT = "is_omission_inclusion_new"   # S5's primary class: O+ (new criterion)


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO), stderr=subprocess.DEVNULL, text=True
        )
        return out.strip()
    except Exception:
        return "unknown"


def bin_edges_s() -> np.ndarray:
    n_bins = int(round((FIT_WIN_MS[1] - FIT_WIN_MS[0]) / BIN_MS))
    return np.linspace(FIT_WIN_MS[0] / 1000.0, FIT_WIN_MS[1] / 1000.0, n_bins + 1)


def bin_centers_ms(edges_s: np.ndarray) -> np.ndarray:
    return (edges_s[:-1] + edges_s[1:]) / 2.0 * 1000.0


def population_rate_trace(spike_times_list: list, slot_onsets_s: np.ndarray, edges_s: np.ndarray) -> np.ndarray:
    """Pooled population rate (Hz), summed spikes across all units in spike_times_list, averaged
    over trials, per bin -- one unweighted population trace, not a per-unit average (a unit
    firing more contributes more spikes, same convention as a raw population PSTH)."""
    n_bins = len(edges_s) - 1
    if len(slot_onsets_s) == 0 or len(spike_times_list) == 0:
        return np.full(n_bins, np.nan)
    bin_width_s = edges_s[1] - edges_s[0]
    counts = np.zeros(n_bins)
    for st in spike_times_list:
        st = np.sort(np.asarray(st, dtype=float))
        for onset in slot_onsets_s:
            mask = (st >= onset + edges_s[0]) & (st <= onset + edges_s[-1])
            rel = st[mask] - onset
            c, _ = np.histogram(rel, bins=edges_s)
            counts += c
    return (counts / len(slot_onsets_s)) / bin_width_s / max(1, len(spike_times_list))


def fit_area_onset(spike_times_list: list, slot_onsets_s: np.ndarray, edges_s: np.ndarray, centers_ms: np.ndarray) -> dict:
    rate = population_rate_trace(spike_times_list, slot_onsets_s, edges_s)
    if np.any(np.isnan(rate)):
        return {"t0": np.nan, "tau": np.nan, "amplitude": np.nan, "baseline": np.nan,
                "r2": np.nan, "converged": False}
    smoothed = causal_exp_smooth(rate, bin_ms=BIN_MS, tau_ms=SMOOTH_TAU_MS)
    fit = fit_exponential_onset(centers_ms, smoothed, t0_bounds=T0_BOUNDS_MS, baseline_window=BASELINE_WIN_MS)
    return fit


def session_bootstrap_ci(values: np.ndarray, n_boot=N_BOOT, seed=SEED):
    n = len(values)
    point = float(np.mean(values))
    if n < MIN_SESSIONS_FOR_CI:
        return point, point, point
    rng = np.random.default_rng(seed)
    draws = np.array([values[rng.integers(0, n, size=n)].mean() for _ in range(n_boot)])
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return point, float(lo), float(hi)


def pairwise_diff_ci(vals_a: np.ndarray, vals_b: np.ndarray, n_boot=N_BOOT, seed=SEED):
    if len(vals_a) < MIN_SESSIONS_FOR_CI or len(vals_b) < MIN_SESSIONS_FOR_CI:
        mean_diff = float(np.mean(vals_a) - np.mean(vals_b))
        return mean_diff, mean_diff, mean_diff, True
    rng = np.random.default_rng(seed)
    na, nb = len(vals_a), len(vals_b)
    draws = np.array([
        vals_a[rng.integers(0, na, size=na)].mean() - vals_b[rng.integers(0, nb, size=nb)].mean()
        for _ in range(n_boot)
    ])
    lo, hi = np.percentile(draws, [2.5, 97.5])
    point = float(np.mean(vals_a) - np.mean(vals_b))
    non_discriminating = bool(lo <= 0.0 <= hi)
    return point, float(lo), float(hi), non_discriminating


def run(max_sessions: int = None, class_col: str = CLASS_COL_DEFAULT, quality_tier: str = "stable") -> dict:
    incl = pd.read_csv(INCLUSION_CSV)
    incl = incl[(incl["quality_tier"] == quality_tier) & (incl[class_col] == True)].copy()  # noqa: E712
    incl["area_pooled"] = incl["area"].apply(pool_area)

    readiness = pd.read_csv(READINESS_CSV)
    ready_sessions = set(readiness[readiness["nwb_ok"] == True]["session_prefix"])
    incl = incl[incl["session"].isin(ready_sessions)]

    sessions = sorted(incl["session"].unique())
    if max_sessions is not None:
        sessions = sessions[:max_sessions]

    edges_s = bin_edges_s()
    centers_ms = bin_centers_ms(edges_s)

    per_area_session_t0: dict = {}
    n_units_used = 0

    t0_start = time.time()
    for si, prefix in enumerate(sessions, start=1):
        sub = incl[incl["session"] == prefix]
        if len(sub) == 0:
            continue
        path = P.resolve_nwb_path(prefix)
        if not path.exists():
            print(f"  [{si}/{len(sessions)}] MISSING nwb for {prefix}, skipping")
            continue
        try:
            sess = oa.read(str(path))
        except Exception as e:
            print(f"  [{si}/{len(sessions)}] FAILED to load {prefix}: {e}")
            continue

        onsets = precompute_condition_onsets(sess, correct_only=True)
        omit_slot_onsets = pooled_event_onsets_s(onsets, omission_events())

        for area, grp in sub.groupby("area_pooled"):
            spike_lists = []
            for _, urow in grp.iterrows():
                sp = sess.get_spike_times(int(urow["unit_row"]))
                if sp is not None and len(sp) > 0:
                    spike_lists.append(sp)
            if len(spike_lists) < MIN_UNITS_PER_AREA_SESSION:
                continue
            fit = fit_area_onset(spike_lists, omit_slot_onsets, edges_s, centers_ms)
            n_units_used += len(spike_lists)
            if fit["converged"] and not np.isnan(fit["t0"]):
                per_area_session_t0.setdefault(area, {})[prefix] = {
                    "t0": fit["t0"], "n_units": len(spike_lists), "r2": fit["r2"],
                }

        print(f"  [{si}/{len(sessions)}] {prefix}: {sub['area_pooled'].nunique()} areas, "
              f"{time.time()-t0_start:.0f}s elapsed")

    area_results = {}
    for area, by_session in per_area_session_t0.items():
        vals = np.array([v["t0"] for v in by_session.values()])
        point, lo, hi = session_bootstrap_ci(vals)
        area_results[area] = {
            "point_t0_ms": point, "ci_lo_ms": lo, "ci_hi_ms": hi,
            "n_sessions": len(by_session), "session_ids": list(by_session.keys()),
            "t0_values_ms": vals.tolist(),
            "n_units_total": int(sum(v["n_units"] for v in by_session.values())),
        }

    areas_present = sorted(area_results.keys(), key=lambda a: figstyle.AREA_ORDER.index(a) if a in figstyle.AREA_ORDER else 99)
    pairwise = []
    for i, a in enumerate(areas_present):
        for b in areas_present[i + 1:]:
            va = np.array(area_results[a]["t0_values_ms"])
            vb = np.array(area_results[b]["t0_values_ms"])
            point, lo, hi, nd = pairwise_diff_ci(va, vb)
            pairwise.append({"area_a": a, "area_b": b, "diff_ms_a_minus_b": point,
                              "ci_lo": lo, "ci_hi": hi, "discriminating": not nd})

    return {
        "class_col": class_col, "quality_tier": quality_tier,
        "area_results": area_results, "areas_present": areas_present, "pairwise": pairwise,
        "n_sessions_processed": len(sessions), "n_units_used": n_units_used,
        "centers_ms": centers_ms,
    }


def build_stats(run_out: dict) -> dict:
    any_discriminating = any(p["discriminating"] for p in run_out["pairwise"])
    return {
        "id": "S5_onset_latency_hierarchy_spk",
        "spec_source": "context/analysis_spec_SPK.md SS5",
        "inclusion_source": str(INCLUSION_CSV),
        "class_col": run_out["class_col"], "quality_tier": run_out["quality_tier"],
        "fit_win_ms": list(FIT_WIN_MS), "baseline_win_ms": list(BASELINE_WIN_MS),
        "bin_ms": BIN_MS, "t0_bounds_ms": list(T0_BOUNDS_MS), "smooth_tau_ms": SMOOTH_TAU_MS,
        "smoothing": "causal (forward-only) exponential kernel, omission.jnwb_ext.onset_fitting.causal_exp_smooth -- "
                     "per spec: acausal smoothing manufactures spurious early onsets",
        "onset_fit": "omission.jnwb_ext.onset_fitting.fit_exponential_onset -- causality-bounded (t0 cannot leave "
                     "t0_bounds_ms regardless of data), grid-search-then-refine (see module docstring "
                     "for why a joint 4-parameter fit is unidentifiable on real PSTHs)",
        "ci_method": f"session-level bootstrap (n_boot={N_BOOT}, seed={SEED}, 95%% percentile) on "
                     "per-session fitted t0 -- degenerate when n_sessions<2, not fabricated",
        "n_sessions_processed": run_out["n_sessions_processed"], "n_units_used": run_out["n_units_used"],
        "area_results": {a: {k: v for k, v in r.items() if k != "t0_values_ms"} | {"t0_values_ms": r["t0_values_ms"]}
                          for a, r in run_out["area_results"].items()},
        "areas_present_hierarchy_order": run_out["areas_present"],
        "pairwise_onset_diff": run_out["pairwise"],
        "discriminating_any_pair": any_discriminating,
        "interpretation_note": "Per spec SS0.9 ('do not conclude'): reported here as quantities+CIs, "
                                "not a H1/H2/H3 verdict. If discriminating_any_pair is false, this is a "
                                "legitimate null result promoting CSD (LFP L4) to primary evidence, per "
                                "spec's own acceptance criterion -- not a failure of this analysis.",
        "git_sha": _git_sha(), "generated_at_utc": datetime.now(timezone.utc).isoformat(), "seed": SEED,
    }


def plot_figure(run_out: dict, out_path_stem: Path, title_suffix: str = ""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figstyle.use_house_style()
    areas = run_out["areas_present"]
    area_results = run_out["area_results"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2))

    ax = axes[0]
    y = np.arange(len(areas))
    points = [area_results[a]["point_t0_ms"] for a in areas]
    los = [area_results[a]["ci_lo_ms"] for a in areas]
    his = [area_results[a]["ci_hi_ms"] for a in areas]
    colors = [figstyle.AREA_COLORS.get(a, "#888888") for a in areas]
    for yi, (p, lo, hi, c) in enumerate(zip(points, los, his, colors)):
        ax.plot([lo, hi], [yi, yi], color=c, lw=2)
        ax.plot(p, yi, "o", color=c, markersize=6)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{a} (n_sess={area_results[a]['n_sessions']}, n={area_results[a]['n_units_total']})"
                         for a in areas], fontsize=7)
    ax.set_xlabel("fitted onset t0 (ms from omission-slot onset)", fontsize=9)
    ax.set_title("Onset latency by area (session-bootstrap 95%% CI)", fontsize=9)
    ax.axvline(0, color="gray", lw=0.5, ls=":")
    ax.invert_yaxis()

    ax2 = axes[1]
    n = len(areas)
    mat = np.full((n, n), np.nan)
    disc_mat = np.zeros((n, n), dtype=bool)
    for p in run_out["pairwise"]:
        i, j = areas.index(p["area_a"]), areas.index(p["area_b"])
        mat[i, j] = p["diff_ms_a_minus_b"]
        mat[j, i] = -p["diff_ms_a_minus_b"]
        disc_mat[i, j] = disc_mat[j, i] = p["discriminating"]
    im = ax2.imshow(mat, cmap="RdBu_r", vmin=-np.nanmax(np.abs(mat)) if np.any(~np.isnan(mat)) else -1,
                     vmax=np.nanmax(np.abs(mat)) if np.any(~np.isnan(mat)) else 1)
    for i in range(n):
        for j in range(n):
            if i != j and not np.isnan(mat[i, j]) and not disc_mat[i, j]:
                ax2.text(j, i, "ns", ha="center", va="center", fontsize=6, color="gray")
    ax2.set_xticks(range(n)); ax2.set_xticklabels(areas, rotation=90, fontsize=7)
    ax2.set_yticks(range(n)); ax2.set_yticklabels(areas, fontsize=7)
    ax2.set_title("Pairwise onset diff (ms, row-col); 'ns' = CI crosses 0", fontsize=9)
    fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)

    fig.suptitle(f"S5: cross-area spiking onset latency{title_suffix} "
                 f"(class={run_out['class_col']}, quality={run_out['quality_tier']})", fontsize=10, y=0.98)
    fig.subplots_adjust(top=0.85, bottom=0.28, wspace=0.35)
    figstyle.save(fig, out_path_stem.parent, out_path_stem.name)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _synthetic_area_spike_trains(t0_ms: float, tau_ms: float, amp_hz: float, base_hz: float,
                                  n_trials: int, n_units: int, seed: int) -> list:
    from omission.jnwb_ext.onset_fitting import onset_model
    rng = np.random.default_rng(seed)
    trial_onsets = np.arange(n_trials) * 6.0
    win0_s, win1_s = FIT_WIN_MS[0] / 1000.0, FIT_WIN_MS[1] / 1000.0
    spike_lists = []
    for u in range(n_units):
        spikes = []
        for t0 in trial_onsets:
            n_pts = 400
            t_fine = np.linspace(win0_s * 1000, win1_s * 1000, n_pts)
            rate_fine = onset_model(t_fine, t0_ms, tau_ms, amp_hz, base_hz)
            rate_fine = np.clip(rate_fine, 0, None)
            for ti in range(n_pts - 1):
                dt = (t_fine[ti + 1] - t_fine[ti]) / 1000.0
                lam = rate_fine[ti] * dt
                n_sp = rng.poisson(lam)
                if n_sp > 0:
                    st = t_fine[ti] / 1000.0 + rng.random(n_sp) * dt
                    spikes.append(t0 + st)
        spike_lists.append(np.sort(np.concatenate(spikes)) if spikes else np.array([]))
    return spike_lists, trial_onsets


def test_known_lag_recovered():
    """Two synthetic areas with distinct injected onset latencies (50ms vs 250ms) must be
    recovered within tolerance, and the pairwise diff must correctly discriminate them."""
    edges_s = bin_edges_s()
    centers_ms = bin_centers_ms(edges_s)

    area_a_spikes, onsets_a = _synthetic_area_spike_trains(
        t0_ms=50.0, tau_ms=25.0, amp_hz=25.0, base_hz=5.0, n_trials=80, n_units=6, seed=1)
    area_b_spikes, onsets_b = _synthetic_area_spike_trains(
        t0_ms=250.0, tau_ms=25.0, amp_hz=25.0, base_hz=5.0, n_trials=80, n_units=6, seed=2)

    slot_onsets_a = onsets_a  # trial onset IS the slot onset in this synthetic construction
    slot_onsets_b = onsets_b

    fit_a = fit_area_onset(area_a_spikes, slot_onsets_a, edges_s, centers_ms)
    fit_b = fit_area_onset(area_b_spikes, slot_onsets_b, edges_s, centers_ms)

    assert fit_a["converged"] and fit_b["converged"]
    err_a = abs(fit_a["t0"] - 50.0)
    err_b = abs(fit_b["t0"] - 250.0)
    assert err_a < 60.0, f"area A onset recovery error {err_a:.1f}ms too large (fit={fit_a['t0']:.1f})"
    assert err_b < 60.0, f"area B onset recovery error {err_b:.1f}ms too large (fit={fit_b['t0']:.1f})"
    assert fit_b["t0"] > fit_a["t0"], "area B (true later onset) must fit later than area A"
    print(f"PASS: known-lag recovery (A true=50 fit={fit_a['t0']:.1f}, B true=250 fit={fit_b['t0']:.1f})")


def test_zero_lag_not_discriminating():
    """Two areas with the SAME true onset, across several synthetic 'sessions', must produce a
    pairwise CI that crosses zero -> discriminating:false, per the spec's own required test."""
    edges_s = bin_edges_s()
    centers_ms = bin_centers_ms(edges_s)
    vals_a, vals_b = [], []
    for seed_offset in range(4):
        sp_a, on_a = _synthetic_area_spike_trains(
            t0_ms=100.0, tau_ms=25.0, amp_hz=20.0, base_hz=5.0, n_trials=50, n_units=4, seed=10 + seed_offset)
        sp_b, on_b = _synthetic_area_spike_trains(
            t0_ms=100.0, tau_ms=25.0, amp_hz=20.0, base_hz=5.0, n_trials=50, n_units=4, seed=20 + seed_offset)
        fit_a = fit_area_onset(sp_a, on_a, edges_s, centers_ms)
        fit_b = fit_area_onset(sp_b, on_b, edges_s, centers_ms)
        if fit_a["converged"]:
            vals_a.append(fit_a["t0"])
        if fit_b["converged"]:
            vals_b.append(fit_b["t0"])

    point, lo, hi, non_disc = pairwise_diff_ci(np.array(vals_a), np.array(vals_b))
    assert non_disc, f"zero-lag synthetic case must return non-discriminating, got CI=[{lo:.1f},{hi:.1f}]"
    print(f"PASS: zero-lag synthetic case correctly non-discriminating (diff={point:.1f}, CI=[{lo:.1f},{hi:.1f}])")


def test_session_bootstrap_ci_degenerate_below_two():
    point, lo, hi = session_bootstrap_ci(np.array([42.0]))
    assert point == lo == hi == 42.0
    point2, lo2, hi2 = session_bootstrap_ci(np.array([10.0, 20.0, 30.0, 40.0]))
    assert lo2 <= point2 <= hi2 and (lo2 < point2 or hi2 > point2)
    print("PASS: session bootstrap CI degenerate at n<2, real spread at n>=2")


def test_pairwise_diff_ci_degenerate_below_two():
    point, lo, hi, nd = pairwise_diff_ci(np.array([50.0]), np.array([100.0]))
    assert point == lo == hi == -50.0
    assert nd is True, "degenerate (n<2) case must be treated as non-discriminating, not fabricated significance"
    print("PASS: pairwise diff CI degenerate + non-discriminating at n<2")


def test_determinism():
    edges_s = bin_edges_s()
    centers_ms = bin_centers_ms(edges_s)
    sp, on = _synthetic_area_spike_trains(t0_ms=80.0, tau_ms=25.0, amp_hz=20.0, base_hz=5.0,
                                           n_trials=40, n_units=3, seed=99)
    fit1 = fit_area_onset(sp, on, edges_s, centers_ms)
    fit2 = fit_area_onset(sp, on, edges_s, centers_ms)
    assert fit1["t0"] == fit2["t0"] and fit1["tau"] == fit2["tau"], "identical input must give identical fit"
    print("PASS: determinism (fit is a pure function of its input trace)")


def run_self_tests():
    test_known_lag_recovered()
    test_zero_lag_not_discriminating()
    test_session_bootstrap_ci_degenerate_below_two()
    test_pairwise_diff_ci_degenerate_below_two()
    test_determinism()
    print("\nAll S5 self-tests PASSED")


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
        manifest = {
            "method": "S5_onset_latency_hierarchy_spk", "git_sha": _git_sha(),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "inputs": {"inclusion_csv": str(INCLUSION_CSV), "readiness_csv": str(READINESS_CSV)},
            "n_sessions": run_out["n_sessions_processed"], "n_units_used": run_out["n_units_used"],
            "seed": SEED, "n_boot": N_BOOT,
        }
        (OUT_DIR / "S5_stats.json").write_text(json.dumps(stats, indent=2))
        (OUT_DIR / "S5_manifest.json").write_text(json.dumps(manifest, indent=2))
        plot_figure(run_out, OUT_DIR / "S5")
        print(f"\nDone. n_sessions={run_out['n_sessions_processed']} n_units_used={run_out['n_units_used']} "
              f"discriminating_any_pair={stats['discriminating_any_pair']}")
