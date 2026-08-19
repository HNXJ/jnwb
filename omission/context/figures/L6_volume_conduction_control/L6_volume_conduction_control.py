r"""
L6 -- Volume conduction control: how much cross-area LFP coupling survives re-referencing and
removal of zero-lag components. Required to interpret L5 (see L5_stats.json/README: every band
returned H3_simultaneous_or_ambiguous, which the spec's own text says cannot be told apart from
"shared conducted field" without this analysis).

METHOD (per spec)
    (a) Bipolar/Laplacian re-referencing -- computed via omission.jnwb_ext.spectral.laplacian_reference
        (already validated as this project's CSD/re-referencing estimator, L0 method (d) and
        L4's whole pipeline). Applied to a small channel block (N_CH_BLOCK=5) around a
        representative channel per area BEFORE coherence is computed, per
        imaginary_coherency's own docstring ("callers are responsible for re-referencing...
        before calling this").
    (b) Removing zero-lag components -- omission.jnwb_ext.spectral.imaginary_coherency itself: its own
        docstring identifies it as "the estimator this project's fig06/fig07 volume-conduction
        control requires" (Im(coherency) is insensitive to zero-lag mixing by construction).
    Both (a) and (b) are applied together (CSD-referenced signals fed to imaginary coherency)
    AND separately (raw vs CSD comparison at fixed icoh; icoh vs coh_mag at fixed referencing)
    so the two contributions are not conflated.

COMPARISON DESIGN
    Within-probe vs across-probe area pairs, per spec. Probe assignment is resolved FRESH per
    session (never assumed fixed -- see omission-data skill and _l_lfp_common.find_probe_for_area
    docstring) so "within-probe" is a measured property of a given session for a given pair, not
    a hardcoded label on the pair itself. Area pairs surveyed: (V1,V2) -- share a probe on
    V198o; (MT,MST) -- share a probe on several C31o sessions; (FEF,PFC) -- always different
    probes in this corpus; (V1,MT) -- always different probes, different subject pools too, as
    an additional across-probe reference point.

DERIVED INDEX (stated as an informal index, not a formal variance decomposition)
    lagged_fraction = clip(icoh_abs_mean / sqrt(coh_mag_mean), 0, 1)   [since |Im(coherency)| <=
    |coherency| = sqrt(coh_mag) pointwise, this ratio is bounded in [0,1] in expectation, though
    per-band-average clipping is applied defensively for finite-sample noise]
    zero_lag_fraction = 1 - lagged_fraction
    This operationalizes the "large gap between coh_mag_mean and icoh indicates zero-lag-
    dominated mixing" comparison imaginary_coherency's own docstring already describes -- it is
    not a new estimator, just a scalar summary of that same comparison.

SCOPE (stated, not hidden)
    Stim condition (RRRR) only, broadband 4-80 Hz (this analysis is about volume conduction in
    general, not band-specific coupling -- band-resolved icoh is a stated, not-yet-built
    extension). Representative single channel per area (middle of a 5-channel block used for
    Laplacian referencing) -- NOT full-area coverage; a channel-resolved version is a stated
    extension. Up to 3 sessions per area pair (tractability cap), all subjects pooled per pair
    (too few sessions per pair for a per-subject breakdown to be meaningful).

DO NOT CONCLUDE: this script reports zero-lag vs lagged coupling FRACTIONS per area pair and
per referencing scheme. It does not itself decide whether L5's H3 verdicts reflect genuine
simultaneous engagement or volume conduction -- that reading is left to the manuscript text,
against this quantity.

OUTPUT
    L6.svg / L6.png / L6.pdf, L6_stats.json, L6_manifest.json.

TESTS
    --test: (a) a purely zero-lag shared source must give high coh_mag, low icoh_abs, HIGH
    zero_lag_fraction; a genuinely lagged shared source must give high coh_mag AND meaningfully
    higher icoh_abs, LOWER zero_lag_fraction than (a); independent noise must give low coh_mag
    for both. (b) Laplacian re-referencing must reduce coh_mag_mean for a common-average-
    reference-only artifact (no real coupling) relative to the raw-referenced signals.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "archive_oneoff"))
sys.path.insert(0, str(REPO / "context" / "figures"))

from _l_lfp_common import (  # noqa: E402
    extract_epoch_trials, find_probe_for_area, git_sha, resolve_area_channel_block,
)
from omission.jnwb_ext.spectral import imaginary_coherency, laplacian_reference  # noqa: E402
import figstyle  # noqa: E402

FIG_DIR = Path(__file__).resolve().parent
L0_STATS = REPO / "context" / "figures" / "L0_pooling_reconciliation" / "L0_stats.json"

SEED = 42
EPOCH_WIN_S = (-0.6, 2.2)
MAX_TRIALS = 40
N_CH_BLOCK = 5
MAX_SESSIONS_PER_PAIR = 3
FREQ_RANGE_HZ = (4.0, 80.0)
CONDITION_CODE = "RRRR"  # stim only, see module docstring SCOPE

AREA_PAIRS = [("V1", "V2"), ("MT", "MST"), ("FEF", "PFC"), ("V1", "MT")]


def require_l0_canonical_method() -> str:
    if not L0_STATS.is_file():
        raise RuntimeError(f"L0 has not been run ({L0_STATS} missing) -- run L0 first.")
    stats = json.loads(L0_STATS.read_text())
    method = stats.get("canonical_pooling_method")
    if method != "a_per_channel_then_pool":
        raise RuntimeError(f"L0_stats.json canonical_pooling_method={method!r} unexpected.")
    return method


def lagged_and_zero_lag_fraction(icoh: dict) -> tuple[float, float]:
    lagged = 0.0
    if icoh["coh_mag_mean"] > 1e-12:
        lagged = float(np.clip(icoh["icoh_abs_mean"] / np.sqrt(icoh["coh_mag_mean"]), 0.0, 1.0))
    return lagged, 1.0 - lagged


def sessions_for_pair(area_a: str, area_b: str, cap=MAX_SESSIONS_PER_PAIR):
    """(session_prefix, subject, probe_a, probe_b, same_probe) for every ready session carrying
    BOTH areas. Probe letters resolved fresh per session -- see module docstring."""
    import jnwb.paths as P
    import pandas as pd
    readiness = pd.read_csv(REPO / "artifacts" / "data" / "session_readiness.csv")
    prefixes = readiness.loc[readiness.nwb_ok, "session_prefix"].tolist()
    nwb_dir = Path(P.nwb_dir())
    out = []
    for prefix in prefixes:
        if len(out) >= cap:
            break
        cand = list(nwb_dir.glob(prefix + "*.nwb"))
        if not cand:
            continue
        subject = prefix.split("_")[0].replace("sub-", "")
        try:
            with h5py.File(cand[0], "r") as f:
                pa = find_probe_for_area(f, area_a)
                pb = find_probe_for_area(f, area_b)
        except Exception:
            continue
        if pa is None or pb is None:
            continue
        out.append((prefix, subject, pa, pb, pa == pb))
    return out


def extract_representative_channel(nwb_path: Path, probe_letter: str, area: str,
                                    condition_code: str):
    """Returns (raw_1d, csd_1d, fs, n_trials, frac_repaired) -- middle channel of an
    N_CH_BLOCK-wide block, raw and Laplacian-referenced, trials concatenated along time
    (same convention extract_lfp_coupling_matrices.py already uses for this corpus). Repair
    (artifact interpolation) is applied inside extract_epoch_trials (repair=True default)."""
    with h5py.File(nwb_path, "r") as f:
        lfp_key, lo, hi = resolve_area_channel_block(f, probe_letter, area, N_CH_BLOCK)
        trials, fs, n_trials, frac_repaired = extract_epoch_trials(
            f, lfp_key, lo, hi, condition_code, EPOCH_WIN_S, MAX_TRIALS)
    mid = trials.shape[1] // 2
    raw_1d = trials[:, mid, :].reshape(-1)
    csd_trials = np.stack([laplacian_reference(trials[t]) for t in range(trials.shape[0])])
    csd_1d = csd_trials[:, mid, :].reshape(-1)
    return raw_1d, csd_1d, fs, n_trials, frac_repaired


def run():
    require_l0_canonical_method()
    import jnwb.paths as P
    nwb_dir = Path(P.nwb_dir())

    stats = {
        "canonical_pooling_method": "a_per_channel_then_pool",
        "l0_source": str(L0_STATS),
        "method": "imaginary_coherency (Nolte et al. 2004) on raw-referenced and Laplacian-"
                  "referenced representative channels, per area pair per session. "
                  "zero_lag_fraction = 1 - clip(icoh_abs_mean/sqrt(coh_mag_mean), 0, 1), an "
                  "informal scalar summary of imaginary_coherency's own documented "
                  "coh_mag-vs-icoh comparison -- see module docstring.",
        "freq_range_hz": list(FREQ_RANGE_HZ), "condition": "stim (RRRR)",
        "epoch_window_s": list(EPOCH_WIN_S), "max_trials_per_session": MAX_TRIALS,
        "n_channel_block": N_CH_BLOCK, "max_sessions_per_pair": MAX_SESSIONS_PER_PAIR,
        "pairs": {},
    }
    manifest = {
        "analysis_id": "L6", "git_sha": git_sha(), "seed": SEED,
        "freq_range_hz": list(FREQ_RANGE_HZ), "epoch_window_s": list(EPOCH_WIN_S),
        "max_trials_per_session": MAX_TRIALS, "n_channel_block": N_CH_BLOCK,
        "sessions_used": {},
    }

    pair_results = {}
    for area_a, area_b in AREA_PAIRS:
        sessions = sessions_for_pair(area_a, area_b)
        pair_key = f"{area_a}-{area_b}"
        manifest["sessions_used"][pair_key] = [
            {"session": s, "subject": subj, "probe_a": pa, "probe_b": pb, "same_probe": bool(sp)}
            for s, subj, pa, pb, sp in sessions]
        if not sessions:
            continue
        rows = []
        for session_prefix, subject, probe_a, probe_b, same_probe in sessions:
            nwb_path = nwb_dir / f"{session_prefix}_rec.nwb"
            if not nwb_path.is_file():
                nwb_path = nwb_dir / f"{session_prefix}.nwb"
            try:
                raw_a, csd_a, fs, na, fra = extract_representative_channel(
                    nwb_path, probe_a, area_a, CONDITION_CODE)
                raw_b, csd_b, fs2, nb, frb = extract_representative_channel(
                    nwb_path, probe_b, area_b, CONDITION_CODE)
            except Exception as e:
                print(f"  SKIP {pair_key} {session_prefix}: {e}")
                continue
            n = min(len(raw_a), len(raw_b))
            icoh_raw = imaginary_coherency(raw_a[:n], raw_b[:n], fs, FREQ_RANGE_HZ)
            icoh_csd = imaginary_coherency(csd_a[:n], csd_b[:n], fs, FREQ_RANGE_HZ)
            lag_raw, zl_raw = lagged_and_zero_lag_fraction(icoh_raw)
            lag_csd, zl_csd = lagged_and_zero_lag_fraction(icoh_csd)
            rows.append({
                "session": session_prefix, "subject": subject, "probe_a": probe_a,
                "probe_b": probe_b, "same_probe": bool(same_probe),
                "n_trials_a": na, "n_trials_b": nb,
                "raw": {**icoh_raw, "lagged_fraction": lag_raw, "zero_lag_fraction": zl_raw},
                "csd": {**icoh_csd, "lagged_fraction": lag_csd, "zero_lag_fraction": zl_csd},
            })
        if not rows:
            continue
        pair_results[pair_key] = rows
        stats["pairs"][pair_key] = {
            "area_a": area_a, "area_b": area_b, "n_sessions": len(rows),
            "sessions": rows,
            "mean_zero_lag_fraction_raw": float(np.mean([r["raw"]["zero_lag_fraction"] for r in rows])),
            "mean_zero_lag_fraction_csd": float(np.mean([r["csd"]["zero_lag_fraction"] for r in rows])),
            "mean_coh_mag_raw": float(np.mean([r["raw"]["coh_mag_mean"] for r in rows])),
            "mean_coh_mag_csd": float(np.mean([r["csd"]["coh_mag_mean"] for r in rows])),
            "any_same_probe": bool(any(r["same_probe"] for r in rows)),
            "any_diff_probe": bool(any(not r["same_probe"] for r in rows)),
        }

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "L6_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    (FIG_DIR / "L6_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    plot_summary(pair_results)
    return stats


def plot_summary(pair_results: dict):
    figstyle.use_house_style()
    pair_keys = list(pair_results.keys())
    if not pair_keys:
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.text(0.5, 0.5, "no pairs with usable sessions", ha="center", va="center")
        figstyle.save(fig, FIG_DIR, "L6")
        fig.savefig(FIG_DIR / "L6.pdf", bbox_inches="tight")
        plt.close(fig)
        return

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    ax_zl, ax_coh = axes

    x = np.arange(len(pair_keys))
    width = 0.35
    for offset, ref, color in [(-width / 2, "raw", "#B35806"), (width / 2, "csd", "#1B7837")]:
        zl_means = [np.mean([r[ref]["zero_lag_fraction"] for r in pair_results[k]]) for k in pair_keys]
        coh_means = [np.mean([r[ref]["coh_mag_mean"] for r in pair_results[k]]) for k in pair_keys]
        ax_zl.bar(x + offset, zl_means, width=width, color=color, label=ref)
        ax_coh.bar(x + offset, coh_means, width=width, color=color, label=ref)

    for ax, ylabel, title in [(ax_zl, "zero-lag fraction", "Zero-lag coupling fraction"),
                               (ax_coh, "coh_mag_mean", "Total (magnitude-sq) coherence")]:
        ax.set_xticks(x)
        labels = []
        for k in pair_keys:
            rows = pair_results[k]
            tag = "within-probe" if all(r["same_probe"] for r in rows) else (
                "across-probe" if not any(r["same_probe"] for r in rows) else "mixed")
            labels.append(f"{k}\n({tag})")
        ax.set_xticklabels(labels, fontsize=7)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.set_title(title, fontsize=9)
        ax.legend(fontsize=7)
        ax.tick_params(labelsize=7)

    fig.suptitle("L6: volume conduction control -- raw vs Laplacian-referenced imaginary "
                 "coherency, within- vs across-probe area pairs, stim condition, "
                 f"{FREQ_RANGE_HZ[0]:.0f}-{FREQ_RANGE_HZ[1]:.0f} Hz. Do not conclude in-code.",
                 fontsize=8.5, y=1.03)
    fig.tight_layout()
    figstyle.save(fig, FIG_DIR, "L6")
    fig.savefig(FIG_DIR / "L6.pdf", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------------------- self-test --

def run_synthetic_selftest():
    rng = np.random.default_rng(SEED)
    fs = 1000.0
    n = 60_000  # 60s equivalent, plenty of Welch segments at nperseg=1024

    shared = rng.normal(0, 1.0, n)
    shared = np.convolve(shared, np.ones(5) / 5, mode="same")  # broadband-ish common source
    noise_a = rng.normal(0, 0.3, n)
    noise_b = rng.normal(0, 0.3, n)
    indep_a = rng.normal(0, 1.0, n)
    indep_b = rng.normal(0, 1.0, n)

    # (a) purely zero-lag shared source.
    sig_a_zl = shared + noise_a
    sig_b_zl = shared + noise_b
    icoh_zl = imaginary_coherency(sig_a_zl, sig_b_zl, fs, FREQ_RANGE_HZ)
    lag_zl, zlfrac_zl = lagged_and_zero_lag_fraction(icoh_zl)

    # (b) genuinely lagged shared source (20-sample / 20ms delay).
    delay = 20
    sig_a_lag = shared + noise_a
    sig_b_lag = np.roll(shared, delay) + noise_b
    icoh_lag = imaginary_coherency(sig_a_lag[delay:], sig_b_lag[delay:], fs, FREQ_RANGE_HZ)
    lag_lag, zlfrac_lag = lagged_and_zero_lag_fraction(icoh_lag)

    # (c) independent noise, no shared source at all.
    icoh_indep = imaginary_coherency(indep_a, indep_b, fs, FREQ_RANGE_HZ)

    print(f"(a) zero-lag:  coh_mag={icoh_zl['coh_mag_mean']:.3f} icoh_abs={icoh_zl['icoh_abs_mean']:.4f} "
          f"zero_lag_fraction={zlfrac_zl:.3f}")
    print(f"(b) lagged:    coh_mag={icoh_lag['coh_mag_mean']:.3f} icoh_abs={icoh_lag['icoh_abs_mean']:.4f} "
          f"zero_lag_fraction={zlfrac_lag:.3f}")
    print(f"(c) independent: coh_mag={icoh_indep['coh_mag_mean']:.3f} icoh_abs={icoh_indep['icoh_abs_mean']:.4f}")

    assert icoh_zl["coh_mag_mean"] > 0.3, "zero-lag case should show substantial total coherence"
    assert zlfrac_zl > 0.75, f"zero-lag case should have high zero_lag_fraction, got {zlfrac_zl:.3f}"
    assert icoh_lag["coh_mag_mean"] > 0.3, "lagged case should also show substantial total coherence"
    assert zlfrac_lag < zlfrac_zl - 0.15, (
        f"lagged case zero_lag_fraction ({zlfrac_lag:.3f}) should be meaningfully lower than "
        f"zero-lag case ({zlfrac_zl:.3f}) -- icoh is not discriminating lag as required")
    assert icoh_indep["coh_mag_mean"] < 0.15, "independent noise should show low total coherence"
    print("PASS: imaginary coherency discriminates zero-lag vs genuinely-lagged shared sources.")

    # (d) Laplacian re-referencing must reduce coh_mag driven purely by a common-average
    # reference artifact (no real per-channel coupling beyond the shared CAR term).
    n_ch = N_CH_BLOCK
    car = rng.normal(0, 1.5, n)
    block_a = np.stack([car + rng.normal(0, 0.4, n) for _ in range(n_ch)])
    block_b = np.stack([car + rng.normal(0, 0.4, n) for _ in range(n_ch)])
    mid = n_ch // 2
    raw_a, raw_b = block_a[mid], block_b[mid]
    csd_a = laplacian_reference(block_a)[mid]
    csd_b = laplacian_reference(block_b)[mid]
    icoh_raw_car = imaginary_coherency(raw_a, raw_b, fs, FREQ_RANGE_HZ)
    icoh_csd_car = imaginary_coherency(csd_a, csd_b, fs, FREQ_RANGE_HZ)
    print(f"(d) CAR artifact: coh_mag raw={icoh_raw_car['coh_mag_mean']:.3f} "
          f"csd={icoh_csd_car['coh_mag_mean']:.3f}")
    assert icoh_raw_car["coh_mag_mean"] > icoh_csd_car["coh_mag_mean"] + 0.05, (
        "Laplacian re-referencing should reduce coh_mag_mean for a shared-CAR-only artifact")
    print("PASS: Laplacian re-referencing reduces common-reference-driven coherence.")

    # Determinism (no RNG inside imaginary_coherency/laplacian_reference themselves).
    icoh_zl_2 = imaginary_coherency(sig_a_zl, sig_b_zl, fs, FREQ_RANGE_HZ)
    assert icoh_zl_2 == icoh_zl, "determinism check failed"
    print("PASS: determinism check.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        run_synthetic_selftest()
        return
    stats = run()
    for pair_key, p in stats["pairs"].items():
        print(f"{pair_key}: n_sessions={p['n_sessions']} "
              f"zero_lag_fraction raw={p['mean_zero_lag_fraction_raw']:.3f} "
              f"csd={p['mean_zero_lag_fraction_csd']:.3f} "
              f"(same_probe seen={p['any_same_probe']}, diff_probe seen={p['any_diff_probe']})")


if __name__ == "__main__":
    main()
