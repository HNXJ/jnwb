# 0.2.15

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.14
closed on 2026-10-27 (tag `v0.2.14`). Items run fastest first; the lanes below split them into
parallel writers that share no file.

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet (`artifacts/skills/jnwb-fact-action` §5); a lane is one clone and one Haiku 5.5 `worker`; up to three lanes at once; a lane's items run in the order listed | lanes share no file, so they merge without conflict |
| A public signature, an estimand or a skill line goes to Hamm before code, batched in one message per wave; Haiku implements a ruled signature and never chooses one | public API and skills are Hamm's |
| A packet reproduces its bullet first, writes the failing test, then the fix; a `reviewer` that did not write it verifies; the integrator commits, owns the stacks, `CHANGELOG.md` and `docs/api.md` | the actor is never the verifier |
| Wave barrier: `python scripts/harness_gate.py`, the full suite, push, CI green on `dev` at that SHA | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then one bullet:
`ID: defect with numbers. Check: a predicate naming the file and the asserted value. Waits: why.`
At most eight lines per item.

## Lanes

Speed: S is one module and one test file, M adds a public signature or several files, L needs a
design or a scan across `jnwb/`.

| Wave | Lane | Items, in order | Speed | Needs first |
|---|---|---|---|---|
| 3 | H coherence graph | 16-20 | M | nothing |
| 3 | I fact graph | 11-09, 17-05 | M | nothing |
| 3 | L suite profile, dashboard, showcase | 17-71, 17-72, 17-73 | S | nothing |
| 4 | J vocabulary, non-finite | 17-07, 17-24 scan, then repairs | L | wave 3 merged (17-07 shares `skills/jnwb-connectivity/SKILL.md` with 16-20 and `scripts/build_fact_graph.py` with 17-05) |

### 16-20 A distance-aware coherence graph

Release: required-0.2.15.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: nothing.
Writes: `tests/test_connectivity_pitfalls.py`, `docs/common_mistakes.md`, `skills/jnwb-connectivity/SKILL.md`, `artifacts/changelog.d/coherence-distance.added.md` (new fragment). Form and normalization ruled 2026-10-31: caller-side, no API change; binned distance mean.
- 16-20: `cross_area_coherence` and `network_topology` take a coherence matrix as it is, so a graph of nearby contacts or electrodes is dense from field spread alone; Nejat and Hajipour Sardouie 2021 normalize edge weights by distance and compare groups edge by edge (`docs/references.md`, Pitfalls). Check: in `tests/test_connectivity_pitfalls.py`, on a planted field with spread between nearby contacts and one planted far-pair interaction, dividing each edge by its distance-bin mean removes a spread edge that the raw graph keeps and keeps the planted far-pair edge; the fixture asserts raw near-pair coherence exceeds the threshold. Waits: raised during 0.2.14, after its scope was set (goal F3, ruled 2026-10-21).

### 11-09 Planned skills: show the empty set

Release: required-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing. Ruled 2026-10-31: the vacuous K5 pass is accepted if reported.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`.
- 11-09: K5 reads HELD on an empty `PLANNED_SKILLS` (65ef303a) and the gate output does not say so. Check: `tests/test_fact_gate.py` asserts the fact gate's K5 line says "examined 0 planned skills" when `PLANNED_SKILLS` is empty.

### 17-24 Non-finite inputs fail loudly

Release: required-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `tests/test_nonfinite_inputs.py` (new), `scripts/build_fact_graph.py`, then one repair per silent function in its own module. Ruled 2026-10-31: split into scan and repairs; refuse; audit ids retired.
- 17-24 scan: S9's holder reads swallowed handlers only (ruled 2026-10-25); NaN or inf passed to a public numeric function can still return a number silently. The 2026-10-31 scan (166 functions) called 61 and found 7 silent: `nwb_read_io`, `channel_correlation_matrix`, `trial_correlation_matrix`, `consensus_bad_trials`, `to_db`, `pairwise_phase_consistency`, `resample_onsets`; 105 could not be called with an array alone. Check: `tests/test_nonfinite_inputs.py` builds valid inputs per public numeric function, injects NaN and inf, and asserts `ValueError` unless the docstring states NaN propagation; its examined set covers all 166, and S9's holder calls it.
- 17-24 repairs: each silent function raises `ValueError` naming the argument on NaN or inf, unless its docstring states NaN propagation (`to_db` is the first to check). Check: the function's row in `tests/test_nonfinite_inputs.py` fails on the baseline and passes after.

### 17-71 Suite profile and a tiered-CI plan

Release: required-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing. Ruled 2026-10-31: plan only; `workflow.yml` is unchanged until Hamm approves the plan.
Writes: `artifacts/evidence/0.2.15/suite_profile.md`, `artifacts/evidence/0.2.15/tiered_ci_plan.md` (new).
- 17-71: the only suite profile is 0.2.14's (`artifacts/evidence/0.2.14/verification_inventory.md` D13-D19) and no tiered-CI plan exists. Check: `suite_profile.md` gives per-file durations from `pytest --durations=0` at a named 0.2.15 SHA; `tiered_ci_plan.md` assigns every test file to a tier, and the fast tier's measured total is given.

### 17-72 Dashboard methods chip uses the ruled verdict word

Release: required-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing. Ruled 2026-10-24 (verdict vocabulary): reproduces maps to reproduced, partial to mixed, does_not to failed.
Writes: `scripts/build_dashboard.py`, `scripts/dashboard/app.js`, `tests/test_build_dashboard.py`.
- 17-72: the methods chip prints the record's raw verdict ("Methods: reproduces", `scripts/dashboard/app.js:1235-1240`); `VERDICT_LABELS` (`scripts/build_dashboard.py:92`) is not applied to it. Check: a test asserts no chip text in the built dashboard contains `reproduces`, `partial` or `does_not`.

### 17-73 Showcase receipts move into jnwb

Release: required-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing. Ruled 2026-10-31: the receipts live in jnwb, under `artifacts/showcases/`.
Writes: `artifacts/showcases/openscope_glo.json`, `artifacts/showcases/openscope_glo/receipts/README.md` (new) and the copied receipt files, `artifacts/showcases/openscope_glo/scripts/README.md` (new) and the copied scripts.
- 17-73: the four entries of `artifacts/showcases/openscope_glo.json` (lines 102, 242, 376, 487) say their receipts are in "local git repository C:/workspace/jnwb-showcase (not public)"; that repository is now `C:/workspace/_temp_jnwb-showcase` (HEAD 8604480; `receipts/` 29 files, 1.0 MB; `scripts/` 180 KB; `results/` 64 MB stays out). Check: each `location` names a committed path under `artifacts/showcases/openscope_glo/`, every receipt the JSON cites resolves on disk, and each copied file's SHA-256 equals its source at 8604480.

### 17-05 B3's lexicon covers the other choice names

Release: required-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing. Ruled 2026-10-31: all groups join B3; an uncited default gets an exceptions row, no API change.
Writes: `artifacts/fact_stack.md`, `scripts/build_fact_graph.py`.
- 17-05: The lexicon holds time windows only (ruled 2026-10-24); defaulted role windows (`response_window`, `response_window_s`, `sink_window_ms`, `exclude_window_ms`, `reward_window_ms`), baselines, bands, bins, segments, null sizes and method names go unchecked. Check: every defaulted parameter in the seven groups (keyword sets from the P4 inventory, reviewed) is in the `B3 choice names` constant of `artifacts/fact_stack.md` and either cites a source or has a row in its `## B3 exceptions` table with a reason; the fact gate reports B3 HELD. Waits: nothing; no shipped default changes.

### 17-07 S8 over prose

Release: required-0.2.15.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: nothing. Ruled 2026-10-31: estimand words per class; SKILL.md:19 reads "PSI: the sign of the phase slope across frequency, a lead or lag between two signals; it does not identify a driver."
Writes: `skills/jnwb-connectivity/SKILL.md`, `jnwb/connectivity/_transfer_entropy.py`, `jnwb/analyzers.py`, `scripts/build_fact_graph.py` (the integrator regenerates the API page).
- 17-07: S8's check reads figure labels and returned units only (ruled 2026-10-25); a sentence-level vocabulary scan of docs, skills and docstrings hit 49 sentences, about 47 legitimate (zflip's delays, "volume conduction", transfer entropy's `delay=`, negations). Two read as overclaims: `skills/jnwb-connectivity/SKILL.md` calls PSI "the frequency-dependent driver/receiver lag", and the `jnwb/connectivity/_transfer_entropy.py` module docstring calls TE "directed information flow"; `TFRAnalyzer.correlate_areas` (`jnwb/analyzers.py:305`) calls a correlation of band power "inter-area synchrony" (audit 2026-10-25); `docs/api.md:82` repeats the TE phrase. Check: S8's holder scans docs, skills and docstrings against the per-class vocabulary (phase measures: lead/lag; TE and Granger: predictive information; correlation and coherence: co-variation or coupling) and a reviewed exceptions table, and reports zero unexcepted hits; SKILL.md:19 reads the ruled sentence. Waits: nothing.

### 17-74 Tag 0.2.15 and tell omission

Release: release-step-0.2.15.
Role: human. Skill: none. Blocked by: the release merge to `main`; the notice needs Hamm's word.
Writes: `artifacts/rulings/2026-10-31.md`.
- 17-74: from open rows P-215-03 and P-215-14. Check: `refs/tags/v0.2.15` peels to the release commit on `main`, and the rulings file records Hamm's word on the omission notice.

### 17-75 Workspace cleanup

Release: deferred-0.2.16.
Role: human. Skill: none. Blocked by: the agent may not delete these (classifier and push guard).
Writes: `artifacts/open_stack.md`.
- 17-75: from P-215-05 and P-215-15. Hamm deletes the origin branches `proposal/spike-qc-pt-skill` and `skill/spectrolaminar-work-bastos` (kept as `_temp_spike-qc-pt-skill`, `_temp_spectrolaminar-work-bastos`), the folder `.claude/worktrees/site-overview-326890` then `git worktree prune`, `C:/workspace/_temp_lane_*` (8 clones, each clean and contained in dev, checked 2026-10-31), `C:/workspace/_temp_oc` and the scratchpad `lanes/`. Check: `git ls-remote origin` lists neither old name and `git worktree list` shows one entry.

### 17-76 agy retry

Release: deferred-0.2.16.
Role: actor. Skill: none. Blocked by: nothing.
Writes: `artifacts/rulings/2026-10-28.md`.
- 17-76: from P-215-06. The 2026-10-28 work-routing ruling waits on a packet that needs no file reads; agy returned empty before. Check: one no-read packet run through `delegate-cli --backend agy` returns a non-empty answer, recorded under the routing ruling.

### 17-77 Stale pointers in the fact stack and standing rulings

Release: deferred-0.2.16.
Role: human. Skill: none. Blocked by: Hamm's word (the fact stack and the rulings are his).
Writes: `artifacts/fact_stack.md`, `artifacts/rulings/standing.md`.
- 17-77: from P-215-20. `standing.md:144-148` and `fact_stack.md:68,82,86` cite roadmap 17-03 to 17-08 and 17-24, which are done or in this stack; `standing.md:144` says psth keeps `(-1000, 2000)` until 0.2.15, while psth now requires `window_ms`; S13 holds `todo:12-21`, which is a roadmap row. Check: every roadmap or todo id the two files cite resolves in `roadmap.md` or `todo_stack.md`, or is marked done with its commit.
