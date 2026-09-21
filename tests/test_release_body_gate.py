"""The GitHub Release body, judged against package metadata.

Every surface stating the supported-Python window was gated except this one: before 06-11,
``grep -rniE "release note|gh release|release body" scripts/ tests/`` returned zero. The
v0.2.5 body shipped "Python 3.10 through 3.14" against ``requires-python = ">=3.12"`` and
was corrected by hand, because nothing read it.

Two properties matter more than the individual rules and are tested first-class here:

* The expected values are **derived**, never written down. Every rule is driven over a
  constructed tree whose floor, ceiling, name and version differ from this repository's, so
  a check that secretly hardcoded ``3.12`` would fail rather than agree by coincidence.
* "Could not check" is **not** "checked and clean". The live half must skip visibly when no
  token, no ``gh`` or no published release is available, and a skip must be unable to
  masquerade as a pass.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import subprocess
import textwrap

import pytest

from scripts.release_gate import (
    BODY_CHECKED,
    BODY_SKIPPED,
    LiveBodyOutcome,
    ReleaseMetadata,
    check_live_release_body,
    check_release_body_claims,
    release_metadata,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: A metadata set deliberately unlike this repository's: a different distribution name, a
#: different version and a support window sharing no endpoint with jnwb's 3.12-3.14. A rule
#: that hardcodes a real value cannot pass against this.
OTHER = ReleaseMetadata(
    name="widget-lib",
    version="7.1.0",
    python_floor="3.9",
    python_ceiling="3.11",
    python_supported=("3.9", "3.10", "3.11"),
)

_GOOD_OTHER_BODY = (
    "widget-lib 7.1.0 fixes things.\n\n"
    "Install: `pip install widget-lib==7.1.0`. Python 3.9 through 3.11.\n"
)


def _pyproject(name: str, floor: str, supported) -> str:
    classifiers = "\n".join(
        f'    "Programming Language :: Python :: {v}",' for v in supported
    )
    return (
        "[project]\n"
        f'name = "{name}"\n'
        f'requires-python = ">={floor}"\n'
        "classifiers = [\n"
        '    "Programming Language :: Python :: 3",\n'
        f"{classifiers}\n"
        "]\n"
    )


def _tree(tmp_path: pathlib.Path, name: str, version: str, floor: str, supported) -> pathlib.Path:
    (tmp_path / "pyproject.toml").write_text(
        _pyproject(name, floor, supported), encoding="utf-8"
    )
    (tmp_path / "jnwb").mkdir(exist_ok=True)
    (tmp_path / "jnwb" / "__init__.py").write_text(
        f"__version__ = '{version}'\n", encoding="utf-8"
    )
    return tmp_path


class TestMetadataIsDerived:
    """The expected values come from the tree, not from this file or from the checker."""

    def test_live_metadata_matches_this_repository(self) -> None:
        md = release_metadata(REPO_ROOT)
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert f'requires-python = ">={md.python_floor}"' in pyproject
        assert f'"Programming Language :: Python :: {md.python_ceiling}"' in pyproject
        assert f"__version__ = '{md.version}'" in (
            REPO_ROOT / "jnwb" / "__init__.py"
        ).read_text(encoding="utf-8")

    def test_metadata_follows_a_constructed_tree(self, tmp_path: pathlib.Path) -> None:
        """Different tree, different answers. This is what "derived" means."""
        md = release_metadata(_tree(tmp_path, "widget-lib", "7.1.0", "3.9", ["3.9", "3.10", "3.11"]))
        assert md == OTHER

    def test_ceiling_is_the_highest_classifier_not_the_last_listed(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Sorted numerically: '3.9' must not outrank '3.10' by string comparison."""
        md = release_metadata(_tree(tmp_path, "w", "1.0", "3.9", ["3.10", "3.9", "3.11"]))
        assert md.python_ceiling == "3.11"

    def test_a_tree_with_no_versioned_classifier_raises(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "w"\nrequires-python = ">=3.9"\nclassifiers = []\n',
            encoding="utf-8",
        )
        (tmp_path / "jnwb").mkdir()
        (tmp_path / "jnwb" / "__init__.py").write_text("__version__ = '1.0'\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="no versioned Python classifier"):
            release_metadata(tmp_path)

    def test_the_checker_hardcodes_no_python_version(self) -> None:
        """A literal '3.12' in the rules would be the replica the item exists to remove.

        The docstring is dropped through the AST, not by string subtraction:
        ``inspect.getdoc`` returns *cleaned* text, which never matches the indented source
        it came from, so ``source.replace(getdoc(fn), "")`` removes nothing and the scan
        silently inspects the prose it meant to exclude.
        """
        import re

        for fn in (release_metadata, check_release_body_claims):
            tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
            func = tree.body[0]
            assert isinstance(func, ast.FunctionDef)
            statements = func.body
            if (
                statements
                and isinstance(statements[0], ast.Expr)
                and isinstance(statements[0].value, ast.Constant)
                and isinstance(statements[0].value.value, str)
            ):
                statements = statements[1:]
            assert statements, f"{fn.__name__} has no body outside its docstring"
            code = "\n".join(ast.unparse(node) for node in statements)
            assert "3.1" not in code.replace("\\d", ""), (
                f"{fn.__name__} contains a literal Python version; it must derive it:\n{code}"
            )


#: The trailer exactly as published at v0.2.5, after its manual correction, and the metadata
#: v0.2.5 actually declared. Both are frozen literals, written independently of each other.
#: Building the body out of the metadata it is then compared against -- which is what this
#: test did first -- agrees by construction and proves only that the regexes round-trip. That
#: is the shape P-150 records on the release path, where the tutorials `release_gate.py`
#: executes against the installed wheel read only NWB files they wrote themselves.
_SHIPPED_V025_TRAILER = (
    "0.2.5 is a correctness and harness release.\n\n---\n\n"
    "Install: `pip install jnwb==0.2.5`. Python 3.12 through 3.14. No API removals beyond\n"
    "those listed under Removed and Deprecated in the changelog.\n"
)

_V025_METADATA = ReleaseMetadata(
    name="jnwb",
    version="0.2.5",
    python_floor="3.12",
    python_ceiling="3.14",
    python_supported=("3.12", "3.13", "3.14"),
)


class TestTheShippedBodyAndItsHistoricalDefect:
    def test_the_body_that_shipped_at_v025_is_accepted(self) -> None:
        """A real published body against the metadata that release really declared."""
        assert check_release_body_claims(
            _SHIPPED_V025_TRAILER, _V025_METADATA, tag_name="v0.2.5", is_prerelease=False
        ) == []

    def test_that_acceptance_is_not_true_by_construction(self) -> None:
        """The frozen body and the frozen metadata are independent: move one, it fails.

        Without this, a body assembled from its own metadata would satisfy the test above
        no matter what either said.
        """
        assert check_release_body_claims(
            _SHIPPED_V025_TRAILER, _V025_METADATA._replace(python_floor="3.11")
        )
        assert check_release_body_claims(
            _SHIPPED_V025_TRAILER, _V025_METADATA._replace(version="0.2.6")
        )

    def test_the_historical_defect_is_rejected(self) -> None:
        """"Python 3.10 through 3.14" against a >=3.12 floor: the body that shipped."""
        md = release_metadata(REPO_ROOT)
        body = (
            f"Install: `pip install {md.name}=={md.version}`. Python 3.10 through "
            f"{md.python_ceiling}.\n"
        )
        violations = check_release_body_claims(body, md)
        assert any("3.10 floor" in v for v in violations), violations

    def test_the_same_defect_shape_is_rejected_on_a_constructed_tree(self) -> None:
        """Not a fact about 3.10: any floor metadata contradicts is rejected."""
        body = _GOOD_OTHER_BODY.replace("Python 3.9 through", "Python 3.7 through")
        violations = check_release_body_claims(body, OTHER)
        assert any("3.7 floor" in v and "3.9" in v for v in violations), violations


class TestPythonSupportClaims:
    def test_a_correct_range_is_accepted(self) -> None:
        assert check_release_body_claims(_GOOD_OTHER_BODY, OTHER) == []

    def test_a_wrong_ceiling_is_rejected(self) -> None:
        body = _GOOD_OTHER_BODY.replace("through 3.11", "through 3.13")
        violations = check_release_body_claims(body, OTHER)
        assert any("3.13 ceiling" in v for v in violations), violations

    @pytest.mark.parametrize("form", ["Python 3.9+", "Python 3.9 or newer", "Python >=3.9"])
    def test_open_ended_floor_forms_are_accepted(self, form: str) -> None:
        body = _GOOD_OTHER_BODY.replace("Python 3.9 through 3.11", form)
        assert check_release_body_claims(body, OTHER) == [], form

    @pytest.mark.parametrize("form", ["Python 3.8+", "Python 3.8 or newer"])
    def test_open_ended_forms_with_a_wrong_floor_are_rejected(self, form: str) -> None:
        body = _GOOD_OTHER_BODY.replace("Python 3.9 through 3.11", form)
        assert any("3.8 floor" in v for v in check_release_body_claims(body, OTHER)), form

    def test_a_bare_mention_of_an_unsupported_version_is_rejected(self) -> None:
        body = _GOOD_OTHER_BODY + "\n- Dropped Python 3.6.\n"
        violations = check_release_body_claims(body, OTHER)
        assert any("names Python 3.6" in v for v in violations), violations

    def test_a_bare_mention_of_a_supported_version_is_accepted(self) -> None:
        body = _GOOD_OTHER_BODY + "\n- Fixed a Python 3.10 crash.\n"
        assert check_release_body_claims(body, OTHER) == []


class TestInstallCommandClaims:
    def test_a_wrong_version_is_rejected(self) -> None:
        body = _GOOD_OTHER_BODY.replace("==7.1.0", "==7.0.9")
        violations = check_release_body_claims(body, OTHER)
        assert any("installs version 7.0.9" in v for v in violations), violations

    def test_a_wrong_distribution_name_is_rejected(self) -> None:
        body = _GOOD_OTHER_BODY.replace("widget-lib==", "widget-core==")
        violations = check_release_body_claims(body, OTHER)
        assert any("widget-core" in v for v in violations), violations

    def test_name_comparison_is_pep503_normalised(self) -> None:
        body = _GOOD_OTHER_BODY.replace("pip install widget-lib==", "pip install Widget_Lib==")
        assert check_release_body_claims(body, OTHER) == []

    def test_an_unpinned_install_is_rejected(self) -> None:
        body = _GOOD_OTHER_BODY.replace("widget-lib==7.1.0", "widget-lib")
        violations = check_release_body_claims(body, OTHER)
        assert any("pins no version" in v for v in violations), violations

    def test_every_install_command_is_checked_not_only_the_first(self) -> None:
        body = _GOOD_OTHER_BODY + "\nOr: `pip install widget-lib==6.0.0`\n"
        violations = check_release_body_claims(body, OTHER)
        assert any("6.0.0" in v for v in violations), violations


class TestAbsenceIsNotAgreement:
    """A body with nothing to compare must fail, not pass by vacuity."""

    @pytest.mark.parametrize("body", ["", "   \n\n", "We shipped it. Enjoy!"])
    def test_a_body_stating_no_claims_is_rejected(self, body: str) -> None:
        violations = check_release_body_claims(body, OTHER)
        assert any("no `pip install` command" in v for v in violations), violations
        assert any("no Python support range" in v for v in violations), violations

    def test_a_body_with_only_an_install_command_is_rejected(self) -> None:
        violations = check_release_body_claims("`pip install widget-lib==7.1.0`", OTHER)
        assert any("no Python support range" in v for v in violations), violations

    def test_a_body_with_only_a_support_range_is_rejected(self) -> None:
        violations = check_release_body_claims("Python 3.9 through 3.11.", OTHER)
        assert any("no `pip install` command" in v for v in violations), violations

    def test_a_bare_mention_alone_does_not_satisfy_the_range_requirement(self) -> None:
        """"Python 3.9" is not a support window, and must not be read as one."""
        body = "`pip install widget-lib==7.1.0`. Built on Python 3.9."
        violations = check_release_body_claims(body, OTHER)
        assert any("no Python support range" in v for v in violations), violations


class TestReleaseStatus:
    def test_a_tag_naming_another_version_is_rejected(self) -> None:
        violations = check_release_body_claims(_GOOD_OTHER_BODY, OTHER, tag_name="v7.0.9")
        assert any("does not name the declared version" in v for v in violations), violations

    @pytest.mark.parametrize("tag", ["v7.1.0", "7.1.0"])
    def test_a_matching_tag_is_accepted_with_or_without_the_v(self, tag: str) -> None:
        assert check_release_body_claims(_GOOD_OTHER_BODY, OTHER, tag_name=tag) == []

    def test_a_final_version_marked_prerelease_is_rejected(self) -> None:
        violations = check_release_body_claims(_GOOD_OTHER_BODY, OTHER, is_prerelease=True)
        assert any("prerelease=True" in v for v in violations), violations

    def test_a_prerelease_version_marked_final_is_rejected(self) -> None:
        md = OTHER._replace(version="7.1.0rc1")
        body = _GOOD_OTHER_BODY.replace("7.1.0", "7.1.0rc1")
        violations = check_release_body_claims(body, md, is_prerelease=False)
        assert any("prerelease=False" in v for v in violations), violations

    def test_a_prerelease_version_marked_prerelease_is_accepted(self) -> None:
        md = OTHER._replace(version="7.1.0rc1")
        body = _GOOD_OTHER_BODY.replace("7.1.0", "7.1.0rc1")
        assert check_release_body_claims(body, md, is_prerelease=True) == []

    def test_status_is_unchecked_when_not_supplied(self) -> None:
        """Offline callers pass no status; that must not invent a verdict."""
        assert check_release_body_claims(_GOOD_OTHER_BODY, OTHER) == []


class TestTheOfflineHalfIsOffline:
    def test_the_body_check_makes_no_network_or_subprocess_call(self, monkeypatch) -> None:
        """The no-token half of the acceptance must hold unconditionally."""
        import urllib.request

        def explode(*args, **kwargs):
            raise AssertionError("check_release_body_claims reached the network")

        monkeypatch.setattr(urllib.request, "urlopen", explode)
        monkeypatch.setattr(subprocess, "run", explode)
        assert check_release_body_claims(_GOOD_OTHER_BODY, OTHER) == []
        assert check_release_body_claims("", OTHER)


def _fake_gh(stdout: str = "", returncode: int = 0, stderr: str = "", raises=None):
    def run(cmd, **kwargs):
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    return run


class TestSkippedIsNotPassed:
    """The dominant defect shape in this repository: a check that cannot tell the two apart."""

    def test_the_two_statuses_are_distinct_values(self) -> None:
        assert BODY_CHECKED != BODY_SKIPPED

    @pytest.mark.parametrize(
        "runner,expect",
        [
            (_fake_gh(raises=FileNotFoundError("gh")), "not on PATH"),
            (_fake_gh(returncode=1, stderr="release not found"), "release not found"),
            (_fake_gh(returncode=4, stderr="gh auth login required"), "gh auth login"),
            (_fake_gh(stdout="not json"), "non-JSON"),
            (_fake_gh(raises=subprocess.TimeoutExpired("gh", 30)), "failed"),
        ],
    )
    def test_every_unreachable_path_skips_visibly(self, runner, expect: str) -> None:
        outcome = check_live_release_body(OTHER, runner=runner)
        assert outcome.status == BODY_SKIPPED
        assert expect in outcome.detail
        # A skip carries no verdict. If it carried violations the caller would fail the
        # gate on a release it never read; if the caller ignored the status it would pass.
        assert outcome.violations == []

    def test_a_skip_is_not_reported_as_a_pass_by_the_gate(self) -> None:
        """main() must branch on status, not on emptiness of violations."""
        source = (REPO_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        main = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"
        )
        segment = ast.get_source_segment(source, main) or ""
        assert "BODY_SKIPPED" in segment, "main() does not distinguish a skipped body check"
        assert "SKIP:" in segment, "main() does not log a skip as a skip"

    def test_a_reachable_release_is_actually_checked(self) -> None:
        payload = (
            '{"body": "Install: `pip install widget-lib==7.1.0`. Python 3.9 through 3.11.",'
            ' "tagName": "v7.1.0", "isDraft": false, "isPrerelease": false}'
        )
        outcome = check_live_release_body(OTHER, runner=_fake_gh(stdout=payload))
        assert outcome.status == BODY_CHECKED
        assert outcome.violations == []

    def test_a_reachable_release_with_a_bad_body_fails_rather_than_skips(self) -> None:
        payload = (
            '{"body": "Install: `pip install widget-lib==7.0.1`. Python 3.7 through 3.11.",'
            ' "tagName": "v7.1.0", "isDraft": false, "isPrerelease": false}'
        )
        outcome = check_live_release_body(OTHER, runner=_fake_gh(stdout=payload))
        assert outcome.status == BODY_CHECKED
        assert any("7.0.1" in v for v in outcome.violations), outcome.violations
        assert any("3.7 floor" in v for v in outcome.violations), outcome.violations

    def test_an_empty_live_body_fails_rather_than_passes(self) -> None:
        payload = '{"body": "", "tagName": "v7.1.0", "isDraft": false, "isPrerelease": false}'
        outcome = check_live_release_body(OTHER, runner=_fake_gh(stdout=payload))
        assert outcome.status == BODY_CHECKED
        assert outcome.violations

    def test_a_missing_body_key_is_treated_as_empty_not_as_clean(self) -> None:
        outcome = check_live_release_body(OTHER, runner=_fake_gh(stdout='{"tagName": "v7.1.0"}'))
        assert outcome.status == BODY_CHECKED
        assert outcome.violations

    def test_the_outcome_type_is_the_tri_state_not_a_bool(self) -> None:
        outcome = check_live_release_body(OTHER, runner=_fake_gh(raises=FileNotFoundError("gh")))
        assert isinstance(outcome, LiveBodyOutcome)
        assert set(LiveBodyOutcome._fields) == {"status", "detail", "violations"}


class TestTheGateRunsIt:
    """A checker nothing calls is the defect it was written to prevent."""

    def test_main_invokes_the_live_check(self) -> None:
        source = (REPO_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        main = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"
        )
        called = {
            node.func.id
            for node in ast.walk(main)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "check_live_release_body" in called
        assert "release_metadata" in called

    def test_main_exits_on_a_body_violation(self) -> None:
        source = (REPO_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        main = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"
        )
        segment = ast.get_source_segment(source, main) or ""
        step = segment.partition("STEP 0d")[2].partition("STEP 1")[0]
        assert "sys.exit(1)" in step, "STEP 0d reports body violations without failing"

    def test_the_step_is_documented_in_the_module_pipeline(self) -> None:
        import scripts.release_gate as rg

        assert "0d." in (rg.__doc__ or ""), "the pipeline docstring omits the new step"


class TestAgainstTheLiveRelease:
    """The second half of the acceptance: the live body, when a token is present."""

    def test_the_live_release_body_agrees_with_metadata_or_skips(self) -> None:
        md = release_metadata(REPO_ROOT)
        outcome = check_live_release_body(md)
        if outcome.status == BODY_SKIPPED:
            pytest.skip(f"live release not reachable: {outcome.detail}")
        assert outcome.violations == [], outcome.violations
