#!/usr/bin/env python3
"""Record the completed Stage 4B receipt as a Labyrinth evidence node."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = Path("D:/analysis/handout4_stage4b_linear_map/stage4b_receipt.json")
DEFAULT_NODE = (
    REPO_ROOT
    / "artifacts"
    / ".lab"
    / "handout-4-stage4b-full-corpus-linear-map-20260810.json"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--node", type=Path, default=DEFAULT_NODE)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    receipt_hash = hashlib.sha256(args.receipt.read_bytes()).hexdigest()
    node = {
        "schema_version": 3,
        "node_id": "handout-4-stage4b-full-corpus-linear-map-20260810",
        "kind": "evidence",
        "title": "Handout 4B full-corpus linear WHAT x WHEN map",
        "status": "complete",
        "action": "Progress",
        "claim": {
            "text": "The authorized Stage 4B linear WHAT x WHEN map was executed on the frozen catalogued corpus using raw SUA, MUAe, and LFP tensors with grouped folds and exchangeability-matched nulls.",
            "falsifier": "The claim is superseded if the frozen corpus, Stage 4A geometry, Stage 4A.1 alignment contract, representation contract, model, or null scheme changes.",
        },
        "evidence": {
            "receipt": str(args.receipt),
            "receipt_sha256": receipt_hash,
            "outputs": receipt.get("outputs", {}),
            "counts": receipt.get("counts", {}),
            "authorization": receipt.get("authorization", {}),
        },
        "relations": [
            {
                "relation": "preserves",
                "target": "handout-4-stage4a-design-corpus-audit-20260810",
            },
            {
                "relation": "preserves",
                "target": "handout-4a1-data-access-and-alignment-gate-20260810",
            },
            {
                "relation": "tests",
                "target": "frontal_omission_decodability",
            },
            {
                "relation": "does_not_authorize",
                "target": "M2_M3_M4",
            },
        ],
        "frozen_corpus": receipt.get("frozen_corpus", {}),
        "coarse_windows_ms": receipt.get("coarse_windows_ms", {}),
        "null": receipt.get("null", {}),
        "git_sha": receipt.get("git_sha"),
        "falsifier": "Receipt or input hashes differ from the signed Stage 4B execution.",
    }
    args.node.parent.mkdir(parents=True, exist_ok=True)
    args.node.write_text(json.dumps(node, indent=2), encoding="utf-8")
    print(json.dumps({"node": str(args.node), "receipt_sha256": receipt_hash}))


if __name__ == "__main__":
    main()
