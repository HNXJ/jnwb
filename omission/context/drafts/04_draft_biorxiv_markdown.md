<!--
Converted from: omission-2026-draft-n.pdf
Output: 04_draft_biorxiv_markdown.md
Figure assets: 04_draft_biorxiv_markdown_assets/
Status: markdown conversion of the draft PDF; content-level scientific claims remain as in the source draft.
-->

# Sparse spiking and broad low-frequency LFP disruption during visual omission mismatch

**Hamed Nejat**, Dept. of Psychology, Vanderbilt University; ...; ...; ...;  
**Andre Bastos**, Dept. of Psychology, Vanderbilt University; Vanderbilt Brain Institute

## Abstract

Predictive routing proposes that low-frequency alpha/beta (~8-30 Hz) rhythms regulate expected input, whereas gamma (>40 Hz) rhythms and spiking reflect feedforward sensory drive. We tested this using a visual omission task in which an expected stimulus was absent but sequence timing and context were preserved. Across multi-area laminar recordings in visual and frontal cortex, omission did not evoke a sensory-like population response. Spiking responses were sparse, time-specific, and strongest in higher-order cortex, while lower-order sensory cortex showed weak omission-driven multi-unit activity. By contrast, local field potentials showed broad low-frequency modulation across the hierarchy, especially in theta, alpha, and beta bands, with weaker gamma effects. Omission therefore appears to perturb the predictive cortical state more broadly than it drives spiking, dissociating field-level state disruption from sparse higher-order omission signaling.

> For citations, for now, write `###` and leave a comment as `(NameYYYY, TITLE-SHORT)` and later the bibliography will be set.  
> Example: The text text `###`

## Introduction

A central principle in neuroscience is that the brain is a predictive machine, using current context to generate internal expectations about future sensory input (Rao and Ballard, 1999; Friston and Kiebel, 2009). Perception, in this view (known as predictive processing), relies on a continuous comparison between expected and observed sensory states, with neural mismatch signals arising when these states diverge. Empirical and computational studies have established robust neurophysiological correlates of these processes (Friston, 2010; Bastos et al., 2012). A mechanistic refinement of this theory is the predictive routing framework, which proposes that predictions and prediction errors are expressed through distinct oscillatory dynamics across the cortical hierarchy (Bastos et al., 2020). Specifically, predictable input contexts are associated with stronger, coherent top-down low-frequency alpha (8-12 Hz) and beta (12-30 Hz) oscillations, which are hypothesized to suppress feedforward signaling of expected input. Conversely, unexpected or surprising input is associated with a release from this suppression, resulting in stronger bottom-up gamma (>=40 Hz) activity and increased spiking in feedforward pathways (Bastos et al., 2020). This rhythmic gating mechanism, rather than a dedicated error population, suggests that top-down alpha/beta activity is linked to predictions, and bottom-up gamma activity and spiking reflect the sensory surprise (figure 1). Consistent with this, causal studies show that dampening top-down alpha/beta activity (e.g., via propofol injections) disinhibits bottom-up gamma, supporting the rhythmic control hypothesis (Xiong et al., 2024).

![Figure 1](04_draft_biorxiv_markdown_assets/figure_01_page_02.png)

**Figure 1.** Predictive routing. (Left) Predictable input leads to dampened feedforward gamma and elevated feedback alpha/beta activity compared to the unpredictable context. (Right) Predictable and unpredictable lack of input (omission) is, however, unknown. There is no feedforward input, only internally generated activity.

Most of the issues with the short-term confounds in LO paradigms are resolved with global-oddball (GO) paradigms. In GO paradigms, the mismatch is strictly non-short term and by definition, cannot be caused by adaptation mechanisms nor working memory. For example, when we frequently present a sequence of “AAAB” to a system yet rarely presenting “AAAA”, the rare “AAAA” is a mismatch (oddball) but if is not confounded with the short-term mismatch. GO paradigms are of significant mathematical interest, since they evoke a neural system's “expectations” rather than its immediate sensory response:

```text
S = {AAAB} given E[S] = {AAAA} ; LO response, typical mismatch
S = {AAAA} given E[S] = {AAAB} ; GO response, atypical mismatch
```

| Term | Definition | Note |
|---|---|---|
| Sequence (input) | A pattern in space-time, received by the ??? | S |
| Stimulus (sensory) | Any physical sensory input or context that drives or stimulates a neural system. | S = {A, B, R, ...} |
| Omission | Any physical absence of an expected stimulus, while preserving its temporal and contextual structure. | S = 0, S = {O}, S = {X} |
| Standard | The expected and non-surprising event. | S = {A} given E[S] = {A} |
| Mismatch | The divergence between the expected input and the actual observed state of the world (Prediction Error). | S = {A} given E[S] = {B} |
| Omission mismatch | An omission where a standard and expected event deviates. | S = {X} given E[S] != {X} |
| Oddball | A surprising event, often a mismatch. | S = {AB} given E[S] = {AA} |
| Local Oddball (LO) | An oddball that is immediate or short-term, often confounded by low-level adaptation mechanisms. | S = {AAAB} given E[S] = {AAAA} |
| Global Oddball (GO) | An oddball that is not LO, often contextual, that is strictly not caused by adaptation mechanisms. | S = {AAAA} given E[S] = {AAAB} |
| Omission Oddball | An oddball that is specific to the absence of the expected input, that is strictly not caused by adaptation mechanisms or offset. | S = {SSXS} given E[S] = {SSSS} |
| Baseline | An interval of space-time that the context is null. | S = {N} |

**Table 1.** Important terms in prediction mismatch paradigms, in particular, omission mismatch.

However, there remains one more critic. Presentation of the sequence S = {AAAA} has a confound with the presence of “stimulus”. This specific critique is answered via the omission paradigm. Omissions are especially valuable because they remove the expected stimulus while preserving its temporal and contextual structure. When an expected event is physically absent, any time-locked neural response cannot be attributed to the features of a replacement stimulus. Instead, it must reflect internally generated dynamics, the consequences of missing bottom-up drive, or an interaction between both. That makes omission a particularly sharp test of predictive processing.

```text
S = {AXAB} given E[S] = {AAAB} ; identity-predictable local omission
S = {AAAX} given E[S] = {AAAB} ; identity-predictable global omission
S = {RXRR} given E[S] = {RRRR} ; identity-unpredictable local omission
S = {RRRX} given E[S] = {RRRR} ; identity-unpredictable global omission
```

A critical challenge in characterizing prediction mechanisms lies in separating neural responses driven by genuine expectation violation (mismatch) from those driven by the direct physical properties of a changed stimulus. Many typical oddball paradigms utilize a deviation in stimulus identity, which confounds prediction error with low-level sensory adaptation, such as the release from adaptation observed in local oddball (LO) sequences. This confound is largely addressed by shifting to global oddball (GO) paradigms, where the surprising event is defined by the larger contextual structure - for example, a sequence S = {AAAA} presented rarely after frequent sequences of E[S] = {AAAB}. While GO paradigms effectively decouple the mismatch from immediate short-term deviance and highlight higher-order contextual expectations, they retain one fundamental confound: the presence of a stimulus. This is where the omission paradigm becomes especially valuable. Omissions specifically remove an expected stimulus while precisely preserving its temporal and contextual structure (omission S = {AAAX} given E[S] = {AAAB}). Crucially, any time-locked neural response to the physical absence of the expected input cannot be attributed to bottom-up sensory features or offset artifacts. Instead, such responses must reflect the internal, generative dynamics of the circuit, the failure of an unfulfilled prediction, or the consequences of missing bottom-up drive. This unique feature makes omission an ideal and sharp test case for the predictive routing framework. If predictions are implemented by low-frequency rhythmic control of circuit state, omission should primarily manifest as a disturbance of the low-frequency state that had prepared the pathway, rather than a strong, sensory-like rise in gamma activity and widespread spiking. The key test is whether omission perturbs this low-frequency predictive state, or simply produces an error signal that mimics a normal sensory response.

The neural expression of prediction error is heterogeneous, depending on the spatial scale of the violation, the sensory modality, and the location within the cortical hierarchy. Large-scale analyses of mismatch processing suggest that simple local mismatches may be widespread and robust across cortex, while more contextual or global violations are often sparse and selectively found in higher-order cortex rather than evenly distributed throughout lower-order sensory cortex (Garrido et al., 2007; Westerberg et al., 2025). This functional specialization suggests that prediction error is carried not by a single, canonical signaling system, but by diverse, circuit-based mechanisms. Previous omission studies across species and modalities further highlight this complexity, showing non-uniform responses (Wacongne et al., 2011, 2012). While human and animal studies have broadly demonstrated that omissions evoke neural responses supporting active prediction, visual omission in rodents tends to show sparse, delayed, and ramp-like activity, sometimes implicating specific inhibitory neuron types (e.g., VIP interneurons) (Garrett et al., 2020; Jamali et al., 2024). In contrast, auditory omission responses often appear sharper and more time-locked. Notably, primate neurophysiology results align with the sparse, selective encoding idea, suggesting that explicit omission-related signals are more prominent in higher-order cortex, such as the frontal pole, compared to primary sensory areas (Suda et al., 2022). This body of work leads to a crucial distinction: if omission primarily reflects the failure of expected bottom-up drive, lower-order cortex might show little overt omission-linked spiking despite being embedded in an altered network state. Conversely, higher-order cortex may be responsible for generating a time-specific spiking signal to transform that failed expectation into an explicit event code. This framework predicts a functional dissociation between broad, distributed changes in local field potential (LFP) dynamics and sparse, selective changes in single-neuron firing.

To test this hypothesized dissociation between LFP state modulation and sparse spiking activity, we recorded spiking activity and LFP signals across multiple visual and frontal areas in non-human primates performing a sequential visual omission task. Our paradigm was specifically designed to address limitations in prior work by controlling for stimulus offset responses and isolating the roles of temporal position and expected stimulus identity in the omission context. Consistent with the central thesis of predictive routing, our preliminary results reveal a key divergence: lower-order visual cortex showed weak or absent multi-unit omission-related spiking information, whereas higher-order areas (TEO, FEF, and PFC) carried more robust omission-linked information about temporal and expected stimulus context. Simultaneously, the LFP displayed a broader and more widespread omission signature across the hierarchy. This broad LFP modulation was most pronounced as a change in spectral power around the expected time of the missing event, particularly in the lower-frequency bands (theta, alpha, and beta), while feedforward-linked gamma power remained closely tied to actual stimulus presentation. Critically, this omission occurred during a static display with constant luminance, confirming that the response reflects internal dynamics, not immediate bottom-up cues. This observed dissociation - sparse omission-linked spiking in higher-order cortex contrasted with broad, low-frequency LFP modulation across the hierarchy - suggests that low-frequency oscillations primarily encode and modulate the predictive circuit state, while only a selective subset of neurons transforms the state violation into an overt spiking signal. We thus aimed to rigorously quantify these phenomena across the cortical hierarchy to determine how the failure of an expected sensory event reshapes rhythmic coordination and neural firing patterns (figure 2, 3).

## Methods

### Subjects and recordings

Neural data were acquired from multi-area, dense laminar macaque electrophysiology experiments performed during a sequential visual omission task. Recordings included spike-sorted single-unit activity (SUA), analog multiunit activity envelope (MUAe), and LFP signals across a distributed cortical hierarchy. The canonical area order used throughout analysis and plotting was V1, V2, V3d, V3a, V4, MT, MST, TEO, FST, FEF, and PFC. For interpretation, areas were additionally grouped into low-level visual cortex (V1, V2), intermediate visual and temporal cortex (V3d, V3a, V4, MT, MST, TEO, FST), and higher-order frontal cortex (FEF, PFC). [figure 2].

Signals were acquired using high-density laminar probes. Probe geometry and session-specific area assignments were resolved from recording metadata and repository mapping tables. Because a single probe could span more than one named area, area identity was not assumed to be one-probe-per-area. Instead, when a probe was assigned to multiple areas, its ordered channel axis was partitioned into contiguous segments corresponding to those listed areas. This same segmentation logic was applied to LFP and MUAe channels, whereas spike-sorted units were assigned to area according to their anchor or peak channel [figure 2].

![Figure 2](04_draft_biorxiv_markdown_assets/figure_02_page_06.png)

**Figure 2.** Multi-area dense laminar neurophysiology (MaDeLaNe) in macaque cortex. Recordings sampled early occipital visual cortex (V1/V2), dorsal extrastriate and motion-related cortex (V3d/V3a, MT/MST/FST), ventral extrastriate-temporal cortex (V4/TEO), and frontal cortex (FEF/LPFC), enabling comparisons across sensory, intermediate, and higher-order stages of the macaque visual-frontal hierarchy. DiagnosticBioChips (DBC) 128-channel array laminar probes were used for acute extracellular recording at 30 KHz sampling rate (Intan RHD). The recordings further preprocessed into LFP (Local-field-potential), MUAe (Multi-unit activity envelope) and spike-sorted single unit activity (Kilosort). Behavioral control (eye-fixation, reward and task events) were implemented via Monkeylogic (NIMH).

### Task design and omission paradigm

Subjects (Macaques, N=2, age 11 and 17) performed a sequential visual omission paradigm in which stimulus identity and temporal regularity jointly established an expected sensory sequence. The full sequence was represented in p1-relative time using the intervals: fixation (fx), p1, d1, p2, d2, p3, d3, p4, and d4 (where S={fx,p1,d1,p2,d2,p3,d3,p4,d4} but only {p1,p2,p3,p4} is variable across trials). All event-locked displays used p1 onset as 0 ms, with a default analysis window extending from -1000 to +4000 ms relative to p1 onset. The canonical sequence timing used throughout was: fx = -500 to 0 ms, p1 = 0 to 531 ms, d1 = 531 to 1031 ms, p2 = 1031 to 1562 ms, d2 = 1562 to 2062 ms, p3 = 2062 to 2593 ms, d3 = 2593 to 3093 ms, p4 = 3093 to 3624 ms, and d4 = 3624 to 4124 ms. [figure 3].

The full condition set included S = {AAAB, AXAB, AAXB, AAAX, BBBA, BXBA, BBXA, BBBX, RRRR, RXRR, RRXR, RRRX}. Omission was organized by position in sequence: p2 conditions S = {AXAB, BXBA, RXRR}, p3 conditions S = {AAXB, BBXA, RRXR}, and p4 conditions S = {AAAX, BBBX, RRRX}. For all omission analyses, the omitted event was compared to its matched full-sequence control and, when relevant, to random-control conditions. Since each omission is preceded by a presented stimulus, local omission analyses were framed in a d-p-d-px-d or p-d-px-d structure rather than as isolated events. Thus, each omission analysis was interpreted with respect to the stimulus immediately preceding the omission, the pre-omission delay, the expected-but-omitted stimulus, and the post-omission delay. [figure 3].

![Figure 3](04_draft_biorxiv_markdown_assets/figure_03_page_07.png)

**Figure 3.** Macaques performed a fixation-controlled four-item visual sequence task in which expected drifting gratings were either presented or omitted at a defined sequence position. Predictable A- and B-family blocks contained frequent full sequences and less frequent omission sequences, whereas the R-family served as a random-control condition with matched omission timing. This design preserves the trial’s temporal structure while removing the expected visual input, allowing omission-locked activity to be analyzed as a missing-input event rather than a response to a replacement stimulus. Right panels summarize spike-sorted single-neuron yield across recorded cortical areas, firing-rate classes based on grand-average activity, and functional response groups defined by peak firing-rate modulation relative to baseline or omission windows. S+ and S- denote stimulus-excited and stimulus-suppressed units; O+ and O- denote omission-excited and omission-suppressed units; Null units show no peak firing-rate relation to the tested context. O+ units with FR(omission) > FR(stimulus) and FR(omission) > FR(baseline) were classified as X neurons using a Wilcoxon rank-sum criterion, p < 0.01. The task logic follows the project contract: omission preserves sequence timing and context while removing the expected sensory event, and p2/p3/p4 omissions should be interpreted with their surrounding pre- and post-omission sequence structure.

### Signal extraction and preprocessing

Three signal classes were analyzed: spike-sorted single-unit activity (SPK), MUAe, and LFP. Signal access was intended to proceed through one canonical accessor that returned session-keyed, condition-filtered data aligned in p1-relative time. For analog signals, the target return shape was trial x channel x time; for spiking data, the target return shape was trial x unit x time. Functional response classes, including stimulus-positive, stimulus-negative, omission-positive, omission-negative, and null units, were determined from within-unit contrasts over prespecified stimulus and omission windows.

### Local field potentials

LFP data were drawn from NWB recordings and kept in trial x channel x time format until late analysis stages wherever possible. For spectral and connectivity-style analyses, bipolar derivation was preferred before cross-site comparison, following the predictive-routing convention of nearest-neighbor laminar differencing. For descriptive power analyses, both monopolar and bipolar representations could be retained, but the exact representation used in each figure was reported explicitly. All LFP analyses preserved trial structure until after time-frequency decomposition and baseline normalization to avoid premature averaging.

### Time-frequency analysis of LFP power

Time-frequency analyses were performed on omission- and stimulus-aligned LFP epochs using moving-window spectrogram methods with high temporal overlap. For the poster-style omission traces and corresponding manuscript figures, spectrograms were computed on trialwise LFP epochs using a moving window with approximately 98% overlap. This high overlap was used to generate smooth band-power traces while retaining sufficient frequency resolution for theta, alpha, beta, and gamma-band comparisons. For omission-centered time-frequency analyses, each omission-family condition was converted from p1-relative time into a local omission-relative time base in which 0 ms marked the expected onset of the missing stimulus. The local analysis window typically extended from -1000 to +1000 ms, encompassing the preceding stimulus, the pre-omission delay, the omitted stimulus slot, and the post-omission delay. Because every omission was preceded by a real stimulus, this local window captured the d-p-d-px-d structure surrounding omission.

Spectral power was first computed in linear units, then normalized at each frequency by the mean power in a late pre-omission delay baseline, approximately -250 to -50 ms relative to omission onset. Relative power change was expressed in decibels as 10 x log10(power/baseline). Band-specific traces were then obtained by averaging baseline-normalized power across canonical frequency ranges and then across trials. The main manuscript spectrograms were computed separately for stimulus-present, omission, and control conditions and were summarized at the area and laminar levels. Population heatmaps displayed relative power in decibels as a function of time and frequency. Band-trace panels collapsed the spectrogram into theta, alpha, beta, low-gamma, and high-gamma trajectories. These traces were used to quantify whether omission primarily suppressed, preserved, or reorganized low-frequency and gamma-band power. All averages were performed at the session level before grand averaging across sessions unless the inferential question explicitly targeted channels.

### Band-specific dynamics and rhythmic coordination

Band-limited LFP dynamics were examined to test whether omission alters the balance of low-frequency predictive structure and higher-frequency feedforward-like activity. Signals were filtered into canonical frequency bands corresponding to theta, alpha, beta, low gamma, and high gamma. For time-resolved power analyses, the preferred estimate came from band-collapsed spectrogram power rather than narrowband Hilbert power, because this preserved consistency with the main TFR pipeline. For selected mechanistic analyses, however, narrowband analytic phase and amplitude were extracted using zero-phase band-pass filters followed by the Hilbert transform.

## Results

Omission-sensitive units are a selective minority across the cortical hierarchy. While stimulus-modulated populations show robust sensory activity, most units are unresponsive to omissions. Sparsely distributed omission-positive and omission-negative groups exhibit firing changes strictly locked to missing-item intervals, providing critical data on how the cortex represents absent expected input. Two key observations emerge: omission-positive units are exceptionally rare (20 of ~5000 units) and their responses are precisely time-specific to the omission's sequence position. This indicates that omission signaling is a specific, time-locked event rather than a global firing shift. These findings align with evidence that contextual surprises are represented by sparse, selective ensembles in higher-order cortex.

![Figure 4](04_draft_biorxiv_markdown_assets/figure_04_page_10.png)

**Figure 4.** Full-sequence firing-rate traces separated into groups based on their activity during four conditions of S={AAAB, AXAB, AAXB, AAAX}. The traces are aligned to the onset of the first stimulus and span the full sequence window.

The pattern of firing during sequences shows that the spiking activity during omission-window is not the same for all units. Some increase around the omission window time, some decrease, and some ramp or shift slowly across the omission period. This argues against a single one-size-fits-all omission signal that is similar to the sensory mismatch response during local oddballs. Omission seems to recruit several response motifs in higher order positions in the cortical hierarchy. This basic clustering result also explains why average population spiking is not different from the baseline even in the areas where a subset of neurons are signaling a clear omission response. Mixed positive and negative unit types can cancel at the population level, especially in lower-order cortex.

![Figure 5](04_draft_biorxiv_markdown_assets/figure_05_page_11.png)

**Figure 5.** Grand average stimulus and omission time firing-rate traces. The traces are aligned to the onset of the first stimulus and span the full sequence window. The key contrast uses the random control sequence AAAB and the omission window of AXAB, locked to the onset of the p2 (second presentation).

Therefore, the abundance of stimulus-positive and stimulus-negative units, and flatness of their neural response during the omission, suggests that omission is not equivalent to ordinary sensory surprise. If omission were simply treated like a strong unexpected stimulus, we would expect more firing, more engaged units and stronger sensory-like spiking across many areas. Instead, activity is limited compared with the stronger and broader changes during the stimulus presence. Therefore, sparsity of omission-positive units and the ratio of number of omission-positive units compared to total units, suggests that omission does not evoke a widespread and distributed activity in single unit spiking activity across the cortical hierarchy.

![Figure 6](04_draft_biorxiv_markdown_assets/figure_06_page_12.png)

**Figure 6.** Full-sequence firing-rate traces. The traces are aligned to the onset of the first stimulus and span the full sequence window. The key contrast uses the random control sequence RRRR and three omission sequences: RXRR, RRXR, and RRRX.

![Figure 7](04_draft_biorxiv_markdown_assets/figure_07_page_13.png)

**Figure 7.** Full-sequence firing-rate traces. The traces are aligned to the onset of the first stimulus and span the full sequence window. The key contrast uses the random control sequence RRRR and three omission sequences: RXRR, RRXR, and RRRX.

![Figure 8](04_draft_biorxiv_markdown_assets/figure_08_page_14.png)

**Figure 8.** Omission TFR. The traces are aligned to the onset of the first stimulus and span the full sequence window. The key contrast uses the random control sequence RRRR and three omission sequences: RXRR, RRXR, and RRRX.

![Figure 9](04_draft_biorxiv_markdown_assets/figure_09_page_15.png)

**Figure 9.** Harmony.

During normal stimulus periods, stronger gamma is more closely linked to spiking, which fits the standard picture of feedforward sensory processing. During omission periods, the pattern shifts: lower-frequency bands, especially beta-related structure, become more important for the relation between LFP and spikes. The result is not that omission creates a large gamma-driven population response. Instead, omission changes how spectral state and spiking are linked.

![Figure 10](04_draft_biorxiv_markdown_assets/figure_10_page_16.png)

**Figure 10.** Spike-field coherence. Omission vs. Stimulus window.

This is important for the predictive routing story. If omission mostly perturbs the circuit state that controls routing, then the relation between LFP bands and spiking should differ from the relation seen during actual stimulus drive. That is exactly what Figure 7 shows. The cortex is not simply processing “nothing.” It is reacting to a failure of expected input, and that reaction is more visible in spectral-spike coupling than in a broad rise of spiking across all neurons.

The main result is that omission pushes the cortex toward a different cross-area spectral pattern, especially in beta-related structure. The harmony or alignment across areas is not identical to the pattern seen during normal stimulus processing. It is also not uniform across the hierarchy. Some areas and some layer groupings show stronger changes than others.

In summary, this result suggests that omission is not only a local event in one area. It changes the broader network state. That network shift is strongest in low-frequency structure and is seen across hierarchy and layer groupings. In simple terms, omission seems to stop the expected cortical state and replace it with a new, omission-linked coordination pattern. Together, Figures 5-8 show a consistent story: omission has broad effects on LFP state across cortex, but its spiking effects are sparse, selective, and often stronger in higher-order areas.

## Discussion

The main finding of this study is that omission broadly halts low-frequency LFP structure across the cortical hierarchy while producing only sparse, selective changes in spiking. This result helps bridge two lines of work: predictive routing in oscillations and sparse higher-order omission signaling in spiking. Our data support three broad conclusions.

First, omission is not equivalent to ordinary sensory surprise. If omission were simply treated like a strong unexpected stimulus, we would expect broader gamma increases and stronger sensory-like spiking across many areas. Instead, gamma changes are limited compared with the stronger and broader changes in theta, alpha, and beta. This suggests that omission mainly disrupts the predictive state of the circuit, not just its sensory output channel.

Second, omission-sensitive spiking is sparse and uneven across the hierarchy. This agrees with the view that strong context violation signals are not carried equally by all neurons in all areas. A small group of neurons, especially in higher-order cortex, appears to carry much of the omission-linked spiking signal, while lower-order sensory cortex often shows weak omission-driven population spiking. This pattern is in line with recent large-scale spiking work showing that higher-order areas carry more of the key signals tied to prediction violation.

Third, the strongest omission effect lies in network state control. The LFP results show that omission changes low-frequency spectral structure across areas, changes spectral harmony across the hierarchy, and changes how band-limited power relates to spiking. In predictive routing terms, omission seems to expose the state that had prepared the pathway for expected input and then interrupts that state when the expected signal does not arrive. This gives a simple way to link the LFP and spiking results. Low-frequency rhythms may carry the broader circuit-level preparation and its disruption, while a sparse set of neurons converts that disrupted state into time-specific omission-linked spiking. That would explain why omission looks broad in LFP but selective in spikes.

### Relation to predictive routing

The predictive routing model proposed that alpha and beta rhythms help suppress expected input, while gamma and spiking carry stronger feedforward processing when input is not suppressed. Our omission data extend this model. When the expected input is absent, the strongest effect is not a broad rise of feedforward gamma and spiking everywhere. Instead, the omission mainly halts or resets the low-frequency predictive state, while only select neurons show strong omission-linked spiking. This suggests that the omission response is a circuit-state event first and a sparse spiking event second.

### Why lower-order cortex looks different from higher-order cortex

The combination of weak lower-order omission MUA, broad low-frequency LFP changes, and stronger higher-order omission-sensitive single-neuron responses suggests a division of labor. Lower-order sensory cortex may mainly reflect the presence or absence of sensory drive and the current rhythmic state of the pathway. Higher-order cortex may be more involved in turning a failure of expected input into an explicit spiking signal. That division would also explain why omission-sensitive units can be real and important without dominating population averages in all areas.

### Limitations: follow-up biophysical modeling and causal stimulation

There is a functional limit in non-causal outside-in studies. The spiking and LFP results are not equally strong in all areas, and some conclusions depend on sparse neuron groups. The precise link between the low-frequency network state and the selective omission-sensitive neurons still needs direct circuit tests. In follow up work, we will test this via a basic hierarchical cortex model on a similar paradigm.

## References [incomplete]
