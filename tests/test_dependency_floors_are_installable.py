"""A declared floor must be installable on the interpreter the package declares.

Seven core floors and two extras were copied from an older support window and never
re-derived after `requires-python` moved to `>=3.12`. `scipy>=1.8.0` was the clearest case:
that release declares `requires_python '>=3.8,<3.11'`, which contradicts the package's own
interpreter floor outright, and six others ship no wheel any 3.12 can use. Nothing noticed,
because every resolution in use is years above the floor -- the floors were never the
versions anyone installed.

The gate step this exercises reads the index. These tests do not: they drive the pure
functions with stubbed metadata so the answer is the same offline, and they derive the
interpreter tag from `pyproject.toml` rather than writing `cp312` down, because a check that
hardcodes the support window keeps passing after the window moves.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.release_gate import (  # noqa: E402
    SKIP_INDEX_ENV,
    check_floor_is_installable,
    declared_dependency_floors,
    interpreter_floor_tag,
    lowest_release_satisfying,
)


#: The oldest final release of each package carrying a wheel usable on cp312, read from the
#: PyPI JSON API on 2026-09-18. This is a cache, not the authority: the release gate re-derives
#: it from the index at build time and `test_the_recorded_table_still_matches_the_gate` holds
#: the two together. It exists so that lowering a floor fails in the suite rather than waiting
#: for a release, which is how these floors drifted three minor versions in the first place.
FIRST_CP312_RELEASE = {
    "numpy": "1.26.0",
    "scipy": "1.11.2",
    "pandas": "2.1.1",
    "h5py": "3.10.0",
    "matplotlib": "3.7.3",
    "scikit-learn": "1.3.1",
    "statsmodels": "0.14.0",
    "torch": "2.2.0",
    "pyyaml": "6.0.1",
}


def _wheel(name: str, version: str, tag: str, requires_python: str = "") -> dict:
    return {
        "filename": f"{name}-{version}-{tag}-none-any.whl",
        "requires_python": requires_python,
    }


def _payload(releases: dict) -> dict:
    return {"releases": releases}


def test_every_declared_floor_is_parsed_from_pyproject() -> None:
    floors = declared_dependency_floors()
    assert len(floors) >= 15, f"only {len(floors)} floors parsed; the reader stopped matching"
    names = {name for _, name, _ in floors}
    for required in ["numpy", "scipy", "pandas", "h5py", "matplotlib", "scikit-learn"]:
        assert required in names, f"{required} has no floor, or the parser missed it"


def test_the_interpreter_tag_follows_requires_python() -> None:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        declared = tomllib.load(fh)["project"]["requires-python"]
    major, minor = re.search(r">=\s*(\d+)\.(\d+)", declared).groups()
    assert interpreter_floor_tag() == f"cp{major}{minor}"
    assert interpreter_floor_tag(">=3.14") == "cp314", "the tag is hardcoded, not derived"


def test_a_floor_whose_release_has_no_wheel_for_the_interpreter_is_refused() -> None:
    payload = _payload({"1.22.0": [_wheel("numpy", "1.22.0", "cp310")]})
    problems = check_floor_is_installable("numpy", "1.22.0", payload, "cp312")
    assert problems and "no cp312 or pure-python wheel" in problems[0]
    assert "cp310" in problems[0], "the refusal does not say what the release actually ships"


def test_a_floor_whose_release_excludes_the_interpreter_is_refused() -> None:
    payload = _payload({"1.8.0": [_wheel("scipy", "1.8.0", "cp310", ">=3.8,<3.11")]})
    problems = check_floor_is_installable("scipy", "1.8.0", payload, "cp312")
    assert problems and "excludes the cp312" in problems[0]


def test_a_floor_with_a_matching_wheel_passes() -> None:
    payload = _payload({"1.26.0": [_wheel("numpy", "1.26.0", "cp312")]})
    assert check_floor_is_installable("numpy", "1.26.0", payload, "cp312") == []


def test_a_pure_python_wheel_satisfies_any_interpreter() -> None:
    payload = _payload({"2.0.0": [_wheel("pynwb", "2.0.0", "py3")]})
    assert check_floor_is_installable("pynwb", "2.0.0", payload, "cp312") == []


def test_the_floor_need_not_be_a_version_that_exists() -> None:
    """`>=` is a lower bound. `pytest-xdist>=3.0` is satisfied by 3.0.2, and there is no 3.0.

    An earlier draft asked the index for the literal floor string and reported a 404 as a
    missing release, which is a fact about URL spelling rather than about installability.
    """
    payload = _payload({
        "3.0.2": [_wheel("pytest-xdist", "3.0.2", "py3")],
        "2.5.0": [_wheel("pytest-xdist", "2.5.0", "py3")],
    })
    assert lowest_release_satisfying(payload, "3.0") == "3.0.2"
    assert check_floor_is_installable("pytest-xdist", "3.0", payload, "cp312") == []


def test_the_oldest_allowed_release_is_the_one_checked() -> None:
    """A newer release with a wheel does not excuse the oldest one the pin permits."""
    payload = _payload({
        "1.22.0": [_wheel("numpy", "1.22.0", "cp310")],
        "1.26.0": [_wheel("numpy", "1.26.0", "cp312")],
    })
    problems = check_floor_is_installable("numpy", "1.22.0", payload, "cp312")
    assert problems, "the check passed on a newer release than the floor allows"


def test_a_floor_above_everything_published_is_refused() -> None:
    payload = _payload({"1.0.0": [_wheel("thing", "1.0.0", "py3")]})
    problems = check_floor_is_installable("thing", "99.0", payload, "cp312")
    assert problems and "no release satisfying" in problems[0]


def test_prereleases_do_not_satisfy_a_floor() -> None:
    payload = _payload({
        "2.0.0rc1": [_wheel("thing", "2.0.0rc1", "cp312")],
        "2.0.0": [_wheel("thing", "2.0.0", "cp312")],
    })
    assert lowest_release_satisfying(payload, "2.0") == "2.0.0"


def test_an_unreachable_index_is_unverified_not_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SKIP_INDEX_ENV, raising=False)
    problems = check_floor_is_installable("numpy", "1.26.0", None, "cp312")
    assert problems and "unverified" in problems[0]
    monkeypatch.setenv(SKIP_INDEX_ENV, "1")
    assert check_floor_is_installable("numpy", "1.26.0", None, "cp312") == []


def test_no_declared_floor_predates_support_for_the_declared_interpreter() -> None:
    """The regression guard: lowering a floor back under the support window fails here.

    Only packages in the recorded table are checked. A package not in it is not exempt -- the
    release gate checks every floor against the index -- it is merely not cached.
    """
    from packaging.version import Version

    floors = {name: floor for _, name, floor in declared_dependency_floors()}
    checked = 0
    problems = []
    for name, first in FIRST_CP312_RELEASE.items():
        if name not in floors:
            continue
        checked += 1
        if Version(floors[name]) < Version(first):
            problems.append(
                f"{name}>={floors[name]} predates {first}, the oldest release installable on "
                f"{interpreter_floor_tag()}"
            )
    assert checked >= 8, f"only {checked} recorded floors were found in pyproject.toml"
    assert not problems, problems


def test_the_gate_actually_runs_the_floor_check_before_it_builds_anything() -> None:
    """A check that exists and is never called is the defect it was written to prevent."""
    import ast

    tree = ast.parse((ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8"))
    main = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"), None
    )
    assert main is not None, "release_gate.py has no main()"

    calls = [
        node for node in ast.walk(main)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    names = [node.func.id for node in calls]
    for required in ["check_floor_is_installable", "declared_dependency_floors",
                     "interpreter_floor_tag", "package_releases"]:
        assert required in names, f"main() never calls {required}"

    checked_at = min(
        node.lineno for node in calls if node.func.id == "check_floor_is_installable"
    )
    built_at = [
        node.lineno for node in ast.walk(main)
        if isinstance(node, ast.Constant) and node.value == "build"
    ]
    assert built_at, "main() no longer builds a distribution; this test is stale"
    assert checked_at < min(built_at), "the floors are checked after the build"


def test_the_scipy_floor_covers_the_scipy_api_this_package_calls() -> None:
    """`scipy.stats.false_discovery_control` arrived in 1.11. The floor said 1.8.0.

    Derived from the source rather than asserted as a constant: if the call goes away, so
    does the requirement, and if another module starts calling it the floor still has to hold.
    """
    callers = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "jnwb").rglob("*.py")
        if "false_discovery_control" in path.read_text(encoding="utf-8")
    ]
    if not callers:
        pytest.skip("nothing calls false_discovery_control any more")

    floors = {name: floor for _, name, floor in declared_dependency_floors()}
    from packaging.version import Version

    assert Version(floors["scipy"]) >= Version("1.11"), (
        f"{callers} call scipy.stats.false_discovery_control, added in SciPy 1.11, against a "
        f"declared floor of {floors['scipy']}"
    )
