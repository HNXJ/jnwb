"""scripts/push_guard.py denies a plain `git push` in a jnwb checkout, whatever its folder, and lets jnwb_push.sh through."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "push_guard.py"


def make_checkout(root: Path, jnwb: bool = True) -> Path:
    """A git checkout at root; with jnwb, it carries the content markers the guard reads."""
    (root / ".git").mkdir(parents=True)
    if jnwb:
        (root / "jnwb").mkdir()
        (root / "jnwb" / "__init__.py").write_text("", encoding="utf-8")
        (root / "scripts").mkdir()
        (root / "scripts" / "jnwb_push.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    return root


def run_guard(raw: str) -> str:
    out = subprocess.run([sys.executable, str(GUARD)], input=raw.encode("utf-8"), capture_output=True,
                         timeout=30, check=True).stdout.decode("utf-8")
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else "allow"


def decide(command: str, cwd: Path | str) -> str:
    return run_guard(json.dumps({"tool_name": "Bash", "tool_input": {"command": command},
                                 "cwd": Path(cwd).as_posix()}))


def test_a_plain_push_in_a_jnwb_checkout_is_denied_under_any_name(tmp_path):
    clone = make_checkout(tmp_path / "_temp_integ")
    assert decide("git push origin dev", clone) == "deny"
    assert decide(f'git -C "{clone.as_posix()}" push origin dev', tmp_path) == "deny"
    assert decide("git push origin dev", clone / "jnwb") == "deny"


@pytest.mark.skipif(os.name != "nt", reason="Git Bash drive paths exist only on Windows")
def test_a_git_bash_drive_path_names_the_same_checkout(tmp_path):
    clone = make_checkout(tmp_path / "_temp_msys")
    posix = clone.as_posix()
    msys = "/" + posix[0].lower() + posix[2:]
    assert decide(f"cd {msys} && git push origin dev", tmp_path) == "deny"
    assert decide(f"git -C {msys} push origin dev", tmp_path) == "deny"


def test_a_folder_named_jnwb_without_jnwb_content_is_not_denied(tmp_path):
    plain = make_checkout(tmp_path / "jnwb", jnwb=False)
    assert decide("git push origin dev", plain) == "allow"


def test_a_chain_with_the_wrapper_is_denied_when_another_segment_pushes(tmp_path):
    clone = make_checkout(tmp_path / "_temp_chain")
    other = make_checkout(tmp_path / "other", jnwb=False)
    wrapper = f'bash "{clone.as_posix()}/scripts/jnwb_push.sh" "{clone.as_posix()}" dev </dev/null'
    assert decide(wrapper, clone) == "allow"
    for sep in ("; ", " && ", " || ", " | ", "\n"):
        assert decide(wrapper + sep + "git push origin dev", clone) == "deny", repr(sep)
    assert decide(wrapper + "; git push origin _temp_a", clone) == "allow"
    assert decide(f'cd "{clone.as_posix()}" && git push origin dev', tmp_path) == "deny"
    assert decide(f'cd "{other.as_posix()}" && git push origin dev', clone) == "allow"


def run_guard_full(raw: bytes) -> dict:
    """The hook's whole reply. The guard must exit 0 and write nothing to stderr, whatever it reads."""
    proc = subprocess.run([sys.executable, str(GUARD)], input=raw, capture_output=True, timeout=30)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert proc.stderr == b"", proc.stderr.decode("utf-8", "replace")
    return json.loads(proc.stdout.decode("utf-8")) if proc.stdout.strip() else {}


@pytest.mark.parametrize("raw", [
    b"not json, git push origin dev",
    b"\xff\xfe git push origin dev",
    json.dumps({"tool_input": ["git push origin dev"]}).encode("utf-8"),
])
def test_an_unreadable_payload_that_names_a_push_is_denied_with_a_message(raw):
    out = run_guard_full(raw)
    deny = out["hookSpecificOutput"]
    assert deny["permissionDecision"] == "deny", raw
    assert "could not read" in deny["permissionDecisionReason"], raw


@pytest.mark.parametrize("raw", [
    b"",
    b"not json, git status",
    b"[]",
    b'{"tool_input": ["git status"]}',
])
def test_an_unreadable_payload_that_names_no_push_is_let_through(raw):
    assert run_guard_full(raw) == {}, raw


@pytest.mark.parametrize("form", [
    "git --git-dir={clone}/.git push origin dev",
    "git --git-dir {clone}/.git push origin dev",
    "git --work-tree={clone} push origin dev",
    "git --work-tree {clone} push origin dev",
    "git --git-dir={clone}/.git --work-tree={clone} push origin dev",
    "git -c core.quotepath=off --git-dir={clone}/.git push origin dev",
    "git -C {elsewhere} --git-dir={clone}/.git push origin dev",
])
def test_a_push_naming_a_jnwb_checkout_by_git_dir_or_work_tree_is_denied(tmp_path, form):
    clone = make_checkout(tmp_path / "_temp_gitdir")
    elsewhere = make_checkout(tmp_path / "elsewhere", jnwb=False)
    command = form.format(clone=clone.as_posix(), elsewhere=elsewhere.as_posix())
    assert decide(command, elsewhere) == "deny", command
    assert decide(command, clone) == "deny", command


def test_a_git_dir_or_work_tree_outside_jnwb_and_a_non_push_pass(tmp_path):
    clone = make_checkout(tmp_path / "_temp_neg")
    other = make_checkout(tmp_path / "elsewhere", jnwb=False)
    assert decide(f"git --git-dir={other.as_posix()}/.git push origin dev", tmp_path) == "allow"
    assert decide(f"git --work-tree {other.as_posix()} push origin dev", tmp_path) == "allow"
    assert decide(f"git --git-dir={clone.as_posix()}/.git status", tmp_path) == "allow"


def test_a_push_of_temp_branches_only_passes(tmp_path):
    clone = make_checkout(tmp_path / "_temp_refs")
    assert decide("git push origin _temp_a _temp_b </dev/null", clone) == "allow"
    assert decide("git push -u origin +refs/heads/_temp_a:refs/heads/_temporary_a", clone) == "allow"
    assert decide("git push origin _temp_a dev", clone) == "deny"
    assert decide("git push origin _temp_a:dev", clone) == "deny"
    assert decide("git push origin", clone) == "deny"
    assert decide("git push --all origin _temp_a", clone) == "deny"
    assert decide("git push origin _temp_a && git push origin dev", clone) == "deny"


def test_pushes_elsewhere_and_other_git_commands_pass(tmp_path):
    clone = make_checkout(tmp_path / "_temp_other_refs")
    other = make_checkout(tmp_path / "other", jnwb=False)
    assert decide("git push origin dev", other) == "allow"
    assert decide(f'git -C "{other.as_posix()}" push', clone) == "allow"
    assert decide("git status", clone) == "allow"


@pytest.mark.parametrize("command", [
    "git --no-pager push origin dev",
    "git -P push origin dev",
    "git -p push origin dev",
    "git --no-optional-locks push origin dev",
    "git --no-pager --no-optional-locks push origin dev",
    "git.exe push origin dev",
    "git.exe --no-pager push origin dev",
])
def test_a_push_with_another_global_option_or_git_exe_is_denied_in_a_jnwb_checkout(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_spellings")
    assert decide(command, clone) == "deny", command


@pytest.mark.parametrize("command", [
    'git --no-pager -C "{clone}" push origin dev',
    'git.exe -C "{clone}" push origin dev',
    'git -P --git-dir="{clone}/.git" push origin dev',
])
def test_a_push_with_another_global_option_or_git_exe_naming_a_jnwb_checkout_is_denied(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_spellings_dir")
    elsewhere = make_checkout(tmp_path / "elsewhere", jnwb=False)
    command = command.format(clone=clone.as_posix())
    assert decide(command, elsewhere) == "deny", command


def test_a_push_with_another_global_option_or_git_exe_that_is_temp_only_or_elsewhere_passes(tmp_path):
    clone = make_checkout(tmp_path / "_temp_spellings_allow")
    other = make_checkout(tmp_path / "other", jnwb=False)
    assert decide("git --no-pager push origin _temp_a", clone) == "allow"
    assert decide("git.exe push origin _temp_a _temp_b", clone) == "allow"
    assert decide("git --no-pager push origin dev", other) == "allow"
    assert decide("git.exe push origin dev", other) == "allow"
    assert decide("git --no-pager status", clone) == "allow"
    assert decide("git.exe status", clone) == "allow"


@pytest.mark.parametrize("command", [
    "git --namespace foo push origin dev",
    "git --namespace=foo push origin dev",
    "GIT push origin dev",
    "git.EXE push origin dev",
])
def test_namespace_and_case_spellings_cannot_bypass_guard(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_namespace")
    assert decide(command, clone) == "deny", command


# ---- 17-147-A: pushes spelled through another executable, an environment, a cd form or a wrapper ----

JNWB_REASON = "jnwb_push.sh"  # the deny message names the wrapper to use instead


def reply(command: str, cwd: Path | str, env: dict | None = None) -> dict:
    """The hook's whole reply for a Bash command run in cwd, under the given environment."""
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": Path(cwd).as_posix()})
    proc = subprocess.run([sys.executable, str(GUARD)], input=raw.encode("utf-8"), capture_output=True,
                          timeout=30, check=True, env=env)
    return json.loads(proc.stdout.decode("utf-8")) if proc.stdout.strip() else {}


def assert_denied(command: str, cwd: Path | str, env: dict | None = None) -> None:
    """The guard denies, and the reason names the wrapper; an allow fails with the command shown."""
    out = reply(command, cwd, env)
    assert out, f"allowed, expected a deny: {command!r}"
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert JNWB_REASON in reason, (command, reason)


QUOTED_OR_ABSOLUTE_EXE = [
    '"C:/Program Files/Git/cmd/git.exe" push origin dev',
    "'/usr/bin/git' push origin dev",
    '"/usr/bin/git" push origin dev',
    r'"C:\Program Files\Git\cmd\git.exe" push origin dev',
    r"C:\Git\cmd\git.exe push origin dev",
    '"git" push origin dev',
    'g"i"t push origin dev',
]


@pytest.mark.parametrize("command", QUOTED_OR_ABSOLUTE_EXE)
def test_a_quoted_or_absolute_git_executable_is_denied_in_a_jnwb_checkout(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_exe")
    assert_denied(command, clone)


@pytest.mark.parametrize("command", QUOTED_OR_ABSOLUTE_EXE)
def test_a_quoted_or_absolute_git_executable_passes_for_temp_branches_and_elsewhere(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_exe_ok")
    other = make_checkout(tmp_path / "other", jnwb=False)
    temp = command.replace(" origin dev", " origin _temp_a")
    assert temp != command
    assert decide(temp, clone) == "allow", temp
    assert decide(command, other) == "allow", command


GIT_ENV_FORMS = [
    "GIT_DIR={clone}/.git git push origin dev",
    'GIT_DIR="{clone}/.git" git push origin dev',
    "env GIT_DIR={clone}/.git git push origin dev",
    "env -i GIT_DIR={clone}/.git git push origin dev",
    "GIT_WORK_TREE={clone} git push origin dev",
    "GIT_COMMON_DIR={clone}/.git git push origin dev",
    "export GIT_DIR={clone}/.git; git push origin dev",
]


@pytest.mark.parametrize("form", GIT_ENV_FORMS)
def test_a_git_dir_or_work_tree_in_the_environment_names_a_checkout(tmp_path, form):
    clone = make_checkout(tmp_path / "_temp_env")
    elsewhere = make_checkout(tmp_path / "elsewhere", jnwb=False)
    assert not (elsewhere / "jnwb" / "__init__.py").exists(), "fixture must be a non-jnwb cwd"
    assert_denied(form.format(clone=clone.as_posix()), elsewhere)


def test_an_environment_git_dir_naming_another_checkout_or_a_temp_push_passes(tmp_path):
    clone = make_checkout(tmp_path / "_temp_env_ok")
    other = make_checkout(tmp_path / "other", jnwb=False)
    assert decide(f"GIT_DIR={other.as_posix()}/.git git push origin dev", tmp_path) == "allow"
    assert decide(f"export GIT_DIR={other.as_posix()}/.git; git push origin dev", tmp_path) == "allow"
    assert decide(f"GIT_DIR={clone.as_posix()}/.git git push origin _temp_a", tmp_path) == "allow"
    assert decide(f"GIT_DIR={clone.as_posix()}/.git git status", tmp_path) == "allow"


GLOBAL_OPTION_FORMS = [
    'git --namespace="x y" push origin dev',
    'git -c "user.name=a b" push origin dev',
    "git --super-prefix sub/ push origin dev",
    "git --config-env a=HOME push origin dev",
]


@pytest.mark.parametrize("command", GLOBAL_OPTION_FORMS)
def test_a_global_option_with_a_quoted_value_or_a_separate_argument_is_parsed(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_globals")
    assert_denied(command, clone)


def test_a_quoted_git_C_option_name_names_its_checkout(tmp_path):
    clone = make_checkout(tmp_path / "_temp_quoted_C")
    elsewhere = make_checkout(tmp_path / "elsewhere", jnwb=False)
    assert_denied(f'git "-C" "{clone.as_posix()}" push origin dev', elsewhere)
    assert decide(f'git "-C" "{elsewhere.as_posix()}" push origin dev', clone) == "allow"


CD_FORMS = [
    "(cd {clone} && git push origin dev)",
    "{{ cd {clone}; git push origin dev; }}",
    "pushd {clone} && git push origin dev",
    'pushd "{clone}" && git push origin dev',
]


@pytest.mark.parametrize("form", CD_FORMS)
def test_a_cd_in_a_subshell_brace_group_or_pushd_names_the_checkout(tmp_path, form):
    clone = make_checkout(tmp_path / "_temp_cd")
    elsewhere = make_checkout(tmp_path / "elsewhere", jnwb=False)
    assert_denied(form.format(clone=clone.as_posix()), elsewhere)


def test_a_cd_in_a_subshell_or_brace_group_to_another_checkout_passes(tmp_path):
    clone = make_checkout(tmp_path / "_temp_cd_ok")
    other = make_checkout(tmp_path / "other", jnwb=False)
    assert decide(f"(cd {other.as_posix()} && git push origin dev)", clone) == "allow"
    assert decide(f"{{ cd {other.as_posix()}; git push origin dev; }}", clone) == "allow"
    assert decide(f"(cd {clone.as_posix()} && git push origin _temp_a)", tmp_path) == "allow"


def test_a_tilde_cd_names_a_checkout_under_home(tmp_path):
    home = tmp_path / "home"
    clone = make_checkout(home / "_temp_home_jnwb")
    make_checkout(home / "plain_home", jnwb=False)
    plain = make_checkout(tmp_path / "plain", jnwb=False)
    env = dict(os.environ, HOME=home.as_posix(), USERPROFILE=home.as_posix())
    assert (clone / "jnwb" / "__init__.py").is_file(), "fixture must be a jnwb checkout under home"
    assert_denied("cd ~/_temp_home_jnwb && git push origin dev", plain, env)
    assert reply("cd ~/plain_home && git push origin dev", plain, env) == {}
    assert reply("cd ~/_temp_home_jnwb && git push origin _temp_a", plain, env) == {}


def test_a_push_inside_the_wrapper_call_is_checked(tmp_path):
    clone = make_checkout(tmp_path / "_temp_wrap")
    wrapper = f'bash "{clone.as_posix()}/scripts/jnwb_push.sh"'
    assert_denied(f'{wrapper} "$(git push origin dev)"', clone)
    assert reply(f'{wrapper} "$(git push origin _temp_a)"', clone) == {}
    assert reply(f'{wrapper} "{clone.as_posix()}" dev </dev/null', clone) == {}


@pytest.mark.parametrize("command", [
    "command git push origin dev",
    r"\git push origin dev",
    "/usr/bin/env git push origin dev",
    "exec git push origin dev",
    "nohup git push origin dev",
    "echo origin dev | xargs git push",
])
def test_a_word_before_git_does_not_hide_a_push_in_a_jnwb_checkout(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_prefix_words")
    assert_denied(command, clone)


# ---- 17-147-A revision: a push nested after a wrapper word, a quote or a backtick ------------------

NESTED_PUSH_FORMS = [
    "bash -c 'git push origin dev'",
    'sh -c "git push origin dev"',
    "bash -lc 'git push origin dev'",
    "`git push origin dev`",
    '"`git push origin dev`"',
    "echo `git push origin dev`",
    "x=`git push origin dev`",
    'echo "$(git push origin dev)"',
    "! git push origin dev",
    "{ git push origin dev; }",
]


@pytest.mark.parametrize("command", NESTED_PUSH_FORMS)
def test_a_push_nested_after_a_wrapper_word_or_a_backtick_is_denied_in_a_jnwb_checkout(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_nested")
    assert_denied(command, clone)


@pytest.mark.parametrize("command", NESTED_PUSH_FORMS)
def test_a_nested_push_temp_only_or_elsewhere_passes(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_nested_ok")
    other = make_checkout(tmp_path / "other", jnwb=False)
    temp = command.replace(" origin dev", " origin _temp_a")
    assert temp != command, "fixture must name the dev push"
    assert decide(temp, clone) == "allow", temp
    assert decide(command, other) == "allow", command


def test_legitimate_commands_pass_inside_and_outside_a_jnwb_checkout(tmp_path):
    clone = make_checkout(tmp_path / "_temp_legit")
    other = make_checkout(tmp_path / "other", jnwb=False)
    wrapper = f'bash "{clone.as_posix()}/scripts/jnwb_push.sh" "{clone.as_posix()}" dev </dev/null'
    for cwd in (clone, other):
        assert reply("git status", cwd) == {}, cwd
        assert reply("git push origin _temp_a", cwd) == {}, cwd
        assert reply("git push origin _temp_a _temp_b </dev/null", cwd) == {}, cwd
        assert reply(wrapper, cwd) == {}, cwd
        assert reply("bash -c 'git status'", cwd) == {}, cwd
        assert reply("bash -c 'git push origin _temp_a'", cwd) == {}, cwd
        assert reply("mygit push origin dev", cwd) == {}, cwd


# ---- 17-147-A revision 2: bounded time on pathological input --------------------------------------

BOUNDED_SECONDS = 5

PATHOLOGICAL_NOISE = [
    ("5000 backslashes", "\\" * 5000),
    ("5000 double quotes", '"' * 5000),
    ("5000 single quotes", "'" * 5000),
    ("50 KB double quotes", '"' * 50000),
    ("git with 1000 option pairs", "git " + "-c -c " * 1000 + "x"),
    ("git with 400 dash groups", "git -a -b -c " * 400),
    ("400 push words without git", "push " * 500),
]


def bounded_reply(command: str, cwd: Path | str) -> dict:
    """The hook's reply from a subprocess that must finish within BOUNDED_SECONDS; a hang fails the test."""
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": Path(cwd).as_posix()})
    try:
        proc = subprocess.run([sys.executable, str(GUARD)], input=raw.encode("utf-8"), capture_output=True,
                              timeout=BOUNDED_SECONDS, check=True)
    except subprocess.TimeoutExpired:
        pytest.fail(f"guard did not finish within {BOUNDED_SECONDS} s on a {len(command)}-character command")
    return json.loads(proc.stdout.decode("utf-8")) if proc.stdout.strip() else {}


@pytest.mark.parametrize("name, noise", PATHOLOGICAL_NOISE, ids=[n for n, _ in PATHOLOGICAL_NOISE])
def test_pathological_noise_from_a_jnwb_checkout_finishes_and_is_allowed(tmp_path, name, noise):
    clone = make_checkout(tmp_path / "_temp_patho_noise")
    assert bounded_reply(noise, clone) == {}, name


@pytest.mark.parametrize("name, noise", PATHOLOGICAL_NOISE, ids=[n for n, _ in PATHOLOGICAL_NOISE])
def test_pathological_noise_ending_in_a_real_push_finishes_and_is_denied(tmp_path, name, noise):
    clone = make_checkout(tmp_path / "_temp_patho_push")
    reason = bounded_reply(noise + " git push origin dev", clone)["hookSpecificOutput"]["permissionDecisionReason"]
    assert JNWB_REASON in reason, name


def test_a_repeated_push_word_finishes_and_is_denied(tmp_path):
    clone = make_checkout(tmp_path / "_temp_patho_repeat")
    reason = bounded_reply("git push " * 500, clone)["hookSpecificOutput"]["permissionDecisionReason"]
    assert JNWB_REASON in reason


# ---- 17-143: `jnwb_push.sh <dir> --tag vX.Y.Z` and the artifacts-only stack checks ---------------
#
# CI reads go to the local stand-in server of test_jnwb_push.py (`ci_api`); the remote is a local bare
# repository. The scaffold commit holds the real verify_lane.py and two stand-ins for the stack checks
# (gate 15 and the item-length test), so each refusal below is caused by the case under test.

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
from tests.test_jnwb_push import OLDER_SHA, _body, _git, _run, ci_api  # noqa: E402, F401  (fixture)

PUSH_SH = Path(__file__).resolve().parents[1] / "scripts" / "jnwb_push.sh"
VERIFY_LANE = Path(__file__).resolve().parents[1] / "scripts" / "verify_lane.py"
TODO_WITH_ITEM = """# 0.2.17

### 17-900 A demo item

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: {writes}
- 17-900: demo.
"""
PASS_STUB = "import sys\nsys.exit(0)\n"
FAIL_STUB = "import sys\nprint('stub gate failed')\nsys.exit(1)\n"
ITEM_TEST_PASS = "def test_ok():\n    assert True\n"
ITEM_TEST_FAIL = "def test_ok():\n    assert False\n"


def _bash_path() -> str:
    if sys.platform != "win32":
        return "bash"
    git_bash = Path("C:/Program Files/Git/usr/bin/bash.exe")
    if not git_bash.exists():
        pytest.skip("Git for Windows bash not found")
    return git_bash.as_posix()


def _remote_ref(bare: Path, ref: str):
    proc = subprocess.run(["git", "rev-parse", "-q", "--verify", ref], cwd=str(bare),
                          capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _scaffold(tmp_path: Path, *, writes: str = "`artifacts/todo_stack.md`",
              gate_stub: str = PASS_STUB, item_test: str = ITEM_TEST_PASS):
    """A clone whose origin dev and main both hold the scaffold; returns (repo, bare, home)."""
    home = tmp_path / "home"
    (home / ".claude" / "bin").mkdir(parents=True)
    (home / ".claude" / "bin" / "ci_inflight.py").write_text("print(0)\n", encoding="utf-8")
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", bare.as_posix())
    repo = tmp_path / "_temp_stack"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/dev")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "remote", "add", "origin", bare.as_posix())
    (repo / "scripts").mkdir()
    (repo / "scripts" / "verify_lane.py").write_bytes(VERIFY_LANE.read_bytes())
    (repo / "scripts" / "harness_gate.py").write_text(gate_stub, encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_stack_item_length.py").write_text(item_test, encoding="utf-8")
    (repo / "artifacts").mkdir()
    (repo / "artifacts" / "todo_stack.md").write_text(TODO_WITH_ITEM.format(writes=writes),
                                                      encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "scaffold")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-q", bare.as_posix(), "HEAD:refs/heads/dev", "HEAD:refs/heads/main")
    _git(repo, "update-ref", "refs/remotes/origin/dev", head)
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    return repo, bare, home


def _wrapper(repo: Path, home: Path, api_url: str, *args: str, extra_env: dict | None = None):
    env = dict(os.environ)
    env["HOME"] = home.as_posix()
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])
    env["JNWB_CI_API"] = api_url
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    env.pop("JNWB_PUSH_OVER_RED", None)
    env.update(extra_env or {})
    return subprocess.run([_bash_path(), PUSH_SH.as_posix(), repo.as_posix(), *args],
                          cwd=str(repo), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=600)


def _commit_artifacts_only(repo: Path, text: str = "\n- note 17-900\n") -> None:
    todo = repo / "artifacts" / "todo_stack.md"
    todo.write_text(todo.read_text(encoding="utf-8") + text, encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "stack edit")


def test_tag_push_refuses_when_the_newest_main_run_is_not_at_the_tip(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    state["body"] = _body([_run("CI/CD", OLDER_SHA, "success")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "refusing" in out and "tip" in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") is None, "a tag reached the remote without a run at its tip"


def test_tag_push_refuses_when_a_main_run_at_the_tip_failed(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    tip = _git(repo, "rev-parse", "origin/main")
    state["body"] = _body([_run("CI/CD", tip, "failure")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "not successful" in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") is None


def test_tag_push_refuses_an_unreadable_main_answer(tmp_path, ci_api):
    state, url = ci_api
    state["status"], state["body"] = 403, b'{"message": "API rate limit exceeded"}'
    repo, bare, home = _scaffold(tmp_path)
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "unreadable" in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") is None


@pytest.mark.parametrize("name", ["0.2.17", "v0.2", "v0.2.17-rc1", "release-1"])
def test_tag_name_must_be_vX_Y_Z(tmp_path, ci_api, name):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    tip = _git(repo, "rev-parse", "origin/main")
    state["body"] = _body([_run("CI/CD", tip, "success")])
    proc = _wrapper(repo, home, url, "--tag", name)
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "vX.Y.Z" in out, out
    assert _remote_ref(bare, "refs/tags/" + name) is None


def test_tag_push_pushes_the_tag_at_main_tip_when_the_tip_runs_succeeded(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    tip = _git(repo, "rev-parse", "origin/main")
    state["body"] = _body([_run("CI/CD", tip, "success"), _run("dashboard", tip, "success")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _remote_ref(bare, "refs/tags/v0.2.17") == tip


def test_tag_push_refuses_to_move_an_existing_tag(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    old_tip = _git(repo, "rev-parse", "origin/main")
    _git(repo, "push", "-q", bare.as_posix(), f"{old_tip}:refs/tags/v0.2.17")
    _commit_artifacts_only(repo, "\n- main moved\n")
    new_tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-q", bare.as_posix(), "HEAD:refs/heads/main")
    _git(repo, "update-ref", "refs/remotes/origin/main", new_tip)
    state["body"] = _body([_run("CI/CD", new_tip, "success")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "already exists" in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") == old_tip, "an existing tag was moved"


def test_artifacts_only_push_refuses_a_bare_directory_in_writes(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path, writes="`artifacts`")
    _commit_artifacts_only(repo)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", _remote_ref(bare, "refs/heads/dev"), "success")])
    proc = _wrapper(repo, home, url, "dev", "--item", "17-900")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "bare directory" in out, out
    assert _remote_ref(bare, "refs/heads/dev") != head, "a refused artifacts-only push reached the remote"


def test_artifacts_only_push_with_a_file_in_writes_passes(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    _commit_artifacts_only(repo)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", _remote_ref(bare, "refs/heads/dev"), "success")])
    proc = _wrapper(repo, home, url, "dev", "--item", "17-900")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _remote_ref(bare, "refs/heads/dev") == head


def test_artifacts_only_push_refuses_when_the_stack_gate_fails(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path, gate_stub=FAIL_STUB)
    _commit_artifacts_only(repo)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", _remote_ref(bare, "refs/heads/dev"), "success")])
    proc = _wrapper(repo, home, url, "dev", "--item", "17-900")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "stack gate" in out, out
    assert _remote_ref(bare, "refs/heads/dev") != head


def test_tag_push_refuses_when_the_tip_has_no_successful_CI_CD_run(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    tip = _git(repo, "rev-parse", "origin/main")
    state["body"] = _body([_run("dashboard", tip, "success")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "CI/CD" in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") is None, "a tag reached the remote without a CI/CD run"


def test_the_override_does_not_reach_a_tag_push(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    tip = _git(repo, "rev-parse", "origin/main")
    state["body"] = _body([_run("CI/CD", tip, "failure"), _run("dashboard", tip, "success")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17", extra_env={"JNWB_PUSH_OVER_RED": "1"})
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "pushing anyway" not in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") is None, "the override pushed a tag"


def test_a_push_whose_diff_cannot_be_read_is_refused(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    _commit_artifacts_only(repo)
    _git(repo, "update-ref", "-d", "refs/remotes/origin/dev")
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", _remote_ref(bare, "refs/heads/dev"), "success")])
    proc = _wrapper(repo, home, url, "dev")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "git diff" in out, out
    assert _remote_ref(bare, "refs/heads/dev") != head


import threading as _threading  # noqa: E402
from http.server import BaseHTTPRequestHandler as _BaseHandler  # noqa: E402
from http.server import ThreadingHTTPServer as _Server  # noqa: E402


@pytest.fixture
def ci_api_with_hook():
    """The CI stand-in of test_jnwb_push.py, with a hook that runs before each response is sent, so a
    test can move origin/main between the CI read and the tag push."""
    state = {"status": 200, "body": b'{"workflow_runs": []}', "before_response": None}

    class Handler(_BaseHandler):
        def do_GET(self):
            hook, state["before_response"] = state["before_response"], None
            if hook is not None:
                hook()
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(state["body"])

        def log_message(self, format, *args):
            pass

    server = _Server(("127.0.0.1", 0), Handler)
    _threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield state, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def test_tag_push_refuses_when_origin_main_moves_during_the_CI_read(tmp_path, ci_api_with_hook):
    state, url = ci_api_with_hook
    repo, bare, home = _scaffold(tmp_path)
    tip = _git(repo, "rev-parse", "origin/main")
    _commit_artifacts_only(repo, "\n- main moves\n")
    moved = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", tip, "success")])
    state["before_response"] = lambda: _git(repo, "push", "-q", bare.as_posix(), "HEAD:refs/heads/main")
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "moved" in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") is None, "a tag landed at a tip that had moved"
    assert _remote_ref(bare, "refs/heads/main") == moved


def test_artifacts_only_push_refuses_when_the_item_length_test_fails(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path, item_test=ITEM_TEST_FAIL)
    _commit_artifacts_only(repo)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", _remote_ref(bare, "refs/heads/dev"), "success")])
    proc = _wrapper(repo, home, url, "dev", "--item", "17-900")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert _remote_ref(bare, "refs/heads/dev") != head
