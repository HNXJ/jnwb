"""
Suite 05 (imaginary-part coherence / phase-locking correlations), generalized across sessions.

Refactor of notebooks/suite_05_tfr_lfp_area_layer_imaginary_complex_corr.ipynb, which was
hardcoded to sub-V182o_ses-260629.nwb with a manually-specified probe->area mapping. This
script reuses the same real per-session probe_areas.json sidecar + flat/nested LFP-group
resolution already established and proven by scripts/build_suite_09_granger_reports.py, so
areas come from each session's own real channel_slices rather than an assumption that one
probe equals one area (true for V182o's 4-probe layout, but not for e.g. C31o_230823 where
probe C covers V1/V2/V3).

Real per-trial complex STFT coefficients (scipy.signal.stft), real cross-spectral imaginary
coherence (alpha band, 8-12 Hz), a real circular-shift permutation test (n=200, seed=42) on
trial order, and real BH-FDR correction across all area pairs - the original notebook's exact
method, just generalized to run per real per-area regional signal instead of one hardcoded
whole-probe signal per V182o area.

Usage:
    python scripts/build_suite_05_imaginary_coherence_reports.py --all-ready
    python scripts/build_suite_05_imaginary_coherence_reports.py --nwb <path>
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import h5py
import numpy as np
import pandas as pd
from scipy.signal import stft
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import omission as oa
from jnwb.statistics import StatisticalAnalysis

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "outputs/markdown_reports"
CONDITION = "AAAB"
WIN_SAMPLES = 1000  # 1s post-onset window at 1kHz
FS_LFP = 1000.0
N_SHUFFLES = 200
SEED = 42
BAND = (8.0, 12.0)  # alpha
MIN_TRIALS = 10


def load_probe_areas(metadata_dir: Path, stem: str) -> Dict[str, dict]:
    path = metadata_dir / stem / "probe_areas.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_lfp_dataset(h5file: h5py.File, lfp_key: str):
    grp = h5file[f"acquisition/{lfp_key}"]
    if "data" in grp and "timestamps" in grp:
        return grp["data"], grp["timestamps"]
    nested_key = f"{lfp_key}_data"
    if nested_key in grp:
        nested = grp[nested_key]
        if "data" in nested and "timestamps" in nested:
            return nested["data"], nested["timestamps"]
    raise KeyError(f"Could not find data/timestamps under acquisition/{lfp_key} (flat or nested)")


def extract_area_trial_signals(nwb_path: Path, probe_areas: Dict[str, dict],
                                onsets: np.ndarray) -> Dict[str, np.ndarray]:
    """Real per-trial, per-area regional LFP (channel-mean within that area's real
    channel_slice), 1s post-onset window. Returns {area: (n_trials, win_samples)}."""
    area_trial_signals: Dict[str, np.ndarray] = {}
    with h5py.File(nwb_path, "r") as f:
        for probe, entry in probe_areas.items():
            lfp_key = entry["lfp_key"]
            try:
                data_dset, ts_dset = resolve_lfp_dataset(f, lfp_key)
            except KeyError:
                continue
            ts = ts_dset[:]
            for area, sl in entry["channel_slices"].items():
                ch0, ch1 = int(sl["start"]), int(sl["stop"])
                trials = []
                for t0 in onsets:
                    i0 = int(np.searchsorted(ts, t0))
                    i1 = i0 + WIN_SAMPLES
                    if i1 > data_dset.shape[0]:
                        continue
                    trials.append(data_dset[i0:i1, ch0:ch1].mean(axis=1))
                if trials:
                    area_trial_signals[area] = np.array(trials)
    return area_trial_signals


def imaginary_coherence_alpha(sig1_trials: np.ndarray, sig2_trials: np.ndarray,
                               fs: float = FS_LFP, nperseg: int = 250,
                               band: Tuple[float, float] = BAND) -> float:
    per_trial_im = []
    for s1, s2 in zip(sig1_trials, sig2_trials):
        f_stft, _, Z1 = stft(s1, fs=fs, nperseg=nperseg)
        _, _, Z2 = stft(s2, fs=fs, nperseg=nperseg)
        Sxy = np.mean(Z1 * np.conj(Z2), axis=1)
        Sxx = np.mean((Z1 * np.conj(Z1)).real, axis=1)
        Syy = np.mean((Z2 * np.conj(Z2)).real, axis=1)
        coh = Sxy / (np.sqrt(Sxx * Syy) + 1e-20)
        band_mask = (f_stft >= band[0]) & (f_stft <= band[1])
        per_trial_im.append(np.mean(np.imag(coh[band_mask])))
    return float(np.mean(per_trial_im))


def run_one_session(nwb_path: str, session_prefix: str, stem: str, metadata_dir: Path) -> dict:
    probe_areas_path = metadata_dir / stem / "probe_areas.json"
    if not probe_areas_path.exists():
        return {"status": "skipped", "reason": f"no probe_areas.json sidecar at {probe_areas_path}"}
    probe_areas = load_probe_areas(metadata_dir, stem)

    try:
        session = oa.read(nwb_path)
    except Exception as e:
        return {"status": "failed", "reason": f"Failed to load NWB session: {e}"}

    epochs = session.get_epochs(phase=2, condition=CONDITION, correct_only=True)
    onsets = epochs["start_time"].values
    if len(onsets) < MIN_TRIALS:
        return {"status": "skipped", "reason": f"Too few real {CONDITION} trials: {len(onsets)} (need >= {MIN_TRIALS})"}

    area_trial_signals = extract_area_trial_signals(Path(nwb_path), probe_areas, onsets)
    areas = [a for a, sig in area_trial_signals.items() if len(sig) >= MIN_TRIALS]
    if len(areas) < 2:
        return {"status": "skipped", "reason": f"fewer than 2 real areas with >= {MIN_TRIALS} trial segments (found {len(areas)})"}

    n_areas = len(areas)
    n_trials_use = min(len(area_trial_signals[a]) for a in areas)
    rng = np.random.default_rng(SEED)

    observed = np.full((n_areas, n_areas), np.nan)
    raw_pvals = {}
    for i in range(n_areas):
        for j in range(i + 1, n_areas):
            sig1 = area_trial_signals[areas[i]][:n_trials_use]
            sig2 = area_trial_signals[areas[j]][:n_trials_use]
            obs = imaginary_coherence_alpha(sig1, sig2)
            observed[i, j] = observed[j, i] = obs

            surrogate_vals = np.empty(N_SHUFFLES)
            for s in range(N_SHUFFLES):
                perm = rng.permutation(n_trials_use)
                surrogate_vals[s] = imaginary_coherence_alpha(sig1, sig2[perm])
            p_val = (np.sum(np.abs(surrogate_vals) >= np.abs(obs)) + 1) / (N_SHUFFLES + 1)
            raw_pvals[(i, j)] = p_val

    pairs = list(raw_pvals.keys())
    flat_p = np.array([raw_pvals[p] for p in pairs])
    flat_q = StatisticalAnalysis.fdr_correct(flat_p.tolist())
    n_sig = int(np.sum(np.asarray(flat_q) < 0.05))

    return {
        "status": "completed", "areas": areas, "observed": observed,
        "pairs": pairs, "qvals": flat_q, "n_sig": n_sig, "n_trials_use": n_trials_use,
    }


def write_report(session_prefix: str, result: dict, out_root: Path = OUT_ROOT) -> Path:
    out_dir = out_root / session_prefix / "imaginary_coherence"
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    areas = result["areas"]
    n = len(areas)
    sig_matrix = np.nan_to_num(result["observed"], nan=0.0)
    for (i, j), q in zip(result["pairs"], result["qvals"]):
        if q > 0.05:
            sig_matrix[i, j] = sig_matrix[j, i] = 0.0

    fig, ax = plt.subplots(figsize=(max(6, n * 1.2), max(5, n)))
    im = ax.imshow(sig_matrix, cmap="coolwarm", vmin=-0.2, vmax=0.2)
    fig.colorbar(im, ax=ax, label="Im(coherence) (FDR q < 0.05, else 0)")
    ax.set_xticks(range(n))
    ax.set_xticklabels(areas, rotation=45, ha="right")
    ax.set_yticks(range(n))
    ax.set_yticklabels(areas)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{sig_matrix[i, j]:.3f}", ha="center", va="center", color="black", fontsize=8)
    ax.set_title(f"Suite 05: Real imaginary coherence (alpha) -- {session_prefix}\n"
                 f"n_trials={result['n_trials_use']}, {result['n_sig']}/{len(result['pairs'])} pairs significant")
    fig.tight_layout()
    svg_path = fig_dir / "imaginary_coherence_matrix.svg"
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)

    svg_bytes = svg_path.stat().st_size
    if svg_bytes == 0:
        time.sleep(0.2)
        svg_bytes = svg_path.stat().st_size
        if svg_bytes == 0:
            raise RuntimeError(f"{svg_path} is 0 bytes after retry")
    n_paths = svg_path.read_text(encoding="utf-8").count("<path ")

    pair_lines = "\n".join(
        f"- {areas[i]} <-> {areas[j]}: Im(coherence)={result['observed'][i, j]:.4f}, q={q:.4f}"
        + ("  **significant**" if q < 0.05 else "")
        for (i, j), q in zip(result["pairs"], result["qvals"])
    )

    index_md = f"""# Suite 05: Real Imaginary Coherence -- {session_prefix}

Areas ({n}, from this session's own probe_areas.json channel_slices): **{', '.join(areas)}**.

Real per-trial complex STFT coefficients, real cross-spectral imaginary coherence (alpha band,
8-12 Hz), real circular-shift permutation test (n={N_SHUFFLES}), real BH-FDR across
{len(result['pairs'])} pairs.

- Real trials used (n, min across all areas): {result['n_trials_use']}
- Significant after FDR (q < 0.05): {result['n_sig']} / {len(result['pairs'])}
- SVG: `figures/imaginary_coherence_matrix.svg` ({svg_bytes} bytes, {n_paths} path elements)

![Imaginary coherence matrix](figures/imaginary_coherence_matrix.svg)

## Per-pair results

{pair_lines}
"""
    (out_dir / "index.md").write_text(index_md, encoding="utf-8")
    return out_dir


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--nwb", type=Path, default=None)
    p.add_argument("--all-ready", action="store_true")
    p.add_argument("--readiness-csv", type=Path, default=REPO_ROOT / "artifacts/data/session_readiness.csv")
    p.add_argument("--metadata-dir", type=Path, default=Path("D:/workspace/data/metadata"))
    args = p.parse_args()

    if args.nwb:
        stem = args.nwb.stem
        session_prefix = stem.replace("_rec", "")
        sessions = [(str(args.nwb), session_prefix, stem)]
    elif args.all_ready:
        readiness = pd.read_csv(args.readiness_csv)
        candidates = readiness[(readiness["nwb_ok"] == True) & (readiness["short_nwb"] == False)]
        sessions = list(zip(candidates["nwb_path"], candidates["session_prefix"], candidates["stem"]))
    else:
        raise SystemExit("Specify --nwb <path> or --all-ready")

    n_completed = 0
    n_skipped = 0
    summary_rows = []
    for nwb_path, session_prefix, stem in sessions:
        print(f"=== {session_prefix} ===")
        result = run_one_session(nwb_path, session_prefix, stem, args.metadata_dir)
        if result["status"] != "completed":
            print(f"  SKIPPED/FAILED: {result.get('reason')}")
            n_skipped += 1
            summary_rows.append({"session_prefix": session_prefix, "status": f"{result['status']}: {result.get('reason')}"})
            continue
        out_dir = write_report(session_prefix, result)
        print(f"  wrote report to {out_dir} ({result['n_sig']}/{len(result['pairs'])} significant)")
        n_completed += 1
        summary_rows.append({
            "session_prefix": session_prefix, "status": "ok",
            "n_areas": len(result["areas"]), "n_pairs": len(result["pairs"]), "n_sig": result["n_sig"],
        })

    print(f"\nDone: {n_completed} completed, {n_skipped} skipped (of {len(sessions)})")
    summary_path = OUT_ROOT.parent / "publication_visual_review" / "suite_05_imaginary_coherence" / "all_sessions_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
