<!--
omission-a — rough draft v1
Merged from: context/04_draft_biorxiv_markdown.md (intro, discussion, abstract, voice)
         and: context/omission-a-2026-manuscript-v2-provenance.docx (structure, methods scaffold)
Built 2026-07-28. Text-only: no figures embedded (step 1 of the agreed plan).

CONVENTIONS IN THIS DRAFT
  ###                     citation placeholder, per Hamm's convention, with a
                          (NameYYYY, TITLE-SHORT) comment alongside
  [[STAT: ...]]           a number that must come from a computation that has not yet been
                          run. NEVER fill these from the previous draft — those values are
                          hardcoded literals (see artifacts/.lab/
                          census_provenance_synthetic_finding_20260728.json)
  [[CONFLICT: ...]]       two sources disagree; resolve before v2
  [[FIG N]]               figure slot

TARGETS (context/PUBLICATION_STYLE_CRITERIA.md)
  Abstract 220-280 | Intro 800-1100 | Results 2000-2600 | Discussion 2000-2500
  Methods 3500-4500 | 5 main figures | <=4 inferential families | ~10 p-values
-->

# Sparse higher-order spiking and subject-specific low-frequency field change during visual omission

<!-- Title changed from "Sparse spiking and broad low-frequency LFP disruption during visual
     omission mismatch". "Broad ... disruption" is not what the fitted models show: the pooled
     session-level effect is null and the sign reverses between animals. Receipt:
     artifacts/.lab/omission_lfp_glmm_subject_sign_reversal_20260728.json -->



**Hamed Nejat**¹, [[CONFLICT: author list incomplete in both sources — markdown has placeholders,
docx had a literal "ET Al" placeholder now removed]], **André M. Bastos**¹˒²

¹Department of Psychology, Vanderbilt University, Nashville, TN, USA
²Vanderbilt Brain Institute, Vanderbilt University, Nashville, TN, USA

---

## Abstract

Predictive routing proposes that low-frequency alpha and beta rhythms regulate the passage of
expected input through cortex, whereas gamma rhythms and spiking reflect feedforward sensory
drive ###. *(Bastos2020, PREDICTIVE-ROUTING)* What happens to this arrangement when the expected
input never arrives is unknown: an omission removes bottom-up drive entirely while leaving the
temporal and contextual structure of the sequence intact. We recorded spiking activity and local
field potentials simultaneously across visual, temporal and frontal cortex in awake macaques
performing a four-item sequence task in which an expected grating was omitted at a defined
position. Omission did not evoke a sensory-like population response. Spiking changes were sparse
and time-specific, confined to a small minority of units and weighted toward higher-order
cortex, while lower-order visual areas showed weak or absent omission-driven population spiking.
Field potentials behaved differently. Low-frequency power changed substantially around the
expected time of the missing event, with gamma remaining tied to actual stimulus presentation,
but the direction of that change reversed between animals, so that pooling across the corpus
returned no net modulation. Elevated alpha and beta in V3 was the largest area-level departure,
and the only test holding animal and session constant is consistent in direction but
underpowered. The relationship between
band-limited power and spiking also reorganised: during stimulus periods spiking tracked gamma,
whereas during omission the low-frequency bands carried that relationship. These results are
consistent with a division of labour in which a selective subset of neurons converts a missing
event into an explicit, time-locked code, while the low-frequency state that accompanies it
varies in sign across individuals and cannot be summarised by a single direction.

<!-- 246 words. No statistics, per house style (the exemplar reports none in its abstract). -->

---

## Introduction

A central principle in systems neuroscience is that the brain is a predictive machine, using
current context to generate internal expectations about future sensory input ###.
*(RaoBallard1999, PREDICTIVE-CODING; FristonKiebel2009, PREDICTIVE-CODING-FEP)* Perception, in
this view, relies on a continuous comparison between expected and observed sensory states, with
mismatch signals arising when the two diverge. Empirical and computational work has established
robust neurophysiological correlates of these processes ###. *(Friston2010, FREE-ENERGY;
Bastos2012, CANONICAL-MICROCIRCUITS)*

A mechanistic refinement of this theory is the predictive routing framework, which proposes that
predictions and prediction errors are expressed through distinct oscillatory dynamics across the
cortical hierarchy ###. *(Bastos2020, PREDICTIVE-ROUTING)* Predictable input contexts are
associated with stronger top-down alpha and beta oscillations, hypothesised to suppress
feedforward signalling of expected input. Unexpected input is associated with a release from
this suppression, producing stronger bottom-up gamma activity and increased spiking in
feedforward pathways. The mechanism is rhythmic gating rather than a dedicated error population:
top-down alpha and beta activity is linked to predictions, and bottom-up gamma and spiking to
sensory surprise. Consistent with this, dampening top-down alpha and beta activity
pharmacologically disinhibits bottom-up gamma ###. *(Xiong2024, PROPOFOL-PREDICTIVE)*

Testing this framework requires a mismatch that is not confounded with a change in physical
stimulation. Sequence-based oddball paradigms are the standard tool, but the most common variant
— the local oddball, in which a repeated item is replaced by a different item — confounds
prediction error with low-level adaptation and with release from adaptation ###.
*(GrillSpector2006, REPETITION-SUPPRESSION; MayTiitinen2010, MMN-ADAPTATION)* Global oddball
paradigms address this by defining the surprising event through the larger contextual structure:
when a sequence AAAB is presented frequently and AAAA rarely, the rare AAAA violates a rule that
cannot be encoded by short-term adaptation ###. *(Bekinschtein2009, GLOBAL-LOCAL;
Chao2018, HIERARCHICAL-PREDICTION)* Global oddballs are consequently of particular interest,
because they probe a system's expectations rather than its immediate sensory response.

One confound survives even this design: the surprising event is still a stimulus. Any response
may therefore reflect the physical properties of the substituted item rather than the violated
expectation. The omission paradigm removes that confound. Omissions delete the expected stimulus
while preserving its temporal and contextual position, so that a time-locked response cannot be
attributed to the features of a replacement stimulus, nor to an offset artefact. Such a response
must instead reflect internally generated dynamics, the consequences of missing bottom-up drive,
or an interaction between the two. This makes omission a sharp test of predictive processing,
and a direct one for predictive routing. If predictions are implemented by low-frequency
rhythmic control of circuit state, omission should manifest primarily as a disturbance of the
low-frequency state that had prepared the pathway, rather than as a sensory-like rise in gamma
and widespread spiking.

The neural expression of prediction error is heterogeneous, varying with the spatial scale of
the violation, the sensory modality, and position in the cortical hierarchy. Large-scale
analyses suggest that simple local mismatches are widespread and robust across cortex, whereas
contextual or global violations are sparse and concentrated in higher-order areas rather than
distributed evenly through sensory cortex ###. *(Garrido2007, MMN-MECHANISMS; Westerberg2025,
HIERARCHICAL-SUBSTRATES)* Prediction error thus appears to be carried not by a single canonical
signalling system but by diverse, circuit-specific mechanisms. Omission studies across species
and modalities reinforce this: visual omission in rodents produces sparse, delayed, ramp-like
activity, sometimes implicating specific inhibitory cell types, whereas auditory omission
responses are typically sharper and more time-locked ###. *(Wacongne2011, PREDICTION-HIERARCHY;
Garrett2020, VIP-DYNAMICS; Jamali2024, OMISSION-RODENT)* Primate work aligns with sparse,
selective encoding, with explicit omission-related signals more prominent in higher-order cortex
than in primary sensory areas ###. *(Suda2022, FRONTAL-OMISSION)*

This body of work motivates a specific dissociation. If omission primarily reflects the failure
of expected bottom-up drive, lower-order cortex may show little overt omission-linked spiking
despite being embedded in an altered network state, while higher-order cortex generates a
time-specific spiking signal that converts the failed expectation into an explicit event code.
The prediction is a functional dissociation between broad, distributed changes in field
potential dynamics and sparse, selective changes in single-neuron firing.

To test this, we recorded spiking activity and local field potentials across multiple visual,
temporal and frontal areas in awake macaques performing a sequential visual omission task. The
paradigm was designed to control for stimulus offset responses and to separate the contributions
of temporal position and expected stimulus identity. Because omission occurred during a static
display of constant luminance, any time-locked response necessarily reflects internal dynamics
rather than bottom-up cues.

<!-- ~940 words. Target 800-1100. -->

### Terminology

| Term | Definition | Notation |
|---|---|---|
| Sequence (input) | A pattern in space-time received by the system | S |
| Stimulus (sensory) | Any physical sensory input that drives the system | S = {A, B, R, …} |
| Omission | Physical absence of an expected stimulus, preserving temporal and contextual structure | S = {X} |
| Standard | The expected, non-surprising event | S = {A} given E[S] = {A} |
| Mismatch | Divergence between expected input and observed state (prediction error) | S = {A} given E[S] = {B} |
| Omission mismatch | An omission where a standard, expected event deviates | S = {X} given E[S] ≠ {X} |
| Oddball | A surprising event, often a mismatch | S = {AB} given E[S] = {AA} |
| Local oddball (LO) | An immediate or short-term oddball, confounded by adaptation | S = {AAAB} given E[S] = {AAAA} |
| Global oddball (GO) | A contextual oddball, not attributable to adaptation | S = {AAAA} given E[S] = {AAAB} |
| Omission oddball | An oddball specific to absence of expected input, not attributable to adaptation or offset | S = {SSXS} given E[S] = {SSSS} |
| Baseline | An interval in which the context is null | S = {N} |

**Table 1.** Terms used in prediction-mismatch paradigms, with emphasis on omission mismatch.

The four omission conditions used here span the identity-predictability and sequence-position
dimensions:

```text
S = {AXAB} given E[S] = {AAAB}   identity-predictable,   local omission
S = {AAAX} given E[S] = {AAAB}   identity-predictable,   global omission
S = {RXRR} given E[S] = {RRRR}   identity-unpredictable, local omission
S = {RRRX} given E[S] = {RRRR}   identity-unpredictable, global omission
```

---

## Methods

### Subjects and recordings

Neural data were acquired from multi-area dense laminar macaque electrophysiology during a
sequential visual omission task. Recordings were obtained from three adult macaques
(ages 11, 17, and [[STAT: age of the third subject]] years at the time of recording) across
17 sessions: C31o (8 sessions), V182o (4), and V198o (5). All procedures were approved by the
Vanderbilt University Institutional Animal Care and Use Committee and conformed to NIH
guidelines ###. *(IACUC, PROTOCOL-TBD)*

<!-- Subject count resolved 2026-07-28 (Hamm): the third subject was added after the source
     markdown was written, so that document's N = 2 and its unit counts describe an earlier,
     smaller corpus. N = 3 is current. Every count inherited from the markdown is therefore a
     lower bound pending recomputation on the full corpus. -->



Recordings comprised spike-sorted single-unit activity (SUA), analog multi-unit activity
envelope (MUAe), and local field potentials (LFP). The canonical area order used throughout
analysis and plotting was V1, V2, V3d, V3a, V4, MT, MST, TEO, FST, FEF, PFC. For interpretation,
areas were grouped into low-level visual cortex (V1, V2), intermediate visual and temporal
cortex (V3d, V3a, V4, MT, MST, TEO, FST), and higher-order frontal cortex (FEF, PFC). V3d and
V3a were retained as separate labels in descriptive displays but were pooled to V3a/d for
inference, for the reason given under *Probes, channel geometry, and area assignment*.

### Probes, channel geometry, and area assignment

Signals were acquired with DiagnosticBioChips 128-channel laminar probes at 30 kHz (Intan RHD),
and preprocessed into LFP, MUAe and spike-sorted single units (Kilosort). Behavioural control —
fixation, reward, and task event marking — was implemented in MonkeyLogic (NIMH) ###.
*(MonkeyLogic, NIMH-ML)*

Probe geometry and session-specific area assignments were resolved from recording metadata and
repository mapping tables. **A single probe could span more than one named cortical area, so
area identity was not assumed to be one probe per area.** When a probe was assigned to multiple
areas, its ordered channel axis was partitioned into contiguous segments corresponding to those
listed areas, in order along the probe. **The segment boundaries were not estimated from the
data: each listed area was assigned an equal share of the channel axis, so a two-area probe
split at channel 64 of 128 and the single three-area probe split at channels 42 and 85.** Of 51
probes, 27 spanned more than one area, and the boundary in every one of them is a uniform
division of this kind. The same segmentation was applied to LFP and MUAe channels;
spike-sorted units were assigned to an area according to their anchor or peak channel.

This procedure guarantees that area labels are disjoint — each channel contributes to exactly
one area — which is what the analysis requires, because the precomputed time-frequency arrays
store the whole 128-channel probe once per area named in its label. It does not establish that
a given channel lies within the area its label names, and channels near a segment boundary are
assigned by assumption rather than by measurement. We therefore treat area as a coarse
grouping variable and make no claim that depends on the precise location of a boundary. For the
same reason, **V3d and V3a — the upper and lower halves of a single shank under this
partition — are pooled to V3a/d wherever an inferential model is fitted**, and are shown
separately only in descriptive per-channel displays.

Putative cortical layer was assigned from the laminar profile of the current source density and
the spectrolaminar power gradient, using the depth of the alpha/beta-to-gamma crossover (the
"vflip") as the layer 4 reference ###. *(Mendoza-Halliday2024, SPECTROLAMINAR)* Layer
assignments were treated as putative throughout and were used for grouping rather than for
inference about individual channels.

### Task design and omission paradigm

Subjects performed a sequential visual omission paradigm in which stimulus identity and temporal
regularity jointly established an expected sensory sequence. Each trial comprised a fixation
interval followed by four stimulus slots and their intervening delays, denoted
{fx, p1, d1, p2, d2, p3, d3, p4, d4}; only {p1, p2, p3, p4} varied across trials.

All event-locked displays used p1 onset as 0 ms, with a default analysis window from −1000 to
+4000 ms. The canonical sequence timing was: fx −500 to 0 ms; p1 0 to 531 ms; d1 531 to 1031 ms;
p2 1031 to 1562 ms; d2 1562 to 2062 ms; p3 2062 to 2593 ms; d3 2593 to 3093 ms; p4 3093 to
3624 ms; d4 3624 to 4124 ms. Stimuli were drifting gratings presented for 531 ms, separated by
500 ms delays.

**Critically, the delay intervals and the fixation interval are visually identical to an
omission.** All are a gray screen carrying only the fixation point. An omitted slot is therefore
not a distinct visual event: it is indistinguishable on screen from the delays that flank it. A
sequence AAAB is seen as o–A–o–A–o–A–o–B–o, and an omission sequence RRXR as
o–R–o–R–o–o–o–R–o, in which the omission produces three consecutive, visually identical empty
periods. The central period of that triplet is the omitted slot itself, and is the interval in
which an omission signature must appear; the flanking periods are ordinary delays and serve as a
within-trial control that is matched to the omitted slot in every respect except expectation.

The full condition set was S = {AAAB, AXAB, AAXB, AAAX, BBBA, BXBA, BBXA, BBBX, RRRR, RXRR,
RRXR, RRRX}. Omissions were organised by sequence position: p2 omissions {AXAB, BXBA, RXRR}, p3
omissions {AAXB, BBXA, RRXR}, and p4 omissions {AAAX, BBBX, RRRX}. A- and B-family blocks
contained frequent full sequences and infrequent omission sequences; the R-family served as a
random control with matched omission timing. Each omission was compared to its matched
full-sequence control and, where relevant, to the random-control conditions.

Because every omission is preceded by a presented stimulus, omission analyses were framed with
respect to the surrounding sequence structure — the preceding stimulus, the pre-omission delay,
the expected-but-omitted slot, and the post-omission delay — rather than as isolated events.

Only correct, completed fixation trials were analysed. [[STAT: trial counts per condition per
session, and the fixation-break exclusion rate]]

### Signal extraction and preprocessing

Three signal classes were analysed: spike-sorted single units (SPK), MUAe, and LFP. Signal
access proceeded through a single canonical accessor returning session-keyed,
condition-filtered data aligned in p1-relative time. Analog signals were returned as
trial × channel × time; spiking data as trial × unit × time. SUA, MUAe and LFP were maintained
as separate signal classes at every stage and were never pooled.

LFP data were drawn from NWB recordings and kept in trial × channel × time format until late
analysis stages. For spectral and connectivity analyses, bipolar derivation by nearest-neighbour
laminar differencing was applied before any cross-site comparison, following the predictive
routing convention. For descriptive power analyses both monopolar and bipolar representations
were retained, and the representation used is stated explicitly in each figure legend. Trial
structure was preserved until after time-frequency decomposition and baseline normalisation, to
avoid premature averaging.

### Unit classification

Functional response classes were determined from within-unit contrasts over prespecified
stimulus and omission windows. Units were classified as stimulus-excited (S+),
stimulus-suppressed (S−), omission-excited (O+), omission-suppressed (O−), or Null. A unit was
classified O+ when its firing rate in the omission window exceeded both its stimulus-window rate
and its baseline rate, assessed by Wilcoxon rank-sum test at p < 0.01. Classification used
unit-quality-tiered spike-sorted units only; MUAe was analysed separately and never merged into
the single-unit census.

[[STAT: unit counts per class per area, with denominators, recomputed on the full three-subject
corpus. The source markdown's ~20 omission-positive of ~5,000 screened describes the earlier
two-subject corpus and is a lower bound. The prior DOCX draft's 421 of 8,597 are hardcoded
literals and must not be reused
(artifacts/.lab/census_provenance_synthetic_finding_20260728.json).]]

### Time-frequency analysis of LFP power

Time-frequency analyses were performed on omission- and stimulus-aligned LFP epochs using
moving-window spectrogram methods with approximately 98% window overlap, chosen to produce
smooth band-power traces while retaining frequency resolution adequate for theta, alpha, beta
and gamma comparisons.

For omission-centred analyses, each omission-family condition was converted from p1-relative
time into a local omission-relative time base in which 0 ms marks the expected onset of the
missing stimulus. The local analysis window extended from −1000 to +1000 ms, encompassing the
preceding stimulus, the pre-omission delay, the omitted slot, and the post-omission delay.

Spectral power was computed in linear units and normalised at each frequency by the mean power
in a late pre-omission delay baseline, −250 to −50 ms relative to omission onset. Relative power
change was expressed in decibels as 10 · log₁₀(power / baseline). Band-specific traces were
obtained by averaging baseline-normalised power across canonical frequency ranges and then
across trials. Canonical bands were theta 4–8 Hz, alpha 8–14 Hz, beta 14–30 Hz, low gamma
30–50 Hz, and high gamma 50–80 Hz. Throughout, *low-frequency* denotes the theta–beta range
(4–30 Hz), contrasted with gamma (30–80 Hz); the term is used in this band sense and does not
imply that effects are largest at the lowest frequencies.

Spectrograms were computed separately for stimulus-present, omission, and control conditions and
summarised at the area and putative-laminar levels. Population heatmaps displayed relative power
in decibels as a function of time and frequency; band-trace panels collapsed the spectrogram
into theta, alpha, beta, low-gamma and high-gamma trajectories. All averaging was performed at
the session level before grand averaging across sessions, unless the inferential question
explicitly targeted channels.

### Band-specific dynamics and spike–field relationships

Band-limited LFP dynamics were examined to test whether omission alters the balance between
low-frequency predictive structure and higher-frequency feedforward-like activity. For
time-resolved power, the estimate came from band-collapsed spectrogram power rather than
narrowband Hilbert power, preserving consistency with the main time-frequency pipeline. For
mechanistic analyses requiring instantaneous phase, narrowband analytic phase and amplitude were
extracted with zero-phase band-pass filters followed by the Hilbert transform.

Spike–field relationships were assessed by comparing band-limited power with concurrent spiking
in matched omission and stimulus windows. [[STAT: spike–field coherence method, frequency
resolution, and trial-count matching between omission and stimulus windows]]

### Statistics

Inference rests on a single backbone. Population-level effects were evaluated with generalised
linear mixed-effects models (GLMM), with the link function stated per model and with random
intercepts for subject and session; the unit of statistical inference is the session, never the
individual channel or unit, to avoid pseudo-replication. Binary outcomes (unit class membership)
used a binomial logit link; continuous outcomes (band power in decibels) used an identity link.

Proportions are reported with exact Clopper–Pearson binomial confidence intervals, which require
no resampling and are exact for count data. Within-unit contrasts used the Wilcoxon rank-sum
test. Time-frequency comparisons used cluster-based permutation testing, which controls the
family-wise error rate intrinsically over the time-frequency search space; where multiple areas
were tested, the false discovery rate across areas was controlled with the Benjamini–Hochberg
procedure. No other inferential families were used, and rank correlations across areas are
reported as descriptive effect sizes only.

[[STAT: GLMM specifications, convergence diagnostics, and random-effects variance components for
each fitted model. No mixed model has yet been fitted for this draft; the coefficients in the
prior draft were presentation-layer constants and are excluded here.]]

### Data and code availability

Analysis pipelines, the `jnwb` Python package, statistical analysis code, and manifest receipts
are available at https://github.com/HNXJ/omission. Primary NWB recordings, electrode metadata
sidecars, precomputed time-frequency arrays, and unit classification tables will be deposited
with a persistent identifier prior to publication; SHA-256 file hashes and verification receipts
are maintained in the repository manifest. [[STAT: replace with the DOI/accession before
submission]]

<!-- ~1,750 words. Target 3,500-4,500. Expansion needed in: surgery and implant, stimulus
     specification (size, contrast, spatial/temporal frequency, eccentricity), fixation window
     and reward schedule, spike sorting parameters and quality tiers, CSD computation,
     per-model GLMM specifications. All require facts not present in either source document. -->

---

## Results

### Omission-sensitive units are a selective minority across the hierarchy

Stimulus-modulated populations showed robust sensory activity, but most units were unresponsive
to omissions. Omission-positive and omission-negative units were sparsely distributed, and their
firing changes were locked to the missing-item interval rather than distributed across the
trial. Two observations follow. First, omission-positive units were rare
[[STAT: n O+ / n screened on the full three-subject corpus, with exact binomial CI. The
two-subject figure was ~20 of ~5,000 (~0.4%); expect the same order, not the prior draft's
4.9%]].
Second, their responses were specific to the sequence position of the omission, not to the trial
as a whole. Omission signalling is therefore a time-locked event rather than a global shift in
firing.

[[FIG 1 — predictive routing schematic; accepted, quality pass later]]

[[FIG 2 — MaDeLaNe recording topology; accepted]]

[[FIG 3 — paradigm and unit yield; accepted]]

### Omission recruits several response motifs rather than one

Firing during the omission window was not uniform across units. Some units increased their rate
around the omission, some decreased, and some ramped or shifted slowly across the omission
period. This argues against a single, canonical omission signal analogous to the sensory
mismatch response seen for local oddballs, and indicates instead that omission recruits several
response motifs, more prominently at higher positions in the hierarchy.

This heterogeneity also explains a negative result: average population spiking did not differ
from baseline even in areas where a subset of neurons carried a clear omission response. Mixed
positive and negative unit types cancel at the population level, particularly in lower-order
cortex. Population averages are therefore a poor instrument for detecting omission signalling,
and the sparsity of the effect is not an artefact of insufficient sensitivity but a property of
the code. [[STAT: per-area O+ and O− counts and the resulting population mean, showing the
cancellation explicitly]]

[[FIG 4 — full-sequence firing-rate traces by response group, A-family; accepted]]

### Omission is not equivalent to ordinary sensory surprise

Stimulus-positive and stimulus-negative units were abundant, and their responses were flat
during omission. Were omission treated as a strong unexpected stimulus, more units should have
engaged and sensory-like spiking should have appeared across many areas. Instead, omission-linked
activity was limited relative to the broader and stronger changes seen during stimulus
presentation. The proportion of omission-positive units relative to the screened population
indicates that omission does not evoke widespread distributed spiking across the cortical
hierarchy. [[STAT: proportion, with exact binomial CI, and the GLMM contrast for higher-order
enrichment]]

[[FIG 5 — NEEDS ALIGNMENT. Currently grand-average stimulus and omission traces. Should carry
the sparse-spiking claim with per-area prevalence and its uncertainty, and headline the
hierarchy contrast that the GLMM tests.]]

### Low-frequency field power during omission does not change consistently across animals

Field potentials behaved differently from spiking, but not in the direction the framing above
anticipates. We computed, for every channel assigned to an area by the segmentation described in
Methods, the power in the omitted slot relative to the late pre-omission delay, in decibels, in
each of five bands (293,760 channel × band × condition observations from 711 condition files,
17 sessions, three subjects, median 39 trials per channel).

Pooled across the corpus at the session level, no band changed significantly during the omitted
slot: theta −0.53 dB (P=0.07), alpha −0.37 dB (P=0.18), beta −0.22 dB (P=0.28), low gamma
−0.06 dB (P=0.55), high gamma +0.13 dB (P=0.07); n = 17 sessions. Every low-frequency point
estimate is negative. We note that the same models fitted to individual channels return
q < 0.01 for theta and alpha, but channels on one shank sample overlapping field potentials and
are not independent; the session-level estimate is the one the design supports, and we report it
in preference throughout.

The pooled null is not an absence of effect but a cancellation. Fitted within each animal, the
low-frequency bands change substantially and in opposite directions. In C31o, power fell in
every band below 50 Hz — theta −1.58 dB, alpha −1.36 dB, beta −0.89 dB, low gamma −0.39 dB, all
q < 0.005 across 8 sessions. In V182o, power rose — theta +0.56 dB (P=0.049), low gamma +0.28 dB
and high gamma +0.27 dB, both q < 0.002 across 4 sessions. In V198o no band reached significance,
with alpha (+0.71 dB) and beta (+0.62 dB) trending positive across 5 sessions. Two animals move
one way and one moves the other, which is what the pooled estimate averages away.

This result is consistent with a field response to omission whose sign is set by something that
differs between animals — recording site composition, laminar sampling, or state — rather than
by the omission itself. It is not consistent with a uniform low-frequency modulation across the
hierarchy, and it is not consistent with the sustained beta elevation reported previously on this
corpus, which is not reproduced at any level of analysis we ran.

[[FIG 6 — NEEDS ALIGNMENT. Should show omission-relative time-frequency structure for
representative low- and high-order areas on segmented channels, with the three consecutive empty
periods marked, and must display the three subjects separately rather than pooled.]]

### Elevated alpha and beta in V3 is the largest area effect but rests on one animal

The one area-level departure large enough to matter is in V3. Relative to V1, and estimated at
the session level, V3a/d power during the omitted slot was higher in beta by +1.82 dB
(q=1.6 × 10⁻⁶), in alpha by +1.32 dB (q=0.006) and in low gamma by +0.52 dB (q=0.004). No other
area reached comparable magnitude; the next largest were PFC in alpha (+1.02 dB, q=0.03) and FEF
in low gamma (+0.44 dB, q=0.02).

These area estimates cannot be interpreted as area effects on their own, because area and subject
are confounded by the recording design: no cortical area in this corpus was recorded in all three
animals. V3 was recorded only in C31o; V3a and V3d only in V198o; FEF, MT, MST, FST, TEO and PFC
only in C31o and V182o. A between-area coefficient is therefore not separable from a
between-animal difference.

The V3 effect can be tested with subject held constant in exactly one place. In V198o, the
V3a/d probe and the V1/V2 probe were recorded simultaneously in the same five sessions, so the
two can be compared within animal, within session and within day. Paired across those sessions,
V3a/d exceeded V1/V2 by +1.59 dB in beta (P=0.076), +1.16 dB in alpha (P=0.24) and +0.56 dB in
low gamma (P=0.24), and was marginally lower in high gamma (−0.17 dB, P=0.60). The direction is
the predicted one and the beta magnitude is large for a band-power contrast, but with five
sessions the contrast does not reach significance. We therefore report elevated alpha and beta in
V3 as a consistent, sizeable, single-animal observation, and not as an established area
difference.

[[FIG 6 — NEEDS ALIGNMENT. Should show omission-relative time-frequency structure for
representative low- and high-order areas, computed on segmented channels, with the three
consecutive empty periods marked so the reader can see the middle-slot logic.]]

### Gamma tracks stimulation; low-frequency structure tracks omission

During stimulus periods, gamma power was closely linked to spiking, consistent with feedforward
sensory processing. During omission periods the pattern shifted, and lower-frequency structure —
beta in particular — carried the relationship between field and spiking. The result is not that
omission produces a large gamma-driven population response, but that omission changes how
spectral state and spiking are coupled. [[STAT: spike–field coupling by band and window, with
the GLMM condition × band contrast]]

This bears directly on the predictive routing account. If omission perturbs the circuit state
that controls routing, the relationship between band-limited power and spiking should differ
from that seen during genuine stimulus drive. Cortex is not processing "nothing" during an
omission; it is responding to a failure of expected input, and that response is more visible in
spectral–spike coupling than in any broad increase of firing.

[[FIG 7 — NEEDS ALIGNMENT. Should carry spike–field coupling by band for omission vs stimulus
windows, at the area and putative-layer level.]]

### Omission shifts the cross-area spectral pattern

Omission moved cortex toward a different cross-area spectral pattern, most clearly in
beta-range structure. The alignment across areas during omission was not identical to that
during normal stimulus processing, and it was not uniform across the hierarchy: some areas and
some laminar groupings changed more than others. [[STAT: cross-area spectral alignment measure,
by band and hierarchical level]]

Omission is therefore not only a local event within one area. It alters the broader network
state, most strongly in low-frequency structure, and that alteration is visible across both
hierarchy and laminar groupings.

[[FIG 8 — NEEDS ALIGNMENT. Should synthesise the spiking and field results into the central
dissociation, on segmented channels, without implying causal coupling.]]

<!-- ~1,150 words of prose plus placeholders. Target 2,000-2,600 once the [[STAT]] slots carry
     real numbers and their surrounding sentences are completed. -->

---

## Discussion

The main finding of this study is that visual omission produces only sparse, selective changes in
spiking, concentrated in higher-order cortex, and that the accompanying change in low-frequency
field structure is substantial within an animal but does not share a common sign across animals.
This bridges two lines of work that have developed largely separately — predictive routing in
oscillatory dynamics, and sparse higher-order mismatch signalling in spiking — while placing a
sharper limit on the first than we expected to place. Three conclusions follow.

**Omission is not equivalent to ordinary sensory surprise.** Were omission treated as a strong
unexpected stimulus, broader gamma increases and stronger sensory-like spiking should have
appeared across many areas. Instead, gamma changes were limited relative to the broader changes
in theta, alpha and beta. This suggests that omission primarily disrupts the predictive state of
the circuit rather than its sensory output channel. The distinction matters because it separates
two accounts that make similar predictions for conventional oddballs but diverge sharply for
omission: an error-population account predicts a positive, sensory-like response wherever a
prediction is violated, whereas a state-control account predicts a change in the rhythmic
context within which sensory drive would have been evaluated.

**Omission-sensitive spiking is sparse and unevenly distributed.** A small group of neurons,
concentrated in higher-order cortex, appears to carry much of the omission-linked spiking
signal, while lower-order sensory cortex shows weak omission-driven population spiking. This
agrees with the view that strong context-violation signals are not carried equally by all
neurons in all areas, and with large-scale spiking work showing that higher-order areas carry
more of the signals tied to prediction violation ###. *(Westerberg2025, HIERARCHICAL-SUBSTRATES)*
The heterogeneity of response motifs within the omission window reinforces this: omission does
not recruit a single canonical response, and the cancellation of positive and negative units at
the population level explains why population averages can appear flat in areas that nonetheless
contain genuine omission signalling.

**The field response to omission is large within an animal and inconsistent between them.**
Omission changed low-frequency spectral power by roughly one decibel in each animal we recorded,
but downward in one and upward in another, so the pooled estimate across seventeen sessions is
indistinguishable from zero. Two readings are available and this design cannot separate them.
Either the sign of the low-frequency response is genuinely set by something that varies between
animals — the composition of recorded sites, the laminar depth actually sampled by each shank, or
behavioural state — or the effect is smaller than the between-animal variability and what we are
measuring is that variability. What we can state is that the direction is not a property of
omission alone in this corpus. Reporting a pooled low-frequency modulation here would have
required averaging over a sign reversal, and we note it explicitly because a previous analysis of
this corpus reported sustained beta elevation, which none of our models reproduce.

This tempers, without overturning, the predictive-routing reading. The routing account predicts
that omission interrupts a low-frequency state that had prepared the pathway for expected input;
it does not, on its own, predict which direction the interruption takes, and our data are
compatible with either sign. The claim that survives is the narrower one: omission alters
low-frequency structure substantially and alters how band-limited power relates to spiking, while
a sparse set of neurons converts that altered state into time-specific omission-linked spiking.
The magnitude is real; the common direction is not established.

### Relation to predictive routing

Predictive routing proposed that alpha and beta rhythms suppress expected input, while gamma and
spiking carry feedforward processing when that suppression is released ###.
*(Bastos2020, PREDICTIVE-ROUTING)* Our data extend the model into a regime it did not originally
address: what happens when the expected input never arrives. The answer is not a broad rise of
feedforward gamma and spiking. Instead, the low-frequency predictive state is itself disrupted,
while only selected neurons show omission-linked spiking. The omission response is a
circuit-state event first and a sparse spiking event second.

This has a specific implication for how prediction errors should be modelled. In a strict
subtractive scheme, absent input yields a negative prediction error whose magnitude equals the
prediction, and that error should propagate feedforward. We do not observe a feedforward
signature of that kind. The result is more consistent with schemes in which predictions set the
gain or routing of a pathway than with schemes in which they are subtracted from incoming
signals at each level ###. *(Bastos2012, CANONICAL-MICROCIRCUITS; Aizenbud2024, PP-MECHANISMS)*

### Why lower-order and higher-order cortex differ

Weak lower-order omission spiking, broad low-frequency field changes, and stronger higher-order
omission-sensitive single-neuron responses together suggest a division of labour. Lower-order
sensory cortex may mainly reflect the presence or absence of sensory drive and the current
rhythmic state of the pathway. Higher-order cortex may be more involved in converting a failure
of expected input into an explicit spiking signal. That division also explains how
omission-sensitive units can be genuine and functionally important without dominating population
averages in the areas that contain them.

An alternative reading deserves stating. Sparse higher-order spiking could reflect not an
explicit omission code but a downstream consequence of altered input statistics — higher-order
areas may simply be further from sensory drive and therefore more sensitive to changes in the
temporal structure of their inputs. Distinguishing these requires manipulating the low-frequency
state directly and asking whether omission-linked spiking follows.

### Limitations

Several constraints bound the interpretation.

The design is observational. Co-occurrence of sparse spiking and broad low-frequency change does
not establish a causal direction between field state and spiking, and the division of labour
proposed above is an inference from correlation.

Subject-level generalisation is provisional. With a small number of subjects and unbalanced
sampling of areas across them, no single area contrast is cleanly separable from subject
identity. This constraint is not specific to any one area; it applies wherever an area was
recorded predominantly in one animal.

Area assignment is instrumental as well as anatomical. Individual laminar probes span more than
one cortical area, and until the contiguous-segment partition is applied to the analysis
products, channel counts attributed to neighbouring areas are not independent. Area-resolved
field results should be read as probe-resolved until that segmentation is in place.

Laminar assignment is putative. Layers were inferred from the spectrolaminar power gradient
rather than from histological reconstruction, and are used for grouping rather than for claims
about individual channels.

Trial counts per omission condition are low by design, since omissions must remain rare to
retain their status as violations. Per-channel significance testing is correspondingly
underpowered, and channel-level prevalence figures are reported as descriptive rather than
inferential.

Finally, omission removes bottom-up drive but does not isolate the mechanism that generates the
response. The precise link between the low-frequency network state and the selective
omission-sensitive neurons requires direct circuit tests.

### Outlook

Two follow-ups are indicated. First, a biophysically constrained hierarchical cortical model
running the same paradigm would test whether a routing-based architecture reproduces the
observed dissociation while a subtractive-error architecture does not. Second, causal
manipulation of the pre-omission low-frequency state — pharmacological or optogenetic — would
test whether omission-linked spiking depends on the state it appears to follow. Together these
would convert the present correlational dissociation into a mechanistic claim.

<!-- ~1,180 words. Target 2,000-2,500. -->

---

## References

<!-- Bibliography to be generated from the ### markers above. Each ### carries a
     (NameYYYY, TITLE-SHORT) comment identifying the intended source.

     Carried forward from the prior draft's reference list, with three defects to fix:
       - Wacongne et al. 2011 is listed as J Neurosci with a PNAS DOI
       - Bastos et al. 2015 is listed as Neuron 85(2) with a DOI suffix of 2015.09
       - Rao & Ballard 1999 is cited for the deep/superficial alpha-beta vs gamma laminar
         claim, which is Bastos et al. 2012
     House target is 70-110 references. -->

---

## Figure captions

**Figure 1.** Predictive routing and the omission case. (Left) Predictable input is associated
with dampened feedforward gamma and elevated feedback alpha/beta activity relative to an
unpredictable context. (Right) The consequence of a predictable or unpredictable *absence* of
input is unknown: there is no feedforward drive, only internally generated activity.

**Figure 2.** Multi-area dense laminar neurophysiology (MaDeLaNe) in macaque cortex. Recordings
sampled early occipital visual cortex (V1, V2), dorsal extrastriate and motion-related cortex
(V3d, V3a, MT, MST, FST), ventral extrastriate–temporal cortex (V4, TEO), and frontal cortex
(FEF, PFC), spanning sensory, intermediate and higher-order stages of the visual–frontal
hierarchy. Recordings used 128-channel laminar probes (DiagnosticBioChips) at 30 kHz (Intan
RHD), preprocessed into LFP, MUAe and spike-sorted single units (Kilosort). Behavioural control
used MonkeyLogic (NIMH).

**Figure 3.** Sequential visual omission paradigm. Macaques performed a fixation-controlled
four-item sequence in which an expected drifting grating was either presented or omitted at a
defined position. A- and B-family blocks contained frequent full sequences and infrequent
omission sequences; the R-family served as a random control with matched omission timing. The
design preserves the temporal structure of the trial while removing the expected visual input,
so that omission-locked activity can be analysed as a missing-input event rather than a response
to a replacement stimulus. Right panels summarise spike-sorted yield by area, firing-rate
classes from grand-average activity, and functional response groups. S+ and S− denote
stimulus-excited and stimulus-suppressed units; O+ and O− denote omission-excited and
omission-suppressed units; Null units show no peak firing-rate relation to the tested context.
O+ classification required FR(omission) > FR(stimulus) and FR(omission) > FR(baseline),
Wilcoxon rank-sum, p < 0.01.

**Figure 4.** Full-sequence firing-rate traces separated by functional response group for
S = {AAAB, AXAB, AAXB, AAAX}. Traces are aligned to the onset of the first stimulus and span the
full sequence window.

**Figure 5.** *[Needs alignment.]* Sparse omission-linked spiking across the hierarchy. Should
carry per-area omission-positive prevalence with exact binomial confidence intervals and the
GLMM contrast for higher-order enrichment. [[STAT]]

**Figure 6.** *[Needs alignment.]* Omission-relative time-frequency structure for representative
lower- and higher-order areas, computed on area-segmented channels. Time base is
omission-relative, 0 ms marking the expected onset of the missing stimulus; the three
consecutive visually identical empty periods should be marked. Baseline −250 to −50 ms relative
to omission onset; colour scale in decibels. [[STAT]]

**Figure 7.** *[Needs alignment.]* Spike–field relationships by band for omission and stimulus
windows, at area and putative-laminar level. [[STAT]]

**Figure 8.** *[Needs alignment.]* Synthesis of the dissociation between sparse omission-linked
spiking and broad low-frequency field change, on area-segmented channels. Captions should avoid
implying causal coupling. [[STAT]]

---

<!--
STATUS SUMMARY FOR v1

Word counts (prose only, placeholders excluded):
  Abstract    246   target 220-280   OK
  Introduction ~940 target 800-1100  OK
  Methods    ~1,750 target 3500-4500 SHORT — needs surgery, stimulus spec, sorting params,
                                     CSD method, per-model GLMM specs
  Results    ~1,150 target 2000-2600 SHORT — gated on [[STAT]] slots
  Discussion ~1,180 target 2000-2500 SHORT — expandable now, does not depend on new numbers

Inferential families declared: GLMM (backbone), Wilcoxon rank-sum, cluster-based permutation,
Clopper-Pearson intervals = 4. Meets the <=4 house limit.

Figures: 8 slots. House standard is 5 main. Candidates for Extended Data once 5/6/7/8 are
rebuilt.

Resolved 2026-07-28: subject count is N=3. The markdown was written on a two-subject corpus
before the third subject was added, so all counts inherited from it are lower bounds.

Open conflicts: O+ prevalence (~0.4% on two subjects vs the prior draft's 4.9%, which is
synthetic — recompute on three subjects).

RESOLVED 2026-07-28 by step 3 — direction of the low-frequency effect. Settled against the
prior draft. The segmented, area-resolved census (711/711 condition files, 293,760 rows,
17 sessions) plus session-level mixed models give: pooled null in every band; a significant
DECREASE in all bands below 50 Hz in C31o; a significant INCREASE in theta, low gamma and high
gamma in V182o; nothing significant in V198o. Sustained beta elevation is not reproduced at any
level of analysis. Title, abstract, Results and Discussion updated accordingly. Receipts:
outputs/lfp_band_census_v2/{receipt.json, glmm_results.json, glmm_summary.csv};
artifacts/.lab/omission_lfp_glmm_subject_sign_reversal_20260728.json.

RESOLVED 2026-07-28 by step 3 — area aliasing. Per-channel area vector built for all 17 TFR
sessions (6,528 channels, 51 probes, 0 unresolved area tokens). Note the boundaries are an
equal-share assumption, not a measurement, and V3d/V3a are pooled for inference in consequence.
Receipt: artifacts/.lab/channel_area_vector_uniform_split_finding_20260728.json.

DEFERRED — laminar model. vFLIP2 returns "na" for about two thirds of channels, so the laminar
mixed model is skipped with a stated reason rather than fitted on the converged subset.
Note also that scripts/archive_oneoff/build_channel_layer_mapping.py had been dead since a
refactor moved it (stale REPO_ROOT); it is fixed and re-running.

Next per the agreed plan: (2) integrity and whitespace condensing, merged into (4); (4) draft v2
with the spiking [[STAT]] slots filled and figures 5-8 rebuilt.
-->
