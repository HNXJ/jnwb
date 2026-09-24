"""Deterministic Release Gate for jnwb.

Pipeline:
  0. Required release/test tooling is present in the active environment
  0b. The declared version is not one the package index already serves
  0c. Every declared dependency floor installs on the declared interpreter
  0d. The release body's version, Python support and install command match package metadata
  0e. CI concluded success, per required leg, for the exact commit being qualified
  1. Full test suite execution (pytest tests/)
  2. Harness pre-flight gates
  3. Clean distribution build (sdist + wheel)
  4. Manifest & forbidden-content inspection (no _unused, no omission, no artifacts)
  5. Distribution metadata & README validation (twine check)
  6. Isolated environment wheel installation & pip check
  7. Installed-package smoke verification without omission

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


#: Extras whose tooling must be present for release qualification to mean anything. ``docs`` is
#: included because tests/ contains a strict MkDocs build assertion: without it the suite does
#: not fail, it reports a *different* result, which is worse.
REQUIRED_EXTRAS = ("test", "docs")


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

    A job carrying an ``if:`` is excluded: the two publish jobs are conditional by design and
    report ``skipped`` on an ordinary push, so requiring them would make the check fail for
    every commit and therefore be switched off. A job *without* an ``if:`` is unconditional,
    and ``skipped`` on such a job means an upstream ``needs:`` never produced it -- which is
    exactly the shape this check exists to catch. Measured at 30c425cf: ``Build & Validate
    Distribution`` is ``needs: test``, and with four test legs red it reported ``skipped``
    rather than ``failure``. A rule reading "no job concluded failure" calls that green.
    """
    import itertools

    import yaml

    if workflow is None:
        workflow = ((root or REPO_ROOT) / CI_WORKFLOW_PATH).read_text(encoding="utf-8")
    document = yaml.safe_load(workflow) or {}
    jobs = document.get("jobs") or {}

    names: List[str] = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict) or "if" in job:
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
        for combination in itertools.product(*(axes[key] for key in keys)):
            values = {k: str(v) for k, v in zip(keys, combination)}
            names.append(_MATRIX_REF.sub(
                lambda m: values.get(m.group(1), m.group(0)), template).strip())
    return names


def select_run_for_commit(sha: str, stdout: str) -> Tuple[Optional[dict], Optional[str]]:
    """``(run, None)`` or ``(None, reason)`` for the newest run whose head is ``sha``.

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
    # Newest first is gh's order; databaseId is monotonic, so re-derive rather than assume.
    return max(matching, key=lambda r: r.get("databaseId") or 0), None


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
    authentication, no network, no run for this SHA, a run still executing, unreadable
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
        "--json", "databaseId,headSha,status,conclusion,workflowName",
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


PROBLEM_STACK = "artifacts/problem_stack.md"
# A problem row as it would render in any section: a table line, optionally blockquoted, whose
# first cell starts with a `P-` id in any case and under any inline markup. Matched however its
# cells are counted, so a row under a stray heading or with a missing cell still counts.
_PROBLEM_ROW = re.compile(r"^[ \t>]*\|[ \t*`_~]*P-\w", re.IGNORECASE)
#: The header of the one table `## Open` may hold. Pinned, so a problem cannot stand in as it.
OPEN_HEADER = ("ID", "Problem", "Found by")
_OPEN_HEADING = re.compile(r"^ {0,3}##[ \t]+Open[ \t]*$")
_SECTION_END = re.compile(r"^ {0,3}#{1,2}(?:[ \t]|$)")
_SEPARATOR_CELL = re.compile(r"^:?-+:?$")


def _cells(line: str) -> Optional[List[str]]:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def open_section_content(text: str) -> Optional[List[Tuple[int, str]]]:
    """``(line number, line)`` for every line under ``## Open`` that is not blank and is not
    the table's one header row or the separator row directly below it; ``None`` when the stack
    has no ``## Open`` section.

    Under ``## Open`` anything else is an untriaged problem, whatever form it takes. Reading
    only row-shaped lines let a bold, code-spanned or lower-case id, a blockquoted table, a
    bullet, an id in the second column and a row with no id all stand in the section unseen.
    """
    found: Optional[List[Tuple[int, str]]] = None
    in_open, expect = False, None
    for lineno, line in enumerate(text.splitlines(), 1):
        if _OPEN_HEADING.match(line):
            found = [] if found is None else found
            in_open, expect = True, "header"
            continue
        if in_open and _SECTION_END.match(line):
            in_open = False
        if not in_open or not line.strip():
            continue
        cells = _cells(line)
        if expect == "header" and cells is not None and tuple(cells) == OPEN_HEADER:
            expect = "separator"
            continue
        if expect == "separator" and cells and all(_SEPARATOR_CELL.match(c) for c in cells):
            expect = None
            continue
        expect = None
        found.append((lineno, line.strip()))
    return found


def problem_rows(root: pathlib.Path = REPO_ROOT) -> Optional[List[str]]:
    """Every problem in the problem stack, or ``None`` when the file is missing.

    That is every line under ``## Open`` other than its header and separator, and every
    problem-shaped table row in any other section. A release requires the stack to hold none:
    a problem leaves it by being repaired, by being shown false, or by moving into the todo
    stack as an item.
    """
    path = root / PROBLEM_STACK
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    rows = dict(open_section_content(text) or [])
    for lineno, line in enumerate(text.splitlines(), 1):
        if _PROBLEM_ROW.match(line):
            rows.setdefault(lineno, line.strip())
    return [rows[n][:120] for n in sorted(rows)]


def remaining_todo_items(root: pathlib.Path = REPO_ROOT) -> List[str]:
    """Item headings left in the todo stack. Finished items are deleted, so any heading is work."""
    path = root / "artifacts" / "todo_stack.md"
    if not path.exists():
        return [f"{path} is missing; condition 3 cannot be evaluated"]
    # `\d\d-\d+`, not `\d\d-\d\d`: item ids passed three digits at 06-100, and the two-digit
    # form matched none of them. Measured at 1be7c144: 46 of 57 items counted, 11 invisible --
    # including 06-101, an unresolved human ruling. Under the pre-amendment condition that made
    # STEP 0a able to pass with eleven items outstanding.
    items, _ = _parse_todo_stack(path.read_text(encoding="utf-8"))
    return [f"{ident} {title}".strip() for ident, title, _ in items]


# A heading of any depth. Matching only `### ` made an item written one level deeper invisible,
# together with its `Release:` field, which then belonged to the item above it.
_HEADING = re.compile(r"^ {0,3}(#+)(?:[ \t]+(.*?))?[ \t]*$")
# A heading inside a blockquote or a list item still renders as a heading. Read as body text, it
# and its field belonged to the section above, so a required item hid under a deferred one.
_CONTAINED_HEADING = re.compile(
    r"^[ \t]*(?:(?:>|[-*+]|\d+[.)])[ \t]*)+(#+)(?:[ \t]+(.*?))?[ \t]*$")
# The one item-heading form STEP 0a reads an id from; the title may be empty.
_ITEM_HEADING = re.compile(r"^(\d\d-\d+)(?:[ \t]+(.*))?$")
# Anything that starts like an item id once leading markup is dropped, and is not an ISO date.
# A heading of this shape that `_ITEM_HEADING` does not read is a violation, never a skip.
_ITEM_SHAPED = re.compile(r"^[\s*_`\[(#]*\d+-\d+(?!\d|-\d)")
# The value is read from the canonical form only. Detection is looser, so that a bold, listed,
# quoted, indented or lowercase field still marks its heading as an item rather than as prose,
# and makes an item's release unreadable rather than letting its canonical line speak alone.
_RELEASE_VALUE = re.compile(r"^Release:\s*(.*)$")
# Searched anywhere in a line, so a field in a table cell or wrapped in HTML tags is seen too.
_RELEASE_ANY = re.compile(r"(?<![\w-])Release(?:[*_`]|</?\w+[^>]*>)*\s*:", re.IGNORECASE)
# The two other heading syntaxes Markdown renders: a setext underline below a paragraph line,
# and an HTML heading element. Either one read as body text hid its item under the one above.
_SETEXT_UNDERLINE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
_HTML_HEADING = re.compile(r"^\s*<h([1-6])\b[^>]*>(.*?)</h\1>\s*$", re.IGNORECASE)


def _parse_todo_stack(text: str) -> Tuple[List[Tuple[str, str, str]], List[str]]:
    """``(items, unparseable)`` read from todo-stack text.

    A section is a heading and the lines up to the next heading of any depth. It is an item when
    its heading reads as an id, or when its lines carry a ``Release:`` field, at any depth. The
    release value is the section's own field: ``MISSING`` when it has none, every distinct
    value joined when it states more than one, and ``NONCANONICAL`` when any of its ``Release:``
    lines is not in the canonical form, so that none of these reads as deferred. A heading inside
    a blockquote or list item opens a section like any other.

    ``unparseable`` names each section that is item-shaped, or carries a ``Release:`` field, but
    whose id cannot be read, and each item whose release cannot be read. The caller reports these
    as violations: an item the parser cannot read is still work, and skipping it would report
    emptiness that was not established.
    """
    sections: List[Tuple[Optional[str], List[str]]] = [(None, [])]
    for line in text.splitlines():
        heading = (_HEADING.match(line) or _CONTAINED_HEADING.match(line)
                   or _HTML_HEADING.match(line))
        body = sections[-1][1]
        if heading:
            sections.append(((heading.group(2) or "").strip(), []))
        elif _SETEXT_UNDERLINE.match(line) and body and body[-1].strip():
            sections.append((body.pop().strip(), []))
        else:
            body.append(line)
    items: List[Tuple[str, str, str]] = []
    unparseable: List[str] = []
    for title, body in sections:
        values = [m.group(1).strip().rstrip(".").strip()
                  for m in map(_RELEASE_VALUE.match, body) if m]
        has_field = any(_RELEASE_ANY.search(line) for line in body)
        item = _ITEM_HEADING.match(title) if title is not None else None
        if item:
            distinct = list(dict.fromkeys(values))
            # Capture to end of line and strip one trailing sentence period. Stopping at the
            # first `.` would truncate `deferred-0.2.7` to `deferred-0`, and the truncated value
            # compares unequal to the deferred marker -- so every deferred item would read as
            # still required.
            value = ("MISSING" if not distinct else distinct[0] if len(distinct) == 1
                     else "CONFLICTING: " + " / ".join(distinct))
            noncanonical = [line.strip() for line in body
                            if _RELEASE_ANY.search(line) and not _RELEASE_VALUE.match(line)]
            if noncanonical:
                value = "NONCANONICAL"
                unparseable.append(
                    f"item {item.group(1)} has a Release: line not written 'Release: <value>' "
                    f"at the start of a line, so its release cannot be read: "
                    f"{noncanonical[0][:60]!r}")
            items.append((item.group(1), (item.group(2) or "").strip(), value))
        elif title is None:
            if has_field:
                unparseable.append("a Release: field appears before the first heading")
        elif has_field or _ITEM_SHAPED.match(title):
            unparseable.append(f"heading {title[:60]!r} is item-shaped or carries a Release: "
                               "field, but no item id can be read from it")
    return items, unparseable


def unparseable_todo_headings(root: pathlib.Path = REPO_ROOT) -> List[str]:
    """Todo-stack sections that look like items but whose id STEP 0a cannot read."""
    path = root / "artifacts" / "todo_stack.md"
    if not path.exists():
        return []
    return _parse_todo_stack(path.read_text(encoding="utf-8"))[1]


RELEASE_CYCLE = jnwb_source_version()
NEXT_CYCLE = "{}.{}.{}".format(
    *(int(p) + (i == 2) for i, p in enumerate(
        re.match(r"(\d+)\.(\d+)\.(\d+)", RELEASE_CYCLE).groups())))
RECEIPT_PATH = "artifacts/blocker_fixpoint_receipt.md"
TODO_PATH = "artifacts/todo_stack.md"
# The files a commit may change after the closure pass without invalidating it. A committed
# receipt cannot name its own commit, so it names the one the pass ran against, and the commit
# that records it -- together with the todo-stack update the pass produced -- follows.
RECEIPT_MAY_FOLLOW = frozenset({RECEIPT_PATH, TODO_PATH})
# The two release values that do not hold this cycle open. A release step completes only after
# the tag, so STEP 0a cannot wait for it; any other cycle's value is not this cycle's.
DEFERRED_VALUE = f"deferred-{NEXT_CYCLE}"
RELEASE_STEP_VALUE = f"release-step-{RELEASE_CYCLE}"


def todo_release_fields(root: pathlib.Path = REPO_ROOT) -> List[Tuple[str, str, str]]:
    """``(id, title, release)`` for every item in the todo stack, at any heading depth."""
    path = root / "artifacts" / "todo_stack.md"
    if not path.exists():
        return []
    return _parse_todo_stack(path.read_text(encoding="utf-8"))[0]


def blocker_fixpoint_receipt(root: pathlib.Path = REPO_ROOT) -> Tuple[Optional[str], Optional[int]]:
    """``(commit, new_blockers)`` from the closure-pass receipt, or ``(None, None)``.

    ``commit`` is the commit the pass ran against. A committed receipt cannot name its own
    commit, so :func:`receipt_commit_violation` decides whether it still stands for HEAD.
    """
    path = root / RECEIPT_PATH
    if not path.exists():
        return None, None
    text = path.read_text(encoding="utf-8")
    commit = re.search(r"^\|\s*commit\s*\|\s*`([0-9a-f]{40})`\s*\|", text, re.M)
    found = re.search(r"^\|\s*new release-blocking problems found\s*\|\s*(\d+)\s*\|", text, re.M)
    return (commit.group(1) if commit else None,
            int(found.group(1)) if found else None)


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


def _todo_stack_at(root: pathlib.Path, rev: str) -> Optional[str]:
    """The todo stack's text at ``rev``, or ``None`` when git cannot show it there."""
    shown = subprocess.run(["git", "show", f"{rev}:{TODO_PATH}"], cwd=root, capture_output=True)
    return shown.stdout.decode("utf-8", errors="replace") if shown.returncode == 0 else None


def relabelled_after_receipt(root: pathlib.Path, commit: str, head: str) -> List[str]:
    """Why the todo stack at HEAD does not carry the receipt's release values forward.

    The todo stack may change after the closure pass so that finished items can be deleted, but
    the pass judged what stays required. An item this cycle's release waited on at the receipt's
    commit (any value but the deferred and release-step ones) must carry the same value at HEAD,
    or be gone: a deleted item is done. Items added after the receipt are judged by condition 2
    alone. A stack absent at either commit, or unreadable at the receipt's, is refused.
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
    changed = [f"{i}: {held[i][:40]} -> {r[:40]}"
               for i, _, r in _parse_todo_stack(at_head)[0] if i in held and r != held[i]]
    if not changed:
        return []
    return [f"{len(changed)} todo item(s) held open for {RELEASE_CYCLE} at the receipt's commit "
            f"{commit[:12]} carry another release at HEAD {head[:12]}; only a new closure pass "
            "may relabel an item it judged, so finish and delete it or record a new receipt: "
            + "; ".join(changed[:8]) + (" ..." if len(changed) > 8 else "")]


def check_release_readiness(root: pathlib.Path = REPO_ROOT,
                            head: Optional[str] = None) -> List[str]:
    """AGENTS.md section 11 condition 3, as amended 2026-09-23.

    The problem stack holds only problems not yet triaged; the record of a triaged problem is
    its repair, the commit that showed it false, or its todo entry. What is required,
    mechanically:

      1. the problem stack exists, its ``## Open`` section holds nothing but the table header
         and separator, and no other section holds a problem row;
      2. no todo item is still required for this cycle, and every item's release is readable.
         An item is not required when it is deferred to the next cycle, or when it is this
         cycle's release step, which completes only after the tag;
      3. the independent blocker-focused closure receipt exists and reports zero, and its
         commit is HEAD or an ancestor of HEAD that differs from it only in the receipt and
         the todo stack, where no item held open at the receipt's commit changed its release.

    Deliberately not a harness gate: this is false for almost all of a cycle, and a gate that
    fails every day is a gate people learn to skip.
    """
    violations: List[str] = []

    # 1. the problem stack is empty
    rows = problem_rows(root)
    if rows is None:
        violations.append(
            f"{PROBLEM_STACK} is missing, so whether any problem is untriaged is unknown")
    elif open_section_content((root / PROBLEM_STACK).read_text(encoding="utf-8")) is None:
        violations.append(
            f"{PROBLEM_STACK} has no '## Open' section, so whether any problem is untriaged "
            "is unknown")
    elif rows:
        violations.append(
            f"{len(rows)} problem row(s) remain in {PROBLEM_STACK}; each must be repaired, "
            "shown false, or moved into the todo stack: " + "; ".join(r[:40] for r in rows[:8])
            + (" ..." if len(rows) > 8 else ""))

    # 2. no required item remains
    if not (root / TODO_PATH).exists():
        violations.append(f"{TODO_PATH} is missing, so whether any item is still required for "
                          f"{RELEASE_CYCLE} is unknown")
    items = todo_release_fields(root)
    # A value other than this cycle's `required-` is named, so a release step or a deferral
    # written for the wrong cycle says why it still counts.
    required = [f"{i} {t[:34]}" + ("" if r == f"required-{RELEASE_CYCLE}" else f" [{r[:40]}]")
                for i, t, r in items if r not in (DEFERRED_VALUE, RELEASE_STEP_VALUE)]
    if required:
        violations.append(
            f"{len(required)} todo item(s) are still required for {RELEASE_CYCLE}: "
            + "; ".join(required[:8]) + (" ..." if len(required) > 8 else ""))
    unreadable = unparseable_todo_headings(root)
    if unreadable:
        violations.append(
            f"{len(unreadable)} todo section(s) look like items but cannot be read, so whether "
            f"they are required for {RELEASE_CYCLE} is unknown: " + "; ".join(unreadable[:8])
            + (" ..." if len(unreadable) > 8 else ""))

    # 3. the independent closure receipt
    commit, found = blocker_fixpoint_receipt(root)
    if commit is None:
        violations.append(
            f"{RECEIPT_PATH} is missing or states no commit; the blocker-focused fixpoint pass "
            "has not been recorded")
    else:
        stale = receipt_commit_violation(root, commit, head)
        if stale:
            violations.append(stale)
        elif commit != head:
            violations.extend(relabelled_after_receipt(root, commit, head))
    if found is None:
        violations.append(f"{RECEIPT_PATH} does not state how many new release-blocking "
                          "problems the closure pass found")
    elif found != 0:
        violations.append(
            f"the closure pass found {found} new release-blocking problem(s); the fixpoint is "
            "zero NEW BLOCKERS, not zero new observations")
    return violations


def main() -> None:
    log.info("=== STEP 0a: Checking release readiness (AGENTS.md section 11, condition 3) ===")
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        head = None
    stack_violations = check_release_readiness(head=head)
    if stack_violations:
        for violation in stack_violations:
            log.error(violation)
        log.error(
            "A release requires: an empty problem stack; zero todo items still required for "
            "this cycle; and a blocker-focused closure receipt reporting zero new blockers, "
            "recorded at HEAD or at an ancestor that differs from HEAD only in the receipt and "
            "%s, with no item it held open relabelled since. Work deferred to %s, and %s "
            "items, stay in the todo stack.",
            TODO_PATH, NEXT_CYCLE, RELEASE_STEP_VALUE)
        sys.exit(1)
    releases = [r for _, _, r in todo_release_fields()]
    log.info(
        "PASS: the problem stack is empty and no required item remains; %d todo item(s) are "
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
        else:
            log.error(
                "A tag must name a commit whose pipeline ran and passed, leg by leg. An "
                "aggregate 'no failure' is not that: a job with `needs:` reports `skipped` "
                "when its dependency failed, so a red suite can leave the build job showing "
                "no red at all. Push this commit, let CI finish green, then re-run. To tag "
                "without CI evidence anyway, set %s=1 -- deliberately, and knowing it is "
                "recorded here as unverified.", SKIP_CI_ENV)
            sys.exit(1)

    log.info("=== STEP 1: Running full test suite ===")
    # Parallel, because the serial run took over twenty minutes; the ten slowest tests and the
    # wall time are printed so a cost that grows is seen at the release that grew it.
    started = time.monotonic()
    run_cmd([sys.executable, "-m", "pytest", "-q", "-n", "auto", "--durations=10",
             "-p", "no:cacheprovider", "tests/"])
    log.info("Suite wall time: %.0f s", time.monotonic() - started)

    log.info("=== STEP 2: Running harness pre-flight verification gate ===")
    run_cmd([sys.executable, str(REPO_ROOT / "scripts" / "harness_gate.py")])

    log.info("=== STEP 2a: Recorded mutation gaps still hold at HEAD ===")
    gaps_hold, gaps_report = check_known_gaps_hold()
    log.info(gaps_report)
    if not gaps_hold:
        log.error("A recorded mutation gap no longer matches the measurement; update KNOWN_GAPS.")
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
        smoke_script = staging_dir / "smoke_test.py"
        smoke_script.write_text(f"EXPECTED_VERSION = {jnwb_source_version()!r}\n" + """
import sys
import pathlib
import numpy as np
import pandas as pd

cwd = pathlib.Path.cwd()
assert 'jnwb' not in cwd.name, f'CWD must be outside repository, got {cwd}'

# 1. Verify omission is absent
try:
    import omission
    raise RuntimeError('FAIL: omission is unexpectedly importable!')
except ModuleNotFoundError:
    print('PASS: omission is strictly absent and unimportable.')

# 2. Import jnwb
import jnwb
print(f'PASS: import jnwb successful from {jnwb.__file__}')
print(f'      jnwb.__version__ = {jnwb.__version__}')
assert jnwb.__version__ == EXPECTED_VERSION, (
    f'Installed wheel reports {jnwb.__version__}, source declares {EXPECTED_VERSION}')
pkg = pathlib.Path(jnwb.__file__).resolve()
assert 'site-packages' in str(pkg) or 'dist-packages' in str(pkg), f'expected installed location, got {pkg}'
out_dir = jnwb.paths.outputs_dir()
assert 'site-packages' not in str(out_dir) and 'dist-packages' not in str(out_dir)

# 3. Test all exported symbols in __all__. The wheel is installed without extras, so an
# optional submodule must name its extra rather than resolve; `hasattr` sees only
# AttributeError, and the ImportError it raises instead would fail this step every time.
from jnwb._lazy_exports import OPTIONAL_SUBMODULES
missing = [s for s in jnwb.__all__ if s not in OPTIONAL_SUBMODULES and not hasattr(jnwb, s)]
assert not missing, f'Missing symbols: {missing}'
for name, extra in OPTIONAL_SUBMODULES.items():
    try:
        getattr(jnwb, name)
    except ImportError as exc:
        assert f'pip install jnwb[{extra}]' in str(exc), exc
    else:
        raise AssertionError(f'jnwb.{name} resolved without the {extra} extra')
print(f'PASS: All {len(jnwb.__all__)} symbols in jnwb.__all__ resolved or name their extra.')

# 4. Workflows
rng = np.random.default_rng(42)
st = np.sort(rng.uniform(0, 10, 50))
onsets = np.array([1.0, 3.0, 5.0, 7.0])
tb, rate, sem = jnwb.raster_psth(st, onsets, win_ms=(-100, 300), bin_ms=10.0)
smooth = jnwb.causal_exp_smooth(rate, bin_ms=10.0, tau_ms=30.0)
fit = jnwb.fit_exponential_onset(tb, rate, t0_bounds=(0.0, 200.0))
assert 't0' in fit and 'bound_status' in fit
ppc = jnwb.pairwise_phase_consistency(rng.uniform(-np.pi, np.pi, 30))
assert np.isfinite(ppc)
gs = jnwb.gaussian_smooth_rate(rate, bin_ms=10.0, sigma_ms=20.0)
assert gs.shape == rate.shape

# Spectral & TFR
sig = rng.normal(size=1000)
freq_grid = np.linspace(10.0, 50.0, 9)
tfr_res = jnwb.complex_tfr(sig, fs=1000.0, freqs=freq_grid, n_cycles=5.0)
acc = jnwb.TFRAccumulator((1, len(freq_grid), 1000))
acc.add_trial(tfr_res.z[None, :, :], valid=tfr_res.coi_mask[None, :, :])
assert acc.power().shape == (1, 9, 1000)
mt_f, mt_p = jnwb.compute_multitaper_psd(sig, fs=1000.0)
assert len(mt_f) == len(mt_p)
filt = jnwb.bandpass_filter(sig, fs=1000.0, low_cut=8.0, high_cut=40.0)
assert filt.shape == sig.shape
lfp = rng.normal(size=(6, 200))
csd = jnwb.current_source_density_1d(lfp, pitch_um=50.0, conductivity_s_per_m=0.3)
assert csd.shape == (4, 200)

# Statistics, decoding, connectivity, artifact
boot = jnwb.StatisticalAnalysis.bootstrap_ci(sig, n_bootstrap=100, rng=rng)
labels = np.array(['A', 'B', 'A', 'B'])
shuf = jnwb.permute_labels(labels, scheme='global', rng=rng)
X = rng.normal(size=(20, 4))
y = np.repeat([0, 1], 10)
dec = jnwb.nested_cv_linear_svm(X, y, n_splits=2)
g_res = jnwb.granger(rng.normal(size=300), rng.normal(size=300), order=2, n_surrogates=5, seed=0)
corr = jnwb.channel_correlation_matrix(rng.normal(size=(8, 200)))
rep_lfp, frac, diag = jnwb.repair_lfp_trials(rng.normal(size=(8, 4, 100)))
clust = jnwb.cluster_permutation_test(
    rng.normal(size=(8, 20)), rng.normal(size=(8, 20)), n_permutations=20, rng=rng,
)
masks = [c['mask'].tobytes() for c in clust['clusters']]
assert len(masks) == len(set(masks))

# Addressing
elec = pd.DataFrame({'location': ['V1, V2', 'V1, V2'], 'group_name': ['probeA', 'probeA']}, index=[0, 1])
assert jnwb.map_peak_channel_to_area(0, elec) == 'V1'

# 5. NWB discovery, processing LFP, calibration, and epoching (0.1.8 contract)
import pathlib
import tempfile
from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    TASK_TABLE,
    canonical_co_resident_options,
    processing_lfp_options,
    write_synth_nwb,
)
# Top-level acquisition test
nwb_path = pathlib.Path(tempfile.mkdtemp()) / 'wheel_smoke.nwb'
receipt = write_synth_nwb(nwb_path, canonical_co_resident_options())
info = jnwb.inspect(nwb_path)
assert any(t['name'] == TASK_TABLE for t in info['interval_tables'])
onsets = jnwb.event_onsets(nwb_path, table=TASK_TABLE, codes=[CODE_LABEL_A])
assert onsets.size == len(receipt.task_onsets_s[::2])
spikes = jnwb.unit_spike_times(nwb_path, unit_index=0)
lfp, fs_hz = jnwb.acquisition_channel(nwb_path, name='probe_0_lfp', channel=0)
assert spikes.size > 0 and lfp.size > 0 and fs_hz == receipt.fs_hz

# Processing-module LFP discovery and calibrated access
proc_nwb_path = pathlib.Path(tempfile.mkdtemp()) / 'wheel_proc.nwb'
proc_receipt = write_synth_nwb(proc_nwb_path, processing_lfp_options())
proc_info = jnwb.inspect(proc_nwb_path)
assert len(proc_info['processing_continuous']) > 0
assert any(p['neurodata_type'] == 'LFP' for p in proc_info['processing_continuous'])
proc_lfp, proc_fs = jnwb.acquisition_channel(proc_nwb_path, channel=0)
assert proc_lfp.size > 0 and proc_fs == proc_receipt.fs_hz

# epoch_continuous primitive & drop retained indices
epochs, t_axis, retained = jnwb.epoch_continuous(
    proc_lfp,
    onsets=[0.1, 0.5, 999.0],
    win_s=(-0.05, 0.1),
    fs=proc_fs,
    boundary_policy='drop',
    return_indices=True,
)
assert epochs.ndim == 2
assert epochs.shape[0] == 2
assert np.array_equal(retained, [0, 1])
assert len(t_axis) == epochs.shape[1]

# 6. 0.2.1 additions: aperiodic_fit, relative_power, exact stats, stream_npz_array, probe_geometry
f_axis = np.linspace(5.0, 50.0, 46)
psd_toy = 10.0 ** (2.0 - 1.5 * np.log10(f_axis))
ap_res = jnwb.aperiodic_fit(f_axis, psd_toy, freq_range=(5.0, 50.0), mode="fixed")
assert ap_res.accepted is True and np.isclose(ap_res.exponent, 1.5, atol=1e-3)

rp = jnwb.relative_power(psd_toy * 1.5, psd_toy, model="mean_of_ratios", axis=0)
assert np.isclose(rp, 1.5)

obs_m, p_val, p_fl = jnwb.exact_sign_flip([1.0, 2.0, 3.0, 4.0], alternative="greater")
assert np.isclose(p_val, 0.0625) and np.isclose(p_fl, 0.0625)
mwp_fl = jnwb.mann_whitney_p_floor(3, 3, alternative="two-sided")
assert np.isclose(mwp_fl, 0.1)
cp_ci = jnwb.clopper_pearson(5, 10, alpha=0.05)
assert len(cp_ci) == 2

tmp_npz = pathlib.Path(tempfile.mkdtemp()) / 'test_stream.npz'
arr_raw = np.arange(100, dtype=np.float32).reshape(10, 10)
np.savez_compressed(tmp_npz, arr=arr_raw)
streamed = jnwb.stream_npz_array(tmp_npz, 'arr', (slice(0, 5), slice(0, 5)))
assert np.array_equal(streamed, arr_raw[0:5, 0:5])

coords_df = pd.DataFrame({'x': [0, 0, 0, 0], 'y': [0, 0, 0, 0], 'z': [0, 20, 40, 60]})
p_geom = jnwb.probe_geometry(coords_df, units="um", nominal_pitch=20.0, strict_linear=True)
assert p_geom.is_linear is True and p_geom.is_uniform is True

# 7. 0.2.4 additions: wpli, zflip, rdm
# `wpli` returns a dict, so `hasattr` is always False on it; and the debiased key is
# `wpli_debiased_sq`, not `wpli_debiased`. Check the keys and their contracts.
wpli_res = jnwb.wpli(sig[:500], sig[500:], fs=1000.0, freq_range=(10.0, 40.0))
assert set(wpli_res) == {'wpli', 'wpli_debiased_sq', 'freqs', 'wpli_spectrum', 'n_segments', 'n_freqs'}
assert 0.0 <= wpli_res['wpli'] <= 1.0, wpli_res['wpli']
assert -1.0 <= wpli_res['wpli_debiased_sq'] <= 1.0, wpli_res['wpli_debiased_sq']
assert wpli_res['freqs'].shape == wpli_res['wpli_spectrum'].shape
assert 1 <= wpli_res['n_freqs'] <= wpli_res['freqs'].size
assert wpli_res['n_segments'] >= 2

zflip_res = jnwb.zflip(rng.normal(size=(8, 1000)), fs=1000.0, pitch_um=20.0, freq_range=(15.0, 35.0), seed=42)
assert isinstance(zflip_res.delay_identifiable, bool) and isinstance(zflip_res.accepted, bool)
# White noise carries no travelling wave: the estimator must decline it and say why.
assert zflip_res.accepted is False and zflip_res.rejection_reason

# `rdm` returns a CONDENSED vector by default; the square form is condensed=False.
condensed = jnwb.rdm(rng.normal(size=(10, 20)), metric="correlation")
assert condensed.shape == (45,), condensed.shape
square = jnwb.rdm(rng.normal(size=(10, 20)), metric="correlation", condensed=False)
assert square.shape == (10, 10), square.shape
assert np.allclose(square, square.T) and np.allclose(np.diag(square), 0.0)
rho_rdm, p_rdm = jnwb.rdm_similarity(condensed, condensed, metric="spearman")
assert np.isclose(rho_rdm, 1.0)

# 8. Viz
jnwb.setup_vector_graphics()

print('ALL SMOKE VERIFICATIONS PASSED IN ISOLATED WHEEL ENVIRONMENT.')
""", encoding="utf-8")

        res = subprocess.run([venv_python, str(smoke_script)], cwd=str(staging_dir), capture_output=True, text=True)
        if res.returncode != 0:
            log.error(f"Smoke test failed in isolated environment:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
            sys.exit(res.returncode)
        log.info(res.stdout.strip())

        log.info("=== STEP 8: Executing tutorials against the installed wheel ===")
        tutorials = sorted((REPO_ROOT / "examples" / "tutorials").glob("[0-9][0-9]_*.py"))
        if not tutorials:
            log.error("No numbered tutorials found; 0.2.4-03 cannot be verified.")
            sys.exit(1)
        # PYTHONPATH is stripped and the CWD is the staging directory, so a tutorial that
        # only runs from the source tree fails here instead of passing by checkout proximity.
        tutorial_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
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

    log.info("=============================================================")
    log.info("=== RELEASE GATE VERIFIED: DISTRIBUTABLE PACKAGE READY ===")
    log.info("=============================================================")


if __name__ == "__main__":
    main()
