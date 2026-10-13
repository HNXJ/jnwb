# 0.2.12

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. This
stack holds the current window only; the rest of 0.2.12 to 0.2.14 is one row per item in
`artifacts/roadmap.md`, and an item moves here with its full text when its lane opens. 0.2.11
closed on 2026-10-11 with every item done (`git log -- artifacts/todo_stack.md`).

Theme, ruled 2026-10-12: consumers first (`artifacts/evidence/0.2.12/plan.md`). Acceptance:
`artifacts/goal.md` and `AGENTS.md` §11.

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

Three lanes run at once; a wave opens when the lanes it depends on have merged. Full suites run
one at a time through `C:/Users/nejath/.claude/bin/suite_lock.py`.

| Wave | Lane | Items, in order | Owns | Waits for |
|---|---|---|---|---|
| 3 | R release tooling | 12-02, 12-03 (roadmap rows) | `scripts/release_gate.py`, `scripts/harness_gate.py`, `.github/workflows/` and their tests | none |
| 3 | S code reductions | 12-13, then 12-22 (roadmap rows) | the files each names, `skills/` | none |
| 4 | H harness | 12-05, 12-01 (roadmap rows) | `scripts/harness_gate.py`, process tests | R |
| 4 | M docs restructure | the menu by reader arrival, overlapping pages merged, every page under its ceiling | `docs/`, `mkdocs.yml` | S |
| 5 | F figures and citations | 14-01 to 14-05, 12-08 (roadmap rows) | `docs/`, `examples/tutorials/` | M |
| any | J ground truth | 12-21 | the files 12-21 names | jaxfne's excerpt |

Scope ruled 2026-10-12 (`artifacts/rulings/2026-10-12.md`, full-release scope): 0.2.12 is the full
release. Its last step rewrites the GLO showcase records as replication rows.

### 12-21 A jaxfne simulation as jnwb ground truth

Release: deferred-0.2.12.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: jaxfne delivering the excerpt.
Writes: `examples/data/jaxfne_*.nwb`, `examples/data/jaxfne_*.provenance.json`, `tests/test_jaxfne_ground_truth.py`.
- No jnwb test recovers a known coupling, delay or spectrum from a jaxfne simulation (meet 204dfdaa item 8, 2026-10-12). Check: a small NWB excerpt with a provenance file, whose simulated directed coupling and delay are stated in it, is recovered by the jnwb connectivity call within a tolerance the provenance states, and a shuffled control is not. Waits: needs jaxfne's excerpt; nothing shipped changes.
Accept: the check passes.
