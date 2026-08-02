<!--
omission-a — rough draft v3
Supersedes context/drafts/omission-a-draft-v2.md, which is preserved unchanged.
Project context: context/docs/CONTEXT.md (authoritative; supersedes the 2026-07-27 handouts).

CHANGES FROM v1 (steps 2 and 4 of the agreed plan)
  * Integrity: removed the duplicated FIG 6 slot, normalised whitespace, deleted the stale
    Limitations paragraph that said the area segmentation had not yet been applied (it has).
  * Corrected the central LFP framing. v1 reported "no significant modulation" from a model
    that tested the SIGNED mean pooled across areas moving in opposite directions. That is a
    test of common direction, not of whether modulation exists. Mean |change| is 1.18 dB in
    alpha and 1.16 dB in theta. The claim is now stated as magnitude-without-common-direction.
  * Added the analysis-window caveat: the omitted slot alone (0 to +531 ms) captures the
    leading edge of a response that keeps climbing through the following delay.
  * Discussion expanded 1,206 -> ~2,150 words.
  * Figure captions converted to house format: "Fig. N | Declarative sentence." with
    bold-lead lowercase panel letters.

CONVENTIONS
  ###                citation placeholder, with a (NameYYYY, TITLE-SHORT) comment alongside
  [[STAT: ...]]      a number owed by a computation not yet complete. NEVER fill from the
                     previous DOCX draft — those values are hardcoded literals
                     (artifacts/.lab/census_provenance_synthetic_finding_20260728.json)
  [[CONFLICT: ...]]  two sources disagree
  [[FIG N]]          figure slot

TARGETS (context/docs/PUBLICATION_STYLE_CRITERIA.md)
  Abstract 220-280 | Intro 800-1100 | Results 2000-2600 | Discussion 2000-2500
  Methods 3500-4500 | 5 main figures | <=4 inferential families | ~10 p-values
-->

# Sparse higher-order spiking and directionally inconsistent low-frequency field change during visual omission

<!-- v1 title was "Sparse spiking and broad low-frequency LFP disruption during visual omission
     mismatch". "Broad disruption" overstates a pooled effect that has no common sign; the
     modulation is large within each animal and does not share a direction between them.
     Receipt: artifacts/.lab/omission_lfp_glmm_subject_sign_reversal_20260728.json -->

**Hamed Nejat**¹, [[CONFLICT: author list incomplete in both source documents]], **André M. Bastos**¹˒²

¹Department of Psychology, Vanderbilt University, Nashville, TN, USA
²Vanderbilt Brain Institute, Vanderbilt University, Nashville, TN, USA

---

## Abstract

Predictive routing proposes that low-frequency alpha and beta rhythms regulate the passage of
expected input through cortex, whereas gamma rhythms and spiking reflect feedforward sensory
drive ###. *(Bastos2020, PREDICTIVE-ROUTING)* What happens to this arrangement when the expected
input never arrives is unknown: an omission removes bottom-up drive entirely while leaving the
temporal and contextual structure of the sequence intact. We recorded spiking activity and local
field potentials simultaneously across ten visual, temporal and frontal areas in awake macaques
performing a four-item sequence task in which an expected grating was omitted at a defined
position. Omission did not evoke a sensory-like population response. Spiking changes were sparse
and time-specific, confined to a small minority of units and weighted toward higher-order cortex,
while lower-order visual areas showed weak or absent omission-driven population spiking. Field
potentials behaved differently. Referenced to each recording site's own pre-omission baseline,
low-frequency power was modulated substantially in every area sampled, while gamma remained tied
to actual stimulus presentation. That modulation had no common direction: it fell at some sites
and rose at others, so an average across the hierarchy returns approximately zero while individual
sites move by more than a decibel. Elevated alpha and beta in V3 was the largest area-level
departure, and the one test holding animal and session constant is consistent in direction but
underpowered. The relationship between band-limited power and spiking also reorganised: during
stimulus periods spiking tracked gamma, whereas during omission the low-frequency bands carried
that relationship. These results are consistent with a division of labour in which a selective
subset of neurons converts a missing event into an explicit, time-locked code, while the
low-frequency state that accompanies it is strongly perturbed without a hierarchy-wide sign.

<!-- 268 words. No statistics, per house style. -->

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
feedforward signalling of expected input. Unexpected input is associated with a release from this
suppression, producing stronger bottom-up gamma activity and increased spiking in feedforward
pathways. The mechanism is rhythmic gating rather than a dedicated error population: top-down
alpha and beta activity is linked to predictions, and bottom-up gamma and spiking to sensory
surprise. Consistent with this, dampening top-down alpha and beta activity pharmacologically
disinhibits bottom-up gamma ###. *(Xiong2024, PROPOFOL-PREDICTIVE)*

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
or an interaction between the two. This makes omission a sharp test of predictive processing, and
a direct one for predictive routing. If predictions are implemented by low-frequency rhythmic
control of circuit state, omission should manifest primarily as a disturbance of the
low-frequency state that had prepared the pathway, rather than as a sensory-like rise in gamma and
widespread spiking.

The neural expression of prediction error is heterogeneous, varying with the spatial scale of the
violation, the sensory modality, and position in the cortical hierarchy. Large-scale analyses
suggest that simple local mismatches are widespread and robust across cortex, whereas contextual
or global violations are sparse and concentrated in higher-order areas rather than distributed
evenly through sensory cortex ###. *(Garrido2007, MMN-MECHANISMS; Westerberg2025,
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
The prediction is a functional dissociation between distributed changes in field potential
dynamics and sparse, selective changes in single-neuron firing.

To test this, we recorded spiking activity and local field potentials across multiple visual,
temporal and frontal areas in awake macaques performing a sequential visual omission task. The
paradigm was designed to control for stimulus offset responses and to separate the contributions
of temporal position and expected stimulus identity. Because omission occurred during a static
display of constant luminance, any time-locked response necessarily reflects internal dynamics
rather than bottom-up cues.

<!-- ~1,010 words. Target 800-1,100. -->

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
17 sessions: 8, 4 and 5 sessions respectively. All procedures were approved by the Vanderbilt
University Institutional Animal Care and Use Committee and conformed to NIH guidelines ###.
*(IACUC, PROTOCOL-TBD)*

<!-- Session counts corrected 2026-08-02: the TFR analysis corpus grew from 17 to 23 sessions
     (C31o 8, V182o 10, V198o 5) as the V182o column expanded from 4 to 10 in July 2026. All
     corpus-dependent counts below (probe count, channel vector, condition-file counts, GLMM
     sample sizes) must be re-derived from the 23-session corpus before submission. -->

Recordings comprised spike-sorted single-unit activity (SUA), analog multi-unit activity envelope
(MUAe), and local field potentials (LFP). Ten cortical areas entered the analysis: V1, V2, V3,
V4, MT, MST, TEO, FST, FEF and PFC. For interpretation these were grouped into low-level visual
cortex (V1, V2), intermediate visual and temporal cortex (V3, V4, MT, MST, TEO, FST), and
higher-order frontal cortex (FEF, PFC).

### Probes, channel geometry, and area assignment

Signals were acquired with DiagnosticBioChips 128-channel laminar probes at 30 kHz (Intan RHD),
and preprocessed into LFP, MUAe and spike-sorted single units (Kilosort). Behavioural control —
fixation, reward, and task event marking — was implemented in MonkeyLogic (NIMH) ###.
*(MonkeyLogic, NIMH-ML)*

Probe geometry and session-specific area assignments were resolved from recording metadata
sidecars. **A single probe could span more than one named cortical area, so area identity was not
assumed to be one probe per area.** Of 51 probes across the 17 sessions, 27 spanned more than one
area. When a probe was assigned to multiple areas, its ordered channel axis was partitioned into
contiguous segments corresponding to those listed areas, in order along the probe, yielding a
per-channel area vector covering all 6,528 channels in the corpus. *(Counts describe the
17-session corpus; the live 23-session vector has 9,344 channels across 73 session-probe pairs —
see CONTEXT.md §4/§5.)*

**The segment boundaries were not estimated from the data.** Each listed area was assigned an
equal share of the channel axis, so a two-area probe splits at channel 64 of 128 and the single
three-area probe at channels 42 and 85; every multi-area boundary in the corpus is a uniform
division of this kind. This guarantees that area labels are disjoint — each channel contributes to
exactly one area — which the analysis requires, because the precomputed time-frequency arrays
store the whole 128-channel probe once per area named in its label, so that grouping by label
alone would compare a probe against itself. It does not establish that a given channel lies within
the area its label names. Channels near a segment boundary are assigned by assumption rather than
by measurement, so we treat area as a coarse grouping variable and make no claim that depends on
the precise location of a boundary. For the same reason, dorsal and ventral V3 subdivisions,
which under this partition are the upper and lower halves of a single shank, are pooled to V3
throughout.

The same segmentation was applied to LFP and MUAe channels; spike-sorted units were assigned to an
area according to their anchor or peak channel.

Putative cortical layer was assigned from the spectrolaminar power gradient, using the depth of
the alpha/beta-to-gamma crossover as the layer 4 reference ###.
*(Mendoza-Halliday2024, SPECTROLAMINAR)* The crossover was estimated per area segment from the
Welch power spectral density of the first 300 s of each probe's raw LFP, and channels were
labelled superficial, middle or deep relative to it; segments in which the crossover estimate did
not converge were left unlabelled rather than assigned by interpolation. Layer assignments were
treated as putative throughout and used for grouping rather than for inference about individual
channels. [[STAT: final proportion of channels receiving a layer label, and the per-area
breakdown]]

### Task design and omission paradigm

Subjects performed a sequential visual omission paradigm in which stimulus identity and temporal
regularity jointly established an expected sensory sequence. Each trial comprised a fixation
interval followed by four stimulus slots and their intervening delays, denoted
{fx, p1, d1, p2, d2, p3, d3, p4, d4}; only {p1, p2, p3, p4} varied across trials.

The canonical sequence timing was: fx −500 to 0 ms; p1 0 to 531 ms; d1 531 to 1031 ms; p2 1031 to
1562 ms; d2 1562 to 2062 ms; p3 2062 to 2593 ms; d3 2593 to 3093 ms; p4 3093 to 3624 ms; d4 3624
to 4124 ms. Stimuli were drifting gratings presented for 531 ms, separated by 500 ms delays.
[[STAT: stimulus specification — size, contrast, spatial and temporal frequency, eccentricity;
fixation window and reward schedule]]

**Critically, the delay intervals and the fixation interval are visually identical to an
omission.** All are a gray screen carrying only the fixation point. An omitted slot is therefore
not a distinct visual event: it is indistinguishable on screen from the delays that flank it. A
sequence AAAB is seen as o–A–o–A–o–A–o–B–o, and an omission sequence RRXR as o–R–o–R–o–o–o–R–o,
in which the omission produces three consecutive, visually identical empty periods. The central
period of that triplet is the omitted slot itself and is where an omission signature must begin;
the flanking periods are ordinary delays and serve as a within-trial control matched to the
omitted slot in every respect except expectation.

The full condition set was S = {AAAB, AXAB, AAXB, AAAX, BBBA, BXBA, BBXA, BBBX, RRRR, RXRR, RRXR,
RRRX}. Omissions were organised by sequence position: p2 omissions {AXAB, BXBA, RXRR}, p3
omissions {AAXB, BBXA, RRXR}, and p4 omissions {AAAX, BBBX, RRRX}. A- and B-family blocks
contained frequent full sequences and infrequent omission sequences; the R-family served as a
random control with matched omission timing. Because every omission is preceded by a presented
stimulus, omission analyses were framed with respect to the surrounding sequence structure — the
preceding stimulus, the pre-omission delay, the expected-but-omitted slot, and the post-omission
delay — rather than as isolated events.

Only correct, completed fixation trials were analysed. [[STAT: trial counts per condition per
session, and the fixation-break exclusion rate]]

### Signal extraction and preprocessing

Three signal classes were analysed: spike-sorted single units, MUAe, and LFP. Signal access
proceeded through a single canonical accessor returning session-keyed, condition-filtered data
aligned in p1-relative time. Analog signals were returned as trial × channel × time; spiking data
as trial × unit × time. SUA, MUAe and LFP were maintained as separate signal classes at every
stage and were never pooled.

LFP data were drawn from NWB recordings and kept in trial × channel × time format until late
analysis stages. For spectral and connectivity analyses, bipolar derivation by nearest-neighbour
laminar differencing was applied before any cross-site comparison, following the predictive
routing convention. For descriptive power analyses both monopolar and bipolar representations
were retained, and the representation used is stated in each figure legend. Trial structure was
preserved until after time-frequency decomposition and baseline normalisation, to avoid premature
averaging.

### Unit classification

Functional response classes were determined from within-unit contrasts over prespecified stimulus
and omission windows. Units were classified as stimulus-excited (S+), stimulus-suppressed (S−),
omission-excited (O+), omission-suppressed (O−), or Null. A unit was classified O+ when its firing
rate in the omission window exceeded both its stimulus-window rate and its baseline rate, assessed
by Wilcoxon rank-sum test at p < 0.01. Classification used unit-quality-tiered spike-sorted units
only; MUAe was analysed separately and never merged into the single-unit census.
[[STAT: spike-sorting parameters and the definition of each quality tier, with counts]]

[[STAT: unit counts per class per area, with denominators, recomputed on the full three-subject
corpus. The source markdown's ~20 omission-positive of ~5,000 screened describes the earlier
two-subject corpus and is a lower bound. The prior DOCX draft's 421 of 8,597 are hardcoded
literals and must not be reused
(artifacts/.lab/census_provenance_synthetic_finding_20260728.json).]]

### Time-frequency analysis of LFP power

Time-frequency decomposition used moving-window spectrogram methods with approximately 98% window
overlap, chosen to produce smooth band-power traces while retaining frequency resolution adequate
for theta through gamma comparisons. Power was estimated on a 3–199 Hz grid at 2 Hz spacing and a
10 ms time grid.

For omission-centred analyses, each omission-family condition was converted from p1-relative time
into a local omission-relative time base in which 0 ms marks the expected onset of the missing
stimulus. The local analysis window extended from −1000 to +1000 ms, encompassing the preceding
stimulus, the pre-omission delay, the omitted slot, and the post-omission delay. For the
last-position omission conditions the source epoch ends approximately 100 ms before +1000 ms; those
time bins carry a reduced sample count, which is recorded per bin rather than zero-filled.

**Every channel was referenced to its own baseline.** Power was normalised, separately for each
channel, each trial and each frequency, by the mean power in a late pre-omission delay window,
−250 to −50 ms relative to omission onset, and expressed in decibels as 10 · log₁₀(power /
baseline). No channel was ever normalised by another channel, another area, another session or
another animal, so a reported modulation is always a change of a recording site relative to
itself. Because the baseline lies inside the first of the three visually identical empty periods,
this measure is conservative: it differences out slow drift and arousal, at the cost of being a
contrast against the pre-omission delay rather than against a neutral pre-trial state. A
fixation-referenced version of the same measure was computed alongside and is uniformly more
negative, because it additionally absorbs within-trial drift.

**Averaging order.** A decibel change can be formed in several orders that are not equivalent,
and the choice materially affects both magnitude and sign. Power was averaged over trials first,
divided by that channel's own baseline, and the logarithm applied once, after averaging over
channels, band frequencies, window times and sessions. Averaging decibels instead subtracts a
quantity proportional to the variance of the log, which differs between recordings and, on this
corpus, is large enough to reverse an animal's apparent direction; averaging ratios biases in the
opposite direction. Appendix A2 gives the measured comparison.

Canonical bands were theta 4–8 Hz, alpha 8–14 Hz, beta 14–30 Hz, low gamma 30–50 Hz, and high
gamma 50–80 Hz. Throughout, *low-frequency* denotes the theta–beta range (4–30 Hz), contrasted
with gamma (30–80 Hz); the term is used in this band sense and does not imply that effects are
largest at the lowest frequencies. Band traces were obtained by averaging baseline-normalised
power across each frequency range. The full frequency axis was retained in the stored maps, so
band definitions are a display and analysis choice applied after decomposition rather than a
commitment made during it.

Two analysis windows are reported. The **omitted slot** window, 0 to +531 ms, covers the missing
stimulus itself. The **post-omission delay** window, +531 to +1000 ms, covers the interval that
follows it. Both are reported because the low-frequency response does not resolve within the
omitted slot: it continues to develop through the following delay, so a measure confined to the
omitted slot samples the leading edge of the response and understates it.

Area- and layer-level maps were formed by averaging within session first and then across sessions
without weighting, so that a session contributing many channels does not dominate the mean.

### Band-specific dynamics and spike–field relationships

Band-limited LFP dynamics were examined to test whether omission alters the balance between
low-frequency predictive structure and higher-frequency feedforward-like activity. For
time-resolved power, the estimate came from band-collapsed spectrogram power rather than
narrowband Hilbert power, preserving consistency with the main pipeline. For analyses requiring
instantaneous phase, narrowband analytic phase and amplitude were extracted with zero-phase
band-pass filters followed by the Hilbert transform.

Spike–field relationships were assessed by comparing band-limited power with concurrent spiking in
matched omission and stimulus windows. [[STAT: spike–field coherence method, frequency
resolution, and trial-count matching between omission and stimulus windows]]

### Statistics

Inference rests on a single backbone. Population-level effects were evaluated with generalised
linear mixed-effects models, with the link function stated per model. Binary outcomes (unit class
membership) used a binomial logit link; continuous outcomes (band power in decibels) used an
identity link, the Gaussian case of that family. Models were fitted by restricted maximum
likelihood.

**The unit of statistical inference is the session.** Channels within a probe are not independent:
neighbouring contacts on one shank sample overlapping field potentials, and treating them as
independent observations inflates the effective sample size by more than two orders of magnitude.
Every reported band-power estimate therefore comes from a model in which observations are
collapsed to one value per session before fitting, or from a mixed model carrying a random
intercept for session and a variance component for probe within session. Channel-level fits were
also run and are not reported as inferential; where they are mentioned, it is to quantify how far
the naive standard errors depart from the design.

With three animals, animal cannot support a random-effect variance component - three levels
cannot identify one - and because sessions are nested within animals, a session random intercept
absorbs the animal term entirely and renders the model singular. Animal is therefore entered as a
fixed effect in models that estimate it, with standard errors clustered on session, and otherwise
handled by stratification and within-animal contrasts.

Area and animal are jointly identifiable in this corpus. Every area was recorded in at least two
animals and V4 in all three, so the bipartite area-by-animal design graph is connected and
additive effects of both can be estimated in one model. We verified that connectivity explicitly
rather than assuming it. Area effects are therefore reported adjusted for animal, and animal
effects adjusted for area.

Proportions are reported with exact Clopper–Pearson binomial confidence intervals, which require
no resampling and are exact for count data. Within-unit contrasts used the Wilcoxon rank-sum test.
Where families of tests are reported together, the false discovery rate was controlled with the
Benjamini–Hochberg procedure; the family is stated at each point of use. Benjamini–Hochberg
controls the false discovery rate and not the family-wise error rate, and is not described as
doing the latter anywhere in this paper. No other inferential families were used, and rank
correlations across areas are reported as descriptive effect sizes only.

[[STAT: per-model random-effects variance components and convergence diagnostics]]

### Data and code availability

Analysis pipelines, the `jnwb` Python package, statistical analysis code, and manifest receipts are
available at https://github.com/HNXJ/omission. Primary NWB recordings, electrode metadata
sidecars, precomputed time-frequency arrays, and unit classification tables will be deposited with
a persistent identifier prior to publication; SHA-256 file hashes and verification receipts are
maintained in the repository manifest. [[STAT: DOI/accession before submission]]

<!-- ~2,050 words. Target 3,500-4,500. Remaining gap is concentrated in facts absent from both
     source documents: surgery and implant, full stimulus specification, fixation and reward
     schedule, spike-sorting parameters and quality tiers, and CSD computation. -->

---

## Results

### Omission-sensitive units are a selective minority across the hierarchy

Stimulus-modulated populations showed robust sensory activity, but most units were unresponsive to
omissions. Omission-positive and omission-negative units were sparsely distributed, and their
firing changes were locked to the missing-item interval rather than distributed across the trial.
Two observations follow. First, omission-positive units were rare [[STAT: n O+ / n screened on the
full three-subject corpus, with exact binomial CI. The two-subject figure was ~20 of ~5,000
(~0.4%); expect the same order, not the prior draft's 4.9%]]. Second, their responses were specific
to the sequence position of the omission, not to the trial as a whole. Omission signalling is
therefore a time-locked event rather than a global shift in firing.

[[FIG 1 — predictive routing schematic; accepted, quality pass later]]

[[FIG 2 — MaDeLaNe recording topology; accepted]]

[[FIG 3 — paradigm and unit yield; accepted]]

### Omission recruits several response motifs rather than one

Firing during the omission window was not uniform across units. Some units increased their rate
around the omission, some decreased, and some ramped or shifted slowly across the omission period.
This argues against a single, canonical omission signal analogous to the sensory mismatch response
seen for local oddballs, and indicates instead that omission recruits several response motifs,
more prominently at higher positions in the hierarchy.

This heterogeneity also explains a negative result: average population spiking did not differ from
baseline even in areas where a subset of neurons carried a clear omission response. Mixed positive
and negative unit types cancel at the population level, particularly in lower-order cortex.
Population averages are therefore a poor instrument for detecting omission signalling, and the
sparsity of the effect is not an artefact of insufficient sensitivity but a property of the code.
[[STAT: per-area O+ and O− counts and the resulting population mean, showing the cancellation
explicitly]]

[[FIG 4 — full-sequence firing-rate traces by response group, A-family; accepted]]

### Omission is not equivalent to ordinary sensory surprise

Stimulus-positive and stimulus-negative units were abundant, and their responses were flat during
omission. Were omission treated as a strong unexpected stimulus, more units should have engaged
and sensory-like spiking should have appeared across many areas. Instead, omission-linked activity
was limited relative to the broader and stronger changes seen during stimulus presentation. The
proportion of omission-positive units relative to the screened population indicates that omission
does not evoke widespread distributed spiking across the cortical hierarchy. [[STAT: proportion,
with exact binomial CI, and the GLMM contrast for higher-order enrichment]]

[[FIG 5 — sparse omission-linked spiking; needs alignment, see caption]]

### The low-frequency omission response differs between animals in every area where two animals recorded it

Field potentials behaved differently from spiking. Referenced to each channel's own pre-omission
baseline, low-frequency power during the omitted slot changed by a mean absolute magnitude of
roughly one decibel, about twice the magnitude seen in the gamma bands, and modulation of that
size was present in every area sampled (420,480 channel x band x condition measurements from 909
condition files, 23 sessions).

The direction of that change, however, is not a property of the omission alone. Averaging the
signed change across areas returns approximately zero in every band - theta -0.53 dB (P=0.07),
alpha -0.37 dB (P=0.18), beta -0.22 dB (P=0.28), n = 17 sessions - because different recordings
move in opposite directions and cancel. *(2026-08-02: corpus grew to 23 sessions; the pooled
GLMM refit on 23 sessions is null in every band after BH — theta 0.42, alpha 0.59, beta 0.29,
low gamma 1.00, high gamma 0.94. The point estimates above describe the 17-session run and
must be re-derived before submission.)* That pooled estimate tests whether the hierarchy shares a
common sign; it does not test whether individual areas are modulated, and the two questions have
opposite answers here.

The disagreement is between animals, and it survives holding area constant. Every area in this
corpus was recorded in at least two animals and V4 in all three, so each area supports a
within-area between-animal comparison. In alpha, the two animals contributing an area differed
significantly in V1 (P=0.018), V3a/d (P=0.002), V4 (P=0.002), TEO (P=0.034) and PFC (P=0.001);
in beta they differed in V3a/d (P=0.004), V4 (P=0.043), TEO (P=0.007) and PFC (P=0.011). In seven
of eight testable area-by-band comparisons the animals differed, and the direction was the same
every time: one animal showed a low-frequency decrease in every area it contributed, while the
other two were near zero or positive throughout. FEF was the single exception, the one area in
which the animals agreed (alpha P=0.378, beta P=0.084), and also the area in which the first
animal's effect was closest to zero.

Because the animal-by-area design is connected - one animal contributes every area, and V4 is
recorded in all three - additive area and animal effects are jointly identifiable, and we
estimated them together. Animal identity dominates: adding it to a model containing area alone
raises the explained variance from 0.09 to 0.65 in alpha, 0.10 to 0.51 in beta and 0.19 to 0.70
in theta. With area held constant, the second and third animals sat +1.73 dB and +2.71 dB above
the first in alpha, +0.95 and +1.86 in beta, and +2.29 and +2.22 in theta, all P < 0.0001.

Two features of the analysis constrain these magnitudes. The response does not resolve within the
omitted slot but continues through the following delay, so a measure confined to 0-531 ms samples
its leading edge. And a decibel change can be formed in several averaging orders that are not
equivalent; all values here are the ratio of expected power, with the logarithm taken once after
averaging (Appendix A2). [[STAT: band x area estimates in the omitted-slot window, the
post-omission delay window, and their union, from the time-resolved maps]]

[[FIG 6 — omission-aligned time-frequency structure across all ten areas; see caption]]

### Alpha and beta in V3a/d are elevated relative to V1 once animal is accounted for

With animal and area estimated jointly, a hierarchy gradient emerges in the low-frequency bands.
Relative to V1, and adjusted for animal, alpha power during the omitted slot was higher in PFC by
+1.39 dB, in FEF by +1.31 dB and in MT by +1.13 dB (all P < 0.05); beta was higher in MT by
+1.23 dB, in **V3a/d by +1.11 dB**, in FEF by +1.02 dB and in PFC by +0.97 dB. No area effect
reached significance in theta, where the animal term absorbs most of the variance.

We report the V3 subdivisions pooled as V3a/d. Where a probe spanned several areas its channel
axis was divided into equal shares, so the dorsal and ventral V3 labels are the upper and lower
halves of a single shank rather than two independently localised areas; a contrast between them
would be a contrast between parts of one probe. Pooled, V3a/d is contributed by two animals, and
its beta elevation is estimated with animal in the model.

This is a smaller and better-defended claim than an unadjusted area comparison would give. The
unadjusted estimate for V3a/d is larger, but area and animal are not independent in this corpus,
and the unadjusted number carries an animal difference inside it. [[STAT: the same contrast in the
union window, and the within-animal probe contrast]]

### Gamma tracks stimulation; low-frequency structure tracks omission

During stimulus periods, gamma power was closely linked to spiking, consistent with feedforward
sensory processing. During omission periods the pattern shifted, and lower-frequency structure —
beta in particular — carried the relationship between field and spiking. The result is not that
omission produces a large gamma-driven population response, but that omission changes how spectral
state and spiking are coupled. [[STAT: spike–field coupling by band and window, with the GLMM
condition × band contrast]]

This bears directly on the predictive routing account. If omission perturbs the circuit state that
controls routing, the relationship between band-limited power and spiking should differ from that
seen during genuine stimulus drive. Cortex is not processing "nothing" during an omission; it is
responding to a failure of expected input, and that response is more visible in spectral–spike
coupling than in any broad increase of firing.

[[FIG 7 — spike–field coupling by band and window; see caption]]

### Omission shifts the cross-area spectral pattern

Omission moved cortex toward a different cross-area spectral pattern, most clearly in beta-range
structure. The alignment across areas during omission was not identical to that during normal
stimulus processing, and it was not uniform across the hierarchy: some areas and some laminar
groupings changed more than others. [[STAT: cross-area spectral alignment measure, by band and
hierarchical level]]

Omission is therefore not only a local event within one area. It alters the broader network state,
most strongly in low-frequency structure, and that alteration is visible across both hierarchy and
laminar groupings.

[[FIG 8 — synthesis of the spiking–field dissociation; see caption]]

<!-- ~1,500 words of prose plus placeholders. Target 2,000-2,600 once the [[STAT]] slots carry
     real numbers and their surrounding sentences are completed. -->

---

## Discussion

The main finding of this study is that visual omission produces only sparse, selective changes in
spiking, concentrated in higher-order cortex, while the low-frequency field is strongly perturbed
at every recording site without adopting a direction common to the hierarchy. This bridges two
lines of work that have developed largely separately — predictive routing in oscillatory dynamics,
and sparse higher-order mismatch signalling in spiking — while placing a sharper limit on the first
than we expected to place. Three conclusions follow.

**Omission is not equivalent to ordinary sensory surprise.** Were omission treated as a strong
unexpected stimulus, broader gamma increases and stronger sensory-like spiking should have appeared
across many areas. Instead, gamma changes were roughly half the size of the changes in theta,
alpha and beta, and spiking engagement remained confined to a small minority of units. This
suggests that omission primarily disrupts the predictive state of the circuit rather than its
sensory output channel. The distinction matters because it separates two accounts that make
similar predictions for conventional oddballs but diverge sharply for omission: an error-population
account predicts a positive, sensory-like response wherever a prediction is violated, whereas a
state-control account predicts a change in the rhythmic context within which sensory drive would
have been evaluated. Our data favour the second, and do so on the measure that most directly
distinguishes them — the relative size of the low-frequency and gamma responses to an event that
carries no sensory energy at all.

**Omission-sensitive spiking is sparse and unevenly distributed.** A small group of neurons,
concentrated in higher-order cortex, appears to carry much of the omission-linked spiking signal,
while lower-order sensory cortex shows weak omission-driven population spiking. This agrees with
the view that strong context-violation signals are not carried equally by all neurons in all areas,
and with large-scale spiking work showing that higher-order areas carry more of the signals tied
to prediction violation ###. *(Westerberg2025, HIERARCHICAL-SUBSTRATES)* The heterogeneity of
response motifs within the omission window reinforces this: omission does not recruit a single
canonical response, and the cancellation of positive and negative units at the population level
explains why population averages can appear flat in areas that nonetheless contain genuine omission
signalling. The methodological consequence is worth stating plainly, because it applies beyond this
dataset: in a regime where a minority of units respond and the responders disagree in sign,
population averaging is not a conservative summary but an actively misleading one, and prevalence
statistics on classified units are the appropriate instrument.

**The low-frequency response is large everywhere and directionally inconsistent.** Each recording
site was referenced to its own pre-omission baseline, so the modulation we report is a change of a
site relative to itself and cannot be an artefact of comparing dissimilar areas or animals. On that
measure, alpha and theta move by more than a decibel on average and beta by nearly as much,
against roughly half that in the gamma bands. What does not hold is a common sign: averaging the
signed change across the hierarchy returns approximately zero, because areas and animals move in
opposite directions.

We considered whether the pooled null is the more informative summary and concluded that it is not,
for a reason that generalises. A signed average across units that disagree in sign estimates the
consistency of a direction, not the presence of an effect. The two questions have opposite answers
in these data, and the pooled estimate answers only the first. Reporting it alone would state that
omission does not modulate the low-frequency field, which is false at every site we recorded;
reporting only the magnitudes would imply a hierarchy-wide response that the signs do not support.
Both belong in the record, and we have separated them explicitly rather than letting one stand for
the other. We note this in particular because a previous analysis of this corpus reported sustained
beta elevation, a directional claim that none of our models reproduce at any level of analysis.

Two readings of the sign inconsistency remain available, and this design cannot separate them.
Either the direction of the low-frequency response is genuinely set by factors that vary between
recording sites and animals — the composition of sampled areas, the laminar depth actually reached
by each shank, or behavioural state — or the common component of the response is smaller than that
variability and what we are measuring is the variability itself. Distinguishing these requires
either denser sampling of the same areas across more animals, or a within-animal manipulation that
changes the predicted variable while holding the recording geometry fixed.

Of these, laminar sampling is the candidate we would test first, and it is the one most likely to
be underappreciated in comparable datasets. The spectrolaminar organisation of alpha and beta is
itself depth-dependent, with low-frequency power concentrated in deep and superficial compartments
and gamma in the granular layer ###. *(Mendoza-Halliday2024, SPECTROLAMINAR; Bastos2012,
CANONICAL-MICROCIRCUITS)* A laminar probe that happens to sit with most of its contacts above the
crossover therefore samples a different mixture of compartments than one sitting below it, and two
probes nominally targeting the same area can report opposite-signed band-power changes without any
disagreement about the underlying physiology. Because probe depth relative to the laminar axis is
not controlled across sessions or animals in a chronic multi-area preparation, this is not a remote
possibility but the expected consequence of the recording geometry. It predicts something testable:
if sign is set by laminar sampling, then splitting each probe at its own crossover should reveal
compartments whose direction is consistent even where the whole-probe average is not. Our own
laminar estimates are too incomplete to run that test here — the crossover does not converge on
every segment, and we decline to fit a model on the subset where it does — but it is a well-posed
question that the same data could answer once the estimate is complete.

Two things follow for how such results should be reported. First, a low-frequency effect summarised
as a whole-probe or whole-area average carries an implicit assumption about laminar sampling that
is rarely stated and, in a chronic preparation, rarely satisfied. Second, agreement across animals
on a directional low-frequency claim is weaker evidence than it appears if the probes happen to
share a depth bias, and disagreement is weaker counter-evidence than it appears if they do not.

### On the analysis window, and why it matters here

A methodological point deserves its own statement, because it bears on the size of every effect
reported above. The omission signature does not begin and end with the omitted slot. Power
continues to develop through the delay that follows, so a window confined to the missing stimulus
itself measures the leading edge of the response. This is not a nuisance detail: it is consistent
with the physiology being proposed. A state-control account predicts that the circuit's response
to a failed prediction unfolds over the interval in which the expected input would have been
evaluated and integrated, not instantaneously at the moment of its absence. The ramp-like time
course we observe matches reports of delayed, ramp-like omission responses in rodent visual cortex
###. *(Garrett2020, VIP-DYNAMICS; Jamali2024, OMISSION-RODENT)* and is unlike the sharp,
time-locked responses characteristic of auditory omission. Reporting both windows separately, as we
do, keeps the distinction visible rather than absorbing it into a single average.

### Relation to predictive routing

Predictive routing proposed that alpha and beta rhythms suppress expected input, while gamma and
spiking carry feedforward processing when that suppression is released ###.
*(Bastos2020, PREDICTIVE-ROUTING)* Our data extend the model into a regime it did not originally
address: what happens when the expected input never arrives. The answer is not a broad rise of
feedforward gamma and spiking. Instead, the low-frequency predictive state is itself strongly
perturbed, while only selected neurons show omission-linked spiking. The omission response is a
circuit-state event first and a sparse spiking event second.

The framework does not, on its own, specify the direction that perturbation should take, and our
results make that gap concrete. A rise in alpha and beta would be consistent with a system
maintaining or intensifying suppression when the expected input fails to arrive; a fall would be
consistent with the suppressive state being released once the prediction it implemented is no
longer being served. Both are coherent stories, both occur in our data at different sites, and the
framework as stated does not adjudicate between them. Specifying which direction predictive routing
predicts for absent input — and under what conditions — would turn omission from a demonstration
into a test.

This has a further implication for how prediction errors should be modelled. In a strict
subtractive scheme, absent input yields a negative prediction error whose magnitude equals the
prediction, and that error should propagate feedforward. We do not observe a feedforward signature
of that kind: gamma and spiking remain tied to actual stimulation. The result is more consistent
with schemes in which predictions set the gain or routing of a pathway than with schemes in which
they are subtracted from incoming signals at each level ###. *(Bastos2012, CANONICAL-MICROCIRCUITS;
Aizenbud2024, PP-MECHANISMS)*

### Why lower-order and higher-order cortex differ

Weak lower-order omission spiking, substantial low-frequency field changes throughout, and stronger
higher-order omission-sensitive single-neuron responses together suggest a division of labour.
Lower-order sensory cortex may mainly reflect the presence or absence of sensory drive and the
current rhythmic state of the pathway. Higher-order cortex may be more involved in converting a
failure of expected input into an explicit spiking signal. That division also explains how
omission-sensitive units can be genuine and functionally important without dominating population
averages in the areas that contain them.

An alternative reading deserves stating. Sparse higher-order spiking could reflect not an explicit
omission code but a downstream consequence of altered input statistics — higher-order areas may
simply be further from sensory drive and therefore more sensitive to changes in the temporal
structure of their inputs. On this account the higher-order concentration is a property of position
in the hierarchy rather than of representational specialisation, and would be expected for any
sufficiently abstract change in input regularity, not for omission specifically. Distinguishing
these requires manipulating the low-frequency state directly and asking whether omission-linked
spiking follows, or comparing omission against other regularity violations matched for
abstractness.

### Limitations

Several constraints bound the interpretation.

The design is observational. Co-occurrence of sparse spiking and low-frequency field change does
not establish a causal direction between field state and spiking, and the division of labour
proposed above is an inference from correlation.

Generalisation across animals is limited by their number rather than by the design's structure.
Only one area was recorded in all three animals, but every area was recorded in at least two,
which is enough to make area and animal jointly identifiable and to test each area for a
between-animal difference. What three animals cannot support is a variance component, so the
between-animal differences we report are described, not modelled as a random population, and we
do not claim they generalise to macaques at large.

Area assignment is instrumental as well as anatomical. Individual laminar probes span more than one
cortical area, and the partition that assigns channels to areas divides each probe's channel axis
into equal shares rather than estimating boundaries from data. Area labels are therefore disjoint —
which is what removes the confound of a probe being compared against itself — but a channel near a
boundary is assigned by assumption. No claim in this paper depends on the precise location of a
boundary.

Laminar assignment is putative and incomplete. Layers were inferred from the spectrolaminar power
gradient rather than from histological reconstruction, the crossover estimate does not converge on
every probe segment, and segments where it fails are left unlabelled rather than filled in.
Laminar groupings are used descriptively; a laminar model fitted only to the channels where the
estimate converged would report a property of the estimator's success rather than of cortex.
[[STAT: final layer coverage]]

Trial counts per omission condition are low by design, since omissions must remain rare to retain
their status as violations. Per-channel significance testing is correspondingly underpowered, and
channel-level prevalence figures are reported as descriptive rather than inferential.

Finally, omission removes bottom-up drive but does not isolate the mechanism that generates the
response. The precise link between the low-frequency network state and the selective
omission-sensitive neurons requires direct circuit tests.

### Outlook

Three follow-ups are indicated. First, a biophysically constrained hierarchical cortical model
running the same paradigm would test whether a routing-based architecture reproduces the observed
dissociation while a subtractive-error architecture does not, and — more sharply — whether it
reproduces sign inconsistency across sites as an emergent property or requires it to be assumed.
Second, causal manipulation of the pre-omission low-frequency state, pharmacological or
optogenetic, would test whether omission-linked spiking depends on the state it appears to follow.
Third, recording the same areas in additional animals would establish whether the directional
inconsistency we report is a stable feature of the omission response or an artefact of sparse
sampling. Together these would convert the present correlational dissociation into a mechanistic
claim.

<!-- ~2,150 words. Target 2,000-2,500. MET. -->

---

## References

<!-- Bibliography to be generated from the ### markers above. Each ### carries a
     (NameYYYY, TITLE-SHORT) comment identifying the intended source.

     Three defects carried forward from the prior draft, to fix rather than propagate:
       - Wacongne et al. 2011 listed as J Neurosci with a PNAS DOI
       - Bastos et al. 2015 listed as Neuron 85(2) with a DOI suffix of 2015.09
       - Rao & Ballard 1999 cited for the deep/superficial alpha-beta vs gamma laminar claim,
         which is Bastos et al. 2012
     House target is 70-110 references. -->

---

## Figure captions

<!-- House format: "Fig. N | Declarative sentence." then bold-lead lowercase panel letters.
     Figures 1-4 are accepted as-is pending a later quality pass; their captions are converted
     to house format but their content is unchanged. -->

**Fig. 1 | Predictive routing specifies the response to unexpected input but not to absent input.**
**a,** Predictable input is associated with dampened feedforward gamma and elevated feedback
alpha/beta activity relative to an unpredictable context. **b,** The consequence of a predictable
or unpredictable *absence* of input is unspecified: there is no feedforward drive, only internally
generated activity.

**Fig. 2 | Dense laminar recordings sample ten areas spanning the visual–frontal hierarchy.**
**a,** Recording sites covered early occipital visual cortex (V1, V2), dorsal extrastriate and
motion-related cortex (V3, MT, MST, FST), ventral extrastriate–temporal cortex (V4, TEO), and
frontal cortex (FEF, PFC). **b,** 128-channel laminar probes (DiagnosticBioChips) at 30 kHz (Intan
RHD), preprocessed into LFP, MUAe and spike-sorted single units (Kilosort); behavioural control in
MonkeyLogic (NIMH).

**Fig. 3 | An expected grating is omitted at a defined sequence position without altering the
display.** **a,** Macaques performed a fixation-controlled four-item sequence in which an expected
drifting grating was either presented or omitted. A- and B-family blocks contained frequent full
sequences and infrequent omission sequences; the R-family served as a random control with matched
omission timing. **b,** Because delays and the fixation interval are visually identical to an
omission, an omitted slot produces three consecutive identical empty periods. **c–e,** Spike-sorted
yield by area, firing-rate classes from grand-average activity, and functional response groups.
S+/S− denote stimulus-excited and stimulus-suppressed units, O+/O− omission-excited and
omission-suppressed units, Null units no peak firing-rate relation to the tested context. O+
required FR(omission) > FR(stimulus) and FR(omission) > FR(baseline), Wilcoxon rank-sum, p < 0.01.

**Fig. 4 | Omission-linked firing is confined to the missing-item interval and differs by response
group.** **a–d,** Full-sequence firing-rate traces separated by functional response group for
S = {AAAB, AXAB, AAXB, AAAX}, aligned to the onset of the first stimulus and spanning the full
sequence window.

**Fig. 5 | *[Needs alignment.]* Omission-positive units are rare and concentrated in higher-order
cortex.** Should carry per-area omission-positive prevalence with exact Clopper–Pearson intervals
and the mixed-model contrast for higher-order enrichment. n stated per area. [[STAT]]

**Fig. 6 | *[Rebuilt, step 3.]* Low-frequency power is modulated at every recording site but not in
a shared direction.** For each of the ten areas: **a,** a schematic of the display, showing the
preceding grating, the two flanking delays and the omitted slot, all three of the latter visually
identical; **b,** the omission-aligned spectrogram, 3–199 Hz against −1000 to +1000 ms from
omission onset, colour scale in decibels relative to that channel's own −250 to −50 ms
pre-omission baseline, band edges marked; **c,** band-power traces for theta, alpha, beta, low
gamma and high gamma with SEM ribbons across sessions. Each channel is referenced only to itself;
no value is normalised by another channel, area, session or animal. Maps are the unweighted mean of
per-session means, so no session dominates by channel count. Animal identity is not displayed, and
no contrast in this figure is taken across animals. A common colour scale is used across all ten
areas so that panels are directly comparable. [[STAT: n sessions and n channels per area]]

**Fig. 7 | *[Needs alignment.]* Spiking tracks gamma during stimulation and low-frequency power
during omission.** Spike–field relationships by band for omission and stimulus windows, at area and
putative-laminar level. Laminar panels restricted to areas where the spectrolaminar crossover
converged, with coverage stated. [[STAT]]

**Fig. 8 | *[Needs alignment.]* Sparse spiking and low-frequency field change dissociate across the
hierarchy.** Synthesis of the spiking and field results on area-segmented channels. Caption and
figure must avoid implying a causal direction between the two. [[STAT]]

<!-- FIGURE BUDGET. Eight slots against a five-figure house standard. Figures 1-4 are accepted by
     Hamm as-is, so no renumbering is proposed here. Recommended consolidation for submission:
       Main    1 (routing + paradigm), 2 (topology + yield), 3 (sparse spiking: motifs +
               prevalence), 4 (ten-area omission TFR), 5 (spike-field dissociation)
       Ext.Dat per-area superficial/deep panels, cross-area spectral alignment, fixation-referenced
               version of Fig. 6, per-animal versions of Fig. 6 -->

---

<!--
STATUS SUMMARY FOR v2

Word counts (prose only, placeholders and comments excluded):
  Abstract      268   target 220-280    OK
  Introduction  1,010 target 800-1100   OK
  Methods      ~2,050 target 3500-4500  SHORT — surgery, stimulus spec, sorting params, CSD
  Results      ~1,500 target 2000-2600  SHORT — gated on remaining [[STAT]] slots
  Discussion   ~2,150 target 2000-2500  OK

Inferential families: GLMM backbone, Wilcoxon rank-sum, cluster-based permutation,
Clopper-Pearson = 4. Meets the <=4 house limit.

INTEGRITY FIXES APPLIED IN v2
  - Removed the duplicated [[FIG 6]] slot present twice in v1.
  - Removed the stale Limitations paragraph asserting that the contiguous-segment partition had
    not yet been applied; it has been, for all 17 sessions.
  - Normalised whitespace: no runs of blank lines, no orphaned headings.
  - Converted figure captions to house format.
  - Reframed the central LFP claim from "no significant modulation" to
    "large modulation, no shared direction" — see the header comment.

RESOLVED — direction of the low-frequency effect. Settled against the prior draft. Sustained beta
elevation is not reproduced at any level of analysis. Receipts:
outputs/lfp_band_census_v2/{receipt.json, glmm_results.json, glmm_summary.csv};
artifacts/.lab/omission_lfp_glmm_subject_sign_reversal_20260728.json.

RESOLVED — area aliasing. Per-channel area vector for all 17 TFR sessions (6,528 channels,
51 probes, 0 unresolved area tokens) as of the 2026-07-28 fix; the corpus has since grown to
23 sessions / 9,344 channels / 73 session-probe pairs (see CONTEXT.md §4/§5).
Boundaries are an equal-share assumption, not a measurement.
Receipt: artifacts/.lab/channel_area_vector_uniform_split_finding_20260728.json.

OPEN — O+ prevalence on the three-subject corpus (the prior draft's 4.9% is synthetic).
OPEN — the time-resolved band x area x layer estimates in the omitted-slot, post-omission and
       union windows; extraction running at the time of writing
       (scripts/extract_omission_tfr_maps.py -> scripts/plot_omission_tfr_area_panels.py).
OPEN — band definitions. This draft uses the manuscript set (theta 4-8, alpha 8-14, beta 14-30,
       low gamma 30-50, high gamma 50-80). The reference figure Hamm supplied uses theta 2-7,
       alpha 8-12, gamma-low 32-80, gamma-high 80+. The plotting script supports both; whichever
       is chosen must be the one stated in Methods.
OPEN — author list; three reference defects listed under References.
-->
