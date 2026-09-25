# 0.2.7

Opened 2026-09-24, after 0.2.6 was published to PyPI, on Hamm's instruction.
Items are deleted when done; git, `CHANGELOG.md` and the receipts hold history. The previous cycle's record is
`artifacts/archive/0.2.6/todo_stack_0.2.6.md`, with its closure receipt beside it.

0.2.7 is measured against `artifacts/goal.md` and opens under the three conditions of `AGENTS.md`
§11. Its authorized input is `artifacts/planned_post_0.2.6.md` (07-04), the findings deferred from
0.2.6 (07-01), and what the 0.2.6 release and a post-release inspection observed (07-02, 07-03).
Everything in 07-01 to 07-03 is to be checked: a packet reproduces a finding against its own tree
before it repairs anything, and a finding that does not reproduce is deleted. Rulings are in
`artifacts/rulings/`.

While the 0.2.6.1 patch is open the package version is 0.2.6.1, so the release gate reads
the 0.2.7 items as deferred; they return to `required-0.2.7` when the version becomes 0.2.7.

## How this stack is executed

Every item is a delegation packet in the contract of `skills/jnwb-fact-action` §5; the executing
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
| 0 | 06-201 to 06-204, then 06-205 (the 0.2.6.1 patch) |
| 1 | 07-03 blocker candidates, then the rest of 07-03 |
| 2 | 07-01, triaged against the blocker predicate |
| 3 | 07-02 |
| 4 | 07-04 |

## 0.2.6.1 patch

Ruled 2026-09-25: the silently wrong results and misleading documentation found in the shipped
0.2.6 ship as 0.2.6.1, cut from `dev`. Each item reproduces its finding at `057957aa` first.

### 06-201 `jrsa` circular-shift null

Release: required-0.2.6.1.
Role: jnwb-developer. Skill: jnwb-population. Blocked by: none.
Writes: `jnwb/jrsa.py`, `tests/test_jrsa*.py`, `docs/03_representational_similarity_jrsa.md`, `skills/jnwb-population/SKILL.md`.
The permutation null for paired metrics shuffles time samples as if exchangeable, so on
independent AR(1) pairs at phi 0.9 it rejects about half the time (IA-03, reproduced by both
inspections). Add `null=` with `'circular_shift'` (default), `'block'` and `'iid'`; the result
records the scheme; the skill row and the page name it. The changelog text goes to the dispatcher.
Discriminator: the false-positive rate on independent AR(1) pairs at phi 0.9 is at most 0.08 under
the default, and above it under `'iid'`.
Accept: the discriminator, the existing `jrsa` tests, and an independent verifier's kill of a
mutant that restores the i.i.d. default.

### 06-202 Refuse symbolic transfer entropy

Release: required-0.2.6.1.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `jnwb/connectivity.py`, `tests/test_connectivity.py`, `docs/08_directed_connectivity_and_information.md`, `skills/jnwb-connectivity/SKILL.md`.
`transfer_entropy(estimator='symbolic')` reports significant flow in both directions for a
zero-lag common source with no coupling (IA-01). It now raises, naming `'quantile'`, until a
calibrated null exists. Every caller in the repository, docs and skills included, moves off it.
Accept: the refusal is tested, no document or skill routes to the symbolic estimator, and an
independent verifier kills a mutant that lets it through.

### 06-203 Directed estimators honour `rng`

Release: required-0.2.6.1.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: 06-202.
Writes: `jnwb/connectivity.py`, `tests/test_connectivity.py`, `tests/test_rng_control.py`.
`_rng` maps `rng=None` to seed 0, rejects a `Generator` and truncates a float, so `granger`,
`granger_spectral`, `phase_slope_index` and `transfer_entropy` break their documented contract
and report `seed=None` for stream 0 (IA-02). Route them through `_rng.resolve_rng`; record the seed
actually used. Blocked by 06-202 because both edit one file in one lane.
Accept: `None` differs between calls, the recorded seed reproduces p, a `Generator` is accepted and
a float refused, each in a test; an independent verifier kills a mutant restoring seed 0.

### 06-204 Documentation that invites wrong claims

Release: required-0.2.6.1.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `docs/common_mistakes.md`, `docs/references.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/quickstart.md`, `jnwb/laminar.py`.
Three statements from 07-03, the text of each kept here:

- IB-01 (blocker candidate): `docs/common_mistakes.md:119-121` calls the decoder's accuracy "Unbiased Outer CV Accuracy" computed "without leakage", while `docs/09` says the same function draws row-wise folds that leak across blocks and must be reported as an upper bound (`jnwb/decoding.py:155`, no `groups`); found by both inspections. Check: one statement, the leakage one, on both pages.
- IB-02 (blocker candidate): the PSI row of `docs/common_mistakes.md:161` says PSI tests whether phase differences grow linearly with frequency, "indicating a consistent time delay"; PSI tests neither linearity nor delay (`AGENTS.md` invariant 8); `docs/references.md:43` says "X causes Y when" of Granger, and `docs/api.md:130` summarises `zflip` as a "propagation delay" with no caveat. Check: reword the three sentences, and extend the gate 14 term scan to "causes", "time delay" and "propagation delay" in `docs/` with an allowlist.
- IB-13 (blocker candidate): `docs/06:158` and `docs/quickstart.md:115-121` read `bound_status None` as a valid unconstrained onset estimate, but only t0 is checked against its bound, so 14 of 20 pure-noise PSTHs read valid (t0 30.0, tau at its bound, r2 0). Check: flag a tau bound and low r2, or reword to "t0 not at a bound"; a noise-only PSTH test.

The `zflip` summary line lives in its docstring in `jnwb/laminar.py`; `docs/api.md` is regenerated
by the dispatcher. Only the documentation changes: `bound_status` keeps its behaviour and the page
says what it checks.
Accept: no page calls the decoder unbiased or leak-free, PSI is described as a sign of phase
change, and "causes" and "propagation delay" appear only with the caveat `AGENTS.md` section 5
requires; the docs build and the suite pass.

### 06-205 Release 0.2.6.1

Release: release-step-0.2.6.1.
Role: actor. Skill: none. Blocked by: 06-201, 06-202, 06-203, 06-204. AUTONOMY: none.
Writes: none.
The dispatcher sets the version and the changelog, records an independent closure pass over the
patch as the receipt, and releases as 0.2.6 was: a pull request from `dev` into `main` through the
seven checks, the tag, the GitHub Release whose PyPI job waits for Hamm's approval, and Zenodo.
Accept: PyPI serves 0.2.6.1 and its wheel's `jnwb/` equals the tag byte for byte; a clean install
runs the 06-201 and 06-202 discriminators; Zenodo shows the version.

### 07-01 Findings carried from 0.2.6

Release: deferred-0.2.7.
Role: jnwb-developer. Skill: per finding. Blocked by: none.
Writes: `jnwb/**/*.py`, `scripts/*.py`, `tests/**/*.py`, `docs/**/*.md`, `skills/*/SKILL.md`, `examples/**/*.py`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`.
Each finding below was deferred under `AGENTS.md` section 11 during 0.2.6. A packet takes one
finding and narrows the write set to its paths. The item stays required until each finding is
triaged: one that meets the blocker predicate is repaired in 0.2.7, and one that does not moves to
a `deferred-0.2.8` item with the reason it waits.

- P-01: `scripts/docs_build.py` writes `site/` inside the repository, and the test suite also creates `site/` mid-run with no build invoked, so no read-only packet can establish that the strict docs build passes while keeping the tree clean. Deferred: changes no shipped behaviour and invalidates no release evidence; 06-36 builds into a temporary directory.
- P-08: Two reproduced review findings carry wrong counts: `doc-assets/module-map-omits-nwb-entry-points` says 36 omitted exports where a probe counts 35, and `ai-plumbing/agent-roles-exist-but-ship-nowhere` says five roles where six exist. Deferred: record counts only.
- P-20: The unit-to-layer composition works through existing exports and no document or skill shows it. Deferred: documentation only; planned as 06-89 in `artifacts/planned_post_0.2.6.md`.
- P-36: Reading computational order off the source was wrong on six specs: five predicted a gap the measurement did not find, and one exponential case a reading of the loop structure would miss; a nested loop is not evidence of the order it looks like. Deferred: a method finding, not a code defect; planned as 06-87.
- P-63: 30 public exports are named in no skill, including `TFRAnalyzer`, `UnitAnalyzer`, `PopulationAnalyzer` and the `Query`/`Question`/`Result`/`Interpretation`/`Lineage`/`Provenance` cluster; the seven domain skills otherwise partition 110 operations with one overlap. Deferred: a routing gap that changes no behaviour or evidence.
- P-69: The problem stack's rule section stated a hand-written count of closing dispositions that contradicted its own table and `AGENTS.md` section 2; the sentence was repaired, and nothing checks hand-written counts in that file. Deferred: only the missing check remained, and the 2026-09-23 rewrite of that section removed the counted sentence.
- P-76: `examples/quickstart_jnwb.py` writes two tracked files and `docs/quickstart.md:55` tells the reader to run it; the SVG carries a `<dc:date>` and random `<path id=...>` hashes, so every run dirties the checkout. `rcParams["svg.hashsalt"]` plus `metadata={"Date": None}` gives byte-identical SVG, and the PNG is already deterministic (re-measured 2026-09-23). Deferred: no shipped behaviour or evidence; `docs/generate_figures.py` is already held to its outputs by a test.
- P-84: `tests/test_docs_call_shapes.py` missed documented calls that raise: its arity check was one-sided, dotted receivers were skipped, and `docs/10` had no fences. The code half is landed (`Signature.bind`, a per-page import map, receivers at any depth, a `docs/10` table collector that fails on an unresolved row). Deferred, upheld by the deferral attack on 2026-09-23: what remains is P-167's record correction and the type oracle.
- P-90: 06-44 declared its write target in prose ("the documentation page that names the keys"), and no page names `fdr_pval`: a pointer born wrong, and no gate resolves prose write targets. Deferred: a prose target cannot be resolved mechanically; the repair is a gate that rejects a `Writes:` field naming a path outside backticks.
- P-100: Gate 14 gates 2 of the 6 agent role names: `authority`, `critic`, `actor` and `verifier` are ordinary English, the gap is documented in the constant's comment, and a test keeps those four ungated. Deferred: deliberate; recorded so it is not rediscovered as a defect.
- P-101: `checked >= 65` in the skills signature test sits against 116 rows, so only mass deletion trips it. Deferred: cheap to tighten now that the concurrent lanes have landed, and the coverage test makes the weak floor's failure nearly unreachable.
- P-102: The repository mixed line-ending conventions with no rule and no check (`artifacts/*.md` and three `skills/*/SKILL.md` CRLF; `AGENTS.md`, `scripts/`, `tests/` and `docs/` LF): a byte-mode edit anchored with the wrong ending matches nothing, and `git apply` refuses mismatched context. `.gitattributes` now declares `-text` and Gate 16 fails a mixed file; the wholesale conversion Gate 16 cannot see is P-159. Deferred: whether to level the conventions is a ruling.
- P-119: Three lanes (06-19, 06-21, 06-22) each read the highest problem id as P-107 and wrote `P-108` into an `xfail` reason for three different defects; a worktree cannot see ids allocated after it was cut, and the packet contract allocates none. All four references were renumbered on integration. Deferred: the repair is a packet that carries the allocated id or a named placeholder.
- P-154: Scheduling fields carried prose that quoted field labels, so neither parsed: 11 defects across 10 items in one pass; the shapes were notes spliced into a `Blocked by:` field (06-30, 06-36, 06-27, 06-06), prose quoting a label inside its own item (06-31, 06-80), and five stale blockers hidden behind them, including 06-105 naming itself. All 11 were repaired by hand. Deferred: the durable half is a gate 15 check for a blocker naming no live item, an item naming itself, and a second field label in one item.
- P-155: Ruling items 06-13 and 06-67 asked for evidence that committed artifacts already held (`artifacts/evidence/0.2.6/compress_fp32_default_candidates.md`, `compress_fp32_policy.md`, `missingness_table.md`), because each artifact named its item and the item never named it back; the unread missingness table held unrecorded defects (P-157, P-158) and a fourth candidate, `c3d`. Deferred: the durable half is a backlink check (an artifact naming a live todo id in its first 12 lines that the item does not name back), measured at 3 links with 2 broken, then 0 after repair.
- P-162: Lane concurrency compared `Writes:` strings, so `docs/*.md` and `docs/08_directed_connectivity_and_information.md` read as disjoint though they name one file: 33 string-disjoint pairs of dispatchable work shared a tracked file, and a greedy batch of eighteen split into six once tokens were resolved against `git ls-files`. The parser also invented the write set `repaired` for 06-17. Deferred, upheld by the deferral attack on 2026-09-23: the 0.2.6 waves are scheduled on resolved paths; the gate expands each token with `fnmatch` against `git ls-files`, fails a token matching nothing, and fails an empty field unless the Role is `verifier` or `human ruling`.
- P-167: P-84's record was partly wrong: the corpus did reach `docs/02`, `docs/07` and `docs/09` (25, 17 and 9 calls); a fourth cause was the per-fence import map (why P-78 survived, found when mutant M3 survived the repair of the three recorded causes); `docs/10` has no fences of any kind; and the module docstring was right about P-82. The code half is repaired. Deferred: P-79b, P-79c and P-82 are wrong-type calls that bind cleanly and need a type oracle, planned as 06-110.
- P-171: `test_the_value_is_a_density_not_an_integrated_power` does not catch `signal.welch(..., scaling="spectrum")`, though it catches `mean -> sum`; the scaling mutant is killed by `test_band_power_is_the_mean_psd_over_the_band` instead. Deferred: the class is covered and only the test's name misleads.
- P-190: `acquisition_channel` raises `AcquisitionNotFoundError` for a series found with `timestamps` and no constant `rate`, so a caller catching "not found" to try another name reads a present series as absent. Deferred: the message says "has no constant sampling rate" and no rate is invented; a new exception class is a public API decision.
- P-191: A contributor install without the `vis` extra fails the tests that sweep `jnwb.__all__` (19 counted by one lane, 21 by another in a git-less export). Deferred: false failures, never false passes; the test legs install the extra, and the CI smoke step and release-gate STEP 7 check the no-extra state.
- P-192: `enrich_units_dataframe` on a units table without `peak_channel_id` fills `area=None`, `layer='Unknown'` and `group_name=None` on every row with no warning, and `docs/02_paths_addressing_metadata.md` does not state the prerequisite. Deferred: unknown values rather than wrong labels, ratified by `tests/test_substitution_class_sweep.py`; planned as 06-90.
- P-196: No test pins `psi_freqs` or `psi_per_freq[0]` of `phase_slope_index`: zeroing the first bin or shifting the frequencies by half a bin survives every PSI-touching module. Deferred: the output is correct and its sign and spectrum are pinned.
- P-197: The checkout-provenance scanners miss ten spellings (an annotated alias, a two-step alias, `jnwb.__path__`, `inspect.getfile`, `Path.cwd()`, tuple unpacking, `pathlib.Path('skills/..')`, `open('docs/..')`, `Path('./skills')`, `os.path.join('scripts', ..)`), and the test-path scanner accepts five more (`sys.path[:0] = [ROOT]`, `insert(1, ROOT)`, `insert(0, ROOT / 'scripts' / '..')`, `import sys as _s; _s.path.insert(0, ...)`, and any plant in `tests/__init__.py`). No live instance. Deferred: the installed-wheel CI leg, with `test_import_provenance.py`, fails a checkout-pinned test.
- P-198: `run_full_preflight` records a failed gate once and nothing pins it: removing the de-duplication passes all 26 tests. Deferred: reachable only when a gate fails and then raises, and a duplicate record cannot hide a failure.
- P-199: `examples/tutorials/09_open_data.py` checks the tick rate across three segments and nothing pins it: checking only the `window` segment passes all 5 tests. Deferred: the rate derivation is pinned; the unpinned part is a redundant cross-check.
- P-200: `examples/tutorials/09_open_data.py` says the recording starts within a millisecond of its first spike; the page measures 6 to 9 ms against its enforced 10 ms bound. Deferred: wording only, and the bound is enforced.
- P-203: `relative_power(model="log_ratio")` computes `10*log10` in `jnwb/spectral.py` instead of calling `to_db`, a retyped copy of the rule invariant 7 of `AGENTS.md` section 4 asks callers to reuse. Deferred: the same formula, so no number differs.
- P-204: `ContainerTypeContradictionWarning` fires on LFP `ElectricalSeries` stored in `uV` (pynwb reports volts with `conversion=1.0`, so values are out by 1e6) and blames the declared type when only the unit is wrong: 78 of 96 corpus warnings. Deferred: it errs toward caution, and separating a unit-scale error from a type error is a public message choice.
- P-209: Comments and docstrings in `scripts/` and `tests/` carry item identifiers (for example around the gate 8 and gate 14 helpers in `scripts/harness_gate.py`), which the head rule of `AGENTS.md` keeps out, and no gate scans them. Deferred: neither tree ships, and a comment cannot make a gate or test pass falsely (measured in full as P-284).
- P-216: Branches that behave correctly and that no test pins, found by surviving mutants: the `/acquisition` bare-name ambiguity refusal, the gradients crossover default in `jnwb.vis`, a second contradicting interpreter sentence (gate 8 reads the first), `Claimed by: X; Y closed` spellings in STEP 0a (moot: that check was removed on 2026-09-23), a paraphrase of the unscoped delay instruction, direct `sys.modules.clear()` in the collection-order detector, the `jnwb.vis` vocabulary beyond a grep, and `VISp6a/b` splitting into a spurious area. Deferred: every branch behaves correctly on the live tree, and `VISp6a/b` is an edge no corpus here carries.
- P-218: Gate 2 still excuses a directory at the path of a stale worktree registration: a deleted worktree re-created with a `.git` file pointing at the root's `.git` or another worktree's admin directory is listed, not prunable, and passes the identity check. Deferred: it needs a counterfeit at a stale registration's exact path and none exists here; the repair checks that the admin `gitdir` file points back at the directory.
- P-219: Gate 2's PASS message reads `(no .agents/skills/ duplicate)` though the gate checks every `SKILL.md` outside `skills/`. Deferred: the check is wider than its message and no verdict changes.
- P-220: An empty group named `session_description`, read with the waiver, raises `ValueError: already exists in root.groups` instead of reading `""` or raising `MissingRequiredNWBFieldError`, and the missingness table has no row for it. Deferred: the read still fails loudly on a malformed file; the repair is a table row and a named error.
- P-221: `ContainerTypeContradictionWarning` is raised through public reads and not exported, so filtering it by name needs a submodule import. Deferred: emitted and documented, and it changes no value; exporting it is a decision.
- P-227: The `phase_slope_index` jackknife leaves out one segment rather than one epoch, so its z is conservative under the null: 400 null draws give sd 0.669 and P(|z|>2) = 0.005 at the default overlap; the divergence is documented at the function. Deferred: conservative, so it cannot make evidence falsely pass; the repair is an epoch-level jackknife.
- P-228: The name `vflip` collides with the published vFLIP of Mendoza-Halliday 2024, a different procedure; the `jnwb/laminar.py` module docstring states the difference. Deferred: a rename changes public API and needs a ruling.
- P-229: The vflip calibration receipt hashes `inspect.getsource` of the estimator, docstrings included, so a documentation-only edit invalidates it. Deferred: it fails closed; the repair hashes code without docstrings.
- P-230: `aperiodic_fit` fits without removing peaks first, unlike Donoghue 2020: a 10 Hz peak moves the exponent from 2.000 to 2.157; the function documents this and advises fitting a peak-free range. Deferred: documented use is correct, and changing the fit changes shipped values, which needs a ruling.
- P-231: The `phase_locking_index` Rayleigh p-value comment quotes the second-order formula while the code computes the first-order one; at n = 10 the two and a Monte Carlo reference differ by at most 0.0004. Deferred: the code is correct; the comment is to be aligned.
- P-232: Gate 15 and gate 17 read only `### 06-` item headings while STEP 0a reads items at any heading depth and any id, so they disagree on an item under `####`, and neither gate reads this item. Deferred: STEP 0a is the wider reader, so the gates can only under-read; the repair shares one parser.
- P-234: The `JRSAResult` 0-d shim warns under the name `JRSAResult.p` when a copied `q` is indexed, and `p[-1]` raises without a deprecation warning. Deferred: values, dtype and arithmetic are unaffected; carried with the shim's removal.
- P-235: The stated-gate-count test scans the instruction surfaces but not `skills/` or `docs/`, and matches digits but not number words or "Gates 1 to N". Deferred: the one live stated count is covered and correct.
- P-238: `scripts/mutation_harness.py`'s `collect_selector` drops every node id containing a space, so such a parametrized discriminator cannot be named in `must_fail`. Deferred: it fails closed (the selector is rejected) and cannot produce a false kill.
- P-240: With transparent figure backgrounds, legends lost their opaque box and overlap data: fig07 panel A (text over bars 4-5, both variants) and fig10 panel B. Deferred: legibility only; no value or label changes.
- P-241: The contrast check in `tests/test_figure_form.py` exempts each generator's `THEMES` table and parses only 6-digit hex and `white/black/k/w`, so a dark `fg` of `#202020` or a named color such as `navy` passes. Deferred: this release's dark variants were checked by eye, all 11 legible.
- P-242: `unit_census_report` with the default grouping, on a frame lacking `area` or `depth_class` and with no `layer`, drops those columns without a warning. Deferred: this matches the documented filter to available columns and gives no wrong number; an explicit `group_by` warns.
- P-244: `apply_tight_auto_axis` floors the y lower limit at 0, so negative values in signed data (z-scores, LFP) are drawn outside the axes. Deferred: display only; the docstring and skill row state it.
- P-245: `assign_quality_tier` maps an unknown quality code (anything but 0 or 1) to `'unstable'` instead of refusing it. Deferred: conservative and stated in the skill row; refusing it is an API change.
- P-246: `paired_fire_prob_test(rng=<int>)` raises `AttributeError` rather than a checked `TypeError`. Deferred: a loud failure with no wrong value.
- P-254: `Canvas.save_and_seal` and the `docs/vis.md` export block fail with kaleido's "Couldn't close or kill browser subprocess" when several kaleido exports run at once on this machine (two or more concurrent suites; a 24-way stress run also hung); CI runs the suite serially and has not shown it. Deferred: it fails loudly; a red local run naming this test is re-run alone before it is read.
- P-255: `causal_exp_smooth(tau_ms=0)` returns all NaN with only a RuntimeWarning instead of raising. Deferred: loud, with no plausible-looking value.
- P-256: Three errors name the wrong thing: `binary_occupancy_mutual_information` and `spike_count_mutual_information` name `spike_mutual_information`; `build_permutation_plan(labels, None)` raises a bare `TypeError` without naming `groups`; and a series with no constant rate raises `AcquisitionNotFoundError` although it exists (P-190). Deferred: each raises, so this is message quality only.
- P-257: `ComplexTFR(device=...)` accepts any string as its device record. Deferred: only a hand-built `ComplexTFR` can carry a false record; `complex_tfr` sets it from the resolver.
- P-258: The `_backend.py` row of `tests/test_substitution_class_sweep.py` gives `gpu_available` as its reason but now also covers `jax_metal_available`. Deferred: a reason string; the sweep's check is unchanged.
- P-259: Rule F7 of the documentation contract (no fact that no gate or test enforces) conflicts with 06-51's "no fact present before is absent after"; the import timings in `docs/install.md` are the example, kept. Deferred: needs a ruling on which rule wins, and keeping the facts cannot mislead.
- P-264: `phase_slope_index` with some bands undefined sums `net` over the defined bands while its docstring says "the whole requested range". Deferred: flagged by `ok_for_interpretation` and stated in the skill row.
- P-265: With one value per group the ANOVA is NaN but `eta_squared` reads 1.0 beside it. Deferred: the arithmetic is right (no within-group variation) and cannot make a p or a flag pass.
- P-266: `scripts/computational_contract_gate.py` tracks argument aliases without regard to order, so an argument overwritten before it reaches the switch counts as reaching it, and its static checks accept one correct path among several. Deferred: stated in the gate's docstring; no live export has the shape, and `tests/test_execution_switch.py` and `tests/test_precision_switch.py` hold the live behaviour.
- P-267: No skill routes the `jnwb.ontology` objects, and the exclusion comment in `tests/test_skill_symbol_coverage.py` points to a workflow no skill has. Deferred: the exclusion is deliberate and tested; routing belongs to the skills `artifacts/fact_stack.md` plans beyond the ten of 0.2.6.
- P-268: No single maintained capability map covers the public surface. Deferred: a capability-by-capability matrix is frozen out of 0.2.6, and the module map is checked against the exports.
- P-269: No diagram shows the scientific-semantics distinctions (magnitude, direction, delay, inference). Deferred: the goal requires none; the four diagrams on `docs/architecture.md` meet the canonical-model line.
- P-274: STEP 0a leaves four HTML heading forms unparsed: a `<b>`-wrapped id, an anchor before the id, a heading over three lines, and `Release&#58;`. Deferred: the stack uses no HTML heading.
- P-275: `tests/test_vis_draws_no_default_landmark.py` misses a negative default (`UnaryOp`) and a body fallback such as `0.5 if crossover_depth is None`. Deferred: the code has a default of neither form.
- P-276: The figure-form self-test does not pin the changed-pixel slack: raising it from 1e-5 to 2e-4 passes, and a real one-digit edit changes 8.1e-5 to 9.1e-5 of the pixels. Deferred: the constant at HEAD is 1e-5.
- P-277: The architecture reachability test misses an agent named only in an edge label, nodes labelled "Assistant" or "LLM", and phrases such as "requires an LLM agent", and it fails a legitimate `subgraph` line. Deferred: the current pages violate none of these.
- P-278: In `docs/architecture.md` the routing diagram asks "inference supported?" before "inputs present?", an order no skill or `artifacts/direction.md` states, and the dependency diagram omits h5py, hdmf, matplotlib, scikit-learn, statsmodels and joblib. Deferred: a presentation choice and an incomplete list, not a wrong edge.
- P-279: The tuple check in `tests/test_skills_validation.py` counts elements only, so a swapped return order in `rdm_similarity` or `exact_sign_flip` survives it. Deferred: `tests/test_rsa.py` and `tests/test_statistics.py` kill both swaps.
- P-280: Minor text: the open-data example's "within a millisecond" (6-9 ms measured); `plot_decoding_timecourse` promises a CI ribbon and cluster bars the caller supplies; `rdm_similarity`'s Step 5 and wPLI's zero-lag threshold are stated only in docstrings; `correlate`'s note says `test=` for `method=`; the quickstart's "single trial" PSI wording; `population_trajectory` warns under a short context name. Deferred: none changes a value or a documented contract.
- P-281: `TestJrsaIsUnitFree::test_cuda_matches_cpu` compares CPU with CPU. Deferred: `jrsa` has no GPU path and warns on a device request.
- P-282: `scripts/docs_form_gate.py` and the older tests (`tests/test_documentation_form.py`, `tests/test_docs_user_navigation.py`, `tests/test_figure_form.py`) assert F1, F5, N1, N2, N5 and G2 on the live tree twice, with only the corpus and vocabulary readers shared; the gate imports private helpers from two test modules; the old F1 test misses `#####`. Deferred: both copies must pass, so nothing passes falsely, and the gate covers the `#####` gap.
- P-283: In `_timestamps_fate`, a regular `timestamps` array beside a `starting_time` with no `rate` attribute does arithmetic with `None`, so `convert` raises `TypeError`, now also through `select=`. Deferred: a loud failure with no wrong value.
- P-284: Comments in `scripts/` (134 identifiers in 7 files) and `tests/` (641 in 98 files) cite item and problem ids, which the head rule of `AGENTS.md` keeps out; many are literals the stack parsers and their fixtures need, and no gate separates the two. Deferred: neither directory ships, and the ids change no behaviour or evidence.
- P-287: The trial-mean view check reads a list one level deep: `[[P[0]],[P[1]]]` and a list of memoryviews pass. Deferred: `np.asarray` copies these, under the copy limit ruled acceptable on 2026-09-23.
- P-288: `scripts/docs_form_gate.py` leaves `docs/tutorials/*.md` outside F1, F5 and F2, and misses a `####` heading indented one to three spaces. Deferred: measured with the gate's own functions, the live tree has 0 violations of either.
- P-289: The MCP writes-nothing test snapshots only the file's directory and the working directory, and the no-`jnwb.testing` check is static and misses `importlib.import_module`. Deferred: no current code path writes or imports that way.
- P-290: `CONTRIBUTING.md:265-266` says four-outcome routing tests are planned for 0.2.7 while `tests/test_skill_decline_behaviour.py` has them, and the ruled test taxonomy (`CONTRIBUTING.md:154`) is enforced by nothing. Deferred: a contributor page understates coverage; no evidence depends on it.
- P-291: `stream_npz_array` accepts `Ellipsis` on a 0-d array where its docstring says it raises `TypeError`. Deferred: NumPy accepts it too, so the value is right and the docstring is wrong.
- P-292: After a `cupy.linalg` call in a plain script, `compute_population_trajectory(device='cuda')` computes on the CPU and warns "no usable CUDA device was found via PyTorch". Deferred: `device_used` is `cpu` and invariant 6 holds; the wording misstates the cause (P-261's DLL conflict).
- P-294: `acquisition_channel` does not resolve behavior containers under `processing/` (e.g. `processing/behavior/EyeTracking`) and raises "No acquisitions or processing continuous series found" while `inspect` lists them. Deferred: loud, changes no number.
- P-295: Gate 14's identifier pattern passes `items/06-55`, `P-1000` and `p-29`, and fails a month-day `09-23`. Deferred: the live tree is clean and the false positive fails closed.
- P-296: Dangling internal references in `jnwb/`: `nwb_tfr_storage_spec.md` (`compression.py:14`, `__init__.py:49,52`, untracked) and `artifacts/benchmarks/...` (`laminar.py:78`, `spectral.py:486,966`, pruned from the sdist); development-history comments such as the excluded-date note at `artifact_repair.py:445`. Deferred: no behavioural or scientific effect.
- P-297: The `compare_multiple_groups` docstring omits that `eta_squared` is NaN for an empty group. Deferred: the value is a loud NaN and the CHANGELOG states it.
- P-298: `_find_timestamp_paths` walks with `visititems`, which visits an object once under its first name, so a regular timestamps array with an earlier hard-link name is neither collapsed nor refused, and is cast and kept. Deferred: the receipt stays consistent; older than this cycle.
- P-299: `inspect` reports `packaging` `direct` for wrapped behavior and `FilteredEphys` containers whose `data_path` is nested. Deferred: vocabulary only.
- P-285: The xflip calibration receipt hashes the estimator's source text including comments, so a comment edit forces a 130 s recalibration. Waits: it can only fail when nothing is wrong, never pass when something is.
- P-300: `AGENTS.md` says "P-153's row carries why", which now resolves only through git history; the STEP 0a message truncates item titles. Waits: wording only.
- P-301: No test pins the removal of an external project's name from `jnwb/vis/sidecar.py`; the author-year check cannot see a project name. Waits: the live tree is clean.
- P-302: Outside `## Open`, a problem-shaped row with its id in column 2 or no id is not counted by STEP 0a. Waits: the Open section, the only place a problem is recorded, is fully checked.
- P-303: `inspect` of an in-memory file unwraps the known container types while the file walk unwraps any group holding series, so an unknown container type can differ between the two forms. Waits: known types agree; older than this cycle.
- P-304: Mutation-pass coverage gaps with correct code at HEAD: Gate 9's api.md sync is not tested against a same-length drift, the contract gate does not test an export recorded in two order categories, and documented `win_ms=` literals are not checked against `bin_ms`. Waits: no current evidence passes falsely.
- P-305: `tests/test_semantic_mutation_classes.py` fails on any uncommitted byte change to its target modules, so a full-suite mutation oracle must deselect it, and the CUDA agreement tests kill device mutants only on a GPU machine. Waits: 06-34 accounted for both; a recipe note for the next pass.
- P-307: No CI leg or fresh environment compares the documentation figures: every venv and CI leg has Matplotlib 3.11.2 against figures written by 3.10.8, so all 20 comparisons skip there. Waits: a skip is reported, and the figures pass where they were generated.
- P-308: CI's setup-python installs the newest 3.12 patch, so no leg runs the declared floor 3.12.0, which is how 06-146 shipped unseen. Waits: 06-146 is verified on 3.12.0 by hand; the durable leg changes the CI matrix and Gate 8.
- P-309: The distribution tests read only `<repo>/dist`, no variable points them at an external build, and `forbidden_entries` rejects no `examples` or `data` component, so keeping `examples/data` out of the wheel rests on a configuration check. Waits: 06-37's byte comparison held at `f657fce7`.
- P-310: The sdist ships `AGENTS.md`, the repository's internal working rules, by `MANIFEST.in`. Waits: deliberate; whether it belongs in a distributed artifact needs a ruling.
- P-311: Gate 14's identifier check does not read `README.md`, and its vocabulary check does not follow `--8<--` includes, although its docstring says an included page is scanned like any other. Waits: both surfaces are clean at `3f533574`; the closure pass re-runs both probes at the release HEAD.
- P-312: `compare_old_new_criteria` given a nullable `is_stable` raises on a new-side `<NA>` and reads an old-side `<NA>` as unscreened. Waits: not exported, and no caller passes `is_stable`.
- P-313: The stability panel coerces with `astype(bool)`, so a caller's text flag column (`"False"`, `"0"`) plots every unit Stable. Waits: jnwb writes `is_stable` as `boolean`; display only.
- P-314: `acquisition_channel` cannot read a `BehavioralEvents` series from a file by any name while `inspect` reports it; `_WRAPPED_SERIES_ATTR` has no entry for it, and `BehavioralEpochs` and the ophys containers were not probed. Waits: loud, no number wrong; same root as P-294 and P-303.
- P-315: `_whole_bin_count` gives a malformed message ("Use , or ...") for a reversed window or a negative bin, and its tolerance at about 3e7 bins was not rechecked after 06-145 scaled it. Waits: both fail loudly on unrealistic input.
- P-316: STEP 0a does not see a todo section with no item id and no release field, nor a required bullet inside a deferred item. Waits: neither is an item under the stack's format, the basis of P-302.
- P-317: `docs/02_paths_addressing_metadata.md` says a stored entry is seeked past what a slice skips; on 3.12.0 it is read forward instead, so the cost grows with the slice's position there. Waits: values are correct, the docstring and CHANGELOG state the exception, and the page is at its tabled length.
- P-318: `UnitAnalyzer.autocorrelogram` keeps `refractory_period_violation`, `is_single_unit`, `refr_count` and `baseline_count` in 0.2.6 as NaN with a `FutureWarning` (ruled 2026-09-23); 0.2.7 removes them. Waits: the removal is scheduled by the ruling.
- P-319: The test of the withdrawn refractory keys uses `assertWarnsRegex`, which accepts any number of warnings, so a second `FutureWarning` per call survives it. Waits: shipped behaviour warns once in 60 of 60 calls.
- P-320: At large absolute times the whole-bin refusal prints the refused and the suggested window as the same text (`.10g`), and `{n:g}` can print a whole bin count for a window 1e-6 of a bin off. Waits: error path only; the refusal is correct.
- P-321: `confirmatory_compare` returns `correction: "none"` beside BH `q_*` values and `confirmed_*` flags. Waits: the key describes the raw `pval` fields beside it, and the q-values are named separately.
- P-322: `get_all_units_metadata(filter_quality=True)` on a file with no `quality` column raises a `KeyError` handled as a read failure, where the CHANGELOG says a `RuntimeWarning`. Waits: loud, and those units would be excluded anyway.
- P-323: `compute_population_trajectory` leaves out `device_used` when the area has no units. Waits: no trajectory is computed.
- P-324: `compress_fp32(select=)` on a same-file SoftLink writes an independent float32 copy under the link's name while the target stays float64. Waits: nothing requested is miscast; a test pins the behaviour.
- P-325: The `FutureWarning` for `compress_fp32` without `select=` advises a path that raises `TypeError` on an int16 LFP, so an int16 LFP has no non-deprecated route. Waits: the floats-only rule is ruled; only the advice is wrong.
- P-326: `composition_subset_0.2.6.md` still reads "Live defect" for H1-H7, repaired since. Waits: stale internal evidence text.
- P-327: `release_gate.py` compares the receipt's commit with HEAD but does not refuse a dirty working tree, so uncommitted code at release time would not invalidate the receipt. Waits: the release runs from a clean tree, checked by hand before tagging.
- P-328: The workflow pins `actions/checkout`, `setup-python`, `upload-artifact` and `download-artifact` to tags, so the repository's SHA-pin requirement for Actions stays off. Waits: those are GitHub-owned and allow-listed; pin them to commits, then turn the requirement on.
- P-329: A paired difference built by arithmetic (`a` against `a - 0.3`) is not exactly constant, so the paired t is about 6e15 rather than inf. Waits: outside the exact-equality rule the docstring states, and significant either way.
- P-330: STEP 0a matches items by id across the receipt, so renaming a required item's id to a new deferred one after the receipt reads as one item done and one added. Waits: it takes a deliberate rename; P-327's clean-tree check and a rule against new ids after the receipt would close it.
- P-331: Zero-spread guards that exact equality cannot reach: the PSI jackknife gives z about 2.5e10 and p 0 for identical segments, `jrsa` standardises the residue of a detrended constant or linear row, the coherence and Granger residual-variance `> 0` guards see the same residue, and `bilinear`'s `std < 1e-9` cutoff is a fixed tolerance. Waits: each needs a numerical tolerance, which is a choice, and identical segments are degenerate input.
- P-332: Twelve observations of the closure pass at `1d5e8b81`: wPLI and icoh report coupling with one flat channel; `quality_metrics` accepts unsorted spike times; `cross_modal_comparison` does not report its seed; flat input in `fit_exponential_onset`, `population_trajectory` and `rdm`; `UnitAnalyzer.psth` right-edge rounding and the sklearn multi-class error; the docs/10 `zflip` row says it raises on zero imaginary coherency; `cka` and `rv` give about 1e-33 on a constant pattern; project-history text in `nam.py` and `bilinear.py`; the `imaginary_coherency` docstring and docs/04 sign sentence; `_phase_slope`'s docstring says normal-approximation p where the code uses t; `plot_sorted_heatmap(category_labels)` is ignored; `jrsa(align='bogus')` is accepted when lengths are equal. Waits: each is loud, degenerate input, display or wording.
- P-333: No test catches `is_constant(ignore_nan=True)` regressing to plain max/min, because its NaN case sits in a row whose std is exactly 0. Waits: the code is verified correct.
- P-334: `_spread.zscore` on a slice holding plus or minus inf returns `[-inf, -inf, nan]` where the removed per-module code returned NaN. Waits: only non-finite input, where neither output meant anything.
- P-335: Review the omission project's laminar curation pull request (ruled 2026-09-24): composable public parts plus a thin orchestrator, every threshold a parameter with a cited default, new WM and outside-cortex labels, a discriminator per rule, units in micrometres, and no project vocabulary. Waits: new capability, arriving after the 0.2.6 tag.
- P-336: Two refusals have no test: `acquisition_channel` on a `channel_conversion` whose length is not the channel count (a mutant removing the check survived 121 tests), and STEP 0a when `git status` itself fails (a mutant reading that as clean survived 100). Waits: both behave correctly today, and the stacks are read from HEAD either way.
- P-337: `acquisition_channel`'s unit-contradiction warning names only `conversion=` although `channel_conversion` is applied too, and its `starting_time` warning points at `nwb_inspect.py` rather than the caller's line. Waits: the messages are true and complete in substance.
- P-338: `compress_fp32(select=)` can still cast an irregular timestamps array that a second link opens; through a hard link the two names then disagree by up to 2.4e-7 s. Waits: opt-in, unchanged since 0.2.5, and recorded in `stored_dtype_note`.
- P-339: The MCP tool `prepare_signal_reference` tells an agent to slice raw `/data` without `conversion`, `channel_conversion`, `offset` or `starting_time`, and guesses layout from the shape. Waits: unchanged since it shipped, and `acquisition_channel` is the documented reader.
- P-340: `compute_psd` and `compute_multitaper_psd` return rounding residue (1e-33 to 1e-23) for a constant trace instead of zero. Waits: they return arrays with no positivity guard to mislead.
- P-341: Three documentation claims verified at `d42abd9c` have no test guarding them: the docs/03 direction table and population skill row for the directed `jrsa` metrics, the docs/03 loop that replaces `sliding=True`, and the extent of the source window in the docs/08 transfer-entropy formula (a mutant writing `t-u-l` for `t-u-l+1` survived). Waits: each is correct today.
- P-342: Gate 19 hashes the first definition of a registered name, so a later redefinition or module-level rebinding passes, and it accepts a killing test whose class part is wrong or whose name appears only inside a string. Waits: no registered name is bound twice today, and every listed test was re-killed independently.
- P-343: For float32 input whose top two singular values nearly coincide (relative gap 1.5e-5), CPU and CUDA PCA return different components; unchanged since before the sign-pin repair. Waits: document that device parity is undefined below working precision.
- P-344: `compress_fp32` wall time still rises 2.4x from 800 to 1600 series although its operation count is linear; the extra slope is HDF5's per-operation cost in large groups. Waits: the quadratic link scan is gone, and files with that many series are rare.
- P-345: Other permutation nulls miss draws that reproduce the observed statistic in a different summation order, so p comes out too small: `jrsa`'s `_p_from_null` when x1 has ties (p 0.035 to 0.039 where the exact p is 0.05), `shuffle_r2_ci` with tied scores, `cross_modal_comparison` with periodic spikes (up to 72x), `cluster_permutation_test` when a row of X equals a row of Y, `granger`, `granger_spectral` and `phase_slope_index` with identical trials, and `xflip` at small n (23 of 200 cross 0.05 at n=6). Repairs per site: a tolerance relative to the statistic, `math.fsum`, or sorted rows. Waits: deferred under the 2026-09-23 closure ruling as not a regression from the fourteen repairs; the §11 predicate alone would call it required, so it leads the 0.2.7 work.
- P-346: The tie tolerance of `exact_sign_flip` and `shuffle_pvalue_paired` over-counts when one difference is 1e11 or more times the others (p up to +0.027 at 1e13), and no test pins its size (cutting it from 8 eps to 1 eps survives). Waits: conservative, and only at unphysical dynamic range.
- P-347: `TFRAccumulator.mean` returns a copy, so `acc.mean[...] = x` no longer writes through; nothing in the repository does this. Waits: stated in the docstring.
- P-348: Four verified behaviours have no test that would catch a regression: `compress_fp32` resolving a relative soft link from its own group, the `select=` message for a soft-linked regular timestamps array, the constant-channel NaN of `wpli` and `imaginary_coherency` on CUDA, and the exactness of `zflip`'s constancy check (a `ptp < 1e-6` mutant survives). Waits: each was observed correct at `c7949748`.
- P-349: `zflip` still reports `adjacent_identifiable=True` and a finite delay from rounding residue for a pair with a constant contact, though `accepted` is now False; CPU and CUDA `wpli` differ for a channel one ulp from constant; the `starting_time` alignment patterns in README and docs/common_mistakes raise `TypeError` for a series stored with timestamps. Waits: the first two predate this cycle's repairs and the third fails loudly.
- P-350: `permutation_test` and `shuffle_pvalue_unpaired` report `significant=True` at the p floor with a NaN `observed_difference` when finite inputs have a pooled sum beyond 1.8e308; before the centring they reported p 1.0, also wrong. Waits: no physical input reaches it; a guard returning NaN on non-finite centred values is the repair.
- P-351: `vflip` reports `support_score = log(max(1e-12, metric))`, so a metric at or below zero reads as the score -27.63 rather than as no support; a consumer comparing probes saw identical scores on two unrelated probes and suspected a sentinel. Waits: such fits are rejected at the 3.75 gate either way; the repair reports -inf or NaN with the reason.
- P-352: The installed-wheel smoke script in `scripts/release_gate.py` runs only when the release gate reaches its seventh step, so an exact key set in it went stale for a whole cycle while the suite stayed green. Waits: it fails closed, refusing a correct wheel rather than passing a wrong one; the repair runs the extracted script against the tree in the suite.
- P-353: Three release-gate and `vflip` edges from the closure pass at `f0d905bf`: the readiness check treats any item deleted after the receipt as done, so it cannot tell a finished item from a dropped one; the smoke step keeps `PYTHONPATH` where the tutorial step strips it; and a caller's `vflip` `min_support_score` at or below -27.63 accepts a zero-support fit at the floor value (P-351). Waits: the deletions this cycle are backed by the receipt's verification table, the smoke script asserts a `site-packages` import, and the default threshold is 3.75.


### 07-02 Release-process observations from 0.2.6

Release: deferred-0.2.7.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/*.py`, `tests/**/*.py`, `.github/workflows/*.yml`, `CONTRIBUTING.md`.
Observed while releasing 0.2.6; each is to be checked and either repaired or moved to a
`deferred-0.2.8` item.

- RP-1: Merging the release pull request deleted `dev`: the repository deletes merged heads, and the `dev` ruleset's deletion rule lets the admin role bypass always. It was restored at the merge commit. Check: switch off automatic deletion of merged heads, or restrict the bypass, and say which in `CONTRIBUTING.md`'s release steps.
- RP-2: STEP 0e resolved the newest CI run for the commit, a pull-request run still in progress, and refused although the push run for the same commit had passed. Check: whether a concluded green run for the exact commit suffices, and test the choice.
- RP-3: `scripts/release_gate.py` stops at its first failing step, and each run takes 12 to 30 minutes; 0.2.6 needed four runs, one lost to a stale `artifacts/state.md`. Check: run the cheap checks (state freshness, the extracted smoke script, the release body) before the suite.
- RP-4: At release the full CI matrix ran four times on one commit (the `main`, `dev` and tag pushes and the release event), and the release run queued behind the tag run in one concurrency group, about 45 minutes before the PyPI approval was requested. Check: skip a run on a commit whose tree already passed, and measure the saving.
- RP-5: Publishing to TestPyPI was skipped on both the tag push and the release run. Check: which event is meant to publish to TestPyPI, and whether the recorded publication order still holds.
- RP-6: Locked entries remain under `.git/worktrees/` from earlier lanes. Check: remove them once no process holds them, stopping the fsmonitor daemons first.
- RP-7: `artifacts/goal.md` section 8 names suite peak memory as a cost measured before each release, and no check measures it. Check: record peak memory beside wall time in the release gate's suite step.

### 07-03 Post-release inspection findings

Release: deferred-0.2.7.
Role: jnwb-developer. Skill: per finding. Blocked by: none.
Writes: `jnwb/**/*.py`, `scripts/*.py`, `tests/**/*.py`, `docs/**/*.md`, `skills/*/SKILL.md`, `examples/**/*.py`, `README.md`, `CHANGELOG.md`.
Two independent read-only inspections at `e66e70a9`, one of library code, cost and coverage and
one of documentation, skills and the release apparatus. Each bullet carries its receipt in short;
the probes are in the inspection reports. Bullets marked blocker candidate would meet the blocker
predicate if they reproduce, and go first.

- IA-04 (blocker candidate): `jrsa` `lag` rolls the last axis, which holds features for the six metrics with observations on axis 0, so a lag sweep of cka, rv, rsa, procrustes, dcor or hsic returns one value under every label (`jnwb/jrsa.py:941-956`). Check: assert an axis-0 metric changes with lag on a delayed copy, or refuse `lag` for those metrics.
- IA-05 (blocker candidate, weak): when CUDA fails part-way through the coherence surrogates, the CPU recompute draws new shifts from the advanced `rng`, so p differs from a CPU run under the same seed while the reported seed is unchanged (`jnwb/spectral.py:879-884`, `929-936`). Check: draw the shifts once before the device attempt; test an injected mid-null failure against the CPU result.
- IA-06: the `jrsa` lag is circular (`xp.roll`), so the window recipe of `docs/03` wraps each window's end onto its start (lag 10 gives r 0.46 against 0.998 on the truncated overlap). Check: truncate to the overlap; test on a trended series.
- IA-07: `verify_roundtrip` in `jnwb/compression.py:694` passes a cast under an absolute error of 1e-3, so an all-zero destination passes at volt scale and a correct float32 cast near 5e4 fails. Check: a tolerance relative to max|x| times float32 epsilon; a negative test with a zeroed destination.
- IA-08: `compute_response_metrics` accepts a reversed window and returns a negative spike count with a positive rate (`jnwb/spiking.py:95-135`). Check: refuse start at or after stop for both windows.
- IA-09: `aggregate_to_db` turns a zero baseline into +inf dB with warnings suppressed, where `relative_power` raises on the same input (`jnwb/spectral.py:400-417`). Check: one policy for both, pinned by a test.
- IA-10: `TFRAnalyzer.compare_conditions` reports `n_significant` from uncorrected per-location t-tests (792 of 16000 on null data), and no test runs it (`jnwb/analyzers.py:182-217`). Check: correct for multiple comparisons or label the count uncorrected; a null-data test.
- IA-11: `PopulationAnalyzer.pie_chart_data` silently skips a filter on an absent column, so the counts cover every unit; untested (`jnwb/analyzers.py:671-673`). Check: raise or warn on an unknown key.
- IA-12: `explained_variance` is a scalar ratio in `compute_population_trajectory` and a per-component array of absolute variances in `PopulationAnalyzer.population_trajectory`; `jnwb/trajectory.py:108` cites a `UnitAnalyzer.population_trajectory` that does not exist. Check: one meaning with a deprecation path; fix the reference.
- IA-13: `crossover_depth_um` is the absolute z coordinate when z varies along the shank and rank times pitch otherwise, while `label_layers(depth_range_um=)` always uses rank times pitch (`jnwb/laminar.py:488-495`, `965`). Check: one stated frame; a z-descending geometry test.
- IA-14: `_resolve_electrode_row` falls through from `channel_id` to `id` when a value is missing, switching identifier space silently (`jnwb/addressing.py:109-115`). Check: stop at the first identifier column that exists.
- IA-15: `xflip(rng=None)` seeds from entropy and neither result class records the seed (`jnwb/laminar.py:1276`, `1506`). Check: record the seed; test that it reproduces p.
- IA-16: `jrsa(nan_policy='omit')` on axis-0 metrics drops a feature column rather than the observation (`jnwb/jrsa.py:632-659`). Check: drop along the observation axis.
- IA-17: `granger` order selection passes `RSS/(N-k)` to `_info_criterion`, which documents the ML `RSS/N`, and scores each order on a different sample (`jnwb/connectivity.py:1195-1205`, `359-371`). Check: an order-recovery test on a known VAR(p) scored on one trimmed sample.
- IA-18: `classify_response_significance` turns an effect size (mean difference over per-trial SD) into a normal p-value that does not fall with trial count (`jnwb/spiking.py:149-158`, `212-219`). Check: decide effect size or test; test p against trial count at a fixed effect.
- IA-19: two-class `bilinear` `predict_proba` is sigmoid(2 D) and overconfident (held-out bin 0.8 to 0.9 predicts 0.856, observes 0.582) though documented as calibrated; experimental and outside `__all__` (`jnwb/bilinear.py:31`, `134-138`). Check: one model for two classes and a calibration test.
- IA-20: `np.unique(axis=0)` in `_codes` is 97% of `transfer_entropy` runtime; a mixed-radix integer key gives identical codes 71 times faster (`jnwb/connectivity.py:2023-2029`). Check: frozen-output diff on fixed seeds, with a radix-overflow guard.
- IA-21: the `xflip` partition search is a pure-Python triple loop per surrogate; vectorising the inner loop gives identical cuts 10 to 45 times faster (`jnwb/laminar.py:1172-1191`). Check: frozen-cut diff, then timing.
- IA-22: `cluster_permutation_test` sums each cluster with a full-map mask, O(K M) per permutation; `ndimage.sum_labels` gives identical sums (31 ms against 0.8 ms at 1582 clusters) (`jnwb/statistics.py:1900-1912`). Check: diff `max_null_stats` against a frozen run.
- IA-23: `bootstrap_ci` resamples in a Python loop (11 times slower than vectorised at n 200), and `UnitAnalyzer.psth` calls it every time (`jnwb/statistics.py:1177-1181`). Check: vectorise; the random stream changes, so values move under a fixed seed and need a changelog entry or a ruling.
- IA-24: `enrich_units_dataframe` makes three row-wise `.apply` passes (4000 units by 1536 electrodes, 4.2 s) (`jnwb/addressing.py:430-449`). Check: a vectorised lookup against a frozen output.
- IA-25: `raster_psth` masks the whole train per onset (0.43 s against 0.14 s with `searchsorted`), and a list `st` fails with an unrelated `TypeError` (`jnwb/viz.py:155-157`). Check: `searchsorted` and `np.asarray(st)`.
- IA-26: conditional Granger (`granger(Z=...)`) never runs in the suite (`jnwb/connectivity.py:1133-1143`). Check: a common driver passed as `Z` removes a spurious x to y.
- IA-27: exported callables at 0% coverage: `TFRAnalyzer.by_layer`, `UnitAnalyzer.raster`, `DirectedResult.to_dict/ok/summary`, `jnwb.vis.plot_granger_spectra`, `plot_rsm_heatmap`, `paths.resolve_nwb_path/sha256_file/require`; `nam.train_nam` at 3%. Check: one value-pinning test each, or a declared exclusion.
- IA-28: tests that assert too little: `bilinear` checks only a length, the `jrsa` multi-lag test checks a shape over a fixture that evaluates to NaN, and no test feeds `verify_roundtrip` a corrupted cast. Check: value-pinning tests for IA-04, IA-07 and IA-19.
- IA-29: unbacked claims and project leftovers ship in the wheel: `nam` cites a missing script and receipts and calls `torch.manual_seed`, which resets the global torch stream; `REWARD_WINDOW_MS` is a task constant no function uses; `artifact_repair` cites two missing scripts; `layer_masks_path` hardcodes project output folders. Check: extend P-296's sweep to these; use a local `torch.Generator`.
- IA-30: with one correlated block beside an uncorrelated rest, `xflip` places the boundary at the midpoint rather than the true edge; the fit is rejected, so it is a missed boundary rather than a false one (`jnwb/laminar.py:1138-1167`). Check: a boundary-recovery test for one block and background.
- IB-03: `docs/10_operation_specifications.md:98` gives `vflip_from_lfp` as `compute_psd(lfp, fs) -> vflip(psd, freqs)`; on channels-by-time input that runs over channels and `vflip` raises; the code uses the time axis. Check: write `axis=-1` into the composition and test it equals `vflip_from_lfp`.
- IB-04: `README.md:79-80`, `docs/errors.md:137-139`, `226` and `docs/common_mistakes.md:290-291` say `event_onsets` warns when a table has no `codes` column; it does not, and its docstring says so; only `events` warns. Check: correct the pages.
- IB-05: `docs/07:21` says a non-`Generator` `rng` raises `TypeError`, but `StatisticalAnalysis` accepts and coerces an int or `None`. Check: state the accepted types per surface.
- IB-06: `docs/10:18` says every stochastic function accepts an int, a `Generator` or `None`; `shuffle_pvalue_paired` and `shuffle_pvalue_unpaired` fail on an int or `None` with `AttributeError`, and `permute_labels` refuses them. Check: one accepted set, enforced, and the page to match.
- IB-07: `docs/10:48-49` says the structured returns, `JRSAResult` among them, implement `.to_dict()` and `__getitem__`; `JRSAResult` has neither. Check: add them or exclude it on the page.
- IB-08: `docs/10:33` says seeds are spawned per worker with `SeedSequence(seed).spawn(n_jobs)`; the code spawns one seed per iteration, which is what makes results independent of `n_jobs`. Check: correct the page.
- IB-09: `docs/09:116-118` says `compare_session_quality` takes the frame `diagnostics.compare_sessions()` returns; no such function exists, and the columns it reads are unnamed. Check: name the columns and drop the reference.
- IB-10: `docs/errors.md:94-97` gives two layout bases; an electrode-less `TimeSeries` reports a third, `schema` (`jnwb/nwb_inspect.py:251-252`). Check: list all three.
- IB-11: `docs/08:186` prints `network["matrix"]` as the net matrix; it is the directed matrix, not antisymmetric. Check: relabel.
- IB-12: `docs/10:100` gives `testing.synth` an output type of `np.ndarray`; its builders return a receipt, a 3-tuple and a pair. Check: correct the row.
- IB-14 (blocker candidate, weak): `skills/jnwb-landmark-viz/SKILL.md:60,71` pass millimetre depths, and `jnwb/vis/laminar.py:101,301,423` infer the unit from the maximum, so 0 to 1.55 mm is labelled "Relative Depth (0=Pia, 1=WM)". Check: a `depth_unit=` parameter with no default, or refusal of ambiguous ranges.
- IB-15: `docs/api.md` drops every keyword-only `*` marker (34 exports have keyword-only parameters, no row shows one), so it shows calls that raise (`scripts/generate_api_md.py:158-181`). Check: render `inspect.signature` and compare parameter kinds in gate 18.
- IB-16: `docs/03:103` says `nan_policy="omit"` propagates NaN across the affected RDM pairs; one empty condition makes the whole result NaN, and one NaN sample moves the value 0.343 to 0.425. Check: correct the prose or omit pairwise; test one empty condition.
- IB-17: `skills/jnwb-fact-action` is a contributor-process skill that ships (sdist, `SKILLS_URL`, `docs/agents.md`) with implicit invocation, internal ids and a trigger claiming all multi-step work, while the router scopes it to repository tasks. Check: a ruling on whether it ships; meanwhile scope its trigger.
- IB-18: gate 14 scans `docs/` and `README.md` for process terms but not the shipped `skills/`, and checks only identifiers in `jnwb/`, where `jnwb/__init__.py:22` names a harness gate. Check: add `skills/` to gate 14, with a named exemption if IB-17 rules it stays.
- IB-19: `skills/jnwb-landmark-viz/SKILL.md:35` mandates a chance line at 0.5 and `jnwb/vis/state_space.py:28` defaults `chance_level=0.5`, against the population skill's rule for unbalanced classes. Check: point to `majority_baseline` or make `chance_level` required.
- IB-20: `skills/jnwb-statistics/SKILL.md:3-4` and its `agents/openai.yaml` say "family-wise FDR", conflating FWER with Benjamini-Hochberg. Check: "FDR (Benjamini-Hochberg)".
- IB-21: the CSD and curvature row of `skills/jnwb-lfp-spectral/SKILL.md:28` omits that the output has two fewer channels, so output row k is input channel k+1 (`AGENTS.md` invariant 4). Check: state the shape and offset; a routing test on it.
- IB-22: the router `skills/jnwb/SKILL.md` never routes to `jnwb-landmark-viz`. Check: a test that every skill directory is reachable from the router.
- IB-23: `docs/04:164` calls a value near -2 the aperiodic exponent while `aperiodic_fit` on the same page returns +2; the sign note lives only in the skill. Check: one sign convention or a named field.
- IB-24: the `classify_layer_from_depth` docstring summary says it classifies a cortical layer, against `docs/02:89` ("a cut on depth, not a cortical layer"). Check: fix the docstring and regenerate `docs/api.md`.
- IB-25: `AGENTS.md` section 11 and `artifacts/problem_stack.md:10` write the cycle labels as literals `required-0.2.6` and `deferred-0.2.7`, which STEP 0a derives from the version, so a 0.2.7 triage following the text writes the wrong label. Check: write `required-<cycle>` and `deferred-<next>`, with a test that no standing rule names a literal cycle.
- IB-26: the module docstring of `scripts/release_gate.py` omits STEPs 0a, 2a, 2b and 8, and `CONTRIBUTING.md:88-96` omits the readiness step. Check: extend `tests/test_module_docstrings_match_their_code.py` to the release gate.
- IB-27: `artifacts/agents.md` sends readers to `artifacts/agents/` and `jnwb-developer`, which gate 14 lists as internal vocabulary banned from public docs. Check: a ruling on whether the roles are public, then gate the page or drop the terms.
- IB-28: `docs/documentation_form.md`, an internal contributor contract, is in the user navigation, and `docs/index.md:52` and `docs/install.md:26` say "gate-enforced" and "release gate". Check: move it to `CONTRIBUTING.md` or out of the navigation.
- IB-29: the six CI test legs run the suite serially (`.github/workflows/workflow.yml:67`), 558 to 745 s each, while the wheel leg uses `-n auto` at 385 s. Check: `-n auto` on the matrix after P-254's kaleido isolation.
- IB-30: the live harness runs twice in the suite (`tests/test_every_gate_runs.py:55`, `tests/test_harness_adversarial_gates.py:307`, about 5 s each on six legs) and again in the build job. Check: keep one live-tree run.
- IB-31: the two slowest tests take 25.6 s and 22.4 s (`test_rng_convention_matches_the_signatures.py[cross_modal_comparison]`, `test_api_md_is_interpreter_independent.py`), about 20% of the parallel wall time. Check: shrink the entropy test's input.
- IB-32: `scripts/measure_agents_md_duplication.py:37-52` reads gitignored `.claude/agents/*.md`, present on one machine, and skips `docs/agents.md`, where the skill table already differs from `AGENTS.md` section 7 in three rows. Check: tracked files only, including `docs/agents.md`.
- IB-33: in four of ten skills the `agents/openai.yaml` description differs from the SKILL.md description; the test checks only that the key exists. Check: byte equality of the two.
- IB-34: the router calls itself a "memory bank" and sends readers to `AGENTS.md` for agent pitfalls that live in `docs/common_mistakes.md`; `jnwb-landmark-viz` lacks the routing, invariants and doc-link sections of the other domain skills, and its layout constants disagree with `jnwb/vis/canvas.py:226-267`. Check: the shared template of 07-04's first step.
- IB-35: `skills/jnwb-connectivity/SKILL.md:50` cites `docs/common_mistakes.md` section 7 for a narrow-band PSI (`net=-2.1e-05`), while that section reports `nan` for the same case at another signal length. Check: one receipt with a stated length, cited by both.
- IB-36: `CONTRIBUTING.md:111,205,347` states the docs-and-skills lockstep rule three times. Check: keep one.
- IB-37: P-63's count is stale (25 of 160 exports are named in no skill, not 30), and a git-less export of the tag, which is what GitHub archives and Zenodo store, fails 30 tests and errors on 7, every one a git call. Check: correct P-63; skip git-dependent tests when there is no `.git`.
- IB-38: `AGENTS.md` is about 8k tokens loaded into every session in this repository; section 10's recipes repeat what `docs/` and the skills carry, and section 11's history paragraphs repeat the rulings they cite; 14 tests pin its text, `tests/test_agents_md_recipes.py` among them. Check: move the recipes to a tested docs page and the history to `artifacts/rulings/`, leaving pointers, and move the tests with them.

### 07-04 The planned 0.2.7 sequence

Release: deferred-0.2.7.
Role: jnwb-developer. Skill: per skill. Blocked by: none.
Writes: `artifacts/todo_stack.md`.
The plan in `artifacts/planned_post_0.2.6.md` is authorized input to this cycle (ruled 2026-09-22). Reproduce
each of its steps against this tree and turn each into its own item here, with fields, before any
of it is implemented.
Accept: every step of the plan is an item of this stack or is recorded as already done.

## Out of 0.2.7 scope

Carried from 0.2.6. Each needs its own authorization.

- Raw-data-to-NWB conversion.
- An authorization or permission subsystem.
- Benchmark execution; the design is retained and marked unrun (06-33).
- A capability-by-capability matrix over the whole public surface.
- Repository minimization: dead tests, hand-transcribed examples, root and documentation cleanup.
- Dataset-specific package code, and new estimators that only improve a demonstration.
- The 36 unverified review findings, except where an item reaches one.

## Acceptance

`AGENTS.md` §11, the same three conditions as 0.2.6, measured against `artifacts/goal.md`.
