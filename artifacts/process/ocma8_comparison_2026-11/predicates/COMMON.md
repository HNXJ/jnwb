# Predicate packet: common rules (read fully before the task text in your prompt)

You write two files for one task `t<n>` of a preregistered experiment, in `D:/repos/_work/exp_prereq/t<n>/` and
nowhere else. You do not do the task itself for anyone's use.

Files:
1. `predicates_t<n>.py`: usage `python predicates_t<n>.py <tree> <baseline tree>`. Standard library only (it may
   run `git`, `python`, `pytest` as subprocesses with `cwd=<tree>`). It prints one line per check,
   `<id> PASS|FAIL <what was examined, with the numbers>`, ids `P1..` (primary) then `C1..` (constraints), and a
   last line `PRIMARY <k>/<n> CONSTRAINTS <j>/<m>`. Exit 0 whenever it ran to the end, 2 on a usage error. A check
   that cannot be evaluated (missing file, command error) is FAIL and says why. It never writes inside `<tree>` or
   `<baseline tree>` beyond what the commands it runs write on their own (use `-p no:cacheprovider` and a
   `--basetemp` outside the trees for pytest; set `PYTHONDONTWRITEBYTECODE=1` for subprocesses). Module docstring
   first: what it checks and the usage. No `argparse` needed; no options.
2. `accept_t<n>.sh`: usage `bash accept_t<n>.sh <tree>`. Runs the task's acceptance commands in `<tree>` one after
   another, prints each command's last output line, and a last line `ACCEPT_RC=<0 if all passed else 1>`.

Trees: the baseline worktree named in your prompt is read-only for you: never run anything inside it. Make your own
copy first: `git clone -q --shared <baseline worktree> D:/repos/_work/exp_prereq/t<n>/base` then
`git -C D:/repos/_work/exp_prereq/t<n>/base checkout -q --detach <baseline SHA>`. Run everything there or in further
clones under `D:/repos/_work/exp_prereq/t<n>/`.

Controls you must run and report, with the printed lines:
- Known negative: `python predicates_t<n>.py <base clone> <base clone>` must end `PRIMARY 0/<n>` (every primary FAIL
  on the untouched baseline). Constraints may pass there.
- Known positive for acceptance: `bash accept_t<n>.sh <base clone>` must end `ACCEPT_RC=0`.
- Each primary check must be able to pass: build a throwaway tree (a second clone, `.../t<n>/pos`) by the cheapest
  honest means, run the predicates on it, and report the scores. In your report describe the throwaway tree in ONE
  line at most; do not explain how the task is best solved.
- Each constraint must be able to fail: show one small perturbation of the throwaway tree that turns it to FAIL.

Shell rules on this Windows host (Git Bash): never `python -c`, never `python -` and no heredocs for code: write a
file with the Write tool and run it by path; close stdin with `</dev/null` on python and git network commands;
never `sed -i`; never `git add .`; no commits, no pushes, no branch creation; pytest always with
`-p no:cacheprovider --basetemp=D:/pytest_temp/exp_t<n>` (outside the repos). Do not read or write `~/.claude`.
If the task text conflicts with what the tree shows (a count, a file name), do not choose: implement the check as
written, report the conflict with both values in your Unresolved table.
Report: worker form, at most 350 words, with the three control outputs' last lines.
