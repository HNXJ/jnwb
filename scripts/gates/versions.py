"""Version gates: package and metadata agreement, and the Python support floor."""
from __future__ import annotations

import itertools
import re
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]


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

# --- Python support policy -------------------------------------------------
# Corrected 2026-09-09. The earlier "3.12 only" rule was a decision scoped to one
# specific run that got generalized into repository-wide policy; it shipped an upper
# pin in 0.1.1 and made that release uninstallable. Declared support is a floor with
# no ceiling; CI tests every declared version. Testing only the floor and the head is
# what let 0.2.5 ship a 3.13 classifier no leg of the matrix ever ran.
PYTHON_FLOOR = "3.12"
PYTHON_SUPPORTED = ("3.12", "3.13", "3.14", "3.15")   # what the classifiers must claim
PYTHON_CI_REQUIRED = ("3.12", "3.13", "3.14", "3.15")  # every claimed version must be tested


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
