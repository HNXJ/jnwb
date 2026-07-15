"""
scripts/update_prp_for_markdowns.py

Adds the new plan, progress, and review items to artifacts/developer/plans.json,
progress.json, and review.json to establish the backlog items for creating the
5 context markdown files explaining the omission paradigm.
"""

from __future__ import annotations

import json
from pathlib import Path

PRP_DIR = Path("D:/workspace/omission/artifacts/developer")


def main():
    # 1. Update plans.json
    plans_path = PRP_DIR / "plans.json"
    with open(plans_path, "r", encoding="utf-8") as f:
        plans = json.load(f)

    new_plan_item = {
        "title": "Omission Paradigm Context Documentation Suite",
        "description": "Generate 5 comprehensive markdown documentation files under context/ detailing the omission paradigm, signal modalities, task configurations, temporal alignment, and the JRSA connectivity core.",
        "priority": "high",
        "status": "in-progress"
    }
    
    # Check if already added
    if not any(p["title"] == new_plan_item["title"] for p in plans):
        plans.append(new_plan_item)
        with open(plans_path, "w", encoding="utf-8") as f:
            json.dump(plans, f, indent=2, ensure_ascii=False)
        print("Updated plans.json")

    # 2. Update progress.json
    progress_path = PRP_DIR / "progress.json"
    with open(progress_path, "r", encoding="utf-8") as f:
        progress = json.load(f)

    markdown_files = [
        ("context/01_omission_paradigm.md", "Overview of the omission task paradigm, correct vs. incorrect trials, and task phases."),
        ("context/02_temporal_dynamics.md", "Details on sequence epoch timings (fx, p1-4, d1-4), slot windows, and temporal alignments."),
        ("context/03_signal_modalities.md", "Explanation of signal streams (SPK, LFP, TFR, pupil dynamics) and layer masks mappings."),
        ("context/04_analysis_pipelines.md", "Summary of pipeline flows: single-unit template correlation classifiers, stable-trial filtering, and SVM population decoders."),
        ("context/05_connectivity_jrsa.md", "Detailed specification of the unified JRSA relationship analysis, metrics dispatch, and permutation tests.")
    ]

    for path, purpose in markdown_files:
        if not any(e["path"] == path for e in progress["entries"]):
            progress["entries"].append({
                "filename": Path(path).name,
                "purpose": purpose,
                "score": 0,
                "tbis": 0,
                "tbds": 0,
                "warnings": "",
                "path": path,
                "status": "todo",
                "last_verified": "",
                "evidence": ""
            })
            
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)
    print("Updated progress.json")

    # 3. Update review.json
    review_path = PRP_DIR / "review.json"
    with open(review_path, "r", encoding="utf-8") as f:
        review = json.load(f)

    for path, purpose in markdown_files:
        if not any(e["path"] == path for e in review["entries"]):
            review["entries"].append({
                "filename": Path(path).name,
                "path": path,
                "score": 0,
                "verdict": "NEEDS REPRODUCTION",
                "issues": "Document has not yet been drafted.",
                "fix_actions": "Create markdown file detailing task description in omission/context.",
                "review_command": f"cat {path}",
                "last_reviewed": ""
            })

    with open(review_path, "w", encoding="utf-8") as f:
        json.dump(review, f, indent=2, ensure_ascii=False)
    print("Updated review.json")


if __name__ == "__main__":
    main()
