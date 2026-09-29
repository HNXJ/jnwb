---
name: jnwb-review
description: Review checks for jnwb. Lists what a review applies to each changed artifact - computation, figure, prose, statistics and citation.
---

# jnwb-review — Review Checks

## 1. Trigger
Activate this skill before reviewing, verifying or approving any change to `jnwb`: a computation or test, a figure, docs or skill prose, a reported statistic, or a citation.

The domain skill named in the packet supplies the scientific rules for the operation under review; this skill supplies the checks applied to the artifact that carries it.

## 2. Checks
Apply every row whose artifact the change touches. Mark a check the artifact cannot fail N/A.

| Artifact changed | Checks |
|---|---|
| Computation or test | Units and dimensions of every term; sign and orientation against the skill row; limiting cases (N=1, zero, one bin); each equation a docstring states matches the code term for term; log-domain arithmetic where a product or sum would under- or overflow; float32 justified; tolerances justified, never loosened; each new test fails on its defect; constants named with unit and source |
| Figure | Rendered at final size in both page themes, every panel inspected; no clipped or overlapping text, no legend over data; every axis and colorbar gives quantity and unit matching the producing operation; colorblind-safe perceptual colormaps, diverging maps centred on zero; text at or above the minimum font size, with a true minus sign; values trace to computed results; findings labelled observed or inferred |
| Docs or skill prose | Semantic lock before, audit after; frozen elements (code, paths, identifiers, numbers, units, citations, defined terms) byte-exact; drift checked in order: certainty, scope, causation, quantities, operators and modality, attribution and tense; every fact and number recomputed from its source; a word goes only when deleting it loses no proposition, boundary or load-bearing hedge |
| Statistic reported | A p names its test, sidedness, n and multiple-comparison correction; an effect names its interval and the interval's level; a permutation null names its exchangeability scheme; a result that consumed randomness names the `rng` it used |
| Citation | DOI shape and docstring agreement (test); registration and support with a locator (review); never add an unresolved reference |

## 3. Reporting
A failed check is a `DEFECT` claim in the return contract `artifacts/skills/jnwb-fact-action` §5 defines, with its receipt. That contract is the only return format.

## 4. Verification
The checks a machine settles:

```bash
python -m pytest tests/test_figure_form.py tests/test_references_resolve.py -q
python scripts/docs_form_gate.py
```

The rest are review items: the figure eye-check, proposition preservation across a prose edit, and each cited source supporting what jnwb attributes to it.
