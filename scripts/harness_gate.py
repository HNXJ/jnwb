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
  14. Internal process vocabulary kept out of public documentation, and item or problem
      identifiers out of jnwb/.
  15. Stack form consistency: declared write sets are comparable and problem rows keep shape.
  16. Line ending consistency: no tracked text file carries both conventions at once.
  17. Stack pointers resolve: Skill, Role and Blocked by name something on this tree.
  18. API member types: each docs/api.md Type cell is true of the runtime object.

Returns exit code 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import ast
import itertools
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, Union

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


def _is_inside_nested_checkout(skill: Path, root: Path, identities: Optional[Dict[Any, Any]] = None) -> bool:
    """True when this ``SKILL.md`` belongs to a linked worktree of this repository nested in the tree.

    Such a worktree holds this same ``skills/`` tree seen through another checkout, not a second
    tree, so gate 2 has nothing to say about it. Anything else below the root stays in scope,
    including a nested clone or an unrelated repository: each has its own object store and is a
    second tree an agent can read.

    This is detected rather than hardcoded. The agent fan-out this project runs puts worktrees
    under ``.claude/worktrees/`` today, but that is where this harness happens to place them and
    not a property of the thing being excluded; a path literal would stop working the moment they
    moved. Being untracked is deliberately *not* the test: a duplicate skill tree that is merely
    gitignored is still a tree an agent can read, which is the hazard gate 2 exists for.

    git runs only for a parent that carries an entry named ``.git``, so a tree without nested
    checkouts costs no subprocess.
    """
    for parent in skill.parents:
        if parent == root:
            return False
        if os.path.lexists(parent / ".git") and _is_checkout_of(parent, root, identities):
            return True
    return False


def _test_job_matrix(workflow_text: str) -> Optional[set]:
    """The python-version matrix of the `test` job specifically, or None if it has none.

    Read by path rather than by first regex match: a decoy `python-version:` list anywhere above
    `jobs.test` satisfied the old search while the job that actually runs the suite tested
    something else. PyYAML is a hard dependency of mkdocs, which this repository already builds
    with, so parsing costs nothing new; the regex fallback exists so a YAML error degrades to the
    previous behaviour rather than to silence.

    The versions returned are those of the legs CI runs: the matrix axes are expanded, every
    `exclude` entry removes the legs it matches, and every `include` entry adds its version. The
    `python-version` list alone is what the matrix declares, and an `exclude` can leave one of
    its versions with no leg at all.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover - mkdocs pulls PyYAML in every supported env
        yaml = None
    if yaml is not None:
        try:
            doc = yaml.safe_load(workflow_text)
            matrix = doc["jobs"]["test"]["strategy"]["matrix"]
            axes = {k: v for k, v in matrix.items()
                    if k not in ("include", "exclude") and isinstance(v, list)}
            if "python-version" not in axes:
                return None
            legs = [dict(zip(axes, combo)) for combo in itertools.product(*axes.values())]
            for excluded in matrix.get("exclude") or []:
                legs = [leg for leg in legs
                        if not all(str(leg.get(k)) == str(v) for k, v in excluded.items())]
            legs.extend(inc for inc in matrix.get("include") or [] if "python-version" in inc)
            return {str(leg["python-version"]) for leg in legs}
        except (yaml.YAMLError, KeyError, TypeError, AttributeError):
            return None
    matrix = re.search(r"python-version:\s*\[([^\]]*)\]", workflow_text)
    return set(re.findall(r'"(\d+\.\d+)"', matrix.group(1))) if matrix else None


#: Variables that redirect git's repository discovery. A gate run from a git hook inherits them,
#: and every ``git -C`` below would then describe the hook's repository rather than the
#: directory it names.
_GIT_DISCOVERY_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")


class GitUnavailable(RuntimeError):
    """git could not be run, so whether a nested ``.git`` is a checkout of this tree is unknown."""


def _canonical(path: Path) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def _run_git(directory: Path, *args: str) -> subprocess.CompletedProcess:
    """``git -C directory *args`` with discovery redirection stripped; GitUnavailable if git cannot run."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_DISCOVERY_ENV}
    try:
        return subprocess.run(
            ["git", "-C", str(directory), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitUnavailable(f"git could not be run in {directory}: {exc}") from exc


def _registered_worktrees(root: Path) -> FrozenSet[str]:
    """Every worktree path ``git worktree list`` reports for ``root``'s repository, canonicalised.

    Empty when git ran and does not recognise ``root``: such a root has no worktrees to excuse.
    """
    done = _run_git(root, "worktree", "list", "--porcelain")
    if done.returncode != 0:
        return frozenset()
    return frozenset(
        _canonical(Path(line[len("worktree "):]))
        for line in done.stdout.splitlines()
        if line.startswith("worktree ")
    )


def _git_identity(directory: Path) -> Optional[Tuple[str, str]]:
    """``(top level, common directory)`` as git resolves them from ``directory``, or None.

    None means git ran and refused the directory. :class:`GitUnavailable` means git did not run;
    answering that case from the shape of the ``.git`` entry is the proxy this replaces.
    """
    done = _run_git(directory, "rev-parse", "--show-toplevel", "--git-common-dir")
    lines = done.stdout.splitlines()
    if done.returncode != 0 or len(lines) != 2:
        return None
    common = Path(lines[1])
    if not common.is_absolute():
        common = Path(directory) / common  # git prints it relative to the -C directory
    return _canonical(Path(lines[0])), _canonical(common)


def _is_checkout_of(directory: Path, root: Path, identities: Optional[Dict[Any, Any]] = None) -> bool:
    """True only when ``directory`` is a registered worktree of ``root``'s repository and git agrees.

    Two conditions, each closing a counterfeit the other admits:

    * ``git worktree list`` for ``root`` names ``directory``. Asking git from inside the directory
      is not enough: a ``.git`` file reading ``gitdir: <root>/.git`` makes git report the
      directory as its own top level over the root's common directory, though no worktree was
      ever registered there.
    * git, run from ``directory``, reports it as its own top level over the root's common
      directory. The listing alone keeps a registered worktree whose ``commondir`` was deleted,
      which git no longer opens.

    The shape of a ``.git`` entry was the test before either: a zero-byte ``HEAD``, a ``gitdir:``
    line pointing at nothing and an unrelated ``git init`` each passed it and hid a duplicate
    skill tree from gate 2.

    ``identities`` caches every git answer for the duration of one gate run.
    """
    cache = {} if identities is None else identities

    def identity(path: Path) -> Optional[Tuple[str, str]]:
        if path not in cache:
            cache[path] = _git_identity(path)
        return cache[path]

    listing_key = ("worktree list", root)
    if listing_key not in cache:
        cache[listing_key] = _registered_worktrees(root)
    if _canonical(directory) not in cache[listing_key]:
        return False
    root_identity = identity(root)
    if root_identity is None or root_identity[0] != _canonical(root):
        return False  # a root git does not recognise has no worktrees to excuse
    found = identity(directory)
    return found is not None and found[0] == _canonical(directory) and found[1] == root_identity[1]


def check_skill_tree_uniqueness(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 2 (Skill Tree Uniqueness): every SKILL.md in the tree lives under skills/.

    This checked one hardcoded path, ``.agents/skills``, so a duplicate tree anywhere else
    passed: `jnwb/skills/` and `docs/skills/` were both accepted when constructed. The
    canonical tree is `skills/`, and a second one is the hazard whatever it is called.
    """
    root = repo_root or REPO_ROOT
    violations = []
    identities: Dict[Any, Any] = {}
    git_unavailable: Optional[str] = None
    for skill in sorted(root.rglob("SKILL.md")):
        relative = skill.relative_to(root)
        if relative.parts[0] in EPHEMERAL_ROOT_DIRS:
            continue  # another package's skills inside a .venv are not this tree
        if git_unavailable is None:
            try:
                if _is_inside_nested_checkout(skill, root, identities):
                    continue  # a worktree is this tree seen twice, not two trees
            except GitUnavailable as exc:
                git_unavailable = str(exc)  # nothing is excused without git's answer
        if relative.parts[0] != "skills":
            violations.append(
                f"DUPLICATE_SKILL_TREE: {relative.as_posix()} is a SKILL.md outside skills/. "
                "The canonical tree is skills/; a second tree is what this gate exists for."
            )
    if git_unavailable is not None:
        violations.append(
            f"GIT_UNAVAILABLE: {git_unavailable}. A nested .git entry is excused only when git "
            "says it is a worktree of this repository, so every SKILL.md below one stayed in scope."
        )
    return violations


def check_no_hardcoded_test_paths(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 3 (Test Independence): no machine-local hardcoded drive paths in tests or scripts.

    Scanned `tests/` alone until 2026-09-20, when a script shelled out to BY the suite was added
    to `scripts/` carrying `C:\\workspace\\jnwb`. The pattern below matched it; the scope never
    reached it, so the test that ran that script measured one machine's tree wherever it ran.
    A gate whose scope excludes the directory the defect lands in is not a weaker gate, it is
    absent. `scripts/` is in scope because the suite executes it.
    """
    root = repo_root or REPO_ROOT
    scan_dirs = [d for d in (root / "tests", root / "scripts") if d.exists()]
    if not scan_dirs:
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
    for py_file in sorted(p for d in scan_dirs for p in d.rglob("*.py")):
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
    ".gitattributes",
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
        # `.git` is the checkout marker, not repository content, and its TYPE varies: a directory
        # in an ordinary clone, a one-line file in a linked worktree. It was allowlisted only as a
        # directory, so gate 4 rejected every agent worktree and took gates 5 through 13 with it.
        # Three separate packets reported the same red suite before this was found.
        if entry.name == ".git":
            continue
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
    5. Every classifier in `pyproject.toml` is run by a leg of the `workflow.yml` matrix.
       Checks 2 and 3 both route through a constant in this file, so shrinking
       PYTHON_SUPPORTED and PYTHON_CI_REQUIRED together satisfies both while a declared
       version goes untested -- every assertion in them is a containment or a membership,
       and all of them survive that edit. This check reads the two files and compares them
       to each other, so no edit to a constant can make it agree with a wrong tree.
    6. `README.md` and `docs/install.md` state the floor `requires-python` declares and the
       interpreter set the test matrix runs, compared with those files and not a constant.
    """
    root = repo_root or REPO_ROOT
    violations = []
    # Set by block 1 when pyproject.toml is readable; block 3 compares it against the
    # matrix. None means the classifiers are unknown, which block 1 has already reported.
    declared: Optional[set] = None
    # Set by blocks 1 and 3 from the files themselves; block 4 holds the prose surfaces to them.
    floor_declared: Optional[str] = None
    tested: Optional[set] = None

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
            # And against the surfaces themselves, with no constant in between. Comparing only to
            # PYTHON_FLOOR let 06-64 move requires-python, PYTHON_FLOOR and the order of
            # PYTHON_SUPPORTED together and pass 13 gates and 241 tests while pip would refuse to
            # install on a version whose classifier the package still advertises. An editor can
            # change a constant; it cannot make the lowest classifier stop being the lowest.
            stated_floor = re.search(r">=\s*(\d+\.\d+)", spec)
            if stated_floor is not None:
                floor_declared = stated_floor.group(1)
                declared_versions = sorted(
                    {
                        m.group(1)
                        for m in re.finditer(
                            r'"Programming Language :: Python :: (\d+\.\d+)"', pyproject_text
                        )
                    },
                    key=lambda v: tuple(int(p) for p in v.split(".")),
                )
                if declared_versions and stated_floor.group(1) != declared_versions[0]:
                    violations.append(
                        f"PYTHON_FLOOR_DISAGREES_WITH_CLASSIFIERS: requires-python declares a "
                        f">={stated_floor.group(1)} floor while the lowest classifier is "
                        f"{declared_versions[0]}. A user on {declared_versions[0]} is told the "
                        "package supports them and pip refuses to install it."
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
        # By path, not by first match. `re.search` took whichever `python-version:` list came
        # first in the file, so 06-64 put a decoy job above `jobs.test` and passed gate 8 with the
        # real matrix saying something else. "The first matrix in the file" was the proxy; "the
        # matrix the test job runs" is the invariant, and only a parse reaches it.
        tested = _test_job_matrix(wf_text)
        if tested is None:
            violations.append(
                "PYTHON_FLOOR_INCONSISTENCY: workflow.yml declares no python-version matrix under "
                "jobs.test.strategy.matrix"
            )
        else:
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

            # 3b. The two files against each other, with no constant in between.
            # PYTHON_CI_REQUIRED is what an editor changes to make this gate agree with a
            # tree that ships an untested classifier: reverting it to ("3.12", "3.14") and
            # shrinking the matrix to match leaves every check above satisfied and prints
            # "all agree" over a 3.13 no leg runs. This one cannot be satisfied that way,
            # because neither side of it is a constant.
            if declared is not None:
                for unrun in sorted(declared - tested):
                    violations.append(
                        f"PYTHON_CLASSIFIER_UNTESTED: pyproject.toml carries a classifier for "
                        f"Python {unrun}, which no leg of the workflow.yml test matrix "
                        f"{sorted(tested)} runs. A claimed version is a tested version."
                    )

    # 4. The prose surfaces a user reads before installing: README.md and docs/install.md each
    # state the floor and the tested set, and both are held to the files above rather than to
    # a constant. docs/install.md was once corrected by hand because nothing here read it.
    for rel in ("README.md", "docs/install.md"):
        path = root / rel
        if not path.exists():
            violations.append(f"PYTHON_FLOOR_INCONSISTENCY: {rel} not found")
            continue
        text = path.read_text(encoding="utf-8")
        floor = re.search(r"Requires Python \**(\d+\.\d+) or newer", text)
        if floor is None:
            violations.append(
                f"PYTHON_FLOOR_INCONSISTENCY: {rel} does not state the Python floor as "
                "'Requires Python X.Y or newer'"
            )
        elif floor_declared is not None and floor.group(1) != floor_declared:
            violations.append(
                f"PYTHON_DOC_FLOOR_SKEW: {rel} says Python {floor.group(1)} or newer while "
                f"requires-python declares >={floor_declared}"
            )
        listed = re.search(r"Tested in CI on ([\d., and]+\d)", text)
        if listed is None:
            violations.append(
                f"PYTHON_FLOOR_INCONSISTENCY: {rel} does not state the tested interpreters as "
                "'Tested in CI on ...'"
            )
            continue
        stated = set(re.findall(r"\d+\.\d+", listed.group(1)))
        reference = tested if tested is not None else declared
        if reference is not None and stated != reference:
            violations.append(
                f"PYTHON_DOC_CI_SKEW: {rel} says CI tests {sorted(stated)} while the workflow "
                f"matrix runs {sorted(reference)}"
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


#: Terms naming a mechanism of this repository's own process of building jnwb, gated as phrases
#: rather than as words.
#:
#: The one-sentence rule: a term belongs here when it names part of how this repository is worked
#: on -- the delegation packets, the two stacks, the worktrees, the harness gates, the role files
#: -- and is spelled specifically enough that no sentence about what jnwb does for a caller can
#: contain it.
#:
#: The second half is the whole difficulty, and 06-02 retired a rule that failed it. The old rule
#: gated the word "agent", which is a proxy: agents, skills and routing are public jnwb
#: capabilities and five published pages describe them. Each exclusion below was resolved against
#: the live corpus rather than assumed, because a gate justified by a guess is the same defect one
#: layer up:
#:
#:   "agent", "skill", "routing"  -- public capabilities; `docs/agents.md` is an entire page of them
#:   "batch"                      -- `docs/02:11` "batch jobs", `docs/api.md` `batch_size=`
#:   "authority"                  -- `docs/agents.md:85` "authority loading order"
#:   "actor", "critic", "verifier" -- ordinary English before they are role names here
#:
#: Four of the six stems under `artifacts/agents/` are ordinary English, so only the two that are
#: internal by construction appear here. **This gate therefore does not claim that no internal
#: vocabulary reaches `docs/`; it claims that these terms do not.**
#:
#: "packet" was held out of this list while one legitimate-looking use remained --
#: `docs/documentation_form.md:23` used it in its internal sense, and gating it then would have
#: been gating a common word to catch one sentence, which is the 06-02 failure mode. That
#: sentence now reads "any change that trims, retitles or reformats documentation", and `grep`
#: across `docs/` finds **zero** remaining occurrences of the word in any form, so the bare term
#: is gated and its live zero is a true negative rather than a gap (P-98). The use that would
#: legitimately reintroduce it is a networking one -- a streaming page describing packets on the
#: wire -- and that is the case to revisit this entry for, not a reason to leave it ungated now.
INTERNAL_PROCESS_TERMS: Tuple[str, ...] = (
    # "delegation packet" was removed when "packet" was added: the bare term subsumes it, so it
    # could never be the sole reason for a violation and every hit would be reported twice. A
    # term that cannot fire on its own is the dead-entry class this module already carries a
    # scar from -- three multi-word terms were silently dead while the gate reported PASS.
    "packet",
    "todo stack",
    "todo_stack.md",
    "problem stack",
    "problem_stack.md",
    "fact_stack.md",
    "harness gate",
    "harness_gate.py",
    "worktree",
    "fan-out",
    "artifacts/agents/",
    "docs-harness",
    "jnwb-developer",
)


def _internal_term_pattern(term: str) -> Any:
    """Match one gated term allowing plural, case and space/hyphen variation.

    Spelling the terms as plain literals would let "Delegation Packets" and "fan out" through,
    which is a gate passing for the wrong reason rather than a gate with a narrow scope.

    Built by splitting and rejoining rather than by patching `re.escape`'s output. Escaping first
    and then replacing "\\ " and "\\-" in sequence was tried and is silently wrong: the first
    substitution inserts a "[\\s\\-]+" that contains "\\-", which the second substitution then
    rewrites into "[\\s[\\s\\-]+]+". That compiles, matches nothing that matters, and made three
    of the multi-word terms dead while the gate still reported PASS.
    """
    body = r"[\s\-]+".join(re.escape(part) for part in re.split(r"[\s-]+", term))
    # The edges guard against `\w` and not against `[\w-]`. Excluding a neighbouring hyphen was
    # tried and loses the compounds these terms are most often written as: "worktree-local" and
    # "harness-gate-adjacent" both escaped it while meaning exactly the gated thing.
    pattern = f"(?<!\\w){body}s?"
    # Only guard the right edge when the term ends in a word character: `artifacts/agents/` is
    # always followed by a filename, and a trailing `(?!\w)` would make it match nothing.
    if term[-1].isalnum() or term[-1] == "_":
        pattern += "(?!\\w)"
    return re.compile(pattern, re.IGNORECASE)


def check_internal_process_vocabulary(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 14 (Internal Process Vocabulary): repository-process terms stay out of public docs.

    06-02 ruled the boundary on 2026-09-19: public documentation may describe agents, skills and
    routing, because those are jnwb capabilities a caller uses; internal repository-agent roles,
    harness and process vocabulary, private coordination state and implementation-only
    terminology may not appear there. The ruling says to gate the distinction mechanically *where
    practical*, and that qualifier is load-bearing -- the rule it replaced gated the word "agent"
    and was broken by four published pages the day it was written.

    Scope is `docs/**/*.md`, which is the surface 06-02 and 06-68 both name. A generated or
    included page is scanned like any other, and its fix goes to the generator.

    `README.md` is deliberately **not** in scope, and the reason is a measurement rather than an
    oversight. Scanning it too was tried first and it fails on one line: `README.md:132` links
    `artifacts/todo_stack.md` from the Contributing section, to tell a contributor where the
    queued work is. Whether the most public file in the repository may point at private
    coordination state is a boundary question for the ruling that owns the boundary, not
    something a gate should settle by being widened until it wins. Widen the scope here once that
    line is ruled on -- and do not instead drop `todo_stack.md` from the term list, which is the
    edit that would make this pass while the boundary moved.
    """
    root = repo_root or REPO_ROOT
    violations = []

    docs_dir = root / "docs"
    pages = sorted(docs_dir.rglob("*.md")) if docs_dir.is_dir() else []

    # A sweep that finds no files reports no violations, which reads exactly like a clean tree.
    # Gate 8's three `if not path.exists()` blocks exist for the same reason.
    if not pages:
        return [
            "INTERNAL_VOCABULARY: no public documentation found to scan under "
            f"{docs_dir}; the sweep is broken, not the tree"
        ]

    patterns = [(term, _internal_term_pattern(term)) for term in INTERNAL_PROCESS_TERMS]
    for page in pages:
        rel = page.relative_to(root).as_posix()
        for lineno, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
            for term, pattern in patterns:
                found = pattern.search(line)
                if found:
                    violations.append(
                        f"INTERNAL_VOCABULARY: {rel}:{lineno} says {found.group(0)!r}. "
                        f"{term!r} names part of how this repository is worked on and has no "
                        "public-interface use. Say what the reader can do, or move the sentence "
                        "out of the published documentation."
                    )
    return violations


#: An item or problem identifier from the coordination stacks: `P-29`, `P-C7`, `06-55`,
#: `0.2.4-04`. The item form requires a leading zero because two-digit ranges are ordinary
#: library prose (`14-30 Hz`, `50-80`), and every edge excludes a neighbouring word character,
#: dot, slash or hyphen, so a date (`2026-09-23`), a version (`0.2.6`) and a DOI fragment
#: (`s41593-020-00744-x`) never match.
PROCESS_IDENTIFIER = re.compile(
    r"(?<![\w./\-])(?:P-C?\d{1,3}|0\d-\d{2,3}|\d+\.\d+\.\d+-\d{2,3})(?![\w\-])"
)


def check_no_process_identifiers_in_library(repo_root: Optional[Path] = None) -> List[str]:
    """Part of gate 14: no item or problem identifier anywhere in `jnwb/**/*.py`.

    The head rule of `AGENTS.md` keeps internal process terminology out of the library surface,
    comments and docstrings included. Identifiers were the form it took there: behaviour was
    explained by citing the stack row that changed it, which tells a library reader nothing.
    The scan is textual, so comments, docstrings and string constants are all covered.
    """
    root = repo_root or REPO_ROOT
    modules = sorted(
        py for py in (root / "jnwb").rglob("*.py") if "__pycache__" not in py.parts
    )
    if not modules:
        return [
            f"PROCESS_IDENTIFIER: no library source found to scan under {root / 'jnwb'}; the "
            "sweep is broken, not the tree"
        ]
    violations = []
    for py in modules:
        rel = py.relative_to(root).as_posix()
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            for found in PROCESS_IDENTIFIER.finditer(line):
                violations.append(
                    f"PROCESS_IDENTIFIER: {rel}:{lineno} cites {found.group(0)!r}. State the "
                    "behaviour it stands for instead; the identifier means nothing to a reader "
                    "of the library."
                )
    return violations


#: The two coordination stacks gate 15 reads. Both are tracked; a missing one is a broken
#: sweep rather than a clean tree, and is reported as such.
TODO_STACK = "artifacts/todo_stack.md"
PROBLEM_STACK = "artifacts/problem_stack.md"


def _code_span_mask(text: str) -> bytearray:
    """A byte per character, 1 where that character sits inside a code span or fenced block.

    The stacks quote their own rules, so this cannot be skipped. `artifacts/todo_stack.md`
    contains the literal ``Writes:`` inside a code span twice, where 06-94 states the rule it
    is asking for. A scanner that treats those as field labels starts in the middle of a span,
    has its backtick parity inverted from that point on, and pairs the gaps *between* code
    spans instead of the spans. The first version of this check did exactly that: two labels
    swallowed 12,488 and 11,377 characters to the end of the file, and it still reported zero
    violations -- not because the stack was clean, but because it was no longer looking at
    code spans at all. A run-on field is the failure this mask exists to prevent.
    """
    mask = bytearray(len(text))
    index, end = 0, len(text)
    while index < end:
        if text.startswith("```", index):
            close = text.find("```", index + 3)
            close = end if close == -1 else close + 3
            for offset in range(index, close):
                mask[offset] = 1
            index = close
            continue
        if text[index] == "`":
            close = text.find("`", index + 1)
            newline = text.find("\n", index + 1)
            # An inline span closes on its own line; a lone backtick is not a span.
            if close != -1 and (newline == -1 or close < newline):
                for offset in range(index, close + 1):
                    mask[offset] = 1
                index = close + 1
                continue
        index += 1
    return mask


def _writes_fields(text: str) -> List[Tuple[int, str]]:
    """Every `Writes:` field, as (line number, field text), bounded at its own sentence end.

    The boundary is where this check is hard, not the pattern. A field wraps across up to four
    lines, and a `.` inside a code span is content -- `docs/api.md` is a path, not two
    sentences -- so the scan ends at the first `.` outside a code span that is followed by
    whitespace, with a blank line as a backstop so a malformed field cannot run past its own
    paragraph.

    Bounding by a fixed character count instead reports prose as a violation. At 220 characters
    this named 06-67, whose text *discusses* `tests/`, and 06-73, which names the cache
    directory it exists to exclude. Both items are correct. A check that fires on prose is
    worse than no check, because it teaches its reader to dismiss the output, and that is how
    the one real violation gets waved through.
    """
    return [(lineno, field) for lineno, field, _end in _writes_field_spans(text)]


def _writes_field_spans(text: str) -> List[Tuple[int, str, int]]:
    """`_writes_fields` plus each field's end offset, which the truncation check needs.

    Split out rather than duplicated: a second copy of this scan would be a second boundary
    rule, and the two would drift. The offset is what `_suspected_truncated_writes` inspects,
    and recovering it with `text.find` instead would alias two identical fields to one site.
    """
    mask = _code_span_mask(text)
    spans: List[Tuple[int, str, int]] = []
    for label in re.finditer(r"Writes:", text):
        if mask[label.start()]:
            continue  # the rule quoted in prose, not a field declaring a write set
        index = label.end()
        paragraph = text.find("\n\n", index)
        stop = len(text) if paragraph == -1 else paragraph
        while index < stop:
            if (
                text[index] == "."
                and not mask[index]
                and (index + 1 >= stop or text[index + 1].isspace())
            ):
                break
            index += 1
        spans.append(
            (text.count("\n", 0, label.start()) + 1, text[label.end():index], index)
        )
    return spans


#: Content that continues a `Writes:` field past the point the sentence boundary stopped: a run
#: of backtick tokens, optionally joined by commas or `and`. Anything else -- a capital letter, a
#: field label, prose -- is the next sentence and not part of the field.
_CONTINUES_AS_PATHS = re.compile(r"[\s]*(?:and\s+)?`[^`\n]*`(?:[\s,]*(?:and\s+)?`[^`\n]*`)*")


def _suspected_truncated_writes(text: str) -> List[Tuple[int, str]]:
    """`Writes:` fields whose text ends immediately before more path-like tokens.

    06-67 read ``Writes: `jnwb/nwb_io.py`, `artifacts/goal.md`, AUTONOMY: none.`` on one line
    and ``` `docs/errors.md`, `tests/`. ``` on the next. Any parser bounded by a sentence stops
    at that full stop and never sees the last two entries, one of which was a genuine bare
    `tests/` -- the exact P-108 defect this gate exists to catch, sitting undetected inside the
    gate's own live zero (P-125).

    The boundary is **not** changed, because the replacement P-125 prescribes -- a run of
    backtick tokens separated only by commas and whitespace -- does not fit the data. Measured
    against the live stack, that rule read *fewer* tokens in six fields and more in none, and
    nothing at all in two: the fields legitimately interleave prose, as in
    ``Writes: a new page under `docs/*.md` (named at dispatch; ...)`` and
    ``Writes: the routed skill file and `tests/test_skills_validation.py``. Bounding at the
    next field label instead runs into free-prose bodies, which is the false-positive failure
    the boundary docstring already records.

    So instead of moving the boundary, the gate says when it might be in the wrong place. A
    field followed immediately by more backticked paths is reported for a human to read. That
    turns a silent truncation into a visible question, and needs no solution to a boundary
    problem the stack's own format does not admit.

    Measured on the live stack at the time of writing: zero fields flagged, and zero bare
    directories hidden from the sentence rule. This is a tripwire for the shape's return, not
    a repair of a live instance -- 06-67's field was repaired by hand when P-125 was raised.
    """
    flagged: List[Tuple[int, str]] = []
    for lineno, _field, end in _writes_field_spans(text):
        after = end + 1 if end < len(text) and text[end] == "." else end
        match = _CONTINUES_AS_PATHS.match(text, after)
        if not match or not match.group(0).strip():
            continue
        tail = match.group(0)
        if not any("/" in token for token in re.findall(r"`([^`\n]*)`", tail)):
            continue  # a backticked identifier is prose continuing; only paths look truncated
        flagged.append((lineno, " ".join(tail.split())))
    return flagged


#: A present-tense assertion that the item is blocked. Deliberately shallow, and deliberately
#: not taught to parse negation: the repair sentence written to discharge 06-103's stale block
#: read "this item is no longer blocked on it", which a phrase list matches as an assertion.
#: That sentence was reworded to "that block is discharged" instead, because a phrase list that
#: tries to read polarity is a worse thing to trust than one that is obviously shallow and
#: prints what it suppressed (P-163).
_BLOCK_ASSERTIONS = (
    "blocked on",
    "blocked by",
    "is blocked",
    "blocked until",
    "waits on",
    "waiting on",
    "cannot start until",
    "needs a ruling",
    "requires a ruling",
    "awaits a ruling",
)

#: The phrase list as one alternation, longest first so `blocked until` is not read as the
#: shorter `blocked` prefix of another entry.
_ANY_BLOCK_ASSERTION = re.compile(
    "|".join(re.escape(p) for p in sorted(_BLOCK_ASSERTIONS, key=len, reverse=True))
)

_ITEM_HEADER = re.compile(r"^### (06-\d+)\b", re.MULTILINE)
_ITEM_ID = re.compile(r"\b06-\d+\b")


def _stack_items(text: str) -> List[Tuple[int, str, str]]:
    """Every `### 06-NN` item, as (line number, id, item text including its header)."""
    starts = list(_ITEM_HEADER.finditer(text))
    items: List[Tuple[int, str, str]] = []
    for position, match in enumerate(starts):
        end = starts[position + 1].start() if position + 1 < len(starts) else len(text)
        items.append(
            (text.count("\n", 0, match.start()) + 1, match.group(1), text[match.start():end])
        )
    return items


#: A field label opens a new clause, and so closes the one before it. Used to bound a `Stop:`
#: clause, which runs to the next label and *not* to the next full stop: 06-89's stop reads
#: "Stop: ... resolved first. Then this waits on 06-77 ...", so the assertion sits one sentence
#: after the key. A first draft keyed the suppression on the sentence and missed it -- P-163's
#: attempt-1 failure with "line" replaced by "sentence", which is P-37 again.
_FIELD_LABEL = re.compile(
    r"\b(?:Release|Role|Skill|Blocked by|Reads|Writes|Reproduce|Do|Discriminator|Accept|"
    r"AUTONOMY|Stop):"
)


def _unwrapped_spans(text: str) -> Tuple[str, List[Tuple[int, int]]]:
    """`text` unwrapped, with each sentence's `(start, end)` offsets into the unwrapped string.

    Offsets rather than substrings, because both suppressions below key on where a match sits
    relative to a clause that can begin in an earlier sentence.
    """
    flat = " ".join(text.split())
    mask = _code_span_mask(flat)
    spans, start = [], 0
    for index, char in enumerate(flat):
        if char == "." and not mask[index] and index + 1 < len(flat) and flat[index + 1] == " ":
            spans.append((start, index + 1))
            start = index + 1
    spans.append((start, len(flat)))
    return flat, [(a, b) for a, b in spans if flat[a:b].strip()]


def _stop_clause_spans(flat: str) -> List[Tuple[int, int]]:
    """Where each `Stop:` clause begins and ends in an unwrapped item body."""
    spans = []
    for stop in re.finditer(r"\bStop:", flat):
        following = _FIELD_LABEL.search(flat, stop.end())
        spans.append((stop.start(), following.start() if following else len(flat)))
    return spans


def _unwrapped_sentences(text: str) -> List[str]:
    """`text` with its hard wrapping removed, split into sentences outside code spans.

    **A physical line is not a semantic unit in this file.** A line-based version of the check
    below flagged three items and suppressed none, because the stack is hard-wrapped and both
    exclusion keys -- a `Stop:` clause and the blocking item's id -- sat on the *previous*
    physical line. Unwrapping raised recall as well as precision: it surfaced 06-89, which the
    line scan had missed entirely (P-163). This is P-125's mechanism in a third guise -- a
    proxy for a unit of meaning mistaken for the unit.
    """
    flat, spans = _unwrapped_spans(text)
    return [flat[a:b].strip() for a, b in spans]


def _blocked_by_none_contradictions(
    text: str,
) -> Tuple[List[Tuple[int, str, str]], List[Tuple[int, str, str, str]]]:
    """Items declaring `Blocked by: none` whose own text asserts they are blocked.

    06-31 recorded `Blocked by: none` and was in fact blocked on data-access authority; 06-32
    inherited that block through `Blocked by: 06-31`, unrecorded too. 06-86 read
    `Blocked by: none` while its body said "Blocked on one ruling" and its Accept clause said
    P-34 closes only once that ruling is recorded -- and the scheduler offered it as
    dispatchable, twice (P-149). The metadata is *confidently wrong rather than absent*, which
    is why every reader trusts it.

    Returns `(flagged, suppressed)`. **Both are returned, and the caller prints the
    suppressions**, because a narrowing that is invisible is how P-125 turned a false positive
    into a blind spot: one of the two cases silenced there was real. Two suppressions are
    applied, each keyed on the match's own position rather than on the sentence it sits in:

    | Suppressed when | Why |
    |---|---|
    | a `Stop:` clause opens before the match | the field states the stop; the clause describes it |
    | every item id in the sentence has retired | the block named is discharged with its item |
    """
    live = {match.group(1) for match in _ITEM_HEADER.finditer(text)}
    flagged: List[Tuple[int, str, str]] = []
    suppressed: List[Tuple[int, str, str, str]] = []

    for lineno, item_id, body in _stack_items(text):
        field = re.search(r"Blocked by:\s*([^.\n]*)", body)
        if not field or field.group(1).strip().lower().rstrip(".") != "none":
            continue
        # Excise *every* field declaration, not just the one read above. `Blocked by: none.`
        # matches the phrase list on its own, and a first draft flagged 33 of 52 live items on
        # nothing but their own metadata. Removing only the first left a second declaration --
        # which a malformed item can carry -- readable as prose.
        prose = re.sub(r"Blocked by:\s*[^.\n]*", " ", body)
        flat, spans = _unwrapped_spans(prose)
        stops = _stop_clause_spans(flat)
        for start, end in spans:
            sentence = flat[start:end].strip()
            # Every occurrence of every phrase, not the first: a sentence whose opening match
            # is suppressed can carry a real assertion afterwards, and stopping at the first
            # would let the suppression cover it.
            reason = None
            for hit in _ANY_BLOCK_ASSERTION.finditer(flat.lower(), start, end):
                at = hit.start()
                if any(a <= at < b for a, b in stops):
                    reason = "inside a `Stop:` clause"
                    continue
                named = set(_ITEM_ID.findall(sentence)) - {item_id}
                if named and not (named & live):
                    reason = f"names only retired items: {', '.join(sorted(named))}"
                    continue
                flagged.append((lineno, item_id, sentence))
                reason = None
                break
            if reason is not None:
                suppressed.append((lineno, item_id, sentence, reason))
    return flagged, suppressed


#: A count of items in summary prose, including the elided form "three more" where the noun
#: carries over from the preceding clause. Requiring the literal word "items" missed the one
#: live instance while matching two sentences that state counts about items they never list.
_ITEM_COUNT = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)\s+"
    r"(?:(?:more|further)\b\s*(?:items?\b)?|items?\b)",
    re.IGNORECASE,
)
_COUNT_VALUE = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
#: A clause break. The ids an assertion enumerates sit in its own clause, so ids beyond the
#: break belong to a different statement -- which is what separates a miscount from "it
#: assigned 16 items to five lanes ... -- the compression lane pointed at 06-24 and 06-51".
_CLAUSE_BREAK = re.compile(r"\s--\s|;")


def _summary_regions(text: str) -> List[Tuple[int, int]]:
    """The spans of `todo_stack.md` that are prose ABOUT items rather than an item body.

    A count inside an item is that item's own statement about its work. A count in a batch
    preamble is a summary of the items below it, and is derived data stored as prose.
    """
    starts = [m.start() for m in _ITEM_HEADER.finditer(text)]
    heads = [m.start() for m in re.finditer(r"^## ", text, re.MULTILINE)]
    regions: List[Tuple[int, int]] = []
    cursor = 0
    for start in starts:
        if start > cursor:
            regions.append((cursor, start))
        following = [h for h in heads if h > start]
        cursor = following[0] if following else len(text)
    if cursor < len(text):
        regions.append((cursor, len(text)))
    return regions


def _miscounted_summaries(text: str) -> List[Tuple[int, str, int, List[str], str]]:
    """Summary sentences whose stated item count disagrees with the ids they enumerate.

    P-133: Batch 0 opened with "Six items wait on a human ruling ... 06-13, 06-18, 06-67,
    06-84, 06-85 and 06-92". Four waited, not six; three of the six named had closed earlier
    the same day; and none of the four gated more than one item, so the sentence named a
    binding constraint that no longer bound. Every number in it is recomputable from the
    fields below it, so storing it as prose could only ever drift, and re-deriving it by hand
    is a fix with a shelf life.

    **"Recompute each count a summary asserts" is not mechanically reliable in general** --
    a first attempt counted every id in the sentence and flagged 2 of 2 as false positives,
    because one sentence carries several counts each governing its own list, and because
    "it assigned 16 items to five lanes, and 14 of those 16 were retired" states counts about
    items it never enumerates. What *is* reliable is the enumerated form, which is the shape
    P-133's own instance had: a count, then the ids, within one clause.

    Measured on the live stack: 1 flagged, and it was real -- "three more are blocked on
    authority Hamm holds: 06-31 and 06-32 on the corpus grant, 06-86 and 06-99 on a ruling
    and that grant respectively" names four. A stricter variant requiring the ids to form a
    contiguous run flagged exactly the same sentence, so it buys no separation and is not
    used.

    The corollary is that a summary asserting a count **without** naming the items cannot be
    checked at all. Batch 0's "three items Hamm must decide" was such a claim, and was two.
    It was rewritten to name them rather than checked by a second mechanism, so the prose is
    now in a form this one rule covers.
    """
    flagged: List[Tuple[int, str, int, List[str], str]] = []
    for start, end in _summary_regions(text):
        base = text.count("\n", 0, start) + 1
        flat, spans = _unwrapped_spans(text[start:end])
        for a, b in spans:
            sentence = flat[a:b].strip()
            counts = list(_ITEM_COUNT.finditer(sentence))
            for index, counted in enumerate(counts):
                word = counted.group(1).lower()
                asserted = _COUNT_VALUE.get(word, int(word) if word.isdigit() else None)
                if asserted is None:
                    continue
                stop = counts[index + 1].start() if index + 1 < len(counts) else len(sentence)
                brk = _CLAUSE_BREAK.search(sentence, counted.end(), stop)
                span = sentence[counted.end():brk.start() if brk else stop]
                ids = sorted(set(_ITEM_ID.findall(span)))
                if ids and asserted != len(ids):
                    flagged.append((base, counted.group(0).strip(), asserted, ids, sentence))
    return flagged


#: A numeral immediately followed by "item"/"items". The lookbehind keeps the digits after the
#: hyphen of an item id, a problem row or a date, and those after a decimal point, a thousands
#: comma or a section sign, from reading as a count.
_NUMERAL_ITEMS = re.compile(r"(?<![\w.,\xa7-])(\d+)\s+items?\b", re.IGNORECASE)
#: What makes that count a claim about the whole stack rather than about a subset of it.
_TOTAL_BEFORE = re.compile(r"(?:\bof\s+the|\ball(?:\s+of\s+the|\s+the)?)\s+$", re.IGNORECASE)
_TOTAL_AFTER = re.compile(r"\s+(?:below\b|in\s+(?:this|the)\s+stack\b)", re.IGNORECASE)


def _inside_quotation(sentence: str, at: int) -> bool:
    """Whether offset `at` sits inside a double-quoted span: a report of what a line once said."""
    before = sentence[:at]
    opened = before.count("\N{LEFT DOUBLE QUOTATION MARK}")
    closed = before.count("\N{RIGHT DOUBLE QUOTATION MARK}")
    return before.count('"') % 2 == 1 or opened > closed


def _stale_item_totals(text: str) -> List[Tuple[int, str, int, int, str]]:
    """Summary sentences stating a total number of items that differs from the live count.

    The dispatch map read "37 of the 57 items below" while the stack held 52, and before that
    "45 of the 74 items below" through twenty revisions of the stack as it shrank to 57. Neither
    names an id, so `_miscounted_summaries` has nothing to count them against; the total is
    checkable only against the stack itself, which is the count of `### 06-NN` headers.

    A total is a numeral directly before "items", outside code spans and quotations, in a
    summary region, whose clause names no item id, and which is marked as the whole stack:
    preceded by "of the", "all", "all the" or "all of the", or followed by "below" or "in
    this/the stack". Run over every revision of the stack, this flagged the two stale totals
    above and nothing else. Two unmarked counts in the same history, "It assigned 16 items to
    five lanes" and "24 items declared `tests/`", are statements about a subset, and a
    quotation of an earlier total (the map once read "45 of the 74 items below") is history
    rather than a claim; none of the three is flagged.

    Not caught, by design: number words ("fifty-seven items"), an adjective between the numeral
    and the noun ("57 open items"), a total phrased without a marker ("the stack holds 57
    items"), counts inside an item body, and the subset numeral in "37 of the 57".
    """
    live = len(_ITEM_HEADER.findall(text))
    stale: List[Tuple[int, str, int, int, str]] = []
    for start, end in _summary_regions(text):
        base = text.count("\n", 0, start) + 1
        flat, spans = _unwrapped_spans(text[start:end])
        mask = _code_span_mask(flat)
        for a, b in spans:
            sentence = flat[a:b]
            for counted in _NUMERAL_ITEMS.finditer(sentence):
                if mask[a + counted.start()] or _inside_quotation(sentence, counted.start()):
                    continue
                if not (
                    _TOTAL_BEFORE.search(sentence[:counted.start()])
                    or _TOTAL_AFTER.match(sentence, counted.end())
                ):
                    continue
                brk = _CLAUSE_BREAK.search(sentence, counted.end())
                if _ITEM_ID.search(sentence[counted.end():brk.start() if brk else len(sentence)]):
                    continue  # an enumerated count is `_miscounted_summaries`'s to check
                asserted = int(counted.group(1))
                if asserted != live:
                    stale.append((base, counted.group(0), asserted, live, sentence.strip()))
    return stale


#: Unescaped `|` delimits a GFM table cell. `\|` is content wherever it appears, including
#: inside a code span: GFM splits a row into cells *before* it parses inline code, which is
#: why P-29 and P-81 shipped rows whose backticked pipes silently became extra columns.
_ESCAPED_PIPE = re.compile(r"\\\|")


#: Files that are *derived*, with what invalidates each and what regenerates it. This is the
#: generation closure P-173 asked for, written down: a lane's write set can be complete,
#: correct and disjoint and still invalidate a file outside it, so disjointness alone is not
#: sufficient for concurrency. 06-47 added a parameter to `probe_geometry`'s signature and
#: `docs/api.md` went stale the moment it landed, because no lane edits that page by hand and
#: so it was in no lane's write set. The integrated suite went 25 failed, 18 of them
#: `test_every_gate_runs.py` cascading from one real gate-9 failure -- 25 masks on one defect,
#: and a count of failures is not a count of causes.
#:
#: The obligation is placed on the **integrator**, not on the write sets, and that choice was
#: measured rather than assumed: 7 of 52 live items name a path under `jnwb/` and none names
#: `docs/api.md`, so requiring them all to name it would make those 7 mutually exclusive with
#: one another and declare a maximum parallelism of one across every item that touches the
#: package. That is exactly the defect P-108 recorded for bare directories, in a new spelling.
#:
#: `tracked` distinguishes a file that must be committed in step from one generated per tree
#: and deliberately gitignored -- `artifacts/state.md` is the latter, so its absence in a
#: fresh worktree is correct and not drift.
GENERATED_FROM = (
    {
        "derived": "docs/api.md",
        "sources": ("jnwb/",),
        "generator": "scripts/generate_api_md.py",
        "verified_by": "gate 9, which regenerates the page and compares it to the committed copy",
        "tracked": True,
    },
    {
        "derived": "artifacts/state.md",
        "sources": ("<any HEAD move>",),
        "generator": "scripts/reconstruct_state.py",
        "verified_by": "`--check`, which AGENTS.md section 3 Prepare runs before reading the file",
        "tracked": False,
    },
)


def _row_delimiters(line: str) -> int:
    return _ESCAPED_PIPE.sub("", line).count("|")


def check_stack_form_consistency(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 15 (Stack Form Consistency): the coordination stacks stay machine-readable.

    Two defects in the form of the stacks themselves, both repaired by hand during 0.2.6 and
    both recurring because nothing read the files.

    **Declared write sets must be comparable.** Two agents may run concurrently exactly when
    their `Writes` sets are provably disjoint, so a `Writes:` field naming a bare directory
    answers no question a scheduler asks. Measured at `5257e430`: 37 of 60 items named one and
    31 named the same directory, which declared a maximum parallelism of one across more than
    half the work (P-108). A glob passes, because `docs/*.md` conflicts honestly with
    `docs/api.md` while `docs/` conflicts with everything and says nothing.

    **Every problem row carries its own table's column count.** The open table is
    `ID | Problem | Found by | Answered in` and the closed table is
    `ID | Problem | Disposition | Evidence` -- four columns each, but not the same four, so a
    row moving between them acquires the wrong shape. This shipped five times in one session.
    """
    root = repo_root or REPO_ROOT
    violations: List[str] = []

    todo_path = root / TODO_STACK
    if not todo_path.is_file():
        violations.append(f"STACK_FORM: {TODO_STACK} is missing; the sweep is broken, not the tree")
    else:
        fields = _writes_fields(todo_path.read_text(encoding="utf-8"))
        # A sweep that finds no field reports no violation, which reads exactly like a clean
        # stack. Gate 14 and gate 8 guard the same way.
        if not fields:
            violations.append(
                f"STACK_FORM: no 'Writes:' field found in {TODO_STACK}; the sweep is broken"
            )
        stack_text = todo_path.read_text(encoding="utf-8")
        for lineno, tail in _suspected_truncated_writes(stack_text):
            violations.append(
                f"STACK_FORM: {TODO_STACK}:{lineno} has a 'Writes:' field followed immediately "
                f"by more paths -- {tail}. The field is bounded at a sentence, so those entries "
                "are not being read, and a bare directory among them would be invisible to the "
                "check above. Put the whole write set in one sentence."
            )
        flagged, suppressed = _blocked_by_none_contradictions(stack_text)
        for lineno, item_id, sentence in flagged:
            violations.append(
                f"STACK_FORM: {TODO_STACK}:{lineno} item {item_id} declares 'Blocked by: none' "
                f"and its own text says it is blocked -- \"{sentence[:180]}\". A scheduler reads "
                "the field, so the item is offered as dispatchable. Record the block in the "
                "field, or reword the sentence if the block is discharged."
            )
        # Printed whether or not anything was flagged. A suppression nobody reads is how the
        # narrowing in P-125 turned a false positive into a blind spot -- one of the two cases
        # silenced there was real. These go to stdout rather than into `violations`: they are
        # not defects, and a reader has to be able to check that each narrowing was right.
        for lineno, item_id, sentence, why in suppressed:
            print(
                f"STACK_FORM note: {TODO_STACK}:{lineno} item {item_id} asserts a block and was "
                f"suppressed, {why} -- \"{sentence[:180]}\""
            )
        for lineno, phrase, asserted, ids, sentence in _miscounted_summaries(stack_text):
            violations.append(
                f"STACK_FORM: {TODO_STACK}:{lineno} a summary says '{phrase}' and then names "
                f"{len(ids)} -- {', '.join(ids)}. The count is derived from the items below it, "
                f"so prose can only drift from them: \"{sentence[:160]}\""
            )
        for lineno, phrase, asserted, live, sentence in _stale_item_totals(stack_text):
            violations.append(
                f"STACK_FORM: {TODO_STACK}:{lineno} a summary states a total of '{phrase}' and "
                f"the stack holds {live}. A total is derived from the items, so prose can only "
                f"drift from it; drop the number or name the items: \"{sentence[:160]}\""
            )
        for lineno, field in fields:
            for span in re.findall(r"`([^`\n]*)`", field):
                if span.endswith("/"):
                    violations.append(
                        f"STACK_FORM: {TODO_STACK}:{lineno} declares `{span}` in its 'Writes:' "
                        "field. A bare directory cannot be compared against another item's "
                        "write set, so the item is mutually exclusive with everything that "
                        "touches the tree. Name the files, or a glob if the item genuinely "
                        "spans them."
                    )

    problem_path = root / PROBLEM_STACK
    if not problem_path.is_file():
        violations.append(
            f"STACK_FORM: {PROBLEM_STACK} is missing; the sweep is broken, not the tree"
        )
        return violations

    header, header_line, rows, fenced = None, 0, 0, False
    for lineno, raw in enumerate(problem_path.read_text(encoding="utf-8").splitlines(), 1):
        if raw.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        line = raw.strip()
        if not line.startswith("|"):
            header = None  # a blank line or a heading ends the table
            continue
        rows += 1
        count = _row_delimiters(line)
        if header is None:
            header, header_line = count, lineno
            continue
        if count != header:
            violations.append(
                f"STACK_FORM: {PROBLEM_STACK}:{lineno} has {count} cell delimiters against the "
                f"{header} its table declares at line {header_line}. Either a cell is missing, "
                "or a `|` inside a code span was left unescaped -- GFM splits cells before it "
                r"parses inline code, so write `\|` even inside backticks."
            )
    if not rows:
        violations.append(f"STACK_FORM: no table row found in {PROBLEM_STACK}; the sweep is broken")

    # The generation closure is a file that points at other files, so it goes stale without
    # erroring: a generator that is renamed or a derived path that moves leaves a declaration
    # that still reads as true. Resolve every entry against disk rather than trusting it.
    if not GENERATED_FROM:
        violations.append(
            "STACK_FORM: GENERATED_FROM is empty, so the generation closure declares nothing "
            "and this check passes vacuously"
        )
    for entry in GENERATED_FROM:
        generator = root / entry["generator"]
        if not generator.is_file():
            violations.append(
                f"STACK_FORM: GENERATED_FROM names {entry['generator']} as the generator of "
                f"{entry['derived']}, and no such file exists. A closure that points at a "
                "missing generator cannot tell an integrator what to regenerate."
            )
        derived = root / entry["derived"]
        if entry["tracked"] and not derived.is_file():
            violations.append(
                f"STACK_FORM: GENERATED_FROM declares {entry['derived']} tracked and derived, "
                f"and it is not in the tree. Either it was retired and the entry is stale, or "
                "it was lost."
            )
        for source in entry["sources"]:
            if source.startswith("<"):
                continue  # a described trigger, e.g. a HEAD move, not a path
            if not (root / source).exists():
                violations.append(
                    f"STACK_FORM: GENERATED_FROM says {entry['derived']} derives from "
                    f"{source}, which is not in the tree, so the closure is describing a "
                    "dependency that no longer exists."
                )
    return violations


def _convention(data: bytes) -> Optional[str]:
    """`"CRLF"`, `"LF"`, `"mixed"`, or `None` for a file with no line endings at all."""
    crlf = data.count(b"\r\n")
    bare = data.count(b"\n") - crlf
    if crlf and bare:
        return "mixed"
    if crlf:
        return "CRLF"
    if bare:
        return "LF"
    return None


def _wholesale_conversions(root: Path) -> List[str]:
    """Files whose line-ending convention differs from the bytes committed at HEAD.

    **Gate 16 fails a file that MIXES the two conventions; it cannot see a file whose
    convention was CONVERTED wholesale, which is the failure that actually happens** (P-159).
    The dispatcher inserted a 13-line notice into `artifacts/evidence/0.2.6/compress_fp32_policy.md` with
    `pathlib.Path.write_text`, which opens with `newline=None` and translates `\\n` to
    `os.linesep` on Windows. The file was pure LF, 206 lines, 0 CRLF; afterwards it was 0 LF
    and 219 CRLF -- every line rewritten, a 425-line diff for a 13-line insertion, and the real
    change buried inside it. **Gate 16 passes that**, because the result is perfectly uniform.

    `.gitattributes` states the invariant correctly -- the tree is `-text`, so the committed
    bytes are the convention. The mixed-file rule is a *proxy* for it, and the two are not the
    same: the gap is exactly where the conversion lives. That is P-37's shape, and P-159
    records it as the seventh measured instance this cycle of a check that passes for the
    wrong reason.

    So this compares against the committed bytes rather than against the file itself. It is a
    working-tree check by nature, which is also when the accident is recoverable: once the
    conversion is committed, HEAD carries it and there is nothing left to compare to. A clean
    tree yields nothing, so the discriminators in
    `tests/test_line_endings_survive_an_edit.py` construct a repository and convert a file in
    it -- a live zero here would otherwise be indistinguishable from a working check.
    """
    # An unborn branch -- `git init` with nothing committed -- has no committed bytes for a file
    # to have departed from, so there is nothing to compare and that is not a failure. It is
    # distinguished from a broken git here rather than swallowed with it: a bare `except` around
    # the diff reported "could not compare against HEAD" for five adversarial fixtures that are
    # working exactly as intended, which is a check failing on the absence of its own subject.
    if subprocess.run(
        ["git", "rev-parse", "--verify", "-q", "HEAD"],
        cwd=root, capture_output=True,
    ).returncode != 0:
        return []
    try:
        changed = subprocess.run(
            ["git", "diff", "--name-only", "-z", "HEAD"],
            cwd=root, capture_output=True, text=True, check=True,
        ).stdout.split("\0")
    except Exception as exc:
        return [f"LINE_ENDINGS: could not compare against HEAD under {root} ({exc})"]

    violations: List[str] = []
    for relative in filter(None, changed):
        path = root / relative
        if not path.is_file():
            continue  # deleted in the working tree
        data = path.read_bytes()
        if b"\0" in data[:8000]:
            continue
        try:
            committed = subprocess.run(
                ["git", "show", f"HEAD:{relative}"],
                cwd=root, capture_output=True, check=True,
            ).stdout
        except Exception:
            continue  # added in the working tree, so there is no committed convention yet
        before, after = _convention(committed), _convention(data)
        if before is None or after is None or before == after or "mixed" in (before, after):
            continue  # a mixed file is gate 16's other rule, and is already reported there
        violations.append(
            f"LINE_ENDINGS: {relative} was committed as {before} and is now {after}. Every "
            f"line of the file is rewritten, so the real change is buried in a whole-file "
            f"diff and a byte-anchored edit against it will match nothing. This is what "
            f"`pathlib.Path.write_text` does on Windows, because it opens with newline=None "
            f"and translates to os.linesep -- pass newline='' or write bytes."
        )
    return violations


def check_line_ending_consistency(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 16 (Line Ending Consistency): no tracked text file mixes CRLF and bare LF.

    P-124. Nothing declared a convention and eight tracked files carried both at once. This is
    not cosmetic: a byte-mode edit anchored with the wrong ending matches nothing and reads
    exactly like "the text is not there", and `git apply` refuses a patch whose context lines
    disagree -- five `git apply --check` runs failed in one release before the cause was found.

    The gate deliberately holds each file only against *itself*. Whether `skills/` should stay
    CRLF while every other directory is LF is a cross-directory policy question that P-124
    records the measurement for and does not answer; a mixed file is a defect under either
    answer. `.gitattributes` marks the tree `-text` so a clone reproduces the committed bytes
    on every platform rather than leaving it to each contributor's `core.autocrlf`.
    """
    root = repo_root or REPO_ROOT
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split("\0")
    except Exception as exc:  # no git, or not a checkout: say so rather than passing
        return [f"LINE_ENDINGS: could not list tracked files under {root} ({exc})"]

    violations: List[str] = []
    scanned = 0
    for relative in filter(None, tracked):
        path = root / relative
        if not path.is_file():
            continue  # listed but not checked out, e.g. a sparse checkout
        data = path.read_bytes()
        if b"\0" in data[:8000]:
            continue  # binary
        crlf = data.count(b"\r\n")
        bare = data.count(b"\n") - crlf
        scanned += 1
        if crlf and bare:
            violations.append(
                f"LINE_ENDINGS: {relative} carries {crlf} CRLF and {bare} bare LF. A file that "
                "mixes conventions is inconsistent under any policy; normalise it to the one "
                "its own directory already holds."
            )
    violations.extend(_wholesale_conversions(root))
    if not scanned:
        violations.append(
            f"LINE_ENDINGS: no tracked text file found under {root}; the sweep is broken"
        )
    return violations


#: The placeholder forms a `Skill:` field may carry instead of a skill directory name. A closed
#: set and not a prefix rule: `per skil` must fail, and it does. A placeholder may take a trailing
#: qualifier after a comma -- 06-25 writes `per skill, nine packets` -- so the head segment is what
#: is matched, and the qualifier is prose the gate does not read.
SKILL_PLACEHOLDERS = frozenset({"none", "per skill", "per module", "per finding", "per chain"})

#: `Role:` values naming a person rather than an agent file. Same shape as the skill placeholders:
#: `human, with verifier receipts` is `human` plus a qualifier.
ROLE_PLACEHOLDERS = frozenset({"human", "human ruling", "none"})

#: The three fields gate 17 resolves. `Reads:` and `Writes:` name paths and are gate 15's.
_RESOLVED_FIELDS = ("Skill", "Role", "Blocked by")


def _field_value(body: str, label: str) -> Optional[Tuple[int, str]]:
    """The value of `label:` in an item body, as (offset of the label, value).

    Three things make this harder than a line regex, and each of them was measured on the live
    stack rather than anticipated:

    * **The value wraps.** Fields are hard-wrapped mid-declaration, so the value ends at the next
      field label or the paragraph break, never at the newline.
    * **A field label appears inside a code span.** 06-80's own heading is "Resolve every
      ``Skill:`` field against ``skills/``", and a scanner that reads it extracts the value
      ``` ` field against `skills/` ``` and reports a missing skill directory -- a false positive
      manufactured by the item that asked for the gate. `_code_span_mask` is what excludes it.
    * **The value ends at a sentence, not at the label alone.** `Skill: none. Blocked by: none.`
      bounds on the next label, but the last field in a paragraph has no next label.
    """
    mask = _code_span_mask(body)
    for match in re.finditer(re.escape(label) + r":", body):
        if mask[match.start()]:
            continue  # the label is quoted, not declared
        rest = body[match.end():]
        offsets = [len(rest)]
        following = _FIELD_LABEL.search(rest)
        if following:
            offsets.append(following.start())
        paragraph = rest.find("\n\n")
        if paragraph != -1:
            offsets.append(paragraph)
        value = rest[:min(offsets)]
        return match.start(), " ".join(value.split())
    return None


def _declared_name(value: str) -> str:
    """A field value reduced to the thing it names: sentence-terminated, unbackticked."""
    text = value.strip()
    # The sentence the field sits in ends the value; `jnwb-nwb-data. Blocked by: ...` already
    # bounded on the label, but `Blocked by: 06-06.` and a trailing `.` have not.
    text = re.split(r"\.(?:\s|$)", text, maxsplit=1)[0]
    return text.strip().strip("`*").strip().rstrip(".").strip()


def check_stack_pointers_resolve(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 17 (Stack Pointers Resolve): every `Skill:`, `Role:` and `Blocked by:` field names
    something that exists on this tree.

    P-53: two items declared ``Skill: jnwb-nwb-io``. No such skill has ever existed -- the tree
    holds `jnwb-nwb-data` -- and the name reached two dispatched packets, where nothing errored
    and a packet worked around it silently. The standing rule is that a file pointing at other
    files goes stale without erroring; this pointer never resolved at all, so it did not go
    stale, it was **born wrong**, and a staleness check would not have caught it either. Only
    resolution against the tree catches it, which is what this does.

    P-57 widened it to the cross-references. Of the three directions that widening names, one is
    implemented here and two no longer exist:

    * ``Blocked by:`` -> a live item is **here**. Nothing resolved it before: P-161's parenthesis
      "the blocker direction is checked" refers to a sweep somebody ran, not to a check in any
      script.
    * A problem row's ``Answered in`` -> a live item: `scripts/release_gate.py` STEP 0a requires
      the problem stack to hold no row at release, so no such cell is left to resolve.
    * The todo stack's ``P-NN`` -> a problem row: the id labels a row that has left the problem
      stack, and it resolves through that file's git history rather than against the tree.

    **What this gate cannot see**, stated because narrowing a check is how blind spots are made:
    it resolves the *name* and not the *fit*. ``Skill: jnwb-spiking`` on an item about spectra
    resolves and passes. Nothing here reads whether the named skill is the right one, and nothing
    should -- that is a judgement, and a gate that guesses at it would be a proxy.
    """
    root = repo_root or REPO_ROOT
    violations: List[str] = []

    todo_path = root / TODO_STACK
    if not todo_path.is_file():
        return [f"STACK_POINTER: {TODO_STACK} is missing; the sweep is broken, not the tree"]
    text = todo_path.read_text(encoding="utf-8")
    items = _stack_items(text)
    if not items:
        return [f"STACK_POINTER: no item found in {TODO_STACK}; the sweep is broken, not the tree"]
    live = {ident for _, ident, _ in items}

    skills_dir = root / "skills"
    agents_dir = root / "artifacts" / "agents"
    # A sweep that finds no skill directory would pass every item vacuously.
    available_skills = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
    if not available_skills:
        violations.append(
            f"STACK_POINTER: no skills/*/SKILL.md found under {skills_dir}; every Skill: field "
            "would resolve vacuously, so the sweep is broken, not the tree"
        )
    available_roles = {p.stem for p in agents_dir.glob("*.md")}
    if not available_roles:
        violations.append(
            f"STACK_POINTER: no artifacts/agents/*.md found under {agents_dir}; every Role: "
            "field would resolve vacuously, so the sweep is broken, not the tree"
        )

    resolved = 0
    for lineno, ident, body in items:
        for label in _RESOLVED_FIELDS:
            found = _field_value(body, label)
            if found is None:
                violations.append(
                    f"STACK_POINTER: {TODO_STACK}:{lineno} item {ident} declares no '{label}:' "
                    "field; the scheduler reads it, so an absent field is not a silent default"
                )
                continue
            offset, raw = found
            line = lineno + body.count("\n", 0, offset)
            name = _declared_name(raw)

            if label == "Blocked by":
                # Prose blockers ("all repairs", "a Hamm ruling ...") name no item and resolve to
                # nothing. Only the ids are resolvable, and each one must be live.
                #
                # `name`, the first sentence, and NOT the whole label-bounded span. Measured: the
                # span version reported 12 violations on a pristine tree and every one was the
                # parser's. An item that has been unblocked records why on the line after the
                # field -- 06-06 declares `Blocked by: none.` and then "06-01 and 06-02 were both
                # ruled 2026-09-19 and deleted as complete" -- so a span running to the next
                # field label reads the history as the declaration and flags exactly the items
                # that are correctly maintained. **What the narrowing cannot see:** an id in a
                # second sentence of the field. That is deliberate -- after the first full stop
                # the field is narrating, not declaring -- and `test_a_dead_id_in_the_narration_
                # is_not_read_as_a_blocker` plants both shapes to hold the boundary where it is.
                for ref in re.findall(r"\b06-\d+\b", name):
                    resolved += 1
                    if ref not in live:
                        violations.append(
                            f"STACK_POINTER: {TODO_STACK}:{line} item {ident} is 'Blocked by: "
                            f"{ref}', which is not an item in this stack. A block on a retired "
                            "item is a block that can never lift, and the scheduler reads this "
                            "field."
                        )
                continue

            head = name.split(",")[0].strip().lower()
            if label == "Skill":
                if head in SKILL_PLACEHOLDERS:
                    continue
                segments = [s.strip().strip("`") for s in name.split(",") if s.strip()]
                for segment in segments:
                    resolved += 1
                    if segment not in available_skills:
                        violations.append(
                            f"STACK_POINTER: {TODO_STACK}:{line} item {ident} declares "
                            f"'Skill: {segment}', and skills/{segment}/SKILL.md does not exist. "
                            f"Available: {sorted(available_skills)}. Declared placeholders: "
                            f"{sorted(SKILL_PLACEHOLDERS)}."
                        )
            else:  # Role
                if head in ROLE_PLACEHOLDERS:
                    continue
                resolved += 1
                if name not in available_roles:
                    violations.append(
                        f"STACK_POINTER: {TODO_STACK}:{line} item {ident} declares "
                        f"'Role: {name}', and artifacts/agents/{name}.md does not exist. "
                        f"Available: {sorted(available_roles)}. Declared placeholders: "
                        f"{sorted(ROLE_PLACEHOLDERS)}."
                    )

    # Every item could legally declare `none` for all three fields, and then this gate would pass
    # while resolving nothing. It would still be honest -- there would be nothing to resolve --
    # but it would be indistinguishable from a parser that extracts no values at all, which is
    # this repository's dominant defect shape. So the count is asserted, not assumed.
    if resolved == 0:
        violations.append(
            f"STACK_POINTER: {len(items)} items were read and not one named a skill, a role or a "
            "blocking item. Either the stack genuinely declares nothing, or the field parser is "
            "matching nothing; the gate cannot tell those apart, so it fails rather than pass "
            "vacuously."
        )
    return violations


#: `| jnwb.NAME | type | cell |`. The description cell admits pipes of its own -- a rendered union
#: such as `-> str | None` -- so the `$` anchor is what makes the closing pipe unambiguous.
#: Shared with `tests/test_api_md_member_types.py`, which imports it from here.
API_MD_ROW = re.compile(
    r"^\|\s*jnwb\.([A-Za-z_][A-Za-z0-9_]*)\s*\|([^|]*)\|(.*)\|\s*$",
    re.MULTILINE,
)


def api_member_kind(obj: Any) -> str:
    """What an export is, asked of the object itself.

    A property rather than a list of known types. The defect this answers existed because the
    generator asked ``isinstance(obj, (dict, tuple, frozenset, list))``: an enumeration has to be
    maintained, and the one scalar constant in `__all__` was missing from it.
    """
    import inspect

    if inspect.isclass(obj):
        return "class"
    if inspect.ismodule(obj):
        return "module"
    if callable(obj):
        return "function"
    return "constant"


def check_api_md_member_types(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 18 (API Member Types): each `docs/api.md` Type cell is true of the runtime object.

    **Gate 9 is a fixed point and this is the way out of it.** Its two checks are
    `check_documented_api_matches_all`, which matches the first column only and compares that set
    of names to `jnwb.__all__`, and `check_api_md_is_generated`, which regenerates the page and
    compares it to the committed copy. The first never looks at the Type column; the second
    asserts that the page agrees with the generator, never that either agrees with the runtime. A
    wrong answer produced inside the generator is written into both sides of that comparison,
    where it cancels.

    P-151 proved it rather than arguing it: with `_object_type_name` returning the literal
    ``"BLINDSPOT"`` for every export and the page regenerated from it, all 156 rows declared a
    type true of nothing and the harness still reported ``ALL HARNESS GATES PASSED. 16 of 16``.

    So the oracle is `api_member_kind`, stated here and asked of the live object. It is
    deliberately **not** imported from `scripts.generate_api_md`: importing the generator's own
    classifier would rebuild the fixed point inside the gate that exists to break it.

    **What this gate cannot see:** the *kind*, not the rendered signature or description. A row
    correctly typed `function` whose description cell states the wrong arguments passes here;
    `tests/test_docs_call_shapes.py` is what covers that, and P-84 records where it does not.
    """
    root = repo_root or REPO_ROOT
    page = root / "docs" / "api.md"
    if not page.is_file():
        return [f"API_TYPE: {page} is missing; the sweep is broken, not the tree"]

    import jnwb

    rows = [
        (m.group(1), m.group(2).strip())
        for m in API_MD_ROW.finditer(page.read_text(encoding="utf-8"))
    ]
    violations: List[str] = []

    # The vacuity guard comes first and is not optional. Every check below iterates `rows`, so a
    # regex that matches nothing satisfies all of them while asserting nothing -- and a Type
    # column nobody parses is exactly the hole this gate was added to close.
    names = [name for name, _ in rows]
    exported = sorted(jnwb.__all__)
    if sorted(names) != exported:
        violations.append(
            f"API_TYPE: parsed {len(names)} rows against {len(exported)} exports; "
            f"missing={sorted(set(exported) - set(names))}, "
            f"extra={sorted(set(names) - set(exported))}, "
            f"duplicated={sorted({n for n in names if names.count(n) > 1})}. "
            "Until the parse covers every export, the type comparison below is not a check."
        )
        return violations

    from jnwb._lazy_exports import OPTIONAL_SUBMODULES

    for name, declared in rows:
        try:
            obj = getattr(jnwb, name)
        except ImportError:
            # An optional submodule whose extra is not installed here. Its import spec is
            # what can be asked without the extra: an importable spec is a module.
            if name not in OPTIONAL_SUBMODULES:
                raise
            import importlib.util

            spec = importlib.util.find_spec(f"jnwb.{name}")
            if spec is None:
                violations.append(f"API_TYPE: jnwb.{name} has no importable source")
                continue
            # Built from the spec and never executed, so nothing it imports is needed.
            obj = importlib.util.module_from_spec(spec)
        expected = api_member_kind(obj)
        if not declared:
            violations.append(f"API_TYPE: jnwb.{name} has an empty Type cell")
        elif declared != expected:
            violations.append(
                f"API_TYPE: jnwb.{name}: docs/api.md says '{declared}', the runtime object is "
                f"'{expected}' (type {type(obj).__name__}). Gate 9 cannot see this: it compares "
                "the page to the generator, and a wrong answer inside the generator is on both "
                "sides of that comparison."
            )
    return violations


def _one(check: Any, header: str) -> Any:
    """Adapt a check returning violations into the (header, violations) shape the runner wants."""

    def run() -> List[Tuple[str, List[str]]]:
        violations = check()
        return [(header, violations)] if violations else []

    return run


def _api_reference_checks() -> List[Tuple[str, List[str]]]:
    """Adapter, not a gate: the API reference is two checks under one PASS line.

    Deliberately does not open with ``Gate N``. That prefix is how
    ``tests/test_harness_adversarial_gates.py`` discovers which function *is* a numbered gate, and
    a helper claiming the number would read as the gate being declared twice.
    """
    from scripts.generate_api_md import check_api_md_is_generated

    found: List[Tuple[str, List[str]]] = []
    set_violations = check_documented_api_matches_all()
    if set_violations:
        found.append(("FAIL: Documented API does not match jnwb.__all__:", set_violations))
    generator_violations = check_api_md_is_generated()
    if generator_violations:
        found.append(
            ("FAIL: docs/api.md is out of sync with the API generator:", generator_violations)
        )
    return found


def _internal_vocabulary_checks() -> List[Tuple[str, List[str]]]:
    """Adapter, not a gate: public documentation and the library source under one PASS line."""
    found: List[Tuple[str, List[str]]] = []
    docs_violations = check_internal_process_vocabulary()
    if docs_violations:
        found.append(
            ("FAIL: Internal process vocabulary found in public documentation:", docs_violations)
        )
    library_violations = check_no_process_identifiers_in_library()
    if library_violations:
        found.append(("FAIL: Item or problem identifiers found in jnwb/:", library_violations))
    return found


def _python_pass_line() -> str:
    return (
        f"PASS: Python >={PYTHON_FLOOR} floor, classifiers {list(PYTHON_SUPPORTED)}, "
        f"CI covering {list(PYTHON_CI_REQUIRED)} all agree."
    )


#: Every gate, in the runner's order, as (number, run, pass_line). `pass_line` is a callable
#: because two gates compute their message from constants. The numbers are the ones this module's
#: docstring lists, and `tests/test_module_docstrings_match_their_code.py` holds the two together.
GATES: List[Tuple[int, Any, Any]] = [
    (1, _one(check_frozen_boundary, "FAIL: jnwb/ frozen boundary check failed:"),
     lambda: "PASS: jnwb/ frozen boundary clean (zero unauthorized project imports)."),
    (2, _one(check_skill_tree_uniqueness, "FAIL: Skill tree uniqueness violated:"),
     lambda: "PASS: Single canonical skill tree verified (no .agents/skills/ duplicate)."),
    (3, _one(check_no_hardcoded_test_paths,
             "FAIL: Hardcoded machine-local paths detected in tests:"),
     lambda: "PASS: Tests free of machine-local hardcoded drive paths."),
    (4, _one(check_root_allowlist, "FAIL: Repository root allowlist violated:"),
     lambda: "PASS: Repository root strictly frozen & clean."),
    (5, _one(check_public_symbols_documented, "FAIL: Undocumented public symbols detected:"),
     lambda: "PASS: 100% of public symbols documented in docs/."),
    (6, _one(check_dataset_leakage, "FAIL: Dataset leakage detected in generic modules:"),
     lambda: "PASS: No forbidden study tokens on Gate 6 scan surface "
             "(jnwb/, skills/, docs/**, examples/**, root user-facing docs)."),
    (7, _one(check_version_consistency, "FAIL: Version inconsistency detected:"),
     lambda: "PASS: Package and pyproject.toml versions synchronized."),
    (8, _one(check_python_floor_consistency,
             "FAIL: Python support policy inconsistency detected:"), _python_pass_line),
    (9, _api_reference_checks,
     lambda: "PASS: docs/api.md matches jnwb.__all__ and the runtime API generator."),
    (10, _one(check_docs_version_matches_package,
              "FAIL: Documentation version does not match the package version:"),
     lambda: "PASS: Documentation versions derive from jnwb.__version__."),
    (11, _one(check_no_shadow_packages,
              "FAIL: Import-shadowing package detected at repository root:"),
     lambda: "PASS: No unowned importable package at the repository root."),
    (12, _one(check_no_project_identifiers_in_code,
              "FAIL: Project identifiers found in jnwb/ code:"),
     lambda: "PASS: No project identifiers in jnwb/ code strings or names."),
    (13, _one(check_nwb_onboarding_alignment, "FAIL: NWB onboarding surface misaligned:"),
     lambda: "PASS: NWB onboarding workflow aligned across README, tutorials, skill, and MkDocs."),
    (14, _internal_vocabulary_checks,
     lambda: f"PASS: No internal process vocabulary in docs/ ({len(INTERNAL_PROCESS_TERMS)} "
             "gated terms; 'agent', 'skill' and 'routing' are public capabilities and are not "
             "among them), and no item or problem identifier in jnwb/."),
    (15, _one(check_stack_form_consistency,
              "FAIL: Coordination stack form is not machine-readable:"),
     lambda: "PASS: Stack form consistent (every declared write set names comparable paths and "
             "is not truncated by a stray full stop; no 'Blocked by: none' is contradicted by "
             "its own item's text; every summary count agrees with the items it names; "
             "no summary states an item total the stack does not hold; "
             "every problem row carries its own table's column count; "
             "every GENERATED_FROM entry resolves against the tree)."),
    (16, _one(check_line_ending_consistency,
              "FAIL: Tracked files carry both line-ending conventions:"),
     lambda: "PASS: Line endings consistent (no tracked text file mixes CRLF and bare LF)."),
    (17, _one(check_stack_pointers_resolve,
              "FAIL: A stack field names something that does not exist:"),
     lambda: "PASS: Stack pointers resolve (every 'Skill:' names a skills/*/SKILL.md or a "
             "declared placeholder, every 'Role:' an artifacts/agents/*.md or a human, and "
             "every 'Blocked by:' item id is live)."),
    (18, _one(check_api_md_member_types,
              "FAIL: A docs/api.md Type cell is not true of the runtime object:"),
     lambda: "PASS: docs/api.md Type column agrees with the runtime object, on an oracle that "
             "does not import the generator."),
]


def run_full_preflight() -> bool:
    """Run every gate and report each one's state independently.

    This returned at the first failure until 2026-09-19, and the cost of that was measured rather
    than argued: agent worktrees inside the repository tripped gate 2, the runner stopped, and
    gates 3 through 13 did not run -- including gate 4, which held a second, genuine instance of
    the same defect and only became visible once gate 2 was fixed. One PASS line was printed where
    thirteen were expected, and three separate packets reported the resulting red suite as
    unrelated to their work without anyone establishing that the remaining gates had executed at
    all. A first failure makes every later gate *unknown*, and the workflow was treating them as
    observed.

    So every gate now runs, whatever the ones before it did, and the contract is:

        harness PASS  <=>  every gate executed and every gate passed

    A gate that raises is reported ERROR and does not stop the rest. A gate that genuinely cannot
    be reached is reported NOT RUN by name, because a gate that vanishes from the output looks
    exactly like a gate with nothing to say.
    """
    # A violation quoting a character the console cannot encode (a Windows cp1252 console and
    # a stack line containing `Θ`) raised inside `print`, so the gate's findings collapsed into
    # one ERROR line and the gate was listed as failed twice. The evidence is the output.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")
    print("=== Running Harness Pre-Flight Verification Gates ===")

    executed: List[int] = []
    failed: List[int] = []

    # The report is a function and the loop is wrapped, because `not_run` used to be unreachable:
    # both the success and the `except` path appended to `executed`, so the only way to skip a
    # gate was an escaping BaseException -- which also skipped the reporting that would have said
    # so. A NOT RUN line nothing can produce is not a safeguard, it is a comment. 06-64 deleted
    # the whole block and the suite stayed green.
    try:
        for number, run, pass_line in GATES:
            try:
                found = run()
                if found:
                    failed.append(number)
                    for header, violations in found:
                        print(header)
                        for violation in violations:
                            print(f"  - {violation}")
                else:
                    # Inside the try: a pass_line() that raises used to abort the runner with no
                    # verdict at all, which is the same failure this gate table exists to prevent.
                    print(pass_line())
            except Exception as exc:  # a gate that breaks must not hide the gates after it
                if number not in failed:
                    failed.append(number)
                print(f"ERROR: gate {number} raised {type(exc).__name__}: {exc}")
            # Appended last, so a gate abandoned part-way is genuinely not executed.
            executed.append(number)
    except BaseException:
        # SystemExit, KeyboardInterrupt, or anything else that is not an ordinary error. Say which
        # gates never ran before letting it go; an interrupted run must not read as a clean one.
        _print_preflight_verdict(executed, failed)
        raise

    return _print_preflight_verdict(executed, failed)


def _print_preflight_verdict(executed: List[int], failed: List[int]) -> bool:
    """Name every gate's state, then the verdict. Unknown is never reported as passing."""
    not_run = [number for number, _, _ in GATES if number not in executed]
    for number in not_run:
        print(f"NOT RUN: gate {number} did not execute; its state is unknown, not passing.")

    if failed or not_run:
        print(
            f"OVERALL: FAIL. {len(executed)} of {len(GATES)} gates executed; "
            f"failed: {failed or 'none'}; not run: {not_run or 'none'}."
        )
        return False

    print(f"ALL HARNESS GATES PASSED. {len(executed)} of {len(GATES)} gates executed.")
    return True


if __name__ == "__main__":
    success = run_full_preflight()
    sys.exit(0 if success else 1)
