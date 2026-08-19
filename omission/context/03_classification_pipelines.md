# 03 — Classification Pipelines (S+/S−/O+/O++)

Generated 2026-08-17. **This is the single most fragmented area of the repo.** There are (at
least) four methodologically distinct generations of unit-response classification, each with its
own script, table, and definition of the same-named classes. All counts below were read directly
from the live CSVs (`pandas .shape`/`.value_counts()`), not from docstrings, unless marked
"per receipt/docstring." **Every citation of an S+/S−/O+/O++ count anywhere — prose, a figure
caption, a manuscript draft — must name which generation and which population it comes from.**
Same-named columns across these tables are not the same field.

## The four generations, at a glance

| Gen | Classes | Script | Table | Method (short) | Population |
|---|---|---|---|---|---|
| **Legacy** | S+/S++/S−/S−− | `scripts/archive_oneoff/find_all_s_and_o_units.py` | `outputs/classification/grand_s_and_o_units.csv` | 27-elem (9 epoch × 3 R-family cond) rate vector, Pearson r vs fixed template, **template has nonzero weight at fx** | 15 sessions, `quality==1.0` only |
| **Legacy (Q1)** | O+/O++/O−/O−− | `scripts/classify_omission_units_grand.py` | `outputs/classification/omission_grand_units.csv` | omitted slot must peak/trough vs **both** flanking delays (conjunction), displacement-shuffle null, BH-FDR | 22 sessions, all units |
| **Template-corr (current)** | O++ only | `fig03_unit_census.py::attach_template_corr_oplusplus` (inline, not persisted) | none — computed fresh each run | Pearson r ≥ 0.65 vs O+/O*+ templates, area-restricted to V4/TEO/FEF/PFC | subset of `grand_oplus_units.csv`'s 359-unit candidate pool |
| **Modern native (`unit_classification.classify_unit`)** | S+/S−/O+/O++ | `scripts/classify_units_omission_inclusion_v1.py` | `outputs/classification/unit_inclusion_v1.csv` | S+/S−: own-trial fx-baseline pooled shuffle test (not template-based, no fx-privileging bug). O+/O++: 3-way shuffle vs local baseline + matched control + delay mean | 22 sessions, all quality tiers |
| **S1 (new, additive)** | O+ inclusion only | `omission/jnwb_ext/unit_inclusion.py` → same runner as above | `unit_inclusion_v1.csv::is_omission_inclusion_new` | paired fire-probability (≥1 spike) vs duration-matched local pre-omission baseline, shuffle+BH-FDR | 22 sessions, all quality tiers |

## 1. Legacy generation

### 1a. S+/S++/S−/S−− — `scripts/archive_oneoff/find_all_s_and_o_units.py`

27-element concatenated rate vector (9 epochs × 3 R-family conditions RXRR/RRXR/RRRX), Pearson
correlation against a **fixed template**. Templates place nonzero weight at the **fx epoch** for
both S+ (fx=1) and S− (fx=2, highest) templates — **this is the exact fixation-privileging
template bug** referenced by `omission/jnwb_ext/unit_inclusion.py`'s own docstring (see S1 section below).

- S+: p<0.05 (5000-shuffle perm) AND r>0.3. S++: p<0.01 AND r>0.3. S−/S−−: mirror at same
  thresholds. O+ (also computed here, not the primary omission source): p<0.01 AND r>0.3,
  gated on peak-dominance (≥2/3 conditions peak at omission slot). O++: p<0.001 AND r>0.3, same
  gates.
- Pre-filters: `quality==1.0`, `firing_rate>=0.5 Hz`, Spearman drift `|rho|<0.45`, ≥20 trials.
- Live shape: **2,921 rows × 20 cols, 15 unique sessions.**
- Live counts: `is_Splus=887, is_Splus_double(S++)=744, is_Sminus=499, is_Sminus_double(S--)=356,
  is_Oplus=68, is_Oplus_double(O++)=16`.
- **Still actively consumed, not dead**, despite the known fx bug: `fig03_unit_census.py`
  (legacy-screened comparison panels, `attach_legacy()`), `fig02_spiking_exemplar_rasters.py`
  (exemplar picker — hardcoded stale `D:/workspace/omission/...` path rather than `jnwb.paths`,
  a path-convention inconsistency, not confirmed broken), `scripts/build_unit_feature_table.py`,
  `scripts/classify_units_omission_inclusion_v1.py` (only for the old-vs-new comparison columns,
  never for is_s_plus/is_s_minus), `fit_s_plus_onset_latency_s1.py`, `fit_class_onset_latency.py`,
  `extract_population_firing_lfp_power_corr.py`, plus three `scripts/historical/confounded/`
  decoders (flagged retired).

### 1b. O+/O++/O−/O−− (Q1 peak+ramp) — `scripts/classify_omission_units_grand.py`

The omitted slot must peak/trough **vs both flanking delays separately** (conjunction — removes
monotonic-decay and stimulus-offset confounds). Null: displace all 3 windows together by
D~U(100,200)ms forward-only, 1000 shuffles, seed 42. BH-FDR (`scipy.false_discovery_control`)
across units, **alpha=0.05** (raised from 0.025 on 2026-08-13 per direct Hamm request — a
corpus-wide effect on every `omission_class`/`knows_when`/`knows_what`/`after_class` consumer,
per the script's own code comment).

- O++ = up (sig+dir vs both flanks) AND ramp-up sig. O+ = up but ramp not sig. O−− = down AND
  ramp-down sig. O− = down but ramp not sig. ns = neither.
- **Also computes a second, not-corpus-adopted `omission_class_v2`** (omission-reporter
  criteria, added 2026-08-11, own separate BH-FDR family): O+v2 = peak in
  `[p_x onset, d_x end]` significantly greater than the mean of the preceding delay; O++v2 = O+v2
  AND that peak beats the best-competing epoch peak in the trial. **Explicitly flagged in the
  script's own docstring as additional, not a replacement** — `omission_class` (v1/Q1) remains
  the corpus default.
- Live shape: **9,056 rows × 49 cols, 22 unique sessions.**
- Live `omission_class` counts: `ns=8573, O+=265, O-=203, O++=12, O--=3`.
- Live `omission_class_v2` counts: `ns=7827, O+=1207, O++=22` — **nearly 5× the Q1 O+ count on
  the same underlying table**, same units, different test design.
- Population: all units (no quality/rate pre-filter), across all 22 NWB files.
- Consumers: `fig03_unit_census.py` (panels A–E base classifier — the template-corr panel F is
  the one exception), `fig03_supp_area_composition_battery.py`, `fig02_spiking_exemplar_rasters.py`,
  `scripts/build_unified_class_census.py` (O−/O−− source), `build_unit_feature_table.py`,
  `fit_all_classes_onset_latency_per_unit.py`, `fit_class_onset_latency.py`,
  `extract_spike_lfp_coupling.py` (+v2), `extract_within_session_spk_lfp_sliding_corr.py`,
  `extract_within_session_spk_spk_sliding_corr.py`, `extract_population_firing_lfp_power_corr.py`
  (feeds `outputs/population_firing_lfp_power_corr/`, which `fig07_lfp_spike_coupling.py` reads
  — confirming fig07 transitively depends on `omission_class`), `extract_condition_spike_trials.py`,
  `compute_unit_trial_presence.py`, `compute_omission_likelihood_grand_table.py`,
  `reclassify_omission_units_alpha.py`.
- **Not confirmed for fig05**: `fig05_v1_area_hierarchy_glmm.py` reads
  `outputs/lfp_band_census_v2/glmm_summary.csv` and `outputs/lfp_band_census_stim/glmm_summary.csv`
  directly, not any unit-classification CSV — no direct grep hit for `omission_class` in fig05's
  own file. Whether fig05's inputs trace back to `omission_class` further upstream was not traced
  by this audit.

## 2. Template-correlation O++ generation

### 2a. Candidate pool — `scripts/archive_oneoff/find_all_oplus_units.py`

Same 27-element vector method as 1a, but with an O+ template (one-hot at omission slot) and O*+
"ramper" template (two-hot: omission slot + following delay). Pearson r computed; permutation
test (1000 shuffles) run **only if r>0.40**; row kept if p<0.05. Peak-dominance gate applied only
to the O+ pattern. Post-filter: `overall_rate>=0.5 Hz AND quality==1.0`.

- Writes `outputs/classification/grand_oplus_units.csv`. Live shape: **435 rows × 12 cols, 21
  sessions.** `pattern_type`: O*+=348 rows, O+=87 rows — **row count, not unit count**; a unit
  can appear twice (once per pattern). **Unique units = 359.**
- This is the shared candidate pool both the superseded (2b) and current (2c) O++ definitions
  read from — the pool itself is not superseded, only what's built on top of it.

### 2b. SUPERSEDED — `scripts/build_oplusplus_census.py` → `grand_oplusplus_units.csv`

Reads the 2a candidate pool, calls `omission.jnwb_ext.unit_classification.assign_o_plusplus_from_template_table`
with `OPlusPlusTemplateConfig(require_higher_order=False)` — i.e. **corpus-wide, no area
restriction** (the dataclass's FEF/PFC default gate was explicitly turned off 2026-08-13 per
direct Hamm request, treating FEF/PFC as a validation hint rather than a hard scope at the time).
Threshold: `min_mean_correlation=0.60, max_permutation_pval=0.05` (the module's own defaults).

- Live shape: **144 rows × 14 cols — row count, not unit count: unique units = 129**, confirming
  the double-count-across-patterns bug (`artifacts/.lab/bug-oplus-row-vs-unit-count-inflation-20260817.json`).
  Area breakdown (rows): V4=26, FEF=23, PFC=23, TEO=19, V2=17, V1=12, V3=8, MT=7, V3d=5, MST=2,
  V3a=2 — **spans all 11 areas**, despite the script's own module docstring opening line stating
  "O++ = FEF/PFC units..." (stale docstring vs. actual `require_higher_order=False` behavior —
  a real doc/code mismatch, not fixed by this audit).
- **Status: explicitly superseded 2026-08-17** by `fig03_unit_census.py`'s inline computation
  (2c), per that file's own block comment (lines 76-98) and function docstring (175-188): the
  r≥0.60/no-area design was found to (i) double-count units and (ii) admit **55–71%
  contamination from S−/S−− (suppressed) units** whose Pearson correlation to the O+ template
  survives despite no real above-baseline omission response (correlation is scale/sign-invariant
  to the unit's own absolute rate) —
  `artifacts/.lab/bug-oplus-candidate-pool-suppressed-unit-contamination-20260817.json`.
- `grand_oplusplus_units.csv` is now effectively an **orphaned artifact on disk**: only its own
  writer script (`build_oplusplus_census.py`) and one stale/unmaintained archived script
  (`build_classification_inventory.py`, hardcoded dead `D:/workspace/omission` path, reads two
  CSVs not found anywhere else in the repo) still reference it. `build_oplusplus_census.py`
  would still regenerate it if re-run — nothing prevents that, but nothing currently reads the
  output either.

### 2c. CURRENT — `fig03_unit_census.py::attach_template_corr_oplusplus` (inline, not persisted)

Correction history (from this session's own code comments, 2026-08-17):

1. **2026-08-13** (direct Hamm request): switch fig03 panel F's grand-average trace from
   `omission_class=="O++"` (the Q1 method, only 12-17 units, visually did not resemble the
   manually-observed FEF/PFC O++ template) to the template-correlation classifier.
2. **2026-08-17**: found the precomputed `grand_oplusplus_units.csv` (2b) both double-counts
   units and is 55-71% contaminated by suppressed units at r≥0.60.
3. **Fix**: raise threshold to **r≥0.65**, dedupe to one row per unit (not per pattern) before
   counting, restrict to **`OPLUSPLUS_AREAS = (V4, TEO, FEF, PFC)`** — this area restriction is
   now stated as causally tested this session (RRRR-vs-omission-condition divergence before the
   40ms causal floor, plus a peak-after/gradual-decay-vs-sharp-cliff falsifier), passing only in
   these four areas — `artifacts/.lab/finding-oplus-area-restriction-causally-validated-20260817.json`.
4. Result: **52 unique units** in V4/TEO/FEF/PFC — matches Hamm's own domain expectation
   ("at least 50 neurons, all in V4/TEO/FEF/PFC").
5. **Explicitly scoped to fig03 only**: `omission_class` (Q1) is unchanged and remains the
   classifier used everywhere else in the repo (fig05 GLMM inputs where applicable, fig07,
   fig02) — this switch does not touch `omission_class` corpus-wide, per explicit Hamm
   direction.

Recomputed live in this audit from `grand_oplus_units.csv` (r≥0.65, p≤0.05, deduped): **84
unique candidate units corpus-wide; 52 unique units after the V4/TEO/FEF/PFC restriction** —
matches the code comments exactly. Denominator (`is_tc_candidate`, r>0.40 prefilter, any area) =
all 359 unique candidate units. Two flags emitted: `is_tc_candidate` (denominator, corpus-wide)
and `is_oplusplus_tc` (r≥0.65 AND area-restricted numerator). **Not written to a CSV** — computed
fresh each run and joined in-memory; no persisted table exists for this definition beyond the
function itself and its reproduced 52-unit count.

## 3. S1 — `omission/jnwb_ext/unit_inclusion.py` → `scripts/classify_units_omission_inclusion_v1.py`

**What S1 actually fixes** (per its own module docstring): the legacy `find_all_s_and_o_units.py`
bug where the O+ template is zero at the fx epoch, so a unit firing strongly during both
fixation and omission scores poorly. **`omission.jnwb_ext.unit_classification`'s own O+ path does not use fx
and is not the buggy mechanism — S1 does not replace it, only adds a second, independent
criterion alongside it.**

Method (`classify_unit_omission_inclusion`): paired binary "fires ≥1 spike" indicator, P(fire |
omission-slot window) vs P(fire | immediately-preceding, **duration-matched** pre-omission
window, gapped by `OM_BASE_GAP_MS=50ms`). Sign-flip shuffle null on the paired difference (2000
shuffles), one-sided. Risk-difference 95% CI via paired bootstrap (2000 resamples, distinct RNG
stream from the shuffle test). BH-FDR applied **per-session**. Inclusion: `q_fire_shuffle<0.05
AND risk_difference>0 AND n_omission_trials>=8`.

**v1→v2 history** (in the module docstring): the first cut reused `unit_classification`'s own
`OM_BASE_LEAD_MS`/`OM_BASE_GAP_MS` fixed 200ms baseline window — wrong for a fire-probability
comparison because `P(fire)=1-exp(-rate*duration)` mechanically favors the longer 531ms omission
window; measured to inflate inclusion to **73.7%** on a smoke-test session against a <1% target.
Fixed (v2, current) by duration-matching the baseline window to 531ms.

**Runner** (`scripts/classify_units_omission_inclusion_v1.py`) does two things per unit: (1) runs
the modern `omission.jnwb_ext.unit_classification.classify_unit` **unmodified** → `is_s_plus`, `is_s_minus`,
`is_o_plus`, `is_o_plusplus`, `display_class` (see §4); (2) runs
`omission.jnwb_ext.unit_inclusion.classify_unit_omission_inclusion` → `is_omission_inclusion_new`. Also joins
`grand_s_and_o_units.csv`'s `is_Oplus` as `is_o_plus_old_templatecorr` for an explicit
old-vs-new gained/lost/unchanged transition table.

**⚠ Correction to a common mislabel**: the `is_s_plus`/`is_s_minus` columns in
`unit_inclusion_v1.csv` do **not** come from an "S1 S+/S− classifier" — no such thing exists.
They come straight from `omission.jnwb_ext.unit_classification.classify_unit`/`_assign_labels` (§4), run
per-session inside this same script. S1's likelihood-of-firing method produces **only**
`is_omission_inclusion_new` (an O+-only inclusion flag). `scripts/build_unified_class_census.py`'s
own docstring line — *"S+/S− (local-baseline, likelihood-of-firing): ... This IS the NWB-scanning
step for S+/S−; see omission/jnwb_ext/unit_inclusion.py for the classifier itself"* — is misleading relative
to the actual code path traced here; flagged in doc09 as a documentation defect worth fixing
before citing S+/S− as "S1-derived."

- Writes `outputs/classification/unit_inclusion_v1.csv` (+ `_stats.json` + `_manifest.json`).
  Live shape: **9,061 rows × 88 cols, 22 sessions.**
- Full-table live counts: `is_s_plus=1795, is_s_minus=1077, is_o_plus=31, is_o_plusplus=5,
  is_omission_inclusion_new=319, is_o_plus_old_templatecorr=68`.
- `quality_tier` value_counts: `mua=4257, unstable=4026, stable=778`.
- **Restricted to non-mua** (stable+unstable) — the population actually cited downstream:
  n=4804, `is_s_plus=1211, is_s_minus=673` (matches the S1 planning brief exactly).
- Population: all 22 sessions with `nwb_ok==True`, every unit with ≥1 spike — no quality
  pre-filter at collection time; `quality_tier` is a post-hoc column for downstream filtering.
- Consumers: `scripts/build_unified_class_census.py` (S+/S− source, filtered to
  stable+unstable), `fig03_supp_area_composition_battery.py`,
  `S5_onset_latency_hierarchy_spk.py`, `S2_population_responses_by_class.py`,
  `fit_all_classes_onset_latency_per_unit.py`, `fit_s_plus_onset_latency_s1_per_unit.py`,
  `fit_s_plus_onset_latency_s1.py`.

## 4. `omission/jnwb_ext/unit_classification.py::classify_unit` — the modern native classifier

**Not dead code** — directly imported in 29 files across `scripts/`, `context/figures/`, and
`tests/`, including the S1 runner itself.

Fully independent S+/S−/O+/O++ logic, distinct from all three generations above:

- **S+/S−** (lines 339-437, 466-477): pools every `(condition, slot)` where the slot is a real
  stimulus against **that trial's own fx baseline** `[-500,0]ms`. Sign-flip shuffle null (2000
  shuffles), two effect floors (`min_abs_stim_effect_hz=0.5`,
  `min_stim_rate_for_s_plus_hz=0.5`/`min_baseline_for_s_minus_hz=3.5`), BH-FDR at alpha=0.05.
  This **is** the fixation-bug-fixed style of comparison for S+/S− (never scores against a
  template that privileges fx) — but it predates and is separate from `unit_inclusion.py`'s S1
  work, which only added a new, independent O+ criterion. See the fixation-baseline
  terminology note below.
- **O+** (lines 479-489): omission slot must be significantly above **(i)** its own local
  pre-omission baseline, **(ii)** the matched full-sequence control condition's same slot, AND
  **(iii)** the mean of all four delay epochs — three separate shuffle tests, all clear
  `q<alpha_omission (0.01)` with `effect>=min_omission_effect_hz (2.0 Hz)`, `n>=8` omission
  events.
- **O++** (lines 491-505): inclusive O+ AND a nested random-control (R-family only) robustness
  check — ≥2 of 3 R-family slots individually significant (p<0.01, effect≥4.0Hz), pooled
  R-family omission-vs-control also significant, AND the original om_vs_base/om_vs_ctrl/
  om_vs_delay effects all ≥4.0 Hz (stricter than O+'s 2.0 Hz floor).
- This is a **fourth**, methodologically distinct O+/O++ design — never a peak/trough
  conjunction (Q1), never a Pearson correlation against a fixed template (template-corr). It's
  the only one of the four O+ methods testing against three separate reference conditions
  simultaneously.
- **Houses two unrelated O++ definitions internally**: its own native shuffle-based one (via
  `classify_unit`/`_assign_labels`) and a separate wrapper around the template-correlation
  candidate table (`assign_o_plusplus_from_template_table`, used only by the now-superseded
  `build_oplusplus_census.py`, §2b).
- Downstream use: feeds `unit_inclusion_v1.csv` directly (§3) and is used standalone by many
  `extract_*`/`compute_*` pipeline scripts — the workhorse classifier for anything not
  specifically reproducing the legacy/template-corr/Q1 methods for comparison.

### Fixation-baseline terminology — a precision note, not a contradiction

`classify_unit`'s S+/S− test **is** fixation-baseline-referenced (`stim_effect_hz` = stim rate −
fx-window rate) — this is standard/expected baseline normalization for a stimulus-response test,
**not** the "fixation-privileging bug" the S1/legacy-fix language targets. That bug was specific
to the archived template-correlation classifier's one-hot 9-epoch template carrying a nonzero
weight at fx for the O+ pattern (§1a, §3). Two different things are informally bundled under "the
fixation bug" in casual conversation — keep them separate when writing about either.

## 5. Reconciliation layer — `scripts/build_unified_class_census.py`

Writes `outputs/classification/unified_class_census_v1.csv` + `_summary.json`. **Pure
aggregation — does not rescan NWB.** Stitches together three already-computed, independently-run
outputs:

1. S+/S−: `unit_inclusion_v1.csv`, filtered to non-mua → **1211 S+, 673 S−** (matches §3 exactly).
2. O+/O++: `grand_oplus_units.csv`, deduped, O++ = area∈{V4,TEO,FEF,PFC} & r≥0.65 & p≤0.05
   (same as §2c) → **52 O++, 307 O+** (excl. O++; 359 − 52 = 307, matches this audit's own
   recomputation).
3. O−/O−−: `omission_grand_units.csv`, `omission_class` (Q1) → **203 O−, 3 O−−** (matches §1b
   exactly).

The script's own docstring **explicitly refuses to report "Other" or a single grand total**,
because these are three methodologically different, non-overlapping-by-design screened
populations, not five slices of one population — stated as a caveat in-file, not glossed over.
Only known consumer of `unified_class_census_v1.csv` is the script itself; a terminal reporting
artifact, not yet a pipeline input elsewhere.

## Flagged discrepancies — same nominal class, incompatible counts

**O++**, four incompatible numbers, none a subset of another by construction:

| Source | Count | Scope |
|---|---|---|
| Q1 peak+ramp (`omission_class=="O++"`) | 12 | 22 sessions, all units, no area gate |
| Q1v2 omission-reporter (`omission_class_v2=="O++"`) | 22 | same table, different (non-default) criteria |
| Template-corr, superseded (r≥0.60, no area gate) | 129 unique (144 rows) | subset of 359-unit candidate pool |
| Template-corr, current (r≥0.65, V4/TEO/FEF/PFC) | **52** | subset of the same pool — this is the number to cite going forward for fig03 |

**O+**, six divergent numbers — every citation must name which:

| Source | Count |
|---|---|
| Q1 (`omission_class=="O+"`) | 265 |
| Q1v2 (`omission_class_v2=="O+"`) | 1207 |
| Legacy template-corr (`grand_s_and_o_units.csv`, 15 sessions) | 68 |
| Template-corr candidate pool (r>0.40 prefilter) | 359 total, or 307 excl. O++ at r≥0.65/area-restricted |
| Modern native (`classify_unit`, full corpus) | 31 |
| S1 fire-probability (`is_omission_inclusion_new`) | 319 — methodologically distinct (paired fire-probability, not rate) |

**S+/S−** disagree by classifier design and population, less dramatically:

| Source | S+ | S− | Population |
|---|---|---|---|
| Legacy (fx-privileging template) | 887 | 499 | 15 sessions, `quality==1.0` only |
| Modern (`classify_unit`, full corpus) | 1795 | 1077 | 22 sessions, all quality tiers |
| Modern, non-mua (cited downstream) | **1211** | **673** | 22 sessions, non-mua |

**Stale docstring**: `build_oplusplus_census.py`'s module docstring opening line still says
"O++ = FEF/PFC units..." while `main()` sets `require_higher_order=False` — the actual output
spans all 11 areas. Not fixed by this audit; a low-risk one-line docstring correction, flagged
in doc09.
