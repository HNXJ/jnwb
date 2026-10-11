# 0.2.11

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. This
stack holds the current window only. Cycles 0.2.12 to 0.2.14 are one row per item in
`artifacts/roadmap.md`, and the full text of each is in `artifacts/archive/0.2.10/todo_stack_0.2.10.md`,
the stack as it stood when 0.2.10 closed. The previous cycle's record is
`artifacts/archive/0.2.9/todo_stack_0.2.9.md`, with its closure receipt beside it.

Theme: interpretation, routing and documentation hold: every interpretational pitfall has a
synthetic test, every skill points to its sources and composes with the router, displays and
documented call shapes are checked, and the identity and scientific-choice facts are held.

Acceptance: `AGENTS.md` §11; the router
composes the minimal skill set for each chain the composition tests run; each published unit measure is a public
operation by its published definition or a ruled exclusion.

Every item here carries `deferred-0.2.11`, the one deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.10 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

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
| C interpreter legs | 11-44 | 0.5 h at the 0.2.11 version bump, then one CI run | `.github/workflows/workflow.yml`, `pyproject.toml`, `scripts/harness_gate.py`, `README.md`, `docs/install.md`, `docs/index.md`, `scripts/release_gate.py`, `tests/test_ci_conclusion_gate.py`, `tests/test_workflow_release_policy.py`, `tests/test_readme_smoke.py`, `tests/test_gate8_covers_every_version_surface.py` |
| K reductions | 11-48 | 2 h, two worktrees (docs; tests) | the files each site names |

The identity and scientific-choice facts (10-10, 11-06, 09-04, 11-32, 11-07) moved to 0.2.12 on
2026-10-11 (`artifacts/rulings/2026-10-11.md`). ETAs are estimates of wall time with one worker per lane.

### 11-44 Python 3.15 is tested but not declared

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: none. Blocked by: the 0.2.11 version bump.
Writes: `.github/workflows/workflow.yml`, `pyproject.toml`, `scripts/harness_gate.py`, `README.md`, `docs/install.md`, `docs/index.md`, `scripts/release_gate.py`, `tests/test_ci_conclusion_gate.py`, `tests/test_workflow_release_policy.py`, `tests/test_readme_smoke.py`, `tests/test_gate8_covers_every_version_surface.py`.
- Ruled 2026-10-11: 3.15 joins the blocking matrix on Ubuntu and the classifiers, gate 8 unchanged; it waits for the version bump, since gate 8 refuses a tested version that is not declared and the release-body check refuses a classifier the 0.2.10 notes lack. Do: apply `artifacts/evidence/0.2.11/py315-blocking.patch` (matrix, exclude-aware `required_ci_jobs`, docs), add 3.15 to the classifiers and `PYTHON_SUPPORTED`. Check: gate 8 passes and the non-blocking job is gone.
Accept: one `dev` run with a green Ubuntu 3.15 leg in the blocking matrix. Stop: a dependency pin would change a supported version.

### 11-48 The compression audit's approved reductions

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: per lane, named in `artifacts/rulings/2026-10-11.md` (compression row).
- Approved 2026-10-11: (1) docs duplicates to pointers, stale `CONTRIBUTING.md` paths, the version-claim test reads `docs/**`; (2) CHANGELOG blocks 0.2.9, 0.2.8, 0.2.5, 0.2.4 and 0.1.0 to 0.1.7 to an archive; (3) the tutorial_00 cached runs and parametrized tables. Steps 4 and 6 moved to roadmap 12-13. Check: each lane's collected test count and every assertion survive, and the full suite and harness pass. Waits: no shipped number changes.
Accept: the check passes. Stop: a cut would drop a fact, ruling or receipt a file cites, or change a public result.
