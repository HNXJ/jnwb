# Publication style criteria — the 100/100 standard

**Reference exemplar:** Westerberg, Xiong, Sennesh, Nejat, Ricci, … Maier & Bastos (2025),
*Hierarchical substrates of prediction in visual cortical spiking*, bioRxiv
`10.1101/2024.10.02.616378` (v. posted 2025-09-25).

Measured directly from the PDF on 2026-07-28, not recalled. This file is the yardstick for
`omission-a`, `-b`, `-c`, … Numbers below are targets, not hard limits.

---

## 1. Length budget

| Section | Reference | Target for our papers |
|---|---|---|
| Abstract | ~250 words (339 incl. title + affiliations) | 220–280, single paragraph, no subheads |
| Introduction | 891 | 800–1,100 |
| Results | 2,359 | 2,000–2,600 |
| Discussion | 2,354 | **2,000–2,500** |
| Methods | 4,154 | **3,500–4,500** |
| References | ~1,170 (≈100 refs) | 70–110 refs |
| **Body total** | **~5,900** (excl. Methods/refs) | 5,500–6,500 |

Two ratios matter more than the absolutes:

- **Discussion ≈ Results.** The reference spends as many words interpreting as reporting
  (2,354 vs 2,359, ratio 1.00). A Discussion under half the Results length reads as an
  unfinished paper.
- **Methods ≈ 1.75× Results.** Methods is the largest section in the paper. Ours are
  routinely the smallest. This is the single most reliable tell of a draft that is not
  submission-ready.

## 2. Abstract

One paragraph, no headings, no citations except superscript numerals. The reference's shape:

1. Field framing in one sentence (*"Predictive processing models have recently flourished"*).
2. What prior methods could not resolve — the gap, stated as a limitation of technique.
3. *"Here, using …"* — the method, in one compact clause chain.
4. Design choice that removes a confound (*"To isolate … we use a no-report task"*).
5. **Numbered findings**: *"Four surprising findings … First, … Second, … Third, … Lastly, …"*
6. One forward-looking sentence on what the results constrain.

Note what is absent: no statistics, no p-values, no n's, no CIs in the abstract at all.
Findings are stated qualitatively and directionally. Ours currently front-loads OR and CI
values — that is a departure from house style.

## 3. Results

**Subheadings are declarative claims with a verb, no trailing period.** The reference:

- *Isolating sensation and establishing priors*
- *Predictable local oddballs are widely signaled*
- *Unpredictable global oddballs do not generate feedforward prediction error*
- *Directed connectivity of global oddballs does not indicate feedforward error propagation*

Two of four are **negative results stated as headings**. Willingness to headline a null is
part of the voice. Avoid the formulaic *"X is Y and Z across the hierarchy."* pattern where
every heading has the same syntax.

Each subsection: motivation sentence → what was done → what was observed → one
interpretive sentence, then stop. Interpretation is deferred to Discussion.

## 4. Statistics

The reference's entire inferential apparatus, counted:

| Family | Count |
|---|---|
| Wilcoxon / rank-sum (nonparametric) | 7 |
| Cluster-based permutation | 3 |
| ANOVA / F | 1 |
| t-test | 1 |
| bootstrap | **0** |
| FDR / Benjamini-Hochberg | **0** |
| GLMM / LMM / mixed models | **0** |
| Spearman / Pearson | **0** |
| Odds ratios | **0** |
| 95% CIs | **0** |
| **Total p-values reported in the paper** | **10** |

**Rules that follow:**

1. **One inferential backbone, ≤4 families total.** The reference uses 4 and leans on
   nonparametric rank tests plus cluster permutation. For our work the backbone is a
   **GLMM** with an explicitly stated link function and random-effects structure; everything
   else is descriptive. Six or more families signals an analysis assembled by accretion.
2. **~10 p-values in the whole paper.** If a draft reports 40, most of those numbers are
   decoration. Report the test that carries the claim; describe the rest.
3. **State the test inline, compactly**: `P=5.75e-5`, `P<0.05, corrected using nonparametric
   cluster-based permutation`. No parenthetical pile-ups of coefficient + SE + z + p + CI +
   correction on one result.
4. **Effect direction and magnitude in words; precision in the figure.**
5. **Correction method named once, in Methods, and applied consistently.** Never write that
   one procedure controls another's error rate.
6. **No statistics in the Abstract.**

## 5. Figures

- **5 main figures.** Not 8. Supplementary/Extended Data absorbs the rest.
- Caption format: **`Fig. N | Declarative sentence summarising the finding.`** then
  `a,` `b,` `c,` panel descriptions in bold-lead lowercase. Ours uses
  `Figure N. Noun phrase title. (A)/(a) …` — convert.
- Caption states what is plotted, the n, and the test; interpretation stays in the text.
- Reference caption median is short. Ours run ~71 words — trim toward 45–60.
- Every figure earns its place: if a panel's claim is already carried by another figure, it
  is Extended Data.

## 6. Voice

Measured, per 1,000 words:

| | Reference | Note |
|---|---|---|
| "consistent with" | 0.99 | the workhorse hedge — use it |
| "we found" | 0.69 | first person plural, active |
| "indicate" | 0.89 | |
| "reveal" | 0.59 | |
| "suggest" | 0.50 | |
| "demonstrate" | **0.00** | never |
| "show that" | **0.00** | never |
| "notably" / "surprisingly" / "strikingly" / "clearly" | **0.00** | never |
| "establish" | 0.20 | rare |

- **Sentence length: median 16, mean 18, p90 31 words.** Keep p90 under ~32; long sentences
  are where overclaims hide.
- Active first-person plural for actions (*"we recorded"*, *"we found"*, *"we limited the
  analysis to"*). Passive for procedures in Methods.
- Hedge the inference, not the observation. Say what was measured flatly, then mark the
  interpretive step with *"consistent with"*.
- No adverbial emphasis. The finding carries itself or it does not.
- Negative results stated plainly, including in headings and the abstract.

## 7. Methods

The reference's Methods is the largest section (4,154 words) and is subdivided by
**species/site then topic**, each a bold run-in head:

`Animals` · `Surgery` · `Electrophysiology Experiments` · `Visual Stimulation Parameters` ·
`Habituation to Predicted Sequence` · `Data Analysis` · `Laminar Identification` ·
`Granger causality analysis` · `Statistics and Visualization` · `Data and Code Availability`

Every parameter a replicator needs appears here: subject counts and ages, probe geometry,
sampling rates, filter settings, trial counts, inclusion/exclusion criteria, window
definitions, and software versions.

**Reproducibility floor for our papers**, in addition:
- Trial inclusion criteria stated (for this corpus: correct trials only, by default).
- Unit quality tiers named and counted (SUA vs MUA never merged silently).
- The channel→area and channel→layer assignment method stated explicitly.
- Every reported number traceable to a named script that reads data and writes a receipt.
- Random seeds where any randomness affects a reported value.

## 8. Disqualifiers — any one of these caps the score regardless of prose quality

1. A reported number that no script computes from data.
2. A named statistical method that did not produce the numbers attributed to it.
3. A model whose reported coefficients were never fitted.
4. Group labels that alias the same underlying data.
5. A "verified"/"resolved" receipt whose check does not test what it claims.
