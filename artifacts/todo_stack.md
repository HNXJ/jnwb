# 0.2.7

Opened 2026-09-24, after 0.2.6 was published to PyPI, on Hamm's instruction.
Items are deleted when done; git, `CHANGELOG.md` and the receipts hold history. The previous cycle's record is
`artifacts/archive/0.2.6/todo_stack_0.2.6.md`, with its closure receipt beside it.

0.2.7 is measured against `artifacts/goal.md` and opens under the three conditions of `AGENTS.md`
§11. Its scope is bounded by the 2026-09-27 ruling (`artifacts/rulings/2026-09-27.md`): the lanes in
flight, the items ruled that day, and the findings that meet the blocker predicate, classified by an
independent critic. Everything else is under `# 0.2.8` below, each item or bullet with the reason it
waits. Every finding is to be checked: a packet reproduces a finding against its own tree before it
repairs anything, and a finding that does not reproduce is deleted. Rulings are in
`artifacts/rulings/`.

The declared version stays 0.2.6.1 on dev until the release step in 07-29 sets it to 0.2.7, so
until then the release gate's cycle is 0.2.6.1 and its deferral value `deferred-0.2.7`, which no
item here carries: it holds every item open. It reads them as marked once the version is 0.2.7.

## How this stack is executed

Every item is a delegation packet in the contract of `artifacts/skills/jnwb-fact-action` §5; the executing
role is `jnwb-developer` (`artifacts/agents/jnwb-developer.md`) unless the item names another.
Map the fields onto the packet: `Role` ROLE, `Skill` DOMAIN SKILL, heading GOAL, id TODO ITEM,
`Reads` extra AUTHORITIES, `Reproduce` OBSERVED BASELINE, `Writes` ALLOWED SCOPE, `Accept`
ACCEPTANCE, `Stop` STOP CONDITIONS.

| Rule | Why it binds |
|---|---|
| `AUTONOMY: max` unless the item says otherwise (`AGENTS.md` §12) | the actor and critic sequence the work and continue past a failing test or a surviving mutant |
| One writable agent per worktree; a lane runs `scripts/verify_lane.py --baseline <commit>` before its first write | a shared tree has silently lost green tests here |
| One item per packet | a batched packet reports the easy items and redefines the hard one |
| The actor is never the verifier | every `repaired` is re-run against the exact diff by someone else |
| Non-reproduction is a result | an imported finding that does not reproduce is returned `unsupported` and its item deleted |
| A contradiction stops the packet | two sources disagreeing on one quantity go to `authority` |
| The dispatcher owns the stacks, `CHANGELOG.md` and `docs/api.md` | a packet reports the disposition, the changelog text and the export change; the dispatcher writes them and regenerates `docs/api.md` at the wave barrier |
| Wave barrier | `python scripts/harness_gate.py` (count the PASS lines), `python -m pytest tests/ -q`, commit, push, confirm CI on `dev` |

Standing stop conditions on every packet: a repair needs a path outside `Writes`; the premise is
already false; acceptance would need invented evidence or a human ruling; a secret would enter the
repository or a transcript.

Item fields: `Release`, `Role`, `Skill` (a skill directory or `none`, `per skill`, `per module`,
`per finding`, `per chain`), `Blocked by` (live item ids or `none`), `Reads`, `Writes` (exact paths
or globs, never a bare directory), `Reproduce`, `Do`, `Discriminator` (fails before, passes after),
`Accept`, `Stop`.

## Execution order

| Order | Items |
|---|---|
| 0 | 07-23: the deferral attack, then the apparatus work |
| 1 | 07-03: the lanes in flight and the bullets ruled 2026-09-27, then the rest |
| 2 | 07-01, P-345 first |
| 3 | 07-02 |
| 4 | 07-29, by hand before the release pull request merges |

The 0.2.8 items are not scheduled in this cycle.

### 07-01 Findings carried from 0.2.6

Release: required-0.2.7.
Role: jnwb-developer. Skill: per finding. Blocked by: none.
Writes: `jnwb/**/*.py`, `scripts/*.py`, `tests/**/*.py`, `docs/**/*.md`, `skills/*/SKILL.md`, `examples/**/*.py`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`.
Each finding below was deferred under `AGENTS.md` section 11 during 0.2.6 and meets the blocker
predicate by the independent classification of 2026-09-27; the findings that do not are in 07-26
under 0.2.8. The second pass of that date added P-240 and clauses of P-241, P-331 and P-332,
and folded clauses of P-336 and P-348 into P-327 and P-349. A packet takes one finding and
narrows the write set to its paths. P-345 leads.

- P-240: With transparent figure backgrounds, legends lost their opaque box and overlap data: fig07 panel A (text over bars 4-5, both variants) and fig10 panel B. Required for 0.2.7 (condition 1, second pass 2026-09-27): Hamm ruled on 2026-09-27 that overlapping legends fail condition 1; fix fig07 panel A and fig10 panel B.
- P-241: IB-73 of 07-03 changes `spectral_tilt`'s `exponent`, which `docs/generate_figures.py:244-251` reads for fig04, so fig04 is regenerated in 0.2.7, and the contrast check in `tests/test_figure_form.py` cannot vouch for a dark variant (the parser gap is in 07-26). Required for 0.2.7 (condition 1, second pass 2026-09-27): every regenerated figure's dark variant gets an eye-check, recorded.
- P-308: CI's setup-python installs the newest 3.12 patch, so no leg runs the declared floor 3.12.0, which is how 06-146 shipped unseen. Required for 0.2.7 (R5, R4, classified 2026-09-27): `requires-python >=3.12` while CI installs the newest 3.12 patch, and behaviour differs on 3.12.0 (06-146, P-317); fold into IB-70's floors leg of 07-03 or raise the floor.
- P-316: STEP 0a does not see a todo section with no item id and no release field, nor a required bullet inside a deferred item. Required for 0.2.7 (R4, classified 2026-09-27): the readiness step cannot see a required bullet inside a deferred item.
- P-318: `UnitAnalyzer.autocorrelogram` keeps `refractory_period_violation`, `is_single_unit`, `refr_count` and `baseline_count` in 0.2.6 as NaN with a `FutureWarning` (ruled 2026-09-23); 0.2.7 removes them. Required for 0.2.7 (R3, classified 2026-09-27): `jnwb/analyzers.py:414` and `:446` promise the removal in 0.2.7; P-319 is moot after it.
- P-327: `release_gate.py` compares the receipt's commit with HEAD but does not refuse a dirty working tree, so uncommitted code at release time would not invalidate the receipt. Folded from P-336 on 2026-09-27: STEP 0a reads a failed `git status` as clean, and a mutant doing so survives 100 tests; a test for it joins this check. Required for 0.2.7 (R4, classified 2026-09-27): the release gate accepts a receipt at HEAD over a dirty tree.
- P-331: `phase_slope_index`'s jackknife has no zero-spread guard: a periodic X with Y equal to X gives z = -2e13, p = 0 and `ok_for_interpretation=True` with no warning (invariant 8). Required for 0.2.7 (R1, second pass 2026-09-27): the minimal repair is a zero-spread guard.
- P-332: Two observations of the closure pass at `1d5e8b81`: `UnitAnalyzer.quality_metrics` accepts unsorted spike times, counting negative inter-spike intervals as violations and reading a wrong duration (`jnwb/analyzers.py:580-593`); and `cross_modal_comparison` does not report its seed (`jnwb/statistics.py:1689-1710`, invariant 5). Required for 0.2.7 (R1, classified 2026-09-27): fold the seed with IB-75, IB-76 and IB-77 of 07-03. The other observations of this row are in 07-26.
- P-332: `UnitAnalyzer.psth` drops spikes at the window edges, 168 of 405 at the left edge and 108 of 405 at the right, while its docstring says the right edge is inclusive; the defect class of IB-81 in 07-03. Required for 0.2.7 (R1, second pass 2026-09-27): bin so that no selected spike falls outside the edges, with both edges as the test.
- P-339: The MCP tool `prepare_signal_reference` tells an agent to slice raw `/data` without `conversion`, `channel_conversion`, `offset` or `starting_time`, and guesses layout from the shape. Required for 0.2.7 (R2, classified 2026-09-27): `jnwb/mcp_server/nwb_tools.py:80-86` tells an agent to slice raw `/data` without conversion, offset or `starting_time`.
- P-345: Other permutation nulls miss draws that reproduce the observed statistic in a different summation order, so p comes out too small: `jrsa`'s `_p_from_null` when x1 has ties (p 0.035 to 0.039 where the exact p is 0.05), `shuffle_r2_ci` with tied scores, `cross_modal_comparison` with periodic spikes (up to 72x), `cluster_permutation_test` when a row of X equals a row of Y, `granger`, `granger_spectral` and `phase_slope_index` with identical trials, and `xflip` at small n (23 of 200 cross 0.05 at n=6). Repairs per site: a tolerance relative to the statistic, `math.fsum`, or sorted rows. Required for 0.2.7 (R1, classified 2026-09-27): anti-conservative p across permutation nulls.
- P-349: `zflip` still reports `adjacent_identifiable=True` and a finite delay from rounding residue for a pair with a constant contact, though `accepted` is now False (invariant 8). Required for 0.2.7 (R1, classified 2026-09-27): reproduce first. Folded from P-348 on 2026-09-27: no test pins the exactness of `zflip`'s constancy check (a `ptp < 1e-6` mutant survives); one joins this check. The other two observations of this row are in 07-26.
- P-353: The readiness check treats any item deleted after the receipt as done, so it cannot tell a finished item from a dropped one (closure pass at `f0d905bf`). Required for 0.2.7 (R4, classified 2026-09-27). The other two edges of this row are in 07-26.

### 07-02 Release-process observations from 0.2.6

Release: required-0.2.7.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/*.py`, `tests/**/*.py`, `.github/workflows/*.yml`, `CONTRIBUTING.md`.
Observed while releasing 0.2.6. RP-5 meets the blocker predicate by the independent
classification of 2026-09-27, and RP-7's minimal check is Hamm's ruling of that date; the rest
is in 07-27 under 0.2.8, and RP-1's ruled bypass removal is the release step 07-29.

- RP-5: Publishing to TestPyPI was skipped on both the tag push and the release run. Check: which event is meant to publish to TestPyPI, and whether the recorded publication order still holds. Ruled 2026-09-25: the tag push publishes to TestPyPI, so PyPI publishes only after TestPyPI succeeded. Required for 0.2.7 (R5, R3, classified 2026-09-27): TestPyPI before PyPI, as `artifacts/fact_stack.md` records and 2026-09-25 ruled.
- RP-7: `artifacts/goal.md` section 8 names suite peak memory as a cost measured before each release, and no check measures it. Required for 0.2.7 (Hamm ruled 2026-09-27, a minimal check): a script measures peak RSS for a fixed set of representative operations and records it before the release, with no threshold yet. `artifacts/goal.md` section 8 names 07-02 as the carrier.

### 07-03 Post-release inspection findings

Release: required-0.2.7.
Role: jnwb-developer. Skill: per finding. Blocked by: none.
Writes: `jnwb/**/*.py`, `scripts/*.py`, `tests/**/*.py`, `docs/**/*.md`, `skills/*/SKILL.md`, `examples/**/*.py`, `README.md`, `CHANGELOG.md`.
Two independent read-only inspections at `e66e70a9`, one of library code, cost and coverage and
one of documentation, skills and the release apparatus. Each bullet carries its receipt in short;
the probes are in the inspection reports. Every bullet here is required for 0.2.7: a lane in
flight, ruled on 2026-09-27, or meeting the blocker predicate by that date's independent
classification. The deferred bullets are in 07-28 under 0.2.8.

- IA-19: two-class `bilinear` `predict_proba` is sigmoid(2 D) and overconfident (held-out bin 0.8 to 0.9 predicts 0.856, observes 0.582) though documented as calibrated; experimental and outside `__all__` (`jnwb/bilinear.py:31`, `134-138`). Check: the documentation stops calling it calibrated, or the claim is removed. Required for 0.2.7 (R1, classified 2026-09-27): the minimal repair is to correct or remove the "calibrated probabilities" claim at `jnwb/bilinear.py:31`; the one-model redesign is in 07-28.
- IB-37: P-63's count is stale: 25 of 160 exports are named in no skill, not 30. Check: P-63's figure corrected where it is quoted, from a recount.
- IB-46: with a `Generator`, the directed estimators record `surrogate_seed_entropy` as `None`, so the result alone cannot reproduce p; this matches `cross_area_coherence`. Check: rule whether to record a child seed. Graded 2026-09-25 highly recommended: record a child seed so the result alone reproduces p. Required for 0.2.7 (R1, classified 2026-09-27): invariant 5; fold with IB-75 and IB-77.
- IB-49: `jrsa`'s null, bootstrap and `lag` act on the last axis (the paired metrics) or axis 0 (the row metrics) whatever `adim` names; 0.2.6.1 discloses it in the docstring and on `docs/03`. Check: rule whether they follow `adim` or refuse a non-default `adim` with a null or a lag. Graded 2026-09-25 minimal expandable: refuse a non-default `adim` when a null or `lag` is used; following `adim` waits. Required for 0.2.7 (R1, classified 2026-09-27): resolve jointly with IB-58.
- IB-58: for the six `jrsa` axis-0 metrics at the default `adim=-1`, `window` slices the feature axis while `lag` and the null act on axis 0. Check: say so in the docstring, or window the observation axis for those metrics. Required for 0.2.7 (R1, classified 2026-09-27): reproduced: `jrsa(x, y, metric='cka', window=(0, 20))` on (200, 40) input windows the features, not the observations, silently.
- IB-72: `select_optimal_lag`, reached only from the deprecated `granger_causality(order='auto')`, still scores each order on its own sample (n - p) while `granger` now uses one common trimmed sample. Check: align it with `granger`'s criteria or state the departure in its docstring. Required for 0.2.7 (R1, classified 2026-09-27): the minimal repair is a common sample for the order selection, or the departure stated.
- IB-89: the Plotly export tests (`tests/test_vis.py::test_canvas_save_and_seal_triple_export`, `tests/test_docs_call_shapes.py` on `docs/vis.md`) still fail under a loaded `-n 12` with "Couldn't close or kill browser subprocess" from choreographer, though they sit in one `xdist_group` under `--dist=loadgroup`; both pass alone. A bounded test-side retry of that shutdown error is in both files and has not yet been seen to fire. Check: a loaded run in which the retry fires and the tests pass, or a cause that removes the error; the Windows 3.12 CI leg under `-n auto` stays green.

### 07-29 Remove the admin bypass of the `dev` deletion rule before the release merge

Release: release-step-0.2.7.
Role: human. Skill: none. Blocked by: none.
Split from RP-1 of 07-27 on 2026-09-27: an action done by hand in the repository settings, before
the release pull request merges.

- RP-1: Remove the admin role's bypass of the `dev` ruleset's deletion rule (ruled 2026-09-25), so
  merging the release pull request cannot delete `dev`; automatic deletion of merged heads stays for
  feature branches. Check: read the ruleset's bypass actors before the merge.

### 07-23 Bound the cycle and simplify the apparatus

Release: required-0.2.7.
Role: jnwb-developer. Skill: none. Blocked by: none.
Ruled 2026-09-27.

- Classify every remaining item as `required-0.2.7` or `deferred-0.2.8` against the blocker predicate of `AGENTS.md` §11: an independent critic classifies, a second pass attacks each deferral; the deferred items move under a `# 0.2.8` heading with their reason. Check: no item unclassified; the ruled items and the lanes in flight stay in 0.2.7.
- `scripts/stack_edit.py`: delete or replace a todo item by id, preserving line endings and asserting the result, with a test. Check: the integrator's stack edits go through it.
- CHANGELOG fragments: one file per change under a fragments directory, assembled into `CHANGELOG.md` at release by a script with a test; `CONTRIBUTING.md` says how. Check: two parallel fragments merge without conflict.
- A draft `AGENTS.md` of about 1500 words: rules and routes only, reasons and incidents moved to `artifacts/rulings/history.md`. Check: Hamm approves the draft before it lands.
- Audit the process tests: for each file under `tests/` that checks docs, stacks, prose, gates or rulings, say whether it executes library code or pins wording, and what evidence of release acceptance it carries. Check: the prune list, with evidence per file, goes to Hamm; nothing is deleted before his ruling.
- Package inventory: exports no skill names and public modules outside `__all__`, with where each is used. Check: the list goes to Hamm; nothing moves this cycle.
- Compact the todo stack to one line per item (id, surface, check), detail moved to `artifacts/evidence/0.2.7/`. Check: no item's check is lost.

## Out of 0.2.7 scope

Carried from 0.2.6. Each needs its own authorization.

- Raw-data-to-NWB conversion.
- An authorization or permission subsystem.
- Benchmark execution; the design is retained and marked unrun (06-33).
- A capability-by-capability matrix over the whole public surface.
- Repository minimization: dead tests, hand-transcribed examples, root and documentation cleanup, beyond the audit and inventory of 07-23.
- Dataset-specific package code, and new estimators that only improve a demonstration.
- The 36 unverified review findings, except where an item reaches one.

## Acceptance

`AGENTS.md` §11, the same three conditions as 0.2.6, measured against `artifacts/goal.md`.

# 0.2.8

Deferred from 0.2.7 by the 2026-09-27 scope ruling (`artifacts/rulings/2026-09-27.md`). Each item and
bullet here meets every deferral condition of `AGENTS.md` §11 by the independent classification of
that date, and carries its reason; the second pass of 07-23 attacks each deferral, and one that
could make release evidence falsely pass returns to 0.2.7.

### 07-26 Findings carried from 0.2.6, deferred to 0.2.8

Release: deferred-0.2.8.
Role: jnwb-developer. Skill: per finding. Blocked by: none.
Writes: `jnwb/**/*.py`, `scripts/*.py`, `tests/**/*.py`, `docs/**/*.md`, `skills/*/SKILL.md`, `examples/**/*.py`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`.
Split from 07-01 on 2026-09-27. Each finding below meets every deferral condition of `AGENTS.md`
section 11 by the independent classification of that date, and carries its reason. A packet
takes one finding and narrows the write set to its paths.

- P-01: `scripts/docs_build.py` writes `site/` inside the repository, and the test suite also creates `site/` mid-run with no build invoked, so no read-only packet can establish that the strict docs build passes while keeping the tree clean. Deferred: changes no shipped behaviour and invalidates no release evidence; 06-36 builds into a temporary directory.
  deferred-0.2.8: site/ written in tree; no shipped behaviour or evidence; 06-36 builds to tmp.
- P-08: Two reproduced review findings carry wrong counts: `doc-assets/module-map-omits-nwb-entry-points` says 36 omitted exports where a probe counts 35, and `ai-plumbing/agent-roles-exist-but-ship-nowhere` says five roles where six exist. Deferred: record counts only.
  deferred-0.2.8: record counts only; P-63 count carried by IB-37.
- P-20: The unit-to-layer composition works through existing exports and no document or skill shows it. Deferred: documentation only; planned as 06-89 in `artifacts/planned_post_0.2.6.md`.
  deferred-0.2.8: documentation of an existing composition only.
- P-36: Reading computational order off the source was wrong on six specs: five predicted a gap the measurement did not find, and one exponential case a reading of the loop structure would miss; a nested loop is not evidence of the order it looks like. Deferred: a method finding, not a code defect; planned as 06-87.
  deferred-0.2.8: method finding, not a code defect.
- P-76: `examples/quickstart_jnwb.py` writes two tracked files and `docs/quickstart.md:55` tells the reader to run it; the SVG carries a `<dc:date>` and random `<path id=...>` hashes, so every run dirties the checkout. `rcParams["svg.hashsalt"]` plus `metadata={"Date": None}` gives byte-identical SVG, and the PNG is already deterministic (re-measured 2026-09-23). Deferred: no shipped behaviour or evidence; `docs/generate_figures.py` is already held to its outputs by a test.
  deferred-0.2.8: quickstart dirties checkout; no behaviour/evidence.
- P-84: `tests/test_docs_call_shapes.py` missed documented calls that raise: its arity check was one-sided, dotted receivers were skipped, and `docs/10` had no fences. The code half is landed (`Signature.bind`, a per-page import map, receivers at any depth, a `docs/10` table collector that fails on an unresolved row). Deferred, upheld by the deferral attack on 2026-09-23: what remains is P-167's record correction and the type oracle.
  deferred-0.2.8: code half landed; remainder is P-167 record + type oracle.
- P-90: 06-44 declared its write target in prose ("the documentation page that names the keys"), and no page names `fdr_pval`: a pointer born wrong, and no gate resolves prose write targets. Deferred: a prose target cannot be resolved mechanically; the repair is a gate that rejects a `Writes:` field naming a path outside backticks.
  deferred-0.2.8: prose write targets; process gate.
- P-102: The repository mixed line-ending conventions with no rule and no check (`artifacts/*.md` and three `skills/*/SKILL.md` CRLF; `AGENTS.md`, `scripts/`, `tests/` and `docs/` LF): a byte-mode edit anchored with the wrong ending matches nothing, and `git apply` refuses mismatched context. `.gitattributes` now declares `-text` and Gate 16 fails a mixed file; the wholesale conversion Gate 16 cannot see is P-159. Deferred: whether to level the conventions is a ruling.
  deferred-0.2.8: levelling line endings is Hamm's ruling to make; Gate 16 fails mixed files.
- P-119: Three lanes (06-19, 06-21, 06-22) each read the highest problem id as P-107 and wrote `P-108` into an `xfail` reason for three different defects; a worktree cannot see ids allocated after it was cut, and the packet contract allocates none. All four references were renumbered on integration. Deferred: the repair is a packet that carries the allocated id or a named placeholder.
  deferred-0.2.8: id allocation in packets; renumbered on integration.
- P-154: Scheduling fields carried prose that quoted field labels, so neither parsed: 11 defects across 10 items in one pass; the shapes were notes spliced into a blocker field (06-30, 06-36, 06-27, 06-06), prose quoting a label inside its own item (06-31, 06-80), and five stale blockers hidden behind them, including 06-105 naming itself. All 11 were repaired by hand. Deferred: the durable half is a gate 15 check for a blocker naming no live item, an item naming itself, and a second field label in one item.
  deferred-0.2.8: stack-parser hardening; repaired by hand.
- P-155: Ruling items 06-13 and 06-67 asked for evidence that committed artifacts already held (`artifacts/evidence/0.2.6/compress_fp32_default_candidates.md`, `compress_fp32_policy.md`, `missingness_table.md`), because each artifact named its item and the item never named it back; the unread missingness table held unrecorded defects (P-157, P-158) and a fourth candidate, `c3d`. Deferred: the durable half is a backlink check (an artifact naming a live todo id in its first 12 lines that the item does not name back), measured at 3 links with 2 broken, then 0 after repair.
  deferred-0.2.8: backlink check; process only.
- P-162: Lane concurrency compared `Writes:` strings, so `docs/*.md` and `docs/08_directed_connectivity_and_information.md` read as disjoint though they name one file: 33 string-disjoint pairs of dispatchable work shared a tracked file, and a greedy batch of eighteen split into six once tokens were resolved against `git ls-files`. The parser also invented the write set `repaired` for 06-17. Deferred, upheld by the deferral attack on 2026-09-23: the 0.2.6 waves are scheduled on resolved paths; the gate expands each token with `fnmatch` against `git ls-files`, fails a token matching nothing, and fails an empty field unless the Role is `verifier` or `human ruling`.
  deferred-0.2.8: separate worktrees surface overlap as merge conflict, not silent loss.
- P-167: P-84's record was partly wrong: the corpus did reach `docs/02`, `docs/07` and `docs/09` (25, 17 and 9 calls); a fourth cause was the per-fence import map (why P-78 survived, found when mutant M3 survived the repair of the three recorded causes); `docs/10` has no fences of any kind; and the module docstring was right about P-82. The code half is repaired. Deferred: P-79b, P-79c and P-82 are wrong-type calls that bind cleanly and need a type oracle, planned as 06-110.
  deferred-0.2.8: wrong-type calls need a type oracle (06-110).
- P-171: `test_the_value_is_a_density_not_an_integrated_power` does not catch `signal.welch(..., scaling="spectrum")`, though it catches `mean -> sum`; the scaling mutant is killed by `test_band_power_is_the_mean_psd_over_the_band` instead. Deferred: the class is covered and only the test's name misleads.
  deferred-0.2.8: class covered by another test; name only.
- P-190: `acquisition_channel` raises `AcquisitionNotFoundError` for a series found with `timestamps` and no constant `rate`, so a caller catching "not found" to try another name reads a present series as absent. Deferred: the message says "has no constant sampling rate" and no rate is invented; a new exception class is a public API decision.
  deferred-0.2.8: message true; new exception class is an API decision.
- P-191: A contributor install without the `vis` extra fails the tests that sweep `jnwb.__all__` (19 counted by one lane, 21 by another in a git-less export). Deferred: false failures, never false passes; the test legs install the extra, and the CI smoke step and release-gate STEP 7 check the no-extra state.
  deferred-0.2.8: false failures only, never false passes.
- P-192: `enrich_units_dataframe` on a units table without `peak_channel_id` fills `area=None`, `layer='Unknown'` and `group_name=None` on every row with no warning, and `docs/02_paths_addressing_metadata.md` does not state the prerequisite. Deferred: unknown values rather than wrong labels, ratified by `tests/test_substitution_class_sweep.py`; planned as 06-90.
  deferred-0.2.8: Unknown values, not wrong labels; ratified by sweep.
- P-196: No test pins `psi_freqs` or `psi_per_freq[0]` of `phase_slope_index`: zeroing the first bin or shifting the frequencies by half a bin survives every PSI-touching module. Deferred: the output is correct and its sign and spectrum are pinned.
  deferred-0.2.8: PSI output correct; test gap.
- P-197: The checkout-provenance scanners miss ten spellings (an annotated alias, a two-step alias, `jnwb.__path__`, `inspect.getfile`, `Path.cwd()`, tuple unpacking, `pathlib.Path('skills/..')`, `open('docs/..')`, `Path('./skills')`, `os.path.join('scripts', ..)`), and the test-path scanner accepts five more (`sys.path[:0] = [ROOT]`, `insert(1, ROOT)`, `insert(0, ROOT / 'scripts' / '..')`, `import sys as _s; _s.path.insert(0, ...)`, and any plant in `tests/__init__.py`). No live instance. Deferred: the installed-wheel CI leg, with `test_import_provenance.py`, fails a checkout-pinned test.
  deferred-0.2.8: installed-wheel leg catches a checkout-pinned test.
- P-198: `run_full_preflight` records a failed gate once and nothing pins it: removing the de-duplication passes all 26 tests. Deferred: reachable only when a gate fails and then raises, and a duplicate record cannot hide a failure.
  deferred-0.2.8: duplicate record cannot hide a failure.
- P-199: `examples/tutorials/09_open_data.py` checks the tick rate across three segments and nothing pins it: checking only the `window` segment passes all 5 tests. Deferred: the rate derivation is pinned; the unpinned part is a redundant cross-check.
  deferred-0.2.8: redundant cross-check unpinned.
- P-203: `relative_power(model="log_ratio")` computes `10*log10` in `jnwb/spectral.py` instead of calling `to_db`, a retyped copy of the rule invariant 7 of `AGENTS.md` section 4 asks callers to reuse. Deferred: the same formula, so no number differs.
  deferred-0.2.8: same formula, no number differs.
- P-204: `ContainerTypeContradictionWarning` fires on LFP `ElectricalSeries` stored in `uV` (pynwb reports volts with `conversion=1.0`, so values are out by 1e6) and blames the declared type when only the unit is wrong: 78 of 96 corpus warnings. Deferred: it errs toward caution, and separating a unit-scale error from a type error is a public message choice.
  deferred-0.2.8: errs toward caution; message wording is a public choice.
- P-209: merged into P-284 on 2026-09-27; the identifiers it names are measured there.
  deferred-0.2.8: non-shipping trees; merge with P-284/IB-71.
- P-216: Branches that behave correctly and that no test pins, found by surviving mutants: the `/acquisition` bare-name ambiguity refusal, the gradients crossover default in `jnwb.vis`, a second contradicting interpreter sentence (gate 8 reads the first), a paraphrase of the unscoped delay instruction, direct `sys.modules.clear()` in the collection-order detector, the `jnwb.vis` vocabulary beyond a grep, and `VISp6a/b` splitting into a spurious area. Deferred: every branch behaves correctly on the live tree, and `VISp6a/b` is an edge no corpus here carries. Removed as stale on 2026-09-27: the STEP 0a claim-spelling branch, whose check was removed on 2026-09-23.
  deferred-0.2.8: branches behave correctly; STEP 0a clause moot by its own text.
- P-218: Gate 2 still excuses a directory at the path of a stale worktree registration: a deleted worktree re-created with a `.git` file pointing at the root's `.git` or another worktree's admin directory is listed, not prunable, and passes the identity check. Deferred: it needs a counterfeit at a stale registration's exact path and none exists here; the repair checks that the admin `gitdir` file points back at the directory.
  deferred-0.2.8: needs a counterfeit at a stale registration path.
- P-219: Gate 2's PASS message reads `(no .agents/skills/ duplicate)` though the gate checks every `SKILL.md` outside `skills/`. Deferred: the check is wider than its message and no verdict changes.
  deferred-0.2.8: message narrower than check; no verdict changes.
- P-220: An empty group named `session_description`, read with the waiver, raises `ValueError: already exists in root.groups` instead of reading `""` or raising `MissingRequiredNWBFieldError`, and the missingness table has no row for it. Deferred: the read still fails loudly on a malformed file; the repair is a table row and a named error.
  deferred-0.2.8: fails loudly on malformed file.
- P-221: `ContainerTypeContradictionWarning` is raised through public reads and not exported, so filtering it by name needs a submodule import. Deferred: emitted and documented, and it changes no value; exporting it is a decision.
  deferred-0.2.8: exporting is a decision; changes no value.
- P-227: The `phase_slope_index` jackknife leaves out one segment rather than one epoch, so its z is conservative under the null: 400 null draws give sd 0.669 and P(|z|>2) = 0.005 at the default overlap; the divergence is documented at the function. Deferred: conservative, so it cannot make evidence falsely pass; the repair is an epoch-level jackknife.
  deferred-0.2.8: conservative jackknife, cannot falsely pass.
- P-228: The name `vflip` collides with the published vFLIP of Mendoza-Halliday 2024, a different procedure; the `jnwb/laminar.py` module docstring states the difference. Deferred: a rename changes public API, which is Hamm's to rule.
  deferred-0.2.8: rename is a public API ruling.
- P-229: The vflip calibration receipt hashes `inspect.getsource` of the estimator, docstrings included, so a documentation-only edit invalidates it. Deferred: it fails closed; the repair hashes code without docstrings.
  deferred-0.2.8: fails closed.
- P-230: `aperiodic_fit` fits without removing peaks first, unlike Donoghue 2020: a 10 Hz peak moves the exponent from 2.000 to 2.157; the function documents this and advises fitting a peak-free range. Deferred: documented use is correct, and changing the fit changes shipped values, which is Hamm's to rule. Graded 2026-09-25 recommended: keep; an opt-in `remove_peaks=` comes later.
  deferred-0.2.8: documented; graded keep 2026-09-25.
- P-231: The `phase_locking_index` Rayleigh p-value comment quotes the second-order formula while the code computes the first-order one; at n = 10 the two and a Monte Carlo reference differ by at most 0.0004. Deferred: the code is correct; the comment is to be aligned.
  deferred-0.2.8: comment only; code correct.
- P-232: Gate 15 and gate 17 read only `###` item headings while STEP 0a reads items at any heading depth, so they disagree on an item under `####`. Deferred: STEP 0a is the wider reader, so the gates can only under-read; the repair shares one parser. Removed as stale on 2026-09-27: the premise that the gates read only `06-` ids (`scripts/harness_gate.py:1682` reads any two-digit cycle).
  deferred-0.2.8: gates can only under-read `####`, the stack has none; premise partly stale.
- P-235: The stated-gate-count test scans the instruction surfaces but not `skills/` or `docs/`, and matches digits but not number words or "Gates 1 to N". Deferred: the one live stated count is covered and correct.
  deferred-0.2.8: the live stated count is correct.
- P-238: `scripts/mutation_harness.py`'s `collect_selector` drops every node id containing a space, so such a parametrized discriminator cannot be named in `must_fail`. Deferred: it fails closed (the selector is rejected) and cannot produce a false kill.
  deferred-0.2.8: fails closed; no false kill.
- P-241: The contrast check in `tests/test_figure_form.py` exempts each generator's `THEMES` table and parses only 6-digit hex and `white/black/k/w`, so a dark `fg` of `#202020` or a named color such as `navy` passes. Deferred: widening the parser. The eye-check of each regenerated dark variant is required, in 07-01.
  deferred-0.2.8: widening the parser; each figure regenerated this cycle is eye-checked under the required half, in 07-01.
- P-242: `unit_census_report` with the default grouping, on a frame lacking `area` or `depth_class` and with no `layer`, drops those columns without a warning. Deferred: this matches the documented filter to available columns and gives no wrong number; an explicit `group_by` warns.
  deferred-0.2.8: matches documented filter.
- P-244: `apply_tight_auto_axis` floors the y lower limit at 0, so negative values in signed data (z-scores, LFP) are drawn outside the axes. Deferred: display only; the docstring and skill row state it.
  deferred-0.2.8: display only, stated.
- P-245: `assign_quality_tier` maps an unknown quality code (anything but 0 or 1) to `'unstable'` instead of refusing it. Deferred: conservative and stated in the skill row; refusing it is an API change.
  deferred-0.2.8: conservative; refusal is an API change.
- P-246: `paired_fire_prob_test(rng=<int>)` raises `AttributeError` rather than a checked `TypeError`. Deferred: a loud failure with no wrong value.
  deferred-0.2.8: loud.
- P-254: `Canvas.save_and_seal` and the `docs/vis.md` export block fail with kaleido's "Couldn't close or kill browser subprocess" when several kaleido exports run at once on this machine (two or more concurrent suites; a 24-way stress run also hung); CI runs the suite serially and has not shown it. Deferred: it fails loudly; a red local run naming this test is re-run alone before it is read.
  deferred-0.2.8: same failure IB-89 serializes; closes with IB-89.
- P-255: `causal_exp_smooth(tau_ms=0)` returns all NaN with only a RuntimeWarning instead of raising. Deferred: loud, with no plausible-looking value.
  deferred-0.2.8: loud NaN.
- P-256: Two errors name the wrong thing: `binary_occupancy_mutual_information` and `spike_count_mutual_information` name `spike_mutual_information`, and `build_permutation_plan(labels, None)` raises a bare `TypeError` without naming `groups`. Deferred: each raises, so this is message quality only. Removed on 2026-09-27 as a duplicate of P-190: the series with no constant rate raising `AcquisitionNotFoundError`.
  deferred-0.2.8: message quality; third clause duplicates P-190.
- P-257: `ComplexTFR(device=...)` accepts any string as its device record. Deferred: only a hand-built `ComplexTFR` can carry a false record; `complex_tfr` sets it from the resolver.
  deferred-0.2.8: only hand-built ComplexTFR.
- P-258: The `_backend.py` row of `tests/test_substitution_class_sweep.py` gives `gpu_available` as its reason but now also covers `jax_metal_available`. Deferred: a reason string; the sweep's check is unchanged.
  deferred-0.2.8: reason string only.
- P-259: Rule F7 of the documentation contract (no fact that no gate or test enforces) conflicts with 06-51's "no fact present before is absent after"; the import timings in `docs/install.md` are the example, kept. Deferred: which rule wins is Hamm's to rule, and keeping the facts cannot mislead.
  deferred-0.2.8: needs a rule-precedence ruling.
- P-264: `phase_slope_index` with some bands undefined sums `net` over the defined bands while its docstring says "the whole requested range". Deferred: flagged by `ok_for_interpretation` and stated in the skill row.
  deferred-0.2.8: flagged by ok_for_interpretation and skill row.
- P-265: With one value per group the ANOVA is NaN but `eta_squared` reads 1.0 beside it. Deferred: the arithmetic is right (no within-group variation) and cannot make a p or a flag pass.
  deferred-0.2.8: arithmetic correct; no p/flag passes.
- P-266: `scripts/computational_contract_gate.py` tracks argument aliases without regard to order, so an argument overwritten before it reaches the switch counts as reaching it, and its static checks accept one correct path among several. Deferred: stated in the gate's docstring; no live export has the shape, and `tests/test_execution_switch.py` and `tests/test_precision_switch.py` hold the live behaviour.
  deferred-0.2.8: limit stated; switch tests hold live behaviour.
- P-267: No skill routes the `jnwb.ontology` objects, and the exclusion comment in `tests/test_skill_symbol_coverage.py` points to a workflow no skill has. Deferred: the exclusion is deliberate and tested; routing belongs to the skills `artifacts/fact_stack.md` plans beyond the ten of 0.2.6.
  deferred-0.2.8: deliberate tested exclusion; routing is 0.2.8 skills.
- P-268: No single maintained capability map covers the public surface. Deferred: a capability-by-capability matrix is frozen out of 0.2.6, and the module map is checked against the exports.
  deferred-0.2.8: capability matrix is out of scope.
- P-269: No diagram shows the scientific-semantics distinctions (magnitude, direction, delay, inference). Deferred: the goal requires none; the four diagrams on `docs/architecture.md` meet the canonical-model line.
  deferred-0.2.8: goal requires no such diagram.
- P-274: STEP 0a leaves four HTML heading forms unparsed: a `<b>`-wrapped id, an anchor before the id, a heading over three lines, and `Release&#58;`. Deferred: the stack uses no HTML heading.
  deferred-0.2.8: stack uses no HTML headings.
- P-275: `tests/test_vis_draws_no_default_landmark.py` misses a negative default (`UnaryOp`) and a body fallback such as `0.5 if crossover_depth is None`. Deferred: the code has a default of neither form.
  deferred-0.2.8: code has neither default form.
- P-276: The figure-form self-test does not pin the changed-pixel slack: raising it from 1e-5 to 2e-4 passes, and a real one-digit edit changes 8.1e-5 to 9.1e-5 of the pixels. Deferred: the constant at HEAD is 1e-5.
  deferred-0.2.8: constant at HEAD is correct.
- P-277: The architecture reachability test misses an agent named only in an edge label, nodes labelled "Assistant" or "LLM", and phrases such as "requires an LLM agent", and it fails a legitimate `subgraph` line. Deferred: the current pages violate none of these.
  deferred-0.2.8: current pages violate none.
- P-278: In `docs/architecture.md` the routing diagram asks "inference supported?" before "inputs present?", an order no skill or `artifacts/direction.md` states, and the dependency diagram omits h5py, hdmf, matplotlib, scikit-learn, statsmodels and joblib. Deferred: a presentation choice and an incomplete list, not a wrong edge.
  deferred-0.2.8: presentation choice.
- P-279: The tuple check in `tests/test_skills_validation.py` counts elements only, so a swapped return order in `rdm_similarity` or `exact_sign_flip` survives it. Deferred: `tests/test_rsa.py` and `tests/test_statistics.py` kill both swaps.
  deferred-0.2.8: swaps killed elsewhere.
- P-280: Minor text: the open-data example's "within a millisecond" (6-9 ms measured); `plot_decoding_timecourse` promises a CI ribbon and cluster bars the caller supplies; `rdm_similarity`'s Step 5 and wPLI's zero-lag threshold are stated only in docstrings; `correlate`'s note says `test=` for `method=`; the quickstart's "single trial" PSI wording; `population_trajectory` warns under a short context name. Deferred: none changes a value or a documented contract.
  deferred-0.2.8: wording; no value or contract changes.
- P-281: `TestJrsaIsUnitFree::test_cuda_matches_cpu` compares CPU with CPU. Deferred: `jrsa` has no GPU path and warns on a device request.
  deferred-0.2.8: jrsa has no GPU path.
- P-282: `scripts/docs_form_gate.py` and the older tests (`tests/test_documentation_form.py`, `tests/test_docs_user_navigation.py`, `tests/test_figure_form.py`) assert F1, F5, N1, N2, N5 and G2 on the live tree twice, with only the corpus and vocabulary readers shared; the gate imports private helpers from two test modules; the old F1 test misses `#####`. Deferred: both copies must pass, so nothing passes falsely, and the gate covers the `#####` gap.
  deferred-0.2.8: both copies must pass.
- P-283: In `_timestamps_fate`, a regular `timestamps` array beside a `starting_time` with no `rate` attribute does arithmetic with `None`, so `convert` raises `TypeError`, now also through `select=`. Deferred: a loud failure with no wrong value.
  deferred-0.2.8: loud TypeError.
- P-284: Comments in `scripts/` (134 identifiers in 7 files) and `tests/` (641 in 98 files) cite item and problem ids, which the head rule of `AGENTS.md` keeps out; many are literals the stack parsers and their fixtures need, and no gate separates the two. Deferred: neither directory ships, and the ids change no behaviour or evidence. Merged here on 2026-09-27: P-209 and IB-71, which count the same identifiers. IB-71's check: a sweep that removes them or rewrites them as plain reasons, then gate 14 extended to both folders with an allowlist for machine-required literals.
  deferred-0.2.8: non-shipping; merge IB-71 and P-209 here.
- P-285: The xflip calibration receipt hashes the estimator's source text including comments, so a comment edit forces a 130 s recalibration. Waits: it can only fail when nothing is wrong, never pass when something is.
  deferred-0.2.8: fails closed only.
- P-287: The trial-mean view check reads a list one level deep: `[[P[0]],[P[1]]]` and a list of memoryviews pass. Deferred: `np.asarray` copies these, under the copy limit ruled acceptable on 2026-09-23.
  deferred-0.2.8: copies under ruled limit.
- P-288: `scripts/docs_form_gate.py` leaves `docs/tutorials/*.md` outside F1, F5 and F2, and misses a `####` heading indented one to three spaces. Deferred: measured with the gate's own functions, the live tree has 0 violations of either.
  deferred-0.2.8: live tree 0 violations.
- P-289: The MCP writes-nothing test snapshots only the file's directory and the working directory, and the no-`jnwb.testing` check is static and misses `importlib.import_module`. Deferred: no current code path writes or imports that way.
  deferred-0.2.8: no current path writes/imports that way.
- P-290: The ruled test taxonomy (`CONTRIBUTING.md:154`) is enforced by nothing. Deferred: no evidence depends on it. Removed as stale on 2026-09-27: the `CONTRIBUTING.md` sentence calling the four-outcome routing tests planned, which no longer appears there.
  deferred-0.2.8: remainder only: taxonomy unenforced; first half stale.
- P-291: `stream_npz_array` accepts `Ellipsis` on a 0-d array where its docstring says it raises `TypeError`. Deferred: NumPy accepts it too, so the value is right and the docstring is wrong.
  deferred-0.2.8: value right, docstring wrong.
- P-292: After a `cupy.linalg` call in a plain script, `compute_population_trajectory(device='cuda')` computes on the CPU and warns "no usable CUDA device was found via PyTorch". Deferred: `device_used` is `cpu` and invariant 6 holds; the wording misstates the cause (P-261's DLL conflict).
  deferred-0.2.8: device_used correct; wording.
- P-294: `acquisition_channel` does not resolve behavior containers under `processing/` (e.g. `processing/behavior/EyeTracking`) and raises "No acquisitions or processing continuous series found" while `inspect` lists them. Deferred: loud, changes no number.
  deferred-0.2.8: loud.
- P-295: Gate 14's identifier pattern passes `items/06-55`, `P-1000` and `p-29`, and fails a month-day `09-23`. Deferred: the live tree is clean and the false positive fails closed.
  deferred-0.2.8: live tree clean; false positive fails closed.
- P-296: Dangling internal references in `jnwb/`: `nwb_tfr_storage_spec.md` (`compression.py:14`, `__init__.py:49,52`, untracked) and `artifacts/benchmarks/...` (`laminar.py:78`, `spectral.py:486,966`, pruned from the sdist); development-history comments such as the excluded-date note at `artifact_repair.py:445`. Deferred: no behavioural or scientific effect.
  deferred-0.2.8: dangling refs, no behavioural effect; merge with IA-29.
- P-297: The `compare_multiple_groups` docstring omits that `eta_squared` is NaN for an empty group. Deferred: the value is a loud NaN and the CHANGELOG states it.
  deferred-0.2.8: loud NaN, CHANGELOG states it.
- P-298: `_find_timestamp_paths` walks with `visititems`, which visits an object once under its first name, so a regular timestamps array with an earlier hard-link name is neither collapsed nor refused, and is cast and kept. Deferred: the receipt stays consistent; older than this cycle.
  deferred-0.2.8: rare hard-link layout; receipt consistent.
- P-299: `inspect` reports `packaging` `direct` for wrapped behavior and `FilteredEphys` containers whose `data_path` is nested. Deferred: vocabulary only.
  deferred-0.2.8: vocabulary only.
- P-300: The STEP 0a message truncates item titles. Waits: wording only. Removed on 2026-09-27 as subsumed by the `AGENTS.md` draft of 07-23: the "P-153's row carries why" pointer.
  deferred-0.2.8: wording only; subsumed by 07-23 AGENTS draft.
- P-301: No test pins the removal of an external project's name from `jnwb/vis/sidecar.py`; the author-year check cannot see a project name. Waits: the live tree is clean.
  deferred-0.2.8: live tree clean.
- P-302: Outside `## Open`, a problem-shaped row with its id in column 2 or no id is not counted by STEP 0a. Waits: the Open section, the only place a problem is recorded, is fully checked.
  deferred-0.2.8: Open section fully checked.
- P-303: `inspect` of an in-memory file unwraps the known container types while the file walk unwraps any group holding series, so an unknown container type can differ between the two forms. Waits: known types agree; older than this cycle.
  deferred-0.2.8: known types agree.
- P-304: Mutation-pass coverage gaps with correct code at HEAD: Gate 9's api.md sync is not tested against a same-length drift, the contract gate does not test an export recorded in two order categories, and documented `win_ms=` literals are not checked against `bin_ms`. Waits: no current evidence passes falsely.
  deferred-0.2.8: no evidence passes falsely.
- P-305: `tests/test_semantic_mutation_classes.py` fails on any uncommitted byte change to its target modules, so a full-suite mutation oracle must deselect it, and the CUDA agreement tests kill device mutants only on a GPU machine. Waits: 06-34 accounted for both; a recipe note for the next pass.
  deferred-0.2.8: accounted by 06-34.
- P-307: No CI leg or fresh environment compares the documentation figures: every venv and CI leg has Matplotlib 3.11.2 against figures written by 3.10.8, so all 20 comparisons skip there. Waits: a skip is reported, and the figures pass where they were generated.
  deferred-0.2.8: skips are reported; figures unchanged since v0.2.6.
- P-309: The distribution tests read only `<repo>/dist`, no variable points them at an external build, and `forbidden_entries` rejects no `examples` or `data` component, so keeping `examples/data` out of the wheel rests on a configuration check. Waits: 06-37's byte comparison held at `f657fce7`.
  deferred-0.2.8: 06-37 byte comparison held.
- P-311: Gate 14's identifier check does not read `README.md`, and its vocabulary check does not follow `--8<--` includes, although its docstring says an included page is scanned like any other. Waits: both surfaces are clean at `3f533574`; the closure pass re-runs both probes at the release HEAD.
  deferred-0.2.8: clean; closure pass re-probes at release HEAD.
- P-312: `compare_old_new_criteria` given a nullable `is_stable` raises on a new-side `<NA>` and reads an old-side `<NA>` as unscreened. Waits: not exported, and no caller passes `is_stable`.
  deferred-0.2.8: not exported, no caller.
- P-313: The stability panel coerces with `astype(bool)`, so a caller's text flag column (`"False"`, `"0"`) plots every unit Stable. Waits: jnwb writes `is_stable` as `boolean`; display only.
  deferred-0.2.8: display only.
- P-314: `acquisition_channel` cannot read a `BehavioralEvents` series from a file by any name while `inspect` reports it; `_WRAPPED_SERIES_ATTR` has no entry for it, and `BehavioralEpochs` and the ophys containers were not probed. Waits: loud, no number wrong; same root as P-294 and P-303.
  deferred-0.2.8: loud.
- P-315: `_whole_bin_count` gives a malformed message ("Use , or ...") for a reversed window or a negative bin, and its tolerance at about 3e7 bins was not rechecked after 06-145 scaled it. Waits: both fail loudly on unrealistic input.
  deferred-0.2.8: loud on unrealistic input.
- P-317: `docs/02_paths_addressing_metadata.md` says a stored entry is seeked past what a slice skips; on 3.12.0 it is read forward instead, so the cost grows with the slice's position there. Waits: values are correct, the docstring and CHANGELOG state the exception, and the page is at its tabled length.
  deferred-0.2.8: values correct; exception stated.
- P-319: The test of the withdrawn refractory keys uses `assertWarnsRegex`, which accepts any number of warnings, so a second `FutureWarning` per call survives it. Waits: shipped behaviour warns once in 60 of 60 calls.
  deferred-0.2.8: one warning in 60/60; moot after P-318.
- P-320: At large absolute times the whole-bin refusal prints the refused and the suggested window as the same text (`.10g`), and `{n:g}` can print a whole bin count for a window 1e-6 of a bin off. Waits: error path only; the refusal is correct.
  deferred-0.2.8: error path only.
- P-321: `confirmatory_compare` returns `correction: "none"` beside BH `q_*` values and `confirmed_*` flags. Waits: the key describes the raw `pval` fields beside it, and the q-values are named separately.
  deferred-0.2.8: key describes raw pval; q named separately.
- P-322: `get_all_units_metadata(filter_quality=True)` on a file with no `quality` column raises a `KeyError` handled as a read failure, where the CHANGELOG says a `RuntimeWarning`. Waits: loud, and those units would be excluded anyway.
  deferred-0.2.8: loud; units excluded anyway.
- P-323: `compute_population_trajectory` leaves out `device_used` when the area has no units. Waits: no trajectory is computed.
  deferred-0.2.8: nothing computed.
- P-324: `compress_fp32(select=)` on a same-file SoftLink writes an independent float32 copy under the link's name while the target stays float64. Waits: nothing requested is miscast; a test pins the behaviour.
  deferred-0.2.8: pinned, nothing requested miscast.
- P-326: `composition_subset_0.2.6.md` still reads "Live defect" for H1-H7, repaired since. Waits: stale internal evidence text.
  deferred-0.2.8: stale internal evidence text.
- P-328: The workflow pins `actions/checkout`, `setup-python`, `upload-artifact` and `download-artifact` to tags, so the repository's SHA-pin requirement for Actions stays off. Waits: those are GitHub-owned and allow-listed; pin them to commits, then turn the requirement on.
  deferred-0.2.8: GitHub-owned actions, allow-listed.
- P-329: A paired difference built by arithmetic (`a` against `a - 0.3`) is not exactly constant, so the paired t is about 6e15 rather than inf. Waits: outside the exact-equality rule the docstring states, and significant either way.
  deferred-0.2.8: outside stated exact-equality rule.
- P-330: STEP 0a matches items by id across the receipt, so renaming a required item's id to a new deferred one after the receipt reads as one item done and one added. Waits: it takes a deliberate rename; P-327's clean-tree check and a rule against new ids after the receipt would close it.
  deferred-0.2.8: needs a deliberate rename; 07-23 compaction keeps ids.
- P-331: Zero-spread guards that exact equality cannot reach: `jrsa` standardises the residue of a detrended constant or linear row, the coherence and Granger residual-variance `> 0` guards see the same residue, and `bilinear`'s `std < 1e-9` cutoff is a fixed tolerance. Waits: each needs a numerical tolerance, which is a choice, and identical segments are degenerate input. The PSI jackknife clause is required, in 07-01.
  deferred-0.2.8: degenerate identical segments; tolerance is a choice.
- P-332: Observations of the closure pass at `1d5e8b81`: flat input in `fit_exponential_onset`, `population_trajectory` and `rdm`; the `UnitAnalyzer` sklearn multi-class error; `cka` and `rv` give about 1e-33 on a constant pattern; project-history text in `nam.py` and `bilinear.py`; the `imaginary_coherency` docstring and docs/04 sign sentence; `_phase_slope`'s docstring says normal-approximation p where the code uses t; `plot_sorted_heatmap(category_labels)` is ignored; `jrsa(align='bogus')` is accepted when lengths are equal. Waits: each is loud, degenerate input, display or wording. Removed as stale on 2026-09-27: the wPLI and icoh flat-channel observation, repaired (a probe returns all NaN), and the docs/10 `zflip` row said to raise on zero imaginary coherency (`docs/10_operation_specifications.md:118` makes no such claim). The `quality_metrics`, seed and `psth` edge observations are required, in 07-01.
  deferred-0.2.8: loud, degenerate, display or wording; wPLI/icoh clause stale.
- P-333: No test catches `is_constant(ignore_nan=True)` regressing to plain max/min, because its NaN case sits in a row whose std is exactly 0. Waits: the code is verified correct.
  deferred-0.2.8: code verified correct.
- P-334: `_spread.zscore` on a slice holding plus or minus inf returns `[-inf, -inf, nan]` where the removed per-module code returned NaN. Waits: only non-finite input, where neither output meant anything.
  deferred-0.2.8: non-finite input only.
- P-335: Review the omission project's laminar curation pull request (ruled 2026-09-24): composable public parts plus a thin orchestrator, every threshold a parameter with a cited default, new WM and outside-cortex labels, a discriminator per rule, units in micrometres, and no project vocabulary. Waits: new capability, arriving after the 0.2.6 tag.
  deferred-0.2.8: new capability (external PR review).
- P-336: A refusal has no test: `acquisition_channel` on a `channel_conversion` whose length is not the channel count (a mutant removing the check survived 121 tests). Waits: it behaves correctly today. Folded into P-327 in 07-01 on 2026-09-27: the STEP 0a `git status` clause.
  deferred-0.2.8: it behaves correctly.
- P-337: `acquisition_channel`'s unit-contradiction warning names only `conversion=` although `channel_conversion` is applied too, and its `starting_time` warning points at `nwb_inspect.py` rather than the caller's line. Waits: the messages are true and complete in substance.
  deferred-0.2.8: messages true.
- P-338: `compress_fp32(select=)` can still cast an irregular timestamps array that a second link opens; through a hard link the two names then disagree by up to 2.4e-7 s. Waits: opt-in, unchanged since 0.2.5, and recorded in `stored_dtype_note`.
  deferred-0.2.8: opt-in, recorded in stored_dtype_note.
- P-340: `compute_psd` and `compute_multitaper_psd` return rounding residue (1e-33 to 1e-23) for a constant trace instead of zero. Waits: they return arrays with no positivity guard to mislead.
  deferred-0.2.8: residue, no positivity guard to mislead.
- P-341: Three documentation claims verified at `d42abd9c` have no test guarding them: the docs/03 direction table and population skill row for the directed `jrsa` metrics, the docs/03 loop that replaces `sliding=True`, and the extent of the source window in the docs/08 transfer-entropy formula (a mutant writing `t-u-l` for `t-u-l+1` survived). Waits: each is correct today.
  deferred-0.2.8: each correct today.
- P-342: Gate 19 hashes the first definition of a registered name, so a later redefinition or module-level rebinding passes, and it accepts a killing test whose class part is wrong or whose name appears only inside a string. Waits: no registered name is bound twice today, and every listed test was re-killed independently.
  deferred-0.2.8: no name bound twice today; closure pass re-probes at release HEAD.
- P-343: For float32 input whose top two singular values nearly coincide (relative gap 1.5e-5), CPU and CUDA PCA return different components; unchanged since before the sign-pin repair. Waits: document that device parity is undefined below working precision.
  deferred-0.2.8: below working precision; document parity undefined.
- P-344: `compress_fp32` wall time still rises 2.4x from 800 to 1600 series although its operation count is linear; the extra slope is HDF5's per-operation cost in large groups. Waits: the quadratic link scan is gone, and files with that many series are rare.
  deferred-0.2.8: linear op count; HDF5 per-op cost.
- P-346: The tie tolerance of `exact_sign_flip` and `shuffle_pvalue_paired` over-counts when one difference is 1e11 or more times the others (p up to +0.027 at 1e13), and no test pins its size (cutting it from 8 eps to 1 eps survives). Waits: conservative, and only at unphysical dynamic range.
  deferred-0.2.8: conservative, unphysical range.
- P-347: `TFRAccumulator.mean` returns a copy, so `acc.mean[...] = x` no longer writes through; nothing in the repository does this. Waits: stated in the docstring.
  deferred-0.2.8: stated; no user.
- P-348: Three verified behaviours have no test that would catch a regression: `compress_fp32` resolving a relative soft link from its own group, the `select=` message for a soft-linked regular timestamps array, and the constant-channel NaN of `wpli` and `imaginary_coherency` on CUDA. Waits: each was observed correct at `c7949748`. Folded into P-349 in 07-01 on 2026-09-27: the `zflip` constancy-check clause.
  deferred-0.2.8: observed correct.
- P-349: CPU and CUDA `wpli` differ for a channel one ulp from constant; the `starting_time` alignment patterns in README and docs/common_mistakes raise `TypeError` for a series stored with timestamps. Waits: the first predates this cycle's repairs and the second fails loudly. The `zflip` constant-contact observation is required, in 07-01.
  deferred-0.2.8: one-ulp device edge; docs pattern fails loudly.
- P-350: `permutation_test` and `shuffle_pvalue_unpaired` report `significant=True` at the p floor with a NaN `observed_difference` when finite inputs have a pooled sum beyond 1.8e308; before the centring they reported p 1.0, also wrong. Waits: no physical input reaches it; a guard returning NaN on non-finite centred values is the repair.
  deferred-0.2.8: no physical input reaches it.
- P-351: `vflip` reports `support_score = log(max(1e-12, metric))`, so a metric at or below zero reads as the score -27.63 rather than as no support; a consumer comparing probes saw identical scores on two unrelated probes and suspected a sentinel. Waits: such fits are rejected at the 3.75 gate either way; the repair reports -inf or NaN with the reason.
  deferred-0.2.8: rejected at the 3.75 gate.
- P-352: The installed-wheel smoke script in `scripts/release_gate.py` runs only when the release gate reaches its seventh step, so an exact key set in it went stale for a whole cycle while the suite stayed green. Waits: it fails closed, refusing a correct wheel rather than passing a wrong one; the repair runs the extracted script against the tree in the suite.
  deferred-0.2.8: fails closed.
- P-353: Two release-gate and `vflip` edges from the closure pass at `f0d905bf`: the smoke step keeps `PYTHONPATH` where the tutorial step strips it; and a caller's `vflip` `min_support_score` at or below -27.63 accepts a zero-support fit at the floor value (P-351). Waits: the smoke script asserts a `site-packages` import, and the default threshold is 3.75. The readiness-check edge is required, in 07-01.
  deferred-0.2.8: smoke asserts site-packages import; default threshold 3.75.

### 07-27 Release-process observations from 0.2.6, deferred to 0.2.8

Release: deferred-0.2.8.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/*.py`, `tests/**/*.py`, `.github/workflows/*.yml`, `CONTRIBUTING.md`.
Split from 07-02 on 2026-09-27. Observed while releasing 0.2.6; each observation below meets
every deferral condition of `AGENTS.md` section 11 and carries its reason.

- RP-1: Merging the release pull request deleted `dev`: the repository deletes merged heads, and the `dev` ruleset's deletion rule lets the admin role bypass always. It was restored at the merge commit. Check: switch off automatic deletion of merged heads, or restrict the bypass, and say which in `CONTRIBUTING.md`'s release steps. Ruled 2026-09-25: remove the admin bypass of the `dev` deletion rule, which is the release step 07-29; automatic deletion of merged heads stays for feature branches. What stays here is saying so in `CONTRIBUTING.md`'s release steps.
  deferred-0.2.8: repository setting; no artifact or evidence effect; the ruled bypass removal is the release step 07-29.
- RP-2: STEP 0e resolved the newest CI run for the commit, a pull-request run still in progress, and refused although the push run for the same commit had passed. Check: whether a concluded green run for the exact commit suffices, and test the choice.
  deferred-0.2.8: fails closed (false refusal).
- RP-3: `scripts/release_gate.py` stops at its first failing step, and each run takes 12 to 30 minutes; 0.2.6 needed four runs, one lost to a stale `artifacts/state.md`. Check: run the cheap checks (state freshness, the extracted smoke script, the release body) before the suite.
  deferred-0.2.8: release-gate speed only.
- RP-4: At release the full CI matrix ran four times on one commit (the `main`, `dev` and tag pushes and the release event), and the release run queued behind the tag run in one concurrency group, about 45 minutes before the PyPI approval was requested. Check: skip a run on a commit whose tree already passed, and measure the saving.
  deferred-0.2.8: CI cost only.
- RP-7: A threshold on the peak memory the 0.2.7 check records, and its place beside wall time in the release gate's suite step. The minimal measurement is required, in 07-02.
  deferred-0.2.8: a threshold needs the measurements the 0.2.7 check records first.
- CI guard hardening: the floors and matrix pytest steps still accept exit-masking forms a test does not refuse (`| tee` without pipefail, `! pytest`, a step `if:`, `shell: bash {0}` with a trailing command, `--collect-only` through `PYTEST_ADDOPTS`, a narrowed suite); the Resolve step is not scanned for `set +e`, a re-upgrade after the constrained install passes, and only `env.FLOOR_PYTHON` is checked; the browser-shutdown retry has two copies and only the `tests/test_vis.py` one is tested.
  deferred-0.2.8: every form needs a deliberate workflow edit, and the six named forms are refused.
- RNG surface: the dataset builders now accept an `rng`-style seed but still annotate `seed: int`, and the walk that collects stochastic parameters finds only those named `rng` or `seed`, so a differently named one escapes it.
  deferred-0.2.8: an annotation changes no behaviour, and the walk's blind spot is a coverage gap over parameters that already resolve through `resolve_rng`.
- Depth declaration guard: `vflip` accepts a declared `depth_axis` that is not monotone along the rows, such as the stagger column of a staggered shaft with `shallow_end="min"`, and anchors on it. Check: a criterion for an axis the declaration may name (monotone, or varying along the shaft), refused otherwise, with the staggered case as the test.
  deferred-0.2.8: the anchor is recorded on the result and the motif test still rejects a contradicted fit; what counts as a depth axis is a scientific choice left open this cycle.
- `classify_layer_from_depth` reads electrode z as depth (larger is deeper) with no declared shallow end, where NWB fixes no sign for z.
  deferred-0.2.8: the docstring states the rule, and the 2026-09-27 ruling keeps the depth declaration in the laminar functions; widening it is a ruling.
- Deprecations to complete: `spectral_tilt`'s `exponent` key is removed, leaving `slope`, and `relative_power` raises `ValueError` for a baseline with fewer dimensions than `power`, where it now warns with `FutureWarning`.
  deferred-0.2.8: ruled 2026-09-27 to land one release after the warning.
- Response-significance wording: the bursting limit (about 30% of units below 0.05 at no effect) holds for bursts of spikes 4 ms apart and falls to about 19% at 50 ms, which the docstring, `docs/06`, the spiking skill and the changelog do not say; the claim has four homes and the test pins only the rate; `RenamedKeyDict.setdefault` on a renamed key inserts a shadow key; `docs/04` grew past its ceiling with release-transitional clauses the changelog already carries.
  deferred-0.2.8: the direction of the limit is right everywhere and the classifier's effect-size cut keeps bursting units from reading significant; the rest is wording and length.

### 07-28 Post-release inspection findings, deferred to 0.2.8

Release: deferred-0.2.8.
Role: jnwb-developer. Skill: per finding. Blocked by: none.
Writes: `jnwb/**/*.py`, `scripts/*.py`, `tests/**/*.py`, `docs/**/*.md`, `skills/*/SKILL.md`, `examples/**/*.py`, `README.md`, `CHANGELOG.md`.
Split from 07-03 on 2026-09-27. From the two read-only inspections at `e66e70a9`; each bullet
below meets every deferral condition of `AGENTS.md` section 11 and carries its reason.

- IA-19: The one-model redesign of two-class `bilinear` `predict_proba`, which is sigmoid(2 D) and overconfident (held-out bin 0.8 to 0.9 predicts 0.856, observes 0.582): one model for two classes and a calibration test (`jnwb/bilinear.py:134-138`). Correcting the "calibrated" claim is required, in 07-03.
  deferred-0.2.8: experimental and outside `__all__`; the required half corrects the calibration claim.
- IA-23: `bootstrap_ci` resamples in a Python loop (11 times slower than vectorised at n 200), and `UnitAnalyzer.psth` calls it every time (`jnwb/statistics.py:1177-1181`). Check: vectorise; the random stream changes, so values move under a fixed seed and need a changelog entry or a ruling. Graded 2026-09-25 recommended: keep the loop now; a vectorised path lands later with a version note.
  deferred-0.2.8: graded keep 2026-09-25; same order, constant factor; RNG stream change needs a version note.
- IA-28: tests that assert too little: `bilinear` checks only a length, and the `jrsa` multi-lag test checks a shape over a fixture that evaluates to NaN. Check: value-pinning tests for IA-04 and IA-19.
  deferred-0.2.8: jrsa multi-lag values pinned elsewhere; bilinear half goes with IA-19.
- IA-29: unbacked claims and project leftovers ship in the wheel: `nam` cites a missing script and receipts and calls `torch.manual_seed`, which resets the global torch stream; `REWARD_WINDOW_MS` is a task constant no function uses; `artifact_repair` cites two missing scripts; `layer_masks_path` hardcodes project output folders. Check: extend P-296's sweep to these; use a local `torch.Generator`.
  deferred-0.2.8: non-exported modules; 07-23 inventory lists them; nam.py:114 global torch seed is an invariant-5 smell, fixing changes values.
- IB-44: ruled 2026-09-25, a calibrated block bootstrap for the `jrsa` paired metrics replaces the 0.2.6.1 refusal. Check: coverage of a 95% interval near 0.95 on independent AR(1) pairs at phi 0.9, with a stated block rule.
  deferred-0.2.8: current refusal is correct, and its text names no version.
- IB-45: `directed_network` with an int `rng` (the default 0) gives every pair the same surrogate stream, while a `Generator` draws one seed per pair. Check: one scheme for both, recorded per pair.
  deferred-0.2.8: each pair's permutation p stays valid; only cross-pair dependence changes.
- IB-48: `jrsa` accepts `device='cuda'` and `backend='cupy'` but its permutation loop never reaches the CuPy branch and records `cpu`/`numpy`. Check: route it or drop the branch, and say which in the docstring.
  deferred-0.2.8: records cpu/numpy truthfully; dead branch.
- IB-56: the `quickstart_inputs` fixture in `tests/test_docs_smoke.py` seeds a fresh `default_rng(0)`, so its arrays differ from the ones the quickstart page draws in sequence; a docs-smoke pass says the calls run, not that the page's numbers do. Check: build the inputs by executing the page's own setup lines.
  deferred-0.2.8: quickstart states no numeric output except IB-40's.
- IB-60: the coherence GPU-fallback test compares only p and the observed spectrum, so a device path that uses a different shift set with the same band counts passes it. Check: record the shift each estimator call receives and assert the fallback's list equals the CPU run's.
  deferred-0.2.8: p and spectrum equality is the number invariant 6 protects.
- IB-61: the skill-coverage test still excludes `PopulationAnalyzer`, `TFRAnalyzer` and `UnitAnalyzer` as class facades over routed functions, but they compute on their own (`UnitAnalyzer.psth` bins itself with a closed last bin, unlike `bin_spikes`; `population_trajectory` runs its own covariance SVD; `raster`, `autocorrelogram`, `quality_metrics`, `extract_band`, `by_layer` have no public counterpart), and the router's GPU table names `PopulationAnalyzer.population_trajectory` and `UnitAnalyzer.autocorrelogram`, which have no routing row. `network_connectivity` and `pie_chart_data` are now routed. Check: routing rows or de-export for the rest, then a reason the test can verify.
  deferred-0.2.8: routing completeness; no wrong value.
- IB-63: `skills/jnwb-landmark-viz/SKILL.md` routes by `jnwb.vis` module, not by the per-operation `jnwb.fn(args)` rows the template's routing section describes, so no signature check covers its rows. Check: per-function rows for the `vis` extra, checked against `inspect.signature` when plotly is installed.
  deferred-0.2.8: a stale row raises loudly.
- IB-71: merged into P-284 on 2026-09-27 as its duplicate; its check is carried there.
  deferred-0.2.8: duplicate of P-284.

### 07-05 A downstream paper agent can consume jnwb

Release: deferred-0.2.8.
Deferred to 0.2.8, classified 2026-09-27: new downstream capability; IA-27 tests ride with it.
Role: jnwb-developer. Skill: per skill. Blocked by: none.
Reads: `artifacts/direction.md` (the four outcomes, Boundary), `artifacts/planned_post_0.2.6.md`, `jnwb/ontology.py`, `jnwb/paths.py`.
Writes: `jnwb/*.py`, `tests/*.py`, `skills/*/SKILL.md`, `docs/*.md`, `CONTRIBUTING.md`, `CHANGELOG.md`.
Ruled 2026-09-25: a paper-reproduction agent lives downstream, pinned to a jnwb release, with its
claim registry, decline tree, reference outputs and scorer. jnwb gains only what that agent cannot
do without and every NWB consumer can use. The preflight it scores through is
`jnwb.preflight`.
- a. A script scores decline accuracy from `jnwb.preflight` alone: the outcome, the reason and
  the missing inputs it returns as data.
- b. A result names the exact input it came from: the NWB file's sha256 (`paths.sha256_file`) and
  the object path. Use `Provenance` or `Lineage` if they can carry it; add a field only if not.
  IA-27's tests for `paths.resolve_nwb_path`, `sha256_file` and `require` land here.
- c. `CONTRIBUTING.md` states the intake: a downstream miss classified as a jnwb defect enters the
  problem stack as a generic row with a synthetic discriminator; a missing capability goes through
  the capability gate.
Accept: a test per outcome in (a); a round-trip test in (b) that writes a result's dict and
re-opens the same file by path and hash; Gate 6 passes.
Stop: anything that names a study, a paradigm or a DANDI id in `jnwb/`, `skills/` or `docs/`.

### 07-08 The router composes the minimal skill set a task needs

Release: deferred-0.2.8.
Deferred to 0.2.8, classified 2026-09-27: router architecture, feature.
Role: jnwb-developer. Skill: jnwb. Blocked by: none.
Writes: `skills/jnwb/SKILL.md`, `skills/jnwb/agents/openai.yaml`, `tests/test_skill_router_reach.py`.
Plan step 1, second bullet. Reproduced at `dcb75f12`: section 2 of the router
(`skills/jnwb/SKILL.md:11-23`) maps each task phrase to one skill, so a task spanning several
reaches the first match only. The plan's two examples are the acceptance cases: plotting supplied
arrays reaches `jnwb-figures` and `jnwb-qc`; comparing a band between two conditions reaches
paradigm, NWB data, spectral, statistics, figures and QC. The `jnwb-paradigm` and `jnwb-qc` rows are
added by 07-10 and 07-11 in their own changes.
Accept: `tests/test_skill_router_reach.py` holds a table of tasks and the skill set each requires,
the plan's two examples among them, and every case passes for the skills that exist; a case naming a
skill not yet created is `xfail(strict=True)`, so its arrival forces the marker off.
Stop: a task needs a skill outside the planned set of the fact stack.

### 07-09 Composition tests over the chains the router sequences

Release: deferred-0.2.8.
Deferred to 0.2.8, classified 2026-09-27: follows 07-08; new tests of new composition.
Role: jnwb-developer. Skill: per chain. Blocked by: 07-08.
Writes: `tests/test_composition_*.py`.
Plan step 1, fourth bullet. Reproduced at `dcb75f12`: the operation-level chains H1 to H9 of
`artifacts/evidence/0.2.6/composition_subset_0.2.6.md` are pinned in five
`tests/test_composition_*.py` modules, and the four-outcome routing tests landed as
`tests/test_skill_decline_behaviour.py`. Open: no test composes operations of two skills in the
order the router sequences them, where each call is correct and the order of aggregation, an
identifier carried across the skill boundary, or a substituted signal class is wrong. Graded
recommended: the minimal base is the plan's band-comparison task as one chain; further chains follow
the composed rows 07-08 adds.
Accept: each new chain runs on unequal dimensions and on inputs where the right and wrong orders
give separated values, fails on the wrong composition and passes on the right one; a chain correct
today is pinned as a regression guard with the mutation that kills it recorded in its docstring.
Stop: a chain is wrong today and its repair needs a path outside `Writes`.

### 07-10 `jnwb-paradigm`: experiment structure, timing and condition semantics

Release: deferred-0.2.8.
Deferred to 0.2.8, classified 2026-09-27: new skill.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Reads: `artifacts/fact_stack.md` (skill creation is capability-gated), `docs/errors.md` (the waived-requirements table).
Writes: `skills/jnwb-paradigm/SKILL.md`, `skills/jnwb-paradigm/agents/openai.yaml`, `skills/jnwb/SKILL.md`, `skills/jnwb-nwb-data/SKILL.md`, `tests/test_skills_validation.py`, `tests/test_skill_decline_behaviour.py`, `tests/test_skill_router_reach.py`, `AGENTS.md`, `docs/agents.md`.
Plan step 2, first bullet. Reproduced at `dcb75f12`: no `skills/jnwb-paradigm/` exists and
`CANONICAL_SKILLS` (`tests/test_skills_validation.py:34-44`) lists nine skills; the operations it
would route (`events`, `EventTable`, `resolve_interval_table`, `EpochCollection`,
`epoch_continuous`, `detect_trial_cycles`) are routed from `skills/jnwb-nwb-data/SKILL.md` (lines
20-23, 41 and 76) or, for `EpochCollection`, by no skill. The plan's prerequisite, the 06-67
missingness ruling, was ruled on 2026-09-22 (event flag) and is implemented:
`jnwb_waived_requirements` is in `jnwb/nwb_io.py` and `docs/errors.md`. Condition meaning comes from
explicit metadata first and structural inference last; an undocumented code is reported, never
named.
Accept: the skill meets the template in `CONTRIBUTING.md` and all four outcomes in
`tests/test_skill_decline_behaviour.py`, with an undocumented condition code as its decline case;
each row it takes over leaves `jnwb-nwb-data`; its router row and its `AGENTS.md` section 7 row
exist; Gate 2 and Gate 6 pass.
Stop: the capability gate of the fact stack is not met; a condition vocabulary would enter the
skill.

### 07-11 `jnwb-qc`: independent scientific and output QC

Release: deferred-0.2.8.
Deferred to 0.2.8, classified 2026-09-27: new skill.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Reads: `artifacts/fact_stack.md` (skill creation is capability-gated).
Writes: `skills/jnwb-qc/SKILL.md`, `skills/jnwb-qc/agents/openai.yaml`, `skills/jnwb/SKILL.md`, `skills/jnwb-figures/SKILL.md`, `skills/jnwb-nwb-data/SKILL.md`, `tests/test_skills_validation.py`, `tests/test_skill_decline_behaviour.py`, `tests/test_skill_router_reach.py`, `AGENTS.md`, `docs/agents.md`.
Plan step 2, second bullet. Reproduced at `dcb75f12`: no `skills/jnwb-qc/` exists; `visual_qc` is
routed from `skills/jnwb-figures/SKILL.md:18` and `audit_units` and `audit_electrodes` from
`skills/jnwb-nwb-data/SKILL.md:71`, while `Result`, `Provenance` and `Lineage` are named by no
skill. The split makes the skill that draws a figure a different one from the skill that judges it.
Accept: the skill meets the template in `CONTRIBUTING.md` and all four outcomes in
`tests/test_skill_decline_behaviour.py`; `visual_qc`, `audit_units`, `audit_electrodes`, `Result`,
`Provenance` and `Lineage` each have one routing row, in this skill only; its router row and its
`AGENTS.md` section 7 row exist; Gate 2 passes.
Stop: the capability gate of the fact stack is not met.

### 07-12 Route the public exports no skill names

Release: deferred-0.2.8.
Deferred to 0.2.8, classified 2026-09-27: routing coverage; follows 07-10 and 07-11.
Role: jnwb-developer. Skill: per skill. Blocked by: 07-10, 07-11.
Writes: `skills/*/SKILL.md`, `tests/test_skill_symbol_coverage.py`.
Plan step 2, third bullet (P-63). Reproduced at `dcb75f12` with a word scan of every
`skills/*/SKILL.md` against `jnwb.__all__`: 25 exports appear in no skill (`AlignedDataset`,
`Alignment`, `ChannelIndexError`, `DB_AGGREGATIONS`, `DETECTION_TAILS`, `EpochCollection`,
`Interpretation`, `IntervalTableNotFoundError`, `InvalidOnsetValueError`, `JRSAResult`, `Lineage`,
`NWBEventError`, `NWBInspectError`, `ProbeGeometry`, `Provenance`, `Query`, `Question`,
`RELATIVE_POWER_MODELS`, `Result`, `SKILLS_URL`, `SqueezedAttributeWarning`, `TFRAnalyzer`,
`UnitNotFoundError`, `ZFlipResult`, `assert_mergeable`), and 47 carry no routing call. The count
correction of P-63 stays with IB-37 of 07-03 and the analyzer exclusions with IB-61; this item
carries the routing.
Accept: every export is routed by a call row or excluded in `tests/test_skill_symbol_coverage.py`
under a category whose assertion holds for it; the excluded set is smaller than at `dcb75f12` and
each remaining reason is checked by the test.
Stop: routing an export would restate a mathematical definition that belongs in `docs/`.

### 07-13 Skills say each thing once

Release: deferred-0.2.8.
Deferred to 0.2.8, classified 2026-09-27: skill dedup; three short shared lines.
Role: jnwb-developer. Skill: per skill. Blocked by: 07-10, 07-11.
Writes: `skills/*/SKILL.md`, `tests/test_skills_validation.py`.
Plan step 2, fourth bullet. Reproduced at `dcb75f12`: a scan of normalised lines of 40 characters or
more finds three shared by two skills: the volume-conduction safeguard in `jnwb` and
`jnwb-connectivity`, the SVG `<text>` sentence in `jnwb-figures` and `jnwb-landmark-viz`, and one
`docs/09` link in `jnwb-figures` and `jnwb-population`. Verbatim repetition is small; the scan does
not see a skill restating a `docs/` definition in other words, which the Surface section of
`artifacts/direction.md` forbids.
Accept: a test fails when a normalised invariant line appears in two skills, `docs/` links excluded;
each invariant that restates a `docs/` definition is replaced by the link; the summed length of the
existing skills does not grow.
Stop: removing a restatement leaves a routing row that no longer states a dimension its operation
requires.

### 07-18 Skill examples run in the suite

Release: deferred-0.2.8.
Deferred to 0.2.8, classified 2026-09-27: 7 of 9 skill example blocks execute; the 2 failures use placeholder inputs.
Role: jnwb-developer. Skill: per skill. Blocked by: none.
Writes: `skills/*/SKILL.md`, `tests/test_skill_examples_execute.py`.
Deferred 06-26. Reproduced at `dcb75f12`: no test executes a `SKILL.md` example block (the two
example tests, `tests/test_examples_quickstart.py` and `tests/test_open_data_example.py`, read no
skill), and six of nine skills build their inputs from a random generator (`jnwb`,
`jnwb-connectivity`, `jnwb-lfp-spectral`, `jnwb-population`, `jnwb-spiking`, `jnwb-statistics`). The
aim is that a routing example never implies inventing data, not that generators vanish.
Accept: every example block executes in the suite; each declares its input class (real NWB,
deterministic array, stochastic synthetic, calibration fixture), the test checks the declaration,
and a normal routing example uses one of the first two.
Stop: an example needs data the repository does not carry.

### 07-21 A public NWB mutation API

Release: deferred-0.2.8.
Deferred to 0.2.8, classified 2026-09-27: public API; Hamm rules first.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Reads: `artifacts/fact_stack.md` (NWB mutation and execution infrastructure belong in the core).
Writes: `jnwb/*.py`, `tests/*.py`, `docs/*.md`, `CHANGELOG.md`.
Plan, capability-gated, first bullet: validate, write, transform, convert, structural repair and
verified output, then `jnwb-data-engineering` only if the surface warrants one; neither is a
required endpoint. Reproduced at `dcb75f12`: the only writer is `compress_fp32`, a float32 cast;
`nwb_read_io` refuses every mode but `'r'` (ruled 2026-09-23); no export validates, writes, repairs
or verifies an NWB file. Raw-data conversion stays out of 0.2.7 scope. Graded minimal expandable:
the minimal base is a proposed operation set with signatures and refusals, before code.
Accept: each landed operation has a test that re-reads its output and one that it refuses an
ambiguous mapping; API, documentation and tests land before or with any skill.
Stop: every signature here is a public API choice, so the proposed set goes to Hamm before code;
anything that infers condition meaning, anatomy or units.

### 07-22 A public execution and cache API

Release: deferred-0.2.8.
Deferred to 0.2.8, classified 2026-09-27: public API; Hamm rules first.
Role: jnwb-developer. Skill: jnwb. Blocked by: none.
Reads: `artifacts/fact_stack.md` (NWB mutation and execution infrastructure belong in the core), `artifacts/goal.md`.
Writes: `jnwb/*.py`, `tests/*.py`, `docs/*.md`, `CHANGELOG.md`.
Plan, capability-gated, second bullet: device, precision, workers and content-addressed checkpoints,
after numerical identity and performance evidence, then `jnwb-compute` only if the router cannot
carry it. Reproduced at `dcb75f12`: device and precision are resolved privately in
`jnwb/_backend.py` (`working_dtype`, lines 156-174); no export sets a precision or worker policy,
and no module in `jnwb/` mentions a checkpoint or a content address. The order of the fact stack
binds: numerical identity, then the public abstraction, then performance evidence, then routing.
Graded minimal expandable: the minimal base is the identity evidence.
Accept: identity across CPU, parallel CPU and CUDA is shown for every operation the API would cover
before it is public; a cache key includes the input hash, the parameters and the version, with an
invalidation test.
Stop: a control would change a number; the API surface is a public API choice and goes to Hamm
before code.
