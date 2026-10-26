"""Deterministic Release Gate for jnwb.

Pipeline, in the order the steps run. The labels are names, not positions: the suite keeps
the label 1 and runs last, because it is the one step that takes tens of minutes, and every
cheaper check that can refuse the release runs before it.
  0a. Release readiness: artifacts/state.md is absent or records HEAD, the working tree is
      clean, the open stack holds no row, no todo item is still required this cycle, every
      roadmap row is readable and deferred past this cycle, and the
      blocker-focused closure receipt reports zero for this commit
  0. Required release/test tooling is present in the active environment
  0b. The declared version is not one the package index already serves
  0c. Every declared dependency floor installs on the declared interpreter
  0d. The release body's version, Python support and install command match package metadata
  0e. CI concluded success, per required leg, for the exact commit being qualified, on main
  2. Harness pre-flight gates
  2a. Recorded mutation gaps still hold at HEAD
  2b. API docs generator drift check, on this interpreter and on the Python floor
  3. Clean distribution build (sdist + wheel)
  4. Manifest & forbidden-content inspection (no _unused, no omission, no artifacts)
  5. Distribution metadata & README validation (twine check)
  6. Isolated environment wheel installation & pip check
  7. Installed-package smoke verification without omission (``scripts/smoke_installed.py``)
  8. Every numbered tutorial runs against the installed wheel
  1. Full test suite execution (pytest tests/), in parallel, with its wall time, and the
     peak memory of a fixed set of representative operations, recorded

Exits 0 on complete verified success; non-zero otherwise.
"""

import json
import os
import sys
import shutil
import tempfile
import pathlib
import urllib.error
import urllib.request
import zipfile
import tarfile
import time
import subprocess
import logging
import re
from typing import Iterable, List, NamedTuple, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("release_gate")

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # never insert(0): pyproject sets pythonpath = ["."]
# The one stack reader, shared with gates 15 and 17 (scripts/stack_parse.py). The names keep the
# spelling this module used, so its call sites read the shared parser unchanged.
from scripts.stack_parse import (  # noqa: E402
    ITEM_HEADING as _ITEM_HEADING,
    ITEM_SHAPED as _ITEM_SHAPED,
    parse_todo_stack as _parse_todo_stack,
    sections as _todo_sections,
)


#: Extras whose tooling must be present for release qualification to mean anything: every extra
#: the suite uses. A test whose extra is absent skips, naming the extra, so without this check
#: the suite would not fail, it would report a *different* result, which is worse. ``vis`` is
#: here because the suite imports ``jnwb.vis``, and every CI leg installs it; ``wavemap`` because
#: tests/test_wavemap.py clusters with umap-learn and networkx.
REQUIRED_EXTRAS = ("test", "docs", "vis", "wavemap")
# The extras STEP 8 installs before running the tutorials, as CI's tutorial step has them.
TUTORIAL_EXTRAS = ("vis", "wavemap")


_VERSION_RE = re.compile(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def jnwb_source_version(root: Optional[pathlib.Path] = None) -> str:
    """The version the source tree declares, parsed textually.

    Read rather than imported: the gate compares the *source* declaration against what the
    built wheel reports, so importing the package under test would make the comparison
    tautological. Pinning the expected version as a literal here is the same drift failure
    class the documentation gates exist to prevent.

    ``root`` is parameterised so the release-body checks below can be driven over a
    constructed tree. A check that can only run against the live repository is one whose
    failure branch is never exercised.
    """
    init = (root or REPO_ROOT) / "jnwb" / "__init__.py"
    match = _VERSION_RE.search(init.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError(f"could not parse __version__ from {init}")
    return match.group(1)


#: Where the published version list is read from. A release gate that never asks the index
#: cannot tell a rebuild from a release: it compares the declared version to the changelog
#: entry the same tree wrote, which agrees with itself by construction.
PYPI_JSON_URL = "https://pypi.org/pypi/{name}/json"

#: Set to "1" to build without consulting the index. Named, logged and deliberate -- an
#: offline release is a decision, not a default.
SKIP_INDEX_ENV = "JNWB_SKIP_INDEX_CHECK"

#: Checks this run skipped, each named once, for the closing banner. A skip is never a pass.
SKIPPED_CHECKS: list[str] = []
INDEX_SKIPPED = "package index unreachable: version collision and dependency floors unverified"


def _record_skip(name: str) -> None:
    if name not in SKIPPED_CHECKS:
        SKIPPED_CHECKS.append(name)


def verified_banner(skipped) -> str:
    """The closing line. Names every skipped check, so a run with a skip is not VERIFIED."""
    if not skipped:
        return "=== RELEASE GATE VERIFIED: DISTRIBUTABLE PACKAGE READY ==="
    return (f"=== RELEASE GATE NOT FULLY VERIFIED: {len(skipped)} CHECK(S) SKIPPED, NOT A PASS: "
            + "; ".join(skipped) + " ===")


def published_versions(name: str = "jnwb", timeout: float = 30.0) -> Optional[Set[str]]:
    """Versions the index already serves, or ``None`` when it could not be reached.

    ``None`` is not "nothing is published". The caller must treat an unreachable index as
    unverified rather than clear, or the gate passes hardest exactly when the network is
    down.
    """
    url = PYPI_JSON_URL.format(name=name)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return set()  # never published; a first release is not a collision
        return None
    except Exception:  # noqa: BLE001 - any transport failure is "unverified"
        return None
    return set(payload.get("releases", {}))


def unreleased_entry_lines(changelog: Optional[str] = None) -> List[str]:
    """Non-empty lines under ``## [Unreleased]``, up to the next ``## `` heading."""
    text = changelog if changelog is not None else (
        REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    body = text.partition("## [Unreleased]")[2]
    end = body.find("\n## ")
    if end != -1:
        body = body[:end]
    return [line for line in body.splitlines() if line.strip()]


def check_version_is_not_already_published(
    version: str,
    published: Optional[Set[str]],
    unreleased: Optional[List[str]] = None,
) -> List[str]:
    """Two distributions can never share a version string.

    Split from the network call so the suite can exercise every branch without reaching the
    index, and so an offline run has one named way through rather than a silent one.
    """
    if published is None:
        if os.environ.get(SKIP_INDEX_ENV) == "1":
            _record_skip(INDEX_SKIPPED)
            return []
        return [
            f"the package index could not be reached, so it is unknown whether {version} "
            f"is already published. Set {SKIP_INDEX_ENV}=1 to build anyway."
        ]
    if version not in published:
        return []
    pending = unreleased if unreleased is not None else unreleased_entry_lines()
    detail = (
        f" and CHANGELOG.md has {len(pending)} non-empty lines under [Unreleased], so the "
        f"two would not even carry the same contents"
        if pending else ""
    )
    return [
        f"version {version} is already on the index{detail}. Bump "
        f"jnwb/__init__.py and move [Unreleased] under a new heading before building a "
        f"release."
    ]


#: Directory names that must not appear as a path component anywhere in a distribution.
#: Matched on components rather than as substrings: the previous rule searched for
#: ``/tests/``, which no wheel entry contains -- wheel entries have no leading distribution
#: directory, so ``"/tests/" in "tests/__init__.py"`` is False and a wheel carrying the whole
#: suite passed. Component matching also stops the reverse error, where ``artifacts`` would
#: reject a module legitimately named ``foo_artifacts.py``.
FORBIDDEN_COMPONENTS = frozenset({
    # Every `prune` target in MANIFEST.in. The two lists said different things: the gate
    # never rejected `site` or `_build`, which the sdist prunes.
    "tests", "scripts", "artifacts", "omission", "site", "_build",
    # Build, cache and checkout noise. `.lab_bundle_build` is the directory that actually
    # exists; the old rule caught it only because `.lab` was a substring match.
    "dist", ".git", ".github", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__",
    ".lab", ".lab_bundle_build", "outputs",
    # The repository's example scripts and data, which neither a wheel nor an sdist may carry. No
    # package directory is named `examples` or `data`; one added later would be refused here.
    "examples", "data",
    # The repository's working rules and the skills about working on this repository. All
    # stay out of the sdist; a component match on the file and folder names catches each
    # one wherever a manifest change puts it.
    "AGENTS.md", "jnwb-fact-action", "jnwb-review",
})

#: Pollution markers forbidden anywhere in an entry name, including inside a file name.
#: These are not directories, so a component check would be the weaker rule here.
FORBIDDEN_SUBSTRINGS = ("omission", "_unused")


def forbidden_entries(names: Iterable[str]) -> List[str]:
    """Every archive entry that must not ship, each with the rule that rejected it.

    Entries are split on both separators. A zip written by a tool that did not normalise
    paths can carry backslashes, and splitting on ``/`` alone would read
    ``tests\\test_x.py`` as a single component and miss it.
    """
    problems = []
    for name in names:
        parts = [part for part in re.split(r"[\\/]+", name) if part and part != "."]
        hit = next((part for part in parts if part in FORBIDDEN_COMPONENTS), None)
        if hit is not None:
            problems.append(f"{name}: forbidden path component {hit!r}")
            continue
        token = next((t for t in FORBIDDEN_SUBSTRINGS if t in name), None)
        if token is not None:
            problems.append(f"{name}: forbidden token {token!r}")
    return problems


#: A dependency floor written as ``name>=version``. Anything else -- an unpinned requirement,
#: an extra reference like ``jnwb[all]`` -- states no floor and is nothing to check.
_FLOOR_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*>=\s*([0-9][^\s,;\[]*)")


def declared_dependency_floors() -> List[Tuple[str, str, str]]:
    """``(extra, name, floor)`` for every ``>=`` pin in pyproject.toml.

    ``extra`` is ``""`` for a core dependency, so a failure says where the pin lives.
    """
    import tomllib

    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        project = tomllib.load(fh)["project"]

    groups = [("", project.get("dependencies", []))]
    for extra, items in (project.get("optional-dependencies") or {}).items():
        groups.append((extra, items))

    floors = []
    for extra, items in groups:
        for item in items:
            match = _FLOOR_RE.match(item.strip())
            if match:
                floors.append((extra, match.group(1), match.group(2)))
    return floors


def interpreter_floor_tag(requires_python: Optional[str] = None) -> str:
    """The cp tag of the oldest interpreter this package claims to support.

    Derived from ``requires-python`` rather than written down: a floor check that hardcodes
    ``cp312`` keeps passing after the support window moves, which is the drift that produced
    the defect it exists to catch.
    """
    import tomllib

    if requires_python is None:
        with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
            requires_python = tomllib.load(fh)["project"]["requires-python"]
    match = re.search(r">=\s*(\d+)\.(\d+)", requires_python or "")
    if not match:
        raise RuntimeError(f"no minimum interpreter in requires-python {requires_python!r}")
    return f"cp{match.group(1)}{match.group(2)}"


def package_releases(name: str, timeout: float = 30.0) -> Optional[dict]:
    """Every release of a package, or ``None`` when the index is unreachable."""
    url = PYPI_JSON_URL.format(name=name)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"releases": {}}  # no such package at all
        return None
    except Exception:  # noqa: BLE001
        return None


def lowest_release_satisfying(payload: dict, floor: str) -> Optional[str]:
    """The oldest final release at or above ``floor`` -- what a minimal resolution installs.

    A ``>=`` pin is a lower bound, not a version that has to exist: ``pytest-xdist>=3.0`` is
    satisfied by ``3.0.2`` and there is no ``3.0`` on the index. Checking the literal floor
    string reported that as missing, which is a fact about PyPI's URL scheme rather than about
    whether the requirement can be installed.
    """
    from packaging.version import InvalidVersion, Version

    try:
        wanted = Version(floor)
    except InvalidVersion:
        return None
    candidates = []
    for version in payload.get("releases", {}):
        try:
            parsed = Version(version)
        except InvalidVersion:
            continue
        if parsed.is_prerelease or parsed.is_devrelease:
            continue
        if parsed >= wanted:
            candidates.append((parsed, version))
    if not candidates:
        return None
    return min(candidates)[1]


def check_floor_is_installable(
    name: str,
    floor: str,
    payload: Optional[dict],
    tag: str,
    extra: str = "",
) -> List[str]:
    """A declared floor must be installable on the interpreter the package declares.

    Seven core floors and two extras were copied from an older support window and never
    re-derived: ``scipy>=1.8.0`` declares ``requires_python '>=3.8,<3.11'``, which contradicts
    ``requires-python = ">=3.12"`` outright, and six more ship no wheel any 3.12 can use.
    Nothing noticed, because the resolutions in use are years above the floors.

    What is checked is the oldest release the pin allows, because that is what a resolver
    asked for a minimal install would choose.
    """
    where = f"{name}>={floor}" + (f" [{extra}]" if extra else "")
    if payload is None:
        if os.environ.get(SKIP_INDEX_ENV) == "1":
            _record_skip(INDEX_SKIPPED)
            return []
        return [f"{where}: the index could not be reached, so the floor is unverified"]

    resolved = lowest_release_satisfying(payload, floor)
    if resolved is None:
        return [f"{where}: the index serves no release satisfying that floor"]

    files = payload.get("releases", {}).get(resolved) or []
    # Per-file, because that is where the index records it on this endpoint.
    declared = ""
    for entry in files:
        declared = str(entry.get("requires_python") or "") or declared
    urls = files
    if resolved != floor:
        where = f"{where} (oldest allowed: {resolved})"
    if _python_excluded(declared, tag):
        return [
            f"{where}: that release declares requires_python {declared!r}, which excludes the "
            f"{tag} this package requires"
        ]

    tags: Set[str] = set()
    for entry in urls:
        filename = entry.get("filename", "")
        if filename.endswith(".whl"):
            tags.update(filename.rsplit("-", 3)[1].split("."))
    if tags & {tag, "py3", "py2"}:
        return []
    return [
        f"{where}: no {tag} or pure-python wheel; that release ships {sorted(tags) or 'no wheel'}"
    ]


def _python_excluded(requires_python: str, tag: str) -> bool:
    """Whether ``requires_python`` rules out the interpreter named by ``tag``.

    Only the upper bound is read. A lower bound below the floor is the normal case, and an
    exact parse of every specifier form is a packaging library's job, not a gate's.
    """
    if not requires_python:
        return False
    major, minor = int(tag[2]), int(tag[3:])
    for clause in requires_python.split(","):
        clause = clause.strip()
        match = re.match(r"^<\s*(\d+)\.(\d+)", clause)
        if match and (major, minor) >= (int(match.group(1)), int(match.group(2))):
            return True
        match = re.match(r"^<=\s*(\d+)\.(\d+)", clause)
        if match and (major, minor) > (int(match.group(1)), int(match.group(2))):
            return True
    return False


class ReleaseMetadata(NamedTuple):
    """What the package itself says, as the release body's claims will be judged against it."""

    name: str
    version: str
    python_floor: str
    python_ceiling: str
    python_supported: Tuple[str, ...]


def _version_tuple(value: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def release_metadata(root: Optional[pathlib.Path] = None) -> ReleaseMetadata:
    """Derive the release's mechanically knowable facts from package metadata.

    Every field is read, never written down here. A second copy of the supported-Python
    window in this file would be the defect the body check exists to catch, one surface
    further in: P-126 records four places in this repository asserting a stale gate count
    right now, each of them a replica that drifted because nothing derived it.

    The floor comes from ``requires-python`` and the ceiling from the highest versioned
    classifier. Harness gate 8 independently enforces that those two agree with each other,
    with ``.readthedocs.yaml`` and with the CI matrix, so reading them here adds a consumer
    of that invariant rather than a competing statement of it.
    """
    root = root or REPO_ROOT
    import tomllib

    with open(root / "pyproject.toml", "rb") as handle:
        project = tomllib.load(handle)["project"]

    requires = project.get("requires-python") or ""
    floor = re.search(r">=\s*(\d+\.\d+)", requires)
    if floor is None:
        raise RuntimeError(f"no minimum interpreter in requires-python {requires!r}")

    supported = sorted(
        {
            m.group(1)
            for m in re.finditer(
                r"Programming Language :: Python :: (\d+\.\d+)",
                "\n".join(project.get("classifiers", [])),
            )
        },
        key=_version_tuple,
    )
    if not supported:
        raise RuntimeError(f"{root / 'pyproject.toml'} declares no versioned Python classifier")

    return ReleaseMetadata(
        name=project["name"],
        version=jnwb_source_version(root),
        python_floor=floor.group(1),
        python_ceiling=supported[-1],
        python_supported=tuple(supported),
    )


def _normalize_distribution(name: str) -> str:
    """PEP 503 normalisation, so ``jnwb``, ``jnwb_`` and ``JNWB`` are one name."""
    return re.sub(r"[-_.]+", "-", name).lower()


#: An install instruction. The version pin is optional so an *unpinned* command is reported
#: rather than skipped -- "no `==` was found" must not read as "the version agrees".
_INSTALL_RE = re.compile(
    r"pip\s+install\s+(?:(?:-U|--upgrade|--pre)\s+)*"
    r"(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?:\s*==\s*(?P<version>[0-9][A-Za-z0-9.!+-]*))?"
)

#: A statement about supported Python. Three shapes, distinguished because they claim
#: different things: a closed range ("3.12 through 3.14") claims a floor and a ceiling, an
#: open one ("3.12+", "3.12 or newer") claims only a floor, and a bare mention ("Python
#: 3.11") claims only that the version is relevant to this package.
_PY_SUPPORT_RE = re.compile(
    r"Python\s*(?P<ge>>=\s*)?(?P<low>\d+\.\d+)"
    r"(?:\s*(?:through|thru|to|[-‐-―])\s*(?P<high>\d+\.\d+)"
    r"|\s*(?P<plus>\+)"
    r"|(?P<ornewer>\s+or\s+(?:newer|later|above|higher)))?",
    re.IGNORECASE,
)


def _claims_a_floor(match: "re.Match[str]") -> bool:
    """Whether a matched statement asserts a support window rather than merely naming a version.

    Every open-ended form needs its own group. Leaving ``>=`` and "or newer" uncaptured made
    both parse as bare mentions: ``Python >=3.12`` then satisfied nothing, and a body whose
    only support statement used that spelling was reported as stating no range at all.
    """
    return any(match.group(name) for name in ("high", "plus", "ge", "ornewer"))


def check_release_body_claims(
    body: str,
    metadata: ReleaseMetadata,
    *,
    tag_name: Optional[str] = None,
    is_prerelease: Optional[bool] = None,
) -> List[str]:
    """Judge a release body's mechanically knowable claims against package metadata.

    Pure and offline: it takes the body as a string so the whole rule set is exercisable
    without a token, a network or a published release.

    Scope is deliberately the claims metadata can settle -- the distribution name and version
    in the install command, the supported-Python window, the tag, and whether the prerelease
    flag matches PEP 440. It does **not** judge the narrative: "120 entries", "18 survived"
    and "no API removals beyond those listed" are claims about the changelog and about an API
    diff, not about metadata, and inventing a source of truth for them here would be the
    replica this check exists to avoid.

    Absence is a violation, not a pass. A body stating no install command and no support
    range satisfies every comparison below by having nothing to compare, which is precisely
    the shape that lets a wrong body through. The v0.2.5 body shipped "Python 3.10 through
    3.14" against a ``>=3.12`` floor and no check read it.
    """
    from packaging.version import InvalidVersion, Version

    violations: List[str] = []

    installs = list(_INSTALL_RE.finditer(body))
    if not installs:
        violations.append(
            "the body states no `pip install` command, so its install instruction and the "
            f"version it pins cannot be checked. State one naming "
            f"{metadata.name}=={metadata.version}."
        )
    for match in installs:
        if _normalize_distribution(match.group("name")) != _normalize_distribution(metadata.name):
            violations.append(
                f"install command names distribution {match.group('name')!r}, but this package "
                f"is {metadata.name!r}"
            )
        pinned = match.group("version")
        if pinned is None:
            violations.append(
                f"install command `{match.group(0).strip()}` pins no version; a release body "
                f"must pin =={metadata.version} so the reader installs the release it describes"
            )
        elif pinned != metadata.version:
            violations.append(
                f"install command installs version {pinned}, but this release is "
                f"{metadata.version}"
            )

    statements = list(_PY_SUPPORT_RE.finditer(body))
    if not any(_claims_a_floor(m) for m in statements):
        violations.append(
            "the body states no Python support range, so its support claim cannot be checked. "
            f"State one, e.g. 'Python {metadata.python_floor} through {metadata.python_ceiling}'."
        )
    for match in statements:
        low, high = match.group("low"), match.group("high")
        if _claims_a_floor(match):
            if low != metadata.python_floor:
                violations.append(
                    f"{match.group(0).strip()!r} claims a {low} floor; pyproject.toml declares "
                    f">={metadata.python_floor}"
                )
            if high and high != metadata.python_ceiling:
                violations.append(
                    f"{match.group(0).strip()!r} claims a {high} ceiling; the highest classifier "
                    f"is {metadata.python_ceiling}"
                )
        elif low not in metadata.python_supported:
            violations.append(
                f"the body names Python {low}, which is not in the supported set "
                f"{list(metadata.python_supported)}"
            )

    if tag_name is not None and tag_name.lstrip("vV") != metadata.version:
        violations.append(
            f"release tag {tag_name!r} does not name the declared version {metadata.version}"
        )

    if is_prerelease is not None:
        try:
            expected = Version(metadata.version).is_prerelease
        except InvalidVersion:
            expected = None
        if expected is not None and bool(is_prerelease) != expected:
            violations.append(
                f"the release is marked prerelease={bool(is_prerelease)}, but version "
                f"{metadata.version} is "
                f"{'a prerelease' if expected else 'a final release'} under PEP 440"
            )

    return violations


#: The live check ran and its verdict is in ``violations``.
BODY_CHECKED = "checked"
#: The live check did not run. This is not a pass, and the two must never share a value:
#: ``artifacts/state.md``'s ``--check`` asserts ``"PASS" in out or "ERROR" in out``, which
#: both outcomes satisfy, and it has protected nothing for a cycle.
BODY_SKIPPED = "skipped"


class LiveBodyOutcome(NamedTuple):
    """Tri-state so a caller cannot read "could not check" as "checked and clean"."""

    status: str
    detail: str
    violations: List[str]


def check_live_release_body(
    metadata: ReleaseMetadata,
    runner=None,
    timeout: float = 30.0,
) -> LiveBodyOutcome:
    """Check the published release body for this version, or say why it was not checked.

    Every way of not reaching the release -- no ``gh``, no token, no network, no release
    published for this version yet -- returns ``BODY_SKIPPED`` with the reason. None of them
    fails the gate: before the tag exists there is no body to read, which is the normal
    pre-tag state rather than a defect. None of them passes it either.
    """
    run = runner if runner is not None else subprocess.run
    tag = f"v{metadata.version}"
    try:
        result = run(
            ["gh", "release", "view", tag, "--json", "body,tagName,isDraft,isPrerelease"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return LiveBodyOutcome(BODY_SKIPPED, "the `gh` CLI is not on PATH", [])
    except Exception as exc:  # noqa: BLE001 - any transport or tooling failure is "not checked"
        return LiveBodyOutcome(BODY_SKIPPED, f"`gh release view {tag}` failed: {exc}", [])

    if result.returncode != 0:
        reason = (result.stderr or result.stdout or "").strip().splitlines()
        return LiveBodyOutcome(
            BODY_SKIPPED,
            f"`gh release view {tag}` exited {result.returncode}: "
            f"{reason[0] if reason else 'no diagnostic'}",
            [],
        )

    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        return LiveBodyOutcome(BODY_SKIPPED, f"`gh release view {tag}` returned non-JSON: {exc}", [])

    violations = check_release_body_claims(
        payload.get("body") or "",
        metadata,
        tag_name=payload.get("tagName"),
        is_prerelease=payload.get("isPrerelease"),
    )
    detail = f"tag {payload.get('tagName')!r}, draft={payload.get('isDraft')}"
    return LiveBodyOutcome(BODY_CHECKED, detail, violations)


#: The workflow whose jobs constitute "CI passed". One file, read rather than summarised:
#: a list of required job names written down here would drift from the matrix the moment a
#: Python version is added, and drift silently, because a leg nobody asks about is a leg
#: nobody misses.
CI_WORKFLOW_PATH = ".github/workflows/workflow.yml"

#: Set to "1" to tag without resolving CI. Named, logged loudly and never the default: the
#: whole point of the check is that a red pipeline must not be taggable by omission.
SKIP_CI_ENV = "JNWB_SKIP_CI_CHECK"

#: Every required leg ran and concluded success. The only value that is a pass.
CI_VERIFIED = "verified"
#: CI was resolved and is not green. A defect in the commit.
CI_FAILED = "failed"
#: CI could not be resolved -- no ``gh``, no auth, no network, no run for this SHA, a run
#: still executing, unreadable output. Not a defect in the commit and not a pass either;
#: kept distinct from :data:`CI_FAILED` so the operator is told which problem they have.
CI_UNRESOLVED = "unresolved"


class CIOutcome(NamedTuple):
    """Tri-state, so "could not tell" can never be read as "green"."""

    status: str
    detail: str
    legs: List[Tuple[str, str, str]]   # (job name, status, conclusion)
    violations: List[str]


_MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.([A-Za-z0-9_.\-]+)\s*\}\}")

def required_ci_jobs(workflow: Optional[str] = None,
                     root: Optional[pathlib.Path] = None) -> List[str]:
    """The job names that must have run and passed, expanded over the strategy matrix.

    Derived from the workflow file, for the reason recorded at :data:`CI_WORKFLOW_PATH`.

    A job carrying an ``if:`` is excluded: the publish jobs are conditional by design and
    report ``skipped`` on an ordinary push, so requiring them would make the check fail for
    every commit and therefore be switched off. A job *without* an ``if:`` is unconditional,
    and ``skipped`` on such a job means an upstream ``needs:`` never produced it -- which is
    exactly the shape this check exists to catch. Measured at 30c425cf: ``Build & Validate
    Distribution`` is ``needs: test``, and with four test legs red it reported ``skipped``
    rather than ``failure``. A rule reading "no job concluded failure" calls that green.

    A job carrying ``continue-on-error: true`` is excluded for the opposite reason: it reports
    and does not gate. Its failure must not turn the commit's CI conclusion red, so the release
    gate does not require it.
    """
    import itertools

    import yaml

    if workflow is None:
        workflow = ((root or REPO_ROOT) / CI_WORKFLOW_PATH).read_text(encoding="utf-8")
    document = yaml.safe_load(workflow) or {}
    jobs = document.get("jobs") or {}

    names: List[str] = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        if "if" in job:
            continue
        # Reports and does not gate: see the docstring.
        if job.get("continue-on-error") is True:
            continue
        template = str(job.get("name") or job_id)
        matrix = ((job.get("strategy") or {}).get("matrix")) or {}
        axes = {
            key: value for key, value in matrix.items()
            if isinstance(value, list) and key not in ("include", "exclude")
        }
        if not axes or not _MATRIX_REF.search(template):
            names.append(template.strip())
            continue
        keys = sorted(axes)
        legs = [
            {k: str(v) for k, v in zip(keys, combination)}
            for combination in itertools.product(*(axes[key] for key in keys))
        ]
        # An `exclude` entry removes each leg that matches it on all of its keys.
        for excluded in matrix.get("exclude") or []:
            legs = [leg for leg in legs
                    if not all(leg.get(k) == str(v) for k, v in excluded.items())]
        # An `include` entry adds its keys to each leg it matches on the matrix axes, and is a leg
        # of its own only when it matches none.
        for included in matrix.get("include") or []:
            entry = {k: str(v) for k, v in included.items()}
            shared = {k: v for k, v in entry.items() if k in axes}
            matched = [leg for leg in legs if all(leg[k] == v for k, v in shared.items())]
            if matched:
                for leg in matched:
                    leg.update(entry)
            else:
                legs.append(entry)
        for values in legs:
            names.append(_MATRIX_REF.sub(
                lambda m: values.get(m.group(1), m.group(0)), template).strip())
    return names


def select_run_for_commit(sha: str, stdout: str) -> Tuple[Optional[dict], Optional[str]]:
    """``(run, None)`` or ``(None, reason)`` for the newest concluded run of ``sha`` on ``main``, or
    the newest such run when none has concluded.

    A release is qualified by the ``main`` run at the tag's commit. A run on any other branch, a
    ``dev`` push or a pull request, is not a candidate however it concluded, and the reason names
    the branches the commit's runs are on.

    The SHA comparison is the whole point. ``gh run list --commit`` is asked for the right
    run, and the answer is checked anyway: a gate that trusts the query and reports on the
    branch's latest run would pass while a *different* commit was being tagged, which is this
    repository's dominant defect shape (P-37) rather than a hypothetical one.
    """
    try:
        payload = json.loads(stdout)
    except ValueError as exc:
        return None, f"`gh run list` returned unreadable JSON: {exc}"
    if not isinstance(payload, list):
        return None, f"`gh run list` returned {type(payload).__name__}, expected a list of runs"

    matching = [
        run for run in payload
        if isinstance(run, dict) and str(run.get("headSha") or "").lower() == sha.lower()
    ]
    if not matching:
        seen = sorted({str(r.get("headSha"))[:12] for r in payload if isinstance(r, dict)})
        return None, (
            f"no workflow run has head commit {sha[:12]}; the query returned "
            f"{len(payload)} run(s) for {seen or 'no commit'}. Push this commit and let CI "
            f"run before tagging it."
        )
    # A run still executing does not decide the commit while another run of it has concluded: a
    # pull-request run in progress beside the push run that passed is not a failure. The newest
    # concluded run decides; a commit with none is held by its newest run. Newest first is gh's
    # order; databaseId is monotonic, so re-derive rather than assume.
    on_main = [run for run in matching if run.get("headBranch") == "main"]
    if not on_main:
        branches = sorted({str(r.get("headBranch") or "(no branch)") for r in matching})
        return None, (
            f"runs for {sha[:12]} exist only on {', '.join(branches)}; a release is qualified by "
            "the main run at the tag SHA, so merge the commit to main and let CI run there"
        )
    concluded = [r for r in on_main if r.get("status") == "completed"]
    return max(concluded or on_main, key=lambda r: r.get("databaseId") or 0), None


class JobVerdict(NamedTuple):
    """Per-leg findings, split by *kind* rather than by reading the message text.

    ``failures`` are statements about the commit; ``unresolved`` are statements about the
    measurement. Deciding between them by sniffing for a substring in the rendered message
    would make the verdict depend on the wording of its own error string -- a proxy for the
    thing, and the class of defect P-37 enumerates.
    """

    legs: List[Tuple[str, str, str]]
    failures: List[str]
    unresolved: List[str]


def evaluate_ci_jobs(required: Iterable[str], payload: object) -> JobVerdict:
    """Judge one run's jobs against the required job names.

    Per leg, never in aggregate. A run's own ``conclusion`` can read ``success`` while a leg
    was skipped or cancelled, so the aggregate answers a weaker question than the one asked.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        return JobVerdict([], [], ["`gh run view` returned no readable `jobs` array"])

    legs: List[Tuple[str, str, str]] = []
    by_name: dict = {}
    for job in payload["jobs"]:
        if not isinstance(job, dict):
            continue
        row = (str(job.get("name")), str(job.get("status")), str(job.get("conclusion")))
        legs.append(row)
        by_name.setdefault(row[0], row)

    failures: List[str] = []
    unresolved: List[str] = []
    for name in required:
        row = by_name.get(name)
        if row is None:
            failures.append(
                f"required leg {name!r} is absent from the run: it never started, so nothing "
                f"about it has been verified")
            continue
        _, status, conclusion = row
        if status != "completed":
            unresolved.append(
                f"required leg {name!r} is {status!r} and has not concluded yet")
        elif conclusion != "success":
            failures.append(f"required leg {name!r} concluded {conclusion!r}, not 'success'")
    return JobVerdict(legs, failures, unresolved)


def check_ci_conclusion(sha: str,
                        required: Optional[Iterable[str]] = None,
                        runner=None,
                        timeout: float = 60.0) -> CIOutcome:
    """Resolve the CI verdict for exactly the commit ``sha``.

    Fails closed. Every way of not reaching an answer -- no ``gh`` on PATH, no
    authentication, no network, no run of this SHA on main, a run still executing, unreadable
    output -- returns :data:`CI_UNRESOLVED` with a reason that says which, and the caller
    treats that as non-passing. The alternative fails hardest when the network is down,
    which is when a release is least verifiable.

    ``git fetch`` is deliberately not used: this clone's fetch aborts on missing v0.1.x tag
    objects, so a check built on it would be unresolvable here forever.
    """
    run = runner if runner is not None else subprocess.run
    if required is None:
        try:
            required = required_ci_jobs()
        except Exception as exc:  # noqa: BLE001 - an unreadable workflow is unresolved, not green
            return CIOutcome(
                CI_UNRESOLVED, f"the required job list could not be derived from "
                               f"{CI_WORKFLOW_PATH}: {exc}", [], [])
    required = list(required)
    if not required:
        return CIOutcome(
            CI_UNRESOLVED,
            f"{CI_WORKFLOW_PATH} declares no unconditional job, so 'CI passed' would be "
            f"vacuously true", [], [])

    def invoke(args: List[str]) -> Tuple[Optional[str], Optional[str]]:
        try:
            result = run(args, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            return None, "the `gh` CLI is not on PATH"
        except Exception as exc:  # noqa: BLE001
            return None, f"`{' '.join(args[:3])}` failed: {exc}"
        if result.returncode != 0:
            first = (result.stderr or result.stdout or "").strip().splitlines()
            return None, (f"`{' '.join(args[:3])}` exited {result.returncode}: "
                          f"{first[0] if first else 'no diagnostic'}")
        return result.stdout, None

    stdout, error = invoke([
        "gh", "run", "list", "--commit", sha, "--limit", "20",
        "--json", "databaseId,headBranch,headSha,status,conclusion,workflowName",
    ])
    if error is not None:
        return CIOutcome(CI_UNRESOLVED, error, [], [])

    selected, reason = select_run_for_commit(sha, stdout or "")
    if selected is None:
        return CIOutcome(CI_UNRESOLVED, reason or "no run selected", [], [])

    run_id = str(selected.get("databaseId"))
    where = (f"run {run_id} ({selected.get('workflowName')}) at "
             f"{str(selected.get('headSha'))[:12]}")
    if selected.get("status") != "completed":
        return CIOutcome(
            CI_UNRESOLVED,
            f"{where} is {selected.get('status')!r} and has not concluded yet", [], [])

    stdout, error = invoke(["gh", "run", "view", run_id, "--json", "jobs,headSha,conclusion"])
    if error is not None:
        return CIOutcome(CI_UNRESOLVED, error, [], [])
    try:
        detail_payload = json.loads(stdout or "")
    except ValueError as exc:
        return CIOutcome(
            CI_UNRESOLVED, f"`gh run view {run_id}` returned unreadable JSON: {exc}", [], [])

    # The second call is asked for its head SHA too, and it is checked: two `gh` invocations
    # are two chances to be handed a different run.
    returned_sha = str((detail_payload or {}).get("headSha") or "")
    if returned_sha and returned_sha.lower() != sha.lower():
        return CIOutcome(
            CI_UNRESOLVED,
            f"`gh run view {run_id}` reports head {returned_sha[:12]}, not {sha[:12]}", [], [])

    verdict = evaluate_ci_jobs(required, detail_payload)
    if verdict.failures:
        return CIOutcome(CI_FAILED, where, verdict.legs,
                         verdict.failures + verdict.unresolved)
    if verdict.unresolved:
        return CIOutcome(CI_UNRESOLVED, where, verdict.legs, verdict.unresolved)
    return CIOutcome(CI_VERIFIED, where, verdict.legs, [])


def format_leg_table(legs: Iterable[Tuple[str, str, str]]) -> List[str]:
    """The per-leg verdicts as aligned rows, so the report shows what was measured."""
    rows = list(legs)
    if not rows:
        return ["    (no jobs reported)"]
    width = max(len(name) for name, _, _ in rows)
    return [f"    {name.ljust(width)}  {status:<10}  {conclusion}" for name, status, conclusion in rows]


def declared_extra_requirements(extras=REQUIRED_EXTRAS) -> List[str]:
    """Distribution names pyproject.toml declares for the given extras."""
    import re
    import tomllib

    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        pyproject = tomllib.load(fh)
    optional = pyproject.get("project", {}).get("optional-dependencies", {})

    names: List[str] = []
    for extra in extras:
        for spec in optional.get(extra, []):
            if spec.lstrip().startswith("jnwb["):
                continue                      # self-referential aggregate (the `all` extra)
            name = re.split(r"[<>=!~\[;\s]", spec.strip(), maxsplit=1)[0]
            if name and name not in names:
                names.append(name)
    return names


def verify_declared_environment(extras=REQUIRED_EXTRAS) -> List[str]:
    """Return declared tooling distributions absent from the RUNNING interpreter.

    Release qualification must inspect the environment it claims to qualify. The supported-Python
    contract lives in pyproject.toml and CI (which installs ``.[test,docs]`` on every matrix
    leg) -- not in whatever happens to be installed on the machine invoking this script. An
    interpreter missing declared tooling does not fail loudly; it silently produces a different
    and better-looking result, because a test that cannot import its tool reports one failure
    rather than exercising the surface it was written for.

    This is not hypothetical: an RC audit measured "1 failed, 1021 passed" against a receipt of
    "1026 passed, 1 skipped" purely because the invoking 3.12 interpreter lacked the declared
    ``docs`` tooling. Both numbers were honest; only one described the declared environment.

    Scope, deliberately narrow: this is a PRESENCE check on the distributions named by the
    extras -- it answers "is the tooling installed here at all". It does NOT prove every
    dependency constraint is satisfied, does not read version specifiers, and does not detect a
    conflicting or broken dependency graph. ``pip check`` in STEP 6, run against the isolated
    wheel installation, remains the authoritative installed-distribution consistency check. Use
    this to stop a qualification run that would measure the wrong environment, not as evidence
    that the environment is fully correct.
    """
    from importlib.metadata import PackageNotFoundError, distribution

    missing: List[str] = []
    for name in declared_extra_requirements(extras):
        try:
            distribution(name)
        except PackageNotFoundError:
            missing.append(name)
    return missing


def run_cmd(cmd: list[str], cwd: pathlib.Path = REPO_ROOT) -> None:
    log.info(f"Executing: {' '.join(cmd)} (cwd={cwd})")
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if res.returncode != 0:
        log.error(f"Command failed with code {res.returncode}:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        sys.exit(res.returncode)
    if res.stdout.strip():
        log.info(res.stdout.strip())


def _remove_tree(path: pathlib.Path) -> None:
    """Delete a directory whose files git may have marked read-only."""
    def _writable_then_retry(func, target, _exc):
        os.chmod(target, 0o700)
        func(target)
    shutil.rmtree(path, onexc=_writable_then_retry)


def check_known_gaps_hold(root: pathlib.Path = REPO_ROOT,
                          runner=subprocess.run) -> Tuple[bool, str]:
    """Run the recorded mutation gaps against HEAD in a throwaway worktree.

    A gap that has closed is an UNEXPECTED-KILL, which the harness reports as a failed run; so
    does a gap whose anchor has moved. Either way the record says something that is no longer
    true, and the release waits until it is corrected. The mutation happens in a detached
    worktree of HEAD, never in this checkout, because a mutant here is visible to anything else
    reading the tree.
    """
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="jnwb-known-gaps-"))
    tree = scratch / "tree"
    add = runner(["git", "worktree", "add", "--detach", str(tree), "HEAD"],
                 cwd=str(root), capture_output=True, text=True)
    if add.returncode != 0:
        _remove_tree(scratch)
        return False, f"could not create a worktree of HEAD: {add.stderr.strip()}"
    # The administrative directory git keeps for the tree. On Windows it holds read-only
    # directories that `git worktree prune` cannot delete, so it is removed here by force.
    pointer = tree / ".git"
    admin = None
    if pointer.is_file():
        first = pointer.read_text(encoding="utf-8").splitlines()[0]
        if first.startswith("gitdir:"):
            admin = pathlib.Path(first.split(":", 1)[1].strip())
    try:
        res = runner([sys.executable, str(tree / "scripts" / "mutation_harness.py"),
                      "--known-gaps", "--worktree", str(tree)],
                     cwd=str(tree), capture_output=True, text=True)
        return res.returncode == 0, (res.stdout + res.stderr).strip()
    finally:
        _remove_tree(scratch)
        if admin is not None and admin.is_dir():
            _remove_tree(admin)
        runner(["git", "worktree", "prune"], cwd=str(root), capture_output=True, text=True)


def _api_md_check_commands() -> List[List[str]]:
    """Return generate_api_md --check commands for the current and floor interpreters."""
    api_script = str(REPO_ROOT / "scripts" / "generate_api_md.py")
    commands = [[sys.executable, api_script, "--check"]]
    if sys.version_info[:2] != (3, 12):
        py_launcher = shutil.which("py")
        if py_launcher is not None:
            commands.append([py_launcher, "-3.12", api_script, "--check"])
    return commands


OPEN_STACK = "artifacts/open_stack.md"
_SEPARATOR_CELL = re.compile(r"^:?-+:?$")


def _cells(line: str) -> Optional[List[str]]:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _table_cells(line: str) -> Optional[List[str]]:
    """The cells of a table line, blockquote markers removed; ``None`` for any other line."""
    body = line.lstrip(" \t>").strip()
    if not body.startswith("|"):
        return None
    return [cell.strip() for cell in body.strip("|").split("|")]


def _is_separator(cells: Optional[List[str]]) -> bool:
    return bool(cells) and all(_SEPARATOR_CELL.match(cell) for cell in cells)


def table_data_rows(text: str) -> List[Tuple[int, str]]:
    """``(line number, line)`` for every table data row in ``text``.

    A table line is one whose first non-blank character, after any blockquote marker, is a
    ``|``. A data row is a table line that is neither a separator row nor a header; a header is
    the table line directly above a separator row. Prose does not count, whatever it contains.
    """
    lines = text.splitlines()
    cells = [_table_cells(line) for line in lines]
    rows = []
    for index, line in enumerate(lines):
        if cells[index] is None or _is_separator(cells[index]):
            continue
        if index + 1 < len(lines) and _is_separator(cells[index + 1]):
            continue
        rows.append((index + 1, line.strip()))
    return rows


def open_rows(root: pathlib.Path = REPO_ROOT) -> Optional[List[str]]:
    """Every table data row in the open stack, or ``None`` when the file is missing.

    A release requires none: a row leaves the stack by being repaired, by being shown false, or
    by moving into the todo stack as an item.
    """
    path = root / OPEN_STACK
    if not path.is_file():
        return None
    return _open_rows_in(path.read_text(encoding="utf-8"))


def _open_rows_in(text: str) -> List[str]:
    """:func:`open_rows` for the text of an open stack."""
    return [line[:120] for _, line in table_data_rows(text)]


# A release value written into a line without the `Release:` label: `required-0.2.7` as a
# bullet's own marker, or the prose form `Required for 0.2.7`.
_REQUIRED_MARKER = re.compile(
    r"(?<![\w-])[*_`]*required[*_`]*(?:-|\s+for[*_`]*\s+[*_`]*)v?(\d+(?:\.\d+)+)", re.IGNORECASE)

# A line that starts a list entry or a table row; any other non-blank line continues the one above.
_ENTRY_START = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|\|)")


def _logical_lines(body: List[str]) -> List[str]:
    """``body`` with each wrapped entry or paragraph joined onto one line, so a marker split
    across a line break is read whole."""
    joined: List[str] = []
    for line in body:
        if joined and joined[-1].strip() and line.strip() and not _ENTRY_START.match(line):
            joined[-1] = f"{joined[-1].rstrip()} {line.strip()}"
        else:
            joined.append(line)
    return joined


def required_work_outside_held_items(text: str) -> List[str]:
    """Lines that mark work required for this cycle or an earlier one, in a section that does
    not hold this cycle's release open.

    A section holds it open when it is an item whose release is anything but the deferred and
    release-step values, or a subsection of such an item. Anywhere else -- a deferred item, a
    release step, a subsection of either, or a section that is not an item -- a bullet marked
    ``required-<version>`` or ``Required for <version>`` is required work the item-level field
    does not report. A later version is that cycle's work and is not counted.
    """
    items = {i: r for i, _, r in _parse_todo_stack(text)[0]}
    cycle = _version_tuple(RELEASE_CYCLE)
    found = []
    for title, _, body, enclosing in _todo_sections(text):
        item = _ITEM_HEADING.match(title) if title is not None else None
        owner = item.group(1) if item else enclosing
        if owner is not None and items.get(owner) not in (DEFERRED_VALUE, RELEASE_STEP_VALUE):
            continue
        where = (f"{owner} [{items[owner]}]" if owner is not None
                 else "before the first heading" if title is None else repr(title[:40]))
        for line in _logical_lines(body):
            if any(_version_tuple(m.group(1)) <= cycle for m in _REQUIRED_MARKER.finditer(line)):
                found.append(f"{where}: {line.strip()[:60]!r}")
    return found


RELEASE_CYCLE = jnwb_source_version()
NEXT_CYCLE = "{}.{}.{}".format(
    *(int(p) + (i == 2) for i, p in enumerate(
        re.match(r"(\d+)\.(\d+)\.(\d+)", RELEASE_CYCLE).groups())))
RECEIPT_PATH = "artifacts/process/blocker_fixpoint_receipt.md"
# The path before the move to artifacts/process/. Its commits are part of the receipt's history,
# so the history reads take both paths: a single-path read starts at the move and loses the
# commit that recorded the finished row.
RECEIPT_PRE_MOVE_PATH = "artifacts/blocker_fixpoint_receipt.md"
RECEIPT_PATHS = (RECEIPT_PATH, RECEIPT_PRE_MOVE_PATH)
TODO_PATH = "artifacts/todo_stack.md"
# The files a commit may change after the closure pass without invalidating it. A committed
# receipt cannot name its own commit, so it names the one the pass ran against, and the commit
# that records it -- together with the todo-stack update the pass produced -- follows.
RECEIPT_MAY_FOLLOW = frozenset({RECEIPT_PATH, TODO_PATH})
# The two release values that do not hold this cycle open. A release step completes only after
# the tag, so STEP 0a cannot wait for it; any other cycle's value is not this cycle's.
DEFERRED_VALUE = f"deferred-{NEXT_CYCLE}"
RELEASE_STEP_VALUE = f"release-step-{RELEASE_CYCLE}"

#: Work deferred past the cycles the todo stack holds, one table row per item.
ROADMAP_PATH = "artifacts/roadmap.md"
ROADMAP_HEADER = ("ID", "Theme", "Defect", "Waits", "Release")
_ROADMAP_ID = re.compile(r"^\d\d-\d+$")
_ROADMAP_RELEASE = re.compile(r"^deferred-(\d+\.\d+\.\d+)$")
_BULLET = re.compile(r"^[ \t]*(?:>[ \t]*)*(?:[-*+]|\d+[.)])?[ \t]*")


def roadmap_rows(text: str, stack_ids: Iterable[str] = ()) -> Tuple[List[Tuple[str, str]],
                                                                     List[str]]:
    """``(rows, refused)`` read from roadmap text; each row is ``(id, release)``.

    A row is ``| id | theme | defect | waits | deferred-X.Y.Z |``. Refused: a table row other
    than the header and its separator that does not read as one, or an id-shaped line outside
    the table; a row with an empty ``waits`` cell; a version not later than this cycle; an id
    that appears twice, or also in ``stack_ids``; and any line marking work required. Only
    readable rows are returned, refused or not, so a caller that needs the ids still sees them.
    """
    rows: List[Tuple[str, str]] = []
    refused: List[str] = []
    cycle, stack, seen = _version_tuple(RELEASE_CYCLE), set(stack_ids), set()
    for lineno, line in enumerate(text.splitlines(), 1):
        if _REQUIRED_MARKER.search(line) or re.search(r"(?<![\w-])required-", line, re.I):
            refused.append(f"line {lineno} marks work required: {line.strip()[:60]!r}")
        cells = _cells(line)
        if cells is None:
            if _ITEM_SHAPED.match(_BULLET.sub("", line, count=1)):
                refused.append(f"line {lineno} is id-shaped outside the table: "
                               f"{line.strip()[:60]!r}")
            continue
        if tuple(cells) == ROADMAP_HEADER or (cells and all(_SEPARATOR_CELL.match(c)
                                                            for c in cells)):
            continue
        release = _ROADMAP_RELEASE.match(cells[4]) if len(cells) == 5 else None
        if not (release and _ROADMAP_ID.match(cells[0]) and cells[3]):
            refused.append(f"line {lineno} is not a readable row '| id | theme | defect | "
                           f"waits | deferred-X.Y.Z |': {line.strip()[:60]!r}")
            continue
        ident = cells[0]
        rows.append((ident, cells[4]))
        if _version_tuple(release.group(1)) <= cycle:
            refused.append(f"{ident} is deferred to {release.group(1)}, not later than "
                           f"{RELEASE_CYCLE}")
        if ident in seen or ident in stack:
            refused.append(f"{ident} appears twice" if ident in seen
                           else f"{ident} is also in {TODO_PATH}")
        seen.add(ident)
    return rows, refused


def blocker_fixpoint_receipt(root: pathlib.Path = REPO_ROOT) -> Tuple[Optional[str], Optional[int]]:
    """``(commit, new_blockers)`` from the closure-pass receipt, or ``(None, None)``.

    ``commit`` is the commit the pass ran against. A committed receipt cannot name its own
    commit, so :func:`receipt_commit_violation` decides whether it still stands for HEAD.
    """
    path = root / RECEIPT_PATH
    if not path.exists():
        return None, None
    return _receipt_fields(path.read_text(encoding="utf-8"))


def _receipt_fields(text: str) -> Tuple[Optional[str], Optional[int]]:
    """:func:`blocker_fixpoint_receipt` for the text of a receipt."""
    commit = re.search(r"^\|\s*commit\s*\|\s*`([0-9a-f]{40})`\s*\|", text, re.M)
    found = re.search(r"^\|\s*new release-blocking problems found\s*\|\s*(\d+)\s*\|", text, re.M)
    return (commit.group(1) if commit else None,
            int(found.group(1)) if found else None)


#: The receipt row naming the items the closure pass verified as finished, which the commit that
#: records the receipt then deletes from the todo stack: ``| finished after the pass | 12-34, 12-35 |``.
RECEIPT_FINISHED_FIELD = "finished after the pass"


def receipt_finished_items(text: str) -> Set[str]:
    """The item ids the receipt's ``finished after the pass`` row names; empty when it has none."""
    row = re.search(r"^\|\s*" + re.escape(RECEIPT_FINISHED_FIELD) + r"\s*\|([^|\n]*)\|", text,
                    re.M)
    return set(re.findall(r"(?<![\w-])\d\d-\d+(?![\w-])", row.group(1))) if row else set()


def receipt_commit_violation(root: pathlib.Path, commit: str,
                             head: Optional[str]) -> Optional[str]:
    """Why the receipt's commit does not stand for HEAD, or ``None`` when it does.

    It stands for HEAD when it is HEAD, or when it is an ancestor of HEAD and the only files
    changed since are the receipt and the todo stack (``git diff --name-only <commit> HEAD``).
    An unresolvable HEAD, an unknown commit and a commit off HEAD's history are refused.
    """
    if head is None:
        return (f"HEAD could not be resolved, so whether the closure pass recorded in "
                f"{RECEIPT_PATH} ran against the tree being released is unknown")
    if commit == head:
        return None

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)

    if git("cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        return (f"{RECEIPT_PATH} records commit {commit[:12]}, which this repository does not "
                "know, so the closure pass cannot be tied to the tree being released")
    ancestry = git("merge-base", "--is-ancestor", commit, head)
    if ancestry.returncode == 1:
        return (f"{RECEIPT_PATH} records commit {commit[:12]}, which is not an ancestor of HEAD "
                f"{head[:12]}: the closure pass ran against a different history")
    if ancestry.returncode != 0:
        return (f"whether {RECEIPT_PATH}'s commit {commit[:12]} is an ancestor of HEAD "
                f"{head[:12]} could not be determined: {ancestry.stderr.strip()[:120]}")
    diff = git("diff", "--name-only", "-z", commit, head)
    if diff.returncode != 0:
        return (f"the files changed between {RECEIPT_PATH}'s commit {commit[:12]} and HEAD "
                f"{head[:12]} could not be listed: {diff.stderr.strip()[:120]}")
    outside = sorted(set(filter(None, diff.stdout.split("\0"))) - RECEIPT_MAY_FOLLOW)
    if outside:
        return (f"{RECEIPT_PATH} records commit {commit[:12]}, and {len(outside)} file(s) other "
                f"than the receipt and {TODO_PATH} changed between it and HEAD {head[:12]}, so "
                "the closure pass did not run against the tree being released: "
                + ", ".join(outside[:8]) + (" ..." if len(outside) > 8 else ""))
    return None


def _text_at(root: pathlib.Path, rev: str, path: str) -> Optional[str]:
    """``path``'s committed text at ``rev``, or ``None`` when git cannot show it there."""
    shown = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=root, capture_output=True)
    return shown.stdout.decode("utf-8", errors="replace") if shown.returncode == 0 else None


def _todo_stack_at(root: pathlib.Path, rev: str) -> Optional[str]:
    """The todo stack's text at ``rev``, or ``None`` when git cannot show it there."""
    return _text_at(root, rev, TODO_PATH)


#: What STEP 0a reads. It reads each from HEAD, never from the working copy: an uncommitted edit
#: that deletes required items and adds a receipt would otherwise pass condition 3 for a commit
#: whose stacks still hold them.
STEP_0A_PATHS = (OPEN_STACK, TODO_PATH, ROADMAP_PATH, RECEIPT_PATH)

#: The committed peak-memory record, and the file that declares the version it must name.
PEAK_MEMORY_PATH = "artifacts/benchmarks/performance/peak_memory.json"
#: Where releases up to v0.2.12 kept the record; read only for a previous release.
PEAK_MEMORY_PATH_BEFORE_0_2_13 = "artifacts/benchmarks/peak_memory.json"
VERSION_PATH = "jnwb/__init__.py"


def peak_memory_record_violation(root: pathlib.Path, rev: str = "HEAD") -> Optional[str]:
    """Why the peak-memory record committed at ``rev`` was not taken for the version ``rev``
    declares, or ``None``. The record is refreshed on the clean tree after the version bump is
    committed, so a record naming another version is one the closure pass did not see refreshed."""
    record, init = _text_at(root, rev, PEAK_MEMORY_PATH), _text_at(root, rev, VERSION_PATH)
    declared = _VERSION_RE.search(init) if init is not None else None
    if declared is None:
        return (f"{VERSION_PATH} declares no __version__ at {rev}, so whether {PEAK_MEMORY_PATH} "
                "is this version's is unknown")
    try:
        recorded = json.loads(record)["jnwb_version"] if record is not None else None
    except (ValueError, KeyError, TypeError):
        recorded = None
    if recorded is None:
        return (f"{PEAK_MEMORY_PATH} is missing at {rev} or names no jnwb_version; run "
                "`python scripts/measure_peak_memory.py --write` and commit it")
    if recorded != declared.group(1):
        return (f"{PEAK_MEMORY_PATH} was taken for jnwb {recorded}, and {rev} declares "
                f"{declared.group(1)}; run `python scripts/measure_peak_memory.py --write` and "
                "commit it with the version")
    return None


#: An operation's added MiB may grow by more than this fraction of the previous release's value, and
#: by at least the floor, only with a reason in the declared version's CHANGELOG.md section.
PEAK_MEMORY_GROWTH_FRACTION = 0.20
PEAK_MEMORY_GROWTH_FLOOR_MIB = 5.0
_RELEASE_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def _previous_release_tag(root: pathlib.Path, rev: str, version: str) -> Optional[str]:
    """The newest ``vX.Y.Z`` tag that is an ancestor of ``rev`` and names a version other than
    ``version``, or ``None``."""
    listed = subprocess.run(["git", "tag", "--list", "v*"], cwd=root, capture_output=True,
                            text=True)
    if listed.returncode != 0:
        return None
    candidates = sorted(
        (tag for tag in listed.stdout.split() if _RELEASE_TAG_RE.match(tag) and tag[1:] != version),
        key=lambda tag: _version_tuple(tag[1:]), reverse=True)
    for tag in candidates:
        ancestry = subprocess.run(["git", "merge-base", "--is-ancestor", tag, rev], cwd=root,
                                  capture_output=True)
        if ancestry.returncode == 0:
            return tag
    return None


def _peak_rows(text: Optional[str]) -> Optional[dict]:
    """Each operation's added MiB in a peak-memory record, or ``None`` when the record is absent or
    holds no ``operations`` mapping with an ``added_mib`` for each operation."""
    try:
        operations = json.loads(text)["operations"]
        return {str(name): float(row["added_mib"]) for name, row in operations.items()}
    except (TypeError, ValueError, KeyError, AttributeError):
        return None


def _names_operation(section: str, name: str) -> bool:
    """Whether ``section`` names ``name`` as a whole token, not as the start of a longer name."""
    return re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", section) is not None


def peak_memory_growth_violations(root: pathlib.Path, rev: str = "HEAD") -> List[str]:
    """Why an operation's peak-memory growth since the previous release is unexplained; empty when
    none is.

    The previous release is the newest ``vX.Y.Z`` tag that is an ancestor of ``rev`` and names a
    version other than the one ``rev`` declares. An operation in both records is a violation when
    its added MiB rose by more than the fraction of the previous value and by at least the floor,
    unless the declared version's CHANGELOG.md section names it. An operation added or removed is
    not compared. Fails closed: when a record, the tag or the declared version cannot be read, the
    comparison is reported as not made.
    """
    # Local import: scripts/release_body.py imports this module, so a top-level import would cycle.
    from scripts.release_body import changelog_section

    declared = _VERSION_RE.search(_text_at(root, rev, VERSION_PATH) or "")
    if declared is None:
        return [f"{VERSION_PATH} declares no __version__ at {rev}, so the peak-memory growth "
                "against the previous release could not be compared"]
    version = declared.group(1)
    previous = _previous_release_tag(root, rev, version)
    if previous is None:
        return [f"no release tag v<X.Y.Z> other than {version} is an ancestor of {rev}, so the "
                "peak-memory growth against the previous release could not be compared"]
    before = _peak_rows(_text_at(root, previous, PEAK_MEMORY_PATH)
                        or _text_at(root, previous, PEAK_MEMORY_PATH_BEFORE_0_2_13))
    if before is None:
        return [f"{PEAK_MEMORY_PATH} (or {PEAK_MEMORY_PATH_BEFORE_0_2_13}) is absent or "
                f"unreadable at {previous}, the previous release, "
                "so the peak-memory growth could not be compared"]
    after = _peak_rows(_text_at(root, rev, PEAK_MEMORY_PATH))
    if after is None:
        return [f"{PEAK_MEMORY_PATH} is absent or unreadable at {rev}, so the peak-memory growth "
                f"against {previous} could not be compared"]
    changelog = _text_at(root, rev, "CHANGELOG.md")
    section = (changelog_section(changelog, version) if changelog is not None else None) or ""
    violations: List[str] = []
    for name in sorted(set(before) & set(after)):
        growth = after[name] - before[name]
        if growth <= PEAK_MEMORY_GROWTH_FRACTION * before[name] or growth < PEAK_MEMORY_GROWTH_FLOOR_MIB:
            continue
        if _names_operation(section, name):
            continue
        share = f"+{100 * growth / before[name]:.1f}%" if before[name] > 0 else "from zero"
        violations.append(
            f"{name}: added {before[name]:.1f} MiB at {previous} and {after[name]:.1f} MiB at "
            f"{rev}, {share} (the bound is {100 * PEAK_MEMORY_GROWTH_FRACTION:.0f}% and "
            f"{PEAK_MEMORY_GROWTH_FLOOR_MIB:.0f} MiB); name the operation in CHANGELOG.md's "
            f"{version} section with the reason")
    return violations


def uncommitted_paths(root: pathlib.Path) -> Optional[List[str]]:
    """Every path whose working copy differs from HEAD -- modified, staged, deleted, renamed or
    untracked and not ignored, or marked assume-unchanged or skip-worktree -- sorted, or ``None``
    when git cannot say.

    The whole tree, not only :data:`STEP_0A_PATHS`: the build in STEP 3 packages the working
    copy, so uncommitted code would ship under a receipt that names a commit without it.
    """
    status = subprocess.run(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
        cwd=root, capture_output=True, text=True)
    if status.returncode != 0:
        return None
    named = set()
    entries = iter(filter(None, status.stdout.split("\0")))
    for entry in entries:
        # `XY path`; a rename or copy is followed by its source as an entry of its own.
        named.add(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            named.add(next(entries, ""))
    # `git status` does not report a file marked assume-unchanged or skip-worktree, however it was
    # edited. `ls-files -v` tags such a file with a lowercase letter or `S`, and every other
    # tracked file with `H`, so any other tag names the file.
    tags = subprocess.run(["git", "ls-files", "-v", "-z"], cwd=root, capture_output=True,
                          text=True)
    if tags.returncode != 0:
        return None
    for entry in filter(None, tags.stdout.split("\0")):
        if entry[:1] != "H":
            named.add(entry[2:])
    return sorted(filter(None, named))


def relabelled_after_receipt(root: pathlib.Path, commit: str, head: str,
                             finished: Iterable[str] = ()) -> List[str]:
    """Why the todo stack at HEAD does not carry the receipt's release values forward.

    The todo stack may change after the closure pass so that finished items can be deleted, but
    the pass judged what stays required. An item this cycle's release waited on at the receipt's
    commit (any value but the deferred and release-step ones) must carry the same value at HEAD,
    or be gone and named in ``finished``, the ids the receipt records as finished after the pass.
    A deletion alone cannot tell a finished item from a dropped one. Items added after the receipt
    are judged by condition 2 alone. A stack absent at either commit, or unreadable at the
    receipt's, is refused.
    """
    at_receipt, at_head = _todo_stack_at(root, commit), _todo_stack_at(root, head)
    if at_receipt is None or at_head is None:
        where = (f"the receipt's commit {commit[:12]}" if at_receipt is None
                 else f"HEAD {head[:12]}")
        return [f"{TODO_PATH} does not exist at {where}, so whether an item required for "
                f"{RELEASE_CYCLE} was relabelled after the closure pass is unknown"]
    before, unreadable = _parse_todo_stack(at_receipt)
    if unreadable:
        return [f"{len(unreadable)} section(s) of {TODO_PATH} at the receipt's commit "
                f"{commit[:12]} cannot be read, so whether one was relabelled after the closure "
                "pass is unknown: " + "; ".join(unreadable[:4])]
    held = {i: r for i, _, r in before if r not in (DEFERRED_VALUE, RELEASE_STEP_VALUE)}
    after = _parse_todo_stack(at_head)[0]
    changed = [f"{i}: {held[i][:40]} -> {r[:40]}" for i, _, r in after
               if i in held and r != held[i]]
    dropped = sorted(set(held) - {i for i, _, _ in after} - set(finished))
    violations = []
    if changed:
        violations.append(
            f"{len(changed)} todo item(s) held open for {RELEASE_CYCLE} at the receipt's commit "
            f"{commit[:12]} carry another release at HEAD {head[:12]}; only a new closure pass "
            "may relabel an item it judged, so finish and delete it or record a new receipt: "
            + "; ".join(changed[:8]) + (" ..." if len(changed) > 8 else ""))
    if dropped:
        violations.append(
            f"{len(dropped)} todo item(s) held open for {RELEASE_CYCLE} at the receipt's commit "
            f"{commit[:12]} are gone at HEAD {head[:12]}, and {RECEIPT_PATH} does not record them "
            f"under '{RECEIPT_FINISHED_FIELD}', so whether each was finished or dropped is "
            "unknown: " + ", ".join(dropped[:8]) + (" ..." if len(dropped) > 8 else ""))
    return violations + _finished_row_history(root, commit, head, set(finished), set(held))


def _finished_row_history(root: pathlib.Path, commit: str, head: str, finished: Set[str],
                          held: Set[str]) -> List[str]:
    """Why the receipt's finished row does not come from the closure pass, or ``[]``.

    Between the receipt's commit and HEAD the receipt changes in exactly one commit, and that
    commit deletes from the todo stack every id the row names; every such id was held open at the
    receipt's commit. A row written or extended later names deletions the pass never saw.
    """
    # `--full-history`, then kept only where the receipt differs from every parent. The default
    # simplification follows one side of a merge, so a receipt written on both sides counted as
    # one write; and a merge that only takes one side's receipt is not a write of its own.
    listed = subprocess.run(["git", "rev-list", "--full-history", f"{commit}..{head}", "--",
                             *RECEIPT_PATHS],
                            cwd=root, capture_output=True, text=True)
    if listed.returncode != 0:
        return [f"the commits that changed {RECEIPT_PATH} after {commit[:12]} could not be "
                f"listed: {listed.stderr.strip()[:120]}"]

    def blob(rev: str) -> str:
        # The receipt's content at a commit, under whichever of its two paths holds it there. A
        # move commit carries the same blob at the new path, so it is not a write.
        for path in RECEIPT_PATHS:
            shown = subprocess.run(["git", "rev-parse", "-q", "--verify", f"{rev}:{path}"],
                                   cwd=root, capture_output=True, text=True)
            if shown.returncode == 0:
                return shown.stdout.strip()
        return ""

    writes, parents_of = [], {}
    for rev in listed.stdout.split():
        # The commit's own parents; `--parents` on a path-limited walk prints rewritten ones.
        parents = subprocess.run(["git", "rev-list", "--no-walk", "--parents", rev], cwd=root,
                                 capture_output=True, text=True).stdout.split()[1:]
        if all(blob(rev) != blob(p) for p in parents):
            writes.append(rev)
            parents_of[rev] = parents
    if len(writes) != 1:
        return [f"{RECEIPT_PATH} changed in {len(writes)} commit(s) between the receipt's commit "
                f"{commit[:12]} and HEAD {head[:12]}; it is recorded once, by the commit that "
                "follows the closure pass"]
    violations = []
    unheld = sorted(finished - held)
    if unheld:
        violations.append(
            f"{RECEIPT_PATH} records as finished {len(unheld)} item(s) that were not held open at "
            f"its commit {commit[:12]}: " + ", ".join(unheld[:8]))
    ids_in = (lambda text: {i for i, _, _ in _parse_todo_stack(text)[0]} if text is not None
              else set())
    child = ids_in(_todo_stack_at(root, writes[0]))
    # Deleted by the recording commit means deleted against each of its parents: against the
    # first alone, a merge would count an item the other side had already deleted, and which
    # side is first is only the order the merge was made in.
    deleted = None
    for parent in parents_of[writes[0]] or [f"{writes[0]}^"]:
        gone = ids_in(_todo_stack_at(root, parent)) - child
        deleted = gone if deleted is None else deleted & gone
    kept = sorted((finished & held) - deleted)
    if kept:
        violations.append(
            f"{RECEIPT_PATH} records as finished {len(kept)} item(s) that the commit recording it, "
            f"{writes[0][:12]}, does not delete from {TODO_PATH}: " + ", ".join(kept[:8]))
    return violations


#: The action every PyPI publication step uses. A job with a step that uses it publishes.
PUBLISH_ACTION = "pypa/gh-action-pypi-publish"
#: A run that uploads with twine, by any interpreter: ``twine upload`` or ``python -m twine upload``.
_TWINE_UPLOAD = re.compile(r"\btwine\s+upload\b")


def _publishes(step: dict) -> bool:
    """Whether one step uploads a distribution: the PyPI action, or a twine upload in its run."""
    return (str(step.get("uses") or "").startswith(PUBLISH_ACTION)
            or _TWINE_UPLOAD.search(str(step.get("run") or "")) is not None)


def _continues_on_error(value) -> bool:
    """Whether a ``continue-on-error`` value lets a failure pass: anything but absent or false."""
    return value is not None and value is not False and str(value).strip().lower() != "false"


def publication_continue_on_error(workflow: str) -> List[str]:
    """Each publication job, and each step of one, that continues on error.

    A publication job has a step that uses :data:`PUBLISH_ACTION` or runs ``twine upload``. A job
    that calls a reusable workflow counts too: that workflow's steps are in a file this check does
    not read, so the call is refused as publication rather than taken as none. A failed upload in
    one would read as a passing release. ``continue-on-error`` on any other job is not refused: the
    pandas 3 job reports and does not gate, and :func:`required_ci_jobs` skips it for that reason.
    """
    import yaml

    document = yaml.safe_load(workflow) or {}
    found = []
    for job_id, job in (document.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        steps = [s for s in (job.get("steps") or []) if isinstance(s, dict)]
        if not (job.get("uses") or any(_publishes(s) for s in steps)):
            continue
        if _continues_on_error(job.get("continue-on-error")):
            found.append(f"publication job {job_id!r} continues on error, so a failed upload "
                         "would not fail the release")
        for step in steps:
            if _continues_on_error(step.get("continue-on-error")):
                found.append(f"a step of publication job {job_id!r} continues on error, so a "
                             "failed upload would not fail the release")
    return found


def check_release_readiness(root: pathlib.Path = REPO_ROOT,
                            head: Optional[str] = None) -> List[str]:
    """AGENTS.md section 11 condition 3, as amended 2026-09-23.

    The open stack holds only problems not yet triaged; the record of a triaged problem is
    its repair, the commit that showed it false, or its todo entry. What is required,
    mechanically:

      1. the open stack exists and holds no table data row, in any section;
      2. no todo item is still required for this cycle, and every item's release is readable.
         An item is not required when it is deferred to the next cycle, or when it is this
         cycle's release step, which completes only after the tag; and no line inside such an
         item, or outside any item, marks work required for this cycle; and the roadmap exists
         and :func:`roadmap_rows` refuses none of its lines;
      3. the independent blocker-focused closure receipt exists and reports zero, and its
         commit is HEAD or an ancestor of HEAD that differs from it only in the receipt and
         the todo stack, where no item held open at the receipt's commit changed its release,
         and every one deleted since is one the receipt records as finished;
      4. the committed peak-memory record names the version HEAD declares, and no operation in it
         grew past the bound since the previous release without a reason in CHANGELOG.md;
      5. ``artifacts/changelog.d/`` holds nothing but its README, so every fragment is in CHANGELOG.md.
      6. the workflow at HEAD exists, and no publication job in it continues on error, so a failed
         upload cannot read as a release.

    Deliberately not a harness gate: this is false for almost all of a cycle, and a gate that
    fails every day is a gate people learn to skip.

    The stacks and receipt are read as committed at HEAD, and an uncommitted change anywhere in the
    working tree is itself a violation: the release is of a commit, and a working-copy edit is
    not in it.
    """
    violations: List[str] = []

    # 0. the evidence is what HEAD commits
    dirty = uncommitted_paths(root)
    if dirty is None:
        violations.append(
            "git cannot report whether the working tree has uncommitted changes, so whether "
            f"the tree being released, and the {', '.join(STEP_0A_PATHS)} STEP 0a reads from "
            "HEAD, are the ones in the working copy is unknown")
    elif dirty:
        violations.append(
            f"{len(dirty)} file(s) have uncommitted changes: {', '.join(dirty[:8])}"
            + (" ..." if len(dirty) > 8 else "") + ". The release, and the stacks and receipt "
            "STEP 0a reads, are the commit at HEAD; commit or discard the changes")

    # 1. the open stack holds no table data row
    open_text = _text_at(root, "HEAD", OPEN_STACK)
    if open_text is None:
        violations.append(
            f"{OPEN_STACK} is missing at HEAD, so whether any open row remains is unknown")
    elif _open_rows_in(open_text):
        rows = _open_rows_in(open_text)
        violations.append(
            f"{len(rows)} table row(s) remain in {OPEN_STACK}; each must be repaired, "
            "shown false, or moved into the todo stack: " + "; ".join(r[:40] for r in rows[:8])
            + (" ..." if len(rows) > 8 else ""))

    # 2. no required item remains
    todo = _text_at(root, "HEAD", TODO_PATH)
    if todo is None:
        violations.append(f"{TODO_PATH} is missing at HEAD, so whether any item is still "
                          f"required for {RELEASE_CYCLE} is unknown")
    items, unreadable = _parse_todo_stack(todo) if todo is not None else ([], [])
    # A value other than this cycle's `required-` is named, so a release step or a deferral
    # written for the wrong cycle says why it still counts.
    required = [f"{i} {t}" + ("" if r == f"required-{RELEASE_CYCLE}" else f" [{r[:40]}]")
                for i, t, r in items if r not in (DEFERRED_VALUE, RELEASE_STEP_VALUE)]
    if required:
        violations.append(
            f"{len(required)} todo item(s) are still required for {RELEASE_CYCLE}: "
            + "; ".join(required[:8]) + (" ..." if len(required) > 8 else ""))
    if unreadable:
        violations.append(
            f"{len(unreadable)} todo section(s) look like items but cannot be read, so whether "
            f"they are required for {RELEASE_CYCLE} is unknown: " + "; ".join(unreadable[:8])
            + (" ..." if len(unreadable) > 8 else ""))
    marked = required_work_outside_held_items(todo) if todo is not None else []
    if marked:
        violations.append(
            f"{len(marked)} line(s) mark work required for {RELEASE_CYCLE} or earlier inside a "
            "section that does not hold the release open, so the item's own field under-reports "
            "it: " + "; ".join(marked[:8]) + (" ..." if len(marked) > 8 else ""))
    roadmap = _text_at(root, "HEAD", ROADMAP_PATH)
    if roadmap is None:
        violations.append(f"{ROADMAP_PATH} is missing at HEAD, so whether work deferred past "
                          f"{NEXT_CYCLE} is recorded is unknown")
    else:
        refused = roadmap_rows(roadmap, {i for i, _, _ in items})[1]
        if refused:
            violations.append(
                f"{len(refused)} line(s) of {ROADMAP_PATH} are refused: " + "; ".join(refused[:8])
                + (" ..." if len(refused) > 8 else ""))

    # 3. the independent closure receipt
    receipt = _text_at(root, "HEAD", RECEIPT_PATH)
    commit, found = _receipt_fields(receipt) if receipt is not None else (None, None)
    if commit is None:
        violations.append(
            f"{RECEIPT_PATH} is missing at HEAD or states no commit; the blocker-focused "
            "fixpoint pass has not been recorded")
    else:
        stale = receipt_commit_violation(root, commit, head)
        if stale:
            violations.append(stale)
        elif commit != head:
            violations.extend(relabelled_after_receipt(root, commit, head,
                                                       receipt_finished_items(receipt)))
    if found is None:
        violations.append(f"{RECEIPT_PATH} does not state how many new release-blocking "
                          "problems the closure pass found")
    elif found != 0:
        violations.append(
            f"the closure pass found {found} new release-blocking problem(s); the fixpoint is "
            "zero NEW BLOCKERS, not zero new observations")

    # 4. the peak-memory record is this version's, and no operation in it grew past the bound
    stale_record = peak_memory_record_violation(root)
    if stale_record:
        violations.append(stale_record)
    else:
        violations.extend(peak_memory_growth_violations(root))

    # 5. every changelog fragment has been assembled into CHANGELOG.md
    leftover = unassembled_fragments(root)
    if leftover is None:
        violations.append("git cannot list artifacts/changelog.d/ at HEAD, so whether every changelog "
                          "fragment reached CHANGELOG.md is unknown")
    elif leftover:
        violations.append(
            f"{len(leftover)} file(s) in artifacts/changelog.d/ at HEAD are not assembled into "
            f"CHANGELOG.md, so the release notes would omit them: {', '.join(leftover[:8])}"
            + (" ..." if len(leftover) > 8 else "") + ". Run scripts/assemble_changelog.py")

    # 6. no publication job continues on error, so a failed upload cannot read as a release
    workflow = _text_at(root, "HEAD", CI_WORKFLOW_PATH)
    if workflow is None:
        violations.append(f"{CI_WORKFLOW_PATH} is missing at HEAD, so whether a publication job "
                          "continues on error is unknown")
    else:
        try:
            violations.extend(publication_continue_on_error(workflow))
        except Exception as exc:  # noqa: BLE001 - an unreadable workflow is unknown, not clean
            violations.append(f"{CI_WORKFLOW_PATH} at HEAD cannot be read, so whether a "
                              f"publication job continues on error is unknown: {exc}")
    return violations


def check_release_facts() -> List[str]:
    """STEP 0a's fact condition: no typed fact is VIOLATED in release mode. An UNHELD fact whose
    item is due in this cycle (``RELEASE_CYCLE``) fails here; the everyday gate does not run it."""
    from scripts import fact_gate  # the fact gate imports this module, so the import is local

    _, results = fact_gate.run(release=True)
    return [f"fact {fact_id} is VIOLATED on the release check: {'; '.join(reasons)}"
            for fact_id, status, reasons in results if status == fact_gate.VIOLATED]


def main_ancestry_violations(root: pathlib.Path = REPO_ROOT,
                             head: Optional[str] = None) -> List[str]:
    """Why the commit being released drops a commit of ``main``; empty when it does not.

    ``main`` moves by merging ``dev`` into it. At a two-parent commit that is ``origin/main``
    (else ``main``) or whose first parent is, the first parent (the old ``main``) must be an
    ancestor of the second (``dev``). At any other commit, including a lane merged into ``dev``,
    ``origin/main`` (else ``main``) must be an ancestor of it; with neither, the answer is
    unknown and refused. Nothing here fetches.
    """
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)

    target = head or "HEAD"
    listed = git("rev-list", "--parents", "-n", "1", target)
    words = listed.stdout.split()
    if listed.returncode != 0 or not words:
        return [f"{target[:12]} does not resolve, so whether it contains main is unknown"]
    full, parents = words[0], words[1:]
    ref = next((r for r in ("origin/main", "main")
                if git("rev-parse", "--verify", "--quiet", f"{r}^{{commit}}").returncode == 0),
               None)
    if ref is None:
        return ["neither origin/main nor main resolves, so whether main is an ancestor of "
                "the commit being released is unknown"]
    main_sha = git("rev-parse", f"{ref}^{{commit}}").stdout.strip()
    # A merge commit is a release merge only when it is main or merges onto main; any other
    # two-parent commit (a lane merged into dev) is read as a plain commit.
    if len(parents) == 2 and main_sha in (full, parents[0]):
        container, contained = parents[1], parents[0]
        what = f"the first parent {contained[:12]} (the old main) of the merge {target[:12]}"
        where = f"its second parent {container[:12]}"
    else:
        contained, container = ref, target
        what, where = ref, target[:12]
    ancestry = git("merge-base", "--is-ancestor", contained, container)
    if ancestry.returncode == 0:
        return []
    if ancestry.returncode == 1:
        return [f"{what} is not an ancestor of {where}: bring main's commits into dev before "
                "releasing, so the release contains every commit on main"]
    return [f"whether {what} is an ancestor of {where} could not be determined: "
            f"{ancestry.stderr.strip()[:120]}"]


def unassembled_fragments(root: pathlib.Path = REPO_ROOT) -> Optional[List[str]]:
    """Files committed under ``artifacts/changelog.d/`` at HEAD other than its README, or ``None``.

    Anything else there is a change the assembled section does not carry. The exempt names are
    the assembler's own, imported rather than retyped.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.append(str(REPO_ROOT))
    from scripts.assemble_changelog import FRAGMENT_DIR, NOT_FRAGMENTS

    fragment_path = FRAGMENT_DIR.relative_to(REPO_ROOT).as_posix()
    listed = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD", "--", fragment_path],
                            cwd=root, capture_output=True, text=True)
    if listed.returncode != 0:
        return None
    return sorted(name for name in listed.stdout.splitlines()
                  if pathlib.PurePosixPath(name).name not in NOT_FRAGMENTS)


def check_state_is_current(root: pathlib.Path = REPO_ROOT) -> List[str]:
    """Harness gate 20's rule, run first: a present ``artifacts/state.md`` records HEAD.

    The same function the harness runs, not a copy. The harness runs only after the suite, so a
    stale state file used to fail the release twelve to thirty minutes in; it costs a third of a
    second to find here. Imported late because the harness imports this module.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.append(str(REPO_ROOT))
    from scripts.harness_gate import check_state_file_head

    return check_state_file_head(root)


def probe_jnwb_file(venv_python: str, cwd: str, env: dict) -> str:
    """Where `import jnwb` resolves under `env`, from `cwd`. A failing import exits with the
    probe's stderr, so the cause is in the log rather than a bare CalledProcessError."""
    probe = subprocess.run([venv_python, "-c", "import jnwb; print(jnwb.__file__)"],
                           cwd=cwd, env=env, capture_output=True, text=True)
    if probe.returncode != 0:
        raise SystemExit(f"`import jnwb` failed in the tutorial environment:\n{probe.stderr}")
    return probe.stdout.strip()


def check_resolves_under(resolved: str, purelib: str) -> None:
    """Exit unless `import jnwb` resolved under `purelib`, the installed package root.

    A tutorial that fell back to the checkout would pass STEP 8 while testing the source tree;
    the message names both paths so the fallback is visible. An empty purelib resolves to the
    cwd, and an empty or "None" resolution is no evidence at all, so both are refused first.
    """
    if not purelib or not resolved or resolved == "None":
        raise SystemExit(f"cannot verify where jnwb resolved: resolved={resolved!r}, purelib={purelib!r}")
    if not pathlib.Path(resolved).resolve().is_relative_to(pathlib.Path(purelib).resolve()):
        raise SystemExit(f"jnwb resolved to {resolved}, outside the installed package root {purelib}")


def main() -> None:
    log.info("=== STEP 0a: Checking release readiness (AGENTS.md section 11, condition 3) ===")
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        head = None
    stack_violations = (check_state_is_current() + check_release_readiness(head=head)
                        + main_ancestry_violations(head=head) + check_release_facts())
    if stack_violations:
        for violation in stack_violations:
            log.error(violation)
        log.error(
            "A release requires: a state file that is absent or records HEAD; a working tree "
            "with no uncommitted change; an empty problem "
            "stack; zero todo items still required for this cycle; and a blocker-focused closure "
            "receipt reporting zero new blockers, recorded at HEAD or at an ancestor that differs "
            "from HEAD only in the receipt and %s, with no item it held open relabelled since "
            "or deleted without the receipt recording it as finished; and a commit that contains "
            "main (a merge's first parent contained in its second; otherwise origin/main, "
            "fetched, an ancestor); and no typed fact is VIOLATED in release mode. Work deferred "
            "to %s, and "
            "%s items, stay in the todo stack.",
            TODO_PATH, NEXT_CYCLE, RELEASE_STEP_VALUE)
        sys.exit(1)
    releases = [r for _, _, r in _parse_todo_stack(_text_at(REPO_ROOT, "HEAD", TODO_PATH))[0]]
    log.info(
        "PASS: the open stack holds no table row and no required item remains; %d todo item(s) are "
        "deferred to %s and %d are %s, completing after the tag.",
        releases.count(DEFERRED_VALUE), NEXT_CYCLE, releases.count(RELEASE_STEP_VALUE),
        RELEASE_STEP_VALUE)

    log.info("=== STEP 0: Checking required release/test tooling in the active environment ===")
    missing = verify_declared_environment()
    if missing:
        log.error(
            "This interpreter (%s, Python %s) is missing required tooling: %s",
            sys.executable, ".".join(str(v) for v in sys.version_info[:3]), ", ".join(missing))
        log.error("Release qualification would measure an unprovisioned environment. Provision it:")
        log.error('    "%s" -m pip install ".[%s]"', sys.executable, ",".join(REQUIRED_EXTRAS))
        sys.exit(1)
    log.info(
        "PASS: required release/test tooling from [%s] is importable on Python %s "
        "(presence check; pip check in STEP 6 verifies dependency consistency).",
        ",".join(REQUIRED_EXTRAS), ".".join(str(v) for v in sys.version_info[:3]))

    log.info("=== STEP 0b: Checking the declared version against the package index ===")
    version = jnwb_source_version()
    collisions = check_version_is_not_already_published(version, published_versions())
    if collisions:
        for problem in collisions:
            log.error("%s", problem)
        sys.exit(1)
    log.info(
        "PASS: %s is not a version the index already serves.", version)

    log.info("=== STEP 0c: Checking every declared dependency floor is installable ===")
    tag = interpreter_floor_tag()
    floor_problems: List[str] = []
    floors = declared_dependency_floors()
    if not floors:
        log.error("pyproject.toml declares no dependency floors; this check is vacuous")
        sys.exit(1)
    for extra, name, floor in floors:
        floor_problems.extend(check_floor_is_installable(
            name, floor, package_releases(name), tag, extra))
    if floor_problems:
        for problem in floor_problems:
            log.error("%s", problem)
        sys.exit(1)
    log.info("PASS: all %d declared floors install on %s.", len(floors), tag)

    log.info("=== STEP 0d: Checking the release body against package metadata ===")
    metadata = release_metadata()
    body_outcome = check_live_release_body(metadata)
    if body_outcome.violations:
        for problem in body_outcome.violations:
            log.error("release body: %s", problem)
        log.error(
            "The release body is a published, version-bearing surface. Correct it with "
            "`gh release edit v%s --notes-file <file>` and re-run.", metadata.version)
        sys.exit(1)
    if body_outcome.status == BODY_SKIPPED:
        # Logged as SKIP, never as PASS. An unreachable release means the body's claims are
        # unverified; reporting that as success is the failure mode this step was added for.
        log.warning("SKIP: the release body was NOT checked -- %s", body_outcome.detail)
        log.warning(
            "      Its version, Python support and install command remain unverified. This "
            "is not a pass.")
        _record_skip("release body (STEP 0d)")
    else:
        log.info(
            "PASS: the release body for %s agrees with package metadata (%s).",
            metadata.version, body_outcome.detail)

    log.info("=== STEP 0e: Resolving the CI conclusion for the commit being qualified ===")
    skip_ci = os.environ.get(SKIP_CI_ENV) == "1"
    if head is None:
        ci = CIOutcome(CI_UNRESOLVED, "HEAD could not be resolved with `git rev-parse`", [], [])
    else:
        ci = check_ci_conclusion(head)
    if ci.legs:
        log.info("CI legs for %s:", ci.detail)
        for row in format_leg_table(ci.legs):
            log.info("%s", row)
    if ci.status == CI_VERIFIED:
        log.info("PASS: every required CI leg ran and concluded success for %s (%s).",
                 (head or "?")[:12], ci.detail)
    else:
        logger = log.warning if skip_ci else log.error
        headline = ("CI is NOT green for this commit" if ci.status == CI_FAILED
                    else "the CI conclusion for this commit could NOT be resolved")
        logger("%s: %s", headline, ci.detail)
        for problem in ci.violations:
            logger("  %s", problem)
        if skip_ci:
            log.warning(
                "SKIPPED: %s=1 is set, so a commit whose CI is %s is being allowed through. "
                "This is not a pass -- it is a decision to tag without CI evidence.",
                SKIP_CI_ENV, ci.status)
            _record_skip(f"CI conclusion (STEP 0e, {SKIP_CI_ENV}=1)")
        else:
            log.error(
                "A tag must name a commit whose pipeline ran and passed, leg by leg. An "
                "aggregate 'no failure' is not that: a job with `needs:` reports `skipped` "
                "when its dependency failed, so a red suite can leave the build job showing "
                "no red at all. Merge this commit to main, let CI finish green on main, then "
                "re-run. To tag "
                "without CI evidence anyway, set %s=1 -- deliberately, and knowing it is "
                "recorded here as unverified.", SKIP_CI_ENV)
            sys.exit(1)

    log.info("=== STEP 2: Running harness pre-flight verification gate ===")
    run_cmd([sys.executable, str(REPO_ROOT / "scripts" / "harness_gate.py")])

    log.info("=== STEP 2a: Recorded mutation gaps still hold at HEAD ===")
    gaps_hold, gaps_report = check_known_gaps_hold()
    log.info(gaps_report)
    if not gaps_hold:
        log.error("A recorded mutation gap no longer matches the measurement; update `known_gaps` in scripts/mutation_harness.py.")
        sys.exit(1)

    for cmd in _api_md_check_commands():
        label = "current interpreter" if cmd[0] == sys.executable else "Python 3.12 floor"
        log.info(f"=== STEP 2b: API docs generator drift check ({label}) ===")
        run_cmd(cmd)

    with tempfile.TemporaryDirectory() as tmpdir:
        staging_dir = pathlib.Path(tmpdir)
        dist_dir = staging_dir / "dist"
        dist_dir.mkdir()

        log.info(f"=== STEP 3: Building sdist and wheel in staging directory: {dist_dir} ===")
        run_cmd([sys.executable, "-m", "build", "--outdir", str(dist_dir), str(REPO_ROOT)])

        wheels = list(dist_dir.glob("*.whl"))
        sdists = list(dist_dir.glob("*.tar.gz"))
        if not wheels or not sdists:
            log.error("Build failed to produce wheel or sdist!")
            sys.exit(1)

        whl = wheels[0]
        sdist = sdists[0]
        log.info(f"Produced wheel: {whl.name} ({whl.stat().st_size:,} bytes)")
        log.info(f"Produced sdist: {sdist.name} ({sdist.stat().st_size:,} bytes)")

        log.info("=== STEP 4: Inspecting archive manifests ===")

        with zipfile.ZipFile(whl, "r") as z:
            whl_problems = forbidden_entries(z.namelist())
        if whl_problems:
            for problem in whl_problems:
                log.error("wheel: %s", problem)
            sys.exit(1)
        log.info("PASS: Wheel archive contains zero forbidden entries.")

        with tarfile.open(sdist, "r:gz") as t:
            sdist_problems = forbidden_entries(t.getnames())
        if sdist_problems:
            for problem in sdist_problems:
                log.error("sdist: %s", problem)
            sys.exit(1)
        log.info("PASS: Sdist archive contains zero forbidden entries.")

        log.info("=== STEP 5: Validating metadata with twine ===")
        run_cmd([sys.executable, "-m", "twine", "check", str(whl), str(sdist)])

        log.info("=== STEP 6: Creating isolated venv for wheel installation ===")
        venv_dir = staging_dir / "isolated_venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

        if sys.platform == "win32":
            venv_python = str(venv_dir / "Scripts" / "python.exe")
        else:
            venv_python = str(venv_dir / "bin" / "python")

        log.info(f"Installing wheel {whl} into isolated environment...")
        # `python -m pip`, not the pip executable: on Windows pip refuses to replace its
        # own running .exe and exits 1, which failed this gate before it tested anything.
        subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([venv_python, "-m", "pip", "install", str(whl)], check=True)

        log.info("Checking package dependencies with pip check...")
        check_res = subprocess.run([venv_python, "-m", "pip", "check"], capture_output=True, text=True)
        if check_res.returncode != 0:
            log.error(f"pip check failed: {check_res.stderr}\n{check_res.stdout}")
            sys.exit(check_res.returncode)
        log.info("PASS: pip check verified zero broken requirements.")

        log.info("=== STEP 7: Executing installed-package smoke tests outside repository ===")
        # The one installed smoke, scripts/smoke_installed.py, with the arguments CI passes (Hamm
        # 2026-10-13). PYTHONPATH is stripped, as for the tutorials below: the checkout must not
        # satisfy `import jnwb`.
        smoke_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        res = subprocess.run(
            [venv_python, str(REPO_ROOT / "scripts" / "smoke_installed.py"),
             "--expected-version", jnwb_source_version(), "--not-under", str(REPO_ROOT)],
            cwd=str(staging_dir), env=smoke_env, capture_output=True, text=True)
        if res.returncode != 0:
            log.error(f"Smoke test failed in isolated environment:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
            sys.exit(res.returncode)
        log.info(res.stdout.strip())

        log.info("=== STEP 8: Executing tutorials against the installed wheel ===")
        tutorials = sorted((REPO_ROOT / "examples" / "tutorials").glob("[0-9][0-9]_*.py"))
        if not tutorials:
            log.error("No numbered tutorials found; 0.2.4-03 cannot be verified.")
            sys.exit(1)
        # As CI does: the extras the tutorials draw are installed only now, after STEP 7 has
        # checked the wheel without them (tutorial 10 needs `vis` and `wavemap`).
        subprocess.run([venv_python, "-m", "pip", "install", f"{whl}[{','.join(TUTORIAL_EXTRAS)}]"],
                       check=True)
        purelib = subprocess.run(
            [venv_python, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
            check=True, capture_output=True, text=True).stdout.strip()
        # PYTHONPATH is stripped and the CWD is the staging directory, so a tutorial that
        # only runs from the source tree fails here instead of passing by checkout proximity.
        # JNWB_EXPECTED_PACKAGE_ROOT makes each tutorial's prefer-the-checkout guard stand
        # aside; without it every tutorial imported the checkout it ships in, not the wheel.
        tutorial_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        tutorial_env["JNWB_EXPECTED_PACKAGE_ROOT"] = purelib
        # Before any tutorial runs: where `import jnwb` lands under the same environment.
        resolved = probe_jnwb_file(venv_python, str(staging_dir), tutorial_env)
        check_resolves_under(resolved, purelib)
        for tutorial in tutorials:
            res = subprocess.run(
                [venv_python, str(tutorial)], cwd=str(staging_dir),
                env=tutorial_env, capture_output=True, text=True)
            if res.returncode != 0:
                log.error("Tutorial %s failed against the installed wheel:\nSTDOUT:\n%s\nSTDERR:\n%s",
                          tutorial.name, res.stdout, res.stderr)
                sys.exit(res.returncode)
            log.info("PASS: %s executed against the installed wheel.", tutorial.name)
        log.info("PASS: all %d tutorials ran against the installed artifact.", len(tutorials))

    # Last, because it is the most expensive step: everything before it takes minutes, so a
    # defect any of them finds is reported before, not after, a twelve to thirty minute run.
    # Nothing before it reads what the suite produces, and every step must pass for the
    # verdict below, so the order changes when a failure is seen, not what passes.
    log.info("=== STEP 1: Running full test suite ===")
    # Parallel, because the serial run took over twenty minutes; the ten slowest tests and the
    # wall time are printed so a cost that grows is seen at the release that grew it.
    started = time.monotonic()
    run_cmd([sys.executable, "-m", "pytest", "-q", "-n", "auto", "--durations=10",
             "-p", "no:cacheprovider", "tests/"])
    log.info("Suite wall time: %.0f s", time.monotonic() - started)
    # Peak memory is the other cost measured before a release, logged here with no threshold.
    # Nothing is written into the tree: the committed artifacts/benchmarks/performance/peak_memory.json is
    # refreshed before the closure pass, so the receipt covers it.
    run_cmd([sys.executable, str(REPO_ROOT / "scripts" / "measure_peak_memory.py")])

    log.info("=============================================================")
    banner = verified_banner(SKIPPED_CHECKS)
    (log.warning if SKIPPED_CHECKS else log.info)("%s", banner)
    log.info("=============================================================")


if __name__ == "__main__":
    main()
