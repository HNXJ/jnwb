---
name: scientific-writing
description: |
  Claim calibration for neuroscience and neuropsychology prose: verbs matched to
  study design, nulls reported with sensitivity, effect sizes and intervals, methods
  that match what ran, and structural checks for figure/table/text drift. Use when
  drafting or revising any prose carrying a scientific claim.
---

# Scientific writing

Project-specific voice and style live in that project's own style skill. This file is about
**claim calibration** — the part that is wrong or right independent of taste.

## 1. Match the verb to the design

The single most common overclaim in systems neuroscience, and it is invisible to the author
because the causal story is what motivated the experiment.

| Design | Supports | Does **not** support |
|---|---|---|
| observational / correlational | is associated with, covaries with, predicts, tracks, is accompanied by | drives, causes, modulates, gates, generates, controls, shapes |
| intervention (lesion, opto, TMS, pharmacology) | causal language **for the manipulated variable only** | causal claims about correlated variables you did not manipulate |
| decoding / classification | information is present in, is decodable from, is linearly separable | is encoded by, represents, is used by the brain |

Two specific traps:

- **"Represents" and "encodes" smuggle in a reader.** Decodable-by-you is not used-by-the-brain.
  Say what the analysis established: a classifier trained on X separated conditions above chance.
- **Mediation and directionality require a design that identifies them.** Granger causality,
  PSI, and transfer entropy measure temporal predictability, not mechanism — write "predicts"
  or "leads", and name the method rather than saying "causal".

## 2. A null result is a result — but only with sensitivity

"No significant difference" is uninterpretable alone: it is indistinguishable from "no power".

- **Report the positive control** that establishes the measurement could have detected the
  effect. A decoder at chance on the question of interest means something only if the same
  decoder on the same data decodes a known-present variable well.
- Report the effect size and its interval. A null with a tight interval around zero and a null
  with an interval spanning every effect of interest are different findings.
- Prefer equivalence testing or a Bayes factor if the claim is genuinely "no effect", and say
  which. Absence of significance is not evidence of absence.
- Say how many sessions/subjects carry the null, not just how many observations.

## 3. Numbers

- **Effect size with an interval beats a p-value**, and neither substitutes for the other.
  Never write "significant" without the estimate and its uncertainty in the same sentence.
- **Name the correction family**, not just the method. "FDR-corrected" is incomplete without
  what it was corrected across. Correcting a single pre-specified test implies an undisclosed
  set.
- **FDR and FWER are different guarantees.** Writing that one controls the other's rate is a
  factual error.
- **State the unit of inference.** Trials within units within sessions within subjects do not
  contribute independent degrees of freedom. Say which level carries replication, and defend it.
- Round consistently and report precision that the data supports. Three decimals on a
  correlation from n = 12 is false precision.
- Give `n` for every number, at the level it applies to.

## 4. Methods must describe what actually ran

- **Do not name a method the analysis did not use.** If the Methods say bootstrap and the
  intervals reproduce exactly under an exact analytic formula, the Methods are describing
  something else. This is checkable and reviewers check it.
- A model's name is a definition, not a label. No random effects → not a mixed model, whatever
  the variable is called in the code.
- Report software, versions, seeds, and parameters sufficient to re-run. "Custom MATLAB/Python
  scripts" is not a method.
- Preprocessing is part of the method: filters, referencing, artifact rejection criteria,
  exclusions with counts, and *when* in the pipeline each happened.

## 5. Define every load-bearing term, once, numerically

When a term carries the claim — a band name, a tier label, a threshold word like "sparse",
"broad", "stable", "significant", "early" — define it numerically at first use and use it
consistently everywhere. **A term in the title that is never operationalized is where reviewers
start.** If two papers in the same corpus define a band differently, that is drift; fix it
everywhere or state the difference.

## 6. Structural checks before submission

Long documents accumulate damage that linear reading does not reveal. Walk the body
programmatically and assert the expected sequence:

- **Every number in the abstract and discussion traces to a table or figure**, and the table is
  usually right while the prose is usually stale. Sum every table column and compare against
  every place that total is quoted.
- **Every figure is cited in the text, in order**, and every citation resolves to a figure that
  exists.
- **Captions match their panels** — panel letters present, described in order, none orphaned.
- **Population scope is labelled per number.** Where a project maintains an inclusive census and
  a filtered subset, an unlabelled number sitting between the two is the most expensive
  ambiguity to resolve late.
- Recompute the p-value from the reported statistic and n. A pair that is arithmetically
  impossible at the stated sample size usually means two analyses were merged into one sentence.
- Percentages that are implausibly round (most cells exactly X.0%) were probably back-computed
  rather than counted.

## 7. Discussion sections

- Do not restate the abstract. State what changed about what is knowable.
- **Limitations that matter are the ones that could change the conclusion.** A limitations
  paragraph listing only unfixable generic constraints (sample size, species) reads as evasion
  if the real threat — a confound, a scope mismatch, an unvalidated assumption — is omitted.
- Alternative explanations get named and addressed, not gestured at. If the data cannot
  distinguish two accounts, say so plainly; that is a finding about the design.
- Do not cite a claim your own data contradict without noting the contradiction.

## 8. Neuropsychology specifics

- **Group comparisons on clinical populations carry confounds** (medication, age, education,
  time since onset, testing site). Name which were measured, which were controlled, and how.
- **Dichotomizing an ordered variable** (median split on severity, symptom count) discards
  information and adds a researcher degree of freedom. Prefer the continuous predictor.
- **Test-score units are not interchangeable.** Raw, scaled, standardized, and demographically
  corrected scores mean different things; state which normative sample.
- Person-first vs identity-first language follows the community's stated preference and the
  target journal's guidance — check rather than assume, and be consistent within a paper.
- Individual differences claims need the reliability of the measure. A correlation cannot
  exceed the geometric mean of the two measures' reliabilities; if it appears to, that is the
  error.
