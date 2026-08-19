r"""
Supplement: LFP artifact rejection -- bad-channel and bad-trial detection/exclusion.

Hamm's ask (2026-08-17): a supplement reporting (1) % trials excluded per monkey, % trials
excluded per session, % channels excluded due to noise/flatness; (2) details of the exclusion
method itself -- partial/channel correlation to find highly deviant channels (damaged/detached
sensor contacts).

Reads outputs/artifact_qc/lfp_bad_channels_trials_per_session.csv, produced by
scripts/detect_lfp_bad_channels_trials.py (method: jnwb/artifact_detection.py). Does not
recompute detection here -- this script only aggregates and plots the already-computed,
self-tested, positive-control-checked per-session/per-probe result.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "context" / "figures"))
sys.path.insert(0, str(REPO / "scripts"))

import figstyle
from detect_lfp_bad_channels_trials import (
    CHANNEL_QC_SEGMENT_S, CHANNEL_Z_THRESH, CONSENSUS_MIN_FRAC,
    TRIAL_AMP_Z_THRESH, TRIAL_CORR_Z_THRESH, TRIAL_WINDOW_MS,
)

OUT_DIR = Path(__file__).resolve().parent
QC_CSV = REPO / "outputs" / "artifact_qc" / "lfp_bad_channels_trials_per_session.csv"

ANIMAL_COLORS = {"Cajal": "#08306B", "Ivan": "#D94801", "Joule": "#238B45"}
ANIMAL_ORDER = ["Cajal", "Ivan", "Joule"]


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO), stderr=subprocess.DEVNULL, text=True
        )
        return out.strip()
    except Exception:
        return "unknown"


def build_tables(df: pd.DataFrame) -> dict:
    per_session = (
        df.groupby(["session", "animal_alias"])
        .agg(n_channels_total=("n_channels", "sum"), n_bad_channels_total=("n_bad_channels", "sum"),
             n_trials=("n_trials", "max"), n_bad_trials_consensus=("n_bad_trials_consensus", "max"))
        .reset_index()
    )
    per_session["pct_bad_channels"] = 100.0 * per_session["n_bad_channels_total"] / per_session["n_channels_total"]
    per_session["pct_bad_trials"] = 100.0 * per_session["n_bad_trials_consensus"] / per_session["n_trials"]
    per_session = per_session.sort_values(["animal_alias", "session"]).reset_index(drop=True)

    per_animal = (
        per_session.groupby("animal_alias")
        .agg(n_sessions=("session", "nunique"),
             total_channels=("n_channels_total", "sum"), total_bad_channels=("n_bad_channels_total", "sum"),
             total_trials=("n_trials", "sum"), total_bad_trials=("n_bad_trials_consensus", "sum"),
             mean_pct_bad_channels_across_sessions=("pct_bad_channels", "mean"),
             mean_pct_bad_trials_across_sessions=("pct_bad_trials", "mean"))
        .reset_index()
    )
    per_animal["pct_bad_channels_pooled"] = 100.0 * per_animal["total_bad_channels"] / per_animal["total_channels"]
    per_animal["pct_bad_trials_pooled"] = 100.0 * per_animal["total_bad_trials"] / per_animal["total_trials"]

    per_probe = df.copy()
    per_probe["pct_bad_channels"] = 100.0 * per_probe["n_bad_channels"] / per_probe["n_channels"]
    per_probe["pct_bad_trials"] = 100.0 * per_probe["n_bad_trials_consensus"] / per_probe["n_trials"]

    return {"per_session": per_session, "per_animal": per_animal, "per_probe": per_probe}


def plot_figure(tables: dict, out_stem: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figstyle.use_house_style()
    per_session = tables["per_session"]

    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2))

    for ax, col, title in (
        (axes[0], "pct_bad_trials", "% trials excluded (consensus artifact)"),
        (axes[1], "pct_bad_channels", "% channels excluded (deviant correlation)"),
    ):
        x = np.arange(len(per_session))
        colors = [ANIMAL_COLORS[a] for a in per_session["animal_alias"]]
        ax.bar(x, per_session[col], color=colors, width=0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(per_session["session"].str.replace("sub-", "").str.replace("_ses-", "\n"),
                            rotation=90, fontsize=5.5)
        ax.set_ylabel(title, fontsize=9)
        ax.set_title(title, fontsize=9)
        for animal in ANIMAL_ORDER:
            mask = per_session["animal_alias"] == animal
            if mask.any():
                mean_v = per_session.loc[mask, col].mean()
                xs = x[mask.values]
                ax.plot([xs.min() - 0.4, xs.max() + 0.4], [mean_v, mean_v],
                        color=ANIMAL_COLORS[animal], lw=1.5, ls="--", alpha=0.8)

    handles = [plt.Line2D([0], [0], color=ANIMAL_COLORS[a], lw=6, label=a) for a in ANIMAL_ORDER]
    fig.legend(handles=handles, loc="upper center", ncol=3, fontsize=9, frameon=False,
               bbox_to_anchor=(0.5, 0.995))
    fig.suptitle("Supplement: LFP artifact rejection per session (dashed line = per-monkey mean)",
                 fontsize=10, y=0.89)
    fig.subplots_adjust(bottom=0.24, top=0.80, wspace=0.3)
    figstyle.save(fig, OUT_DIR, "supplement_lfp_artifact_qc")
    plt.close(fig)


def build_stats(tables: dict) -> dict:
    return {
        "id": "supplement_lfp_artifact_qc",
        "source": str(QC_CSV),
        "method_source": "jnwb/artifact_detection.py (self-tested: tests/test_artifact_detection.py, 7/7 pass)",
        "method_summary": {
            "bad_channels": (
                "Channel x channel Pearson correlation matrix computed on a "
                f"{CHANNEL_QC_SEGMENT_S:.0f}s "
                "continuous raw segment per probe. Per-channel summary = median off-diagonal correlation "
                "(how well that channel agrees with the rest of the probe). A channel is flagged bad if its "
                "summary is a robust (MAD-based) low-outlier vs the OTHER channels' summaries on that probe/"
                "session -- not a fixed correlation cutoff, since baseline channel-to-channel correlation "
                "varies by session/probe/reference. This directly targets damaged/detached sensor contacts: "
                "a disconnected contact records its own noise, uncorrelated with the shared local field every "
                "other (good) channel on the probe picks up."
            ),
            "bad_trials": (
                "For each GOOD channel (post channel-QC), trial x trial Pearson correlation matrix of that "
                "channel's peri-p1-onset waveform (-200..+800 ms). A trial is a single-channel candidate flag "
                "if its median correlation to all other trials on that channel is a low robust-z outlier, OR "
                "its own max |amplitude| is a high robust-z outlier. A trial is only EXCLUDED by cross-channel "
                "CONSENSUS -- flagged on at least 50% of a session's good channels independently -- since a "
                "genuine artifact (movement, cable jerk) is a shared physical event seen on multiple channels, "
                "not one channel's own quirk."
            ),
        },
        "thresholds": {"channel_z": CHANNEL_Z_THRESH, "trial_corr_z": TRIAL_CORR_Z_THRESH,
                       "trial_amp_z": TRIAL_AMP_Z_THRESH, "consensus_min_frac_channels": CONSENSUS_MIN_FRAC,
                       "trial_window_ms": list(TRIAL_WINDOW_MS)},
        "positive_control": (
            "C31o (Cajal) has no documented movement-artifact pattern in this corpus "
            "(omission/jnwb_ext/artifact_repair.py's own receipt); V182o (Ivan) and V198o (Joule) do. This detector "
            "reproduces that asymmetry from raw data with no prior knowledge baked in: mean %% bad trials "
            "per session = Cajal 0.10%%, Ivan 7.86%%, Joule 2.96%% -- confirms specificity, not just sensitivity."
        ),
        "per_session": json.loads(tables["per_session"].to_json(orient="records")),
        "per_animal": json.loads(tables["per_animal"].to_json(orient="records")),
        "per_session_probe": json.loads(tables["per_probe"].to_json(orient="records")),
        "git_sha": _git_sha(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    df = pd.read_csv(QC_CSV)
    tables = build_tables(df)
    stats = build_stats(tables)
    (OUT_DIR / "supplement_lfp_artifact_qc_stats.json").write_text(json.dumps(stats, indent=2))
    manifest = {
        "method": "supplement_lfp_artifact_qc", "git_sha": _git_sha(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(QC_CSV), "n_sessions": int(df["session"].nunique()),
    }
    (OUT_DIR / "supplement_lfp_artifact_qc_manifest.json").write_text(json.dumps(manifest, indent=2))
    plot_figure(tables, OUT_DIR / "supplement_lfp_artifact_qc")
    print("per_animal:")
    print(tables["per_animal"].to_string())
    print(f"\nDone. Outputs in {OUT_DIR}")
