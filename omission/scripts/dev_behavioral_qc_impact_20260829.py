"""P1 Step 5 (2026-08-29): real-data impact of the repaired behavioral QC, plus re-derivation of
the distribution statistics the module's QC-threshold docstring cites.

The QC redesign in behavioral_covariates.py was implemented against a 22-session distribution
audit whose receipt was never written (the implementing run was interrupted). Per this project's
"no claim without a receipt" rule, this script RE-DERIVES those numbers rather than inheriting
them, and measures what the repaired gate actually excludes, by subject and session.

Run:
  OMISSION_NWB_DIR=... OMISSION_ANALYSIS_DIR=... .venv/Scripts/python.exe \
    -m omission.scripts.dev_behavioral_qc_impact_20260829
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from jnwb.paths import nwb_dir
from omission.jnwb_ext import behavioral_covariates as bc

WINDOW_MS = (-500.0, 0.0)
OUT = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "behavioral-qc-repair-20260829.json"


def _subject(stem: str) -> str:
    return stem.split("_", 1)[0].removeprefix("sub-")


def session_report(path: Path) -> dict | None:
    stem = path.stem
    try:
        pupil_batch = bc.load_pupil_epochs(path, alignment="p1", window_ms=WINDOW_MS, missing_data="drop")
        gaze_batch = bc.load_gaze_epochs(path, alignment="p1", window_ms=WINDOW_MS, missing_data="drop")
    except Exception as exc:  # noqa: BLE001 - a session that cannot load is a reportable outcome
        return {"session": stem, "subject": _subject(stem), "error": f"{type(exc).__name__}: {exc}"}

    pupil = bc.extract_pupil_features(pupil_batch)
    gaze = bc.extract_gaze_features(gaze_batch)

    # re-derive the block-jump distribution statistics the docstring cites
    jump = bc.block_jump_diagnostics(
        pupil_batch.data[:, 0, :], sampling_rate_hz=bc._batch_rate(pupil_batch), block_ms=bc.QC_BLOCK_MS,
    )
    z = np.asarray(jump["max_jump_z"], dtype=float)
    z = z[np.isfinite(z)]
    v = np.asarray(jump["max_jump_v"], dtype=float)
    v = v[np.isfinite(v)]

    passing_v = v[np.asarray(pupil["qc_pass"], dtype=bool)[: len(v)]] if len(v) else np.array([])
    exc = np.asarray(gaze["excursion_z"], dtype=float)
    exc = exc[np.isfinite(exc)]

    def _q(a, q):
        return float(np.quantile(a, q)) if len(a) else float("nan")

    reasons: dict[str, int] = {}
    for col in ("qc_fail_reasons",):
        for frame, tag in ((pupil, "pupil"), (gaze, "gaze")):
            for r in frame[col]:
                if not r:
                    continue
                for part in str(r).split(","):
                    part = part.strip()
                    if part:
                        reasons[f"{tag}:{part}"] = reasons.get(f"{tag}:{part}", 0) + 1

    return {
        "session": stem,
        "subject": _subject(stem),
        "n_trials": int(len(pupil)),
        "pupil_pass": int(pupil["qc_pass"].sum()),
        "pupil_pass_frac": float(pupil["qc_pass"].mean()),
        "gaze_pass": int(gaze["qc_pass"].sum()),
        "gaze_pass_frac": float(gaze["qc_pass"].mean()),
        "fail_reason_counts": reasons,
        "block_jump_z_median": _q(z, 0.5),
        "block_jump_z_p99": _q(z, 0.99),
        "block_jump_v_max_on_passing_trials": float(passing_v.max()) if len(passing_v) else float("nan"),
        "gaze_excursion_z_p95": _q(exc, 0.95),
        "gaze_excursion_z_max": float(exc.max()) if len(exc) else float("nan"),
        "session_block_diff_scale": float(jump["session_block_diff_scale"]),
    }


def main() -> None:
    paths = sorted(Path(nwb_dir()).glob("*.nwb"))
    rows = [r for p in paths if (r := session_report(p)) is not None]
    ok = [r for r in rows if "error" not in r]
    errs = [r for r in rows if "error" in r]

    print(f"{'session':32s} {'subj':7s} {'n':>5s} {'pupilPass':>10s} {'gazePass':>9s}")
    for r in ok:
        print(f"{r['session']:32s} {r['subject']:7s} {r['n_trials']:5d} "
              f"{r['pupil_pass_frac']:10.3f} {r['gaze_pass_frac']:9.3f}")
    for r in errs:
        print(f"{r['session']:32s} {r['subject']:7s}  ERROR {r['error']}")

    by_subject = {}
    for subj in sorted({r["subject"] for r in ok}):
        sub = [r for r in ok if r["subject"] == subj]
        n = sum(r["n_trials"] for r in sub)
        by_subject[subj] = {
            "n_sessions": len(sub),
            "n_trials": n,
            "pupil_pass_frac": float(sum(r["pupil_pass"] for r in sub) / n) if n else float("nan"),
            "gaze_pass_frac": float(sum(r["gaze_pass"] for r in sub) / n) if n else float("nan"),
            "block_jump_z_p99_range": [min(r["block_jump_z_p99"] for r in sub),
                                        max(r["block_jump_z_p99"] for r in sub)],
            "gaze_excursion_z_p95_range": [min(r["gaze_excursion_z_p95"] for r in sub),
                                            max(r["gaze_excursion_z_p95"] for r in sub)],
        }

    all_reasons: dict[str, int] = {}
    for r in ok:
        for k, c in r["fail_reason_counts"].items():
            all_reasons[k] = all_reasons.get(k, 0) + c

    passing_v = [r["block_jump_v_max_on_passing_trials"] for r in ok
                 if np.isfinite(r["block_jump_v_max_on_passing_trials"])]
    summary = {
        "n_sessions_ok": len(ok),
        "n_sessions_error": len(errs),
        "total_trials": sum(r["n_trials"] for r in ok),
        "corpus_pupil_pass_frac": float(sum(r["pupil_pass"] for r in ok) / max(sum(r["n_trials"] for r in ok), 1)),
        "corpus_gaze_pass_frac": float(sum(r["gaze_pass"] for r in ok) / max(sum(r["n_trials"] for r in ok), 1)),
        "by_subject": by_subject,
        "fail_reason_counts": all_reasons,
        "max_block_jump_v_on_passing_trials_corpus": float(max(passing_v)) if passing_v else float("nan"),
        "block_jump_z_p99_corpus_max": float(max(r["block_jump_z_p99"] for r in ok)) if ok else float("nan"),
        "qc_gate_can_return_both_true_and_false": bool(
            any(0.0 < r["pupil_pass_frac"] < 1.0 or 0.0 < r["gaze_pass_frac"] < 1.0 for r in ok)
        ),
    }
    print("\n=== SUMMARY ===")
    print(json.dumps({k: v for k, v in summary.items() if k != "by_subject"}, indent=2))
    print(json.dumps(by_subject, indent=2))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema_version": 3,
        "id": "behavioral-qc-repair-20260829",
        "kind": "evidence",
        "title": "Behavioral QC repair (P1): criteria, real-data impact, and re-derived threshold statistics",
        "status": "provisional",
        "defect_repaired": (
            "qc_pass previously excluded 0 of 960 trials while 91.8% carried a detected "
            "discontinuity: discontinuity_count was computed but never wired into the gate, so "
            "trial_has_valid_behavior / session_behavior_available could not return False."
        ),
        "criteria_in_force": {
            "QC_BLOCK_MS": bc.QC_BLOCK_MS,
            "QC_MAX_JUMP_Z": bc.QC_MAX_JUMP_Z,
            "QC_ABS_JUMP_V": bc.QC_ABS_JUMP_V,
            "QC_MAX_EXCURSION_Z": bc.QC_MAX_EXCURSION_Z,
            "QC_MIN_VALID_FRAC": bc.QC_MIN_VALID_FRAC,
            "QC_MIN_SESSION_FRAC": bc.QC_MIN_SESSION_FRAC,
            "QC_MIN_TRIALS_FOR_RELATIVE_SCALE": bc.QC_MIN_TRIALS_FOR_RELATIVE_SCALE,
            "CLIP_PROXIMITY_ABS": bc.CLIP_PROXIMITY_ABS,
        },
        "window_ms": list(WINDOW_MS),
        "summary": summary,
        "per_session": ok,
        "errors": errs,
    }, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
