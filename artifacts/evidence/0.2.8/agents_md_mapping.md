# 08-06 mapping: every rule of the old `AGENTS.md`

Old file: `AGENTS.md` at `57094a1a` (4365 words by `wc -w`). Draft:
`artifacts/evidence/0.2.8/agents_md_draft.md`. Moved text: `artifacts/evidence/0.2.8/history_additions.md`
("history" below).

Disposition: **rule** = stated in the draft, same meaning; **route** = the draft points to the one
home that states it; **history** = a reason or incident, moved to the named history section;
**map** = a row of the §0 map, which is a route and no rule.

| # | Old location | Rule or statement (condensed) | Disposition | Where now |
|---|---|---|---|---|
| 1 | preamble | This file is the only repository-level instruction file; no second rule set, no per-assistant variant; a rule not here is not a rule | rule | draft preamble |
| 2 | preamble | A project that uses jnwb keeps its own rules | rule | draft preamble |
| 3 | preamble | Public docs may describe agents, skills, routing, AI-assisted use as public capabilities; internal process terms stay out unless a public interface needs them | rule | draft preamble |
| 4 | preamble | Not in `jnwb/`, `tests/`, `scripts/`, `CHANGELOG.md`, comments, docstrings; machine-required literals excepted | rule | draft preamble |
| 5 | preamble | "A reader of the library should see a library" | history | preamble, Ruled 2026-09-19 |
| 6 | preamble | Ruled 2026-09-19 (06-02) paragraph: the previous `docs/` rule and why it changed | history | preamble, Ruled 2026-09-19 |
| 7 | preamble | Gate 14 holds `docs/` to internal-by-construction terms and lists its omissions | rule (one sentence) + history (the "decisions rather than coverage" reason) | draft preamble; history |
| 8 | §0 | 28 map rows | map | draft §0, 14 rows. Dropped as self-describing: `tests/`, `pyproject.toml`, `CHANGELOG.md`. Moved to the §2 table: the six state and direction rows. Merged: the two scripts, the two skill trees, the two agent paths, evidence with archive, `docs/references.md` into `docs/`, the two example rows. The interpreter sentence of the CI row is §6's pointer to fact R6 |
| 9 | §1 | Classify every claim | rule | draft §1 |
| 10 | §1 | execution != verification; configured != loaded != executed != verified; memory != current state | rule | draft §1 |
| 11 | §1 | Pointer files go stale silently; resolve entries against disk | rule | draft §1 |
| 12 | §1 | Prose counts go stale; re-run | rule | draft §1 |
| 13 | §1 | No claim without a receipt, in the same message, else "ran X, got Y" | rule | draft §1 |
| 14 | §1 | Running without error does not verify content; trace a number to real data | rule | draft §1 |
| 15 | §1 | Authority order on conflict; unresolved material conflict stops | rule | draft §1 |
| 16 | §2 | Five slots, one file each; this file routes and never restates | rule | draft §2 |
| 17 | §2 | A claim in two homes disagrees with itself | history | section 2, Why a claim is never restated |
| 18 | §2 | Slot table: who may edit each | rule | draft §2 table ("Holds" column dropped; each file's header says what it holds) |
| 19 | §2 | state is generated, never committed | rule | draft §2 table |
| 20 | §2 | Why committing mutable truth fails; a third of a second; P-C7 | history | section 2, Why the state file is generated |
| 21 | §2 | Regenerate rather than read a copy; `--check` | rule | draft §2 |
| 22 | §2 | A `P-` id names a row that left; the `git log -S` command | rule | draft §2 |
| 23 | §2 | `artifacts/direction.md` binds the goal slot; §3 loads it first | rule | draft §2 |
| 24 | §2 | Memory is a hypothesis, never evidence | rule | draft §2 |
| 25 | §2 | `docs/` fallback paths | rule | draft §2 |
| 26 | §2 | Todo stack grouped by version (example block) | rule (one clause) + history (the example block) | draft §2; history section 2, The todo stack's form |
| 27 | §2 | Todo holds only undone work; delete, never tick or move | rule | draft §2 |
| 28 | §2 | Git, changelog, receipts hold history; a copy goes stale | history | section 2, The todo stack's form |
| 29 | §3 | Check HEAD against the baseline first, before opening any file | rule | draft §3 Prepare |
| 30 | §3 | `verify_lane.py` does both checks and names the drift direction | rule (does both) + history (names the direction) | draft §3; history section 3 |
| 31 | §3 | Provisioner incidents 192/202/205/232, P-28, P-153 | history | section 3 |
| 32 | §3 | On difference `--ff-only`; else stop and report both SHAs | rule | draft §3 |
| 33 | §3 | Never `git reset --hard` | rule | draft §3 |
| 34 | §3 | Why not `reset --hard` | history | section 3 |
| 35 | §3 | A packet names a commit, never a distance; `verify_lane.py` refuses a distance | rule (the refusal is stated in the §3 clause "never a distance") | draft §3 |
| 36 | §3 | Loading order (1)–(9) | rule | draft §3, same order and wording of each slot |
| 37 | §3 | Order work; define acceptance; a fact is not proof of current state | rule | draft §3 |
| 38 | §3 | Review, Progress, Seal | rule | draft §3 |
| 39 | §3 | Continue while useful; stop conditions | rule | draft §3 |
| 40 | §3 | Who drives is §12, with the `max` restatement | route | draft §3 "§12 sets who drives"; the restatement is §12's own |
| 41 | §3 | Do not stop after one item / commit nothing / leave unpushed / cross a version unsealed | rule | draft §3 |
| 42 | §4.1 | No uncomputed empirical value; missing data fails loudly | route | facts S1, S9 |
| 43 | §4.2 | Logarithm last; use `aggregate_to_db` | route (+ the `aggregate_to_db` pointer kept in the table) | fact S2; router section 4 item 3 |
| 44 | §4.2 | Averaging dB biases each site | history | section 4, reasons |
| 45 | §4.3 | One-way boundary; identical with or without a project package | route | fact B1 |
| 46 | §4.3 | Project vocabulary stays out; the Gate 6 coverage note | route + history | fact B2 (UNHELD with `todo:12-07`); history section 4 |
| 47 | §4.3 | A request to encode a corpus convention is a reason to stop | rule | draft §4 |
| 48 | §4.4 | Boundary identity | route | fact I3 (ruling 2026-09-29) |
| 49 | §4.5 | Named exchangeability; `rng` taken and reported; no `np.random.seed()` | route | facts S10, S5, S11 |
| 50 | §4.6 | Device and workers change no number; GPU results say so | route | facts S6, S12 |
| 51 | §4.7 | Call the library function; widen the shape | rule | draft §4 (ruling 2026-09-29) |
| 52 | §4.7 | A retyped copy drifts | history | section 4, reasons |
| 53 | §4.8 | Coupling, direction, delay, inference distinct | route | facts S13, S8, S14 (ruling 2026-09-29) |
| 54 | §5 | Association / directionality / causality; Granger and PSI are lag asymmetry | route | router section 4 item 2; `CONTRIBUTING.md` Core scientific invariants 3 |
| 55 | §5 | Prevalence vs magnitude, decodability, mechanism | route | `CONTRIBUTING.md` Core scientific invariants 2 |
| 56 | §5 | Spikes and LFP distinct; do not pool without namespacing | rule, meaning changed by ruling Q-2 (2026-09-29) | landed `AGENTS.md` §5: never pooled, namespaced or not, with a route to router section 4 item 1; the route to `CONTRIBUTING.md` Core scientific invariants 1 is removed; history section 5 |
| 57 | §5 | wPLI, imaginary coherency, PSI reduce zero-lag sensitivity, no immunity | route | router section 4 item 8; fact S14 |
| 58 | §5 | Phase slope delay only under a verified linear relation; apparent velocity | route | connectivity skill safeguard 4; fact S13 |
| 59 | §6 | Tools table | rule | draft §6 ("Asserts" column merged into "A pass means") |
| 60 | §6 | A warning fails the publish; bare `mkdocs` forbidden | rule ("strict", "never bare `mkdocs`") | draft §6 |
| 61 | §6 | PATH may point elsewhere; `CONTRIBUTING.md` says why | history | section 6 |
| 62 | §6 | Interpreter set is a fact; Gate 8 holds the surfaces | route | fact R6 (held by gate 8) |
| 63 | §6 | Amended 2026-09-19 paragraph | history | section 6 |
| 64 | §7 | Load the skill first; where skills are tabled; repository-only skills; fact-action and review skills | rule | draft §7 |
| 65 | §7 | jnwb skill governs over a host skill | rule | draft §7 |
| 66 | §8 | `CONTRIBUTING.md` holds change rules | route | draft §8 |
| 67 | §8 | Exact paths; branch and upstream; read before delete; preserve originals | rule | draft §8 |
| 68 | §8 | Push validated checkpoints to `dev`; `main`/tag only on instruction | rule | draft §8 |
| 69 | §8 | API change: changelog, deprecation, routing rows same commit; the test checks rows | rule | draft §8 |
| 70 | §8 | Why the rows must change together | history | section 8, Routing rows |
| 71 | §8 | No secrets; stop, say so, recommend rotation | rule | draft §8 |
| 72 | §8 | One writable agent; readers may share; separate worktrees or branches | rule | draft §8 |
| 73 | §8 | 2026-09-15 zFLIP incident; the failure-mode paragraph | history | section 8, One writable agent |
| 74 | §8 | Confirm exclusive ownership or stop | rule | draft §8 |
| 75 | §8 | Unowned changes: no stash/reset/restore/checkout/reformat/`add -A` | rule | draft §8 |
| 76 | §8 | "follow the single-writer recovery protocol in `artifacts/todo_stack.md`" | rule stated inline; the pointer is dropped because it resolves to nothing (observed: no such protocol in the todo stack) | draft §8; history section 8 |
| 77 | §8 | Fan-out requests isolation; `verify_lane.py` refuses the main tree without `--allow-main-tree` | rule | draft §8 |
| 78 | §8 | Six lanes in the main checkout; P-144 | history | section 8 |
| 79 | §9 | Writing rules | rule | draft §9 |
| 80 | §10 | Recipes page and its test | route | draft §10 |
| 81 | §11 | Standing from 2026-09-19; all three at once | rule | draft §11 |
| 82 | §11 | Each names its evidence, because a condition without a check is a preference | history | section 11, Why each condition names its evidence |
| 83 | §11 | Condition 1 | rule | draft §11 (the "prose where a table belongs has not met this" clause is the "tables for comparable facts" clause) |
| 84 | §11 | Condition 2 | rule | draft §11 |
| 85 | §11 | Why Metal is declared unverified | history | section 11 |
| 86 | §11 | Condition 3; a finding that blocks nothing waits | rule | draft §11 |
| 87 | §11 | "A known issue is not a release-blocking issue" | history (already there: Condition 3, ruled 2026-09-21) | history.md as it stands |
| 88 | §11 | The three exits; the label templates; release gate derives them | rule | draft §11 |
| 89 | §11 | Required predicate, seven clauses | rule | draft §11, one sentence, clauses unchanged in meaning |
| 90 | §11 | Deferred predicate, five clauses | rule | draft §11, one sentence |
| 91 | §11 | Path is not a classifier | rule | draft §11 |
| 92 | §11 | "The question is never where a defect lives..." | history | section 11, The question the blocker predicate asks |
| 93 | §11 | Fixpoint is blocker-focused; a next-cycle finding does not reset closure | rule | draft §11 |
| 94 | §11 | "not that it finds nothing" | history | section 11 |
| 95 | §11 | No backlog laundering | rule | draft §11 |
| 96 | §11 | Conformance to an official reference suffices; tests stay | rule | draft §11 |
| 97 | §11 | "narrows what must be re-proved, not what must be exercised" | history | section 11, Conformance and the red harness |
| 98 | §11 | Report every gate as PASS/FAIL/NOT RUN/ERROR; never "not my defect" | rule | draft §11 |
| 99 | §11 | The runner ordering is not a finding | history | section 11 |
| 100 | §11 | A problem closes unfixed only when shown false; inconvenient repair never deletes a row | rule | draft §11 exits paragraph |
| 101 | §11 | Why this section is shaped as it is: history | route | draft preamble names `history.md` |
| 102 | §12 | autonomy != authority; `max` grants nothing a lower level lacks | rule | draft §12 |
| 103 | §12 | Level table | rule | draft §12 |
| 104 | §12 | The loop at `max` | rule | draft §12 |
| 105 | §12 | Stops that bind at `max`, eight | rule | draft §12 |
| 106 | §12 | "would require inventing authority" | history | section 12 |
| 107 | §12 | Not stops, nine | rule | draft §12 |
| 108 | §12 | "the work, not a reason to hand it back" | history | section 12 |
| 109 | §12 | Decision grades table; skeleton first; trade-off rule | rule | draft §12 |
| 110 | §12 | `AUTONOMY:` inheritance; narrowest wins; default `max`; rulings and release item `none` | rule | draft §12 |

## Summary

Counted by parsing the Disposition column of the 110 rows (text in parentheses and after the
first semicolon ignored):

| Disposition | Rows |
|---|---|
| rule only | 65 |
| route only | 17 |
| history only | 23 |
| rule + history | 3 (7, 26, 30) |
| route + history | 1 (46) |
| map | 1 (28 rows to 14) |

Counted on the draft as reviewed: rules kept 68, routed 18, moved to history 27. No row is
unmapped and none changes meaning in the draft. On landing, row 56 moved from route to rule and
changed meaning by Hamm's ruling Q-2, so the landed file keeps 69 rules and routes 17.

The draft in this folder is the version reviewed; the landed `AGENTS.md` differs from it only in
§5.

## Receipts

Measured on a throwaway repository holding `git archive` of `57094a1a` with the draft copied over
`AGENTS.md` (no worktree touched); scripts in the lane's scratchpad.

| Check | Command | Result |
|---|---|---|
| Size | `wc -w` | old 4365 words, draft 2265 (of which about 160 are table pipes) |
| Two homes, 4-gram Jaccard | `python scripts/measure_agents_md_duplication.py` in the copy | 117 claim-bearing sentences; DUPLICATED 0, ECHOED 2 (live file: 223, 0, 3). The echoes: the `docs_build.py` row against `CONTRIBUTING.md`, the receipt bullet against `artifacts/agents/jnwb-developer.md` |
| Two homes, line test | `_lines_in_two_skills` of `tests/test_skills_validation.py`, draft paired with the router, the fact stack, `CONTRIBUTING.md`, `artifacts/cooperation.md`, `artifacts/goal.md`, the problem stack, every `SKILL.md` and every role file (22 partners) | 0 shared lines. The live file also scores 0, so this check is not what separates them: a planted whole router line is found, the same rule planted without its bold label is not. The Jaccard measurement is the discriminating check |
| Landing | the 16 test files that read `AGENTS.md`, `-n 8`, in the copy | 614 passed, 4 skipped |
| Landing | `python scripts/harness_gate.py` in the copy | 22 of 22 gates executed, all PASS |

## Ruled 2026-09-29

| # | Ruling |
|---|---|
| Q-1 | (a): the draft lands at about 2250 words |
| Q-2 | the router's rule binds: spikes and LFP are never pooled; `AGENTS.md` §5 says so and no longer routes to the `CONTRIBUTING.md` item that permits namespaced pooling. That item is lane A's to change |
| Q-3 | approved: `AGENTS.md` lands and `history_additions.md` is appended to `artifacts/rulings/history.md`, in one commit |
| Q-4 | (a), integrator: the check is the Jaccard ratchet of `scripts/measure_agents_md_duplication.py` and `tests/test_agents_md_stays_a_router.py` |

## The questions as put

| # | Question | Options, graded |
|---|---|---|
| Q-1 | The draft is 2265 words against the item's "about 1500". Every rule is kept; the remainder is §11 (the two predicates) and §12 (levels, stops, grades) | (a) accept about 2250, 75; (b) move the §11 predicates and the §12 level table into one routed rules file to reach about 1600, 45: a second rules file is what the preamble forbids |
| Q-2 | Spikes and LFP: `CONTRIBUTING.md` allows pooling "with explicit namespace tags", the router skill says "Never pool across them"; the old §5 sided with `CONTRIBUTING.md`. The draft routes to both and resolves nothing | (a) the router's "never" binds and `CONTRIBUTING.md` is amended, 55; (b) namespaced pooling is allowed and the router is amended, 45. Scientific semantics: Hamm's |
| Q-3 | Land the draft as `AGENTS.md` and append `history_additions.md` to `artifacts/rulings/history.md` in one commit | approve, or name the rows to change |
| Q-4 | 08-06's third bullet names the line test as its check; it cannot fail on this file (row "Two homes, line test") | (a) the Jaccard ratchet of `tests/test_agents_md_stays_a_router.py` is the check, 85; (b) keep both, 40 |
