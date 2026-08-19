r"""
S1 (context/analysis_spec_SPK.md): unit inclusion criteria rework -- BLOCKER for S2, S4, S5,
S6, S7, S8, S10, S11 and LFP-track L11.

Runs, per session: (1) the existing shuffle-controlled classifier
(omission.jnwb_ext.unit_classification.classify_unit, unmodified) for S+/S-/local-baseline O+/O++; (2) the
new likelihood-of-firing criterion (omission.jnwb_ext.unit_inclusion.classify_unit_omission_inclusion) --
P(unit fires | omission) vs P(unit fires | immediately pre-omission baseline; fixation is not
part of the comparison at any amplitude); (3)
quality-tier tagging from outputs/classification/unit_trial_presence.csv + raw NWB SNR; (4) the
old-vs-new comparison against outputs/classification/grand_s_and_o_units.csv's template-
correlation O+ (the pipeline that literally encodes fx=0 in its O+ template -- see
jnwb/unit_inclusion.py module docstring).

Writes the single canonical downstream-facing table:
    outputs/classification/unit_inclusion_v1.csv
    outputs/classification/unit_inclusion_v1_stats.json
    outputs/classification/unit_inclusion_v1_manifest.json

Subject aliases (Hamm, 2026-08-17): Ivan=V182o, Cajal=C31o, Joule=V198o. All three in scope.
Area naming: figstyle.AREA_ORDER as-is (repo canonical), not the spec's informal area list.
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

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import omission as oa
from jnwb import paths as P
from omission.jnwb_ext.unit_classification import (
    ClassificationConfig,
    classify_unit,
    config_to_dict,
    precompute_condition_onsets,
)
from omission.jnwb_ext.unit_classification import OM_BASE_GAP_MS
from omission.jnwb_ext.unit_inclusion import (
    STABLE_CRITERION_VERSION,
    InclusionConfig,
    assign_omission_inclusion_labels,
    assign_quality_tier,
    classify_unit_omission_inclusion,
    compare_old_new_criteria,
    old_new_summary_table,
)

READINESS_CSV = REPO / "artifacts/data/session_readiness.csv"
GRAND_OLD_CSV = REPO / "outputs/classification/grand_s_and_o_units.csv"
PRESENCE_CSV = REPO / "outputs/classification/unit_trial_presence.csv"
OUT_CSV = REPO / "outputs/classification/unit_inclusion_v1.csv"
OUT_STATS = REPO / "outputs/classification/unit_inclusion_v1_stats.json"
OUT_MANIFEST = REPO / "outputs/classification/unit_inclusion_v1_manifest.json"

ANIMAL_ALIAS = {"V182o": "Ivan", "C31o": "Cajal", "V198o": "Joule"}


def _unit_seed(session_prefix: str, unit_row: int, base_seed: int) -> int:
    """Deterministic per-unit seed from IDENTITY (session, unit_row, base_seed), not from loop
    position -- see the reproducibility incident this replaces, noted at the call site."""
    import hashlib

    key = f"{session_prefix}:{unit_row}:{base_seed}".encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:4], "big")


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO), stderr=subprocess.DEVNULL, text=True
        )
        return out.strip()
    except Exception:
        return "unknown"


def run(max_sessions: int = None) -> pd.DataFrame:
    readiness = pd.read_csv(READINESS_CSV)
    ready = readiness[readiness["nwb_ok"] == True].copy()
    if max_sessions is not None:
        ready = ready.head(max_sessions)

    presence = pd.read_csv(PRESENCE_CSV) if PRESENCE_CSV.exists() else pd.DataFrame(
        columns=["session", "unit_row", "trial_presence_fraction"]
    )
    old = pd.read_csv(GRAND_OLD_CSV) if GRAND_OLD_CSV.exists() else pd.DataFrame(
        columns=["session_prefix", "unit_row_idx", "is_Oplus"]
    )

    class_cfg = ClassificationConfig()
    incl_cfg = InclusionConfig()

    all_rows = []
    t0 = time.time()
    n_sessions_done = 0
    for si, row in enumerate(ready.itertuples(index=False), start=1):
        prefix = row.session_prefix
        subject = row.subject
        path = P.resolve_nwb_path(prefix)
        if not path.exists():
            print(f"  [{si}/{len(ready)}] MISSING nwb for {prefix}, skipping")
            continue
        try:
            sess = oa.read(str(path))
        except Exception as e:
            print(f"  [{si}/{len(ready)}] FAILED to load {prefix}: {e}")
            continue

        onsets = precompute_condition_onsets(sess, correct_only=True)
        units_df = sess._units_df

        sess_presence = presence[presence["session"] == prefix].set_index("unit_row")

        session_rows = []
        for uid in list(units_df.index):
            uid_i = int(uid)
            spikes = sess.get_spike_times(uid_i)
            if spikes is None or len(spikes) == 0:
                continue
            # Seed derived from (session, unit, base seed) identity, NOT from loop/draw order --
            # a sequential rng.integers() draw keyed only to iteration position silently
            # reassigns seeds to different units whenever units_df.index ordering isn't
            # bit-for-bit identical across runs (NWB load/caching order is not guaranteed to
            # be), which produced a confirmed run-to-run reproducibility failure at fixed
            # seed=42 (see artifacts/.lab/S1-unit-inclusion-rework-in-progress-20260817.json).
            rng_old = np.random.default_rng(_unit_seed(prefix, uid_i, class_cfg.seed))
            rng_new = np.random.default_rng(_unit_seed(prefix, uid_i, incl_cfg.seed))

            old_metrics = classify_unit(spikes, onsets, class_cfg, rng_old)
            new_metrics = classify_unit_omission_inclusion(spikes, onsets, incl_cfg, rng_new)

            urow = units_df.loc[uid_i]
            presence_frac = (
                float(sess_presence.loc[uid_i, "trial_presence_fraction"])
                if uid_i in sess_presence.index
                else np.nan
            )
            record = {
                "session": prefix,
                "unit_row": uid_i,
                "unit_id": uid_i,
                "area": urow.get("area", ""),
                "subject": subject,
                "animal_alias": ANIMAL_ALIAS.get(subject, subject),
                "quality": urow.get("quality", np.nan),
                "snr": urow.get("snr", np.nan),
                "trial_presence_fraction": presence_frac,
            }
            record.update(old_metrics)
            record.update(new_metrics)
            session_rows.append(record)

        if not session_rows:
            print(f"  [{si}/{len(ready)}] {prefix}: 0 units")
            continue

        sess_df = pd.DataFrame(session_rows)
        # Assign old-criterion booleans (S+/S-/O+, unmodified) at session level, matching
        # unit_classification._assign_labels' own per-session correction scope.
        from omission.jnwb_ext.unit_classification import _assign_labels

        sess_df = _assign_labels(sess_df, class_cfg)
        sess_df = assign_omission_inclusion_labels(sess_df, incl_cfg)
        sess_df["quality_tier"] = assign_quality_tier(
            sess_df["quality"], sess_df["trial_presence_fraction"], sess_df["snr"]
        )
        sess_df["stable_criterion_version"] = STABLE_CRITERION_VERSION

        all_rows.append(sess_df)
        n_sessions_done += 1
        print(
            f"  [{si}/{len(ready)}] {prefix}: {len(sess_df)} units "
            f"({time.time() - t0:.1f}s elapsed)"
        )

    if not all_rows:
        raise RuntimeError("No sessions produced any classified units")

    full = pd.concat(all_rows, ignore_index=True)

    compared = compare_old_new_criteria(full, old)
    full = full.merge(
        compared[["session", "unit_row", "transition", "old_screened"]],
        on=["session", "unit_row"],
        how="left",
    )
    # Bring the old classifier's own flag across too, named per the canonical schema.
    old_small = old[["session_prefix", "unit_row_idx", "is_Oplus"]].rename(
        columns={"session_prefix": "session", "unit_row_idx": "unit_row", "is_Oplus": "is_o_plus_old_templatecorr"}
    )
    full = full.merge(old_small, on=["session", "unit_row"], how="left")
    full["is_o_plus_old_templatecorr"] = (
        full["is_o_plus_old_templatecorr"].astype("boolean").fillna(False).astype(bool)
    )

    full["git_sha"] = _git_sha()
    full["classified_at_utc"] = datetime.now(timezone.utc).isoformat()
    for k, v in config_to_dict(class_cfg).items():
        if k in ("glo_conditions", "method"):
            continue
        full[f"cfg_old_{k}"] = v
    full["cfg_new_n_shuffles"] = incl_cfg.n_shuffles
    full["cfg_new_n_bootstrap"] = incl_cfg.n_bootstrap
    full["cfg_new_alpha"] = incl_cfg.alpha
    full["cfg_new_min_omission_events"] = incl_cfg.min_omission_events
    full["cfg_new_seed"] = incl_cfg.seed
    full["baseline_window_desc"] = (
        f"duration-matched to omission slot, ending omission_onset-{OM_BASE_GAP_MS:.0f}ms"
    )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    full.to_csv(OUT_CSV, index=False)

    inventory = (
        full.groupby(["animal_alias", "area", "quality_tier"])
        .agg(
            n_units=("unit_row", "count"),
            n_s_plus=("is_s_plus", "sum"),
            n_s_minus=("is_s_minus", "sum"),
            n_o_plus_local=("is_o_plus", "sum"),
            n_omission_inclusion_new=("is_omission_inclusion_new", "sum"),
            n_o_plus_old_templatecorr=("is_o_plus_old_templatecorr", "sum"),
        )
        .reset_index()
    )
    gained_lost = old_new_summary_table(full, group_cols=("area", "quality_tier"))

    stats = {
        "n_sessions": n_sessions_done,
        "n_units": int(len(full)),
        "n_animals": int(full["animal_alias"].nunique()),
        "inventory_by_animal_area_qualitytier": json.loads(inventory.to_json(orient="records")),
        "gained_lost_unchanged_by_area_qualitytier": json.loads(gained_lost.to_json(orient="records")),
        "transition_totals": full["transition"].value_counts().to_dict(),
        "n_omission_inclusion_new": int(full["is_omission_inclusion_new"].sum()),
        "n_o_plus_old_templatecorr": int(full["is_o_plus_old_templatecorr"].sum()),
        "n_o_plus_local_baseline": int(full["is_o_plus"].sum()),
    }
    OUT_STATS.write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")

    manifest = {
        "method": "unit_inclusion_v1",
        "git_sha": _git_sha(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "readiness_csv": str(READINESS_CSV),
            "presence_csv": str(PRESENCE_CSV),
            "old_criterion_csv": str(GRAND_OLD_CSV),
        },
        "n_sessions_attempted": int(len(ready)),
        "n_sessions_succeeded": n_sessions_done,
        "n_units": int(len(full)),
        "seed_old": class_cfg.seed,
        "seed_new": incl_cfg.seed,
        "stable_criterion_version": STABLE_CRITERION_VERSION,
        "stable_criterion_gap": (
            "spec wants presence>=0.98 AND FR<100Hz-at-any-1s AND SNR>0.5; this run implements "
            "presence+KS-quality+SNR only -- FR<100Hz-at-any-1s has no existing primitive in "
            "this repo and is not built here."
        ),
        "old_criterion_scope": (
            "old = template-correlation O+ from grand_s_and_o_units.csv "
            "(scripts/archive_oneoff/find_all_s_and_o_units.py), the pipeline that encodes "
            "fx=0 in its O+ template -- not omission.jnwb_ext.unit_classification's own local-baseline O+, "
            "which does not use fixation and is not the buggy mechanism."
        ),
        "area_naming": "figstyle.AREA_ORDER (repo canonical), not the spec's informal area list.",
        "animal_alias": ANIMAL_ALIAS,
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print(f"\nwrote {OUT_CSV} {full.shape}")
    print(f"wrote {OUT_STATS}")
    print(f"wrote {OUT_MANIFEST}")
    print("\nInventory by animal x area x quality tier:")
    print(inventory.to_string(index=False))
    print("\nGained/lost/unchanged by area x quality tier:")
    print(gained_lost.to_string(index=False))
    print(f"\ntransition totals: {stats['transition_totals']}")
    return full


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--max-sessions", type=int, default=None)
    args = ap.parse_args()
    run(max_sessions=args.max_sessions)
