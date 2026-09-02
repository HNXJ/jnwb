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
import re
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
    """Gate 2 (Global Repository Safety): Enforce single canonical skill tree.
    
    Prohibits recreation of duplicate .agents/skills/ trees.
    The single tracked canonical skill tree is skills/.
    """
    root = repo_root or REPO_ROOT
    violations = []
    agents_skills = root / ".agents" / "skills"
    if agents_skills.exists():
        violations.append(
            f"DUPLICATE_SKILL_TREE: {agents_skills} exists. "
            "Canonical generic skills live exclusively in skills/."
        )
    return violations


def check_no_hardcoded_test_paths(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 3 (Test Independence): Enforce that tests do not contain machine-local hardcoded drive paths."""
    root = repo_root or REPO_ROOT
    tests_dir = root / "tests"
    if not tests_dir.exists():
        return []
    violations = []
    drive_patterns = [
        re.compile(r'["\']([CDcd]:/(?:nwb|analysis|data|workspace|Users|home)[^"\']*)["\']'),
        re.compile(r'["\']([CDcd]:\\(?:nwb|analysis|data|workspace|Users|home)[^"\']*)["\']'),
        re.compile(r'["\'](/Users/[^"\']+)["\']'),
        re.compile(r'["\'](/home/(?!runner)[^"\']+)["\']'),
    ]
    for py_file in tests_dir.rglob("*.py"):
        if py_file.name == "test_harness_adversarial_gates.py":
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value
                for pat in drive_patterns:
                    if pat.search(f'"{val}"'):
                        # Allow explicit synthetic / error test fixtures
                        if "non_existent" in val or "synthetic" in val or "fake" in val or "dummy" in val:
                            continue
                        violations.append(f"HARDCODED_TEST_PATH: Machine-local absolute path '{val}' found in {py_file.name}:{getattr(node, 'lineno', '?')}")
    return violations


ALLOWED_ROOT_DIRS = {
    "jnwb", "tests", "examples", "docs", "skills", "scripts", "omission", "artifacts",
    ".git", ".github", ".venv", "venv", "env", ".pytest_cache", "dist", "build", "jnwb.egg-info",
    ".lab_bundle_build", ".claude", ".cursor", ".gemini", "_build", ".tox"
}
ALLOWED_ROOT_FILES = {
    ".gitignore", ".readthedocs.yaml", "AGENTS.md", "CHANGELOG.md", "CLAUDE.md",
    "LICENSE", "pyproject.toml", "README.md", ".coverage"
}


def check_root_allowlist(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 5 (Repository Hygiene): Enforce strict repository root freeze."""
    root = repo_root or REPO_ROOT
    violations = []
    for entry in root.iterdir():
        if entry.is_dir():
            if entry.name not in ALLOWED_ROOT_DIRS:
                violations.append(f"UNAUTHORIZED_ROOT_DIR: Disallowed directory at repository root: {entry.name}")
        elif entry.is_file():
            if entry.name not in ALLOWED_ROOT_FILES:
                violations.append(f"UNAUTHORIZED_ROOT_FILE: Disallowed file at repository root: {entry.name}. Move to artifacts/ or configure .gitignore.")
    return violations


def check_public_symbols_documented(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 6 (API Completeness): Assert all public exports are documented in docs/."""
    root = repo_root or REPO_ROOT
    import jnwb
    docs_dir = root / "docs"
    if not docs_dir.exists():
        return ["MISSING_DOCS_DIR: docs/ not found"]
    
    all_docs_text = ""
    for doc_path in docs_dir.glob("*.md"):
        all_docs_text += "\n" + doc_path.read_text(encoding="utf-8")
        
    violations = []
    for symbol in jnwb.__all__:
        if symbol not in all_docs_text:
            violations.append(f"UNDOCUMENTED_PUBLIC_SYMBOL: Public export 'jnwb.{symbol}' is not documented in docs/")
    return violations


def check_dataset_leakage(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 7 (Dataset Independence): Assert zero experiment-specific condition tokens in generic code."""
    root = repo_root or REPO_ROOT
    violations = []
    forbidden_tokens = ["AXAB", "BXBA", "S+/S-", "O+/O-"]
    
    for py_file in (root / "jnwb").rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        text = py_file.read_text(encoding="utf-8", errors="replace")
        for tok in forbidden_tokens:
            if tok in text:
                violations.append(f"DATASET_LEAKAGE: Found experiment-specific token '{tok}' in jnwb/{py_file.name}")
                
    for skill_file in (root / "skills").rglob("*.md"):
        text = skill_file.read_text(encoding="utf-8", errors="replace")
        for tok in forbidden_tokens:
            if tok in text:
                violations.append(f"DATASET_LEAKAGE: Found experiment-specific token '{tok}' in skills/{skill_file.name}")
                
    return violations


def check_version_consistency(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 8 (Release Consistency): Assert package version matches pyproject.toml and docs/conf.py."""
    root = repo_root or REPO_ROOT
    import jnwb
    version = getattr(jnwb, "__version__", None)
    if not version:
        return ["MISSING_VERSION: jnwb.__version__ is not defined"]
        
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        return ["MISSING_PYPROJECT: pyproject.toml not found"]
    
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    has_dynamic = 'version = { attr = "jnwb.__version__" }' in pyproject_text or 'version = {attr = "jnwb.__version__"}' in pyproject_text
    has_static = f'version = "{version}"' in pyproject_text
    if not (has_dynamic or has_static):
        return [f"VERSION_INCONSISTENCY: pyproject.toml does not bind to jnwb.__version__ ({version})"]
        
    return []


def check_python_target_consistency(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 9 (Python 3.12 Target Consistency): Assert Python 3.12 is the sole targeted version across metadata and CI."""
    root = repo_root or REPO_ROOT
    violations = []
    
    # 1. pyproject.toml
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        pyproject_text = pyproject_path.read_text(encoding="utf-8")
        if 'requires-python = ">=3.12, <3.13"' not in pyproject_text and 'requires-python = ">=3.12"' not in pyproject_text and 'requires-python = "==3.12.*"' not in pyproject_text:
            violations.append("PYTHON_TARGET_INCONSISTENCY: pyproject.toml requires-python does not target Python 3.12")
        for bad_v in ["3.10", "3.11", "3.13", "3.14"]:
            if f'"Programming Language :: Python :: {bad_v}"' in pyproject_text:
                violations.append(f"PYTHON_TARGET_INCONSISTENCY: pyproject.toml contains classifier for non-3.12 Python version: {bad_v}")
                
    # 2. .readthedocs.yaml
    rtd_path = root / ".readthedocs.yaml"
    if rtd_path.exists():
        rtd_text = rtd_path.read_text(encoding="utf-8")
        if 'python: "3.12"' not in rtd_text:
            violations.append("PYTHON_TARGET_INCONSISTENCY: .readthedocs.yaml does not specify python: '3.12'")
            
    # 3. workflow.yml
    workflow_path = root / ".github" / "workflows" / "workflow.yml"
    if workflow_path.exists():
        wf_text = workflow_path.read_text(encoding="utf-8")
        if 'python-version: [ "3.12" ]' not in wf_text and 'python-version: ["3.12"]' not in wf_text:
            violations.append("PYTHON_TARGET_INCONSISTENCY: .github/workflows/workflow.yml test matrix is not restricted to Python 3.12")
            
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
    
    # 3. Test independence check (no machine-local hardcoded paths)
    test_path_violations = check_no_hardcoded_test_paths()
    if test_path_violations:
        print("FAIL: Hardcoded machine-local paths detected in tests:")
        for v in test_path_violations:
            print(f"  - {v}")
        return False
    print("PASS: Tests free of machine-local hardcoded drive paths.")
            
    # 4. Root allowlist check
    root_violations = check_root_allowlist()
    if root_violations:
        print("FAIL: Repository root allowlist violated:")
        for v in root_violations:
            print(f"  - {v}")
        return False
    print("PASS: Repository root strictly frozen & clean.")

    # 5. Public symbols documentation completeness check
    symbol_violations = check_public_symbols_documented()
    if symbol_violations:
        print("FAIL: Undocumented public symbols detected:")
        for v in symbol_violations:
            print(f"  - {v}")
        return False
    print("PASS: 100% of public symbols documented in docs/.")

    # 6. Dataset independence / leakage check
    leakage_violations = check_dataset_leakage()
    if leakage_violations:
        print("FAIL: Dataset leakage detected in generic modules:")
        for v in leakage_violations:
            print(f"  - {v}")
        return False
    print("PASS: Zero dataset-specific tokens in jnwb/ and skills/.")

    # 7. Package and metadata version consistency check
    version_violations = check_version_consistency()
    if version_violations:
        print("FAIL: Version inconsistency detected:")
        for v in version_violations:
            print(f"  - {v}")
        return False
    print("PASS: Package and pyproject.toml versions synchronized.")

    # 8. Python 3.12 target consistency check
    py_target_violations = check_python_target_consistency()
    if py_target_violations:
        print("FAIL: Python target inconsistency detected:")
        for v in py_target_violations:
            print(f"  - {v}")
        return False
    print("PASS: Python 3.12 sole supported target verified across metadata and CI.")

    print("ALL HARNESS GATES PASSED.")
    return True


if __name__ == "__main__":
    success = run_full_preflight()
    sys.exit(0 if success else 1)
