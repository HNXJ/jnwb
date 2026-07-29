# Unit classification inventory

Version: 2026-07-28
Status: generated inventory, not hand-edited
Truth status: `truth_safe_verified`; regenerate with `python scripts/build_classification_inventory.py`.

## 1. Four passes disagree on how many O+ units exist

| pass | O+ | screened | prevalence % | criteria recorded |
|---|---|---|---|---|
| `grand_oplus_units.csv` | 386 | 6655 | 5.80 | partly: template correlation and permutation p |
| `grand_template_classifications.csv` | 19 | 2778 | 0.68 | no |
| sidecar `units.csv` `display_class` | 7 | 6655 | 0.11 | no |
| `oplusplus_census.json` headline | 421 | 8597 | 4.90 | RETRACTED, hardcoded literal |

The manuscript defines O+ by a Wilcoxon rank-sum contrast at p < 0.01, requiring the omission
rate to exceed both the stimulus rate and the baseline rate. **None of these passes is
documented as having applied that definition.** The number quoted in the manuscript has to come
from a run of the stated criteria, and until then the prevalence remains owed.

## 2. O+ prevalence per area, with denominators

| area | O+ | screened | prevalence % | 95% CI |
|---|---|---|---|---|
| FEF | 62 | 771 | 8.04 | 6.22-10.19 |
| V2 | 46 | 588 | 7.82 | 5.78-10.30 |
| TEO | 44 | 575 | 7.65 | 5.61-10.14 |
| V4 | 57 | 776 | 7.35 | 5.61-9.41 |
| V3a/d | 51 | 911 | 5.60 | 4.20-7.30 |
| V1 | 34 | 628 | 5.41 | 3.78-7.48 |
| PFC | 65 | 1342 | 4.84 | 3.76-6.13 |
| MST | 10 | 290 | 3.45 | 1.67-6.25 |
| MT | 17 | 696 | 2.44 | 1.43-3.88 |
| FST | 0 | 78 | 0.00 | 0.00-4.62 |

**There is no higher-order enrichment.** FEF and PFC together give 127/2113 = 6.01 per
cent; V1 and V2 give 80/1216 = 6.58 per cent. Fisher exact P = 0.551.

The impression of frontal concentration comes from raw counts. PFC and FEF contribute the
largest numbers of O+ units because they contribute the largest numbers of units: PFC alone was
screened at 1,342 units, more than twice V1. Normalised by what was recorded,
PFC sits below V1. The ordering that survives normalisation is not hierarchical -- FEF, V2, TEO
and V4 are high, MT, MST and FST are low.

## 3. Tightening the threshold does not move units frontally

The O++ set is drawn from the O+ pool by requiring a higher template correlation and a
significant permutation test, **and by requiring the unit to lie in FEF or PFC**. Removing only
the area requirement and varying the correlation threshold gives:

| correlation threshold | units | FEF | PFC | % FEF/PFC | largest other area |
|---|---|---|---|---|---|
| r >= 0.50 | 256 | 39 | 43 | 32.00 | V4 (41) |
| r >= 0.60 | 135 | 18 | 21 | 28.90 | V4 (26) |
| r >= 0.70 | 55 | 7 | 11 | 32.70 | V4 (11) |
| r >= 0.80 | 20 | 2 | 6 | 40.00 | V4 (5) |

The O+ pool's own FEF/PFC share is 32.9 per cent. Tightening leaves that share flat, and at
the threshold the census actually uses it sits below the base rate. At `r >= 0.60` with
`p <= 0.05`, 135 units qualify across nine areas; the census kept the
39 in FEF and PFC and discarded the rest, of which
V4 was the largest group.

**So the frontal purity of the O++ set is imposed by its definition, not produced by stricter
selection.** It cannot be cited as evidence that omission signalling favours frontal cortex.

## 4. The layer label is a constant

All 6,655 screened units carry `layer = Superficial`. Every O+ and O++ unit is therefore
superficial by default rather than by measurement, and no laminar statement can rest on this
field.

## 5. What can be said

- O+ units are a small minority in every area, between 0 and roughly 8 per cent, with the exact
  binomial intervals given above.
- Prevalence varies about threefold across areas, and that variation does not follow the visual
  hierarchy.
- 39 units satisfy the published O++ criteria including the area requirement; 135
  satisfy the same statistical criteria without it.
