# jnwb architecture — PRGS Prepare snapshot, 2026-08-15

**Status:** observed-fact map of the live `jnwb/` package on `dev` @ `47d364e` (+ uncommitted
working tree). Built from direct file reads (this agent) and delegated direct file reads
(sub-agents, same session, no synthesis-without-citation). Every claim below carries a
`file.py:line`. Where a sub-agent's finding was not independently re-read by the orchestrating
agent, it is marked **(delegated)** — still a direct read, just not by this document's author.

No absolute data path or corpus count is repeated here — see `context/PROJECT_STATE.md`.

---

## 0. Package inventory

`jnwb/` contains (top level, `.py` files, current working tree):
`__init__.py, addressing.py, analog.py, analyzers.py, artifact_repair.py*, bilinear.py,
compression.py, connectivity.py, decoding.py, diagnostics.py, factories.py, functions.py,
gpu_pca.py, jrsa.py, metadata.py, nam.py, ontology.py, omission_identity.py, onset_fitting.py*,
paths.py, permutation.py, report.py, sequence_layout.py, session.py, spectral.py, spiking.py,
statistics.py, structured_identity.py, structured_identity_m2a.py, tfr_accumulator.py,
trajectory.py, trial_ontology.py, unit_classification.py, viz.py, visual_qc.py`, plus
`jnwb/_unused/` (`__init__.py, complex_tfr.py, markdown_report.py`) and `jnwb/mcp_server/`
(5 files, not deep-audited this pass).

`*` = **untracked in git** (`artifact_repair.py`, `onset_fitting.py` — `git log --all` returns
empty for both; `git status` shows `??`). OBSERVED FACT.

`jnwb/complex_tfr.py` and `jnwb/markdown_report.py` were moved verbatim (byte-identical diff)
to `jnwb/_unused/` on 2026-08-14 (delegated). The move is **git-incomplete**: the adds are
staged (`A`), the deletions of the originals are unstaged (` D`) — restoring the staged/unstaged
halves independently would resurrect a duplicate. `tests/test_tfr_complex.py:14` imports the
new `jnwb._unused.complex_tfr` location live — **this module is not dead code**, despite the
directory name. `jnwb/markdown_report.py`/`jnwb/_unused/markdown_report.py` has zero test
coverage and zero script consumers found — genuinely dead (delegated).

**Stale registries (CLAUDE.md's own "registries go stale silently" tripwire, self-inflicted):**
`.claude/skills/omission-signal/SKILL.md:71` and `.claude/skills/omission-figures/SKILL.md:110,113`
still instruct `from jnwb.complex_tfr import ...` / `from jnwb.markdown_report import ...` —
paths that no longer exist. `jnwb/README.md:81,104` same. (delegated)

---

## 1. NWB / data loading

**Canonical:** `jnwb/session.py::OmissionSession._load_nwb` (session.py:101-170).

- Opens via `pynwb.NWBHDF5IO(str(nwb_path), 'r', load_namespaces=True)` (session.py:132).
- Disk-caches `units_df`/`electrodes_df`/`intervals_df`/metadata as pickle/JSON under
  `artifacts/developer/.cache/{session_stem}_*` (session.py:108-168), keyed off `_REPO_ROOT`
  imported from `jnwb/paths.py` — a documented fix (session.py:22-29) for a real prior bug
  where a relative cache path silently duplicated a 6.7 GB cache tree when a script was
  invoked from a different CWD.
- Cache-read failure (`except Exception` session.py:129-130) falls back to a full NWB reload,
  logged, not silent.
- One `OmissionSession` = one NWB file = one recording session. No multi-session join inside
  the class; population/multi-session queries are external (scripts loop over sessions).

**Path resolution:** `jnwb/paths.py` (full file, all resolvable roots). Two root classes:
repo-internal (derived from `__file__`, always correct) vs external-data (env-var override,
`DEFAULT_NWB_DIR="D:/nwb/omission"`, `DEFAULT_ANALYSIS_DIR="D:/analysis"` — paths.py:83-84).
`require()` (paths.py:186-198) fails loud with the fix; `describe()` (paths.py:201-217) is the
diagnostic entry point after any drive remap. Module docstring (paths.py:1-29) documents the
exact prior incident this module was built to stop: ~27 scripts + session.py/viz.py/report.py
hardcoding `D:/...` literals that silently resolved to nonexistent paths after a drive remap.

**Failure behavior:** loud for the repo-internal roots (can't be wrong); loud via `require()`
for external roots when a caller opts in; **silent** for `nwb_dir()`/`tfr_dir()`/`meta_dir()`
themselves — they always return *a* `Path` object, real or not, and only fail when something
downstream tries to use it (e.g. `tfr_from_preprocessed`'s `if not tfr_root.is_dir(): log.warning(...); return None` — session.py:662-664, a soft/logged, not raised, failure).

**Tests:** `tests/test_jnwb_core.py` (delegated, not independently opened this pass).

---

## 2. Session abstraction

**Canonical:** `jnwb.session.OmissionSession` (session.py:57-1029). Public accessor surface:
`get_units`, `get_electrodes`, `get_epochs`, `get_trial_onsets`, `get_spike_times`,
`channel_unit_mapping`, `lfp_channel_areas`, `tfr_from_preprocessed`, plus a large plotting
surface (`trial_averaged_plot`, `channel_averaged_plot`, `spectrolaminar_motif`, `plot_tfr`,
`raster_suite`, `lfp_tfr_trace_suite_omission`, `lfp_tfr_trace_correlation`, `pie_charts`) and
`info`/`summary`/`__repr__`.

Failure behavior is **uniformly "return empty, log, don't raise"** across almost every accessor:
`get_units` → `pd.DataFrame()` if `_units_df is None` (session.py:194-195); `get_electrodes`
same (session.py:217-218); `get_epochs` → `pd.DataFrame()` + `log.warning` if no intervals
(session.py:249-251); `get_trial_onsets` → empty `np.array` (session.py:298-299);
`get_spike_times` → `None` + `log.warning` if unit not found (session.py:356-358);
`plot_tfr` is the one documented exception — returns an explicit
`status='missing_tfr'` dict rather than fabricating a plot (session.py:729-730, 742-748,
directly citing CLAUDE.md's "no silent science" doctrine in its own docstring).

**Tests:** `tests/test_jnwb_core.py`, `tests/test_jnwb_integration.py`,
`tests/test_jnwb_nwb_integration.py` (delegated, filenames confirmed via `Glob`, contents not
independently re-read this pass).

---

## 3. Metadata + event/trial/epoch ontology

**This is the layer with the most invariant-protection code in the package** — three modules,
each documenting a previously-real bug it was built to prevent.

**`jnwb/trial_ontology.py`** (197 lines, full read) — the canonical condition-code parser.
- `parse_condition(code) -> dict` (trial_ontology.py:53-115): pure string parser. **Raises**
  `ValueError` on any code outside the 12 recognized ones (:60-64), on a partial-but-invalid
  match (:81-82), on >1 'X' (:85-86). Strict-fail by design.
- `build_trial_ontology(session, slot_keys=("p2","p3","p4"), phase=2, families=("A","B","R"))`
  (:122-196) — **one output row per (slot_key, family, epoch)**, not a flat 1:1 map from NWB
  rows. This directly answers the audit question "are event rows treated as trial rows": **no**
  — an NWB interval row can contribute to multiple ontology rows across different `slot_key`
  values in one pass (:152-194).
- Pulls **all** trials (`correct_only=False`, :159) and records `correct_trial` as a data
  column, not a filter — correctness filtering is explicitly deferred to
  `structured_identity.py`.
- Module docstring (:1-22) names the historical incident this module exists to prevent: the
  2026-08-06 p4 A/B label swap (see `omission_identity.py` below) — ad hoc condition-string
  parsing scattered across the codebase was the root cause; this module centralizes it.

**`jnwb/omission_identity.py`** (699 lines, delegated full read) — `OMISSION_IDENTITY_CONDITIONS`
(:35-46) is the per-slot condition→timing map, cross-checked against `trial_ontology.py`'s
independent parser by `tests/test_trial_ontology.py` (per that test file's own docstring claim,
not independently re-verified). Documents, in its own source, **two now-fixed historical bugs**:
  1. (:38-44) 2026-08-06 — p4's expected identity was swapped (AAAX's parent is AAAB, so
     omitting p4 hides B, not A) — "every p4-specific number computed before this fix... must
     be treated as unreliable until rerun; p2 was never affected."
  2. (:229-259) task_block_number was assumed to mark one contiguous trial block per condition;
     it actually reuses the same integer label across ~3 temporally separated repeats per
     session (median inter-trial gap 60-130s, but 2-3 gaps of 3000-4400s) — `detect_trial_cycles`
     (:248-270) was built as the corrected replacement.
- Two functions (`decode_omission_identity_slot`, `decode_omission_identity_full`) carry a
  **live, currently-open** `scientific_status = "invalid_for_inference"` docstring flag
  (:127-133, :356-363), reason `ungrouped_cv` — `StratifiedKFold(shuffle=True)` doesn't respect
  the repeated-cycle structure, so same-cycle trials can leak across train/test. Docstrings
  explicitly redirect callers to `scripts/compute_omission_identity_leakage_safe.py`. These two
  functions are **quarantined-but-retained**, not deleted (:127-133 names the only live callers
  as `scripts/historical/confounded/*`).
- `decode_identity_cycle_deconfound` (:480-628) is the corrected, leave-one-cycle-out variant,
  with a stated "HONEST LIMIT" in its own docstring (:501-505): rules out monotonic drift and
  per-cycle mean shift, cannot rule out a fixed order-locked transient recurring after every
  block transition.

**`jnwb/structured_identity.py`** (413 lines, delegated) — Milestone 1 scaffolding,
`TRAINING_AUTHORIZED = False` hardcoded gate (:27), explicitly "contains no model fitting."
`build_canonical_trial_table` extends `trial_ontology`'s rows with an auditable
`eligibility_reason` column (`np.select`, one of `incorrect_trial|insufficient_cycles|
non_identity_family|eligible|not_primary_target`, :169-178) — never a silent boolean.

**`jnwb/structured_identity_m2a.py`** (492 lines, delegated) — Milestone 2A, the actual
approved ridge-regression decoding implementation, gated behind Milestone 1's sign-off per
`structured_identity.py`'s own docstring. `WINDOWS_MS` (:19-24) gives the full-sequence-relative
per-slot windows in ms (p1: 0-531, p2: 1031-1562, p3: 2062-2593, p4: 3093-3624) — this is the
**full-sequence time base**; omission-relative windows live separately in
`omission_identity.OMISSION_IDENTITY_CONDITIONS`. **These two time bases are kept as distinct,
separately-named constants in separate modules — confirmed distinguishable, not confirmed
reconciled against each other.**

Not duplicates of each other: m1 = ontology/scaffolding, no fitting, hard-gated; m2a = the
fitting step that consumes m1's output once reviewed. Both are live (imported by
`scripts/materialize_structured_identity_milestone1.py`,
`scripts/run_structured_identity_milestone2a.py`, others; delegated grep), both have dedicated
test files.

**`jnwb/metadata.py`** (delegated) — `get_all_units_metadata`'s own docstring is stale: it
claims a `cluster_id` output column that a code comment two lines away (metadata.py:178-180)
confirms is always renamed to `unit_id` and never present. Broad `except Exception` at
metadata.py:84 and :301 silently drops a failed file from a multi-file aggregate, `continue`s,
logs via `log.error` (not raised).

**`jnwb/diagnostics.py`** (delegated) — `audit_session` treats **any** warning as
`passed=False` (diagnostics.py:106-107, a strictness choice, not a bug) but its own top-level
`except Exception` (:100-104) converts a genuine `AttributeError` (e.g. a code typo) into the
same "data quality issue" shape as a real missing-table warning — indistinguishable to a caller.

**Tests:** `tests/test_trial_ontology.py`, `tests/test_structured_identity_milestone1.py`,
`tests/test_structured_identity_m2a.py`, `tests/test_diagnostics_and_metadata.py`. **No
dedicated `test_omission_identity.py`** exists — `omission_identity.py` (699 lines, contains the
two quarantined functions) is exercised only indirectly via `test_cv_grouping_acceptance.py`,
`test_permutation_lint.py`, `test_trial_ontology.py`'s cross-check. **Coverage gap**, flagged.

---

## 4. Probe/channel/unit addressing

**Canonical:** `jnwb/addressing.py` (187 lines, full read) + `jnwb/sequence_layout.py`
(delegated, 603 lines).

- `map_peak_channel_to_area(peak_channel_id, electrodes_df)` (addressing.py:19-81): resolves
  via the electrodes table's `location`/`area`/`group_name` column. **Multi-area probe handling
  is explicit and position-based**, not filename-inferred: for a probe labeled e.g. `"V1, V2,
  V3"`, channel position within the probe is binned via `np.linspace(0, n_channels_on_probe,
  len(areas)+1)` + `searchsorted` (:74-77) — this is a **documented bug fix** (:55-61): the
  previous code always returned the first listed area regardless of channel position,
  confirmed wrong on real probe-C channels 118-120 (labeled V1, should be V3).
- `classify_layer_from_depth` (:84-109): `z > 1000.0 µm → Deep else Superficial`, a **hardcoded
  threshold**, comment calls it "canonical neuroscience threshold" with no citation to a
  fitted/validated boundary — this is a task/domain constant per CLAUDE.md's tripwire-1
  exemption, but its provenance (measured vs conventional) is not stated in-file.
- `enrich_units_dataframe` (:112-185) — the single point where `unit_id` gets standardized
  (`cluster_id`→`unit_id` rename, :128-129) and where the row-position identity convention is
  locked in via `df.reset_index(drop=True)` (:183, comment: "guarantee row-position lookup in
  get_spike_times"). Also silently coerces `firing_rate`/`waveform_duration`/`snr`/`unit_id` to
  numeric (:178-180) — documented fix for a real cross-session dtype bug (string vs float64)
  that silently failed every `==` comparison.

**Documented identity footgun, present in three independent places** (addressing.py's own
comment :327-338 in session.py, `jnwb/ontology.py:98-104`, `jnwb/factories.py:44-51`, all
delegated/direct-quoted): the canonical unit identity is **raw DataFrame row position**
(`units_df.index`, a RangeIndex, globally unique within a session), **not** the `unit_id`/
`cluster_id` **column**, which is a per-probe-local kilosort ID that resets to 0 per probe and
collides across ≥3 areas within one session (confirmed 2026-07-12). `session.get_spike_times`
tries row-position lookup first (session.py:339-341), falls back to column-match only if that
fails (:343-354).

**A second, inconsistent identity convention exists**: `jnwb/omission_identity.py` addresses
units via `units_df["unit_id"].tolist()` (delegated, e.g. :93, :314, :516) — the column, not row
position. Whether this is safe depends on whether `get_units(area=...)` was called with a
single-area filter first (which would make cross-probe collision moot within that slice); **not
independently verified this pass** — flagged as an open question, not a confirmed bug.

**`jnwb/sequence_layout.py`** (delegated): `parse_probe_areas`, `normalize_area_name`,
`channel_slice_for_area` — the probe-string → area-tuple → channel-slice geometry.
`channel_slice_for_area`'s >2-area branch is explicitly commented `"legacy fallback"`
(sequence_layout.py:178, delegated) and uses an unweighted equal-partition, unlike the 2-area
case's documented position-aware fix above — an inconsistency between the ≤2-area and >2-area
code paths worth flagging.

**Band-edge discrepancy (delegated, cross-file):** `sequence_layout.BANDS_7` (theta 3-7, alpha
8-12, l-beta 12-20, h-beta 20-30, Gamma_L 32-50, Gamma_H 50-90, Gamma_HH 90-200) numerically
disagrees with `connectivity.CANONICAL_BANDS` (theta 4-8, alpha 8-14, beta 14-30, low_gamma
30-50, high_gamma 50-80) — same band *names*, different Hz edges. `BANDS_7`'s own docstring
scopes it to visualization/labeling; not confirmed whether it ever feeds a statistical
computation. **Two sources disagree on the same quantity — a CLAUDE.md stop condition,
surfaced, not resolved, here.**

**Tests:** delegated — coverage not independently enumerated for `addressing.py`/
`sequence_layout.py` specifically this pass.

---

## 5. Signal access

### LFP / MUAe

**Canonical:** `jnwb/analog.py::load_analog_epochs` (delegated, full read) +
`load_lfp_epochs`/`load_muae_epochs` thin wrappers (analog.py:492-499). Single code path
parameterized by `signal_class ∈ {"LFP","MUAE"}` (validated, analog.py:341-343), hard h5py-key
namespace split on the `_lfp`/`_muae` acquisition-group suffix (`_series`, :224-278, exact
suffix match). Every call returns exactly one signal class; **no function in this file accepts
both** — LFP and MUAe are never pooled as arrays, only as parallel calls sharing one code path.
Contract: always `(trial, channel, time)`, `time_ms` relative to the alignment anchor,
**raw float32 values, no filtering/resampling** (manifest field states this explicitly).

**SUA/SPK is entirely absent from `analog.py`** — spike access lives in `session.py`
(`get_spike_times`) and `jnwb.spiking`, a structurally separate code path from LFP/MUAe. This is
the primary mechanism keeping the three signal classes apart: **different modules, different
function families, no shared array container** — not a runtime type check.

### Generalized directed-connectivity layer — deliberate class-agnosticism

**`jnwb/connectivity.py`** (2023 lines, delegated full read). Module docstring (:14-26) and an
in-code comment (:504) state as **design intent**: `granger`/`granger_spectral`/
`phase_slope_index`/`transfer_entropy` all take the same `(X, Y)` contract regardless of
whether X/Y are LFP microvolts, spike counts (via `bin_spikes`, :702-764), MUAe envelopes, or
band power — "nothing in this layer knows or cares." **No `signal_class` parameter or check
exists anywhere in this estimator family.** This means a caller can pass LFP as X and a
spike-derived rate as Y into one `granger()` call with zero validation — deliberate by design,
but it means **enforcement of the "SPK/MUAe/LFP never pooled" invariant is pushed entirely to
callers of this layer**, not enforced by the layer itself. Arrays themselves are never
concatenated (X, Y stay separate objects); the risk is silent cross-class *comparison*, not
array corruption.

`CANONICAL_BANDS` (:48-54, the file's own comment calls it "the single canonical source") is
imported by `spectral.py:192` (delegated, confirmed) — but see the `BANDS_7` discrepancy in §4
above; two canonical-sounding band tables coexist.

Two independent Granger implementations coexist: `granger_causality` (legacy, plain-dict
return) vs `granger` (current, `DirectedResult`-return) — overlapping VAR-fitting math
reimplemented in parallel rather than one delegating to the other (delegated).

### Spectral primitives

**`jnwb/spectral.py`** (649 lines, delegated). `to_db` (:26-34) is the single canonical
`10·log10` conversion point — directly enforces CLAUDE.md's "log last" tripwire by
centralization. `band_power(..., normalize=True, baseline=...)` does exactly one log step
(:450, delegated). **Pervasive pattern across all four LFP-facing functions**
(`harmonic_analysis`, `cross_area_coherence`, `spectral_tilt`, `band_power`): empty-input
returns a pre-filled zero/NaN dict or `0.0` rather than raising — `band_power`'s empty-input
`0.0` (:404-405, delegated) is **indistinguishable from a genuine near-zero measurement** in the
return value alone, which is a direct tension with CLAUDE.md tripwire 1 unless every caller
separately checks for empty input before trusting the number.

### Tests

`tests/test_muae_accessor.py` (MUAe), spectral/connectivity coverage not independently
enumerated by module this pass (delegated summary references GPU/CPU parity tests exist —
`test_gpu_spectral_analyzers.py`, `test_gpu_pca.py` — not opened).

---

## 6. Epoch/trial/condition selection API

`session.get_epochs(phase, condition, correct_only)` (session.py:227-281) is the single entry
point: numeric-coerces `correct`/`stimulus_number`/`task_condition_number` columns (NWB stores
them as strings, :256-261), filters `correct==1.0` when `correct_only=True` (default),
`stimulus_number==float(phase)`, and condition via a **subject-aware** crosswalk
(`condition_map_for_stem`, :51-54) — `RRXR`/`RRRX` map to different `task_condition_number`
ranges for V182o vs the other two subjects (documented investigation, session.py:31-39, user
supplied the V182o mapping directly after an inconclusive re-derivation attempt). This is a
**real, subject-specific addressing divergence, correctly handled as data, not silently
pooled.**

`get_trial_onsets` (session.py:283-300) hard-codes `phase=2` to guarantee P1-alignment — the
canonical "t=0" definition for this paradigm, stated as a "CRITICAL PARADIGM TIMING INVARIANT"
directly in `get_epochs`'s docstring (:232-239).

---

## 7. Analysis-facing API used by scripts/

**Two API surfaces coexist; only one is load-bearing (delegated grep, cross-checked):**

1. **"v1.0.0 PUBLIC API FROZEN"** — `jnwb/ontology.py`'s 11 frozen dataclasses (`Query`,
   `Dataset`, `AlignedDataset`, `Alignment`, `EpochCollection`, `Question`, `Result`,
   `Interpretation`, `Figure`, `Provenance`, `Lineage`) + `jnwb/factories.py`'s 7 named
   factories, all re-exported at `jnwb/__init__.py`. **Zero confirmed usages in `scripts/`**
   (grep for the 7 unambiguous factory names returned no matches; the 11 class names are too
   generic to grep reliably but no `jnwb.ontology`/`jnwb.factories` import appears outside
   `jnwb/__init__.py`, `tests/test_factories.py`, and `legacy/examples/`). Several of the
   dataclasses' own "verb" methods (`Dataset.get_spike_times/where/select`,
   `AlignedDataset.get_epochs/answer`, `Result.figure`, `Figure.save`,
   `create_dataset_from_query`, `create_epochs`) are unimplemented stubs that
   `raise NotImplementedError` (ontology.py:178-192, :180, delegated, direct-quoted) — a
   deliberate frozen-API-with-deferred-implementation pattern per the module's own docstring,
   not a bug, but confirms the surface is inert without `factories.py`, which itself has no
   `scripts/` consumers either.
2. **"20 canonical functions"** — `jnwb/functions.py` (845 lines, delegated full read), also
   re-exported at top level. Grep for `from jnwb.functions import` / `jnwb.functions.` in
   `scripts/`: zero matches. Individual function names (`raster_plot`, `pie_charts`, etc.) are
   too generic to grep reliably one-by-one; **not exhaustively disambiguated this pass** — this
   is a moderate-, not full-, confidence "likely unused," unlike the ontology finding above.

**The real, load-bearing API** (delegated frequency count across ~136 of 245 `scripts/*.py`
files that import `jnwb` in some form): `import jnwb as oa` + `jnwb.paths` (73 uses each, tied
top),`jnwb.sequence_layout.EPOCH_ONSETS_MS` (~23), `jnwb.unit_classification
.precompute_condition_onsets` (~12), `jnwb.paths.sha256_file` (~10),
`jnwb.omission_identity.OMISSION_IDENTITY_CONDITIONS` (~6), `jnwb.permutation.permute_labels`
(~6), `jnwb.connectivity.bin_spikes` (~6), `jnwb.statistics.*` (~5-8), plus direct use of
`artifact_repair`, `viz`, `spectral`, `structured_identity*`, `jrsa`, `bilinear`, `nam`,
`decoding`. **Scripts import domain-specific functions/constants directly from their owning
submodule — they do not go through the ontology/factory/20-function "public API" layer at all.**

---

## 8. Downstream omission analyses

Not separately audited this pass beyond the import-frequency table in §7 — see
`JNWB_API_INVENTORY.md` for the per-module function list and `scripts/` consumer counts where
available.

---

## 9. Legacy compatibility layers

- `jnwb/_unused/` — see §0. One of two files (`complex_tfr.py`) is live via tests; the other
  (`markdown_report.py`) appears genuinely dead (zero test, zero script consumer, delegated).
- `jnwb/ontology.py` + `jnwb/factories.py` — see §7. Functionally a legacy/aspirational layer
  despite being labeled "frozen v1.0.0," by usage evidence rather than by naming/directory
  convention.
- `jnwb/report.py` (941 lines, delegated full read) — **not `jnwb/markdown_report.py`, a
  separate, still-`jnwb/`-resident module.** Contains four report sections that run real
  statistical procedures (`mannwhitneyu`, `fdr_correct`) on **`np.random`-generated synthetic
  data** (report.py:507-510, :527-528, :551-559, :582-590, delegated, direct-quoted) — labeled
  only with an orange "⚠️ SIMULATED DATA" HTML pill, not the red `PLACEHOLDER-DUMMY` title
  CLAUDE.md tripwire 2 mandates for exactly this situation. One section (population identity
  decoding, :644-740) is genuinely computed and correctly badged "✓ COMPUTED" — proving the
  authors could and did distinguish real from synthetic elsewhere in the same file, making the
  four synthetic sections' non-conforming badge a gap, not an oversight of the concept.
  **This is the single highest-severity architecture finding in this audit** — see
  `NEXT_ACTIONS.md`.
- `legacy/` (149 git-tracked files, 7.0 MB, top-level repo directory, not inside `jnwb/`) — not
  jnwb code, but includes `legacy/tests/` (57 files) separate from the live `tests/` (36 files);
  not audited for jnwb relevance beyond the `_unused` cross-check above.

---

## Summary table — invariant enforcement status

| Invariant | Status | Evidence |
|---|---|---|
| Event rows ≠ trial rows silently | **enforced** | `trial_ontology.build_trial_ontology` explicit multi-row-per-epoch design, §3 |
| p1-p4 addressing stable | **enforced, with one now-fixed historical violation** | p4 A/B swap fixed 2026-08-06, `omission_identity.py:38-44`; centralized parser added after (`trial_ontology.py`) |
| Full-sequence vs omission-relative time base distinguishable | **enforced (as separate named constants)**, cross-reconciliation **unknown** | `structured_identity_m2a.WINDOWS_MS` vs `omission_identity.OMISSION_IDENTITY_CONDITIONS`, §3 |
| SPK/MUAe/LFP not conflated | **enforced at the data-access layer, not enforced at the generalized-connectivity layer** | `analog.py` hard split; `connectivity.py` deliberately class-agnostic, §5 |
| Channel-area segmentation canonical/deterministic | **enforced for ≤2-area probes, weaker for >2-area (unweighted "legacy fallback")** | `addressing.py:19-81`, `sequence_layout.py:178`, §4 |
| Multi-area probes handled explicitly | **enforced** | `addressing.py` position-based binning, documented bug fix, §4 |
| Unit area via peak/anchor-channel addressing | **enforced, but two coexisting unit-identity conventions (row-position vs `unit_id` column)** | §4 |
| Tensor dims/units not silently transformed | **mixed** — most modules document dims/units in docstrings; `analyzers.compare_conditions` returns a flattened p-value array with no index back-mapping | §5, delegated `analyzers.py` finding |
| Empty selections fail visibly | **violated, pervasively** | `session.py` accessors, `spectral.py`, `metadata.py`, `functions.py` all return empty/zero/NaN rather than raising by default, §2/§5/§3 (see `JNWB_TEST_EVIDENCE.md` and `NEXT_ACTIONS.md` for severity ranking) |
| Condition names / omission positions retain canonical semantics | **enforced**, with **known, self-documented historical violation now fixed** and **two open quarantined functions** | §3 |
