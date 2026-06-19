# Shared utilities for Git commands, SHA-256 hashing, and CSV writing.

import csv
import hashlib
import subprocess
from pathlib import Path


def get_git_commit(cwd=None):
    """Retrieve the current Git commit SHA."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def get_git_info(cwd=None):
    """Retrieve the current Git commit SHA and branch name."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        return {"sha": sha, "branch": branch}
    except Exception:
        return {"sha": "unknown", "branch": "unknown"}


def sha256_file(path):
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "hash_unavailable"


def write_csv(path, rows, fieldnames):
    """Write rows to a CSV file at the specified path."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
