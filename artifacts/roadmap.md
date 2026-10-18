# Roadmap

Work deferred past the cycles the todo stack holds, one row per item. An item moves into the
todo stack, with its full text, when its cycle opens; it is never in both files.

A row is `| id | theme | defect | waits | deferred-X.Y.Z |`: the item id, a short theme, the
defect in one line, the reason it waits (AGENTS.md section 11), and the cycle it is deferred to,
later than the declared version. `scripts/release_gate.py` STEP 0a refuses any row that breaks
this form, and `scripts/fact_gate.py` counts each row's id as a live item. Rows are grouped by theme;
within a theme they run in the order listed, dependencies first.

The full text of each item carried here from the todo stack is in
`artifacts/archive/0.2.10/todo_stack_0.2.10.md`, the stack as it stood when this file opened.

## Laminar validation

Ground truth for vflip2, xflip's null and the curation path; 15-11 in the todo stack leads.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 15-19 | `vflip2`'s acceptance under null and nuisance conditions | 18 of 100 noise-only probes pass `omega_cut` 6 on one generator (`artifacts/evidence/0.2.12/vflip2_simulation.md`), so the cut is an algorithmic threshold with no measured false-acceptance rate; no run varies colored noise, a shared reference, spacing, SNR or the frequency grid, and no count carries an interval (external review, 2026-10-15). On 15-11's planted crossover (1dbcedbf, `artifacts/evidence/0.2.13/vflip2_recovery.md`) the matched SNR-0 null passes 24 of 100 (95% CI 0.16-0.34) and unconditional recovery is 29 of 100, both descriptive targets missed. | Colored noise, a shared reference, spacing and SNR sweeps; a measured threshold is Hamm's scientific ruling. | deferred-0.2.13 |
| 12-21 | A jaxfne simulation as jnwb ground truth | No jnwb test recovers a known coupling, delay or spectrum from a jaxfne simulation (meet 204dfdaa item 8); full text: `git log -S '### 12-21' -- artifacts/todo_stack.md`. | Ruled 2026-10-14: needs jaxfne's excerpt; nothing shipped changes. | deferred-0.2.13 |
| 15-17 | `xflip`'s null calibrated under nuisance structure | The `null_method` field landed (ruled 2026-10-15); no calibration runs `xflip`'s null under smooth Toeplitz correlation, heterogeneous noise, a common reference or planted blocks, and an effective sample size for the Wishart surrogate needs its own ruling. | Planted-block probes; the Wishart effective-n is Hamm's ruling. | deferred-0.2.13 |
| 15-18 | Fusion agreement that can say `agree` or `disagree` | The `'unavailable'`/`'unresolved'` status, the `B` cap and `contact_spacing_um` landed (ruled 2026-10-15); `fuse_laminar_anchors` emits `'agree'` and `'disagree'` only once a calibrated separation threshold exists. | 15-19's calibration. | deferred-0.2.13 |
| 15-13 | `vflip2` above 200 um spacing | Above 200 um, `round(0.1 mm / spacing)` is 0 and `vflip2` searches no window, returning all-None as for a probe with no motif, with no warning (`jnwb/laminar/_vflip2.py`); vFLIP2.m does the same. | A refusal or a doc line is a public-behaviour choice for Hamm. | deferred-0.2.13 |
| 15-15 | `curate_and_label` and vFLIP2 | `curate_and_label` anchors on vFLIP or the motif and passes no vFLIP2 crossover to `fuse_laminar_anchors`; `docs/10_operation_specifications.md` does not say so. | Whether curation runs vflip2 is an API choice for Hamm. | deferred-0.2.13 |
| 13-04 | A screen fitted to caller-supplied curation labels | No screen reports held-out agreement per session with a curator's labels, declines on degenerate inputs, or names its estimand. | The collaborator's label-learning skill; public API, nothing lands before the ruling. | deferred-0.2.14 |
| 14-08 | Unit-curation rows only the lab pipeline holds | D1, D9 and the lab meaning of D3 are defined only in the lab pipeline (`yihan777/alpha_beta_mechanism@826e540`), which no one here can read. | Access to the lab pipeline's code; study-specific rows, jnwb's measures are unchanged. | deferred-0.2.14 |

## Fact closure

Items that hold UNHELD facts; signature types before the scans and holder fixes.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 10-10 | Signature types that compose | I1: no numeric public operation declares signature types, and no composition edge is type-checked; full text: `git log -S '### 10-10' -- artifacts/todo_stack.md`. | Ruled 2026-10-11: the fact reports UNHELD and nothing public claims it. | deferred-0.2.13 |
| 11-06 | A cited reason for each defaulted `window=` | B3: a public function with a defaulted `window=` needs no cited reason in the B3 table; full text: `git log -S '### 11-06' -- artifacts/todo_stack.md`. | After 10-10; ruled 2026-10-11: the fact reports UNHELD and nothing public claims it. | deferred-0.2.13 |
| 09-04 | The claim-class text check | S8: no text check over docs, skills, figure labels and docstrings reports the planted 0.2.7 fig09 unit as VIOLATED; full text: `git log -S '### 09-04' -- artifacts/todo_stack.md`. | After 10-10; ruled 2026-10-11: the fact reports UNHELD and nothing public claims it. | deferred-0.2.13 |
| 11-32 | Holders that name their work | S9 to S14, K4, I2 and I3 cite `todo:09-04` or `todo:10-10` though no bullet of those items names them; full text: `git log -S '### 11-32' -- artifacts/todo_stack.md`. | Holder cells belong to Hamm; ruled 2026-10-11 to wait with 09-04 and 10-10. | deferred-0.2.13 |
| 11-07 | The S1, S2 and S5 scans | S1, S2 and S5 report UNHELD: the S2 and S5 scans land in 0.2.11 and flag `jnwb/spectral/_psd.py:389` and `:558` (S2) and 17 randomness calls without an `rng` parameter plus one seed (S5), and S1's only test covers its reference-line clause; S2's clause 1 and the S5 sites wait on Hamm's reading. The full text is in `git log -S '### 11-07' -- artifacts/todo_stack.md`. | Ruled 2026-10-11: the facts report UNHELD and nothing public claims them. | deferred-0.2.13 |
| 12-11 | The S7 scan | S7 (a caller uses the library function instead of retyping its rule) has no scan that reports its own planted case. Accept (carried from 11-07 by the 2026-10-11 ruling): the S7 scan reports its own planted case in `tests/test_fact_gate.py`, and S7 reports no UNHELD fact. | Ruled 2026-10-11: no scientific criterion for a retyped rule is ruled yet, and nothing public claims S7. | deferred-0.2.13 |
| 11-03 | Design facts held | D1, D2 and D3 of the Design table report UNHELD. | After 07-22; the facts report UNHELD and nothing public claims them, and D2 and D3 land with 07-21 and 07-22. | deferred-0.2.13 |
| 11-09 | A planned skill is reported only when K1 and K5 hold for it | The fact gate can report a planned skill (one of the twelve of Q14, `jnwb-landmark-viz`, `jnwb-paradigm` and `jnwb-qc` included) for which K1 or K5 does not hold; the full text is in `git log -S '### 11-09' -- artifacts/todo_stack.md`. | Ruled 2026-10-11: plan for future skills, no shipped behaviour. | deferred-0.2.13 |
| 12-08 | Every routed method cites a published source | No fact holds `computed:routed_citations`, which lists 73 routed exports with no `cites` edge: containers, I/O, metadata, plotting and plumbing, plus eight with no source the code implements (`xflip`, `network_topology`, `permute_labels`, `build_permutation_plan`, `exploratory_correlate`, `consensus_bad_trials`, `spatial_derivative_sharpness`, `waveform_flatness`). | Ruled 2026-10-14: deferred; the exclusion list ruled 2026-10-13 stands and nothing public claims the fact. | deferred-0.2.13 |
| 12-07 | Release and study-vocabulary facts held | R2 (a verify-pypi job after publish-pypi) and B2 (gate 6 over `jnwb/`, `docs/`, `skills/` and `tests/`) report UNHELD. | After 12-05 and 12-08; the upload step checks sha256 against the verified TestPyPI copy, and `tests/` is not in the wheel while shipped surfaces are scanned. | deferred-0.2.13 |

## Public API

Each needs Hamm's ruling before code.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 07-21 | A public NWB mutation API | No public NWB mutation API exists. | Public API; Hamm rules the shape from 08-08. | deferred-0.2.13 |
| 07-22 | A public execution and cache API | No public execution and cache API exists. | After 07-21; public API, Hamm rules the surface from 08-08. | deferred-0.2.13 |
| 12-13 | `gpu_pca`'s deprecation path | The rest of the 2026-10-11 compression audit's steps 4 and 6 landed in 0.2.12 (one SVD fallback, `_api_surface` in `tests/`, `run_cases` deleted, the MI aliases and `clopper_pearson_ci` deprecated); `gpu_pca` is left because no docs page names its replacement. | Ruled 2026-10-14: deferred; Hamm names the replacement, and the deprecation needs a release of notice. | deferred-0.2.13 |
| 12-23 | Block-constant label permutation | The GLO showcase permutes context labels per block (`C:/workspace/jnwb-showcase` `decode_s2.py:46`) because `build_permutation_plan` permutes per trial or within groups only; its percentile bootstrap over mice (`analyze_s1.py:77`, `aggregate_s2.py:60`) retypes `StatisticalAnalysis.bootstrap_ci` or shows a shape it lacks (showcase review, 2026-10-12). Check: a plan whose labels are constant within each block keeps them constant in every permutation, and the showcase calls jnwb for both. | New public API; the showcase runs with its own code meanwhile. | deferred-0.2.13 |
| 11-04 | Proposals for the pitfall estimators | Four estimators have no proposal: nonparametric Granger by spectral factorization, a time-reversed Granger control, partial coherence conditioned on a third signal, and a bias floor from randomly paired epochs. | Public API, Hamm rules the shape. | deferred-0.2.14 |
| 14-06 | The pitfall estimators Hamm rules | The four estimators 11-04 proposes have no implementation. | After 11-04; public API, nothing lands before the ruling. | deferred-0.2.14 |
| 14-07 | A trial-based noise correlation, if a user needs it | A trial-based noise correlation (Cohen and Kohn's $r_{sc}$) is absent beside the time-bin form, if jaxfne or a study needs it; Hamm rules whether it is a mode or a function. | The docstring, references row and skill now say the time-bin form includes signal correlation. | deferred-0.2.14 |

## NWB reading edges

Reader and integrity edge cases.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 11-01 | Every container `inspect` lists is readable | P-294, P-314, P-303, P-299, P-190 (a series with `timestamps` and no constant `rate` raises `AcquisitionNotFoundError`), P-204, P-220, P-336, P-337, P-216 (reading part), P-289 and P-291 and the MCP signal reference edges leave containers unread or checks unpinned. | P-294, P-314, P-220 and the MCP signal reference edges are loud or outside the schema, P-303's known types agree, P-299 is vocabulary only, P-190's message is true and a new class is API, P-204 errs toward caution, P-336 and P-216 behave correctly, P-337's messages are true, P-289 has no current path doing either, and P-291's value is right. | deferred-0.2.13 |
| 11-02 | Compression, unit tables and addressing edges | `classify_layer_from_depth` with no declared shallow end is open (the hard-linked `select=` cast re-points every name, ruled 2026-10-18; P-348's soft-link cases pinned and P-192's page line written and P-296's dated comments rewritten and P-344's slope matched to raw HDF5 (`artifacts/evidence/0.2.13/compress_scaling.md`) 2026-10-17; `compress_fp32` has no device path, so P-348's CUDA case does not apply). | No behavioural effect: 0.2.9 behaves the same for `compress_fp32`, and the layer classification is stated and waits on D10's ruling. | deferred-0.2.13 |

## Consumers and docs

Use of jnwb from outside: a new dataset, a downstream agent, tutorial figures.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 12-10 | One unfamiliar dataset through the skills | The MCP tools and the skills' routing answer the DANDI 000253 question with the tutorial's numbers and refusals (`tests/test_open_data_through_the_agent_surface.py`, 2026-10-17); a blind agent session through the skills matches the tutorial's counts but not its clock or its dB (0.08 to 0.21 dB low), because no skill says how to put tick-valued timestamps on session time and none states the `CANONICAL_BANDS` edges (`artifacts/evidence/0.2.13/agent_session_dandi000253/`, 2026-10-17; external review 2026-10-11, P2). | New coverage of a path whose operations are already tested; it cannot make release evidence falsely pass. | deferred-0.2.13 |
| 07-05 | A downstream paper agent can consume jnwb | `jnwb.preflight` outcomes are not scored as data, results do not name their input's sha256 and object path (IA-27's tests for `resolve_nwb_path`, `sha256_file` and `require` land with it), `CONTRIBUTING.md` states no intake, and P-335's review (`artifacts/evidence/0.2.13/p335_laminar_curation_review.md`) leaves the working-value defaults uncited and the inner stages unexposed, for a ruling. | After 11-02; new downstream capability, not a defect. | deferred-0.2.13 |

## Harness and gates

Gate reach before pruning; guards for the installed-wheel leg.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 12-05 | Process tests pruned and merged | Four process-test files to prune, four to merge and four weaker checks stay (the unruled list and its receipts: `artifacts/evidence/0.2.10/reduction/prune_list.md`), P-290 is enforced by nothing and the apparatus bound of `artifacts/goal.md` section 10 has no check. | Ruled 2026-10-14: deferred; the prune list waits for Hamm's ruling. keeping tests cannot make evidence falsely pass, P-290 is a contributor rule that ships nothing, and the apparatus bound is stated unchecked in the goal, growth only. | deferred-0.2.13 |
| 09-07 | Checks for the defect classes review keeps finding | Three classes have no check: rewrite-drops-obligation, second-home-contradiction and awareness in state; ruling-cited-not-recorded is checked to the date (`tests/test_process_records_are_counted.py`, 2026-10-17), and matching a citation to its row stays a review rule. The ledger is recounted by the same file. | Process evidence only, no shipped behaviour; rewrites are rare and reviewed, review found every instance so far, and the integrator reads state by hand today. | deferred-0.2.13 |
| 12-06 | No process identifiers outside the stacks | P-284: `scripts/` and test files cite item and problem ids (P-209 and IB-71 merged; the 2026-10 counts no longer reproduce, so the lane re-measures them); P-102 levels line endings if D3 rules it. | After 12-05, 12-07 and 12-08; neither directory ships, and P-102 is bytes only and waits on the D3 ruling. | deferred-0.2.13 |
| 15-20 | An inventory of the verification apparatus | Goal 10 bounds the apparatus ("a new gate or process replaces one") with no check; nothing lists each gate's purpose, runtime, unique failure detection, duplicated assertions and maintenance burden (external review, 2026-10-15). Accept (ruled 2026-10-15): that inventory first, then a measurable constraint proposed to Hamm that does not reward deleting valuable tests; no universal gate-count ceiling. Two candidate checks were built and not integrated (2026-10-15), each to land only by replacing a check the inventory shows weaker: warning reads filter by category (it found one site beyond 51a29bb7's seven), and every artifact path code names is tracked. | The bound is Hamm's, after the inventory. | deferred-0.2.13 |
