# LFP Encoding Battery — Specification (not executed)

Status: **SCOPING ONLY, per Hamm's explicit instruction 2026-08-26. Do not execute until
reviewed and accepted.** Goal: an LFP analogue of the corrected Fig04 SPK encoding analysis,
matched on scientific targets and inferential machinery, with modality-appropriate
preprocessing upstream of a shared operator.

**Correction, same day:** the first version of §1/§2/§8 wrongly concluded the precomputed TFR
cache "does not exist," because only `D:/analysis` was checked. Hamm supplied the real path
(`E:/analysis/tfr_arrays`); re-verified directly against the filesystem and found a complete,
correct 22-session, 735 GB precomputed corpus. This changes the tensor source (§2, now the
cache, not on-the-fly extraction) and the cost estimate (§8, now materially cheaper) below.

Companion evidence node: [`fig04-false-encoding-taxonomy-20260826.json`](../artifacts/.lab/fig04-false-encoding-taxonomy-20260826.json)
(`next_planned_analysis` field is superseded in detail by this document).

---

## 1. Exact eligible LFP corpus

**CORRECTION (2026-08-26, after Hamm supplied the real path):** the first version of this
section wrongly concluded the precomputed TFR corpus "does not exist," because I checked
`D:/analysis` and found nothing. The actual analysis root is `E:/analysis`, not `D:/analysis`
(raw NWB files are on `D:/nwb/omission`; derived products are on a separate `E:` drive) — the
manifest and `jnwb.paths` default I'd been trusting were themselves stale/pointed at the wrong
root, and I did not cross-check against a second location before concluding absence. Re-verified
directly against the filesystem this turn:

```
E:/analysis/
  tfr_arrays/    970 files, 735 GB total, ALL 22 sessions covered (cross-checked against
                 corpus_manifest.json's 22 session_prefixes -- zero missing, zero extra)
  metadata/      22 session sidecars + sidecar_index.json (electrodes.csv, events.csv,
                 h5_paths.json, probe_areas.json, sidecar_summary.json, units.csv per session)
  fig03_unit_census_psth_cache/
```

One sample file read directly:
`sub-C31o_ses-230816-A-PFC-AAAX.npz` -> `power: (23, 128, 99, 500) float32`,
`channels: (128,) int32`, `fit_exponent`, `fit_r2` -- matches
`precompute_tfr_arrays.py`'s documented contract exactly (trials x channels x 99 freqs x 500
time bins, freqs=arange(3,201,2), times=-1000+arange(500)*10ms p1-aligned). Areas present across
the corpus: FEF, FST, MST, MT, PFC, TEO, V1, V2, V3, V3a, V3d, V3v, V4.

`channel_area_vector.csv` also exists (8,993 rows, real per-channel
`session_prefix,probe_letter,channel,area,seg_start,seg_stop,...` assignments) -- but at
`omission/outputs/connectivity/channel_area_vector/channel_area_vector.csv`, not at the path
`precompute_tfr_arrays.py` hardcodes (`jnwb.paths.REPO_ROOT/outputs/channel_area_vector/...`,
missing the `connectivity` segment and pointed at the jnwb repo root rather than `omission/`).
This is a real, live path mismatch in that script (not something this spec needs to fix, but
worth a one-line note in blockers, §10) -- any consumer should reference the actual file
directly rather than trust the hardcoded default.

**Revised conclusion:** the rich, trial- and session-resolved precomputed TFR product **does
exist**, is complete across all 22 sessions, and is the right primary tensor source for this
battery (§2) -- not a fallback. `corpus_manifest.json`'s `n_sidecar_ok`/`n_tfr_ok`/
`n_tfr_files_on_disk` fields are themselves stale relative to `E:/analysis` and should not be
trusted for this question going forward without either fixing the manifest's search root or
re-checking the filesystem directly, as done here.

**Still to determine before implementation:** exactly which sessions carry which areas on which
probe letter (probe-to-area assignment confirmed NOT fixed across sessions -- see
`find_probe_for_area`'s docstring re: V182o), and how that LFP area coverage overlaps with the
SPK session lists Fig04 actually used (21 sessions for the leakage-safe encoding matrix; 4
representative sessions for the context/RSA decoders). `probe_areas.json` in each session's
metadata sidecar directly answers this per session; a one-pass enumeration across all 22
sidecars is a cheap first step (JSON reads, no NWB/TFR loading) once this spec is accepted.

## 2. Proposed trial-level tensor

**Revised (2026-08-26): load from the precomputed TFR cache at `E:/analysis/tfr_arrays/`,
confirmed complete and correct in §1, rather than recomputing on the fly.**

```
per (session, probe_letter, area, condition):
  d = np.load(f"E:/analysis/tfr_arrays/{session_prefix}-{probe_letter}-{area}-{condition}.npz")
  power    = d["power"]        # (n_trials, n_channels_kept, 99, 500) float32
  channels = d["channels"]     # original probe-channel indices, ascending -- provenance preserved
```

giving the real trial-level tensor directly, no extraction/FFT step needed:

```
X_{L,s} in R^{n_trial x n_channel x n_freq x n_time}    (99 freqs x 500 time bins, per file)
```

`freqs = arange(3, 201, 2)` Hz, `times = -1000 + arange(500)*10` ms, p1-aligned -- covering the
full trial (baseline + all four slots: p1=0, p2=1031, p3=2062, p4=3093, sequence end=4124ms,
from the same canonical `EPOCH_ONSETS_MS` already frozen for SPK). Slot-specific sub-windows
(p2/p3/p4, or the omission slot for a given condition) are sliced from this cached tensor by
canonical-timing offset -- exactly mirroring how the SPK pipeline slices `SLOT_ONSETS_MS`-based
windows from a wider extraction, so no independent (and therefore divergence-prone) timing
constant is introduced for LFP, and no re-derivation of p1 onsets is needed either.

The precomputed files already encode the channel-quality (1/f) screen: `channels` gives the
*kept* original indices (post-screen), and `fit_exponent`/`fit_r2` are the per-kept-channel 1/f
fit statistics -- so, unlike the on-the-fly path, this screen does not need to be re-applied or
re-implemented here; it was already applied when the cache was built.

Provenance preserved per cell, not discarded at any flattening step: `session_prefix`,
`subject` (parsed from the filename), `probe_letter`, `area`, `channels` (kept original probe
indices), `condition` code, `sequence_family` (A/B/R, via the same crosswalk
`precompute_tfr_arrays.py` already encodes as `CONDITION_NUMBERS`/`CONDITION_NUMBERS_V182O`),
and slot label (derived from the canonical-timing slice, not stored in the file itself).

**Fallback / cross-check path (not primary):** `_l_lfp_common.py`'s on-the-fly
`extract_epoch_trials` + `batched_spectrogram`, described in the previous version of this
section, remains available for any session/area/condition combination not covered by the cache
(none identified so far -- §1 found full 22-session coverage) or as an independent
numerical cross-check against a handful of cached files before trusting the corpus at scale.

**Trial-order alignment requirement:** the cached `.npz` files do not store per-trial
`start_time` (needed for `G = detect_trial_cycles`, §5) -- only `power`/`channels`/
`fit_exponent`/`fit_r2`. `precompute_tfr_arrays.py:382` confirms the cache's trial axis was
built from exactly `onsets = p1_onsets_s(f, cond)`, in that call's order. Re-calling the same
canonical `p1_onsets_s(f, condition)` against the same NWB file will deterministically reproduce
the identical, identically-ordered onset array, so it is safe to pair a freshly-computed
`start_time` array with the cached `power` trial axis **provided the exact same function and
condition string are used, never a re-derived or reimplemented onset selector.** State this as
an explicit invariant check (e.g. assert `len(onsets) == power.shape[0]`) at load time, not an
assumption left implicit.

**Channel-quality (1/f) screen**: `precompute_tfr_arrays.py`'s `screen_channels()` (via
`jnwb.spectral.spectral_tilt`) is a real per-channel exclusion (flat/positive/noise-dominated
electrodes), currently only wired into the TFR-cache code path. It should be reused (imported,
not reimplemented) against the on-the-fly-extracted channel blocks before any channel enters the
spectrogram step, so noisy/broken contacts are excluded here exactly as they would be in the
cached path — this is a real analysis choice to carry over, not cosmetic.

## 3. Five target constructions

Reusing the same trial-ontology machinery already trusted for SPK (`build_trial_ontology`,
`build_canonical_trial_table`, `POSITIVE_CONTROL`/`MAIN_ANALYSIS` condition families), applied
to LFP trials selected by the same `p1_onsets_s`/condition-crosswalk mechanism:

| Target | Definition | Construction notes |
|---|---|---|
| `Y_stim` | A vs B, at the physically-presented p1 slot | Positive control, same condition families as SPK's `POSITIVE_CONTROL` |
| `Y_position` | 3-way among p2/p3/p4 | Per-cycle centered, same `cross_cycle_id` construction as SPK's `_cross_slot_table` |
| `Y_omission` | Omission (O) vs stimulus-present (S), **position-matched** | Built per-position (`O_{p_i}` vs `S_{p_i}` for each of p2/p3/p4 separately) **and** as one position-balanced pooled cell (equal trial counts per position in both classes) — per Hamm's explicit requirement, so position cannot trivially solve omission-occurrence. This is the one target with no direct SPK analogue yet in `fig04-statistical-receipt-20260826.json` (flagged there as the "most important missing SPK cell" — see §"SPK companion task" below). |
| `Y_context` | Predictable (A/B family) vs Random (R family) at the omission slot | Same construction as the now-corrected SPK context decoder |
| `Y_expected` | X\|A vs X\|B during the omission window | Same construction as the SPK leakage-safe `Y_omit`/expected-identity decoder |

## 4. Representation set

Three representations, capped deliberately (Hamm: "do not create many representations simply to
search for positives"):

- **R1 — band-power x time**: integrate the spectrogram's frequency axis into the same 5 bands
  already used by `compute_multimodal_manifold_battery.py` (theta 4-8, alpha 8-14, beta 15-30,
  low_gamma 30-50, high_gamma 50-90 Hz), retaining the time axis.
- **R2 — frequency x time**: the full 99-bin frequency axis from `batched_spectrogram`, no band
  binning.
- **R3 — channel x frequency x time**: only if per-cell sample support (trial count relative to
  flattened dimensionality) is adequate once real per-session/area channel and trial counts are
  known from §1's enumeration pass — not committed to a fixed shape here.

Flattening to the generic encoding operator's 2D `(n_trial, n_feature)` input happens **only at
the interface**; coordinate provenance (which channel/frequency/time each flattened column came
from) is retained alongside, not discarded.

PCA is described, per Hamm's correction, as **linear variance compression before nonlinear
neighborhood representation** — not automatically as denoising. UMAP is described as
**nonlinear low-dimensional neighborhood/manifold representation.**

## 5. CV / permutation hierarchy

Identical machinery to the corrected SPK pipeline — the frozen operator `E(X, Y, G)`:

- **Outer CV**: cycle-grouped leave-one-cycle-out, `G = jnwb.statistics.detect_trial_cycles`
  applied to each cell's own trial `start_time` column — the exact same canonical function that
  fixed the SPK `Y_context` leakage bug and that `Y_position`'s SPK decoder was independently
  verified to already use.
- **Fold-local transformations**: `StandardScaler`/PCA/UMAP fit only on the training fold of
  each outer split; the outer test fold never participates in fitting any transform.
- **Nested hyperparameter selection**: PCA rank `N` and UMAP dimension `M` (and encoder choice)
  are selected by an inner CV/validation split carved out of the training fold only — the outer
  test fold must never participate in selecting `N`, `M`, the encoder, scaling, or UMAP
  parameters (Hamm's explicit constraint, and the row-6 prospective risk named in the
  false-encoding taxonomy).
- **Permutation null**: within-cycle-group-preserving permutation (`_within_cycle_permutation`
  / `jnwb.permutation.permute_labels(..., scheme="within_group")`), 999 permutations,
  `(1+k)/(N_PERM+1)` finite-sample floor correction (North et al. 2002) — identical to SPK.
- **Multiplicity**: BH-FDR declared per target family (across session x area x position cells
  within a target), matching the Fig04 convention.
- **Biological inference**: session-level, with the project's N>=2-independent-subjects RRR
  adequacy standard already applied throughout `fig04-statistical-receipt-20260826.json`.

## 6. PCA / UMAP search space

An LFP-appropriate grid, not copied blindly from the SPK `UnifiedManifoldEncoderEngine`
(`pca_grid=[5,10,20,30,50]`, `umap_grid=[2,3,5,8,10]`), because LFP's raw feature
dimensionality per representation differs substantially from SPK's (R2's full 99 x ~500
spectrogram grid, before any pooling, is far higher-dimensional than SPK's 10-bin spike-count
features). Proposed **starting** grid, to be bounded per-cell against the real `n_train`/`D`
once §1's enumeration is done (same bounding rule as the SPK engine: `N in [2, min(D,
n_train-2)]`, `M < N`):

```
N (PCA rank):  a data-driven subset of {5, 10, 20, 30, 50, 100}, filtered to N <= min(D, n_train-2)
M (UMAP dim):  {2, 3, 5, 8, 10}, filtered to M < N
```

This is a proposal, not a commitment — the exact usable subset depends on real per-cell trial
counts, which are not yet enumerated.

## 7. Statistical outputs

Reuse the `FIG04_STATISTICAL_RECEIPT` schema verbatim (the same 20-field-per-estimand list used
in `fig04-statistical-receipt-20260826.json`: target, biological N, sessions, subjects, areas,
held-out unit, CV/grouping, metric, chance, observed estimate, effect above chance, permutation
count, exact finite-permutation p, correction family, BH q, confidence interval, significant
prevalence, Clopper-Pearson interval, session/subject consistency, timing source, status) so
LFP rows are directly comparable to the existing SPK rows in one receipt, not a separately
designed schema.

## 8. Computational-cost estimate

**Revised (2026-08-26):** the expensive step -- raw-LFP extraction, artifact repair, and
spectrogram computation across the full corpus -- is **already paid for**. `E:/analysis/tfr_arrays/`
holds 970 files, 735 GB, covering all 22 sessions (§1). This battery's actual cost is therefore
dominated by:

- **I/O to load cached `.npz` files** -- each file is a few hundred MB to low GB (735 GB / 970
  files ~ 0.76 GB average); loading the specific session/area/condition cells a given target
  needs (not the whole corpus at once) keeps this bounded and fast relative to recomputing from
  raw NWB.
- **The encoding operator itself**: fold-local scaling, nested PCA/UMAP selection, the
  classifier, and the 999-permutation within-cycle-group null -- the same cost structure as the
  SPK battery, scaled by however many session x area x target cells actually exist post
  §1's coverage enumeration. This is the dominant, non-trivial cost, same as it was for SPK.
- **Freshly computing `p1_onsets_s(f, condition)` per cell** to pair with the cached tensor for
  cycle-grouping (§2's trial-order-alignment note) still requires opening each session's NWB
  file, but only for one small HDF5 dataset read (`intervals/omission_glo_passive`), not a full
  LFP extraction -- cheap relative to the original spectrogram computation.
- No precompute/regeneration of the TFR cache itself is needed -- the earlier version of this
  section's "2+ TB, don't build the cache" warning no longer applies; it was based on the wrong
  (nonexistent) `D:/analysis` path and doesn't describe the real, already-complete `E:/analysis`
  corpus.
- No committed wall-clock estimate is given here -- the honest number requires a one-session
  smoke test (recommended as the first execution step once this spec is accepted) rather than a
  guess, but it should now be materially cheaper than originally estimated. The known
  operational lesson from this session still applies: **do not run this battery concurrently
  with other heavy NWB-reading/UMAP-fitting scripts** -- run sequentially.

## 9. SPK <-> LFP comparability table

| | SPK (Fig04, corrected) | LFP (this spec) |
|---|---|---|
| Sessions used | 21 (leakage-safe encoding matrix) / 4 representative (context, RSA) | 22 in `corpus_manifest.json`; per-area/probe LFP eligibility **not yet enumerated** |
| Subjects | 3 (C31o, V182o, V198o) | Same 3, pending the same per-session area check |
| CV grouping | `jnwb.statistics.detect_trial_cycles` on trial `start_time` | Identical function, identical construction (§5) |
| Timing source | canonical `EPOCH_ONSETS_MS` | Identical constant, sliced from one wide p1-aligned pull rather than re-derived |
| Permutation scheme | 999 perms, within-cycle, `(1+k)/(N_PERM+1)` | Identical |

**This session set is not assumed identical between modalities.** Recommend explicitly
intersecting the SPK-eligible session x area cells against the LFP-resolvable probe x area
blocks (once enumerated) before finalizing which cells populate the matched SPK/LFP matrix,
rather than assuming full overlap — probe-to-area assignment is confirmed session-specific
(`find_probe_for_area`'s docstring: V182o alone puts FEF on different probe letters across
sessions).

## 10. Blockers / confounds

1. **CORRECTED**: the precomputed TFR cache and `channel_area_vector.csv` DO exist -- at
   `E:/analysis/` and `omission/outputs/connectivity/channel_area_vector/channel_area_vector.csv`
   respectively, not the `D:/analysis` / `jnwb.paths` defaults originally checked. Use the real
   paths directly; do not rely on `jnwb.paths.tfr_dir()`/`meta_dir()`/the hardcoded
   `AREA_VEC_PATH` in `precompute_tfr_arrays.py` without an explicit override, since those
   defaults resolve to the wrong (nonexistent) locations in this environment.
2. `corpus_manifest.json`'s `n_sidecar_ok`/`n_tfr_ok`/`n_tfr_files_on_disk` fields are stale
   relative to `E:/analysis` (they read 0 for all 22 sessions despite the real corpus being
   complete) -- do not trust that manifest for TFR/sidecar availability questions without either
   fixing its search root or re-checking the filesystem directly, as done in §1.
3. The trial-order-alignment requirement in §2 (pairing a freshly-computed `p1_onsets_s` call
   with the cached tensor's trial axis) must be enforced with an explicit length/order check at
   load time, not assumed silently.
4. Probe-to-area assignment is confirmed NOT fixed across sessions — must be resolved
   per-session via `find_probe_for_area`/`probe_channel_areas`, never hardcoded or cached
   across sessions.
5. `jnwb.artifact_repair.repair_lfp_trials` is already wired into `extract_epoch_trials`
   (`repair=True`) — must remain enabled, not skipped for convenience.
6. Large single-file NWB sizes plus the earlier-confirmed resource-contention lesson mean this
   battery should run sequentially, not concurrently with other heavy scripts.
7. `Y_omission` (occurrence) has no corrected SPK-side receipt yet either — see the companion
   task below, which Hamm wants closed on the SPK side before Fig04's final render, and which
   this LFP spec's `Y_omission` row is designed to match once both exist.

---

## Companion SPK task (not part of this LFP scope, tracked separately)

Per Hamm: before Fig04 is declared fully sealed, run `Y_omission` (omission occurrence, O vs
S, position-matched, using the identical corrected/cycle-grouped SPK operator already used for
the other four SPK targets) as a fifth SPK cell. Target result, if it holds:

```
Y_omission > 0,   Y_context ~ 0,   Y_expected ~ 0
```

which would give: "SPK signals that an omission occurred, but not detectably why it occurred or
what absent stimulus was expected." Tracked on the pinned todo list, not started.
