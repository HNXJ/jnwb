# Roadmap proposal: 0.2.8 to 0.2.11

Proposal of 2026-09-28 for Hamm to work through; nothing here is ruled. It assigns every item and
bullet under `# 0.2.8` in `artifacts/todo_stack.md` at `274ec463` to one of four releases. Once a
version is ruled, its items move under their own heading in the stack and this file is deleted.

Each release has one theme, so a critic can review it against a single question. The order puts
velocity and skills first (Hamm's 0.2.8 ask), then shipped scientific behaviour, then data access
and the two public APIs that need rulings, and the release apparatus last.

## Summary

| Release | Theme | Items | Rulings needed first |
|---|---|---|---|
| 0.2.8 | Skills with zero friction, and a faster cycle | 07-30, 07-08, 07-09, 07-10, 07-11, 07-12, 07-13, 07-18, the 07-23 apparatus, about 25 bullets | none; 07-30 carries its rulings |
| 0.2.9 | Scientific semantics and numerical edges | about 45 bullets from 07-26, 07-27 and 07-28 | `vflip` rename (P-228); IB-44 bootstrap design is ruled |
| 0.2.10 | NWB reading, data access, and the mutation and execution APIs | 07-21, 07-22, about 40 bullets | 07-21 and 07-22 API shape (Hamm rules first) |
| 0.2.11 | Release apparatus, CI, gates, documentation reach, downstream consumer | 07-05, about 60 bullets | none |

## 0.2.8 Skills with zero friction, and a faster cycle

| Group | Items and bullets |
|---|---|
| Velocity first | todo compaction to one line per item; CHANGELOG fragments; the ~1500-word `AGENTS.md` draft (Hamm approves); RP-3 (`release_gate` stops at the first failure, 12 to 30 min per run); load-sensitive workflow test; load-sensitive state generation; xflip calibration wall time; IB-89 if it does not close in 0.2.7 |
| Skills and roles | 07-30 in its nine steps; 07-18 examples run; 07-10 `jnwb-paradigm`; 07-11 `jnwb-qc`; 07-12 unrouted exports; 07-13 each thing once; 07-08 router composes; 07-09 composition tests |
| Routing coverage | IB-61, IB-63, P-20, P-267, exports and modules outside the routing, P-279 |
| Figure checks (feed 07-30) | figure checks, legend check reach, P-241, P-244, P-275, P-276, vis label edges, vis range edges |
| Test reach found this cycle | zflip ramp width, prepend scanner reach, tie-width test reach, stack editor edges, nav check edges, directed estimator edges |

Acceptance: the §11 conditions, plus a skill-friction measure from 07-30: every task class in
`docs/agents.md` routes to one skill, and one example per skill executes.

## 0.2.9 Scientific semantics and numerical edges

| Group | Bullets |
|---|---|
| Estimator validity | P-227 (PSI jackknife unit), P-230 (`aperiodic_fit` peaks), P-231 (Rayleigh comment), P-264 (PSI undefined bands), PSI segment count and conditional networks, IA-19 (`bilinear` one model), IB-44 (jrsa block bootstrap, ruled), IB-45 (`directed_network` int rng), P-351 (`vflip` support score) |
| Statistics edges | P-265, P-297 (ANOVA and `eta_squared`), P-321 (`confirmatory_compare` correction label), P-329, P-331, P-332, P-333, P-334, P-346, P-350, response-significance wording |
| Numerical and device | P-203 (log ratio outside `aggregate_to_db`), P-340, P-343, P-292, IB-48 (jrsa cuda), IB-60, P-281, `jrsa` resampling fallback |
| Randomness and records | RNG surface, generator seeds and `jrsa` axes, P-246 |
| Depth and layers | depth declaration guard, `classify_layer_from_depth` depth sign, P-228 (`vflip` name collision) |
| API completion | deprecations to complete, P-171, P-196, P-216, IA-28 |

Acceptance: each estimator change carries a calibration record in `artifacts/evidence/0.2.9/`.

## 0.2.10 NWB reading, data access, and the two public APIs

| Group | Bullets |
|---|---|
| `acquisition_channel` and containers | P-190, P-204, P-220, P-221, P-283, P-294, P-298, P-299, P-303, P-314, P-336, P-337 |
| `compress_fp32` | P-324, P-338, P-344, P-348, P-349 |
| Unit tables and metadata | P-192, P-242, P-245, P-312, P-313, P-322, P-323 |
| Refusals and messages | P-255, P-256, P-257, P-291, P-315, P-320, P-347 |
| Public APIs | 07-21 NWB mutation API; 07-22 execution and cache API; IA-23 (`bootstrap_ci` vectorised) |
| External | P-335 (omission laminar curation pull request review) |

Acceptance: 07-21 and 07-22 ship only after Hamm rules their shape.

## 0.2.11 Release apparatus, CI, gates, documentation, downstream

| Group | Bullets |
|---|---|
| Release and CI | RP-2, RP-4, RP-7, CI guard hardening, floor coverage, one smoke definition, release workflow edges, peak-memory reset evidence, P-307, P-309, P-328, P-352, P-353 |
| Gates and parsers | P-218, P-219, P-232, P-235, P-238, P-266, P-274, P-295, P-300, P-302, P-304, P-305, P-311, P-330, P-342, readiness blind spots, sweep site fingerprint |
| Receipts and hashing | P-229, P-285, P-197, P-198 |
| Documentation reach | P-01, P-76, P-84, P-199, P-259, P-268, P-269, P-277, P-278, P-280, P-282, P-287, P-288, P-289, P-290, P-296, P-301, P-317, P-319, P-341, IA-29, IB-56, MCP signal reference edges |
| Repository hygiene | P-102, P-191, P-284, process tests to prune or merge |
| Downstream consumer | 07-05 a to c |

## Records to delete rather than schedule

These bullets record closed history or were merged into another row. The proposal is to delete
each one, with the commit message naming where its content lives.

| Bullet | Why |
|---|---|
| P-08, P-36, P-90, P-119, P-154, P-155, P-162, P-167, P-326 | records of past miscounts or process defects; the repair landed or the lesson is in `artifacts/rulings/history.md` |
| P-209, IB-71 | merged into P-284 on 2026-09-27 |

## Open questions for the working session

| # | Question | Proposed answer, graded |
|---|---|---|
| 1 | Four releases, or fold 0.2.11 into 0.2.10? | four: each theme gets its own review question (70) |
| 2 | Velocity items first in 0.2.8, ahead of the skills work? | yes: compaction and fragments cut every later merge (80) |
| 3 | P-228: rename `vflip`, or keep the name with a disambiguation note? | note in 0.2.9, rename only with a deprecation path (60) |
| 4 | Delete the historical records listed above? | yes (85) |
| 5 | Does 07-05 (downstream paper agent) belong earlier, since it tests the skills? | stay in 0.2.11 unless the omission project needs it sooner (55) |
