"""Assert a lane is in its own worktree, at the baseline it was given, before it reads anything.

Three defects, all measured in this repository, all of which produced a confident wrong answer
rather than an error:

* **The provisioner branches lanes behind their stated baseline.** Six lanes across two waves
  each found HEAD at ``5ecc12eb`` and fast-forwarded; the distance was reported as 192, then
  213, then 216, then ~220. The number is not the defect -- the fixed base is. At that commit
  ``artifacts/goal.md``, ``artifacts/problem_stack.md`` and ``artifacts/agents/jnwb-developer.md``
  do not exist, cited line numbers point at unrelated code, and the todo items are absent.
  Nothing errors. Every lane so far detected it independently, which is luck: a packet that
  trusted its baseline would have measured the 0.1.8 tree and reported against it.

* **A packet that quotes a distance is stale the moment the dispatcher commits again.** One
  packet stated 213 against a baseline two commits later than the figure was measured from, and
  the lane measured 216. Only the baseline *commit* is stable, so a distance is refused here
  rather than accepted and compared.

* **A fan-out can land in the main tree.** Wave 2's six lanes were dispatched without
  requesting isolation and all six operated directly on the main checkout -- six writers and
  several readers in one tree, the exact failure the one-writable-agent rule exists to prevent.
  No damage occurred, and the reason is worth recording: the packets' own invariants held where
  the provisioning did not. Three lanes had not yet written, one caught the intrusion and began
  investigating it, and one stopped of its own accord.

Once the baseline holds, the lane's ``artifacts/state.md`` is checked with
``reconstruct_state.py --check``; a stale file is regenerated and checked again.

Usage::

    python scripts/verify_lane.py --baseline <commit>
    python scripts/verify_lane.py --baseline <commit> --allow-main-tree
    python scripts/verify_lane.py --push-item <id> --target <ref>

``--push-item`` refuses a push whose diff against ``<ref>`` leaves the ``Writes:`` of the
todo item ``<id>``, read from ``<ref>``'s ``artifacts/todo_stack.md``.

Exits 0 only when every check passes. On failure it prints both SHAs, because a message that
says "mismatch" without them cannot be acted on without a second command.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

#: A distance, not a commit. Refused outright: a packet quoting "216 commits behind" names a
#: figure that was already stale when it was written.
_LOOKS_LIKE_A_DISTANCE = re.compile(r"^\d{1,6}$")

#: An abbreviated or full hex object name. Anything else is a ref whose target moves.
_LOOKS_LIKE_A_COMMIT = re.compile(r"^[0-9a-fA-F]{7,40}$")


def _git(*args: str, cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        ("git",) + args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    return proc.returncode, (proc.stdout or "").strip() or (proc.stderr or "").strip()


def in_linked_worktree(cwd: Path | None = None) -> bool:
    """True when this is a linked worktree rather than the main checkout.

    ``--git-dir`` resolves to ``.git`` in the main tree and to ``.git/worktrees/<name>`` in a
    linked one, while ``--git-common-dir`` names the shared directory in both. Comparing them
    is the only check that does not depend on a path convention the provisioner could change.
    """
    code_a, git_dir = _git("rev-parse", "--absolute-git-dir", cwd=cwd)
    code_b, common = _git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
    if code_a != 0 or code_b != 0:
        return False
    return Path(git_dir).resolve() != Path(common).resolve()


def check(baseline: str, *, allow_main_tree: bool = False,
          cwd: Path | None = None) -> list[str]:
    """Every failing condition, as a list of messages. Empty means the lane may proceed."""
    problems: list[str] = []

    if _LOOKS_LIKE_A_DISTANCE.match(baseline):
        problems.append(
            f"--baseline {baseline!r} is a distance, not a commit. A packet quoting a commit "
            "count is stale the moment the dispatcher commits again: one stated 213 against a "
            "baseline two commits later than that figure was measured from, and the lane "
            "measured 216. Name the baseline commit."
        )
        return problems  # nothing below can be meaningfully checked against a number

    if not _LOOKS_LIKE_A_COMMIT.match(baseline):
        problems.append(
            f"--baseline {baseline!r} is not an object name. A branch or tag moves, so two "
            "lanes given the same ref can start from different trees. Name the commit."
        )
        return problems

    if not allow_main_tree and not in_linked_worktree(cwd):
        problems.append(
            "this is the main checkout, not a linked worktree. A worktree has exactly one "
            "writable agent, and a fan-out that lands here puts several writers and readers "
            "in one tree. Request isolation explicitly, or pass --allow-main-tree if you are "
            "deliberately the single writer."
        )

    code, head = _git("rev-parse", "HEAD", cwd=cwd)
    if code != 0:
        problems.append(f"git rev-parse HEAD failed: {head}")
        return problems

    code, resolved = _git("rev-parse", f"{baseline}^{{commit}}", cwd=cwd)
    if code != 0:
        problems.append(
            f"baseline {baseline} is not an object in this tree: {resolved}. The provisioner "
            "may have branched from a commit that predates it."
        )
        return problems

    if head != resolved:
        # Both directions are counted, because they call for opposite actions and telling them
        # apart is the whole value of the check. HEAD behind the baseline is the provisioning
        # defect and wants a fast-forward; HEAD ahead of it is a stale packet, where a merge
        # would be a no-op and reporting one as the other is a confident wrong answer.
        code_a, ahead_of_head = _git("rev-list", "--count", f"HEAD..{resolved}", cwd=cwd)
        code_b, behind_head = _git("rev-list", "--count", f"{resolved}..HEAD", cwd=cwd)
        n_ahead = int(ahead_of_head) if code_a == 0 and ahead_of_head.isdigit() else -1
        n_behind = int(behind_head) if code_b == 0 and behind_head.isdigit() else -1

        if n_ahead > 0 and n_behind == 0:
            problems.append(
                f"HEAD is {head}, {n_ahead} commit(s) BEHIND the baseline {resolved}. This is "
                f"the provisioning defect. Run `git merge --ff-only {resolved}` as the first "
                "action, before opening any file, and report the resulting rev-parse. Never "
                "`git reset --hard` -- it discards work the tree may be carrying for someone "
                "else."
            )
        elif n_behind > 0 and n_ahead == 0:
            problems.append(
                f"HEAD is {head}, {n_behind} commit(s) AHEAD of the baseline {resolved}. The "
                "tree is newer than the packet, so this is a stale packet rather than a "
                "mis-provisioned worktree, and a fast-forward would do nothing. Confirm the "
                "packet still describes work that applies to this tree before proceeding."
            )
        else:
            problems.append(
                f"HEAD {head} and baseline {resolved} have DIVERGED ({n_behind} ahead, "
                f"{n_ahead} behind). Stop and report both SHAs. Neither a fast-forward nor a "
                "reset is correct here."
            )

    return problems


def state_check(cwd: Path | None = None) -> tuple[str, str]:
    """Run ``reconstruct_state.py --check`` in the tree; on failure regenerate, then check again.

    Returns ``("current", "")``, ``("regenerated", "")`` or ``("failed", message)``.
    """
    code, root = _git("rev-parse", "--show-toplevel", cwd=cwd)
    if code != 0:
        return "failed", f"cannot find the repository root: {root}"
    script = Path(root) / "scripts" / "reconstruct_state.py"
    if not script.is_file():
        return "failed", f"{script} is missing, so artifacts/state.md cannot be checked"

    def run(*extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script), *extra], cwd=root, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        )

    if run("--check").returncode == 0:
        return "current", ""
    regen = run()
    second = run("--check")
    if second.returncode == 0:
        return "regenerated", ""
    said = (second.stdout + second.stderr).strip()[-300:]
    return "failed", (
        f"artifacts/state.md fails --check after regeneration (regeneration exit "
        f"{regen.returncode}). Run python scripts/reconstruct_state.py and read its output. "
        f"The check says: {said}"
    )


#: Paths any push may carry beside an item's Writes: the stacks, changelog fragments and the
#: files every change regenerates. Each is a glob, read the same way as a Writes entry.
ALWAYS_WRITABLE: tuple[str, ...] = (
    "artifacts/todo_stack.md",
    "artifacts/open_stack.md",
    "artifacts/changelog.d/*",
    "CHANGELOG.md",
    "docs/api.md",
    "artifacts/process/frozen_validated.json",
    "artifacts/memory.md",
)

_ITEM_ID = re.compile(r"^\d+-\d+$")
_HEADING_ID = re.compile(r"^###\s+(\S+)")
_BACKTICKED = re.compile(r"`([^`]+)`")


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """A Writes entry as a regex over repository paths: ``**/`` spans directories, ``*`` one name."""
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            parts.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(parts))


def item_writes(todo_text: str, item: str) -> list[str]:
    """The backticked paths on an item's ``Writes:`` line, read from the item's own section.

    Raises ValueError, naming the item, when it is absent, repeated, or has no Writes line.
    """
    sections: list[list[str]] = []
    body: list[str] | None = None
    for line in todo_text.splitlines():
        if line.startswith("#"):
            heading = _HEADING_ID.match(line)
            body = [] if heading and heading.group(1) == item else None
            if body is not None:
                sections.append(body)
            continue
        if body is not None:
            body.append(line)
    if not sections:
        raise ValueError(f"item {item} is not in artifacts/todo_stack.md")
    if len(sections) > 1:
        raise ValueError(f"item {item} heads {len(sections)} sections of artifacts/todo_stack.md")
    for line in sections[0]:
        if line.startswith("Writes:"):
            return _BACKTICKED.findall(line)
    raise ValueError(f"item {item} has no Writes: line in artifacts/todo_stack.md")


def push_check(item: str, target: str, *, cwd: Path | None = None) -> tuple[list[str], int]:
    """Refuse a push whose diff against ``target`` leaves the Writes of the todo item ``item``.

    ``item`` may list several ids separated by commas (a batch push); their Writes are joined.
    The items are read from ``target``'s ``artifacts/todo_stack.md``, not HEAD's: the push itself
    removes finished items. Returns ``(problems, changed paths inside the Writes)``; empty
    problems means the push may proceed.
    """
    items = [i.strip() for i in item.split(",")]
    bad = [i for i in items if not _ITEM_ID.match(i)]
    if bad:
        return [f"{', '.join(map(repr, bad))} does not have the form NN-NNN. Nothing is pushed."], 0
    code, todo = _git("show", f"{target}:artifacts/todo_stack.md", cwd=cwd)
    if code != 0:
        return [f"cannot read artifacts/todo_stack.md at {target}: {todo}. Nothing is pushed."], 0
    writes: list[str] = []
    for one in items:
        try:
            writes += item_writes(todo, one)
        except ValueError as exc:
            return [f"{exc} at {target}. Nothing is pushed."], 0
    diff = subprocess.run(
        ["git", "diff", "--name-only", f"{target}...HEAD"],
        cwd=str(cwd) if cwd else None, capture_output=True, text=True,
    )
    if diff.returncode != 0:
        return [f"git diff {target}...HEAD failed: {diff.stderr.strip()}. Nothing is pushed."], 0
    paths = [line for line in diff.stdout.splitlines() if line.strip()]
    allowed = [glob_to_regex(pattern) for pattern in (*ALWAYS_WRITABLE, *writes)]
    outside = [p for p in paths if not any(rx.fullmatch(p) for rx in allowed)]
    if outside:
        listing = "".join(f"\n  {p}" for p in outside)
        return [
            f"the push leaves the Writes of {item}; {len(outside)} path(s) outside:{listing}\n"
            "Nothing is pushed."
        ], 0
    return [], len(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--baseline",
                        help="the commit the packet names (an object name, never a distance)")
    parser.add_argument("--allow-main-tree", action="store_true",
                        help="permit the main checkout, for a deliberate single writer")
    parser.add_argument("--push-item", metavar="ID",
                        help="check a push: refuse when its diff leaves the Writes of todo item NN-NNN")
    parser.add_argument("--target", metavar="REF",
                        help="the push target read for --push-item, e.g. origin/dev")
    args = parser.parse_args(argv)

    if args.push_item is not None:
        if args.target is None:
            parser.error("--push-item needs --target")
        problems, count = push_check(args.push_item, args.target)
        if problems:
            for problem in problems:
                print(f"PUSH REFUSED: {problem}")
            return 1
        print(f"WRITES OK: {count} changed path(s) inside the Writes of {args.push_item}, "
              "or always writable.")
        return 0

    if args.baseline is None:
        parser.error("the following arguments are required: --baseline")

    problems = check(args.baseline, allow_main_tree=args.allow_main_tree)
    if problems:
        for problem in problems:
            print(f"LANE: {problem}")
        return 1

    state, message = state_check()
    if state == "failed":
        print(f"LANE: {message}")
        return 1

    _, head = _git("rev-parse", "HEAD")
    where = "linked worktree" if in_linked_worktree() else "main checkout (permitted)"
    print(f"LANE OK: {where}, HEAD {head} matches the named baseline.")
    print(f"state: {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
