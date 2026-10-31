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

## Path to the release

One ordered path from now to the tag. Each step names its check; a pass goes to the next step, a fail
takes the branch under it. Steps on one line run in parallel lanes (one Muse or Haiku writer per
clone, at most three); the integrator reads each diff and reruns its acceptance before merging.

1. Suite green at HEAD, stamp written; push `dev`; CI green.
   - Fails: repair the failing test or item text, rerun from 1.
2. Wave 3, three lanes: 16-20 | 11-09 then 17-05 | 17-72 then 17-73.
   - A lane fails its acceptance: send it back once with the failure; a second fail, the integrator does it.
   - 16-20: a `reviewer` reads the planted-field test before merge (science).
   - 17-05: a default with no truthful reason or source: ask Hamm (cite it, or except it).
3. 17-71: profile the suite through the lock; write the tiered-CI plan. Plan only.
   - Hamm approves the plan: a 0.2.16 item changes `workflow.yml`. Not approved: the plan stays a receipt.
4. Barrier: harness gate, suite, push, CI green on `dev`.
5. Wave 4, two lanes: 17-07 | 17-24 scan (each failing function marked strict-xfail).
   - The scan lists N functions awaiting repair: split them into repair lanes by module, three at a time;
     each repair removes its xfail. Done when the awaiting set is empty.
   - A repair would change a released number, or a docstring would need to state NaN propagation: ask Hamm.
   - 17-07 finds an overclaim beyond its three sites: reword it under the same ruling, or ask Hamm if unclear.
6. Barrier, as 4.
7. Open stack to zero: P-215-10 and P-215-16 close with waves 3 and 4; P-215-28, `state.md` to 80 lines
   (generator change, tests first).
8. Release mechanics, in order: assemble `CHANGELOG.md` from `artifacts/changelog.d/`; bump `__version__`
   to 0.2.15; merge `origin/main` into `dev`; regenerate state; barrier as 4.
9. Quality pass (release condition: low-verbosity docs, low-complexity code): agy sweeps the docs, a
   measured complexity scan reads `jnwb/`.
   - A finding that blocks the release: fix it, back to 6. One that blocks nothing: a 0.2.16 item.
10. Closure pass: an independent blocker-focused review (reviewer and agy, different models) checks each
    advertised claim against the deferred rows; its receipt is committed at HEAD.
    - A new blocker: it becomes an item, back to the step that owns its file.
11. `python scripts/release_gate.py` with the checkout on `PYTHONPATH`: passes; checklist 13 of 13.
12. 17-74, after the gate: merge to `main`, tag `v0.2.15`, tell omission on Hamm's word.

Deferred to 0.2.16, off the path: 17-75 (deletions only Hamm runs), 17-76, 17-77, the roadmap rows.

### 16-20 A distance-aware coherence graph

Release: required-0.2.15.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: nothing.
Writes: `tests/test_connectivity_pitfalls.py`, `docs/common_mistakes.md`, `skills/jnwb-connectivity/SKILL.md`, `artifacts/changelog.d/coherence-distance.added.md` (new fragment). Form and normalization ruled 2026-10-31: caller-side, no API change; binned distance mean.
- 16-20: `cross_area_coherence` and `network_topology` take a coherence matrix as it is, so a graph of nearby contacts or electrodes is dense from field spread alone; Nejat and Hajipour Sardouie 2021 normalize edge weights by distance and compare groups edge by edge (`docs/references.md`, Pitfalls). Check: in `tests/test_connectivity_pitfalls.py`, on a planted field with spread between nearby contacts and one planted far-pair interaction, dividing each edge by its distance-bin mean removes a spread edge that the raw graph keeps and keeps the planted far-pair edge; the fixture asserts raw near-pair coherence exceeds the threshold. Waits: raised during 0.2.14, after its scope was set (goal F3, ruled 2026-10-21).

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

### 17-07 S8 over prose

Release: required-0.2.15.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: nothing. Ruled 2026-10-31: estimand words per class; SKILL.md:19 reads "PSI: the sign of the phase slope across frequency, a lead or lag between two signals; it does not identify a driver."
Writes: `skills/jnwb-connectivity/SKILL.md`, `jnwb/connectivity/_transfer_entropy.py`, `jnwb/analyzers.py`, `tests/test_claim_vocabulary_prose.py` (new) (the integrator regenerates the API page).
- 17-07: S8's check reads figure labels and returned units only (ruled 2026-10-25); a sentence-level vocabulary scan of docs, skills and docstrings hit 49 sentences, about 47 legitimate (zflip's delays, "volume conduction", transfer entropy's `delay=`, negations). Two read as overclaims: `skills/jnwb-connectivity/SKILL.md` calls PSI "the frequency-dependent driver/receiver lag", and the `jnwb/connectivity/_transfer_entropy.py` module docstring calls TE "directed information flow"; `TFRAnalyzer.correlate_areas` (`jnwb/analyzers.py:305`) calls a correlation of band power "inter-area synchrony" (audit 2026-10-25); `docs/api.md:82` repeats the TE phrase. Check: `tests/test_claim_vocabulary_prose.py` scans docs, skills and docstrings against the per-class vocabulary (phase measures: lead/lag; TE and Granger: predictive information; correlation and coherence: co-variation or coupling) and a reviewed exceptions table, and reports zero unexcepted hits; SKILL.md:19 reads the ruled sentence. Waits: nothing.

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
