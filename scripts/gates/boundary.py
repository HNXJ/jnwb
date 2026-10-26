"""Repository-boundary gates: frozen imports, skill tree, test paths, root freeze, shadowing, log and modality rules, line endings."""
from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
JNWB_DIR = REPO_ROOT / "jnwb"


AUTHORIZED_JNWB_EXCEPTIONS: set = set()


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
    * the registry entry the nested ``.git`` file names points back at that file. Both checks
      above follow pointers git itself follows, so a registry directory written by hand --
      its ``gitdir`` file naming the counterfeit directory -- passes them: the listing names
      it and git opens it. git's own convention closes it: a genuine linked worktree pairs a
      ``.git`` *file* with a registry ``gitdir`` file reading ``<worktree>/.git``, never the
      bare directory. Both sides are read off disk rather than asked of git.

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
    if found is None or found[0] != _canonical(directory) or found[1] != root_identity[1]:
        return False
    return _admin_gitdir_points_back(directory)


def _admin_gitdir_points_back(directory: Path) -> bool:
    """The registry entry the nested ``.git`` file names points back at that file.

    Anything unreadable fails closed: an excuse that cannot be verified is not granted.
    """
    dot_git = directory / ".git"
    if not dot_git.is_file():
        return False
    try:
        first = dot_git.read_text(encoding="utf-8", errors="strict").splitlines()
        admin = Path(first[0][len("gitdir:"):].strip()) if first else None
        if admin is None or not first[0].startswith("gitdir:") or not str(admin):
            return False
        if not admin.is_absolute():
            admin = directory / admin
        back = (admin / "gitdir").read_text(encoding="utf-8", errors="strict").strip()
    except (OSError, ValueError):
        return False
    return bool(back) and _canonical(back) == _canonical(dot_git) and dot_git.is_file()


def _skill_frontmatter_name(skill: Path) -> Optional[str]:
    """The lower-cased `name:` from a SKILL.md frontmatter, or None when it declares none."""
    found = re.match(r"---\r?\n(?:(?!---).*\r?\n)*?name:\s*(\S+)", skill.read_text(encoding="utf-8"))
    return found.group(1).strip("'\"").lower() if found else None


def check_skill_tree_uniqueness(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 2 (Skill Tree Uniqueness): every SKILL.md in the tree lives under skills/.

    This checked one hardcoded path, ``.agents/skills``, so a duplicate tree anywhere else
    passed: `jnwb/skills/` and `docs/skills/` were both accepted when constructed. The
    canonical tree is `skills/`, and a second one is the hazard whatever it is called.

    One other location is allowed: ``artifacts/skills/``, which holds skills about working on
    this repository rather than about using jnwb. ``artifacts/`` is pruned from the sdist, so
    they never ship. The hazard is two copies of one skill drifting apart, so a skill there
    whose name also exists under ``skills/`` is still a violation.
    """
    root = repo_root or REPO_ROOT
    violations = []
    identities: Dict[Any, Any] = {}
    git_unavailable: Optional[str] = None
    # A copy is the same skill under any spelling: its folder name, compared without case, or
    # the `name:` its frontmatter declares.
    shipped = sorted((root / "skills").glob("*/SKILL.md"))
    shipped_names = {p.parent.name.lower() for p in shipped}
    shipped_names |= {n for n in map(_skill_frontmatter_name, shipped) if n}
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
        if relative.parts[:2] == ("artifacts", "skills") and len(relative.parts) == 4:
            if {relative.parts[2].lower(), _skill_frontmatter_name(skill)} & shipped_names:
                violations.append(
                    f"DUPLICATE_SKILL_TREE: {relative.as_posix()} repeats the shipped skill "
                    f"skills/{relative.parts[2]}/. One skill has one home."
                )
            continue
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
        return [f"NO_SCAN_TREE: {root.as_posix()} holds neither tests/ nor scripts/, so no test "
                "or script path was examined"]
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
# when this gate started seeing namespace packages: `examples/quickstart_jnwb.py` and, before it
# moved to `scripts/figures/`, `docs/generate_figures.py` make both importable without an
# __init__.py, which is the same
# exposure and the same residual hazard documented in docs/install.md. Nothing else may join.
INTERNAL_ROOT_PACKAGES = {"scripts", "tests", "docs", "examples"}

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
    ".gitignore", ".readthedocs.yaml", "AGENTS.md", "CHANGELOG.md", "CITATION.cff", "CLAUDE.md",
    "LICENSE", "MANIFEST.in", "pyproject.toml", "README.md",
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
        except Exception as exc:
            return [f"UNPARSEABLE: code that declares a raw_power estimand does not parse ({exc}), "
                    "so its rule was not checked"]
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


def check_logarithm_last_in_package(repo_root: Optional[Path] = None) -> List[str]:
    """No declared raw-power estimand takes its log before its mean, in any module of ``jnwb/``.

    Applies ``check_logarithm_last_rule`` to each module and names the module of each finding. A
    package with no module is a failure: no estimand was examined.
    """
    root = repo_root or REPO_ROOT
    modules = sorted((root / "jnwb").rglob("*.py")) if (root / "jnwb").is_dir() else []
    if not modules:
        return [f"NO_SOURCE: {(root / 'jnwb').as_posix()} holds no Python module, so no estimand "
                "was examined"]
    violations = []
    for module in modules:
        text = module.read_text(encoding="utf-8")
        for reason in check_logarithm_last_rule(text):
            violations.append(f"{module.relative_to(root).as_posix()}: {reason}")
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
