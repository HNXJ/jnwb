r"""
S6 (context/analysis_spec_SPK.md SS6): S+/S- directionality controls -- POSITIVE CONTROL for S5.

Method: apply S5 identically to S+ (predicted feedforward: low areas lead) and S- populations.
Rationale (spec, verbatim): "This is the positive control. If S+ does not show the expected
feedforward latency ordering, the latency method itself is not working and the O+ result cannot
be trusted either."
Acceptance (spec, verbatim): "Report S+ result before interpreting the O+ result. Method
validation precedes inference."

Does not reimplement anything -- calls S5's run()/build_stats()/plot_figure() unchanged with
class_col swapped to is_s_plus / is_s_minus. S5 was already built with this reuse in mind
(class_col is a parameter, not hardcoded).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "context" / "figures"))
sys.path.insert(0, str(REPO / "context" / "figures" / "S5_onset_latency_hierarchy_spk"))

from S5_onset_latency_hierarchy_spk import (  # noqa: E402
    _git_sha, build_stats, plot_figure, run, run_self_tests as _s5_self_tests,
)

OUT_DIR = Path(__file__).resolve().parent


def run_self_tests():
    # S6 adds no new fitting/CI machinery of its own -- it is S5 called with a different
    # class_col. S5's own self-tests already cover the shared pipeline (known-lag recovery,
    # zero-lag non-discrimination, degenerate CIs, determinism); re-running them here confirms
    # the imported functions are wired correctly, not re-deriving their correctness a second time.
    _s5_self_tests()
    print("\nAll S6 self-tests PASSED (delegates to S5's self-tested pipeline)")


def run_both(max_sessions: int = None, quality_tier: str = "stable") -> dict:
    out_splus = run(max_sessions=max_sessions, class_col="is_s_plus", quality_tier=quality_tier)
    out_sminus = run(max_sessions=max_sessions, class_col="is_s_minus", quality_tier=quality_tier)
    return {"is_s_plus": out_splus, "is_s_minus": out_sminus}


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_self_tests()
    else:
        max_sessions = None
        for a in sys.argv[1:]:
            if a.startswith("--max-sessions="):
                max_sessions = int(a.split("=")[1])

        results = run_both(max_sessions=max_sessions)

        stats_all = {}
        for class_col, run_out in results.items():
            stats = build_stats(run_out)
            stats_all[class_col] = stats
            plot_figure(run_out, OUT_DIR / f"S6_{class_col}", title_suffix=f" ({class_col}, positive control)")

        splus_disc = stats_all["is_s_plus"]["discriminating_any_pair"]
        combined_stats = {
            "id": "S6_directionality_controls_spk",
            "spec_source": "context/analysis_spec_SPK.md SS6",
            "acceptance_note": "Report S+ result BEFORE interpreting any O+ (S5) result -- method "
                                "validation precedes inference (spec, verbatim). S+ is the "
                                "predicted-feedforward positive control: if S+ does not show the "
                                "expected low-area-leads ordering, the S5 latency METHOD is not "
                                "validated and any S5 O+ finding should not be trusted regardless "
                                "of its own p-values.",
            "s_plus_discriminating_any_pair": splus_disc,
            "s_plus_method_validated": splus_disc,
            "s_minus": stats_all["is_s_minus"],
            "s_plus": stats_all["is_s_plus"],
            "git_sha": _git_sha(),
        }
        (OUT_DIR / "S6_stats.json").write_text(json.dumps(combined_stats, indent=2))
        manifest = {
            "method": "S6_directionality_controls_spk", "git_sha": _git_sha(),
            "reuses": "S5_onset_latency_hierarchy_spk.run/build_stats/plot_figure, unchanged",
            "n_sessions_s_plus": results["is_s_plus"]["n_sessions_processed"],
            "n_sessions_s_minus": results["is_s_minus"]["n_sessions_processed"],
        }
        (OUT_DIR / "S6_manifest.json").write_text(json.dumps(manifest, indent=2))
        print(f"\nDone. S+ method_validated={splus_disc} "
              f"(discriminating_any_pair for S+; per spec this gates trust in S5's O+ result)")
