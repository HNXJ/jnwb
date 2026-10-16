# Open stack (jnwb, 2026-10-15)

Everything open on `dev` after 1dbcedbf (15-11's generator half, pushed), grouped by who moves it next. Sources: `artifacts/problem_stack.md` (0 rows), `artifacts/todo_stack.md`, `artifacts/roadmap.md` (39 rows: 34 `deferred-0.2.13`, 5 `deferred-0.2.14`), the session's open work. A repository-wide scan for anything else that looks open is running and will be merged as section E.

## A. Waits on a ruling by Hamm

| Item | Open question | Source |
|---|---|---|
| 0.2.13 theme | The cycle runs on goal and §11 acceptance until a theme is ruled | `todo_stack.md:9` |
| 15-13 | `vflip2` above 200 um spacing: refuse, or a doc line | roadmap |
| 15-15 | Whether `curate_and_label` runs `vflip2` | roadmap |
| 15-19 / item 8 | A measured `omega_cut`, or a data-driven threshold: scientific ruling. Evidence now: recovery 29/100, matched null 24/100, grid 63/100, both targets missed (`artifacts/evidence/0.2.13/vflip2_recovery.md`) | roadmap, 15-11 |
| 15-20 | The apparatus bound, after the inventory. Two candidate checks from the Muse gates lane wait there: warning reads filter by category; every named artifact path is tracked | roadmap, goal 10 |
| 07-21, 07-22 | Public NWB mutation API, then execution and cache API: shape from 08-08 | roadmap |
| 12-13 | `gpu_pca`'s replacement | roadmap |
| 12-23 | Block-constant label permutation: new public API | roadmap |
| 11-04, 14-06, 13-04 | Pitfall estimator and curation-screen shapes (0.2.14) | roadmap |
| 12-05 | The process-test prune list | roadmap |
| 11-32 | Holder cells | roadmap |
| `scripts/measure_order.py` | Keep or remove: no live caller beyond the 0.2.6 order evidence | archive sweep |
| `jnwb-sim-benchmark` skill | Proposal only; skills change by amendment and need the capability gate | session |

## B. Executable by agents now

| Item | Next step | Source |
|---|---|---|
| 15-14 | A working `vflip2` hand-off in `docs/laminar.md` (needs a block-structured probe) | roadmap |
| 15-16 | Repo-root guards that ignore `JNWB_EXPECTED_PACKAGE_ROOT` | roadmap |
| 11-05 | Export `ContainerTypeContradictionWarning` | roadmap |
| 11-01, 11-02, 12-24 | NWB reading edges, diagnostics | roadmap |
| 12-10, 14-05, 07-05 | One unfamiliar dataset, tutorial figures 03-04, downstream paper agent | roadmap |
| 12-04, 09-07, 12-06 | Gate reach, defect-class checks, process identifiers | roadmap |
| Fact closure group | 10-10, 11-06, 09-04, 11-07, 12-11, 11-03, 11-09, 12-08, 12-07: ruled to wait; facts report UNHELD, nothing public claims them | roadmap |
| Dangling pointer | `artifacts/archive/0.2.5/alignment_review_0.2.5.md:197` names `artifacts/capability_review_0.1.7.md`, a path that does not exist | prune sweep |

## C. Waits on someone outside the repository

| Item | Waits on | Source |
|---|---|---|
| 15-11 second half | Andre Bastos's simulation code | todo stack lanes |
| 12-21 | jaxfne's excerpt | roadmap |
| 14-08 | The lab pipeline's code | roadmap |
| jchat additions | Keeper's answer to asks 61-62 (locks, events feed, lanes board, CI ingress, ruling kind, usage totals) | p-jynx |

## D. Housekeeping

| Item | State |
|---|---|
| 40 local lane branches | Kept; 8 hold `_temp_` WIP snapshots (dash-app, dash-gen, dash-pages, k1, k3, m, w, y2) |
| Worktrees | jnwb, jnwb-main, jnwb-pr31 remain |
| Scratch clones | cl-* under the session scratchpad; deleted after integration |
| Evidence prune | Dropped: archived todo stacks cite almost all closed evidence; 2 probe scripts were the only uncited files |
| Data correction | V3v on ses-260724 is an open defect (memory note; omission project) |

## E. Repository scan (Muse, 76 rows; new items only)

Rows that duplicate A to D, or describe a closed decision (B2 removed; 12-22 split done, no SKILL.md over 10 KB; the 2026-10-06 ruling's 0.2.10 defects) are left out.

| Item | Open | Source | Who |
|---|---|---|---|
| `jrsa(align_mode=)` removal | Promised for 0.2.13 by the shipped CHANGELOG (0.2.11 entry) and the warning text; now todo item 15-21 | `jnwb/jrsa/__init__.py:423`, `CHANGELOG.md:95` | agents |
| Legacy constructor path | "Will be removed", no version named | `docs/02_paths_addressing_metadata.md:285` | Hamm: name a version or drop the line |
| `jrsa(sliding=True)` | Raises `NotImplementedError` | `jnwb/jrsa/__init__.py:222` | Hamm: implement or keep the refusal |
| Experimental modules | `bilinear.py`, `nam.py` outside `__all__`, marked experimental | `jnwb/bilinear.py:2`, `jnwb/nam.py:2` | Hamm: promote, keep or remove |
| Metal path | Implemented, never run on Metal hardware, declared unverified | `jnwb/_backend.py:40` | needs hardware |
| Unreleased fragments | 4 in `artifacts/changelog.d/` (15-17, 15-18 twice, B2) plus 15-11's | `CHANGELOG.md:9` | release step |
| WaveMAP units | Volts vs microvolts reading of source labels unverified | `docs/tutorials/10_wavemap.md:20` | agents |
| 0.2.12 sensitivity | Upper-frequency columns not run (PSD ends at 150 Hz) | `artifacts/evidence/0.2.12/vflip2_sensitivity.md:53` | 15-19 |
| 15-17 calibration | Wishart effective-n needs its own ruling | `artifacts/roadmap.md:23` | Hamm |
| Frozen-waveform ownership | One question open in section 5 | `artifacts/evidence/0.2.11/frozen-waveform-disposition.md:4` | unknown |
| Unit QC inventory | A "why open" row | `artifacts/evidence/0.2.9/unit_qc_inventory.md:65` | unknown |
| S5 recount | 17 vs 20 sites | `artifacts/evidence/0.2.13/fact_dispositions.md:37` | 11-07 |
| Goal 8 | Peak memory recorded with no threshold | `artifacts/goal.md:22` | Hamm |
| Open rulings | `window` retargeting to the next axis (2026-09-27); dark plot `theme=` (2026-10-04, 09-10); all-NaN block verdict (2026-10-10, 11-41); showcase publication at Gate B (2026-10-12); which CI run qualifies, dev or main (2026-10-15 R5) | `artifacts/rulings/` | Hamm |
| Issues #32, #33 | Open until A. Bastos answers the review | `artifacts/rulings/2026-10-13.md:14` | A. Bastos |
| Strict xfails | Word-pattern check misses; mobile-width AWAITING ledger (~33 entries) | `tests/test_skill_decline_behaviour.py:927`, `tests/test_figure_form.py:778` | agents |
| GPU paths | Skipped without hardware in CI | `tests/test_adversarial_inputs.py:122` | environment |

Not scanned: live GitHub state, `C:/workspace/jnwb-showcase`, history beyond the clone.
