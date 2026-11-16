# Packets for the four-task comparison (prerequisite 4 of `PREREG.md`; DRAFT until reviewed and frozen)

The orchestrator sends blocks verbatim, fills only the named slots, and adds nothing. Every agent of both arms gets
`TASK-t<n>` first, then its role block; the role blocks marked "+ACCEPT" get `ACCEPT-t<n>` after it, and no other
agent is given the acceptance command (PREREG, Tasks). No role block holds anything about a task.

Slots: `{W}` the agent's worktree; `{W1}`, `{W2}` the two workers' worktrees; `{ACC}` =
`bash D:/repos/_work/exp_accept/accept_t<n>.sh {W}`; `<reports>` = whole reports, verbatim, in dispatch order,
each under a line `--- report of <role> ---`; a run that ended with no report (cap or error) has the one line
`(no report)` under its heading.

Parts (PREREG, Tasks): neither T-82 nor the `cells()` half of 17-95 enumerates parts a worker could take alone
(T-82's second closing condition is a run on vwin-pc, outside a worktree; the eight splitters are one list). By the
frozen rule all four tasks run as one-part tasks: in arm B both workers draft the whole item and the keeper takes
the draft that passes acceptance. The split against one-part tasks then has no split task and, as PREREG says for
that case, is not reported; the reason is.

Worktrees, each a linked worktree at the task's baseline, detached: arm A `D:/repos/_work/exp_t<n>_A`; arm B
`exp_t<n>_B` (keeper), `exp_t<n>_B1`, `exp_t<n>_B2`. They are linked to a clone made for the experiment,
`D:/repos/_work/exp_src_<repo>` (`git clone --single-branch --branch dev`), so no ref of this record, of the
predicates or of the pilot can be read through git from a worktree. Before the first dispatch `exp_prereq/`,
`exp_mut_t2/`, `exp_t2beh/` and `exp_t2cov/` are moved out of `D:/repos/_work/`, and the reviewers' probe trees
are deleted from the session scratch directory; `exp_accept/` holds the `accept/` files of
this record only: the four acceptance scripts and `t2_preserved_test.py`, which `accept_t2.sh` runs.
The predicate scripts (`predicates/`, with `t2_corrected_test.py`) are run by the orchestrator from this record
after a cell's final tree is saved, never before, and their output goes to the ledger only.

## TASK blocks

### TASK-t1

```
Repository: jarness, a linked git worktree at {W}, baseline 3fb6fe0b78228a5d09e07641cc5443020fabea56 (detached).
Work only inside {W}. Read nothing under D:/repos/_work/ outside {W} except what your role block names; never read
or write ~/.claude. Do not commit, push, branch, stash, checkout or reset. Use `git -C {W}` and absolute paths.
Never `python -c`, `python -` or a heredoc for code: write a file and run it by path; pytest always with
`-p no:cacheprovider --basetemp=D:/pytest_temp/<a name of yours>`.

Todo item (artifacts/todo_stack.md at the baseline), verbatim:
  - T-82 Lane J. `selfcheck.py` reports a required hook that `settings.json` does not wire (P-26: six entries were
    absent on vwin-pc for four days and nothing said so). The required set is the Hook wiring table of
    `harness/README.md`; one home, read by the check. Closes when: a test with a `settings.json` lacking
    `SubagentStop` fails on the old code and passes, and selfcheck on vwin-pc lists the missing entries or none.
Scope: the check and its test, in the worktree. The run on vwin-pc is not part of this task.
Rules: a bug becomes a failing test first: the new test must fail on the baseline's `harness/selfcheck.py` and
pass on yours. Make the smallest change that closes the item. Only files under `harness/` and `artifacts/` may
change. An imported claim is a hypothesis: where the item differs from the tree, the tree wins and the report says
so. Invent no value: every path, symbol and number you write is read from the tree.
```

### TASK-t2

```
Repository: jnwb, a linked git worktree at {W}, baseline ac995ddee147c4d6aa78ba15ecda7a998cd70a00 (detached).
Work only inside {W}. Read nothing under D:/repos/_work/ outside {W} except what your role block names; never read
or write ~/.claude. Do not commit, push, branch, stash, checkout or reset. Use `git -C {W}` and absolute paths.
Never `python -c`, `python -` or a heredoc for code: write a file and run it by path; pytest always with
`-p no:cacheprovider --basetemp=D:/pytest_temp/<a name of yours>`.

Todo item (artifacts/todo_stack.md at the baseline), verbatim:
  - 17-95: the markdown table cell splitter is written 8 times in `scripts/` and only `build_dashboard.py:342`
    honours escaped pipes; 13 `_git` wrappers across tests and scripts. Check: one `cells()` and one `git()` each,
    `harness_gate.py` 22 of 22 and the named tests pass.
Scope: the cell-splitter half only. Leave the `_git` wrappers alone. The 8 are 5 function definitions and 3 inline
splits; after the change `scripts/` has one cell splitter, it honours escaped pipes, and every former site uses it.
Rules: behaviour is kept: the gate's outputs and the tracked tables it writes stay byte-equal. Make the smallest
change that closes the scope. Only files under `scripts/` and `tests/` may change. An imported claim is a
hypothesis: where the item differs from the tree, the tree wins and the report says so. Invent no value.
```

### TASK-t3

```
Repository: jnwb, a linked git worktree at {W}, baseline ac995ddee147c4d6aa78ba15ecda7a998cd70a00 (detached).
Work only inside {W}. Read nothing under D:/repos/_work/ outside {W} except what your role block names; never read
or write ~/.claude. Do not commit, push, branch, stash, checkout or reset. Use `git -C {W}` and absolute paths.
Never `python -c`, `python -` or a heredoc for code: write a file and run it by path; pytest always with
`-p no:cacheprovider --basetemp=D:/pytest_temp/<a name of yours>`.

Todo item (artifacts/todo_stack.md at the baseline), verbatim:
  - 17-97: `test_batch_a_regressions.py`, `test_independent_audit_semantics.py`, `test_integration_0_2_1.py`,
    `test_audit_reproducers.py` are named by event; 29 same-subject files (`test_rng_*` 4, `test_vflip2*` 6,
    `test_xflip*` 7, `test_zflip*` 3, `test_api_md_*` 3, ...) split 3 to 7 ways. Check: merged by subject with the
    collected test count unchanged.
Scope: the `test_rng_*` group only: its 4 files become one file, with the same tests under the same names.
Rules: no test is added, dropped, renamed or weakened. Only files under `tests/` may change. An imported claim is
a hypothesis: where the item differs from the tree, the tree wins and the report says so. Invent no value.
```

### TASK-t4

```
Repository: jynx, a linked git worktree at {W}, baseline bc72f27bbd36e0625e116fe6e76e1f7ecd8c98fe (detached).
Work only inside {W}. Read nothing under D:/repos/_work/ outside {W} except what your role block names; never read
or write ~/.claude. Do not commit, push, branch, stash, checkout or reset. Use `git -C {W}` and absolute paths.
Never `python -c`, `python -` or a heredoc for code: write a file and run it by path.

Task: `artifacts/state.md` is 9,003 bytes; `scripts/artifacts_check.py` caps it at `STATE_MAX_BYTES = 6000`. Bring
it to at most 6,000 bytes.
Rules: no pointer is lost: every commit SHA and every `O-`, `T-`, `P-` id that the file holds at the baseline stays
in it or in a tracked file under `artifacts/`. The file stays true to the tree: change no fact, number or status.
Only files under `artifacts/` may change. Invent no value.
```

## ACCEPT blocks (appended only to the role blocks marked "+ACCEPT")

### ACCEPT-t1

```
Acceptance command: `{ACC}`. You may read that script. It prints one line per command and ends `ACCEPT_RC=0` when
all passed. On the baseline it prints:
  rc=0 | python harness/lint.py | markers      gate   0 findings
  rc=0 | python harness/audit.py --selftest | selftest ok
  rc=0 | python -m pytest harness/hooks -q -p no:cacheprovider --basetemp=D:/pytest_temp/exp_t1_accept_<tree name> | 39 passed in 7.77s
  selfcheck test files: harness/test_selfcheck.py
  rc=0 | python -m pytest harness/test_selfcheck.py -q -p no:cacheprovider --basetemp=D:/pytest_temp/exp_t1_accept_selfcheck_<tree name> | 9 passed in 2.05s
  ACCEPT_RC=0
```

### ACCEPT-t2

```
Acceptance command: `{ACC}`. You may read that script. It prints one line per command and ends `ACCEPT_RC=0` when
all passed. It takes about four minutes: run it in the foreground with a 10-minute timeout. On the baseline it prints
(the times and the warning count vary; the rc values and the passed counts are what must hold):
  harness_gate rc=0 last: ALL HARNESS GATES PASSED. 22 of 22 gates executed.
  pytest rc=0 last: 1527 passed, 4 skipped, 1 warning in 202.40s (0:03:22)
  table rows rc=0 last: 56 passed in 2.74s
  ACCEPT_RC=0
```

### ACCEPT-t3

```
Acceptance command: `{ACC}`. You may read that script. It prints one line per command and ends `ACCEPT_RC=0` when
all passed. It takes several minutes: run it in the foreground with a 10-minute timeout. On the baseline it prints:
  201 passed, 10804 deselected, 43 warnings in 103.20s (0:01:43)
  11005 tests collected in 18.69s
  ACCEPT_RC=0
```

### ACCEPT-t4

```
Acceptance command: `{ACC}`. You may read that script. It prints one line per command and ends `ACCEPT_RC=0` when
all passed. On the baseline it prints:
  # map: goal_stack=artifacts/goal_stack.md; todo_stack=artifacts/todo_stack.md; problem_stack=artifacts/open_stack.md; fact_stack=artifacts/fact_stack.md; state=artifacts/state.md; memory=artifacts/memory.md; agents=artifacts/agents.md
  9003 artifacts/state.md
  ACCEPT_RC=0
(the check reports the size as a minor finding and still exits 0: the second line is the size).
```

## Role blocks (the same text for every task)

### A-worker (agent `worker`, effort high) +ACCEPT

```
Role: writer. Close the task above in {W}, the whole of it. Run the acceptance command once, at the end.
Report: RESULT / CHANGES (paths, lines) / COMMANDS with their summary lines / OPEN; mark each claim observed or
inferred; say what you did not do.
```

### B-helper (agent `worker`, effort medium)

```
Role: helper. Change nothing in {W}. Reproduce on disk what the task above states and return an evidence table for
the writers: for each statement, what the tree shows (path:line and the exact text or value, read with a command),
and whether the statement holds. At most 300 words.
```

### B-worker (agent `worker`, effort high; sent to worker 1 with {W} = {W1} and to worker 2 with {W} = {W2})

```
Role: writer. Close the task above in {W}, the whole of it. Another writer does the same in another worktree; a
keeper takes one of the two. The helper's evidence table (verify what you use):
<helper report>
Report: RESULT / CHANGES (paths, lines) / COMMANDS with their summary lines / OPEN; mark each claim observed or
inferred; say what you did not do.
```

### B-keeper (agent `worker`, effort high) +ACCEPT

```
Role: keeper. Two writers each attempted the task above in their own worktree, {W1} and {W2}; you may read both.
Their reports:
<reports>
Run the acceptance command on each attempt: the command above with {W1} in place of {W}, then with {W2}. Take the
attempt whose run ends `ACCEPT_RC=0`; if both do or neither does, take {W1}'s. Bring the taken attempt into {W}:
1. `git -C <taken> diff --binary > D:/pytest_temp/keep_<name of {W}>.diff`; unless that file is empty,
   `git -C {W} apply D:/pytest_temp/keep_<name of {W}>.diff`.
2. Copy every file that `git -C <taken> status --porcelain --untracked-files=all` lists with `??` to the same
   relative path in {W}.
3. Read the result: `git -C {W} status --porcelain` must list the same paths with the same marks as the taken
   attempt's.
In this step change nothing else and do not improve the taken attempt.
Report: RESULT (which attempt and why, with both ACCEPT_RC lines) / CHANGES / COMMANDS with their summary lines /
OPEN; mark each claim observed or inferred.
```

### B-checker (agent `checker`, check mode)

```
Check mode on the lines that the uncommitted change in {W} adds (`git -C {W} diff`, and untracked files): apply
the match skills that fit each file. You may edit only those added lines. Meaning, numbers, paths, symbols, rules
and behaviour are invariant. Report each edit as before -> after, or "no edit", and anything you saw and did not
change.
```

### B-critic (agent `worker`, effort high)

```
Role: critic. Change nothing. Score the uncommitted change in {W} against the task above on the W8 work ontology.
Read D:/repos/_work/ocma/method/work_ontology.md and D:/repos/_work/ocma/method/ontology_core.md (these two files
only, outside {W}). Score each of the eight factors on its scale, null where it does not apply, citing file:line
or a command and its output for every non-zero score. Return one JSON object: {"scores": {<key>: number|null,
...}, "evidence": {<key>: text}, "W": number, "merge": true|false, "notes": text}, then every defect you found, one
per line with file:line.
```

### REVIEW (agent `reviewer`, Sonnet 5.5, medium; the same text in arm A and arm B) +ACCEPT

```
Independent review of the uncommitted change in {W} against the task above. You did not write it. Do not edit the
tree. Read `git -C {W} status --porcelain` and `git -C {W} diff`. Check that the task is closed as its scope says,
that its rules hold, that only the allowed files changed, and that every path, symbol and number in the added
lines exists in the tree with that value. Run the acceptance command once. Verdict first: ACCEPT or REVISE. Then
findings, one per line, each with file:line and the evidence. At most 300 words.
```

### FIX (sent to the writer of the final tree, resumed: arm A the worker, arm B the keeper; always, once) +ACCEPT

`<reports>`: every report of the formation so far, in dispatch order (arm A: worker, reviewer; arm B: helper,
worker 1, worker 2, keeper, checker, critic, reviewer).

```
Reports on the change in {W}, verbatim:
<reports>
For each finding in them: repair it in {W} under the task's rules, or say with evidence why it does not hold. If
nothing needs repair, say so and change nothing. Run the acceptance command once. Report: RESULT / CHANGES (paths,
lines) / COMMANDS with their summary lines / OPEN; mark each claim observed or inferred.
```

If the harness cannot resume the writer, a fresh agent of the same type and effort gets `TASK-t<n>`, then the one
line `Role: writer of the change in {W}; an earlier writer made it and cannot continue.`, then the FIX block and
`ACCEPT-t<n>`; logged, both runs recorded.

### CLOSING (agent `reviewer`, Sonnet 5.5, medium, fresh; the same text in arm A and arm B) +ACCEPT

`<reports>`: the same reports the FIX block carried, in the same order; the fix round's report is not among them
(PREREG: the closing review "receives the same reports").

```
Independent closing review of the uncommitted change in {W} against the task above. You did not write it. Do not
edit the tree. Earlier reports on this change, verbatim:
<reports>
Read `git -C {W} status --porcelain` and `git -C {W} diff`. For each finding in the reports say whether the tree
now has it. Then check the task as a whole: closed as its scope says, rules held, only the allowed files changed.
Run the acceptance command once. Verdict first: ACCEPT or REVISE. Then findings, one per line, each with file:line
and the evidence. At most 300 words.
```

## Evaluation blocks (outside both arms; after all eight cells have final trees)

Labels `p`, `q` per task from `exp_scrub.py labels <n>`. Evaluation trees are linked worktrees of a clone made for
evaluation only, `D:/repos/_eval/src_<repo>` (`git clone --single-branch --branch dev`), at the baseline, with the
scrubbed diff applied uncommitted and untracked files copied: `D:/repos/_eval/eval_t<n>_<p|q>_pre` and
`D:/repos/_eval/eval_t<n>_<p|q>`. Nothing of an arm is under `D:/repos/_eval/`, and no arm worktree is registered
in that clone. `<TASK text>` is the TASK block from its `Todo item` or `Task:` line to its end (the first
paragraph, which names worktree rules, is left out), under the line `Repository: <repo>, baseline <SHA>.` Classes:
wrong-behaviour (code that does the wrong thing), wrong-pointer (a pointer that does not resolve to what it
names), wrong-value (a path, symbol or number the tree does not have), meaning-change (a rule, fact or obligation
added, removed or altered), scope (a change outside the task's allowed files or scope), incomplete (a part of the
task not closed), style.

### EVALUATE (evaluator 1: agent `reviewer`, model sonnet, effort high; evaluator 2: opencode Muse through `delegate-cli`, tier review, read-only, `--dir D:/repos/_eval`; one packet per task)

```
Two independent attempts at one task, p and q. Each has two snapshots of an uncommitted change on the same
baseline: an earlier one and a final one. Trees: p earlier {P_PRE}, p final {P}, q earlier {Q_PRE}, q final {Q}.
You know nothing else about how they were made. Read only these four trees; do not edit any tree and run no
command that writes.
<TASK text>
Defect classes: <classes>
For each of the four trees separately, list every defect you can establish from the tree. Output only these lines:
DEFECT | <p|q> | <pre|final> | <file> | "<a line quoted verbatim from the tree or its diff>" | <class> | <one sentence>
then `COUNT | <number of DEFECT lines>`. A defect present in both snapshots of an attempt gets one line per
snapshot.
```

### EXTRACT (agent `reviewer`, Sonnet 5.5, medium; one per task; judges nothing)

```
Below are reports written about two attempts at one task, p and q, each report under its id. Do not judge whether
any claim is true and drop none. For each report, write every distinct claim that the attempt's tree has a defect
as one line:
CLAIM | <report id> | <p|q> | <file> | "<the line or phrase the report quotes or points at, or empty>" | <one sentence naming the defect>
The sentence names the defect only, in neutral words: no role, no agent, no step of a process, no count of people
or reports. A report that claims no defect gets `NONE | <report id>`. A statement that something is correct is not
a claim. Output only these lines, then `COUNT | <number of CLAIM lines>`.
<scrubbed reports of p, then of q>
```

### ADJUDICATE (agent `reviewer`, model sonnet, effort high, fresh; one per task; blind)

```
Two independent attempts at one task, p and q. Each has an earlier and a final snapshot of an uncommitted change
on the same baseline. Trees: p earlier {P_PRE}, p final {P}, q earlier {Q_PRE}, q final {Q}. You know nothing else
about how they were made. Read only these four trees; do not edit any tree and run no command that writes.
<TASK text>
Defect classes: <classes>
Candidate defects, each with an id, gathered from several sources of unknown reliability; some are false, some
repeat each other:
<candidates of p, then of q, as `CAND | <id> | <p|q> | <file> | "<quoted>" | <sentence>`>
For each attempt build a table with one row per distinct defect. Check every candidate against the trees yourself.
Assign every candidate id to exactly one row of its attempt; a row holds at least one candidate. Output only these
lines:
ROW | <p|q> | <row number> | <real on earlier: yes|no> | <real on final: yes|no> | <class> | <source> | <candidate ids, comma separated> | <one sentence>
<source> is one of: task-text (caused by the task text itself), baseline-outside (already in the baseline and
outside the task's target), baseline-inside (in the baseline, inside the task's target, left unrepaired), arm
(introduced by the attempt), none (the row is real on neither snapshot). A row real only on the final snapshot has
source arm.
Add no row of your own. If you notice a defect that no candidate names, write it after the table, outside it:
NOTE | <p|q> | <pre|final|both> | <file> | "<quoted line>" | <one sentence>
```

`NOTE` lines are exploratory observations (Hamm 2026-11-15): kept whole in the ledger, in no table, in neither `V`
nor the inventory, credited to no arm.

### GUESS (sent to each evaluator and to the adjudicator, resumed, after its output passed its script; Muse through `--session`)

```
One more question; it changes nothing above. The two attempts were made by teams of different size. Output one
line: `GUESS | <p|q|cannot tell>`, the attempt you believe the larger team made.
```

## Scripts (frozen with these packets)

| Script | Does |
|---|---|
| `exp_scrub.py` | `labels`: the arm's label per task from the frozen seed; `reports`: replaces agent ids and role words with `AGENT` and arm worktree names with `TREE`, gives each report an opaque id in shuffled order, writes the key; `diff`: replaces agent ids (token only) in the evaluation copy, logs added lines that hold a role word |
| `exp_candidates.py` | parses the two evaluators' `DEFECT` lines and the extractor's `CLAIM` lines, pools them per label in shuffled order under opaque candidate ids without source, class or snapshot, writes the candidates and the key; refuses a miscounted or malformed output and a report with neither `CLAIM` nor `NONE` |
| `exp_table_check.py` | refuses an adjudicator table that leaves a candidate out, uses one twice, holds a row with no candidate, uses an unknown class or source, gives a real row the source `none` or a false row another, or gives a row real only on the final snapshot a source other than `arm` |
| `exp_scripts_test.py` | controls: each script accepts a valid case and refuses each broken one |

A refused evaluator, extractor or adjudicator output is returned once to the same agent with the script's refusal
lines and the words "Output the lines again in the required form; change no judgment."; a second refusal is
recorded and that output adds nothing. This is outside both arms and its cost is evaluation cost.

Readings fixed here and not in `PREREG.md` (listed in `FREEZE.md` as qualifications): an evaluator's defect listed
on both snapshots is one candidate; a table row holds at least one candidate (Hamm 2026-11-15: the adjudicator is
candidate-only; what it notices beyond them is a `NOTE` outside the scored comparison); a false row carries the source `none`; labels are `random.Random(2026111500 + n).choice("pq")` for arm
A, the other for arm B (T1 A=q, T2 A=p, T3 A=q, T4 A=q); evaluation trees live under `D:/repos/_eval/`; the guess
is asked in a second step, so the first packet does not say that team size differs.
