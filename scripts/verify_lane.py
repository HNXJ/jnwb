"""Assert a lane is in its own worktree, at the baseline it was given, before it reads anything.

Three defects, all measured in this repository, all of which produced a confident wrong answer
rather than an error:

* **The provisioner branches lanes behind their stated baseline.** Six lanes across two waves
  each found HEAD at ``5ecc12eb`` and fast-forwarded; the distance was reported as 192, then
  213, then 216, then ~220. The number is not the defect -- the fixed base is. At that commit
  ``artifacts/goal.md``, ``artifacts/problem_stack.md`` and ``artifacts/agents/jnwb-developer.md``
  do not exist, cited line numbers point at unrelated code, and the todo items are absent.
  Nothing errors. Every lane so far detected it independently, which is luck: a packet that
  trusted its baseline would have measured the 0.1.8 tree and reported against it (P-28, P-153).

* **A packet that quotes a distance is stale the moment the dispatcher commits again.** One
  packet stated 213 against a baseline two commits later than the figure was measured from, and
  the lane measured 216. Only the baseline *commit* is stable, so a distance is refused here
  rather than accepted and compared (P-153).

* **A fan-out can land in the main tree.** Wave 2's six lanes were dispatched without
  requesting isolation and all six operated directly on the main checkout -- six writers and
  several readers in one tree, the exact failure the one-writable-agent rule exists to prevent.
  No damage occurred, and the reason is worth recording: the packets' own invariants held where
  the provisioning did not. Three lanes had not yet written, one caught the intrusion and began
  investigating it, and one stopped of its own accord (P-144).

Usage::

    python scripts/verify_lane.py --baseline <commit>
    python scripts/verify_lane.py --baseline <commit> --allow-main-tree

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--baseline", required=True,
                        help="the commit the packet names (an object name, never a distance)")
    parser.add_argument("--allow-main-tree", action="store_true",
                        help="permit the main checkout, for a deliberate single writer")
    args = parser.parse_args(argv)

    problems = check(args.baseline, allow_main_tree=args.allow_main_tree)
    if problems:
        for problem in problems:
            print(f"LANE: {problem}")
        return 1

    _, head = _git("rev-parse", "HEAD")
    where = "linked worktree" if in_linked_worktree() else "main checkout (permitted)"
    print(f"LANE OK: {where}, HEAD {head} matches the named baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
