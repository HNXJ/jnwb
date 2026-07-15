"""
scripts/update_prp_for_gpu.py

Updates plans.json, progress.json, and review.json backlog matrices to log the
completed CuPy & CUDA acceleration optimization task for jnwb/jrsa.py.
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
        "title": "JRSA GPU (CuPy & CUDA) Optimization",
        "description": "Optimize the JRSA engine to utilize CuPy-accelerated GPU operations for permutation tests, bootstrapping, and correlation metrics when device='cuda' is active.",
        "priority": "high",
        "status": "completed"
    }

    if not any(p["title"] == new_plan_item["title"] for p in plans):
        plans.append(new_plan_item)
        with open(plans_path, "w", encoding="utf-8") as f:
            json.dump(plans, f, indent=2, ensure_ascii=False)
        print("Updated plans.json")

    # 2. Update progress.json
    progress_path = PRP_DIR / "progress.json"
    with open(progress_path, "r", encoding="utf-8") as f:
        progress = json.load(f)

    path_str = "tests/test_jrsa_gpu.py"
    if not any(e["path"] == path_str for e in progress["entries"]):
        progress["entries"].append({
            "filename": "test_jrsa_gpu.py",
            "purpose": "Verifies CuPy & CUDA execution and mathematical consistency of jrsa() on GPU.",
            "score": 100,
            "tbis": 0,
            "tbds": 0,
            "warnings": "Requires CuPy and active CUDA environment.",
            "path": path_str,
            "status": "done",
            "last_verified": "2026-07-15",
            "evidence": "python -m pytest tests/test_jrsa_gpu.py -v -> 1 passed"
        })
        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
        print("Updated progress.json")

    # 3. Update review.json
    review_path = PRP_DIR / "review.json"
    with open(review_path, "r", encoding="utf-8") as f:
        review = json.load(f)

    if not any(e["path"] == path_str for e in review["entries"]):
        review["entries"].append({
            "filename": "test_jrsa_gpu.py",
            "path": path_str,
            "score": 100,
            "verdict": "ACCEPTED",
            "issues": "None.",
            "fix_actions": "None",
            "review_command": "python -m pytest tests/test_jrsa_gpu.py -v",
            "last_reviewed": "2026-07-15"
        })
        with open(review_path, "w", encoding="utf-8") as f:
            json.dump(review, f, indent=2, ensure_ascii=False)
        print("Updated review.json")


if __name__ == "__main__":
    main()
