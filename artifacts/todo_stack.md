# 0.2.0



# 0.2.1


# 0.2.2


# 0.2.3


# 0.2.4

- 0.2.4-01: Empty the executable todo stack (zero unresolved package tasks unless explicit human decision blocks release).
- 0.2.4-02: Documentation minimization pass: Audit and eliminate duplicated explanations, stale version statements, excessive prose, internal codes, unsupported claims, drifting screenshots, and non-executing examples; verify small, accessible docs without internal engineering manual overhead.
- 0.2.4-03: Executable tutorial verification against installed wheel: Run all 8 tutorials (01 basics through 08 end-to-end) in a clean environment against the installed wheel without repo-relative imports; verify synthetic expected truth is known by construction and labeled synthetic.
- 0.2.4-04: Independent numerical audit of every high-risk primitive and composition for sign, scale, units, axes, complex preservation, aggregation order, failure, boundary, and determinism.
- 0.2.4-05: Randomness and inference audit verifying caller control of RNG, no global RNG mutation, no salted hash seeds, verified permutation exchangeability, and CV isolation.
- 0.2.4-06: NWB/addressing audit with synthetic fixtures covering missing tables/columns, alternate layouts, identifiers, malformed labels, units, geometry, ambiguity, and lazy access (no missing metadata becomes valid-looking science).
- 0.2.4-07: API audit verifying implementation == exports == signatures == typing == docstrings == reference docs == examples == skills with zero leaked deprecated symbols.
- 0.2.4-08: Boundary audit scanning code, tests, docs, examples, skills, agents, defaults, and artifacts for zero downstream semantic leakage.
- 0.2.4-09: Skills and agents adversarial acceptance testing against stale APIs, ambiguous units, downstream requests, invalid assumptions, and evidence conflicts.
- 0.2.4-10: Dependency matrix audit verifying base install and declared optional dependency combinations, plus import-time optional dependency behavior.
- 0.2.4-11: Supported Python and OS matrix audit derived from live metadata/CI; every required remote CI job must PASS.
- 0.2.4-12: Strict documentation build audit with all examples/API references resolved, zero stale names, zero contradictory definitions, zero unsupported claims.
- 0.2.4-13: Distribution audit building sdist and wheel from clean checkout, inspecting manifests, installing into clean environments, verifying site-packages resolution, and running representative numerical workflows against installed wheel.
- 0.2.4-14: Reproducibility audit from fresh checkout -> install -> tests -> docs -> calibration -> representative workflows with zero undocumented local state.
- 0.2.4-15: CPU/CUDA/parallelism independent verification: Confirm performance decisions and numerical parity across CPU and GPU backends on clean test systems.
- 0.2.4-16: Independent final critic pass attempting to falsify numerical correctness, boundary, API consistency, docs, skills, agents, packaging, CI, and release state.
- 0.2.4-17: Release seal verifying acceptance predicate Q_release = Q_science & Q_API & Q_performance & Q_CPU/GPU & Q_NWB & Q_docs & Q_tutorials & Q_skills/agents & Q_distribution, changelog/version bump, clean tree, commit, push dev, remote CI PASS, merge/release per policy, tag, build, install, smoke-test, and reconcile.

## 0.2.4 evidence reconciliation

Status at `5c2bd7f2`+ (this commit). No commit in repository history cites a `0.2.4-NN` code, so
no item below was previously sealed; several are nonetheless satisfied by mechanical gates built
under other codes. CLOSED means a gate or receipt demonstrates the item's own predicate. PARTIAL
names what is missing. Nothing here is marked from inference.

| Item | Status | Evidence / named gap |
| --- | --- | --- |
| 01 executable stack empty | CLOSED | every numbered 0.2.4 item is closed against evidence and nothing executable remains under the 0.2.4 heading. What the file still carries is a record (what was repaired, what was triaged and deliberately not repaired, what the handout recovered) plus a 0.2.5 section and the pre-1.0 list. Checked mechanically on 2026-09-16: every file and test module this stack cites resolves on disk |
| 02 documentation minimization | CLOSED | mechanical half gated (Gate 9 documented-API parity, Gate 10 derived version, strict MkDocs 0 warnings, `test_docs_links`, `test_docs_smoke`, `test_readme_smoke`). Editorial pass done: no internal tracker code appears in any user-facing page (the Developer Guide's `0.2.0-07` reference and its stale "planned 0.2.1 through 0.2.3" framing are rewritten), and a paragraph-level scan across `docs/` finds no explanation duplicated between pages |
| 03 tutorials vs installed wheel | CLOSED | all 8 run on the clean-venv interpreter with `PYTHONPATH` stripped and CWD outside the checkout, in CI and in release gate STEP 8; `TestInstalledArtifactVerification` fails if either is removed or reordered before install |
| 04 numerical audit of primitives | CLOSED | 0.2.3-REV-01..11 repaired eleven externally-found numerical defects, with `test_independent_audit_semantics` / `test_audit_reproducers` as regressions. The 0.2.4 pass over `wpli`, `imaginary_coherency`, `zflip`, `rdm`, `rdm_similarity` and `jrsa(metric='rsa')` found and repaired fabricated zeros, amplitude-unit dependence, a CUDA branch that never ran, zFLIP accepting untested or partly unidentifiable delays, and undefined RDM distances set to 0 (see CHANGELOG); regressions in `test_spectral_nonfabrication`, `test_zflip_audit`, `test_rsa_oracle`. A degenerate-input and amplitude-unit sweep over the public numeric API (empty, singleton, NaN/Inf, constant, reversed windows, scale 1e-3..1e-20, CPU vs CUDA) repaired 17 more defects: zeros or p = 1/(n+1) returned for undefined results in spectral summaries, spike-window rates, shuffle p-values, PSTH, `laplacian_reference`, `network_topology`, `xflip`; unit-dependent `jrsa` CKA/RV/dCor/cosine, `vflip` and outlier detection; `jrsa` CUDA pearson/spearman disagreeing with CPU; `harmonic_ratio` double-counting (see CHANGELOG, `test_adversarial_inputs`). Not repaired, model choices: `jrsa(metric='hsic')` uses a fixed RBF bandwidth in data units, so it is unit-dependent by definition; PSTH SEM for N=1 is deferred below. zFLIP's absolute sign convention, its phase-slope formula against a cross-spectral oracle, and its N // 2 segmentation rule are pinned in `test_zflip_audit`; each RSA similarity metric is pinned to a SciPy oracle and the twelve `rdm` metrics to the wrapper's own invariants in `test_rsa_oracle`. vFLIP's centring bias and its uncontrolled, grid-dependent acceptance are repaired: min-max relative power per frequency with each band depth profile rescaled before differencing, bin-count normalization of the score, and a threshold of 3.75 recalibrated over crossover location, channel count, pitch, grid density, orientation, missing contacts and SNR (AUC 1.000, FPR 0.000, TPR 0.999). Discriminators in `TestVFlipNormalizationRepair`, 6 of which fail the pre-repair estimator |
| 05 randomness and inference | CLOSED | no global RNG mutation anywhere in `jnwb/` (no `np.random.seed`, no `random.seed`, no `PYTHONHASHSEED` dependence); `permute_labels` rejects non-`Generator` rng, is deterministic given a seed, preserves per-group label counts, and emits a draw manifest with sequential seeds and digests. CV isolation is now asserted, not just exercised: `TestCrossValidationIsolation` decodes labels drawn independently of 200 features on 60 trials -- the regime where a scaler, selector or hyperparameter fitted outside the outer fold would show -- and gets 0.535 mean accuracy over 10 seeds, while the same features decode at 1.000 with informative labels and fall back to chance when those labels are shuffled . Reopened and re-closed during the release pass: `jrsa` spelled its seed `random_state` while every other seeded entry point in the package spells it `seed`, and forwarded unknown keywords to metrics that swallow `**kwargs`, so `jrsa(..., seed=0)` was accepted in silence and left the permutation test entropy-seeded -- four repeated calls on one dataset gave p = 0.2736, 0.3333, 0.2637, 0.2935. `seed` is now an alias for `random_state` and an unknown keyword is a TypeError naming the metric's accepted options |
| 06 NWB/addressing audit | CLOSED | `test_nwb_synthetic_fixtures`, `test_hdmf_nwb_read_boundary`, `test_addressing`, `test_metadata`, `test_nwb_inspect` cover missing tables/columns, alternate layouts and lazy access; the electrode-region repair added out-of-range enforcement. The units/geometry/ambiguity sweep is now `TestAmbiguousUnitProbes`: depth units are never inferred from magnitude, an undeclared or unsupported unit refuses to classify instead of guessing a layer, accepted spellings agree, an explicit argument deterministically overrides a conflicting table column, and `probe_geometry` takes the declared unit literally and rejects an unsupported one |
| 07 API audit | CLOSED | exports == documented API == generator output is gated (Gate 9 + `generate_api_md --check` + `test_api_surface`), and skills reference only existing symbols. Signature and annotation parity is mechanical after all: `docs/api.md` is generated from runtime introspection and carries the full annotated signature, so any change to a parameter, default or annotation fails the gate -- observed when `min_support_score` moved from 6.0 to 3.75 (API_MD_DRIFT). The first docstring line is likewise generated and compared. Only the docstring body is outside mechanical comparison |
| 08 boundary audit | CLOSED | Gate 6 scans `jnwb/`, `docs/` recursively, `examples/` recursively (`*.py`, `*.ipynb`), `skills/` and the root docs, with `TestGate6RecursiveCoverage` planting tokens on 8 surfaces; plus the no-project-identifiers gate and `test_jnwb_frozen_boundary` |
| 09 skills/agents adversarial | CLOSED | `test_skills_validation` covers frontmatter, routing-parameter/runtime agreement, symbol and docs-path existence, no hardcoded counts, no removed toolchain, no downstream leakage, and representative routing probes. The missing adversarial legs are added: `TestAmbiguousUnitProbes` pins that a depth unit is never inferred from magnitude (1.2 um is Superficial, 1.2 mm is Deep), that an undeclared or unsupported unit refuses to classify rather than guessing, that accepted spellings agree, that an explicit argument deterministically overrides a conflicting table column, and that `probe_geometry` takes the declared unit literally and rejects an unsupported one; `TestEvidenceConflictProbes` pins that no shipped code path can rewrite the human-authorized fact stack and that the receipts-not-consensus rule still stands |
| 10 dependency matrix | CLOSED | base wheel installs and imports with no extras in the CI clean venv, `pip check` clean; lazy-import tests prove optional subsystems are not eager and degrade with a named error. `TestOptionalExtras` adds what was missing without pretending to a matrix: every requirement string parses as PEP 508, `all` is asserted to cover exactly the other five extras, and importing `jnwb` is shown to pull in none of torch, cupy, jax, mcp or mkdocs. Installing all 32 combinations is deliberately not attempted -- `gpu` cannot resolve on a runner without CUDA -- and torch/gpu are exercised on real hardware in `artifacts/benchmarks/cuda_parity_0.2.4.md` |
| 11 Python/OS matrix | CLOSED | run 34921221203: 3.12 and 3.14 on ubuntu-latest and windows-latest all PASS; floor consistency gated |
| 12 strict documentation build | CLOSED | `docs_build.py` strict, 0 warnings, locally and in CI; versions derive from `jnwb.__version__` |
| 13 distribution audit | CLOSED | build -> manifest scan -> `twine check` -> fresh venv -> wheel + transitive install -> `pip check` -> import from site-packages outside the checkout -> numerical workflows -> tutorials |
| 14 reproducibility | CLOSED | CI performs checkout -> install -> tests -> docs -> build -> install -> smoke -> tutorials from a clean runner each run. Calibration regeneration is not run in CI, but calibration staleness is caught there: `test_vflip_calibration_receipt` fails when `vflip` changes without `scripts/calibrate_vflip.py` being rerun, and `test_xflip_calibration` recomputes xFLIP's operating characteristics from the shipped estimator |
| 15 CPU/CUDA parity | CLOSED | against the RC-scoped criterion (structural/fallback tests; representative high-risk paths on one real CUDA system; parity within declared tolerances; CI verifies CPU/fallback). 9 of 13 `resolve_device` call sites executed on an RTX A4000 with no fallback warning, parity 0 to 3.6e-04; `rdm` has no GPU implementation and warns; the 3 uncovered are session-level wrappers over the same resolver, retaining structural coverage. The earlier 7-of-10 closure missed that `wpli(device='cuda')` never reached the GPU (repaired, receipt corrected). Receipt: `artifacts/benchmarks/cuda_parity_0.2.4.md` |
| 16 final critic pass | CLOSED | an independent critic was run against the repaired tree without being told the package was correct. It returned ten major findings and about fifteen minor ones. Every major finding was reproduced before any repair, and each was CONFIRMED by measurement: `jrsa` permuting the feature axis so six whole-representation metrics reported p = 1.0000 on any data; `phase_locking_index` folding the recording modulo 6.2832 s so a unit with true resultant length 0.995 reported pli 0.31 over 60 s; `cross_modal_comparison` calling 99.5% of independent runs significant and silently replacing an asymmetric lag range with a different window; `_adf_pvalue` certifying 46-48% of pure random walks as stationary; `transfer_entropy` returning 0.0000 bits with `ok_for_interpretation=True` on a genuine lag-1 coupling; `permute_labels(within_group)` returning 1000 of 1000 identical draws for nested designs; `repair_lfp_trials` dropping the single-trial amplitude correlation from 0.9996 to 0.4607; `compute_response_metrics` scoring a response on a homogeneous unit and returning 0.0 for a silent baseline; the residual vFLIP centre-shrinkage; and `_rv` returning 1.0000 for independent representations. All ten are repaired, each with tests that fail the previous code. Of the minor findings, four reproduced and are repaired (odd-`n_fft` multitaper doubling, the unit-dependent `imaginary_coherency` clip, `xflip` accepting an unrun surrogate test, the `confirmatory_compare` double-correction advice); the RSA-family silent-truncation finding is UNSUPPORTED -- the truncations are unreachable from the public entry point, which rejects mismatched shapes, though its error message was unclear and is now a contract error. The `_r2` and `aperiodic_fit` zero-return findings are UNSUPPORTED as defects: a constant score genuinely has no explanatory power, and a perfectly flat log-PSD is not reachable from real input. Three tests were found to be encoding defective historical behaviour and retargeted: `test_perfectly_locked_spikes_give_high_pli_and_low_pvalue` (fixture uniform in phase, not locked), `test_zero_surrogates_returns_nan_p_value` (asserted acceptance without a test), and `test_manifest_records_sample_and_group_counts` (nested fixture with a point-mass null). See CHANGELOG 0.2.4 Fixed |
| 17 release seal | CLOSED | 0.2.4 released 2026-09-16. Candidate `d09a4c52` on `dev`: full suite 1473 passed / 1 skipped, 13/13 harness gates, release gate VERIFIED through all 8 steps (151/151 `__all__` symbols resolved from the installed wheel outside the repository, 8/8 tutorials against the installed artifact), and remote CI green on 3.12 and 3.14 x ubuntu and windows. Merged to `main` as `9cfbe142` via PR #14, whose tree SHA `37a6cb08` is identical to the qualified `dev` tree. Tagged `v0.2.4` at `9cfbe142`; GitHub Release `jnwb 0.2.4` (non-draft, non-prerelease) triggered run 35062264236, whose Publish to PyPI job succeeded via Trusted Publishing. PyPI now serves 0.2.4 (`jnwb-0.2.4-py3-none-any.whl`, sha256 a5aad590f825..., and `jnwb-0.2.4.tar.gz`, sha256 1b5a90d6e52f...). Verified against the published artifact, not the checkout: `pip install --no-cache-dir --index-url https://pypi.org/simple jnwb==0.2.4` into a fresh 3.14.3 venv imports from that venv's site-packages and reports version 0.2.4, status Beta, release date 2026-09-16, 151/151 symbols resolving, a seeded `jrsa` p of 0.2189 reproducible across calls, and an unknown keyword rejected |

### Findings triaged in the 0.2.4 critic pass and deliberately not repaired

- vFLIP's crossover remains shrunk toward the centre of the shaft (fitted slope 0.703 at
  SNR 20, 0.804 at SNR 100, 0.864 at SNR 1000). The mechanism was traced, not assumed: both
  band depth profiles are dominated by bins carrying no laminar source, so the per-trial
  min-max range comes from noisy extremes and compresses each profile toward its interior.
  No correction factor is applied, because a factor tuned to flatten the sweep is exactly
  what the repair authorization forbade and the residual is a property of band-averaged
  range-normalized profiles at finite SNR rather than a coding defect. It is measured in the
  calibration, documented on `VFlipResult.crossover_contact`, and pinned in both directions
  by `test_the_documented_centre_shrinkage_is_the_measured_one`.
- `cross_modal_comparison`'s corrected p cannot resolve below about `n_lags / n_samples`,
  because a circular shift relands a genuine peak inside the searched window about that
  often. A shift-predictor null drawing only from beyond the window was written and measured
  and then discarded: it rejected 11.7% of independent pairs against a nominal 5%, because
  excluding the overlapping shifts breaks the group structure the p-value rests on. The
  valid null is reported together with `lag_search_resolution_floor` and a warning.
- `jrsa(metric='hsic')` uses a fixed RBF bandwidth in data units and is therefore
  unit-dependent by definition; unchanged, as recorded under item 04.

## Handout (2026-09-15, Opus 5 session `9fe5eb2c`) -- RESOLVED 2026-09-16

### State

Resolved. The single-writer recovery protocol below was executed in full: the 13 foreign
uncommitted files were classified by provenance rather than stashed or discarded, the
competing zFLIP segmentation rule was settled on test evidence so that exactly one rule
remains in `jnwb/laminar.py`, and the understood changes were partitioned into validated
commits staged by exact path. The RC is no longer blocked on worktree reconciliation. This
section is retained as the record of what was recovered, not as an instruction to repeat it.

The zFLIP discriminators listed as lost were rewritten from the specification rather than
restored from an old file version; they are `tests/test_zflip_audit.py`, which covers delay
and apparent velocity against an independently constructed travelling wave, the phase-slope
convention against an external oracle, reversal negating both delay and direction, pitch
scaling velocity while leaving delay unchanged, amplitude invariance, refusal of independent
noise, zero-lag and constant input, a delay beyond the unambiguous interval being declined,
and seeded reproducibility without mutating the global numpy RNG.

Standing rule that came out of it: one writable agent per worktree (`AGENTS.md` section 8).
Two implementation agents ran against this worktree at once; a `git stash push`/`pop` pair is
what lost work. Repository history is recoverable, a shared working tree is not.

### Sealed with green CI (3.12/3.14 x ubuntu/windows), do not redo

`bf26b0cf` 2-D rejection + first CUDA receipt; `e5a7eecc` coherence single-segment repair;
`4e427ad1` mismatched-length `ValueError`; `d754e895` 0.2.4-15 closed under its narrowed
criterion; `d7d06107` unpaired-trace rejection in `wpli`/`imaginary_coherency`.

Headline result: `cross_area_coherence`, `imaginary_coherency`, `wpli` and `zflip` all
reported perfect coupling for independent signals whenever the segmentation yielded a single
Welch segment, because the cross-spectrum is then an exact function of the auto-spectra. All
four now refuse `K < 2`.

### Next

0.2.4 is released and verified from PyPI; items 01 and 17 are closed on that receipt. Work
continues under the 0.2.5 heading below.

# 0.2.5

Carried forward from 0.2.4. Neither item blocks the 0.2.4 release: both are limitations of
a receipt or a test, each already mitigated by something that runs on every suite, and both
are stated where a reader would look. They are work, not open decisions.

- `artifacts/benchmarks/xflip_calibration_0.2.3.md` has no generator and cannot be
  regenerated. It says so, names the 0.2.4 change to `xflip`, and points at
  `tests/test_xflip_calibration.py`, which measures the same operating characteristics
  against the shipped estimator on every run. For 0.2.5: write the generator, or retire the
  document in favour of the test that supersedes it.
- `test_frequency_grid_resolution_invariance` uses a noise-free PSD, so it cannot measure a
  null's grid dependence; the calibration receipt does that instead. For 0.2.5: give the test
  a noisy PSD so it measures what its name claims.

## Onboarding audit (2026-09-16)

Audited against one persona: a user who knows `pynwb` and nothing else, who has their own
NWB file, wants to inspect it with jnwb, and then wants an agent to analyse it. The library
half passed on evidence -- a foreign file written with plain pynwb (16 channels x 60 s at
1 kHz, a standard `trials` table whose code column is named `stimulus`, 4 units, no jnwb
fixtures) went `inspect` -> `events` -> `unit_spike_times` / `acquisition_channel` ->
`epoch_continuous` -> `compute_psd` with no modification to the documented calls, recovering
the injected 18.0 Hz, and `event_onsets` refused a missing code column by name rather than
silently returning every onset. The agent half did not: the skills are not distributed, and
nothing a user reads tells them the skills exist.

- **05-01 Agent onboarding page. DONE.** `docs/agents.md` is written and in the nav: what ships and what does not, the three MCP tools with a client configuration snippet, the nine skills and why they are not in the wheel, and the safeguards to read when you have none of them. Found and fixed while writing it: `python -m jnwb.mcp_server`, the launch command doc 10 has always given, failed with "'jnwb.mcp_server' is a package and cannot be directly executed" -- the `if __name__ == "__main__"` guard sat in `__init__.py`, where a package can never satisfy it. Original text: There is no documented path from `pip install jnwb` to an
  agent that can analyse a file. Across `docs/` and `README.md` the word "skill" appears only
  in `docs/11_extending_and_development.md`, a contributor page; the only agent pointer is
  README's "If you are an AI agent, read AGENTS.md first", which sits in the contributing
  section. MCP is mentioned twice in all of `docs/` (the `jnwb[mcp]` extra in `install.md`
  and one line in doc 10). Write a user-facing page: the skill inventory, where the skills
  live and how to install them, an MCP configuration snippet, and what the three shipped MCP
  tools (`inspect_nwb`, `get_event_codes_and_timings`, `prepare_signal_reference`) do and do
  not cover -- they are inspection only, so every analysis step is still code.
- **05-02 Distribute the agent surface. PARTLY DONE.** `MANIFEST.in` now grafts `skills` and includes `AGENTS.md`: the rebuilt sdist carries 102 entries with 36 under `skills/`, all nine `SKILL.md` files and `AGENTS.md`, against 63 entries and none before. The wheel still does not carry the skills, and that stays a decision rather than an oversight: the canonical tree is `skills/`, and a copy under `jnwb/` is the second tree harness gate 2 and `test_no_forbidden_skill_trees_or_ide_authority` forbid. Original text: Neither artifact ships it. The 0.2.4 sdist has 63
  entries, of which `skills/` is none, `AGENTS.md` is none, `docs/` is zero and `examples/`
  is zero; the wheel ships `jnwb/mcp_server` but no skills. The README line naming AGENTS.md
  is carried into the installed wheel metadata, where it links to a file the wheel does not
  contain. Ship `skills/` and `AGENTS.md` in the sdist at minimum, and decide whether the
  wheel should carry the skills as package data so an agent working in the user's own
  environment can find them without cloning.
- **05-03 A tutorial that takes the user's own file. DONE.** `examples/tutorials/00_your_own_file.py` takes a path and an optional table name, derives the table and code column from `inspect`, guards both alignment steps on what the file actually has, and writes a plain-pynwb stand-in when given no argument so it still runs unattended in the release gate. It defers table choice to jnwb rather than reimplementing it: an earlier draft took `tables[0]` and, on the canonical fixture's five interval tables, aligned to detected photodiode changes and reported 0.00 Hz without complaining. Original text: All eight tutorials write a synthetic
  fixture into a temporary directory and assert against it; none shows a user-supplied path.
  Tutorial 01 carries nine assertions including
  `info["session"]["identifier"] == "TEST_SYNTH_CANONICAL"` and `n_units == 2`, so a reader
  who points it at their own recording fails inside the tutorial rather than in their data.
  Add a tutorial that accepts a path, derives the interval table and the code column from
  `inspect` output instead of asserting fixture values, and still runs unattended in CI by
  falling back to a generated file when no path is given.
- **05-04 Make `code_column` visible where it is needed. DONE.** README and quickstart now read the column off `inspect` and pass it, and the README block is executed verbatim by `test_readme_nwb_workflow_block_executes`, which previously only reimplemented an analogous flow and would have passed whatever the README said. `events` no longer nulls an absent column in silence: the default name warns and names the columns that exist, a column the caller named raises `ColumnNotFoundError` exactly as `event_onsets` already did. Original text: A file from another lab rarely has
  a column named `codes`. `code_column` appears only in the generated `docs/api.md` and in
  `skills/jnwb-nwb-data/SKILL.md`; README, quickstart, the tutorials and common-mistakes all
  say "usually `codes`" and stop. `jnwb.events(path)` on a file without that column returns
  `code_column=None, codes=()` and raises no warning, and so does an explicitly misspelled
  `code_column="condition"`. Show the parameter in README and quickstart, and make `events`
  warn when the requested code column is absent, naming the columns that do exist -- the
  information `event_onsets` already puts in its `ColumnNotFoundError`.
- **05-06 `resolve_interval_table` does not take a path.** It is exported in `jnwb.__all__`
  alongside `inspect`, `events`, `event_onsets` and `unit_spike_times`, all of which accept
  a path or an in-memory `NWBFile`, but its signature is `(nwb: NWBFile, table: str | None)`
  and passing a path raises `AttributeError: 'str' object has no attribute 'intervals'`
  rather than a contract error. Found while writing the 05-03 tutorial, which now routes
  table resolution through `events` instead. Either accept the same union as its peers, or
  raise a contract error naming what it wants.
- **05-05 An ingest section in common mistakes. DONE.** Section 9, "Assuming a Schema the File Does Not Have": no default interval table, `codes` is a jnwb default and not an NWB requirement, onsets are seconds, layout is discovered. Original text: All eight sections are downstream analysis
  traps; none covers getting a file in. Add one: there is no default interval table, the code
  column is not always `codes`, onsets are seconds, and the channel layout is discovered from
  `inspect` rather than assumed.

# Before 1.0

- Replace example-based estimator coverage with analytic/property-based tests.
- PSTH SEM policy for `N=1` trials (zero vs NaN) if statistical contract tightened.
- Processing-module discovery generalization beyond LFP if corpus requires it.

# Unversioned

- File omission-side expert-feedback items in the omission repository.
