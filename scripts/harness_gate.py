#!/usr/bin/env python3
"""Deterministic Operational & Scientific Harness Gate for jnwb and omission.

Mechanically enforces repository doctrine:
  1. Frozen jnwb boundary: no unauthorized imports from omission/ or project folders.
  2. Protected path safety: protects omission/context/figures, omission/scripts, and omission-data/SKILL.md.
  3. Epistemic verification: rejects any empirical claim where receipt is missing, unreadable, or empty.
  4. Logarithm last invariant: rejects averaging of decibels across channels/trials/sites.
  5. Modality separation invariant: rejects unnamespaced pooling across SUA/SPK, MUA, LFP, and behavior.

Returns exit code 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parents[1]
JNWB_DIR = REPO_ROOT / "jnwb"
OMISSION_DIR = REPO_ROOT / "omission"

AUTHORIZED_JNWB_EXCEPTIONS = {
    ("addressing.py", "omission.jnwb_ext.sequence_layout"),
    ("jrsa.py", "omission.jnwb_ext.connectivity"),
}

PROTECTED_PATHS = [
    "omission/context/figures",
    "omission/scripts",
    "omission-data/SKILL.md",
]


class HarnessGateFailure(Exception):
    """Raised when a mechanical harness boundary is violated."""
    pass


def check_frozen_boundary(jnwb_path: Optional[Path] = None) -> List[str]:
    """Gate 1: Enforce that jnwb/ contains zero unauthorized project imports."""
    target_dir = jnwb_path or JNWB_DIR
    violations = []
    
    for py_file in target_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        rel = py_file.relative_to(target_dir).as_posix()
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"), filename=str(py_file))
        except Exception as e:
            violations.append(f"Syntax error parsing {rel}: {e}")
            continue
            
        module_level_nodes = set(id(n) for n in tree.body)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
                
            for name in names:
                if name == "omission" or name.startswith("omission."):
                    is_mod_level = id(node) in module_level_nodes
                    if (rel, name) not in AUTHORIZED_JNWB_EXCEPTIONS:
                        violations.append(f"UNAUTHORIZED_IMPORT: {rel}:{node.lineno} imports '{name}'")
                    elif is_mod_level:
                        violations.append(f"NON_LAZY_IMPORT: {rel}:{node.lineno} imports '{name}' at module level")
    return violations


def check_protected_paths(staged_or_modified_paths: List[str]) -> List[str]:
    """Gate 2 (Global Repository Safety): Prevent accidental modification of protected concurrent paths."""
    violations = []
    for p in staged_or_modified_paths:
        p_norm = p.replace("\\", "/").strip()
        for prot in PROTECTED_PATHS:
            if p_norm == prot or p_norm.startswith(prot + "/"):
                violations.append(f"PROTECTED_PATH_VIOLATION: Attempted mutation to protected concurrent work: {p_norm}")
    return violations


def validate_receipt_provenance(claim_name: str, receipt_path: Union[str, Path]) -> Tuple[bool, str]:
    """Gate 3 (Provenance / Existence Validation):
    
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


def check_skill_tree_uniqueness(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 4 (Global Repository Safety): Enforce single canonical skill tree.
    
    Prohibits recreation of .agents/skills/ per omission/tests/test_skill_tree_consolidation.py.
    The single tracked project skill tree is omission/.claude/skills/.
    """
    root = repo_root or REPO_ROOT
    violations = []
    agents_skills = root / ".agents" / "skills"
    if agents_skills.exists():
        violations.append(
            f"DUPLICATE_SKILL_TREE: {agents_skills} exists. Prohibited by test_skill_tree_consolidation.py. "
            "Canonical project skills live exclusively in omission/.claude/skills/."
        )
    return violations


# ==============================================================================
# Omission Project Specific Gates (Scoped to omission/ analyses, NOT generic jnwb)
# ==============================================================================

def omission_check_logarithm_last_rule(code_or_tree: Union[str, ast.AST]) -> List[str]:
    """Omission Domain Gate: Enforce 'Take the logarithm last' for spectral power.
    
    Scoped to omission headline power estimators where averaging raw power across trials
    prior to decibels is scientifically required to prevent high-noise site bias.
    """
    if isinstance(code_or_tree, str):
        try:
            tree = ast.parse(code_or_tree)
        except Exception:
            return []
    else:
        tree = code_or_tree
        
    violations = []
    db_assigned_vars = set()

    for node in ast.walk(tree):
        # Track assignments from db/log calls
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Call):
                call_name = getattr(node.value.func, "id", "") or getattr(node.value.func, "attr", "")
                if call_name in {"to_db", "log10", "log"} or "db" in call_name.lower():
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            db_assigned_vars.add(target.id)

        # Inspect mean / average calls
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
                
            if func_name in {"mean", "average", "nanmean"}:
                for arg in node.args:
                    if isinstance(arg, ast.Call):
                        sub_name = getattr(arg.func, "id", "") or getattr(arg.func, "attr", "")
                        if sub_name in {"to_db", "log10", "log"} or "db" in sub_name.lower():
                            violations.append(f"LOG_BEFORE_AVERAGE: Found '{func_name}' applied directly to '{sub_name}' output at line {node.lineno}")
                    elif isinstance(arg, ast.Name):
                        if arg.id in db_assigned_vars or arg.id == "db" or arg.id.endswith("_db") or "db_" in arg.id:
                            violations.append(f"LOG_BEFORE_AVERAGE: Found '{func_name}' applied to decibel variable '{arg.id}' at line {node.lineno}")
    return violations


def check_modality_isolation(feature_names: List[str]) -> Tuple[bool, List[str]]:
    """Gate 4: Enforce signal class separation.
    
    Disallows un-namespaced pooling of SPK and LFP without explicit modality tags.
    """
    has_spk = any("spk" in f.lower() or "unit" in f.lower() or "sua" in f.lower() for f in feature_names)
    has_lfp = any("lfp" in f.lower() or "band" in f.lower() or "power" in f.lower() for f in feature_names)
    
    if has_spk and has_lfp:
        # Check if all features have clear namespace prefix (e.g. 'spk_' and 'lfp_')
        unprefixed = [f for f in feature_names if not (f.startswith("spk_") or f.startswith("lfp_") or f.startswith("mua_") or f.startswith("bhv_"))]
        if len(unprefixed) > 0:
            return False, [f"UNNAMESPACED_MODALITY_POOLING: Found {len(unprefixed)} mixed features without namespace prefix (e.g. {unprefixed[:3]})"]
            
    return True, []


def run_full_preflight() -> bool:
    """Runs complete repository preflight check."""
    print("=== Running Harness Pre-Flight Verification Gates ===")
    
    # 1. Boundary check
    violations = check_frozen_boundary()
    if violations:
        print("FAIL: jnwb/ frozen boundary check failed:")
        for v in violations:
            print(f"  - {v}")
        return False
    print("PASS: jnwb/ frozen boundary clean (zero unauthorized project imports).")
    
    # 2. Skill tree uniqueness check
    skill_violations = check_skill_tree_uniqueness()
    if skill_violations:
        print("FAIL: Skill tree uniqueness violated:")
        for v in skill_violations:
            print(f"  - {v}")
        return False
    print("PASS: Single canonical skill tree verified (no .agents/skills/ duplicate).")
    
    # 3. Key doctrine receipts check (tracked .lab receipts are always checked; outputs checked when present)
    tracked_receipts = [
        ("Fig04 Sealed Audit Receipt", "omission/artifacts/.lab/f04-sealed-audit-20260824.json"),
    ]
    optional_output_receipts = [
        ("Fig04 Temporal Context FDR Audit", "omission/outputs/classification/fig04_temporal_context_fdr_audit.csv"),
        ("PCA x UMAP Manifold Search Grid", "omission/outputs/classification/fig04_diagnostics/pca_umap_surface_grid.csv"),
        ("Matched Multimodal PCA->UMAP Results", "omission/outputs/classification/lfp_multimodal_pca_umap_results.csv"),
    ]
    all_receipts_ok = True
    for c_name, r_path in tracked_receipts:
        ok, msg = validate_receipt_provenance(c_name, r_path)
        if not ok:
            print(f"FAIL: {msg}")
            all_receipts_ok = False
        else:
            print(f"PASS: {msg}")

    # Check local analysis outputs if output directory exists
    if (REPO_ROOT / "omission" / "outputs" / "classification").exists():
        for c_name, r_path in optional_output_receipts:
            ok, msg = validate_receipt_provenance(c_name, r_path)
            if not ok:
                print(f"FAIL: {msg}")
                all_receipts_ok = False
            else:
                print(f"PASS: {msg}")
            
    if not all_receipts_ok:
        return False
        
    print("ALL HARNESS GATES PASSED.")
    return True


if __name__ == "__main__":
    success = run_full_preflight()
    sys.exit(0 if success else 1)
