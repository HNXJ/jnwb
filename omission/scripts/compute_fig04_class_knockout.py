#!/usr/bin/env python3
"""Class-knockout supplemental analysis: who has information about who.

Generalizes ``compute_fig04_encoding_matrix.py``'s SSA-decile ablation (Panel H) from "remove
the top-decile |SSA| units" to "remove a named functional class" -- S+, S-, O+, O++, Other, and
two grouped unions (S+ union S- = stimulus_selective, O+ union O++ = omission_selective) -- and
wires the same masked-refit-vs-matched-random-null pattern to ALL FOUR fig04 targets
(Y_stim/Y_omit/Y_pos/Y_prev), not just Y_omit.

Class source: ``outputs/classification/unit_inclusion_v1.csv``'s ``display_class`` column --
the canonical, currently-maintained S+/S-/O+/O++/Other table (NOT ``grand_s_and_o_units.csv`` or
``omission_grand_units.csv``, which disagree substantially with this one and with each other;
see ``context/03_classification_pipelines.md``). Its own ``session`` column omits the ``_rec``
suffix present in this pipeline's session stems (confirmed empirically: ``sub-C31o_ses-230816``
vs. ``sub-C31o_ses-230816_rec``) -- stripped before the join, not assumed.

**Interpretive framing (the point of this analysis, not an implementation detail)**: S+/S- were
*defined* by stimulus-responsiveness criteria and O+/O++ by omission-responsiveness criteria, so
removing S+/S- hurting ``Y_stim`` (or O+/O++ hurting ``Y_omit``) is an expected manipulation
check, not a novel finding -- the selection criterion already contains that conclusion (project
tripwire 6). The scientifically interesting cells are the OFF-diagonal ones: does removing
O+/O++ hurt ``Y_stim`` or ``Y_prev`` (omission units carrying stimulus/history information)?
Does removing S+/S- hurt ``Y_omit`` or ``Y_pos`` (stimulus units carrying omission-relevant
information)? Render this as a class x target matrix so the distinction is visually immediate.

**Min-count gating**: a (session, area, removal_condition) cell is skipped -- and the skip is
recorded, not silently dropped -- whenever fewer than ``MIN_CLASS_UNITS`` (default 3) of that
session/area's decoding population belong to the class. O++ has only 5 units corpus-wide in
``unit_inclusion_v1.csv``, so it is expected to skip in nearly every cell; that near-universal
skip is itself the finding ("too rare to test at the single-session level"), not a bug.

Outputs, all under ``--output-dir``:

* ``fig04_class_knockout_cells.csv`` -- one row per (session, area, target, position,
  removal_condition);
* ``fig04_class_knockout_receipt.json`` -- provenance, same conventions as the encoding-matrix
  script's receipt, including the per-removal-condition skip rate.

Spike-only. No LFP claim (that is Part 2 of the class-knockout/dissociability plan, a separate
script). Fixed-window (Stage 1 style) only.
"""
from __future__ import annotations

import argparse
import functools
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))
OA_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))

import omission as oa  # noqa: E402
from omission.jnwb_ext.omission_identity import OMISSION_IDENTITY_CONDITIONS  # noqa: E402
from jnwb import paths  # noqa: E402
from jnwb.paths import sha256_file as _sha256  # noqa: E402

from compute_omission_identity_leakage_safe import (  # noqa: E402
    AREAS,
    DEFAULT_SEED,
    DEFAULT_PERMUTATIONS,
    ESTIMATOR,
    _trial_table,
    _resolve_sessions,
    decode_binary_cycle_safe,
)
from compute_omission_identity_extended_v1 import (  # noqa: E402
    SOFTMAX_ESTIMATOR,
    decode_softmax_p4_cycle_safe,
)
from compute_fig04_encoding_matrix import (  # noqa: E402
    POSITIONS,
    POSITION_WINDOW_MS,
    REAL_STIM_WINDOW_MS,
    _y_stim_table,
    _cross_slot_table,
    _spike_matrix_from_onsets,
    _center_within_cycle,
    decode_multiclass_balanced_cycle_safe,
)
from compute_omission_identity_leakage_safe import _spike_count_matrix  # noqa: E402

DEFAULT_CLASS_TABLE = OA_ROOT / "outputs" / "classification" / "unit_inclusion_v1.csv"
DEFAULT_KNOCKOUT_DRAWS = 50
MIN_CLASS_UNITS = 3

REMOVAL_CONDITIONS = {
    "S+": lambda cls: cls == "S+",
    "S-": lambda cls: cls == "S-",
    "O+": lambda cls: cls == "O+",
    "O++": lambda cls: cls == "O++",
    "Other": lambda cls: cls == "Other",
    "stim_selective": lambda cls: cls in ("S+", "S-"),
    "omission_selective": lambda cls: cls in ("O+", "O++"),
}

# (decode_fn, metric_key, "higher_better"|"lower_better")
TARGET_DECODERS = {
    "Y_stim": (decode_binary_cycle_safe, "accuracy_loco_balanced", "higher_better"),
    "Y_omit": (decode_softmax_p4_cycle_safe, "cross_entropy", "lower_better"),
    "Y_pos": (functools.partial(decode_multiclass_balanced_cycle_safe, n_classes=3),
              "accuracy_loco_balanced", "higher_better"),
    "Y_prev": (decode_binary_cycle_safe, "accuracy_loco_balanced", "higher_better"),
}


def load_class_table(path: Path) -> dict[str, dict[int, str]]:
    """session_stem (no _rec) -> {unit_row: display_class}."""
    df = pd.read_csv(path, usecols=["session", "unit_row", "display_class"])
    out: dict[str, dict[int, str]] = {}
    for session_stem, group in df.groupby("session"):
        out[session_stem] = dict(zip(group["unit_row"].astype(int), group["display_class"]))
    return out


def _removal_cols(units_index, class_lookup: dict[int, str], predicate) -> list[int]:
    return [
        col for col, unit_row in enumerate(units_index)
        if predicate(class_lookup.get(int(unit_row), "Other"))
    ]


def run_class_knockout(
    decode_fn, metric_key: str, X: np.ndarray, labels: np.ndarray, cycles: np.ndarray,
    remove_cols: list[int], *, seed: int, n_permutations: int, n_draws: int,
) -> dict:
    """Full model / class-masked model / n_draws matched-random-size-removal null.

    Same three-way comparison as ``compute_fig04_encoding_matrix.run_ablation``, generalized to
    an explicit removal-column list (class membership) instead of an SSA-ranked decile, and to
    any of the four targets' decoders instead of only the Y_omit softmax.
    """
    n_units = X.shape[1]
    n_remove = len(remove_cols)
    if n_remove < MIN_CLASS_UNITS or n_remove >= n_units:
        return {"status": "insufficient_class_units", "n_units_total": n_units,
                "n_class_units": n_remove}

    full = decode_fn(X, labels, cycles, seed=seed, n_permutations=n_permutations)
    if full.get("status") != "success":
        return {"status": "full_fit_failed", "n_units_total": n_units, "n_class_units": n_remove}

    keep_cols = [c for c in range(n_units) if c not in set(remove_cols)]
    removed = decode_fn(X[:, keep_cols], labels, cycles, seed=seed, n_permutations=n_permutations)
    if removed.get("status") != "success":
        return {"status": "removed_fit_failed", "n_units_total": n_units, "n_class_units": n_remove}

    rng = np.random.default_rng(seed + 700_000)
    random_vals: list[float] = []
    for draw in range(int(n_draws)):
        rem = set(rng.choice(n_units, size=n_remove, replace=False).tolist())
        keep = [c for c in range(n_units) if c not in rem]
        # One cheap permutation per draw -- the draw DISTRIBUTION is the object of interest, not
        # each draw's own well-powered null (matches compute_fig04_encoding_matrix.run_ablation).
        r = decode_fn(X[:, keep], labels, cycles, seed=seed + 4000 + draw, n_permutations=1)
        if r.get("status") == "success":
            random_vals.append(float(r[metric_key]))

    random_arr = np.asarray(random_vals, dtype=float)
    full_val = float(full[metric_key])
    removed_val = float(removed[metric_key])
    if len(random_arr):
        # direction-agnostic: fraction of random draws AT LEAST AS UNFAVORABLE as the class
        # removal (>= removed for cross-entropy where higher=worse, <= removed for accuracy
        # where lower=worse) -- a small percentile means the class removal was WORSE than nearly
        # every matched-random removal, i.e. class-specific information.
        percentile = (
            float(np.mean(random_arr >= removed_val)) if metric_key == "cross_entropy"
            else float(np.mean(random_arr <= removed_val))
        )
    else:
        percentile = float("nan")

    return {
        "status": "success",
        "n_units_total": n_units,
        "n_class_units": n_remove,
        "metric_full": full_val,
        "metric_removed": removed_val,
        "metric_random_mean": float(np.mean(random_arr)) if len(random_arr) else np.nan,
        "metric_random_sd": float(np.std(random_arr, ddof=1)) if len(random_arr) > 1 else np.nan,
        "n_random_draws": int(len(random_arr)),
        "percentile_of_removed": percentile,
        "delta": full_val - removed_val,
    }


def run(*, readiness_csv: Path, nwb_dir: Path, class_table_path: Path, output_dir: Path,
        seed: int = DEFAULT_SEED, n_permutations: int = DEFAULT_PERMUTATIONS,
        n_draws: int = DEFAULT_KNOCKOUT_DRAWS, limit: int | None = None) -> dict:
    started = time.time()
    included, excluded = _resolve_sessions(readiness_csv, nwb_dir)
    if limit is not None:
        included = included[:limit]
    if not included:
        raise RuntimeError("no eligible NWB sessions resolved from the readiness gate")

    class_table = load_class_table(class_table_path)
    cell_rows: list[dict] = []
    errors: list[dict] = []

    for session_number, meta in enumerate(included, start=1):
        print(f"[{session_number}/{len(included)}] {meta['stem']}", flush=True)
        session_stem_noR = meta["stem"][:-4] if meta["stem"].endswith("_rec") else meta["stem"]
        class_lookup = class_table.get(session_stem_noR, {})
        try:
            session = oa.read(meta["path"])

            # -- Y_stim: p1 --
            stim_table = _y_stim_table(session)
            for area in AREAS:
                if stim_table.empty:
                    continue
                X, units = _spike_matrix_from_onsets(
                    session, area, stim_table["start_time"].to_numpy(), REAL_STIM_WINDOW_MS
                )
                if X.shape[1] == 0:
                    continue
                labels = stim_table["label_int"].to_numpy(int)
                cycles = stim_table["cycle_id"].to_numpy(int)
                decode_fn, metric_key, _ = TARGET_DECODERS["Y_stim"]
                for cond_name, predicate in REMOVAL_CONDITIONS.items():
                    remove_cols = _removal_cols(units.index, class_lookup, predicate)
                    result = run_class_knockout(
                        decode_fn, metric_key, X, labels, cycles, remove_cols,
                        seed=seed, n_permutations=n_permutations, n_draws=n_draws,
                    )
                    cell_rows.append({
                        "session": meta["stem"], "subject": meta["subject"], "area": area,
                        "target": "Y_stim", "position": "p1", "removal_condition": cond_name,
                        "seed": seed, **result,
                    })

            # -- Y_omit: per slot --
            for slot_key in POSITIONS:
                table = _trial_table(session, slot_key)
                if table.empty or table["cycle_id"].nunique() < 2:
                    continue
                for area in AREAS:
                    X, units = _spike_count_matrix(
                        session, area, table,
                        (OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_onset_ms"],
                         OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_end_ms"]),
                    )
                    if X.shape[1] == 0:
                        continue
                    labels = table["label_int"].to_numpy(int)
                    cycles = table["cycle_id"].to_numpy(int)
                    decode_fn, metric_key, _ = TARGET_DECODERS["Y_omit"]
                    for cond_name, predicate in REMOVAL_CONDITIONS.items():
                        remove_cols = _removal_cols(units.index, class_lookup, predicate)
                        result = run_class_knockout(
                            decode_fn, metric_key, X, labels, cycles, remove_cols,
                            seed=seed, n_permutations=n_permutations, n_draws=n_draws,
                        )
                        cell_rows.append({
                            "session": meta["stem"], "subject": meta["subject"], "area": area,
                            "target": "Y_omit", "position": slot_key, "removal_condition": cond_name,
                            "seed": seed, **result,
                        })

            # -- Y_pos & Y_prev: shared cross-slot table/feature matrix --
            cross_table = _cross_slot_table(session)
            if not cross_table.empty and cross_table["cross_cycle_id"].nunique() >= 2:
                for area in AREAS:
                    X, units = _spike_matrix_from_onsets(
                        session, area, cross_table["effective_onset_s"].to_numpy(), POSITION_WINDOW_MS
                    )
                    if X.shape[1] == 0:
                        continue
                    cycles = cross_table["cross_cycle_id"].to_numpy(int)
                    X_centered = _center_within_cycle(X, cycles)

                    pos_labels = cross_table["position_int"].to_numpy(int)
                    decode_fn, metric_key, _ = TARGET_DECODERS["Y_pos"]
                    for cond_name, predicate in REMOVAL_CONDITIONS.items():
                        remove_cols = _removal_cols(units.index, class_lookup, predicate)
                        result = run_class_knockout(
                            decode_fn, metric_key, X_centered, pos_labels, cycles, remove_cols,
                            seed=seed, n_permutations=n_permutations, n_draws=n_draws,
                        )
                        cell_rows.append({
                            "session": meta["stem"], "subject": meta["subject"], "area": area,
                            "target": "Y_pos", "position": "p2_p3_p4",
                            "removal_condition": cond_name, "seed": seed, **result,
                        })

                    prev_labels = cross_table["preceding_int"].to_numpy(int)
                    decode_fn, metric_key, _ = TARGET_DECODERS["Y_prev"]
                    for cond_name, predicate in REMOVAL_CONDITIONS.items():
                        remove_cols = _removal_cols(units.index, class_lookup, predicate)
                        result = run_class_knockout(
                            decode_fn, metric_key, X, prev_labels, cycles, remove_cols,
                            seed=seed, n_permutations=n_permutations, n_draws=n_draws,
                        )
                        cell_rows.append({
                            "session": meta["stem"], "subject": meta["subject"], "area": area,
                            "target": "Y_prev", "position": "p2_p3_p4_pooled",
                            "removal_condition": cond_name, "seed": seed, **result,
                        })

        except Exception as exc:
            errors.append({"session": meta["stem"], "reason": type(exc).__name__, "detail": str(exc)})
            print(f"  ERROR {type(exc).__name__}: {exc}", flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    cells_df = pd.DataFrame(cell_rows)
    outputs = {"cells": output_dir / "fig04_class_knockout_cells.csv"}
    cells_df.to_csv(outputs["cells"], index=False)

    skip_rates = {}
    if not cells_df.empty:
        for cond_name in REMOVAL_CONDITIONS:
            sub = cells_df[cells_df.removal_condition == cond_name]
            n_total = len(sub)
            n_skipped = int((sub.status == "insufficient_class_units").sum())
            skip_rates[cond_name] = {
                "n_cells": n_total, "n_skipped_insufficient_class_units": n_skipped,
                "skip_fraction": (n_skipped / n_total) if n_total else float("nan"),
            }

    receipt = {
        "analysis_status": "complete" if not errors else "failed_with_errors",
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "git_sha": __import__("subprocess").check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "nwb_dir": str(nwb_dir),
        "readiness_csv": str(readiness_csv),
        "class_table": str(class_table_path),
        "class_table_source": "unit_inclusion_v1.csv::display_class (canonical S+/S-/O+/O++/"
                               "Other; NOT grand_s_and_o_units.csv or omission_grand_units.csv)",
        "eligible_sessions": included,
        "excluded_sessions": excluded,
        "seed": seed,
        "n_permutations_requested": n_permutations,
        "n_draws": n_draws,
        "min_class_units": MIN_CLASS_UNITS,
        "removal_conditions": list(REMOVAL_CONDITIONS.keys()),
        "removal_condition_skip_rates": skip_rates,
        "targets": list(TARGET_DECODERS.keys()),
        "interpretive_note": "diagonal cells (S+/S- vs Y_stim, O+/O++ vs Y_omit) are "
                              "manipulation checks -- the class definition already implies the "
                              "expected result (tripwire 6). Off-diagonal cells are the novel "
                              "who-has-information-about-who question.",
        "signal": "SPK/SUA only",
        "errors": errors,
        "runtime_seconds": time.time() - started,
        "output_hashes": {key: _sha256(path) for key, path in outputs.items()},
        "output_paths": {key: str(path) for key, path in outputs.items()},
    }
    receipt_path = output_dir / "fig04_class_knockout_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        f"Completed {len(included)} eligible sessions, {len(cell_rows)} cells in "
        f"{receipt['runtime_seconds']:.1f}s.",
        flush=True,
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness", type=Path,
                        default=OA_ROOT / "artifacts" / "data" / "session_readiness.csv")
    parser.add_argument("--nwb-dir", type=Path, default=paths.nwb_dir())
    parser.add_argument("--class-table", type=Path, default=DEFAULT_CLASS_TABLE)
    parser.add_argument("--output-dir", type=Path, default=OA_ROOT / "outputs" / "classification")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--permutations", type=int, default=DEFAULT_PERMUTATIONS)
    parser.add_argument("--draws", type=int, default=DEFAULT_KNOCKOUT_DRAWS)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if not args.nwb_dir.exists():
        raise FileNotFoundError(
            f"NWB directory not found: {args.nwb_dir}; pass --nwb-dir or set OMISSION_NWB_DIR"
        )
    if not args.class_table.exists():
        raise FileNotFoundError(f"class table not found: {args.class_table}")
    run(readiness_csv=args.readiness, nwb_dir=args.nwb_dir, class_table_path=args.class_table,
        output_dir=args.output_dir, seed=args.seed, n_permutations=args.permutations,
        n_draws=args.draws, limit=args.limit)


if __name__ == "__main__":
    main()
