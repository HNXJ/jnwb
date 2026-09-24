# 0.2.6

The remaining work of the 0.2.6 cycle, reorganized 2026-09-22 so that executing it in the order
below reaches the release. Items are deleted when done; git, `CHANGELOG.md` and the receipts hold
history. The previous cycle's record is `artifacts/archive/0.2.5/todo_stack_0.2.5.md`.

0.2.6 is a coherence, reachability and evidence release. It is measured against
`artifacts/goal.md` and opens under the three conditions of `AGENTS.md` §11. Deferred work and the
0.2.7 sequence are in `artifacts/planned_post_0.2.6.md`, and findings deferred from the problem
stack are 07-01. Rulings are in `artifacts/rulings/`.

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

Items in one wave have disjoint `Writes`, resolved by path and closed under generation; run them
in any order, at most two agents at a time unless Hamm raises the cap. Close each wave with the
barrier above.

| Wave | Items |
|---|---|
| W0 |  |
| W1 |  |
| W2 |  |
| W3 |  |
| W4 |  |
| W5 |  |
| W6 |  |
| W7 |  |
| W8 |  |
| W9 |  |
| W10 |  |
| Rolling | Verification ran through `c52a9649`; a repair landed later is verified by a verifier that did not make it before 06-60 runs |
| Closure | 06-147, then 06-38, 06-39, 06-60, 06-130, 06-40 |

06-17 dispatches one packet per finding into whichever wave its declared paths fit, and all of its
packets finish before 06-34.

## W0. Integration and verification

## W1. Freeze, sweeps and harness

## W2. API repairs

## W3. Statistics surface, diagrams and the open-data example

## W4. Maintained figures, skill routing and references

## W5. Figures, execution switch and decline

## W6. Orders and empirical labelling

## W7. Contracts

## W8. Vocabulary and cost

## W9-W10. Documentation form

## Any wave. Confirmed findings

## Rolling verification

### 06-147 Repair the blockers the critic found at `8e90a4ad`

Release: required-0.2.6.
Role: actor. Skill: jnwb-statistics. Blocked by: none. Writes: `jnwb/statistics.py`, `jnwb/jrsa.py`, `jnwb/analyzers.py`, `scripts/release_gate.py`, `scripts/harness_gate.py`, `tests/test_statistics*.py`, `tests/test_jrsa*.py`, `tests/test_release_requires_an_empty_problem_stack.py`, `CHANGELOG.md`, `CONTRIBUTING.md`, `skills/jnwb-statistics/SKILL.md`, `skills/jnwb-population/SKILL.md`.
`shuffle_r2_ci` and `compare_groups` read a constant input as spread when the constant is not exactly representable (`np.std` is about 1e-17), so they return p = 1 or an effect size near 1e16 where the CHANGELOG promises NaN. `jrsa` without permutations accepts a misspelt `alternative` and ignores a one-sided one; ruled 2026-09-23 to apply it parametrically. STEP 0a can pass on no committed tree; ruled 2026-09-23 to accept a receipt whose commit differs from HEAD only by the receipt and the todo stack, with 06-130 and 06-40 as the release step.
Accept: each repair has a discriminator that fails without it, and the full suite passes.

## Closure

### 06-38 Verify the candidate from TestPyPI

Release: required-0.2.6.
Role: verifier. Skill: jnwb-nwb-data. Blocked by: none. Writes: none.
The TestPyPI 0.2.6 built by CI run 36012625010 at `8e90a4ad` passed: hashes equal CI's artifact, the wheel's `jnwb/` equals git byte for byte, clean installs on 3.12.0, 3.13.15 and 3.14.3 open and analyse the DANDI 000253 excerpt with the sampling rate derived from the file, the suite against the installed copy passes, and the strict docs build reads 0.2.6. Ruled 2026-09-23: TestPyPI cannot take 0.2.6 again, so what remains is the same checks on a wheel built by the CI build job from the final commit, and the check from production PyPI after 06-40 publishes.
Ruled 2026-09-22 (R-3). The candidate is published to TestPyPI (authorized as part of 06-40's
sequence); in a clean environment install it from TestPyPI, open an NWB file, analyse, verify.
After production publication the same check runs from PyPI.

### 06-39 Independent critic

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: 06-147. Writes: none.
A reviewer that implemented none of the repairs, over the acceptance set, the unresolved unknowns,
the mutation evidence, the public claims and the release artifacts.
The pass at `8e90a4ad` held every other acceptance row, upheld every 07-01 deferral it attacked, reproduced every other Changed, Deprecated and numeric Fixed entry, and killed 13 of 14 sampled mutants; it found 06-147's four blockers. What remains is an independent pass over 06-147's repairs and the wording corrections that came with them.

### 06-60 No blocker remains, confirmed by a pass that finds no new one

Release: required-0.2.6.
Role: critic. Skill: none. Blocked by: 06-39.
Writes: `artifacts/blocker_fixpoint_receipt.md`.
Condition 3 of `AGENTS.md` §11. One independent pass over the documentation, the code and both
stacks applying the blocker predicate. A new blocker becomes a `required-0.2.6` item and re-opens
the owning wave; a new non-blocking observation becomes a `deferred-0.2.7` entry and does not.
P-37: the pass also hunts the root pattern, a proxy mistaken for the invariant it stands for;
fifteen instances are enumerated in the P-37 row of the problem stack at `f140e20e`, and the
pattern closes when one full pass adds none.
Accept: the receipt names the commit it ran against and reports zero new release-blocking
problems; `scripts/release_gate.py` STEP 0a accepts it when the only files changed since that commit are the receipt and this stack.
Stop: a new blocker needs a human ruling; it is not reclassified to close the cycle.

### 06-130 Reconcile `main` with `dev` before the release pull request

Release: release-step-0.2.6.
Role: human. Skill: none. Blocked by: 06-60. AUTONOMY: none.
Writes: none.
P-180. `origin/main` is `9d738211`, a second copy of the `jnwb.vis` commit on top of the 0.2.5
release merge, while `dev` carries the same content as `178b1777`. A merge of `dev` into `main`
treats `packages/jnwb-vis/` as added on `main` and unchanged on `dev`, so the duplicate that `dev`
deleted comes back.
Ruled 2026-09-22: revert on `main` first. `9d738211` is reverted on `main` in its own pull
request, which Hamm authorizes and merges; the verifier then confirms the release merge tree
equals `dev`.
Ruled 2026-09-23: opened ahead of the closure order as HNXJ/jnwb#20 and merged at `5e8ff14d`;
`main`'s tree equals `efdba807`, and `git merge-tree --write-tree origin/main origin/dev` at
`679e70a9` equals `dev`. What remains here is the same check on the release pull request.
P-270: `README.md` links `blob/main/artifacts/agents.md`, which `main` lacks until the release
merge; confirm the link resolves once the merge lands.
Accept: `git diff dev <merge>` is empty on the release pull request, and the README's agent link resolves.

### 06-40 Release

Release: release-step-0.2.6.
Role: human. Skill: none. Blocked by: 06-130. AUTONOMY: none.
Writes: `jnwb/__init__.py`, `CHANGELOG.md`, `README.md`.
dev green; pull request and `main` green; TestPyPI candidate (06-38); tag validates without
publishing; GitHub Release; production PyPI; verification from PyPI in a clean environment.

## 0.2.7

### 07-01 Findings carried from 0.2.6

Release: deferred-0.2.7.
Role: jnwb-developer. Skill: per finding. Blocked by: none.
Writes: `jnwb/**/*.py`, `scripts/*.py`, `tests/**/*.py`, `docs/**/*.md`, `skills/*/SKILL.md`, `examples/**/*.py`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`.
Each finding below was deferred under `AGENTS.md` section 11 during 0.2.6. A packet takes one
finding and narrows the write set to its paths; a finding shown to meet the blocker predicate
leaves this item as a `required-0.2.6` item.

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

## Reported and not admitted

Recorded so that nothing reported disappears by not being chosen.

- `dist/` holds only 0.1.1, 0.1.3 and 0.2.4 artifacts; 06-38 builds fresh.
- The ninth unreadable consumer file fails at `root/units` with `Columns must be the same
  length`, separately from the eight that fail on device attributes.

## Out of 0.2.6 scope

Frozen with the acceptance set. Each needs its own authorization.

- Raw-data-to-NWB conversion.
- An authorization or permission subsystem.
- Benchmark execution; the design is retained and marked unrun (06-33).
- A capability-by-capability matrix over the whole public surface.
- Repository minimization: dead tests, hand-transcribed examples, root and documentation cleanup.
- Dataset-specific package code, and new estimators that only improve a demonstration.
- The 36 unverified review findings, except where an item reaches one.

## Acceptance

Frozen 2026-09-23 (06-05, closed), each line re-established against the live tree; the non-goals under "Out of 0.2.6 scope" are frozen with it. Each line names what establishes it.

| Line | Established by |
|---|---|
| no known material defect under the 0.2.6 acceptance set | 06-34, 06-39 |
| one canonical scientific model, published and reachable | `docs/architecture.md` (in the navigation since `d3d17871`), `tests/test_architecture_page_reachability.py`, the four diagrams on that page |
| every public claim reproduced against the implementation that answers it | 06-17 (now closed), 06-24, 06-136 |
| skills route, decline, and are tested against live behaviour | 06-24, 06-25 (now closed), `tests/test_skill_decline_behaviour.py` |
| cross-surface and compositional audit complete over the declared high-risk set | `artifacts/evidence/0.2.6/composition_subset_0.2.6.md` and its proposal, every magnitude naming a committed test and seed (re-stamped 2026-09-23) |
| documentation assets render and are regenerable | `tests/test_generated_figures_are_maintained.py`, 06-36 |
| one real NWB end-to-end example with provenance | `examples/tutorials/09_open_data.py` (verified at `a9993322`; P-199 and P-200 carry its gaps), `tests/test_synthetic_figures_are_labelled.py` |
| published artifact independently verified, from TestPyPI before publication and from PyPI after | 06-37, 06-38, 06-40 |
| documentation low-verbosity and consistently formed, against a declared contract | 06-51 (now closed), 06-53 (now closed), `scripts/docs_form_gate.py`, `docs/glossary.md`, `tests/test_figure_form.py` |
| one precision switch and one execution switch; CPU, parallel CPU and CUDA exercised here | 06-56 (now closed), 06-59 (now closed), `scripts/computational_contract_gate.py` |
| every declared interpreter qualified by CI on Ubuntu and Windows, and every surface declaring the same set | gate 8, CI on `dev`, 06-35 |
| a read invents no metadata, and a named waiver is recorded as it happened | `tests/test_nwb_read_tolerance_and_visibility.py`, `tests/test_public_api_reachability.py` |
| `jnwb.vis` is an optional extra and `import jnwb` works without it | `tests/test_optional_vis_extra.py`, 06-37 |
| suite wall time and the slowest tests measured before release | `scripts/release_gate.py` STEP 1 |
| no release-blocking problem and no required item remaining, confirmed by a blocker-focused pass | 06-60, `scripts/release_gate.py` STEP 0a |

The form matches 0.2.5's closure: no known material defect under a stated acceptance set, not a
claim of exhaustive correctness. Deliberately absent: a claim that the JAX Metal backend works; it
is implemented and declared unverified.
