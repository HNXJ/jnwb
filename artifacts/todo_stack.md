# 0.2.13

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. This
stack holds the current window only; the rest of 0.2.13 and later is one row per item in
`artifacts/roadmap.md`, and an item moves here with its full text when its lane opens. 0.2.12
closed on 2026-10-14 with every item done or ruled to 0.2.13 (`git log -- artifacts/todo_stack.md`,
`artifacts/rulings/2026-10-14.md`).

Theme (ruled 2026-10-19): inference and refusal correctness: the 2026-10-18 audit's repairs, the
rulings of 2026-10-18 and 2026-10-19, and 12-10. Acceptance: `artifacts/goal.md` and `AGENTS.md` §11.

Every item here carries `deferred-0.2.13`, the one deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.12 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

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

Three lanes run at once; a wave opens when the lanes it depends on have merged. Full suites run
one at a time; on the maintainer's machine through its local `suite_lock.py`, elsewhere as `python -m pytest tests/ -q`.

| Wave | Lane | Items, in order | Owns | Waits for |
|---|---|---|---|---|
| 1 | L laminar | 15-11 | `scripts/vflip2_recovery.py`, `tests/test_vflip2_recovery.py`, `artifacts/evidence/0.2.13/vflip2_recovery.*` | Andre Bastos's simulation code |

### 15-11 `vflip2` recovers a planted vFLIP2 crossover

Release: deferred-0.2.13.
Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: Andre Bastos's simulation code.
Writes: `scripts/vflip2_recovery.py`, `tests/test_vflip2_recovery.py`, `artifacts/evidence/0.2.13/vflip2_recovery.md`, `artifacts/evidence/0.2.13/vflip2_recovery.json`.
- The generator half landed in 1dbcedbf (`synth_vflip2_crossover`, the frozen oracle, `artifacts/evidence/0.2.13/vflip2_recovery.md`: recovery 29 of 100, matched null 24 of 100, grid 63 of 100, both targets missed and untuned). The same table has not run on Andre Bastos's simulation code. Check: `vflip2_recovery.md` gains a section for his code with the six measures, intervals and `target_met`, under the contract in `artifacts/evidence/0.2.13/vflip2_generator_design.md`. Waits: needs his code; nothing shipped changes.
Accept: the CI tests the design names pass and the evidence file names entropy, counts, intervals and `target_met` for his code. Ruled 2026-10-14 (15-03 split) and 2026-10-15 (15-11 design).
