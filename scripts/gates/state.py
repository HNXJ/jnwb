"""State gates: file head, computational contract, fact predicates, receipt provenance."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parents[2]
from scripts.gates.boundary import _run_git


def validate_receipt_provenance(claim_name: str, receipt_path: Union[str, Path]) -> Tuple[bool, str]:
    """Receipt provenance check (not a numbered preflight gate; argument-driven).

    
    Verifies that an empirical receipt exists on disk, is readable, and is non-empty.
    IMPORTANT EPISTEMIC DISTINCTION: Receipt existence is provenance/artifact validation,
    NOT empirical scientific verification. True scientific verification requires verified code,
    valid nulls, and exact claim-to-estimator linkage.
    """
    path = Path(receipt_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
        
    if not path.exists():
        return False, f"MISSING_RECEIPT: Claim '{claim_name}' references non-existent receipt artifact: {path}"
        
    if path.stat().st_size == 0:
        return False, f"EMPTY_RECEIPT: Claim '{claim_name}' references zero-byte artifact: {path}"
        
    return True, f"PROVENANCE_VALID: Claim '{claim_name}' artifact exists: {path} ({path.stat().st_size} bytes)"


def check_state_file_head(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 20 (State File Head): a present artifacts/state.md records the live HEAD.

    Check-only. The generator runs this harness to fill in its gate rows, so a gate that
    regenerated the file would recurse. It reads the recorded HEAD with the generator's own
    parser and compares it with ``git rev-parse HEAD``. An absent file passes: the file is
    generated per tree and gitignored, so a fresh checkout correctly has none. A file with no
    HEAD row, or a HEAD git cannot resolve, fails, because unknown is not current.
    """
    from scripts import reconstruct_state

    root = repo_root or REPO_ROOT
    relative = reconstruct_state.STATE_PATH.relative_to(reconstruct_state.REPO_ROOT)
    path = root / relative
    if not path.is_file():
        return []
    name = relative.as_posix()
    regenerate = "Run: python scripts/reconstruct_state.py"
    recorded = reconstruct_state.recorded_head(path.read_text(encoding="utf-8"))
    if recorded is None:
        return [f"{name} records no HEAD row, so nothing can say it is current. {regenerate}"]
    done = _run_git(root, "rev-parse", "HEAD")
    live = done.stdout.strip()
    if done.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", live):
        return [f"{name} records HEAD {recorded}, and git could not resolve the live HEAD "
                f"(exit {done.returncode}), so the file cannot be shown current. {regenerate}"]
    if recorded != live:
        return [f"{name} was generated at {recorded} and HEAD is now {live}. {regenerate}"]
    return []


def check_computational_contract() -> List[str]:
    """Gate 21 (Computational Contract): execution switches select, precision requests are
    honoured, and every export has a recorded computational order.

    Runs the three checks of `scripts/computational_contract_gate.py` on the imported package.
    The suite runs them too (`tests/test_computational_contract_gate.py`), but an export added
    without a recorded order left the suite red while every gate here stayed green, and the
    gates are what the build job and a release read first. Each violation is prefixed with the
    check that found it; a check that raised is reported as that check's violation.
    """
    import jnwb
    from scripts import computational_contract_gate

    return [
        f"{name}: {violation}"
        for name, violations, _ in computational_contract_gate.run_checks(jnwb)
        for violation in violations
    ]


#: What gate 22 last read and counted, for its pass line; empty until it has run.
_FACT_REPORT: Dict[str, Any] = {}


def check_fact_predicates() -> List[str]:
    """Gate 22 (Fact Predicates): no typed fact is VIOLATED on the generated fact graph.

    Runs `scripts/fact_gate.py` in process: the graph is built from this tree, never read
    from a file that may be stale. Each VIOLATED fact is one violation carrying its reasons.
    UNHELD facts pass and are counted in the pass line, each already naming the live item that
    will hold it. A fact held by another gate or a test is resolved, not re-run, so its truth
    is that gate's or the suite's.
    """
    from scripts import fact_gate

    source, results = fact_gate.run()
    _FACT_REPORT.clear()
    _FACT_REPORT.update(fact_gate.summary(results))
    _FACT_REPORT["source"] = Path(source).resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    return [f"{fact_id}: {'; '.join(reasons)}"
            for fact_id, status, reasons in results if status == fact_gate.VIOLATED]
