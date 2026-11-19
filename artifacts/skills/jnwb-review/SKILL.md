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
| Computation or test | Units and dimensions of every term; sign and orientation against the skill row; limiting cases (N=1, zero, one bin); each equation a docstring states matches the code term for term; log-domain arithmetic where a product or sum would under- or overflow, with the logarithm of power taken last (`AGENTS.md` §4.2); float32 justified; tolerances justified, never loosened; each new test fails on its defect; constants named with unit and source |
| Test module added, or a test import changed | The wheel-leg import guard passes (`tests/test_test_imports_survive_the_wheel_leg.py`): a module that imports `scripts` or `tests` puts the checkout on `sys.path` first, by `append`, never `insert(0, ...)`; a targeted run of the touched modules does not run it, so the full suite does |
| Helper unified or moved (one home per helper) | A differential of the old and the new function over every real input the callers read (each tracked file or table the function parses) and an edge corpus; each difference traced to a caller and judged; the planted-difference control fails the differential; every name a test imports from the old home still resolves |
| Code that reads command or other free text (a hook, a parser, a regex scan) | Old and new verdicts compared in one table row per input (a new allow where the old denied is a regression until shown otherwise); seeded fuzz against the old code; time on 5 KB and 50 KB pathological inputs (long runs of one quote, backslash or option), each under a stated bound, since a backtracking pattern hangs the caller; the unread cases listed in the module docstring and in the open stack |
| File hashed by a generated registry (`scripts/figures/generate_figures.py` and the files `CODE_FILES` in `scripts/figures/figure_registry.py` names) | The registry rewritten by its generator (`--write-registry`, `PYTHONPATH` on the checkout so the recorded jnwb version is the tree's); the diff changes only the hash lines; a change that moves a random stream shows the old and new draw sequences equal for several seeds, with a dropped-draw control that differs |
| Figure | Rendered at final size in both page themes, every panel inspected; no clipped or overlapping text, no legend over data; every axis and colorbar gives quantity and unit matching the producing operation; colorblind-safe perceptual colormaps, diverging maps centred on zero; a true minus sign in every label; values trace to computed results; findings labelled observed or inferred |
| Docs or skill prose | Semantic lock before, audit after; frozen elements (code, paths, identifiers, numbers, units, citations, defined terms) byte-exact; drift checked in order: certainty, scope, causation, quantities, operators and modality, attribution and tense; every fact and number recomputed from its source; a word goes only when deleting it loses no proposition, boundary or load-bearing hedge |
| Statistic reported | A p names its test, sidedness, n and multiple-comparison correction; an effect names its interval and the interval's level; a permutation null names its exchangeability scheme; a result that consumed randomness names the `rng` it used |
| Citation | DOI shape and docstring agreement (test); registration and support with a locator (review); never add an unresolved reference |

## 3. Reporting
A failed check makes a `DEFECT` result in the return contract `artifacts/skills/jnwb-fact-action` §5 defines, with the check and its receipt among the claims. That contract is the only return format.

## 4. Verification
The checks a machine settles:

```bash
python -m pytest tests/test_figure_form.py tests/test_references_resolve.py tests/test_test_imports_survive_the_wheel_leg.py tests/test_figure_registry_current.py -q
python scripts/docs_form_gate.py
```

The rest are review items: the figure eye-check, proposition preservation across a prose edit, and each cited source supporting what jnwb attributes to it.
