# 0.2.12

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. This
stack holds the current window only; the rest of 0.2.12 to 0.2.14 is one row per item in
`artifacts/roadmap.md`, and an item moves here with its full text when its lane opens. 0.2.11
closed on 2026-10-11 with every item done (`git log -- artifacts/todo_stack.md`).

Theme and acceptance: `artifacts/goal.md` and `AGENTS.md` §11, until Hamm rules the 0.2.12 theme.

Every item here carries `deferred-0.2.12`, the one deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.11 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet, in the contract of `artifacts/skills/jnwb-fact-action` §5; role `jnwb-developer` unless named | a batched packet redefines the hard item |
| A lane is one worktree and one writer; up to three lanes run in parallel, one Haiku worker each, when they share no file (Hamm 2026-10-10 and 2026-10-11); a lane's items run in the order listed | lanes never share a file, so they merge without conflict |
| A packet reproduces each bullet on its own tree first; a bullet that does not reproduce is deleted | non-reproduction is a result |
| The actor is never the verifier | every repair is re-run by someone else |
| The integrator owns the stacks, `CHANGELOG.md` and `docs/api.md` | packets report the disposition and the changelog text |
| Wave barrier: `python scripts/harness_gate.py` (count PASS lines), `python -m pytest tests/ -q`, commit, push, CI green on `dev` | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then `Do`, `Accept`, `Stop` as
needed; `AUTONOMY` and a one-line source or ruling note follow the fields they qualify. A bullet reads
`ID: defect, as input -> observed against expected, with numbers and units. Check: a predicate that
decides it, naming the file and the asserted value. Waits: why it cannot make release evidence
falsely pass.` `Waits:` appears in deferred cycles; `Waits: not stated.` marks a reason no source
gives, for the closure pass to classify. An item holds one defect and one check, in at most eight
lines.

## Lanes

| Lane | Items, in order | ETA (estimate) | Owns |
|---|---|---|---|
| K docs reductions | 12-14 | 1 h: rebase `lane-k1` onto the release and rerun its checks | the files 12-14 names |
| G release gate | 12-16 | 20 min | the files 12-16 names |
| C changelog vocabulary | 12-17 | 1 h, after 12-14 moves the old sections | the files 12-17 names |

### 12-14 The audit's docs and CHANGELOG reductions

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `README.md`, `CHANGELOG.md`, `docs/common_mistakes.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/documentation_form.md`, `docs/install.md`, `docs/quickstart.md`, `docs/tutorials/00_your_own_file.md`, `.github/CONTRIBUTING.md`, `tests/test_prose_version_claims_are_live.py`, `artifacts/archive/changelog_0.1.0-0.2.9.md`.
- Steps 1 and 2 of the 2026-10-11 compression audit, built on branch `lane-k1` at `dae02ac0` and not landed before 0.2.11 shipped; duplicated docs passages become links (568 words), stale `CONTRIBUTING.md` paths, the version-claim test reads `docs/**`, and CHANGELOG blocks 0.2.9, 0.2.8, 0.2.4 and 0.1.0 to 0.1.7 move to an archive (816 lines). Check: on the rebased branch the docs tests, `scripts/docs_build.py` and the harness pass, and a script shows every moved CHANGELOG line exactly once. Waits: documentation only; no shipped number changes.
Accept: the check passes. Stop: a cut drops a fact, ruling or receipt a file cites.

### 12-16 STEP 8 asserts the tutorials import the wheel

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/release_gate.py`, `tests/test_workflow_release_policy.py`.
- `release_gate.py` STEP 8 sets `JNWB_EXPECTED_PACKAGE_ROOT` but, unlike CI's tutorial step (`workflow.yml`, `assert 'clean_env' in jnwb.__file__`), never checks where `jnwb` resolves, so a tutorial that fell back to the checkout would pass. Check: before the loop, the venv run of `import jnwb` with `tutorial_env` from the staging dir prints a path under `purelib`, and a test that drops the variable makes STEP 8's check fail. Waits: no path makes a tutorial fall back today; the guard stands aside whenever the variable is set (review of `424a11be`, 2026-10-11).
Accept: the check passes.

### 12-17 Internal vocabulary leaves `CHANGELOG.md`

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: none. Blocked by: 12-14.
Writes: `CHANGELOG.md`, `scripts/harness_gate.py`, `tests/test_harness_gate.py`.
- `AGENTS.md` keeps internal process terms out of `CHANGELOG.md`, but gate 14 checks only `docs/`, and the CHANGELOG carries them (counted in the built dashboard data at `d4e6a710`: "receipt" 30, "AGENTS.md" 35, "agent" 13, "worker" 10, and kinds "Closure (second audit RG)", "Fixed (final independent audit)"); the dashboard republishes the CHANGELOG verbatim. Check: gate 14 also reads `CHANGELOG.md` with its own term list, fails on the current text and passes after the rewording, and every kind heading is one of Added, Changed, Deprecated, Removed, Fixed, Breaking, Documentation. Waits: the CHANGELOG is already public; no shipped behaviour changes (dashboard review, 2026-10-12).
Accept: the check passes. Stop: a rewording changes what an entry says shipped.

