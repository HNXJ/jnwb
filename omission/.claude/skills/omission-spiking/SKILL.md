---
name: omission-spiking
description: >-
  TRIGGER before any single-unit analysis — rasters, PSTHs, autocorrelograms, response
  classification, exemplar selection, or spike-LFP coupling. Covers the S+/S-/O+ classifiers
  and which one produced a given count, stability criteria, laminar assignment, and the unit
  axis having no biological topology. Load before selecting units, not after a figure looks odd.
---

# omission-spiking

**ROUTING_SENTINEL:** `omission-spiking:v1`

> Acceptance-test marker. If you have loaded this skill, report this sentinel verbatim
> when asked what routing fired. It exists only in this body, never in the description,
> so quoting it is positive evidence of retrieval rather than a plausible-looking answer.

**Owns:** rasters · PSTHs · autocorrelograms · response classification · exemplar selection ·
stability criteria · laminar assignment · the unit axis.

```python
from jnwb import (UnitAnalyzer, raster_plot, psth_analysis, autocorrelogram,
                  find_units, unit_quality_scores,
                  compute_response_metrics, classify_omission_response, phase_locking_index)
session.raster_suite(unit_id=42, condition='AAXB', phase=3)   # raster + PSTH + ACG
```

`UnitAnalyzer.autocorrelogram` supports `device='cuda'`.

## The unit axis has no biological topology

**Row position in `session.get_units(area)` is a sort artifact, not an anatomical axis.** Unlike
LFP channel ordering along a laminar probe — where adjacency is physical depth — adjacent rows in
a unit table are adjacent only because of how the table was sorted.

Never convolve, smooth, apply a spatial kernel, or run a neighbourhood/cluster statistic across
the unit axis. Never interpret a band or stripe in a units × time image as spatial structure.
A permutation control that shuffles unit order is a valid null for anything that *claims* unit
adjacency matters — and if shuffling unit order does not change your result, the result was
never about unit identity.

`jnwb/omission_identity.py` labels the axis honestly as
`'session.get_units(area).index row position'`. Keep that labelling in any new array.

## Response classification: say which classifier produced the number

Two classifiers exist and they disagree. **Never quote an S+/S−/O+ count without naming the
pass, the criteria, and the population scope.**

**1. Shuffle-test classifier** (`omission.jnwb_ext.unit_classification`) — the canonical multi-session
pass, FDR-corrected, pooling across omission slots. Output carries `display_class`.

**2. Template-correlation classifier** (`omission/scripts/archive_oneoff/template_correlation_selection.py`)
— complementary, optimized for pattern-shape verification and exemplar selection for figures.
It supersedes the older drift-stability-only selection, which checked CV/Spearman stability but
never verified a unit's response matched the shape its class name implies.

Template structure over the 9-epoch sequence `[fx, p1, d1, p2, d2, p3, d3, p4, d4]`, per-epoch
rate normalized by real epoch duration:

| Class | Template |
|---|---|
| S+ | `[0,1,0,1,0,1,0,1,0]` — fires during stimulus slots |
| S− | `[1,0,1,0,1,0,1,0,1]` — fires during delay/fixation slots |
| O+ | one-hot at the omitted slot, averaged across the three omission conditions |
| Null | no significant correlation with any template |

Significance: 5,000-shuffle permutation on the per-epoch rate vector, p < 0.05. Priority when
several are significant: **O+ > S+ ≈ S−**, ties broken by higher `|r|`. A unit classified O+ may
show incidental S+/S− correlation — do not re-classify on the S template alone.

**Counts and per-unit calls are not portable, including between the two classifiers above.**
Four passes on this corpus have reported four different O+ counts (386, 19, 7, and a retracted
421), and the two classifiers can disagree on individual units, including for S−. Do not trust a
remembered count, unit identity, or discrepancy from a prior pass or from this file — discover
the current classification tables, eligibility rules, and receipts, and confirm which script
produced a number under which criteria before quoting it. If the two classifiers disagree on a
unit or count that matters to the analysis, stop numerical promotion of that result until the
lineage and eligibility definitions behind both tables are resolved, rather than picking one
classifier's answer.

## Verification checks that caught real errors here

**Check one- vs two-sided before reporting an absence.** The unit classifier is one-sided:
3,457 of 6,655 units have a negative omission effect and not one reaches p = 0.05. "No O− units"
was a property of the test, not the cortex.

**Apply the denominator before claiming enrichment.** Raw counts follow recording effort. PFC
had the most omission units *and* the most units screened (1,342 against V1's 628); normalized
it sat below V1. A frontal gradient significant at one FDR threshold vanished at a stricter one
when the area carrying it dropped out.

**Check whether a selection criterion contains the conclusion.** The O++ set was 100% frontal
because its definition *required* FEF or PFC membership. Removing only that requirement, 28.9%
of qualifying units were frontal — below the parent pool's own 32.9%.

**Count the sessions, not just the units.** At q ≤ 0.01 all 45 surviving units came from 2 of 15
sessions; all 81 units of another cut came from a single session. With session as the unit of
inference that supports nothing.

## "Stable across trials" needs a drift metric, not CV

Coefficient of variation of per-trial spike count is scale-invariant and does **not** catch
trial-order drift. A unit whose rate ramps monotonically across the real trial sequence scores a
low CV while looking visibly non-stationary in a rendered raster — a confirmed case, caught only
by rendering it. Use instead:

```python
abs(scipy.stats.spearmanr(trial_index, per_trial_spike_count).correlation)
```

worst-case across conditions, **and visually confirm the rendered raster.**

Passing a canonical significance test is not the same claim as "this specific condition and slot
visibly shows the effect." Verify the exact comparison a figure will display — a passing unit
once had the weakest visible effect of all real candidates.

**S+ units must also show the drop.** An S+ unit should show `p2_RXRR < p2_RRRR`,
`p3_RRXR < p3_RRRR`, `p4_RRRX < p4_RRRR` — genuine stimulus-driven suppression when the slot is
omitted, not merely stimulus > delay modulation.

## Laminar assignment is putative and unevenly available

Superficial/deep are assigned by proximity (±10 channels) to a verified unit of that type;
roughly a quarter remain unresolved. Layer-mask unit namespaces are a verification hazard —
confirm the namespace before joining. **Coverage being high enough is not the same as coverage
being balanced**: vFLIP labels 58% of channels, but the rate differs by animal
(Kruskal–Wallis H = 12.80, P = 0.0017) and about threefold by area. Since animal is the dominant
term for band power, a pooled laminar coefficient carries an animal difference inside it.
Balance, not level, is the criterion.

## Waveform duration

Treat waveform-duration **units** as a verification hazard before any biological claim. For
extracellular data write *putative fast-spiking / regular-spiking* — never PV/SST/VIP.
