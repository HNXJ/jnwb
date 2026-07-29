# omission-a — finalized context

**Status:** authoritative. This file supersedes the handover and handout documents listed in
§11, which are preserved under `context/archive/superseded-2026-07-27/`.
**Last verified:** 2026-07-28.
**Rule for this file:** every path and count below was resolved on disk on the date shown. Where
a previously circulated number is wrong, it appears in §8 with the correction, not silently
deleted.

---

## 1. What this project is

Multi-area dense laminar macaque electrophysiology during a sequential visual omission task,
analysed with the `jnwb` package. Manuscripts on this corpus are lettered: `omission-a`,
`omission-b`, … Each letter is a distinct paper, not a revision.

**omission-a's claim, as currently supported by fitted models:** omission recruits sparse,
higher-order-leaning single-unit spiking, while low-frequency field power is strongly modulated
at every recording site without adopting a direction shared across the hierarchy.

The earlier phrasing — *"broadly perturbing low-frequency cortical state"* — is retained in §8 as
a superseded claim, because it is directional and the direction is not supported.

## 2. The paradigm

A trial is `fx – p1 – d1 – p2 – d2 – p3 – d3 – p4 – d4`. Slots `p1…p4` carry stimulus identity;
`fx` and `d1…d4` are a gray screen with a fixation dot.

**The delays and the fixation interval are visually identical to an omission.** So `AAAB` is seen
as `o–A–o–A–o–A–o–B–o`, and `RRXR` as `o–R–o–R–o–o–o–R–o`. An omission therefore produces **three
consecutive, visually identical empty periods**. The middle one is the omitted slot itself and is
where the signature must begin; the two flanking delays are a within-trial control matched in
every respect except expectation.

**H0:** in each band, at each channel, power during the omitted slot does not differ from the
pre-omission baseline. **H1:** at least one band changes.

Timing (p1-relative, ms): `fx −500`, `p1 0`, `d1 531`, `p2 1031`, `d2 1562`, `p3 2062`,
`d3 2593`, `p4 3093`, `d4 3624`. Stimulus 531 ms; delay 500 ms.

Conditions: `{AAAB, AXAB, AAXB, AAAX, BBBA, BXBA, BBXA, BBBX, RRRR, RXRR, RRXR, RRRX}`.
Nine contain an omission. The minimum omitted slot is 2, so a pre-omission delay always exists.
Use **`stimulus_number`** for slot selection (p1=2, p2=3, p3=4, p4=5). Do not confuse BHV odd
event codes with NWB sequential event codes; `stimulus_number` is the stable crosswalk.
`nwb.intervals["omission_glo_passive"]` is **event-level, not trial-level**.

Use **correct trials only** by default.

## 3. Corpus

Three adult macaques. The third was added recently, so any document written before 2026-07-28
describing N = 2 is reporting a smaller corpus and its counts are lower bounds.

| Source | Sessions | Note |
|---|---|---|
| NWB files (`D:/analysis/nwb/*.nwb`) | 21 | includes sessions with no TFR product |
| `artifacts/data/session_readiness.csv`, `nwb_ok` | 21 | |
| **TFR corpus** (`D:/workspace/data/tfr_arrays/*.npy`) | **17** | 948 files; **this is the analysis corpus** |

TFR sessions by subject: 8, 5 and 4. Two TFR sessions are absent from the readiness list, and six
readiness sessions have no TFR product — the two inventories are not interchangeable.

## 4. Data topology

| What | Path | Verified |
|---|---|---|
| NWB recordings | `D:/analysis/nwb/sub-<subj>_ses-<sess>_rec.nwb` | 21 files |
| Metadata sidecars | `D:/workspace/data/metadata/<session>/` | `probe_areas.json`, `electrodes.csv`, `units.csv`, `events.csv` |
| TFR arrays | `D:/workspace/data/tfr_arrays/sub-<subj>_ses-<sess>-<probe>-<area>-<cond>.npy` | 948 files |
| vFLIP layer tables | `D:/workspace/data/connectivity_databases/<session>_channel_layers.csv` | regenerating |
| Unit table (real) | `outputs/classification/grand_unit_table_shuffle_sso.csv` | 6,655 units |
| Grand unit database | `outputs/publication_figures/data_tables/grand_database_6040_units.csv` | — |
| Layer masks | `outputs/publication_visual_review/area_layer_tfr/layer_masks.json` | — |
| Labyrinth graph | `artifacts/.lab/*.json` | 290 nodes; `labyrinth.db` is **0 bytes** |

**TFR array contract (verified against `scripts/archive_oneoff/precompute_tfr_arrays.py`):**
shape `(trials, 128 channels, 99 freqs, 500 times)`, float32, **raw power, not normalised**;
`freqs = arange(3, 201, 2)` Hz; `times = −1000 + arange(500)·10` ms, **p1-aligned**.

**The aliasing footgun.** For a probe spanning *k* areas, the precompute script writes *k* files
that are **the same full 128-channel array** under *k* different area tokens (its own comment:
*"Build full-probe TFR once per condition, then save per area label"*). Grouping files by their
filename area token compares a probe against itself. The fix is §5.

## 5. Areas, channels, layers

**Ten analysis areas:** V1, V2, V3, V4, MT, MST, TEO, FST, FEF, PFC.
Grouped as low-level visual (V1, V2), intermediate visual/temporal (V3, V4, MT, MST, TEO, FST),
higher-order frontal (FEF, PFC). Eleven or twelve *labels* appear in filenames (V3, V3a, V3d
separately); ten *analysis regions* is the correct count, and the distinction between labelled
recording targets and analysis regions has caused documented drift before.

**Per-channel area vector:** `outputs/channel_area_vector/channel_area_vector.csv`, built by
`scripts/build_channel_area_vector.py`. 6,528 channels, 51 probes, all 17 TFR sessions,
**0 unresolved area tokens**, 0 disagreements against `electrodes.csv`.

**The partition is an assumption, not a measurement.** 27 of 51 probes span multiple areas. In 26
the boundary is channel 64 of 128 — exactly half; the one three-area probe splits at 42 and 85 —
exactly thirds. Every multi-area boundary in the corpus is a uniform division in listing order.
This makes area labels **disjoint**, which removes the aliasing. It does **not** establish that a
channel lies in the area its label names. Consequence: **V3a and V3d are the upper and lower
halves of one shank and must be pooled to V3** for any inference.

**Putative layer** comes from the vFLIP2 spectrolaminar alpha/beta-to-gamma crossover, fitted per
area segment on the first 300 s of raw LFP (Welch PSD, `nperseg=1024`). It returns `na` for
roughly two thirds of channels. A laminar model fitted only where the crossover converged reports
a property of the estimator's success, not of cortex — so it is **skipped with a stated reason**
rather than fitted on the subset.

`scripts/archive_oneoff/build_channel_layer_mapping.py` was dead from a refactor that moved it
(`REPO_ROOT = parents[1]`, correct only while it sat in `scripts/`); fixed to `parents[2]` on
2026-07-28. Its outputs predating that date are stale.

## 6. Analysis contracts

**Bands — canonical, and not negotiable without refitting:**

| Band | Hz |
|---|---|
| theta | 4–8 |
| alpha | 8–14 |
| beta | 14–30 |
| low gamma | 30–50 |
| high gamma | 50–80 |

This set is the **resolution of a documented band-definition drift**: earlier material used alpha
8–12 and theta 3–8 (or 2–7), and the 2026-07-27 figure audit fixed captions and methods onto the
set above. Any figure legend showing alpha 8–12 / theta 2–7 / gamma-low 32–80 / gamma-high 80+ is
**pre-correction** and should not be taken as the house standard. *Low-frequency* means theta–beta
(4–30 Hz), contrasted with gamma (30–80 Hz); it is a band label, not a claim that effects are
largest at the lowest frequencies.

**Baseline.** −250 to −50 ms relative to **omission onset**, applied **per channel, per trial, per
frequency**. Expressed as `10·log10(power / baseline)`. No channel is normalised by another
channel, area, session or animal — a reported modulation is always a site changing relative to
itself. Because the baseline sits inside the first of the three empty periods, this is
conservative: it differences out drift and arousal, at the cost of being a contrast against the
pre-omission delay rather than a neutral pre-trial state. A fixation-referenced version is
computed alongside and is uniformly more negative.

**Averaging order — average power ratios, take the logarithm last.** Accumulate the
dimensionless ratio `power(f,t) / baseline(f)` and apply `10·log10` once, after averaging over
trials, channels, band frequencies, window times and sessions. **Never average decibels.** Mean
of a logarithm is not the logarithm of a mean; the gap grows with the variance of the log, so
averaging dB subtracts a quantity proportional to each unit's *own noisiness*. Measured here:
the gap ranges from −0.17 dB (quietest subject, log-power SD 1.68) to −1.98 dB (noisiest, SD
4.63) and is monotone in the SD. That is large enough to flip a subject's sign — under
log-of-mean one subject's theta is +0.60 dB, under mean-of-log the same data give −1.38 dB.
Receipt: `artifacts/.lab/db_averaging_bias_finding_20260728.json`. Products in
`outputs/omission_tfr_maps/` are dB-averaged and **superseded**; use
`outputs/omission_tfr_maps_ratio/`.

**Windows.** Two are reported, because the response does not resolve within the omitted slot — it
keeps developing through the following delay, so a window confined to the slot samples the leading
edge of a ramp:

- omitted slot, 0 to +531 ms
- post-omission delay, +531 to +1000 ms

**Aggregation.** Session first, then across sessions **unweighted**, so a session contributing many
channels does not dominate.

**Signal separation.** SPK/SUA, MUAe and LFP are never pooled. Session, area, layer, probe and
unit namespaces are preserved throughout.

## 7. Statistical doctrine

One backbone: **GLMM**, link function stated per model — binomial logit for class membership,
identity (Gaussian) for band power in dB. Fitted by REML.

**The unit of inference is the session.** Neighbouring contacts on one shank sample overlapping
field potentials; treating channels as independent inflates the effective n by more than two
orders of magnitude and produces |z| above 40 on sub-decibel effects. Channel-level fits may be
run for comparison but are never reported as inferential.

**Three subjects cannot identify a random-effect variance.** Subject is handled by stratification
and within-subject contrasts, never as a three-level random term.

Proportions use **exact Clopper–Pearson** intervals, not bootstrap. Within-unit contrasts use
Wilcoxon rank-sum. Multiplicity is corrected with Benjamini–Hochberg, which controls **FDR and not
FWER**, and the family is named at each point of use. Four inferential families total; rank
correlations are descriptive only.

**Area and subject are confounded corpus-wide.** No cortical area was recorded in all three
animals. A between-area coefficient is not separable from a between-animal difference. This is a
property of the recording design and cannot be repaired by modelling.

## 8. Superseded claims — do not restore

The 2026-07-27 handout listed the following as **"protected invariants."** They are not
invariants; they are presentation-layer constants that no script computes from data.
`scripts/archive_oneoff/compute_empirical_census_and_power.py` contains them as **hardcoded dict
literals** (lines 32–33, 46–57, 71–82) and writes them to
`artifacts/data/empirical_response_census.json`, which nine downstream scripts then consume.
Receipt: `artifacts/.lab/census_provenance_synthetic_finding_20260728.json`.

| Retracted "invariant" | Status |
|---|---|
| Primary census 8,597 units; O+ = 421/8,597 = 4.90% | **Synthetic.** Real unit table has 6,655 units. Two-subject screening gave ~20 O+ of ~5,000 (~0.4%) — the right order. Recompute on three subjects. |
| LFP census 8,736 channels; beta modulation 6,771/8,736 = 77.51% | **Synthetic.** Real per-channel census is 6,528 channels. |
| GLMM OR = 3.08, CI [2.51, 3.78], z = 10.726, p = 7.25e-27 | **Never fitted.** No mixed model produced these coefficients. |
| Figure 8 alpha 5,816/8,736 = 66.58% | **Synthetic denominator.** The 2026-07-27 correction from 64.50% to 66.58% corrected arithmetic within a fabricated table. |
| "Omission broadly perturbs low-frequency cortical state" | **Directional claim, not supported.** Magnitude holds; direction does not. See §9. |
| "Sustained beta elevation during omission" | **Not reproduced** at channel level, session level, pooled, or within any animal. |

Two of these percentages are exactly whole numbers more often than measurement allows: 32 of 40
displayed cells in the LFP table are exact whole percentages, which for measured proportions at
those denominators has probability ≈ 3×10⁻²⁵.

**What *is* protected** (unchanged, verified, and requiring explicit instruction to alter):

- Condition colours: standard gray `#555555`, omission red `#D9534F`, random control teal `#008080`.
- Epoch shading order p1→p4: yellow `#FCF9E3` → purple `#F3E8F4` → green `#E8F5E9` → blue `#E1F5FE`.
  Defined in `.cursor/rules/omission-palette.mdc` and `.agents/skills/jnwb-visualization/SKILL.md`.
- Figure insertion order in the DOCX is strictly ascending 1→8.
- Figure 6 must be built from the empirical arrays in `D:/workspace/data/tfr_arrays/`. **Do not**
  use `scripts/build_clean_publication_figures.py` — it contains synthetic placeholder construction.
- Results headings are declarative statements, never questions.
- Captions describe what is plotted; interpretation belongs to Results and Discussion.
- `session.get_spike_times(unit_id)` takes the DataFrame **row index**, not the kilosort
  `unit_id` column.
- Multi-area channel resolution uses `jnwb.addressing.map_peak_channel_to_area()`, never string
  splitting.

## 9. Current findings, with receipts

All from `outputs/lfp_band_census_v2/` (census `receipt.json`, models `glmm_results.json`,
`glmm_summary.csv`). Census: 711/711 omission condition files, 0 skipped, 293,760 rows,
17 sessions, median 39 trials per channel.

**Low-frequency power is modulated everywhere.** Against each channel's own baseline, mean
absolute change in the omitted slot: alpha 1.18 dB, theta 1.16 dB, beta 0.91 dB, low gamma
0.59 dB, high gamma 0.42 dB. Low-frequency modulation is roughly twice gamma modulation.

**The direction is not shared.** Signed means pooled across areas: theta −0.53 dB (P=0.07), alpha
−0.37 (P=0.18), beta −0.22 (P=0.28), low gamma −0.06 (P=0.55), high gamma +0.13 (P=0.07);
n = 17 sessions. This tests common *sign*, not presence of modulation. The two questions have
opposite answers.

**Animals disagree in sign.** Session-level, per animal, BH across bands: one animal fell in every
band below 50 Hz (theta −1.58, alpha −1.36, beta −0.89, low gamma −0.39 dB, all q < 0.005,
8 sessions); another rose (theta +0.56 P=0.049; low and high gamma each ≈ +0.27, q < 0.002,
4 sessions); the third reached significance in no band (5 sessions).

**V3 alpha/beta elevation is real in direction, underpowered in test.** Descriptive area model vs
V1, session level: V3 beta +1.82 dB (q=1.6e−6), alpha +1.32 (q=0.006), low gamma +0.52 (q=0.004).
Confounded with animal. The one animal-controlled test — a V3 probe against a V1/V2 probe in the
same five sessions — gives beta +1.59 dB (P=0.076), alpha +1.16 (P=0.24). Both are measured in the
omitted-slot window and are lower bounds for the reason in §6.

## 10. Manuscript lineage

| File | Role |
|---|---|
| `context/omission-a-draft-v2.md` | **current working draft** |
| `context/drafts/omission-a-draft-v1.md` | superseded |
| `context/drafts/04_draft_biorxiv_markdown.md` | source markdown: intro, discussion, abstract, voice |
| `context/PUBLICATION_STYLE_CRITERIA.md` | house yardstick, measured from Westerberg & Xiong 2025 |
| `context/manuscript-docx/omission-2026-manuscript-master.docx` | **original — do not overwrite** |
| `context/manuscript-docx/omission-2026-manuscript-master-scientific-revision.docx` | 2026-07-27 revision |
| `context/manuscript-docx/omission-a-2026-manuscript-integrity-pass.docx` | 2026-07-28, 20 text edits |
| `context/manuscript-docx/omission-a-2026-manuscript-v2-provenance.docx` | 2026-07-28, provenance block |

The DOCX line carries the synthetic numbers of §8 and is retained for history. **The markdown
drafts are the live line**; they carry no number from the DOCX.

⚠ A Word lock file `~$ission-2026-manuscript-master.docx` is present, meaning the master may be
open in Word. Do not write to that DOCX.

## 11. Documents this file supersedes

Moved to `context/archive/superseded-2026-07-27/`, unedited:

- `HANDOUT_NEXT_AGENT_FINAL_2026-07-27.md` — absorbed; its "protected invariants" are retracted in §8.
- `HANDOVER_NEXT_AGENT_2026-07-27.md` — absorbed; its band definitions (alpha 8–12, theta 3–8) are pre-correction.
- `SCIENTIFIC_REVIEW_AND_FIGURE_AUDIT_2026-07-27.md` — absorbed; its editorial fixes stand, its census numbers do not.

Also under `context/archive/`: the `01`–`05` paradigm/pipeline suite and `content.md`
(2026-07-14, describing intended pipelines rather than built ones), `labyrinth_unified.md`
(393 KB export), and `HANDOVER_ONBOARDING_MANIFEST.md`. `context/draft-assets/` holds byte-identical
copies of seven of those files plus the editable figure SVGs; the SVGs are live, the markdown
copies are not.

### Layout of `context/` after the 2026-07-28 reorganisation

```text
context/
  CONTEXT.md                     this file — authoritative project context
  PUBLICATION_STYLE_CRITERIA.md  house yardstick
  omission-a-draft-v2.md         current working draft
  drafts/                        omission-a-draft-v1.md, 04_draft_biorxiv_markdown.md
  manuscript-docx/               the whole DOCX/PDF/zip lineage, incl. the untouched master
  figures/                       loose figure PNGs + figure_asset_manifest_2026-07-27.json
  draft-assets/                  editable figure SVGs (live) + duplicate markdown (not live)
  archive/                       historical material
    superseded-2026-07-27/       the three handouts absorbed into this file
```

Nothing was deleted in the reorganisation; every file was moved.

## 12. Open questions

1. **O+ prevalence on three subjects.** The only headline number still owed. Prior draft's 4.9% is
   synthetic; two-subject screening suggests ~0.4%.
2. **Two-window estimates** per band × area × layer — extraction running as of 2026-07-28.
3. **Does laminar sampling explain the sign inconsistency?** Testable: split each probe at its own
   crossover and ask whether compartments have consistent direction where the whole-probe average
   does not. Blocked on vFLIP coverage.
4. **Methods gaps** absent from every source document: surgery and implant, full stimulus
   specification, fixation and reward schedule, spike-sorting parameters and quality tiers, CSD
   computation.
5. **Author list**; three reference defects (Wacongne 2011 journal/DOI mismatch, Bastos 2015 DOI
   suffix, Rao & Ballard 1999 cited for a Bastos 2012 laminar claim).
6. **Graph health.** 290 nodes but only ~87 carry a verification receipt while ~276 read
   `confirmed`; 40 edges point at a nonexistent `mission` node; `labyrinth.db` is 0 bytes. Do not
   mass-migrate without a deterministic migration receipt — Conservation applies to the graph too.

## 13. Operating rules

- Address the user as **Hamm**; assume domain fluency and match his verification rigor.
- Read `.agents/AGENTS.md`, `CLAUDE.md` and the relevant `.lab` nodes before acting.
- **No receipt, no claim.** Record a Labyrinth delta before finishing a turn.
- Separate observation from inference.
- Do not commit or push unless asked. Preserve originals; write revisions as new files.
