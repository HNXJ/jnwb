---
name: match-my-writing-style
description: Write in Hamm's voice — rigorous, hedged where it should be hedged, flat where the data are flat. Use for manuscripts, abstracts, figure captions, repo markdown, handouts, review replies, and any prose that will carry his name. Covers register separation (his chat voice is not his paper voice), claim discipline, measured style targets, terminology rules, and the anti-patterns that have actually damaged drafts on this corpus.
---

# Writing as Hamm

Governs prose that will be read as his. Two registers, and confusing them is the most common
failure: **he writes to you in compressed telegraphic instructions; he does not want papers
written that way.** Section 1 separates them. Everything after applies to the paper register
unless marked otherwise.

Companion documents, which this skill defers to on their own subjects:
`context/PUBLICATION_STYLE_CRITERIA.md` (measured house targets), `context/CONTEXT.md`
(project facts, retracted numbers), `CLAUDE.md` and `.agents/AGENTS.md` (doctrine).

---

## 1. Register separation

| | His instruction voice | The paper voice he wants |
|---|---|---|
| Openers | lowercase — *"lets proceed"*, *"so consider"* | full sentences, capitalised |
| Separator | ` ; ` between clauses and list items | ordinary punctuation |
| Compression | *"figures 1/2/3/4 are accepted for now"* | expanded, explicit |
| Slashes | `V1/V2`, `S+/S−/O+`, `p1-p4` | expanded on first use, then abbreviated |
| Register | informal (*"gotta"*, *"lets"*) | formal, third-person procedures |

**Never import the instruction voice into a manuscript.** When he writes
*"so the point is this : c31o has all 11 areas"* he is talking, not drafting. Read it for
content, then write it properly.

**Do mirror one thing from his instruction voice: its directness.** No throat-clearing, no
"it is important to note that", no sentence that exists to introduce the next one.

---

## 2. Claim discipline — the core of the voice

This is not a formatting preference. It is what he is checking for.

- **Never assert what was not verified.** If a number came from a script, it can be stated. If
  it came from a previous draft, it cannot, until re-derived.
- **Separate observation from inference in the sentence itself.** *"Power fell by 1.58 dB
  (q < 0.005)"* is an observation. *"consistent with a release of low-frequency suppression"*
  is the inference, and it must be marked as one.
- **State the estimator when the result depends on it.** A direction that flips with the
  averaging order is not a finding until the order is named.
- **Name the unit of inference in the sentence that carries the claim** — *"n = 17 sessions"*,
  not a bare p-value.
- **State the denominator and the population scope for every proportion.** An unlabelled
  number sitting between two populations is the most expensive ambiguity to resolve late.
- **Negative and null results are stated plainly**, including in headings. Willingness to
  headline a null is part of the voice, not a concession.
- **Do not round up.** "Ran X, got Y" beats "X works". "Not yet verified" is an acceptable
  thing to write.

When something is owed, mark it visibly — `[[STAT: what is owed and which computation owes
it]]` — rather than writing a plausible sentence around a gap.

---

## 3. Measured style targets

From `context/PUBLICATION_STYLE_CRITERIA.md`, measured on the exemplar (Westerberg & Xiong 2025):

- **Sentence length**: median 16, mean 18, p90 under 32 words. Long sentences are where
  overclaims hide.
- **Per 1,000 words**: *consistent with* ≈ 1.0 (the workhorse hedge), *indicate* ≈ 0.9,
  *we found* ≈ 0.7, *reveal* ≈ 0.6, *suggest* ≈ 0.5, *establish* ≈ 0.2 (rare).
- **Never**: *demonstrate*, *show that*, *notably*, *surprisingly*, *strikingly*, *clearly*,
  *importantly*, *it is worth noting*. Zero uses in the exemplar; zero here.
- **Hedge the inference, not the observation.** State what was measured flatly, then mark the
  interpretive step. Not *"power may have decreased slightly"* — *"power decreased by 1.58 dB;
  this is consistent with…"*.
- **Active first person plural for actions** (*we recorded*, *we limited the analysis to*),
  passive for procedures in Methods.
- **≤ 4 inferential families in a paper; ~10 p-values total.** Report the test that carries the
  claim and describe the rest.

---

## 4. Sentence architecture

- **Contrastive framing — "not X, but Y".** His signature move and the fastest way to fix a
  vague sentence: *"not a conventional sensory surprise, but a disruption of low-frequency
  state"*; *"not an absence of modulation, but an absence of a shared direction"*.
- **Em-dashes and semicolons carry the qualifications** without breaking the line of argument.
  One qualification per sentence; a second belongs in the next sentence.
- **Topic sentence first, then the evidence, then one interpretive sentence, then stop.**
  Resist a closing sentence that restates the paragraph.
- **Verbs**: perturb, reorganise, dissociate, decouple, constrain, evoke, modulate,
  recapitulate, partition, align, converge, absorb, adjudicate, survive (a control).
- **Parallel structure across a list of areas, bands or conditions** — same clause shape each
  time, so a reader can diff them.

---

## 5. Terminology

**Define a term numerically, once, where it does work, then use it consistently.** A word in
the title that is never operationalised is where reviewers start. This applies to band names,
tier labels, and every threshold word — *sparse*, *broad*, *stable*, *widespread*, *elevated*.

**Canonical bands** (settled by the 2026-07-27 audit; do not re-drift): theta 4–8, alpha 8–14,
beta 14–30, low gamma 30–50, high gamma 50–80 Hz. *Low-frequency* means theta–beta (4–30 Hz)
and is a band label, not a claim that effects are largest at the lowest frequencies.

**Corpus facts to keep straight**: three macaques; 17 sessions carry the time-frequency
analysis; ten analysis areas (V1, V2, V3a/d, V4, MT, MST, TEO, FST, FEF, PFC). **V3a/d** is the
inclusive label covering V3, V3a and V3d — never contrast the subdivisions, they are halves of
one shank under an assumed equal-share partition.

**Use**: *omission perturbs low-frequency predictive state* · *omission-linked spiking is sparse
and time-specific* · *supports a circuit-state interpretation* · *within a bounded parameter
space* · *consistent with* · *the pooled estimate tests whether the hierarchy shares a common
sign, not whether individual areas are modulated*.

**Avoid**: *gamma is the prediction error* · *few neurons control the whole cortex* · *pure
top-down signal* · *PV/SST/VIP neurons* for extracellular data — write *putative fast-spiking /
regular-spiking*, or frame explicitly as a model hypothesis.

---

## 6. Numbers in prose

- Units, coordinate frames and dimensionality are never implicit.
- Effect direction and magnitude in words; precision in the figure.
- State the test inline and compactly: `P = 5.75e-5`; `q < 0.005, Benjamini–Hochberg across
  the ten areas`. Never a parenthetical pile-up of coefficient + SE + z + p + CI + correction.
- **Name what the correction controls.** Benjamini–Hochberg controls FDR; cluster permutation
  controls FWER. Writing that one controls the other's rate is a factual error, not a wording
  choice.
- Proportions get exact Clopper–Pearson intervals, not bootstrap.
- **No statistics in the abstract.** Findings stated qualitatively and directionally.
- Quantify uncertainty where it would change a reader's conclusion — not on every number.

---

## 7. Structure

**Manuscript order he uses** (current, and it is not the classic order): Abstract → Introduction
→ Results (figure captions inline) → Discussion → Methods → Appendix → References.

**Abstract**, one paragraph, ~220–280 words, six moves: field framing → what prior methods could
not resolve → *"Here, using …"* → the design choice that removes a confound → the findings,
qualitative → one forward-looking sentence.

**Results subheadings are declarative claims with a verb and no trailing period.** Vary the
syntax; do not let every heading share one shape. At least one should headline a negative
result if the data contain one.

**Figure captions**: `Fig. N | Declarative sentence.` then bold-lead lowercase panel letters
`a,` `b,` `c,`. State what is plotted, the n, and the test; interpretation stays in the text.
Target 45–60 words.

**Citations**: `[#001]`, numbered in order of first appearance.

**Repo markdown** keeps the header block he uses:

```markdown
Version: YYYY-MM-DD
Status: canonical source draft / research note
Truth status: `truth_safe_unverified`; verify against live repo manifests before submission.
```

Numbered section titles (`## 1. Core rationale`, `### 3.1 Session manifest`), tables for every
inventory and parameter set, bold lead-ins on bullets, and condition sets in raw code blocks:

```text
S = { AAAB, AXAB, AAXB, AAAX,
      BBBA, BXBA, BBXA, BBBX,
      RRRR, RXRR, RRXR, RRRX }
```

**Manuscript series**: `omission-a`, `omission-b`, … Each letter is a distinct paper, not a
revision.

**Typography for DOCX**: Cambria 12 throughout.

---

## 8. Anti-patterns that have actually damaged drafts here

Each of these shipped once. Do not let them ship again.

1. **A number no script computes.** Hardcoded literals presented as a census, protected by a
   handout that told future agents not to change them. Every reported number traces to a named
   script that reads data and writes a receipt.
2. **A named method that did not produce its numbers.** Methods said bootstrap; the intervals
   reproduced exactly under an exact analytic formula.
3. **Coefficients from a model never fitted.** An odds ratio with a CI, a z and a p-value, from
   no model.
4. **Group labels that alias the same data.** Area labels that both pointed at the same probe.
5. **A "verified" receipt whose check does not test what it claims.**
6. **Averaging a signed effect over units that disagree in sign**, then reporting the null as
   an absence of effect. State magnitude and direction as two claims when they have two answers.
7. **Stating a direction that is an artefact of the averaging order.** Name the estimator.
8. **Caption/table drift.** Sum every table column and compare against every place the total is
   quoted; the table is usually right and the prose is usually stale.
9. **Implausibly round percentages.** Measured proportions with large denominators land on
   whole numbers about a tenth of the time. A table of X.0% values needs a provenance receipt.
10. **Mixing population scopes across panels** without labelling each one.
11. **Averaging on the wrong scale.** Decibels and correlations are logarithms and bounded
    quantities; averaging them is biased by the variance of what is averaged, and the bias
    differs between the groups being compared. Average power, then take the logarithm; Fisher-z
    correlations before averaging them.
12. **Reporting an absence that the test could not have detected.** A one-sided test cannot
    find suppression. State the sidedness before writing "no such units were found".
13. **Claiming enrichment from raw counts.** The area with the most responsive units is usually
    the area with the most recorded units. Normalise, then claim.
14. **Citing a result that its own selection criterion guarantees.** If the criterion requires
    membership in a set, prevalence within that set is not evidence.
15. **Interpreting a constant column.** Check that a field varies before drawing an inference
    from its value.
16. **Quoting a per-unit or per-channel count without the session count behind it.** Units
    concentrated in one or two sessions describe those recordings, not the population.

---

## 9. Self-check before delivering prose

- Could a reader trace every number to a script and a receipt?
- Is each claim stated at the strength the design supports — and does the sentence name the
  unit of inference?
- Is any hedge attached to an observation rather than to an inference?
- Any banned word (*demonstrate*, *notably*, *clearly*, *show that*)? Any sentence past ~32
  words?
- Is every threshold word operationalised numerically somewhere?
- Does any heading merely name a topic instead of making a claim?
- Are the correction procedure and what it controls named correctly?
- Did the instruction register leak in — lowercase openers, ` ; ` separators, slashes?
