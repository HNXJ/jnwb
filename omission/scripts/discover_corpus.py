#!/usr/bin/env python
"""Discover the current corpus topology and emit a machine-readable receipt.

This script replaces every remembered path and count in project doctrine. It resolves
state; it does not encode it. There is no absolute path, subject name, session count,
or file count hardcoded anywhere below -- by design, because every such constant in the
previous harness had gone stale.

It reports inconsistencies. It never reconciles them.

Exit codes (--check):
    0   topology resolved; required consistency checks pass
    1   topology resolved, but a blocking scientific/readiness mismatch exists
    2   discovery or configuration failure -- the machinery itself did not work

Without --check the script always exits 0 if it produced a manifest, so it can be used
to refresh the receipt without gating.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2

# Session stems look like: sub-<subject>_ses-<session>_rec
# Parsed, never enumerated: subject identities are discovered from disk.
STEM_RE = re.compile(r"^sub-(?P<subject>[^_]+)_ses-(?P<session>[^_]+)(?:_(?P<suffix>.+))?$")

# Environment overrides documented in the project harness.
ENV_KEYS = {
    "nwb_dir": "OMISSION_NWB_DIR",
    "tfr_dir": "OMISSION_TFR_DIR",
    "metadata_dir": "OMISSION_META_DIR",
}

SEVERITY_BLOCKING = "blocking"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


class Mismatch(dict):
    def __init__(self, kind: str, detail: str, severity: str) -> None:
        super().__init__(kind=kind, detail=detail, severity=severity)


# --------------------------------------------------------------------------- roots


def _resolve_roots(repo_root: Path | None = None) -> tuple[dict[str, dict[str, Any]], list[Mismatch]]:
    """Resolve data roots, recording which mechanism produced each one.

    Order: environment override > jnwb.paths > unresolved. An unresolved or missing
    root is a fact about today, reported as a mismatch -- never an exception.
    """
    mismatches: list[Mismatch] = []
    roots: dict[str, dict[str, Any]] = {}

    # sys.path[0] is this script's directory, not the repo, so an in-tree (non-installed)
    # jnwb is invisible without this. Prepending the repo root makes discovery work from
    # a source checkout as well as an installed environment.
    if repo_root is not None and str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    jnwb_paths = None
    try:
        from jnwb import paths as jnwb_paths  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        mismatches.append(
            Mismatch(
                "jnwb_unavailable",
                f"could not import jnwb.paths ({exc.__class__.__name__}: {exc}); "
                "falling back to environment overrides only",
                SEVERITY_WARNING,
            )
        )

    accessors = {"nwb_dir": "nwb_dir", "tfr_dir": "tfr_dir", "metadata_dir": "metadata_dir"}

    for name, env_key in ENV_KEYS.items():
        value: str | None = None
        mechanism = "unresolved"

        env_value = os.environ.get(env_key)
        if env_value:
            value, mechanism = env_value, f"env:{env_key}"
        elif jnwb_paths is not None:
            accessor = getattr(jnwb_paths, accessors[name], None)
            if callable(accessor):
                try:
                    resolved = accessor()
                    if resolved:
                        value, mechanism = str(resolved), f"jnwb.paths.{accessors[name]}()"
                except Exception as exc:
                    mismatches.append(
                        Mismatch(
                            "root_resolution_failed",
                            f"jnwb.paths.{accessors[name]}() raised "
                            f"{exc.__class__.__name__}: {exc}",
                            SEVERITY_WARNING,
                        )
                    )

        exists = bool(value) and Path(value).is_dir()
        roots[name] = {
            "path": value,
            "resolved_from": mechanism,
            "exists": exists,
        }

        if value is None:
            mismatches.append(
                Mismatch(
                    "root_unresolved",
                    f"{name} could not be resolved from {env_key} or jnwb.paths",
                    SEVERITY_BLOCKING if name == "nwb_dir" else SEVERITY_WARNING,
                )
            )
        elif not exists:
            mismatches.append(
                Mismatch(
                    "root_missing",
                    f"{name} resolved to {value!r} ({mechanism}) which does not exist",
                    SEVERITY_BLOCKING if name == "nwb_dir" else SEVERITY_WARNING,
                )
            )

    return roots, mismatches


# ------------------------------------------------------------------------ sessions


def _parse_stem(stem: str) -> tuple[str | None, str | None]:
    match = STEM_RE.match(stem)
    if not match:
        return None, None
    return match.group("subject"), match.group("session")


def _scan_nwb(nwb_dir: Path) -> tuple[dict[str, dict[str, Any]], list[Mismatch]]:
    sessions: dict[str, dict[str, Any]] = {}
    mismatches: list[Mismatch] = []

    for path in sorted(nwb_dir.glob("*.nwb")):
        stem = path.stem
        subject, session_id = _parse_stem(stem)
        if subject is None:
            mismatches.append(
                Mismatch(
                    "unparseable_stem",
                    f"{path.name} does not match the sub-<subject>_ses-<session> convention",
                    SEVERITY_WARNING,
                )
            )
        session_prefix = f"sub-{subject}_ses-{session_id}" if subject is not None else stem
        sessions[stem] = {
            "stem": stem,
            "session_prefix": session_prefix,
            "subject": subject,
            "session_id": session_id,
            "nwb_path": str(path),
            "nwb_ok": True,
            "nwb_bytes": path.stat().st_size,
            "sidecar_ok": None,
            "tfr_ok": None,
            "tfr_n_files": 0,
            "tfr_formats": [],
        }
    return sessions, mismatches


def _scan_tfr(tfr_dir: Path, sessions: dict[str, dict[str, Any]]) -> int:
    """Attribute TFR products to sessions by session_prefix. Returns total files seen.

    2026-08-14: was matching on the raw NWB `stem` (which keeps a trailing `_rec` for most
    C31o/V198o sessions), but TFR filenames are built from `session_prefix` (sub-<subj>_ses-<id>,
    `_rec` already stripped -- see nwb_catalog.json's own field of the same name) and never carry
    `_rec`. `path.name.startswith(stem)` therefore silently failed to match any `_rec` session,
    undercounting tfr_ok to 10/22 instead of 22/22 -- exactly the kind of session-prefix mismatch
    `omission-data` warns about. Matching on session_prefix instead fixes this.
    """
    total = 0
    counts: Counter[str] = Counter()
    formats: dict[str, set[str]] = {}
    prefix_to_stems: dict[str, list[str]] = {}
    for stem, meta in sessions.items():
        prefix_to_stems.setdefault(meta.get("session_prefix", stem), []).append(stem)

    for path in sorted(tfr_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".npy", ".npz"}:
            continue
        total += 1
        # Longest matching session_prefix wins, so sub-X_ses-1 does not swallow sub-X_ses-10.
        owner = None
        for prefix in prefix_to_stems:
            if path.name.startswith(prefix) and (owner is None or len(prefix) > len(owner)):
                owner = prefix
        if owner is not None:
            counts[owner] += 1
            formats.setdefault(owner, set()).add(path.suffix.lower().lstrip("."))

    for stem, meta in sessions.items():
        prefix = meta.get("session_prefix", stem)
        meta["tfr_n_files"] = counts.get(prefix, 0)
        meta["tfr_formats"] = sorted(formats.get(prefix, set()))
        meta["tfr_ok"] = counts.get(prefix, 0) > 0

    return total


def _scan_sidecars(metadata_dir: Path, sessions: dict[str, dict[str, Any]]) -> None:
    for stem, meta in sessions.items():
        session_dir = metadata_dir / stem
        meta["sidecar_ok"] = session_dir.is_dir() and any(session_dir.iterdir())


# ------------------------------------------------------------------- cross-checking


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "t"}


def _crosscheck_readiness(
    repo_root: Path, sessions: dict[str, dict[str, Any]], tfr_files_on_disk: int
) -> list[Mismatch]:
    """Compare the readiness table against what was just discovered on disk.

    This is the check that surfaced the 2026-08-12 state: a readiness table reporting
    zero TFR-ready sessions while hundreds of arrays sat on disk. It reports; it does
    not choose a side.
    """
    import csv

    mismatches: list[Mismatch] = []
    readiness_path = repo_root / "artifacts" / "data" / "session_readiness.csv"
    if not readiness_path.is_file():
        mismatches.append(
            Mismatch("readiness_absent", f"{readiness_path} not found", SEVERITY_WARNING)
        )
        return mismatches

    with readiness_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    table_stems = {row.get("stem", "") for row in rows if row.get("stem")}
    disk_stems = set(sessions)

    for stem in sorted(disk_stems - table_stems):
        mismatches.append(
            Mismatch("session_absent_from_readiness", stem, SEVERITY_BLOCKING)
        )
    for stem in sorted(table_stems - disk_stems):
        mismatches.append(
            Mismatch("readiness_row_without_nwb", stem, SEVERITY_BLOCKING)
        )

    table_tfr_ok = sum(1 for row in rows if _truthy(row.get("tfr_ok")))
    disk_tfr_ok = sum(1 for meta in sessions.values() if meta.get("tfr_ok"))

    if table_tfr_ok == 0 and tfr_files_on_disk > 0:
        mismatches.append(
            Mismatch(
                "readiness_gate_unsatisfiable",
                f"readiness reports tfr_ok on 0 of {len(rows)} sessions while "
                f"{tfr_files_on_disk} TFR arrays exist under the resolved tfr_dir; "
                "every TFR-gated figure is blocked until this is explained",
                SEVERITY_BLOCKING,
            )
        )
    elif table_tfr_ok != disk_tfr_ok:
        mismatches.append(
            Mismatch(
                "readiness_tfr_count_disagrees",
                f"readiness tfr_ok={table_tfr_ok}, discovered tfr_ok={disk_tfr_ok}",
                SEVERITY_BLOCKING,
            )
        )

    return mismatches


def _crosscheck_catalog(repo_root: Path, sessions: dict[str, dict[str, Any]]) -> list[Mismatch]:
    mismatches: list[Mismatch] = []
    catalog_path = repo_root / "artifacts" / "data" / "nwb_catalog.json"
    if not catalog_path.is_file():
        mismatches.append(
            Mismatch("catalog_absent", f"{catalog_path} not found", SEVERITY_WARNING)
        )
        return mismatches

    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as exc:
        mismatches.append(
            Mismatch("catalog_unreadable", f"{exc.__class__.__name__}: {exc}", SEVERITY_WARNING)
        )
        return mismatches

    declared = catalog.get("n_files")
    if isinstance(declared, int) and declared != len(sessions):
        mismatches.append(
            Mismatch(
                "catalog_count_disagrees",
                f"nwb_catalog.json n_files={declared}, discovered {len(sessions)}",
                SEVERITY_BLOCKING,
            )
        )

    declared_dir = catalog.get("nwb_dir")
    if declared_dir and sessions:
        discovered_dir = str(Path(next(iter(sessions.values()))["nwb_path"]).parent)
        if Path(declared_dir) != Path(discovered_dir):
            mismatches.append(
                Mismatch(
                    "catalog_root_disagrees",
                    f"nwb_catalog.json nwb_dir={declared_dir!r}, discovered {discovered_dir!r}",
                    SEVERITY_WARNING,
                )
            )
    return mismatches


# ------------------------------------------------------------------------ manifest


def build_manifest(repo_root: Path) -> dict[str, Any]:
    roots, mismatches = _resolve_roots(repo_root)
    sessions: dict[str, dict[str, Any]] = {}
    tfr_files_on_disk = 0

    nwb_root = roots["nwb_dir"]
    if nwb_root["exists"]:
        sessions, stem_mismatches = _scan_nwb(Path(nwb_root["path"]))
        mismatches.extend(stem_mismatches)
        if not sessions:
            mismatches.append(
                Mismatch(
                    "no_sessions_discovered",
                    f"no *.nwb under resolved nwb_dir {nwb_root['path']!r}",
                    SEVERITY_BLOCKING,
                )
            )

    tfr_root = roots["tfr_dir"]
    if sessions and tfr_root["exists"]:
        tfr_files_on_disk = _scan_tfr(Path(tfr_root["path"]), sessions)

    meta_root = roots["metadata_dir"]
    if sessions and meta_root["exists"]:
        _scan_sidecars(Path(meta_root["path"]), sessions)

    if sessions:
        mismatches.extend(_crosscheck_readiness(repo_root, sessions, tfr_files_on_disk))
        mismatches.extend(_crosscheck_catalog(repo_root, sessions))

    subjects = sorted({m["subject"] for m in sessions.values() if m["subject"]})
    blocking = [m for m in mismatches if m["severity"] == SEVERITY_BLOCKING]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "roots": roots,
        "totals": {
            "n_sessions": len(sessions),
            "n_subjects": len(subjects),
            "subjects": subjects,
            "n_nwb_ok": sum(1 for m in sessions.values() if m["nwb_ok"]),
            "n_sidecar_ok": sum(1 for m in sessions.values() if m["sidecar_ok"]),
            "n_tfr_ok": sum(1 for m in sessions.values() if m["tfr_ok"]),
            "n_tfr_files_on_disk": tfr_files_on_disk,
        },
        "sessions": [sessions[k] for k in sorted(sessions)],
        "mismatches": sorted(
            mismatches, key=lambda m: (m["severity"], m["kind"], m["detail"])
        ),
        "blocking": len(blocking) > 0,
        "n_blocking": len(blocking),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--check", action="store_true", help="exit non-zero per exit-code table")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        manifest = build_manifest(args.repo_root)
    except Exception as exc:  # discovery machinery itself failed
        print(f"discover_corpus: FAILED {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 2

    out = args.out or (args.repo_root / "artifacts" / "data" / "corpus_manifest.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    if not args.quiet:
        totals = manifest["totals"]
        print(f"sessions={totals['n_sessions']} subjects={totals['n_subjects']} "
              f"tfr_ok={totals['n_tfr_ok']} tfr_files={totals['n_tfr_files_on_disk']}")
        for mismatch in manifest["mismatches"]:
            print(f"  [{mismatch['severity']}] {mismatch['kind']}: {mismatch['detail']}")
        print(f"-> {out}")

    if not args.check:
        return 0

    # Discovery machinery failure: the primary root never resolved at all.
    if not manifest["roots"]["nwb_dir"]["exists"]:
        return 2
    return 1 if manifest["blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
