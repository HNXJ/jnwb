# 0.2.13

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. This
stack holds the current window only; the rest of 0.2.13 and later is one row per item in
`artifacts/roadmap.md`, and an item moves here with its full text when its lane opens. 0.2.12
closed on 2026-10-14 with every item done or ruled to 0.2.13 (`git log -- artifacts/todo_stack.md`,
`artifacts/rulings/2026-10-14.md`).

Theme and acceptance: `artifacts/goal.md` and `AGENTS.md` §11, until Hamm rules the 0.2.13 theme.

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
one at a time through `C:/Users/nejath/.claude/bin/suite_lock.py`.

| Wave | Lane | Items, in order | Owns | Waits for |
|---|---|---|---|---|
| 1 | L laminar | 15-11 | `jnwb/testing/synth.py`, `tests/test_vflip2*.py`, `scripts/vflip2_simulation.py`, `artifacts/evidence/0.2.13/` | a generator; Andre Bastos's simulation code for its second half |

### 15-11 `vflip2` recovers a planted vFLIP2 crossover

Release: deferred-0.2.13. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: none.
Writes: `jnwb/testing/synth.py`, `scripts/vflip2_simulation.py`, `tests/test_vflip2_simulation.py`, `artifacts/evidence/0.2.13/vflip2_simulation.md`.
- No generator plants vFLIP2's own relative-power crossover, so no test shows `vflip2` recovering it: on `synth_laminar_motif` (amplitude-weight crossover) 20 of 100 accepted crossovers lie within one contact and 18 of 100 noise-only probes are accepted at omega_cut 6 (`artifacts/evidence/0.2.12/vflip2_simulation.md`). Check: on 100 seeded probes from a generator whose planted crossover is where the relative band-power profiles cross (32 contacts, 100 um), the accepted crossover lies within one contact in at least 90, and at most 5 of 100 noise-only probes are accepted; the same table then runs on Andre Bastos's simulation code. Waits: needs the generator and his code; 0.2.12 ships the characterization only.
Accept: both rates hold and the evidence file names seeds and counts. Ruled 2026-10-14 (15-03 split and characterization).
