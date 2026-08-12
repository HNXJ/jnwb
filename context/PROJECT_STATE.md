# PROJECT_STATE.md — omission-a

**What this file is:** the current scientific and repository state. It answers *what is true
now*, not *what to do*. **It contains no instructions to any agent.** Behavioral rules live in
`CLAUDE.md` and the skills; evidence semantics live in `EVIDENCE_ARCHITECTURE.md`.

**Every number below carries the date it was resolved.** Counts and paths are observations with
a shelf life — re-resolve from `artifacts/data/corpus_manifest.json` rather than citing this
file as authority for a count.

**Last resolved:** 2026-08-12.

---

## 1. Corpus — and an unresolved inconsistency

| Quantity | Value | Source | Resolved |
|---|---|---|---|
| NWB sessions | **22** | `artifacts/data/nwb_catalog.json` (`n_files`) | 2026-08-11 |
| NWB directory | `D:\nwb\omission` | same (`nwb_dir`) | 2026-08-12 |
| Subjects | C31o, V182o, V198o | `session_readiness.csv` | 2026-08-12 |
| Readiness rows / `nwb_ok` | 22 / 22 | `session_readiness.csv` | 2026-08-12 |
| **`tfr_ok`** | **0 of 22** | `session_readiness.csv` | 2026-08-12 |
| **`suite_tfr_ready`** | **0 of 22** | `session_readiness.csv` | 2026-08-12 |
| TFR array files on disk | 970 | `D:\analysis\tfr_arrays` | 2026-08-12 |

### ⚠ OPEN INCONSISTENCY — TFR readiness gate is unsatisfiable

The readiness table reports **no session has a usable TFR product**, while 970 arrays exist on
disk and §4 below reports fitted findings from a 23-session TFR corpus. This is consistent with
the TFR-array rebuild begun 2026-08-11 (`.npz`, real per-area channel subset + 1/f quality
screen, `scripts/precompute_tfr_arrays_v2.py`), but it is not resolved. **Any figure gated on
`tfr_ok` / `suite_tfr_ready` is currently blocked.** Do not resolve this by choosing a source.

### Superseded paths — do not restore

These appear in pre-2026-08-12 documents and **do not exist**:
`D:/analysis/nwb/` · `D:/workspace/data/tfr_arrays/` · `D:/workspace/data/metadata/`.
Earlier corpus statements of "21 NWB sessions" and "1,236 TFR files" describe pre-migration
inventories. `sub-V198o_ses-230629_rec` was added to both inventories by explicit decision on
2026-08-11, which is the 21→22 change.

## 2. Paradigm

A trial is `fx – p1 – d1 – p2 – d2 – p3 – d3 – p4 – d4`. Slots p1–p4 carry stimulus identity;
`fx` and d1–d4 are a gray screen with fixation dot. **Delays and the fixation interval are
visually identical to an omission**, so an omission produces three consecutive identical empty
periods: the omitted slot, flanked by two delays that serve as a within-trial control matched
in everything but expectation.

Twelve conditions: `AAAB AXAB AAXB AAAX BBBA BXBA BBXA BBBX RRRR RXRR RRXR RRRX`. Nine contain
an omission; minimum omitted slot is 2, so a pre-omission delay always exists.

Ten analysis areas: V1, V2, V3, V4, MT, MST, TEO, FST, FEF, PFC. Eleven-to-twelve *labels*
appear in filenames (V3, V3a, V3d separately); ten *analysis regions* is the correct count.

## 3. Superseded claims — do not restore

The 2026-07-27 handout listed these as "protected invariants". They are presentation-layer
constants that no script computes from data.
`scripts/archive_oneoff/compute_empirical_census_and_power.py` holds them as hardcoded dict
literals and writes `artifacts/data/empirical_response_census.json`, consumed by nine
downstream scripts. Receipt: `artifacts/.lab/census_provenance_synthetic_finding_20260728.json`.

| Retracted | Status |
|---|---|
| Primary census 8,597 units; O+ = 421/8,597 = 4.90% | **Synthetic.** Real unit table has 6,655 units. Two-subject screening gave ~20 O+ of ~5,000 (~0.4%). |
| LFP census 8,736 channels; beta modulation 6,771/8,736 = 77.51% | **Synthetic.** Real per-channel census is 9,344 channels. |
| GLMM OR = 3.08, CI [2.51, 3.78], z = 10.726, p = 7.25e-27 | **Never fitted.** |
| Figure 8 alpha 5,816/8,736 = 66.58% | **Synthetic denominator.** |
| "Omission broadly perturbs low-frequency cortical state" | **Directional claim, not supported.** Magnitude holds; direction does not. |
| "Sustained beta elevation during omission" | **Not reproduced** at any level. |

32 of 40 displayed cells in the LFP table were exact whole percentages — probability ≈3×10⁻²⁵
for measured proportions at those denominators.

## 4. Current findings, with receipts

From `outputs/lfp_band_census_v2/` (`receipt.json`, `glmm_results.json`, `glmm_summary.csv`).
Census receipt 2026-07-29: 1,236 TFR files scanned, 909 omission-condition files processed,
18 skipped, 420,480 rows, 23 sessions, median 39 trials/channel.

**Low-frequency power is modulated everywhere.** Mean absolute change in the omitted slot vs
each channel's own baseline: theta 1.06 dB, alpha 1.02, beta 0.79, low gamma 0.55, high gamma
0.42. Low-frequency modulation ≈ 2× gamma.

**The direction is not shared.** Pooled 23-session model (84,096 obs, random intercept per
session; Intercept tests common sign): theta p_BH 0.42, alpha 0.59, beta 0.29, low gamma 1.00,
high gamma 0.94 — null in every band. This tests common *sign*, not presence of modulation.

**Animals disagree in sign.** C31o (8 sessions) fell in every band below 50 Hz (theta −1.58 dB,
q 5.0e−5; alpha −1.36, q 1.0e−4; beta −0.89, q 4.3e−3; low gamma −0.39, q 2.0e−3). V182o (10)
rose in all five. V198o (5) reached significance in no band. The split survives holding area
constant in 7 of 8 testable area×band comparisons.

**V3a/d vs V1 elevation, animal-controlled (corrected 2026-08-05).** Model F — area effects
with subject as an explicit additive fixed effect, session-level, 23 sessions, 3 subjects:
**beta +1.11 dB, p 0.0056, q_BH 0.0147**; **low gamma +0.34 dB, q_BH 0.0147**. Alpha (+0.75,
q 0.129), theta and high gamma do not survive. Two prior bugs fixed: the area-pooling dict
omitted the raw `"V3"` label, and a local BH function inverted rank order.
Receipt: `artifacts/.lab/v3ad_beta_glmm_two_bugs_fixed_20260805.json`.

## 5. Structural facts that constrain inference

- **Area and subject are confounded corpus-wide.** No area was recorded in all three animals.
  The area×subject graph is nevertheless connected (every area in ≥2 subjects), so additive
  effects are jointly identifiable.
- **The area partition is an assumption.** 27 of 51 probes span multiple areas; in 26 the
  boundary is channel 64 of 128, and the one three-area probe splits at 42 and 85 — uniform
  divisions in listing order. Labels are disjoint (which removes aliasing) but this does not
  establish that a channel lies in the area its label names. **V3a and V3d pool to V3.**
- **Putative layer** comes from the vFLIP2 alpha/beta-to-gamma crossover and returns `na` for
  roughly two thirds of channels. Coverage is also imbalanced by animal
  (Kruskal-Wallis H = 12.80, P = 0.0017) and ~3× by area. A laminar model fitted only where the
  crossover converged reports a property of the estimator, not of cortex.
- **All 6,655 screened units carry `layer = Superficial`** in the classification table. Any
  laminar statement drawn from that field describes a default.
- **The unit classifier is one-sided.** 3,457 of 6,655 units have a negative omission effect;
  none reaches p = 0.05.
- **Four passes report four different O+ counts** (386, 19, 7, and a retracted 421). Confirm
  which script and criteria produced any figure before quoting it.

## 6. Blocked and gated

| Item | Status |
|---|---|
| **Figure 3 — unit census** | O+ prevalence on three subjects is the headline number still owed. Synthetic lineage must not be reused. |
| **Figure 4 — identity decoding** | `_v2` tables exist but the random-CV result is confounded; the cycle-deconfounded estimate is ≈ chance. **Do not promote the 0.601 accuracy.** Requires: p4 label-fix rerun with provenance, grouped/cycle-safe CV, corpus-scale permutation null, no hardcoded values in panels, a stats receipt per panel, and headline wording determined from the deconfounded result even if null. |
| **Figure 5** | Preserve the distinction between descriptive channel-level effects and session-level Model F. |
| **Figure 6** | Empirical ratio-based products, current bands, area segmentation verified before averaging. A heatmap is descriptive without a session-level window/band receipt. |
| **Figure 7** | Establish the statistic and its sampling unit before interpreting coupling as routing. Matched-count resampling if spike counts differ between conditions. |
| **All TFR figures** | Blocked by the §1 readiness inconsistency. |
| **Laminar sign question** | Blocked on vFLIP coverage. |

## 7. Open questions

1. O+ prevalence on three subjects.
2. Two-window estimates per band × area × layer.
3. Does laminar sampling explain the sign inconsistency?
4. Methods gaps absent from every source: surgery/implant, full stimulus specification,
   fixation and reward schedule, spike-sorting parameters and quality tiers, CSD computation.
5. Author list; three reference defects (Wacongne 2011 journal/DOI, Bastos 2015 DOI suffix,
   Rao & Ballard 1999 cited for a Bastos 2012 laminar claim).
6. Graph health — **re-derive, do not inherit.** The last recorded audit (330 nodes, ~87 with
   receipts against ~276 `confirmed`, 40 edges to a nonexistent `mission` node) is stale; the
   graph now holds 395 JSON nodes.

## 8. Manuscript lineage

Markdown drafts are the live line and carry no number from the DOCX. `context/drafts/
omission-a-draft-v3.md` is current. The DOCX lineage carries the §3 synthetic numbers and is
retained for history; `omission-2026-manuscript-master.docx` is the original and is not
overwritten. A Word lock file has been observed on the master — check before any write.

## 9. Model choice for omission-a

Not fixed by doctrine. The design supports session as a grouping factor; three subjects cannot
identify a subject random-effect variance, so subject enters by stratification or as an explicit
fixed term. Whether the paper reports a mixed model is a project decision recorded here, and it
is currently **unsettled**: earlier material named a GLMM backbone while other material deferred
GLMM to a later paper.
