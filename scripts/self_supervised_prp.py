#!/usr/bin/env python3
"""
self_supervised_prp.py — Self-Supervised and Self-Evolving PRP Loop Coordinator
This script automates the verification (auto-review) of open backlog tasks,
handles schema-aware reconciliation, and proposes system modifications (auto-adapt).

Actions:
  python scripts/self_supervised_prp.py --action verify
  python scripts/self_supervised_prp.py --action adapt
  python scripts/self_supervised_prp.py --action sync
"""

import os
import sys
import json
import subprocess
import argparse
import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_DIR = REPO_ROOT / "artifacts/developer"
PLANS_JSON = DEV_DIR / "plans.json"
PROGRESS_JSON = DEV_DIR / "progress.json"
REVIEW_JSON = DEV_DIR / "review.json"
ADAPT_JSON = DEV_DIR / "adapt.json"

def load_json(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 3, "entries": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def run_verify(force: bool = False):
    """
    Self-Supervised Review Loop:
    Finds open items with a review_command, executes them, and automatically grades the state.
    """
    print("=== Phase: Auto-Verify ===")
    review_data = load_json(REVIEW_JSON)
    progress_data = load_json(PROGRESS_JSON)
    
    review_entries = review_data.get("entries", [])
    progress_entries = progress_data.get("entries", [])
    
    updated = False
    
    for i, entry in enumerate(review_entries):
        cmd = entry.get("review_command", "")
        # Skip if empty, placeholder, or already verified successfully (unless --force is passed)
        if not cmd or "TODO" in cmd or (not force and entry.get("verdict") == "ACCEPTED"):
            continue
            
        # Clean up command string if it contains historical output logs
        run_cmd = cmd.split("->")[0].strip()
        print(f"Executing review command for {entry.get('path')}:")
        print(f"  $ {run_cmd}")
        
        try:
            # Run command relative to repo root
            result = subprocess.run(
                run_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=120
            )
            
            output_snippet = result.stdout[-800:].strip()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if result.returncode == 0:
                print("  => SUCCESS!")
                entry["score"] = 100
                entry["verdict"] = "ACCEPTED"
                entry["issues"] = ""
                entry["evidence"] = f"Auto-verified at {timestamp} via command success:\n{output_snippet}"
            else:
                print(f"  => FAILED (code {result.returncode})")
                entry["score"] = 50
                entry["verdict"] = "NOT ACCEPTED"
                entry["issues"] = f"Command failed at {timestamp} with exit code {result.returncode}:\n{output_snippet}"
                
            entry["last_reviewed"] = timestamp.split()[0]
            updated = True
            
            # Sync back to progress.json
            for p_entry in progress_entries:
                if p_entry.get("path") == entry.get("path"):
                    p_entry["score"] = entry["score"]
                    p_entry["status"] = "done" if result.returncode == 0 else "in-progress"
                    p_entry["last_verified"] = entry["last_reviewed"]
                    p_entry["evidence"] = entry["evidence"]
                    
        except subprocess.TimeoutExpired:
            print("  => TIMEOUT EXPIRED")
            entry["verdict"] = "NOT ACCEPTED"
            entry["issues"] = f"Command execution timed out after 120s"
            updated = True
        except Exception as e:
            print(f"  => ERROR: {e}")
            entry["verdict"] = "NOT ACCEPTED"
            entry["issues"] = f"Error during execution: {e}"
            updated = True

    if updated:
        save_json(REVIEW_JSON, review_data)
        save_json(PROGRESS_JSON, progress_data)
        print("PRP review state updated with self-supervised command execution outputs.")
    else:
        print("No active review items to verify.")

def run_adapt():
    """
    Self-Evolving Loop:
    Analyzes review issues or developer actions to automatically propose AGENTS.md rulesets/skills.
    """
    print("=== Phase: Auto-Adapt ===")
    review_data = load_json(REVIEW_JSON)
    adapt_data = load_json(ADAPT_JSON)
    
    proposed_tweaks = adapt_data.get("proposed_tweaks", [])
    review_entries = review_data.get("entries", [])
    
    new_proposals = False
    
    # Example adaptation rule: If a review entry failed due to an obvious issue,
    # generate a proposed tweak to prevent future agent mistakes
    for entry in review_entries:
        issues = entry.get("issues", "")
        if "NOT ACCEPTED" in entry.get("verdict", "") and issues:
            # Detect pattern: e.g. NameError, missing imports
            rule_tweak = None
            if "NameError" in issues:
                rule_tweak = "Ensure all python variables are defined and verify scope before run execution."
            elif "FileNotFoundError" in issues or "does not exist" in issues:
                rule_tweak = "Verify paths exist before performing relative directory lookups."
            
            if rule_tweak:
                # Check if this rule is already proposed
                exists = any(p.get("change") == rule_tweak for p in proposed_tweaks)
                if not exists:
                    print(f"Proposing adaptive rule for {entry.get('path')}: '{rule_tweak}'")
                    proposed_tweaks.append({
                        "target": ".agents/AGENTS.md",
                        "change": rule_tweak,
                        "status": "proposed",
                        "evidence": f"Auto-generated based on test failures in {entry.get('path')}."
                    })
                    new_proposals = True
                    
    if new_proposals:
        adapt_data["proposed_tweaks"] = proposed_tweaks
        save_json(ADAPT_JSON, adapt_data)
        print("Proposed adaptive tweaks added to adapt.json.")
    else:
        print("No new adaptive rules proposed.")

def run_sync():
    """
    Reconciles paths across plans, progress, and review JSON files.
    """
    print("=== Phase: Sync ===")
    progress_data = load_json(PROGRESS_JSON)
    review_data = load_json(REVIEW_JSON)
    
    progress_paths = {e.get("path") for e in progress_data.get("entries", []) if e.get("path")}
    review_paths = {e.get("path") for e in review_data.get("entries", []) if e.get("path")}
    
    missing_in_review = progress_paths - review_paths
    missing_in_progress = review_paths - progress_paths
    
    updated = False
    if missing_in_review:
        print(f"Reconciling review.json: adding {len(missing_in_review)} missing paths from progress.json")
        for path in missing_in_review:
            # Find in progress
            for pe in progress_data["entries"]:
                if pe.get("path") == path:
                    review_data["entries"].append({
                        "filename": pe.get("filename"),
                        "path": path,
                        "score": "unreviewed",
                        "verdict": "NOT REVIEWED",
                        "issues": "",
                        "fix_actions": "",
                        "review_command": pe.get("review_command", ""),
                        "last_reviewed": "",
                        "evidence": ""
                    })
        updated = True
        
    if missing_in_progress:
        print(f"Reconciling progress.json: adding {len(missing_in_progress)} missing paths from review.json")
        for path in missing_in_progress:
            for re in review_data["entries"]:
                if re.get("path") == path:
                    progress_data["entries"].append({
                        "filename": re.get("filename"),
                        "purpose": "Synchronized from review.json",
                        "score": 0,
                        "tbis": 0,
                        "tbds": 0,
                        "warnings": "",
                        "path": path,
                        "status": "in-progress",
                        "last_verified": "",
                        "evidence": ""
                    })
        updated = True
        
    if updated:
        save_json(REVIEW_JSON, review_data)
        save_json(PROGRESS_JSON, progress_data)
        print("Reconciliation complete. Path mapping is now synchronized.")
    else:
        print("All PRP table paths are in sync.")

def main():
    parser = argparse.ArgumentParser(description="Self-Supervised & Self-Evolving PRP Loop Coordinator")
    parser.add_argument("--action", choices=["verify", "adapt", "sync", "all"], default="all",
                        help="The PRP loop phase action to execute")
    parser.add_argument("--force", action="store_true",
                        help="Force execution of all review commands, ignoring existing ACCEPTED verdicts")
    args = parser.parse_args()
    
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.action in ["sync", "all"]:
        run_sync()
    if args.action in ["verify", "all"]:
        run_verify(force=args.force)
    if args.action in ["adapt", "all"]:
        run_adapt()

if __name__ == "__main__":
    main()

