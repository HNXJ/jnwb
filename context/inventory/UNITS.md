# Unit inventory

Version: 2026-07-28
Status: generated inventory, not hand-edited
Truth status: `truth_safe_verified`; regenerate with `python scripts/build_corpus_inventory.py` after any corpus change.


9,228 spike-sorted units across 23 sessions. 6,655 carry a functional classification in the sidecar; 2,573 do not.


## 1. Functional classes, sidecar labels

| class | units | % of classified |
|---|---|---|
| Other | 4458 | 66.99 |
| -- | 2573 | 38.66 |
| S+ | 1432 | 21.52 |
| S- | 758 | 11.39 |
| O+ | 7 | 0.11 |


> **These labels are not the manuscript's classification.** The Methods define O+ by a Wilcoxon rank-sum contrast at p < 0.01 requiring the omission rate to exceed both the stimulus rate and the baseline rate. The sidecar labels were produced by a different pass and their criteria are not recorded alongside them. The O+ prevalence quoted in the manuscript must come from a run of the stated criteria, not from this table.


## 2. Units per area

| area10 | units | sessions | median_FR | median_SNR | median_presence |
|---|---|---|---|---|---|
| V1 | 824 | 9 | 1.70 | 0.44 | 0.99 |
| V2 | 757 | 6 | 1.80 | 0.41 | 0.99 |
| V3a/d | 1110 | 11 | 2.48 | 0.45 | 0.99 |
| V4 | 822 | 8 | 3.85 | 0.23 | 0.99 |
| MT | 1338 | 13 | 3.87 | 0.27 | 0.99 |
| MST | 290 | 5 | 9.56 | 0.13 | 0.99 |
| TEO | 778 | 11 | 2.58 | 0.31 | 0.99 |
| FST | 78 | 2 | 6.07 | 0.11 | 0.99 |
| FEF | 1124 | 12 | 4.63 | 0.32 | 0.99 |
| PFC | 2107 | 14 | 4.55 | 0.30 | 0.99 |


## 3. Units per animal

| subject | units | sessions | median_FR |
|---|---|---|---|
| C31o | 3978 | 8 | 4.88 |
| V182o | 3188 | 10 | 2.60 |
| V198o | 2062 | 5 | 1.68 |


## 4. Quality tiers

| quality | units |
|---|---|
| 1 | 4942 |
| 0 | 4286 |


The `quality` field is binary in the sidecars and its definition is not recorded there. The manuscript states that classification used quality-tiered units only, so the tier definition is owed before that sentence can stand.
