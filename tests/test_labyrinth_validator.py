"""Tests for scripts/validate_labyrinth_claim_status.py (Sol/Hamm Handout 2, P2 item).

Two kinds of coverage:
1. Mechanism correctness on synthetic fixtures -- proves the validator actually detects the
   failure pattern (confirmed target of a contradicts/supersedes edge from a confirmed source
   that never had its own status updated), independent of the real 376-file corpus.
2. Regression guard on the 3 specific nodes fixed 2026-08-10 (the ones this same audit found
   stuck at status:confirmed despite an existing, unactioned contradicts edge) -- these must
   stay non-confirmed unless someone deliberately re-derives the primary census and re-confirms
   them with a real receipt.

Does NOT assert zero violations across the full artifacts/.lab/ corpus -- the validator found
23 more (pre-existing, not part of this fix), which is a real, useful finding but a much larger
backlog item than this task's scope. That count is reported, not gated, so this suite stays
green while the backlog is worked down separately.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_labyrinth_claim_status import build_status_index, find_violations  # noqa: E402


def _write_node(tmp_path: Path, name: str, doc: dict) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


class TestValidatorMechanism:
    def test_detects_confirmed_target_of_confirmed_contradiction(self, tmp_path, monkeypatch):
        import validate_labyrinth_claim_status as mod

        monkeypatch.setattr(mod, "LAB_DIR", tmp_path)
        _write_node(tmp_path, "source", {
            "id": "source-node", "status": "confirmed",
            "edges": [{"to": "target-node", "relation": "contradicts"}],
        })
        _write_node(tmp_path, "target", {"id": "target-node", "status": "confirmed"})

        all_nodes = mod._load_all_nodes()
        violations, dangling = mod.find_violations(all_nodes)

        assert len(violations) == 1
        assert violations[0]["target_id"] == "target-node"
        assert violations[0]["source_id"] == "source-node"
        assert not dangling

    def test_no_violation_when_target_already_demoted(self, tmp_path, monkeypatch):
        import validate_labyrinth_claim_status as mod

        monkeypatch.setattr(mod, "LAB_DIR", tmp_path)
        _write_node(tmp_path, "source", {
            "id": "source-node", "status": "confirmed",
            "edges": [{"to": "target-node", "relation": "contradicts"}],
        })
        _write_node(tmp_path, "target", {"id": "target-node", "status": "retracted"})

        all_nodes = mod._load_all_nodes()
        violations, _ = mod.find_violations(all_nodes)
        assert not violations

    def test_no_violation_when_source_not_confirmed(self, tmp_path, monkeypatch):
        import validate_labyrinth_claim_status as mod

        monkeypatch.setattr(mod, "LAB_DIR", tmp_path)
        _write_node(tmp_path, "source", {
            "id": "source-node", "status": "provisional",
            "edges": [{"to": "target-node", "relation": "contradicts"}],
        })
        _write_node(tmp_path, "target", {"id": "target-node", "status": "confirmed"})

        all_nodes = mod._load_all_nodes()
        violations, _ = mod.find_violations(all_nodes)
        assert not violations, "an unconfirmed source's contradiction should not force a demotion"

    def test_implicit_from_resolves_to_the_defining_document(self, tmp_path, monkeypatch):
        """Real corpus edges usually omit 'from' entirely -- the source is implicitly the
        document the edge is defined in (see census_provenance_synthetic_finding_20260728.json)."""
        import validate_labyrinth_claim_status as mod

        monkeypatch.setattr(mod, "LAB_DIR", tmp_path)
        _write_node(tmp_path, "source", {
            "id": "source-node", "status": "confirmed",
            "edges": [{"to": "target-node", "relation": "supersedes"}],  # no "from" key
        })
        _write_node(tmp_path, "target", {"id": "target-node", "status": "confirmed"})

        all_nodes = mod._load_all_nodes()
        violations, _ = mod.find_violations(all_nodes)
        assert len(violations) == 1
        assert violations[0]["source_id"] == "source-node"

    def test_dangling_edge_reported_separately_not_as_violation(self, tmp_path, monkeypatch):
        import validate_labyrinth_claim_status as mod

        monkeypatch.setattr(mod, "LAB_DIR", tmp_path)
        _write_node(tmp_path, "source", {
            "id": "source-node", "status": "confirmed",
            "edges": [{"to": "nonexistent-node", "relation": "contradicts"}],
        })

        all_nodes = mod._load_all_nodes()
        violations, dangling = mod.find_violations(all_nodes)
        assert not violations
        assert len(dangling) == 1
        assert dangling[0]["to"] == "nonexistent-node"

    def test_nested_claim_ids_are_indexed(self, tmp_path, monkeypatch):
        import validate_labyrinth_claim_status as mod

        monkeypatch.setattr(mod, "LAB_DIR", tmp_path)
        _write_node(tmp_path, "onenode", {
            "id": "container",
            "claims": [
                {"id": "claim-a", "status": "confirmed"},
                {"id": "claim-b", "status": "confirmed"},
            ],
            "edges": [{"from": "claim-a", "to": "claim-b", "relation": "contradicts"}],
        })
        all_nodes = mod._load_all_nodes()
        violations, _ = mod.find_violations(all_nodes)
        assert len(violations) == 1
        assert violations[0]["target_id"] == "claim-b"


class TestKnownFixedNodesStayFixed:
    """Regression guard: these 3 nodes were found status=confirmed despite an existing,
    unactioned contradicts edge from census_provenance_synthetic_finding_20260728.json, and
    were fixed 2026-08-10. They must not silently revert to confirmed."""

    FIXED_NODE_IDS = [
        "analysis-clopper-pearson-confidence-intervals",
        "analysis-hierarchical-inference-mixed-effects",
        "analysis-exploratory-vs-headline-evidence-hierarchy",
    ]

    @pytest.mark.parametrize("node_id", FIXED_NODE_IDS)
    def test_not_confirmed(self, node_id):
        path = REPO_ROOT / "artifacts" / ".lab" / f"{node_id}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["status"] != "confirmed", (
            f"{node_id} reverted to status=confirmed -- it depends on the retracted 421/8597="
            f"4.90% synthetic census (context/docs/CONTEXT.md Section 8) and must not be "
            f"re-confirmed without a real re-derivation."
        )


class TestValidatorCliRunsCleanlyOnRealCorpus:
    def test_cli_runs_and_reports_json(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "validate_labyrinth_claim_status.py"), "--json"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
        )
        # exit 1 is EXPECTED here (pre-existing backlog violations in the real corpus) -- this
        # test only proves the CLI runs without crashing and emits well-formed JSON.
        assert result.returncode in (0, 1), result.stderr
        payload = json.loads(result.stdout)
        assert "violations" in payload
        assert "dangling_edges" in payload
        fixed_ids = set(TestKnownFixedNodesStayFixed.FIXED_NODE_IDS)
        violated_ids = {v["target_id"] for v in payload["violations"]}
        assert not (fixed_ids & violated_ids), (
            f"the specifically-fixed nodes reappeared in the violation list: "
            f"{fixed_ids & violated_ids}"
        )
