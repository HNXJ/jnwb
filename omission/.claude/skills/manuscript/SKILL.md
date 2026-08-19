---
name: manuscript
description: >-
  TRIGGER before drafting or revising any prose that carries a scientific claim or will be read
  as Hamm's — manuscripts, abstracts, captions, handouts, review replies, repo markdown. Covers
  verb-to-design matching, register separation, measured style targets, structure, and DOCX
  layout. Load before writing the sentence, not after the draft exists.
---

# manuscript

**ROUTING_SENTINEL:** `manuscript:v1`

> Acceptance-test marker. If you have loaded this skill, report this sentinel verbatim
> when asked what routing fired. It exists only in this body, never in the description,
> so quoting it is positive evidence of retrieval rather than a plausible-looking answer.

**Owns:** claim calibration · voice and register · style targets · structure · captions ·
terminology · DOCX production.

## 1. Match the verb to the design

The commonest overclaim in systems neuroscience, and invisible to the author because the causal
story is what motivated the experiment.

| Design | Supports | Does **not** support |
|---|---|---|
| observational / correlational | is associated with, covaries with, predicts, tracks, is accompanied by | drives, causes, modulates, gates, generates, controls, shapes |
| intervention (lesion, opto, TMS, pharmacology) | causal language **for the manipulated variable only** | causal claims about correlated variables you did not manipulate |
| decoding / classification | information is present in, is decodable from, is linearly separable | is encoded by, represents, is used by the brain |

- **"Represents" and "encodes" smuggle in a reader.** Decodable-by-you is not used-by-the-brain.
- **Granger, PSI and transfer entropy measure temporal predictability, not mechanism.** Write
  "predicts" or "leads", and name the method rather than saying "causal".

## 2. Register separation

His instruction voice is not his paper voice, and confusing them is the most common failure.

| | Instruction voice | Paper voice |
|---|---|---|
| openers | lowercase — *"lets proceed"* | full sentences, capitalised |
| separator | ` ; ` between clauses | ordinary punctuation |
| compression | *"figures 1/2/3/4 accepted for now"* | expanded, explicit |
| slashes | `V1/V2`, `S+/S−/O+`, `p1-p4` | expanded on first use, then abbreviated |

**Never import the instruction voice into a manuscript.** Read it for content, then write it
properly. **Do mirror its directness**: no throat-clearing, no "it is important to note that",
no sentence that exists to introduce the next one.

## 3. Claim discipline in prose

- **Never assert what was not verified.** A number from a script can be stated; a number from a
  previous draft cannot, until re-derived.
- **Separate observation from inference in the sentence itself.** *"Power fell by 1.58 dB
  (q < 0.005)"* is the observation; *"consistent with a release of low-frequency suppression"*
  is the inference and must be marked as one.
- **Hedge the inference, not the observation.** Not *"power may have decreased slightly"* —
  *"power decreased by 1.58 dB; this is consistent with…"*.
- **State the estimator when the result depends on it.** A direction that flips with averaging
  order is not a finding until the order is named.
- **Name the unit of inference in the sentence carrying the claim** — *"n = 23 sessions"*, not a
  bare p-value.
- **State the denominator and population scope for every proportion.**
- **Negative and null results are stated plainly, including in headings.** Willingness to
  headline a null is part of the voice, not a concession. A null is interpretable only with the
  sensitivity analysis — report the positive control.
- **Do not round up.** "Not yet verified" is an acceptable thing to write.

When something is owed, mark it visibly — `[[STAT: what is owed and which computation owes it]]`
— rather than writing a plausible sentence around a gap.

## 4. Measured style targets

Measured on the exemplar (Westerberg & Xiong 2025); full detail in
`context/docs/PUBLICATION_STYLE_CRITERIA.md`.

- **Sentence length**: median 16, mean 18, p90 under 32 words. Long sentences are where
  overclaims hide.
- **Per 1,000 words**: *consistent with* ≈ 1.0 (the workhorse hedge), *indicate* ≈ 0.9,
  *we found* ≈ 0.7, *reveal* ≈ 0.6, *suggest* ≈ 0.5, *establish* ≈ 0.2.
- **Never**: *demonstrate*, *show that*, *notably*, *surprisingly*, *strikingly*, *clearly*,
  *importantly*, *it is worth noting*. Zero uses in the exemplar; zero here.
- **Active first person plural for actions** (*we recorded*, *we limited the analysis to*),
  passive for procedures in Methods.
- **≤ 4 inferential families; ~10 p-values total.**

## 5. Sentence architecture

- **Contrastive framing — "not X, but Y".** The signature move and the fastest fix for a vague
  sentence: *"not an absence of modulation, but an absence of a shared direction"*.
- **Em-dashes and semicolons carry qualifications** without breaking the argument. One
  qualification per sentence; a second belongs in the next sentence.
- **Topic sentence, evidence, one interpretive sentence, stop.** Resist a closing restatement.
- **Verbs**: perturb, reorganise, dissociate, decouple, constrain, evoke, recapitulate,
  partition, align, converge, absorb, adjudicate, survive (a control).
- **Parallel structure across a list of areas, bands or conditions**, so a reader can diff them.

## 6. Terminology — define numerically, once, where it does work

Applies to band names, tier labels, and every threshold word — *sparse*, *broad*, *stable*,
*widespread*, *elevated*, *early*. **A term in the title that is never operationalised is where
reviewers start.**

Bands: theta 4–8, alpha 8–14, beta 14–30, low gamma 30–50, high gamma 50–80 Hz. *Low-frequency*
means theta–beta (4–30 Hz) — a band label, not a claim that effects are largest at the lowest
frequencies.

Ten analysis areas: V1, V2, V3a/d, V4, MT, MST, TEO, FST, FEF, PFC. **V3a/d** is the inclusive
label; never contrast the subdivisions.

**Corpus facts are discovered, not quoted.** Session counts, unit counts and TFR file counts come
from a `scripts/discover_corpus.py` run, named in the text. Numbers in older drafts (17 sessions
/ 948 files, 23 sessions / 1,236 files, 6,040 units) are historical.

**Condition naming**: AAAB is the **structured standard** (all-A with a B deviant at p4). RRRR is
the random control. A draft sentence calling AAAB "the random control sequence" is wrong and has
survived in at least one live draft.

**Use**: *omission perturbs low-frequency predictive state* · *omission-linked spiking is sparse
and time-specific* · *within a bounded parameter space* · *the pooled estimate tests whether the
hierarchy shares a common sign, not whether individual areas are modulated*.

**Avoid**: *gamma is the prediction error* · *few neurons control the whole cortex* · *pure
top-down signal* · *PV/SST/VIP neurons* for extracellular data — write *putative fast-spiking /
regular-spiking*, or frame explicitly as a model hypothesis.

## 7. Numbers in prose

- Units, coordinate frames and dimensionality are never implicit.
- Effect direction and magnitude in words; precision in the figure.
- State the test inline and compactly: `q < 0.005, Benjamini–Hochberg across the ten areas`.
  Never a parenthetical pile-up of coefficient + SE + z + p + CI + correction.
- **Name what the correction controls.** BH controls FDR; cluster permutation controls FWER.
- Proportions get exact Clopper–Pearson intervals, not bootstrap.
- **No statistics in the abstract** — findings stated qualitatively and directionally.
- Report precision the data supports. Three decimals on a correlation from n = 12 is false.

## 8. Methods must describe what actually ran

Do not name a method the analysis did not use — it is checkable and reviewers check it. A model's
name is a definition, not a label. Report software, versions, seeds and parameters sufficient to
re-run; "custom Python scripts" is not a method. Preprocessing is part of the method: filters,
referencing, rejection criteria, exclusions with counts, and *when* in the pipeline each
happened.

## 9. Structure

**Order used here** (not the classic order): Abstract → Introduction → Results (captions inline)
→ Discussion → Methods → Appendix → References.

**Abstract**: one paragraph, ~220–280 words, six moves — field framing → what prior methods could
not resolve → *"Here, using …"* → the design choice that removes a confound → findings,
qualitative → one forward-looking sentence.

**Results subheadings are declarative claims with a verb and no trailing period.** Vary the
syntax. At least one should headline a negative result if the data contain one.

**Figure captions**: `Fig. N | Declarative sentence.` then bold-lead lowercase panel letters
`a,` `b,` `c,`. State what is plotted, the n, and the test; interpretation stays in the text.
Target 45–60 words.

**Citations**: `[#001]`, numbered by first appearance.

**Discussion**: do not restate the abstract; state what changed about what is knowable.
Limitations that matter are the ones that could change the conclusion — a paragraph listing only
generic constraints reads as evasion if the real threat is omitted. Name and address alternative
explanations; if the data cannot distinguish two accounts, say so plainly.

**Repo markdown** keeps the header block:

```markdown
Version: YYYY-MM-DD
Status: canonical source draft / research note
Truth status: `truth_safe_unverified`; verify against live repo manifests before submission.
```

**Manuscript series**: `omission-a`, `omission-b`, … Each letter is a distinct paper, not a
revision.

## 10. Structural checks before delivering

Long documents accumulate damage linear reading will not reveal. Walk the body programmatically
and assert the expected sequence of sections, figures and tables.

- Every number in abstract and discussion traces to a table or figure. Sum every table column
  against every place the total is quoted — the table is usually right, the prose usually stale.
- Every figure cited in text, in order; every citation resolves.
- Captions match their panels; no orphans.
- Population scope labelled per number.
- Recompute p from the reported statistic and n.
- Implausibly round percentages need a provenance receipt.

## 11. Anti-patterns that have damaged drafts here

Each shipped once.

1. A number no script computes — hardcoded literals presented as a census.
2. A named method that did not produce its numbers (Methods said bootstrap; intervals were exact).
3. Coefficients from a model never fitted — an odds ratio, CI, z and p from no model.
4. Group labels that alias the same data.
5. A "verified" receipt whose check does not test what it claims.
6. Averaging a signed effect over units that disagree in sign, then reporting the null as an
   absence of effect.
7. Stating a direction that is an artefact of the averaging order.
8. Caption/table drift.
9. Implausibly round percentages.
10. Mixing population scopes across panels without labelling each.
11. Averaging on the wrong scale — average power then log; Fisher-z before averaging r.
12. Reporting an absence a one-sided test could not have detected.
13. Claiming enrichment from raw counts without the denominator.
14. Citing a result its own selection criterion guarantees.
15. Interpreting a constant column.
16. Quoting a per-unit count without the session count behind it.

## 12. DOCX production

Word uses a reflowable OpenXML layout; editing text without layout controls moves figures,
splits table rows, and detaches captions.

- **Hard page breaks** (`page_break_before = True`) on major section titles.
- **`keep_with_next = True`** on all headings and figure captions; **`cant_split = True`** on
  table rows; **`keep_together = True`** on caption blocks.
- **Inline images in dedicated centred paragraphs**, never floating anchors — floating images
  anchor to character offsets and jump pages when preceding text changes.
- **Never regex-substitute raw `.docx` XML.** Word splits single words across `<w:r>` runs. Use
  `docxtpl` Jinja2 tags against a designed `template.docx`, which leaves styles, headers,
  footers and breaks untouched.
- Typography: **Cambria 12** throughout.

## 13. Self-check before delivering prose

- Could a reader trace every number to a script and a receipt?
- Is each claim at the strength the design supports, and does the sentence name the unit of
  inference?
- Is any hedge attached to an observation rather than an inference?
- Any banned word? Any sentence past ~32 words?
- Is every threshold word operationalised numerically somewhere?
- Does any heading merely name a topic instead of making a claim?
- Are the correction procedure and what it controls named correctly?
- Did the instruction register leak in — lowercase openers, ` ; ` separators, slashes?
