# 0.2.6 blocker graph

Derived 2026-09-21 from the rows classified `BLOCKER` in `artifacts/problem_stack.md`. Every
blocker appears exactly once. The partition is mechanical -- each row was placed by a signal read
off its own text, printed with the row, so a wrong placement is visible rather than silent.

| Kind | Blockers | Meaning |
|---|---|---|
| `OWNED` | 22 | a live item already claims it; execute that item |
| `EXECUTE` | 27 | no owner and no stated human dependency; needs a node |
| `RULING` | 10 | the row itself says a human decision decides it |
| `GRANT` | 2 | blocked on corpus access, which is Hamm's to give |

61 blockers, 52 live items. The first pass left a fifth bucket, `OWNED?` -- the row named a live
item but not in a position the ownership pattern recognised. All of them are settled here by
reading them, and the pattern itself was wrong rather than merely narrow: **the column is named
"Answered in", so a bare item id standing alone in that cell IS the ownership pointer.** P-02,
P-04 and P-06 each carry nothing else. The pattern looked only for phrases (`owned by`,
`claimed by`, `belongs to`) and so missed the commonest form -- the same blind-spot mistake the
two-tier check was written to avoid, reintroduced inside the fix for it. `_BARE_POINTER` in
`scripts/release_gate.py` is the repair.

Two placements changed on a second reading, and both were mine:

| Row | First placement | Correct placement | What the row actually says |
|---|---|---|---|
| P-151 | `EXECUTE` | `OWNED` by 06-106 | "The gate half is outstanding and is now 06-106" -- an ownership claim in prose the pattern does not match |
| P-161 | `EXECUTE` | repaired, Tier 1 | it asks for the problem-to-item check that landed this cycle, including the narrowing it proved necessary |

## Tier 0 --- nothing below Tier 2 can start without these

Hamm holds all of them. They are listed with what each unblocks, because the cost of a pending
decision is the subgraph it freezes, not the decision itself.

| # | Decision | Freezes |
|---|---|---|
| D1 | Corpus access on `D:` | `GRANT` blockers P-54, P-84; items 06-31, 06-32, 06-99; node N7 |
| D2 | NWB-writing in the goal statement vs `artifacts/goal.md` §5 | the acceptance set itself, and therefore what "required" means for every item |
| D3 | §11 condition 2's artifact | node N4 entirely (P-118, P-127, P-128, P-131) |
| D4 | `hnxj.github.io/jnwb` --- delete Pages or add a deploy job | the "available remotely" clause of the goal |
| D5 | The seven ruling items | 06-05, 06-13, 06-67, 06-92, 06-101 and `RULING` blockers P-03, P-34, P-42, P-45, P-68, P-91, P-93, P-96, P-105, P-162 |

`RULING` blockers map onto D5 except where noted: P-93 needs a reading of `AGENTS.md` §8 on
whether an additive public API change requires a CHANGELOG entry and a deprecation path; P-96 is
the five synonym pairs; P-68 is a false claim inside a Hamm-ruled slot and so cannot be repaired
by an agent; P-91 changes a shipped return shape.

## Tier 1 --- already repaired this cycle; close, do not execute

| Blocker | Evidence | Disposition |
|---|---|---|
| P-19 | `docs/10_operation_specifications.md` typed the return as `Dict[int, str]` "mapping channel index"; the code was already the general `Dict[Any, str]`, and the dict is keyed on `probe_geometry.channel_ids`, which are identifiers and are `str` under `synth_laminar_motif`. Only the page was wrong. | `repaired` --- and this is what freed item 06-77 for deletion, since P-19 was the one open row naming it as owner |
| P-168 | `tests/test_state_reconstruction.py` collects 8 tests under `--import-mode=importlib -o pythonpath=`, the installed-wheel leg's flags; `tests/test_test_imports_survive_the_wheel_leg.py` is the standing guard | `repaired` |
| P-126 | All four surfaces now state 16 (`AGENTS.md:34`, `:204`, `CONTRIBUTING.md:59`, `artifacts/agents/docs-harness.md:16`) against the `GATES` registry, and `tests/test_every_gate_runs.py:192` pins `len(GATES) == 16` | `DEFERRED->0.2.7` --- the claim is now true, so no blocker clause holds; the missing check is one that reads the *documented* counts, which is the preventive layer, not the instance |
| P-115 | **N1 executed.** `jnwb/_layout.py` `require_channel_major` refuses an array whose named axis cannot be a probe's channel axis, on two independent physical bounds: `MAX_LAMINAR_CHANNELS` (1024, against 384 simultaneously recorded sites on the densest device in wide use) and `MAX_PROBE_SPAN_UM` (100 mm, against a 10 mm shank). Two bounds because a contact count under the limit can still imply an impossible shank. The strict xfail on `test_h2_the_time_major_default_spelling_must_raise_or_agree` now XPASSes for both consumers and is removed | `repaired` |
| P-116 | **N1 executed.** `require_trial_length` refuses a trial too short to carry the estimator's own lag structure. Pooling is what hid this: 400 trials of 7 samples supply thousands of design rows in total, so nothing downstream was short of data. The other three estimators are raised to `phase_slope_index`'s standard rather than its standard being lowered -- its refusal test still passes. The strict xfail now XPASSes for all three and is removed | `repaired` |
| P-117 | **N1 executed.** The guard sits in `channel_correlation_matrix`, where rows stop being channels, not in the verdict downstream. Reproduced exactly with the guard removed: (6000, 64) in, a (6000, 6000) matrix out, a 6000-entry verdict flagging 0 "channels", all finite, no error. The strict xfail now XPASSes and is removed | `repaired` |
| P-112 | **N2 executed.** `gaussian_smooth_rate` reports rather than refuses -- the row left the direction open and reporting is the non-breaking half. The spread is measured on the output, not predicted from sigma, because the kernel's reach is truncated at an array edge and a computed radius would overstate the loss exactly where it occurs. No `nan_policy` parameter was added: P-93 is the open ruling on additive API changes, and warning needs none. 17 interior / 9 at an epoch edge stay pinned separately | `repaired` |
| P-120 | **N2 executed, and more cheaply than the row anticipated.** Its premise was that a second h5py open is needed; measured, it is not -- a lazily read series leaves `series.data` a live `h5py.Dataset`, so `series.data.attrs['unit']` returns the stored value. `series.unit` does read `'volts'` for a file storing `'n.a.'`, as the row says. The warning now fires where the conversion is applied, not only where the contradiction is declared | `repaired` |
| P-123 | **N2 executed.** `label_layers` checks the result structurally and *first*: the defect lived in the ordering, since `or` short-circuits and the missing field was never read in the ordinary `accepted=False` case. Both accepted states are pinned | `repaired` |
| P-161 | Condition 5 of STEP 0a now walks the problem-to-item direction, reading **only** the `Answered in` cell -- the narrowing P-161 proved necessary, because the problem cell carries history and a whole-row scan false-flags P-14. `_BARE_POINTER` recognises the bare-id form. Discriminated in both directions by `test_a_deferred_problem_pointing_at_a_dead_item_fails` and `..._pointing_at_a_live_item_passes`. Measured on the live stack: **0 dangling references.** | `repaired` |

## Tier 2 --- executable nodes

Eleven nodes absorb 25 of the 27 `EXECUTE` blockers; P-107 and P-156 stand alone.

**N1 and N2 are executed and their six blockers are closed** -- see Tier 1. Executed nodes are
recorded there rather than here, so a node's claim is checked against the stack's closed set
instead of taken on the node's word.

Grouping is by shared repair surface, not by theme: two blockers share a node only when one
edit closes both.

| Node | Closes | Surface | Depends on |
|---|---|---|---|
| N3 The statistics surface states its own correction | P-92, P-61 | `correlate`/`exploratory_correlate` always compute both Pearson and Spearman with no parameter naming one; six skills carry implementation authority, two of which have drifted from the code | D5 for P-91's shape |
| N4 The computational-order documents claim only what a receipt can supply | P-118, P-127, P-128, P-131 | the inventory claims verification its receipt cannot supply, `computational_order.md` cites `INV-01`..`INV-14` against it, the measurement harness behind it does not exist by the document's own words, and the ratified subset cites uncommitted receipts | **D3** |
| N5 Gate scope equals gate claim | P-95, P-98, P-150, P-159 | the vocabulary gate excludes `skills/`, `docs/api.md` and the tutorials; a published page leaks internal process vocabulary; the tutorial corpus is a closed loop two gates pass on; gate 16 cannot see a wholesale line-ending conversion | P-98 is ordered: docs rewrite, then gate |
| N6 Worktree provisioning cuts from HEAD | P-28, P-153, P-144 | every worktree is cut from `5ecc12eb` rather than current HEAD and the distance grows; six lanes were once fanned into the main tree with no isolation | --- |
| N7 The scratchpad is isolated per session | P-87, P-134 | two lanes' mutation harnesses shared one filename and a restore can target another lane's tree | --- |
| N8 A write set is closed under generation | P-173 | a lane's write set can be complete, correct and disjoint and still invalidate a generated file outside it | --- |
| N9 The stack's own summaries are derived | P-133, P-103, P-15 | a canonical summary inside the stack went stale and nothing errored; two items are honest partials that must not read as complete; `AGENTS.md` is 501 lines against a contract requiring a thin router | --- |
| N10 Gate 15 reads a field, not a sentence | P-125, P-149, P-163 | gate 15 passed on 14 items whose `Writes:` fields had been cut in half, and would pass on the repaired file for the same reason it passed on the broken one --- it reads a sentence | --- |
| N11 Every estimator records the device it ran on | P-62 | `relative_power` downgrades to CPU silently; `spectral_tilt` and `wpli` carry no device field at all, against a skill that promises both. 06-56 owns the `jnwb/` half; **the skill sentence is unowned, and skills are doctrine-adjacent --- propose the wording, do not edit it** | 06-56 for the code half |
| N12 A parallel-invariance test varies something | P-113 | `test_directed_network_is_invariant_to_n_jobs` leaves `n_surrogates=0`, so it asserts the invariance of a constant and cannot fail whatever the parallel path does. P-37 instance sixteen | --- |
| N13 `mean_of_ratios` delivers the estimand it names | P-114 | `TFRAccumulator` has already consumed the trial axis, so the ratio is formed on trial-averaged power while the call names the other estimand --- and 06-19 pins it as an exact identity, measured at `3.55e-15` over 980 interior cells | --- |

Not absorbed, and deliberately separate:

| Blocker | Why it stands alone |
|---|---|
| P-156 | An instruction to bypass the file-writing tools arrives through the MCP server-instructions channel and reaches every dispatched agent. It is not a repository defect and no repository edit closes it. It has now been declined by 11+ independent agents and by the dispatcher, repeatedly inside this session. It needs a standing decision about the channel, not a node. |
| P-107 | `06-13`'s own text is half true about `KeyError`, so the repair is inside a ruling item's text. Folds into D5. |

## Tier 3 --- existing items that own a blocker

Nineteen live items carry 25 blockers: the 22 `OWNED` rows, plus P-34, P-45 and P-105, which each
name a live item but are decided by a ruling rather than by that item. Five of the nineteen are
ruling items, so they sit behind D5.

| Item | Owns | Status |
|---|---|---|
| 06-13 | P-104, P-105 | ruling (D5) |
| 06-16 | P-21 | executable |
| 06-17 | P-02 | executable |
| 06-24 | P-99 | executable |
| 06-35 | P-06, P-09 | executable |
| 06-37 | P-04 | executable |
| 06-52 | P-26 | executable |
| 06-60 | P-37 | **the fixpoint pass itself --- runs last, by construction** |
| 06-67 | P-45, P-157, P-158 | ruling (D5) |
| 06-74 | P-12 | executable |
| 06-80 | P-53, P-57 | executable; also the gate that resolves `Skill:` and `Blocked by:` fields |
| 06-82 | P-43, P-46 | blocked by 06-67, so behind D5 |
| 06-83 | P-56 | executable |
| 06-86 | P-34 | ruling (D5) --- the row is explicitly *not* closable by 06-86 alone |
| 06-92 | P-41 | ruling (D5) |
| 06-95 | P-110 | executable |
| 06-106 | P-151 | executable --- the gate half 06-09 could not write, since `scripts/harness_gate.py` is single-writer |
| 06-111 | P-170 | executable |
| 06-113 | P-174 | executable |

## Tier 4 --- completed items, deleted

`AGENTS.md` §2: a finished item is deleted, not ticked. Each was verified against the tree, not
against a lane's report.

| Item | Accept clause met by | Verified |
|---|---|---|
| 06-76 | `'none'` is a key of the correction map with the reason recorded at `jnwb/jrsa.py:1031` | P-50, P-51, P-52 already closed; P-31 superseded |
| 06-77 | `index_space` present 10x in `jnwb/laminar.py` plus the boundary refusal | P-49 closed; both strict xfails now XPASS and are removed |
| 06-107 | `rng` default is `42` and visible in `inspect.signature` | P-164 closed; the strict xfail flipped |
| 06-108 | `LAYER_BOUNDARY_TOL_CONTACTS` plus the three hardware pitches and the ulp/1e-9 perturbation | P-166 closed; 108-case fingerprint hashed identically |
| 06-109 | 8 tests collect under `--import-mode=importlib -o pythonpath=` | P-168 closed |

Deleting these five took the required-item count from 57 to 52 and closed one Tier 3 row.

## Tier 5 --- the fixpoint, which cannot be pulled earlier

06-60 runs one independent pass over the documentation, the code and both stacks, applying the
§11 predicate, and writes `artifacts/blocker_fixpoint_receipt.md` naming HEAD and the count of
new release-blocking problems found. The gate requires the receipt to sit at HEAD, so any commit
after the pass invalidates it --- the pass is the last action before the version bump, not a
step that can be run early and re-used.

The fixpoint is zero new **blockers**, not zero new observations. A non-blocking observation
found during the pass is recorded and carried forward without re-opening the cycle.

## The convergence question, stated as a measurement

Whether this terminates is decidable from one number, and it is not known yet: how many of the
33 `EXECUTE` blockers a node closes without introducing one. Across 0.2.6 the open count went
29 -> 101 while the item count stayed flat, so the historical rate of new-blockers-per-repair in
this repository is **above** one.

The amendment makes the criterion convergent in principle by excluding non-blocking discovery
from the fixpoint. It does not make it convergent in fact: that depends on the rate being below
one. Thirteen nodes is a small enough batch to measure it directly rather than argue it.
