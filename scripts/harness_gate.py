#!/usr/bin/env python3
"""Deterministic Operational & Scientific Harness Gate for jnwb generic library.

Mechanically enforces repository controls. The list is the runner's, in its order, and
`tests/test_module_docstrings_match_their_code.py` holds the two to each other: this
said twelve while the runner printed thirteen, and gate 2 had been rewritten from
protected paths to skill-tree uniqueness without the list noticing.

  1. Frozen jnwb boundary: no unauthorized imports from project folders.
  2. Skill tree uniqueness: every SKILL.md in the tree lives under skills/.
  3. Machine-local path exclusion: rejects hardcoded drive letters in test suites.
  4. Root allowlist: permits only tracked, authorized root files.
  5. Public symbols documented: every public export is written about by a person.
  6. Dataset leakage: rejects experiment-specific tokens, conditions, and manuscript results.
  7. Version consistency: package and metadata agree.
  8. Python floor consistency: declared support, classifiers, and CI matrix agree.
  9. Documented API matches jnwb.__all__, and the runtime generator agrees.
  10. Docs version matches package: every version the documentation states.
  11. No shadow packages: nothing importable at the repository root that jnwb does not own.
  12. Project identifiers in jnwb/ code strings.
  13. NWB onboarding surface alignment across README, tutorials, skill, and MkDocs.

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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
JNWB_DIR = REPO_ROOT / "jnwb"
OMISSION_DIR = REPO_ROOT / "omission"

AUTHORIZED_JNWB_EXCEPTIONS: set = set()

class HarnessGateFailure(Exception):
    """Raised when a mechanical harness boundary is violated."""
    pass


def check_frozen_boundary(jnwb_path: Optional[Path] = None) -> List[str]:
    """Gate 1 (Frozen Boundary): Enforce that jnwb/ contains zero unauthorized project imports."""
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


def _is_inside_nested_checkout(skill: Path, root: Path) -> bool:
    """True when this ``SKILL.md`` belongs to a second git checkout nested inside the tree.

    A git checkout root carries a ``.git`` entry: a directory for a clone, a file for a linked
    worktree. What it contains is this same ``skills/`` tree seen through another checkout, not a
    second tree, so gate 2 has nothing to say about it.

    This is detected rather than hardcoded. The agent fan-out this project runs puts worktrees
    under ``.claude/worktrees/`` today, but that is where this harness happens to place them and
    not a property of the thing being excluded; a path literal would stop working the moment they
    moved. Being untracked is deliberately *not* the test: a duplicate skill tree that is merely
    gitignored is still a tree an agent can read, which is the hazard gate 2 exists for.
    """
    for parent in skill.parents:
        if parent == root:
            return False
        if (parent / ".git").exists():
            return True
    return False


def check_skill_tree_uniqueness(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 2 (Skill Tree Uniqueness): every SKILL.md in the tree lives under skills/.

    This checked one hardcoded path, ``.agents/skills``, so a duplicate tree anywhere else
    passed: `jnwb/skills/` and `docs/skills/` were both accepted when constructed. The
    canonical tree is `skills/`, and a second one is the hazard whatever it is called.
    """
    root = repo_root or REPO_ROOT
    violations = []
    for skill in sorted(root.rglob("SKILL.md")):
        relative = skill.relative_to(root)
        if relative.parts[0] in EPHEMERAL_ROOT_DIRS:
            continue  # another package's skills inside a .venv are not this tree
        if _is_inside_nested_checkout(skill, root):
            continue  # a worktree is this tree seen twice, not two trees
        if relative.parts[0] != "skills":
            violations.append(
                f"DUPLICATE_SKILL_TREE: {relative.as_posix()} is a SKILL.md outside skills/. "
                "The canonical tree is skills/; a second tree is what this gate exists for."
            )
    return violations


def check_no_hardcoded_test_paths(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 3 (Test Independence): Enforce that tests do not contain machine-local hardcoded drive paths."""
    root = repo_root or REPO_ROOT
    tests_dir = root / "tests"
    if not tests_dir.exists():
        return []
    violations = []
    # Any drive letter, not C: and D:. This machine keeps its analysis data on E:, so the
    # allowlist shape of the original pattern exempted exactly the paths in use here: a
    # test pinned to "E:/analysis/derived/session.nwb" passed.
    drive_patterns = [
        re.compile(r'["\']([A-Za-z]:/(?:nwb|analysis|data|workspace|Users|home)[^"\']*)["\']'),
        re.compile(r'["\']([A-Za-z]:\\(?:nwb|analysis|data|workspace|Users|home)[^"\']*)["\']'),
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


# --- Import shadowing policy -----------------------------------------------
# jnwb installs editable via a .pth that puts the REPOSITORY ROOT on sys.path, so every
# top-level package sitting beside jnwb/ becomes importable for every editable user,
# from any working directory. A user project cloned inside this checkout therefore
# shadows itself (JNWB-002: 88 of 190 importing files silently loaded the wrong copy,
# disagreeing on an anatomical label, with no error raised).
# These two are jnwb's own, are excluded from the wheel, and are the residual hazard
# documented in docs/install.md -- nothing else may join them.
OWNED_ROOT_PACKAGES = {"jnwb"}
# jnwb's own directories, all excluded from the wheel. `docs/` and `examples/` joined the list
# when this gate started seeing namespace packages: `docs/generate_figures.py` and
# `examples/quickstart_jnwb.py` make both importable without an __init__.py, which is the same
# exposure and the same residual hazard documented in docs/install.md. Nothing else may join.
INTERNAL_ROOT_PACKAGES = {"scripts", "tests", "docs", "examples"}

# --- Python support policy -------------------------------------------------
# Corrected 2026-09-09. The earlier "3.12 only" rule was a decision scoped to one
# specific run that got generalized into repository-wide policy; it shipped an upper
# pin in 0.1.1 and made that release uninstallable. Declared support is a floor with
# no ceiling; CI tests every declared version. Testing only the floor and the head is
# what let 0.2.5 ship a 3.13 classifier no leg of the matrix ever ran.
PYTHON_FLOOR = "3.12"
PYTHON_SUPPORTED = ("3.12", "3.13", "3.14")   # what the classifiers must claim
PYTHON_CI_REQUIRED = ("3.12", "3.13", "3.14")  # every claimed version must be tested

#: Directories that hold tracked source. Anything else at the root is a mistake.
SOURCE_ROOT_DIRS = {
    "jnwb", "tests", "examples", "docs", "skills", "scripts", "artifacts", ".github",
}

#: Build output, caches and environments. Tolerated on disk, but each must be gitignored --
#: check_root_allowlist does not verify that, so keep this list short and boring.
EPHEMERAL_ROOT_DIRS = {
    ".git", ".venv", "venv", "env", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", "_build", "site", "jnwb.egg-info", ".tox", ".lab_bundle_build",
}

#: Directories a development tool owns at the root. Gitignored, never shipped, and deliberately
#: kept OUT of EPHEMERAL_ROOT_DIRS: gate 2 skips everything in that set, and `.claude/skills/` is
#: a real location an agent reads skills from, so a duplicate tree placed there must still fail.
#: Gate 2 excuses only a nested git checkout inside this directory, which is a different rule.
TOOL_ROOT_DIRS = {".claude"}

ALLOWED_ROOT_DIRS = SOURCE_ROOT_DIRS | EPHEMERAL_ROOT_DIRS | TOOL_ROOT_DIRS
ALLOWED_ROOT_FILES = {
    ".gitignore", ".readthedocs.yaml", "AGENTS.md", "CHANGELOG.md", "CLAUDE.md",
    "CONTRIBUTING.md", "LICENSE", "MANIFEST.in", "pyproject.toml", "README.md",
    # CLAUDE.md is git-ignored and untracked: AGENTS.md is the only repository-level
    # instruction file. It stays on this list so a contributor's own ignored copy does
    # not trip the root freeze -- permitted locally, never part of the repository.
    # .coverage stays: it is git-ignored, and a contributor running coverage from their
    # own environment should not trip the root freeze. jnwb-unified-rev.md left with the
    # script that produced it.
    ".coverage", "mkdocs.yml",
}


def check_root_allowlist(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 4 (Repository Hygiene): Enforce strict repository root freeze."""
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


GENERATED_REFERENCE = "api.md"


def check_public_symbols_documented(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 5 (API Completeness): every public export is written about by a person.

    05-41: this searched every ``docs/*.md``, and ``docs/api.md`` is generated from
    ``jnwb.__all__``. The gate therefore asserted that every export appears in a file
    guaranteed to contain every export. It passed while twelve symbols -- seven error
    classes, the two NWB resolvers, ``EventTable`` and ``DETECTION_TAILS`` -- appeared on
    no page a reader would find. The generated reference is excluded, so the gate now
    means what its name says. A whole-word match, so ``events`` is not credited to a page
    that only mentions ``event_onsets``.
    """
    root = repo_root or REPO_ROOT
    import jnwb
    docs_dir = root / "docs"
    if not docs_dir.exists():
        return ["MISSING_DOCS_DIR: docs/ not found"]
    
    all_docs_text = ""
    # rglob: docs/tutorials/ holds nine live pages that glob("*.md") never read, so a
    # symbol documented only there counted as undocumented.
    for doc_path in sorted(docs_dir.rglob("*.md")):
        if doc_path.name == GENERATED_REFERENCE:
            continue
        all_docs_text += "\n" + doc_path.read_text(encoding="utf-8")
        
    violations = []
    for symbol in jnwb.__all__:
        if not re.search(rf"\b{re.escape(symbol)}\b", all_docs_text):
            violations.append(
                f"UNDOCUMENTED_PUBLIC_SYMBOL: Public export 'jnwb.{symbol}' appears in "
                f"no hand-written docs/*.md page (docs/{GENERATED_REFERENCE} is "
                f"generated from __all__ and does not count)")
    return violations


def check_documented_api_matches_all(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 9 (API Set Equality): assert documented API == set(jnwb.__all__), both directions.

    Gate 5 checks that every export is *mentioned* somewhere in docs/. That is necessary but
    weak: it cannot see a reference row left behind for a symbol that no longer exists, and it
    is satisfied by an incidental mention anywhere in any file. This gate pins the reference
    surface itself as a set.

    It exists because prose cannot hold a count true. ``docs/memory.md`` carried "exactly 105
    public symbols" while the package exported 111 -- stale within one release cycle, in the
    document agents are pointed at, and nothing failed. The repair is to state the invariant and
    check it here rather than to write a fresher number that will go stale in turn.
    """
    root = repo_root or REPO_ROOT
    import jnwb

    api_path = root / "docs" / "api.md"
    if not api_path.exists():
        return ["MISSING_API_DOC: docs/api.md not found"]

    # Reference rows look like: | jnwb.NAME | function | ... |
    documented = set(re.findall(r"^\|\s*jnwb\.([A-Za-z_][A-Za-z0-9_]*)\s*\|",
                                api_path.read_text(encoding="utf-8"), flags=re.MULTILINE))
    exported = set(jnwb.__all__)

    violations = []
    for symbol in sorted(exported - documented):
        violations.append(
            f"UNDOCUMENTED_EXPORT: 'jnwb.{symbol}' is in __all__ but has no docs/api.md row")
    for symbol in sorted(documented - exported):
        violations.append(
            f"PHANTOM_API_ROW: docs/api.md documents 'jnwb.{symbol}', which is not in __all__")
    return violations


def check_docs_version_matches_package(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 10 (Version Provenance): assert every version the docs state equals the package's.

    A rendered version is provenance: it tells a reader which release they are looking at. A
    *duplicated* version is a liability -- it is correct only until the next release, and
    nothing notices when it stops being. So the rule is not "the docs must state a version"
    but "any version the docs state must be derived from, or equal to, jnwb.__version__".

    Checked locations, each a place a literal can drift:
      * mkdocs.yml ``extra.jnwb_version`` (consumed by the version hook)
      * ``jnwb==X.Y.Z`` install pins in README.md and docs/*.md
    """
    root = repo_root or REPO_ROOT
    import jnwb

    expected = jnwb.__version__
    violations = []

    mkdocs_yml = root / "mkdocs.yml"
    if mkdocs_yml.exists():
        text = mkdocs_yml.read_text(encoding="utf-8")
        for found in re.findall(r"^\s*jnwb_version:\s*[\"']?([0-9][^\"'\s]*)", text,
                                flags=re.MULTILINE):
            if found != expected:
                violations.append(
                    f"DOCS_VERSION_MISMATCH: mkdocs.yml extra.jnwb_version is {found!r}, "
                    f"but jnwb.__version__ is {expected!r}")

    # rglob for the same reason as Gate 5, and here it is a hole rather than a
    # strictness bug: a `jnwb==0.0.9` pin planted in docs/tutorials/01_nwb_basics.md
    # passed this gate.
    for md in [root / "README.md", *sorted((root / "docs").rglob("*.md"))]:
        if not md.exists():
            continue
        for found in re.findall(r"jnwb==([0-9][0-9A-Za-z.\-]*)", md.read_text(encoding="utf-8")):
            if found != expected:
                violations.append(
                    f"DOCS_VERSION_MISMATCH: {md.relative_to(root).as_posix()} pins "
                    f"jnwb=={found}, but jnwb.__version__ is {expected}")

    return violations


#: Root-level user-facing documents included in the Gate 6 scan. These ship to or are read by
#: downstream users, so they carry the same dataset-independence obligation as docs/.
DATASET_SCAN_ROOT_DOCS = ("README.md", "CONTRIBUTING.md", "AGENTS.md")

#: Files exempt from the Gate 6 scan, each with the reason it legitimately carries a token.
#: An exemption is a deliberate, named decision -- never a silent skip.
DATASET_SCAN_EXEMPT = {
    "CHANGELOG.md": "historical release record; not rewritten to satisfy a textual scan",
}


def check_dataset_leakage(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 6 (Dataset Independence): scan a fixed forbidden-token list.

    Scanned, recursively: ``jnwb/**/*.py``, ``skills/**/*.md``, ``docs/**/*.md``,
    ``examples/**/*.py``, ``examples/**/*.ipynb``, and the root user-facing documents listed in
    ``DATASET_SCAN_ROOT_DOCS``. These are the durable surfaces a reader or downstream user sees,
    and all of them are meant to be dataset-independent.

    Deliberately NOT scanned, each for a stated reason:
      * ``tests/`` and ``scripts/`` -- harness code legitimately names the tokens it forbids.
      * ``CHANGELOG.md`` -- a historical record; rewriting history to satisfy a scan would be
        worse than the leak it prevents.
      * files listed in ``DATASET_SCAN_EXEMPT`` -- see that constant for the per-file reason.

    The scan is textual and pattern-bound: it proves the listed tokens are absent, not that a
    surface is free of study-specific content in general.

    This docstring is load-bearing. It previously described a narrower surface than the code
    actually scanned (``docs/*.md``, non-recursive, with ``examples/`` unmentioned), and an
    audit that read it rather than the implementation reported a coverage gap that did not
    exist. Keep it synchronised with the globs below.
    """
    root = repo_root or REPO_ROOT
    violations = []
    
    forbidden_patterns = [
        (re.compile(r"\bAXAB\b"), "experiment condition token 'AXAB'"),
        (re.compile(r"\bBXBA\b"), "experiment condition token 'BXBA'"),
        (re.compile(r"S\+/S-"), "experiment condition token 'S+/S-'"),
        (re.compile(r"O\+/O-"), "experiment condition token 'O+/O-'"),
        (re.compile(r"\bO\+\+?\b"), "omission unit class token 'O+' or 'O++'"),
        (re.compile(r"\bomission-linked\b"), "study-specific concept 'omission-linked'"),
        (re.compile(r"\bomission-relative\b"), "study-specific concept 'omission-relative'"),
        (re.compile(r"p\s*=\s*0\.053\b"), "omission manuscript result 'p = 0.053'"),
        (re.compile(r"p\s*=\s*0\.875\b"), "omission manuscript result 'p = 0.875'"),
        (re.compile(r"\b74\.8\s*%"), "omission manuscript deltaT result '74.8%'"),
        (re.compile(r"\b104\s*/\s*139\b"), "omission manuscript cell count '104/139'"),
        (re.compile(r"\b187\s*/\s*4130\b"), "omission manuscript cell count '187/4130'"),
        (re.compile(r"beta\s*/\s*gamma\s+temporal\s+resolvability"), "omission study finding 'beta/gamma temporal resolvability'"),
        (re.compile(r"beta/gamma\s*>\s*theta/alpha"), "omission study finding 'beta/gamma > theta/alpha'"),
        (re.compile(r"early-decrease\s*/\s*late-increase"), "omission sign timing claim 'early-decrease / late-increase'"),
        (re.compile(r"area\s+and\s+subject\s+are\s+partially\s+confounded"), "omission area-subject confounding claim"),
        (re.compile(r"\bLFP\s+drives\s+SPK\b"), "forbidden causal assertion 'LFP drives SPK'"),
        (re.compile(r"\bSPK\s+drives\s+LFP\b"), "forbidden causal assertion 'SPK drives LFP'"),
    ]
    
    target_files: List[Path] = []
    
    # 1. jnwb/ Python files
    for py_file in (root / "jnwb").rglob("*.py"):
        if "__pycache__" not in py_file.parts:
            target_files.append(py_file)
            
    # 2. skills/ markdown files
    skills_dir = root / "skills"
    if skills_dir.exists():
        for skill_file in skills_dir.rglob("*.md"):
            target_files.append(skill_file)
            
    # 3. Core harness authority and developer guides
    for harness_name in ["AGENTS.md", "CONTRIBUTING.md"]:
        harness_file = root / harness_name
        if harness_file.exists():
            target_files.append(harness_file)
            
    # 4. docs/ markdown files, recursively -- includes docs/tutorials/
    docs_dir = root / "docs"
    if docs_dir.exists():
        for doc_file in docs_dir.rglob("*.md"):
            if doc_file not in target_files:
                target_files.append(doc_file)

    # 5. Every example surface, recursively: executable tutorials, their support modules, the
    #    quickstart, and notebooks. Previously only examples/tutorials/[0-9][0-9]_*.py was
    #    scanned, which left examples/quickstart_jnwb.py, examples/notebooks/*.ipynb and any
    #    non-numbered helper module unscanned -- all of them user-facing.
    examples_dir = root / "examples"
    if examples_dir.exists():
        for pattern in ("*.py", "*.ipynb"):
            for example_file in examples_dir.rglob(pattern):
                if "__pycache__" in example_file.parts:
                    continue
                if example_file not in target_files:
                    target_files.append(example_file)

    # 6. Root-level user-facing documents (README.md above all -- the most-read file here).
    for doc_name in DATASET_SCAN_ROOT_DOCS:
        root_doc = root / doc_name
        if root_doc.exists() and root_doc not in target_files:
            target_files.append(root_doc)

    target_files = [f for f in target_files
                    if f.relative_to(root).as_posix() not in DATASET_SCAN_EXEMPT]
                
    for target in target_files:
        text = target.read_text(encoding="utf-8", errors="replace")
        rel_path = target.relative_to(root).as_posix()
        for pat, desc in forbidden_patterns:
            if pat.search(text):
                violations.append(f"DATASET_LEAKAGE: Found {desc} in {rel_path}")
                
    return violations


def check_version_consistency(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 7 (Release Consistency): Assert package version matches pyproject.toml."""
    root = repo_root or REPO_ROOT
    import jnwb
    version = getattr(jnwb, "__version__", None)
    if not version:
        return ["MISSING_VERSION: jnwb.__version__ is not defined"]
        
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        return ["MISSING_PYPROJECT: pyproject.toml not found"]
    
    # Parsed, not substring-matched. The old check looked for the binding anywhere in the
    # file, so a pyproject.toml carrying `version = "0.0.1"` and the attr binding inside a
    # comment passed: the comment satisfied has_dynamic and the wrong version was never
    # compared to anything.
    import tomllib

    try:
        with open(pyproject_path, "rb") as handle:
            project = tomllib.load(handle).get("project", {})
    except tomllib.TOMLDecodeError as exc:
        return [f"UNPARSEABLE_PYPROJECT: {exc}"]

    declared = project.get("version")
    dynamic = project.get("dynamic") or []
    if declared is None:
        if "version" not in dynamic:
            return [
                "VERSION_INCONSISTENCY: pyproject.toml declares neither a version nor "
                'dynamic = ["version"]'
            ]
        return []
    if declared != version:
        return [
            f"VERSION_INCONSISTENCY: pyproject.toml declares version {declared!r}, but "
            f"jnwb.__version__ is {version!r}"
        ]
    return []


def check_python_floor_consistency(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 8 (Python Floor Consistency): declared support, classifiers and CI must agree.

    The invariant is *agreement*, not a single version. Its predecessor
    (`check_python_target_consistency`) asserted "3.12 is the sole targeted version",
    which was an over-generalization of a decision scoped to one specific run. That
    policy is what put `requires-python = ">=3.12, <3.13"` into 0.1.1 and made the
    release uninstallable on every current interpreter, while pip silently resolved
    users back to 0.1.0. The gate did not catch it because it was enforcing it.

    What is checked here:

    1. `requires-python` declares PYTHON_FLOOR with **no upper bound**. The wheel is
       `py3-none-any` -- pure Python, no compiled extensions -- so no ABI reason for a
       ceiling exists, and an upper pin locks users out of interpreters that work.
    2. The classifier set equals PYTHON_SUPPORTED exactly, in both directions: nothing
       below the floor, and nothing claimed that is not declared.
    3. The CI matrix contains every version in PYTHON_CI_REQUIRED, which is now every
       version the classifiers claim. Requiring only the floor and the head is what let
       0.2.5 ship a 3.13 classifier that CI never exercised, and let this gate report the
       three surfaces as agreeing while one claimed version was untested.
    4. `.readthedocs.yaml` pins one interpreter drawn from PYTHON_SUPPORTED. A docs
       build needs one version, not a matrix -- it just may not drift outside the range.
    """
    root = repo_root or REPO_ROOT
    violations = []

    # 1. pyproject.toml: floor, no ceiling, classifiers == PYTHON_SUPPORTED
    # Each of the three blocks below used to be `if <file>.exists():` with no else, so an
    # empty directory passed the whole gate. A missing file is a failure, not a pass.
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        violations.append("PYTHON_FLOOR_INCONSISTENCY: pyproject.toml not found")
    if pyproject_path.exists():
        pyproject_text = pyproject_path.read_text(encoding="utf-8")

        requires = re.search(r'requires-python\s*=\s*"([^"]*)"', pyproject_text)
        if requires is None:
            violations.append("PYTHON_FLOOR_INCONSISTENCY: pyproject.toml declares no requires-python")
        else:
            spec = requires.group(1)
            if f">={PYTHON_FLOOR}" not in spec.replace(" ", ""):
                violations.append(
                    f"PYTHON_FLOOR_INCONSISTENCY: requires-python {spec!r} does not declare a "
                    f">={PYTHON_FLOOR} floor"
                )
            if "<" in spec:
                violations.append(
                    f"PYTHON_UPPER_PIN: requires-python {spec!r} carries an upper bound. jnwb is a "
                    "pure-Python py3-none-any wheel; an upper pin makes the release uninstallable "
                    "on newer interpreters and silently resolves users to an older version. "
                    "Add a ceiling only for a *named*, demonstrated incompatibility."
                )

        declared = {
            m.group(1)
            for m in re.finditer(
                r'"Programming Language :: Python :: (\d+\.\d+)"', pyproject_text
            )
        }
        for missing in sorted(set(PYTHON_SUPPORTED) - declared):
            violations.append(
                f"PYTHON_CLASSIFIER_MISSING: no classifier for supported Python {missing}"
            )
        for extra in sorted(declared - set(PYTHON_SUPPORTED)):
            violations.append(
                f"PYTHON_CLASSIFIER_UNSUPPORTED: classifier claims Python {extra}, which is not in "
                f"the declared supported set {sorted(PYTHON_SUPPORTED)}"
            )

    # 2. .readthedocs.yaml: one interpreter, inside the supported range
    rtd_path = root / ".readthedocs.yaml"
    if not rtd_path.exists():
        violations.append("PYTHON_FLOOR_INCONSISTENCY: .readthedocs.yaml not found")
    if rtd_path.exists():
        rtd_text = rtd_path.read_text(encoding="utf-8")
        pinned = re.search(r'python:\s*"(\d+\.\d+)"', rtd_text)
        if pinned is None:
            violations.append("PYTHON_FLOOR_INCONSISTENCY: .readthedocs.yaml pins no python version")
        elif pinned.group(1) not in PYTHON_SUPPORTED:
            violations.append(
                f"PYTHON_FLOOR_INCONSISTENCY: .readthedocs.yaml pins Python {pinned.group(1)}, "
                f"outside the supported set {sorted(PYTHON_SUPPORTED)}"
            )

    # 3. workflow.yml: the matrix must cover every version in PYTHON_CI_REQUIRED
    workflow_path = root / ".github" / "workflows" / "workflow.yml"
    if not workflow_path.exists():
        violations.append(
            "PYTHON_FLOOR_INCONSISTENCY: .github/workflows/workflow.yml not found"
        )
    if workflow_path.exists():
        wf_text = workflow_path.read_text(encoding="utf-8")
        matrix = re.search(r"python-version:\s*\[([^\]]*)\]", wf_text)
        if matrix is None:
            violations.append("PYTHON_FLOOR_INCONSISTENCY: workflow.yml declares no python-version matrix")
        else:
            tested = set(re.findall(r'"(\d+\.\d+)"', matrix.group(1)))
            for required in PYTHON_CI_REQUIRED:
                if required not in tested:
                    violations.append(
                        f"PYTHON_CI_UNTESTED: workflow.yml test matrix {sorted(tested)} does not "
                        f"include Python {required}"
                    )
            for untested in sorted(tested - set(PYTHON_SUPPORTED)):
                violations.append(
                    f"PYTHON_CI_UNSUPPORTED: workflow.yml tests Python {untested}, which is not in "
                    f"the declared supported set {sorted(PYTHON_SUPPORTED)}"
                )

    return violations


def check_no_shadow_packages(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 11 (Import Shadowing): no unowned importable package may sit at the repo root.

    The editable install writes a .pth containing the repository root, so anything at
    the root with an `__init__.py` is importable ahead of a consumer's own package of
    the same name -- silently, from any working directory, with a well-formed module
    object and no error. `.gitignore` hides such a directory from `git status`, which
    removes the last signal a user would get.

    This is not hypothetical: a stale clone of a *user project* inside this checkout
    shadowed that project, and 88 of 190 importing files took the wrong copy.

    The gate is deliberately stricter than the wheel. The built wheel already ships
    only `jnwb/`; the exposure is editable installs, which is how every developer and
    every analysis session actually runs.
    """
    root = repo_root or REPO_ROOT
    allowed = OWNED_ROOT_PACKAGES | INTERNAL_ROOT_PACKAGES
    violations = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name in allowed:
            continue
        if entry.name.startswith(".") or entry.name.endswith(".egg-info"):
            continue
        if entry.name in EPHEMERAL_ROOT_DIRS:
            continue
        # An __init__.py is not what makes a directory importable. Since PEP 420 a plain
        # directory holding .py files imports as a namespace package, which is how
        # JNWB-002 happened: the gate asked for __init__.py, found none, and passed the
        # tree that produced the incident. Confirmed with importlib.util.find_spec, which
        # resolves such a directory with origin None.
        importable = (entry / "__init__.py").exists() or any(entry.glob("*.py"))
        if importable:
            kind = "package" if (entry / "__init__.py").exists() else "namespace package"
            violations.append(
                f"SHADOW_PACKAGE: '{entry.name}/' is importable as a {kind} at the repository "
                f"root, so `import {entry.name}` resolves inside the jnwb checkout for every "
                f"editable install, shadowing any consumer package of that name. Move it out "
                f"of the library checkout."
            )
    return violations


#: Projects built on jnwb. A code string or identifier in jnwb/ containing one gives that
#: project privileged meaning in the library.
PROJECT_IDENTIFIERS = ("omission",)
#: The deprecated OMISSION_*_DIR environment variables that jnwb.paths still reads, with a
#: DeprecationWarning. The only project names jnwb/ code may contain.
PROJECT_IDENTIFIER_ALLOWED = re.compile(r"^OMISSION_[A-Z]+_DIR$")


def check_no_project_identifiers_in_code(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 12 (Project Identifiers): no jnwb/ code string or name contains a project name.

    Gate 1 sees imports and Gate 6 sees a fixed list of study tokens. Neither saw 0.1.3's
    MCP tool defaulting to a project's event table ('omission_glo_passive'), so both
    passed. This gate parses jnwb/ and checks every string constant and identifier.
    Docstrings and comments are skipped; they may cite where code came from.
    """
    root = repo_root or REPO_ROOT
    violations = []
    for py in sorted((root / "jnwb").rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        # A string standing alone as a statement is documentation (a docstring, or an
        # attribute docstring under a dataclass field); it never reaches running code.
        docstrings = {
            id(node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in docstrings:
                    continue
                text = node.value
            elif isinstance(node, ast.Name):
                text = node.id
            elif isinstance(node, ast.Attribute):
                text = node.attr
            elif isinstance(node, ast.arg):
                text = node.arg
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                text = node.name
            elif isinstance(node, ast.alias):
                text = node.name
            else:
                continue
            if PROJECT_IDENTIFIER_ALLOWED.match(text):
                continue
            for project in PROJECT_IDENTIFIERS:
                if project in text.lower():
                    violations.append(
                        f"PROJECT_IDENTIFIER: {py.relative_to(root).as_posix()}:{node.lineno} "
                        f"uses {text[:60]!r}. A project's names belong in the project; take "
                        f"the value as an argument instead."
                    )
    return violations


# ==============================================================================
# General Scientific Integrity Gates
# ==============================================================================

def check_logarithm_last_rule(code_or_tree: Union[str, ast.AST]) -> List[str]:
    """Scoped Estimand Gate: Enforce raw-power aggregation before logarithmic transformation.

    Applies ONLY to analyses or functions that explicitly declare raw-power aggregation
    as their estimand (e.g. via '# estimand: raw_power_average' or docstring declaration).
    Does NOT globally reject legitimate mean-of-dB code where logarithmic/log-normal power
    averaging is the intended estimand.
    """
    code_text = code_or_tree if isinstance(code_or_tree, str) else ""
    if isinstance(code_or_tree, str):
        if not re.search(r"estimand\s*[:=]\s*['\"]?raw_power", code_text, re.IGNORECASE):
            return []
        try:
            tree = ast.parse(code_or_tree)
        except Exception:
            return []
    else:
        tree = code_or_tree
        doc = ast.get_docstring(tree) or ""
        if not re.search(r"estimand\s*[:=]\s*['\"]?raw_power", doc, re.IGNORECASE):
            has_declaration = False
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fdoc = ast.get_docstring(node) or ""
                    if re.search(r"estimand\s*[:=]\s*['\"]?raw_power", fdoc, re.IGNORECASE):
                        has_declaration = True
                        break
            if not has_declaration:
                return []

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
    """Modality-isolation check (not a numbered preflight gate; argument-driven).

    Enforce signal class separation.
    
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


#: The public NWB entry points Gate 13 holds the onboarding surface to.
NWB_ONBOARDING_SYMBOLS = ("jnwb.inspect", "jnwb.events", "jnwb.event_onsets")


def check_nwb_onboarding_alignment(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 13: README, tutorials, and skill agree on the public NWB workflow.

    This was a presence check and passed a tree it should have rejected: a README saying
    the three symbols are REMOVED still contains their names, nine tutorials whose whole
    body is ``raise SystemExit`` still exist as files, and a nav line commented out in
    mkdocs.yml is still a substring of the file. Each of the three is now checked for the
    property it was standing in for -- a call, a runnable module, a parsed nav entry.
    """
    root = repo_root or REPO_ROOT
    violations: List[str] = []

    readme = root / "README.md"
    if not readme.exists():
        violations.append("NWB_ONBOARDING: README.md missing")
    else:
        text = readme.read_text(encoding="utf-8")
        for symbol in NWB_ONBOARDING_SYMBOLS:
            # A call, not a mention: "jnwb.inspect is REMOVED" mentions it too.
            if f"{symbol}(" not in text:
                violations.append(
                    f"NWB_ONBOARDING: README never calls {symbol}; naming it is not the same "
                    f"as showing a reader how to use it"
                )

    expected_scripts = [
        "00_your_own_file.py",
        "01_nwb_basics.py",
        "02_addressing_and_metadata.py",
        "03_spiking.py",
        "04_lfp_and_spectral.py",
        "05_statistics.py",
        "06_laminar.py",
        "07_ensembles.py",
        "08_end_to_end_pipeline.py",
    ]
    tutorial_dir = root / "examples" / "tutorials"
    for name in expected_scripts:
        script = tutorial_dir / name
        if not script.exists():
            violations.append(f"NWB_ONBOARDING: missing tutorial script {name}")
            continue
        source = script.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(script))
        except SyntaxError as exc:
            violations.append(f"NWB_ONBOARDING: {name} does not parse: {exc}")
            continue
        # A file that exists is not a tutorial that runs. Nine of them rewritten to
        # `raise SystemExit(...)` passed this gate, because the check was existence.
        if any(isinstance(node, ast.Raise) for node in tree.body):
            violations.append(
                f"NWB_ONBOARDING: {name} raises at module level, so importing or running it "
                f"never reaches the workflow it documents"
            )
        functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        if "main" not in functions:
            violations.append(f"NWB_ONBOARDING: {name} defines no main()")

    for name in expected_scripts:
        md_name = name.replace(".py", ".md")
        md_path = root / "docs" / "tutorials" / md_name
        if not md_path.exists():
            violations.append(f"NWB_ONBOARDING: missing tutorial doc {md_name}")
            continue
        snippet = f'--8<-- "examples/tutorials/{name}"'
        if snippet not in md_path.read_text(encoding="utf-8"):
            violations.append(f"NWB_ONBOARDING: {md_name} not snippet-linked to {name}")

    skill = root / "skills" / "jnwb-nwb-data" / "SKILL.md"
    if skill.exists():
        skill_text = skill.read_text(encoding="utf-8")
        for symbol in NWB_ONBOARDING_SYMBOLS:
            if f"{symbol}(" not in skill_text:
                violations.append(
                    f"NWB_ONBOARDING: the skill names {symbol} but never routes a call to it"
                )
    else:
        violations.append("NWB_ONBOARDING: skills/jnwb-nwb-data/SKILL.md missing")

    mkdocs = root / "mkdocs.yml"
    if not mkdocs.exists():
        violations.append("NWB_ONBOARDING: mkdocs.yml missing")
    else:
        # Parsed, not substring-matched: a commented-out nav line is still a substring of
        # the file, so the page would be missing from the built site while this passed.
        import yaml

        try:
            config = yaml.safe_load(mkdocs.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            config = {}
            violations.append(f"NWB_ONBOARDING: mkdocs.yml does not parse: {exc}")

        def _pages(node) -> List[str]:
            if isinstance(node, str):
                return [node]
            if isinstance(node, dict):
                return [p for value in node.values() for p in _pages(value)]
            if isinstance(node, list):
                return [p for item in node for p in _pages(item)]
            return []

        nav_pages = set(_pages(config.get("nav", [])))
        for name in expected_scripts:
            page = f"tutorials/{name.replace('.py', '.md')}"
            if page not in nav_pages:
                violations.append(
                    f"NWB_ONBOARDING: {page} is not in the mkdocs nav, so the built site "
                    f"does not carry it"
                )

    return violations


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
    print(
        "PASS: No forbidden study tokens on Gate 6 scan surface "
        "(jnwb/, skills/, docs/**, examples/**, root user-facing docs)."
    )

    # 7. Package and metadata version consistency check
    version_violations = check_version_consistency()
    if version_violations:
        print("FAIL: Version inconsistency detected:")
        for v in version_violations:
            print(f"  - {v}")
        return False
    print("PASS: Package and pyproject.toml versions synchronized.")

    # 8. Python floor consistency: declared support, classifiers and CI agree
    py_floor_violations = check_python_floor_consistency()
    if py_floor_violations:
        print("FAIL: Python support policy inconsistency detected:")
        for v in py_floor_violations:
            print(f"  - {v}")
        return False
    print(
        f"PASS: Python >={PYTHON_FLOOR} floor, classifiers {list(PYTHON_SUPPORTED)}, "
        f"CI covering {list(PYTHON_CI_REQUIRED)} all agree."
    )

    # 9. API reference: set equality and generator drift
    from scripts.generate_api_md import check_api_md_is_generated

    api_set_violations = check_documented_api_matches_all()
    if api_set_violations:
        print("FAIL: Documented API does not match jnwb.__all__:")
        for v in api_set_violations:
            print(f"  - {v}")
        return False
    api_gen_violations = check_api_md_is_generated()
    if api_gen_violations:
        print("FAIL: docs/api.md is out of sync with the API generator:")
        for v in api_gen_violations:
            print(f"  - {v}")
        return False
    print("PASS: docs/api.md matches jnwb.__all__ and the runtime API generator.")

    # 10. Documentation version provenance: every stated version equals the package's
    docs_version_violations = check_docs_version_matches_package()
    if docs_version_violations:
        print("FAIL: Documentation version does not match the package version:")
        for v in docs_version_violations:
            print(f"  - {v}")
        return False
    print("PASS: Documentation versions derive from jnwb.__version__.")

    # 11. Import shadowing: no unowned importable package at the repository root
    shadow_violations = check_no_shadow_packages()
    if shadow_violations:
        print("FAIL: Import-shadowing package detected at repository root:")
        for v in shadow_violations:
            print(f"  - {v}")
        return False
    print("PASS: No unowned importable package at the repository root.")

    # 12. Project identifiers: no project name in jnwb/ code strings or names
    identifier_violations = check_no_project_identifiers_in_code()
    if identifier_violations:
        print("FAIL: Project identifiers found in jnwb/ code:")
        for v in identifier_violations:
            print(f"  - {v}")
        return False
    print("PASS: No project identifiers in jnwb/ code strings or names.")

    # 13. NWB onboarding surface alignment (README, tutorials, skill, MkDocs)
    onboarding_violations = check_nwb_onboarding_alignment()
    if onboarding_violations:
        print("FAIL: NWB onboarding surface misaligned:")
        for v in onboarding_violations:
            print(f"  - {v}")
        return False
    print("PASS: NWB onboarding workflow aligned across README, tutorials, skill, and MkDocs.")

    print("ALL HARNESS GATES PASSED.")
    return True


if __name__ == "__main__":
    success = run_full_preflight()
    sys.exit(0 if success else 1)
