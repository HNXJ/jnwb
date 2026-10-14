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

Scope ruled 2026-10-12 (`artifacts/rulings/2026-10-12.md`, full-release scope): 0.2.12 covers
cleaning, organizing, a major doc update and the dashboard's view of each work's replications. The release waits for neither 12-21 (moved to 0.2.13, `artifacts/rulings/2026-10-14.md`) nor the contributed dashboard cards; pull request #31
(`jnwb-laminar`) merged into `dev` on 2026-10-13.

| Wave | Lane | Items, in order | Owns | Waits for |
|---|---|---|---|---|
| 5 | L laminar (focus, Hamm 2026-10-13) | 15-01, 15-03, 15-07, 15-09, 15-10, 15-08 | `jnwb/laminar/`, `tests/test_vflip2*.py`, `tests/test_xflip*.py`, `tests/test_zflip*.py`, `skills/jnwb-laminar/`, their `docs/` rows | none |
| last | Z closure | `main` merged into `dev`; the blocker pass rerun at HEAD; `release_gate.py` | the receipt | every row above |

### 15-01 Omega's dependence on every `vflip2` parameter

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: none.
Writes: `artifacts/evidence/0.2.12/vflip2_sensitivity.md`, its script, `tests/test_vflip2_sensitivity.py`.
- Omega is ln(G x S_d x B_d x channel span x n_low x n_high x bin width^2); S_d is unnormalized and the band minima count bins, so omega and acceptance move with bin width and frequency range (vFLIP2.m lines 238, 264, 454, 474 to 476). Check: on the Dryad `power_example` and 50 seeded synthetic probes, one parameter varied at a time (bin width 0.5, 1, 2 Hz; upper frequency 150, 200, 250 Hz; spacing 50, 100, 200 um by resampling; layer-4 thickness 0.4, 0.586, 0.8 mm; orientation; `omega_cut` 4, 6, 8), the evidence file tables omega, its change from the default, and acceptance flips, each value written by the script; the test pins the bin-width shift of omega to 2 ln(ratio) plus the band-count terms. Waits: not stated.
Accept: the table regenerates; the docstring states each dependence with its measured size. Ruling after: which fixed constants become parameters, defaults staying vFLIP2.m's.

### 15-03 `vflip2` recovers a known layer 4 in simulation

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: none.
Writes: `tests/test_vflip2_simulation.py`, `artifacts/evidence/0.2.12/vflip2_simulation.md`.
- No test shows `vflip2` finds a planted crossover. Check: on 100 seeded probes with a planted alpha-beta/gamma crossover at a known contact (32 contacts, 100 um), the accepted crossover lies within one contact of it in at least 90; on 100 probes with no laminar gradient, at most 5 are accepted. Waits: not stated.
Accept: both rates hold and the evidence file names seeds and counts. The same table on Andre Bastos's simulation code is 15-11 (ruled 2026-10-14).

### 15-07 Laminar anchors take `vflip2`

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: none.
Writes: `jnwb/laminar_curation.py`, its tests.
- `fuse_laminar_anchors` takes `vflip_um` and `xflip_um` but not `vflip2`'s crossover. Proposal: `vflip2_um`, set only from an accepted result, reported beside `vflip_um` and fused under the same rule. Check: an accepted `vflip2` crossover moves the fused anchor as `vflip_um` would at the same position; a rejected one leaves it unchanged. Waits: not stated.
Accept: the check passes. Ruling: Hamm 2026-10-13, `vflip2_um` sits beside `vflip_um`.

### 15-08 `vflip2` in the user docs

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: none.
Writes: `docs/laminar.md`, `README.md`.
- `docs/laminar.md` and `docs/10_operation_specifications.md` never name `vflip2`, omega or `vflip2_from_lfp`, and `README.md:15` names only laminar CSD (Muse review, 2026-10-14). Check: `docs/laminar.md` has a `vflip2` section stating its bands, omega, the cut, the 0-based rows, `vflip2_from_lfp`, and the `window=` and `orientation=` hand-off to `xflip` and `zflip`, each claim matching the docstring; `python scripts/docs_build.py` passes. Waits: not stated.
Accept: the check passes.

### 15-09 `xflip`'s layer-4 thickness and window message

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: none.
Writes: `jnwb/laminar/_xflip.py`, `tests/test_xflip_window.py`.
- `xflip`'s default `min_block_size` uses `LAYER4_THICKNESS_MM` (`_xflip.py:645-650`) while `vflip2` takes `layer4_thickness_mm` (`_vflip2.py:294`), so a non-default thickness gives the two different shortest windows; the out-of-probe message echoes the unsorted pair (`_xflip.py:114-115`). Check: `xflip(..., contact_spacing=100, layer4_thickness_mm=0.8)` defaults `min_block_size` to 8, and the message for `window=(40, 3)` on 32 rows names `(3, 40)`. Waits: not stated.
Accept: the check passes; the sweep tests (`tests/test_unit_suffixed_parameters.py`, `tests/test_substitution_class_sweep.py`) pass.

### 15-10 `zflip` with two `vflip2` results

Release: deferred-0.2.12. Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: none.
Writes: `jnwb/laminar/_zflip.py`, `tests/test_zflip_window.py`.
- `zflip(window=a, orientation=b)` with two different accepted `VFlip2Result`s takes the window from one and the orientation from the other without a check (`_zflip.py:362-364`, `383-386`). Check: two results whose windows or orientations differ raise ValueError; the same result passed twice is accepted. Waits: not stated.
Accept: the check passes.
