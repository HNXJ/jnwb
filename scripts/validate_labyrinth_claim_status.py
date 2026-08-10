#!/usr/bin/env python3
"""Labyrinth graph validator: flags confirmed nodes/claims that are the target of a
contradicts/supersedes edge from another confirmed source but never had their own status
updated to acknowledge it.

WHY THIS EXISTS
    artifacts/.lab/agent-harness-audit-20260810.json (claim-p0-supersession-not-enforced-on-
    target-node): the graph schema supports supersession semantically (contradicts/supersedes/
    corrects edge relations, all in real use) but nothing enforced it onto the target node's
    own status field. Concrete case: census_provenance_synthetic_finding_20260728.json
    explicitly said a sibling node "should be demoted" -- it stayed status:confirmed for
    two weeks. This script is the automated check that was missing; Sol/Hamm's Handout 2
    explicitly asked for "the validator raising an error or at minimum a blocking diagnostic"
    rather than relying on an agent noticing by hand.

WHAT IT CHECKS
    For every edge with relation/type in {"contradicts", "supersedes"}, if the SOURCE node's
    own status is "confirmed" (i.e. the contradiction/supersession claim is itself trusted) and
    the TARGET node/claim's status is STILL "confirmed", that's a violation: the target is
    asserting standing it has not earned given a trusted claim says otherwise.

SCOPE AND LIMITS
    Status is resolved per top-level node id AND per nested claims[].id, since both are used as
    edge targets across this corpus. A target id that resolves to nothing in the corpus is
    reported separately (dangling edge) but is not itself a status violation.
    This does not (yet) attempt corrections=type edges or a full multi-hop transitive check --
    scoped to the specific failure mode found in the audit (direct contradicts/supersedes).

USAGE
    python scripts/validate_labyrinth_claim_status.py           # print violations, exit 1 if any
    python scripts/validate_labyrinth_claim_status.py --json     # machine-readable output
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
LAB_DIR = REPO_ROOT / "artifacts" / ".lab"

FLAGGED_RELATIONS = {"contradicts", "supersedes"}


def _display_path(path: Path) -> str:
    """Relative-to-repo when possible (real corpus); falls back to the absolute path when the
    file lives outside REPO_ROOT (synthetic test fixtures under a pytest tmp_path)."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_all_nodes() -> List[dict]:
    nodes = []
    for path in sorted(LAB_DIR.glob("*.json")):
        try:
            nodes.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return nodes


def _extract_edges(doc: dict) -> List[dict]:
    edges = list(doc.get("edges") or [])
    edges += list(doc.get("links") or [])
    generated = doc.get("generated")
    if isinstance(generated, dict):
        edges += list(generated.get("links") or [])
    return [e for e in edges if isinstance(e, dict)]


def _edge_relation(edge: dict) -> Optional[str]:
    return edge.get("relation") or edge.get("type") or edge.get("relationship")


def _edge_endpoints(edge: dict, default_source: Optional[str] = None) -> tuple:
    # Many nodes in this corpus omit "from" entirely -- the edge's source is implicitly the
    # document it's defined in (confirmed by inspection of census_provenance_synthetic_finding_
    # 20260728.json's edges, which have "to"/"relation"/"reasoning" but no "from" key at all).
    src = edge.get("from") or edge.get("source") or edge.get("src") or default_source
    dst = edge.get("to") or edge.get("target") or edge.get("dst")
    return src, dst


def build_status_index(all_nodes: List[tuple]) -> Dict[str, dict]:
    """Map every id (top-level node id, and every nested claims[].id) to a small record with
    its status and the file it came from."""
    index: Dict[str, dict] = {}
    for path, doc in all_nodes:
        top_id = doc.get("id")
        if top_id and "status" in doc:
            index[top_id] = {"status": doc.get("status"), "path": _display_path(path), "scope": "node"}
        for claim in doc.get("claims") or []:
            if isinstance(claim, dict) and claim.get("id"):
                index[claim["id"]] = {
                    "status": claim.get("status"),
                    "path": _display_path(path),
                    "scope": "claim",
                }
    return index


def find_violations(all_nodes: List[tuple]) -> List[dict]:
    status_index = build_status_index(all_nodes)
    violations = []
    dangling = []

    for path, doc in all_nodes:
        source_id = doc.get("id")
        source_status = doc.get("status")
        for edge in _extract_edges(doc):
            relation = _edge_relation(edge)
            if relation not in FLAGGED_RELATIONS:
                continue
            src, dst = _edge_endpoints(edge, default_source=source_id)
            # An edge's "from" may reference a specific claim within this same file, or the
            # file's own top-level id -- resolve against the status index first, fall back to
            # this document's own top-level status.
            effective_source_status = status_index.get(src, {}).get("status", source_status)
            if effective_source_status != "confirmed":
                continue  # only trust confirmed sources to demand a demotion
            if dst not in status_index:
                dangling.append({"from": src, "to": dst, "relation": relation, "file": _display_path(path)})
                continue
            target = status_index[dst]
            if target["status"] == "confirmed":
                violations.append({
                    "source_id": src,
                    "source_file": _display_path(path),
                    "relation": relation,
                    "target_id": dst,
                    "target_file": target["path"],
                    "target_status": target["status"],
                })
    return violations, dangling


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    all_nodes = _load_all_nodes()
    violations, dangling = find_violations(all_nodes)

    if args.json:
        print(json.dumps({"violations": violations, "dangling_edges": dangling}, indent=2))
    else:
        print(f"Scanned {len(all_nodes)} .lab node files.")
        print(f"{len(violations)} status-enforcement violation(s), {len(dangling)} dangling contradicts/supersedes edge(s).")
        for v in violations:
            print(
                f"  VIOLATION: {v['target_id']} ({v['target_file']}) is status="
                f"'{v['target_status']}' but is the target of a '{v['relation']}' edge from "
                f"confirmed node {v['source_id']} ({v['source_file']}) -- should not still read "
                f"confirmed."
            )
        for d in dangling:
            print(f"  DANGLING: {d['relation']} edge from {d['from']} -> {d['to']} ({d['file']}) -- target id not found in corpus")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
