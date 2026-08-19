# Session inventory

Version: 2026-07-28
Status: generated inventory, not hand-edited
Truth status: `truth_safe_verified`; regenerate with `python scripts/build_corpus_inventory.py` after any corpus change.


23 sessions have metadata sidecars; **23 carry time-frequency products and constitute the analysis corpus**. Sessions without TFR products have recordings and units but no spectral analysis, and are excluded from every area-resolved result.


## 1. All sessions

| session | animal | NWB (GB) | probes | areas | electrodes | units | events | trials | TFR files | TFR conds | layer % | in corpus |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sub-C31o_ses-230630 | C31o | -- | 3 | MT, PFC, V1, V3a/d, V4 | 384 | 167 | 2942 | 378 | 60 | 12 | -- | yes |
| sub-C31o_ses-230816 | C31o | 152.5 | 3 | MT, PFC, V1, V3a/d, V4 | 384 | 357 | 15586 | 1435 | 60 | 12 | 28.1 | yes |
| sub-C31o_ses-230818 | C31o | 176.3 | 3 | FST, MST, MT, PFC, TEO | 384 | 541 | 15972 | 2296 | 60 | 12 | 35.7 | yes |
| sub-C31o_ses-230823 | C31o | 172.5 | 3 | FEF, MST, MT, V1, V2, V3a/d | 384 | 368 | 18387 | 2785 | 72 | 12 | 38.3 | yes |
| sub-C31o_ses-230825 | C31o | 190.4 | 3 | MST, MT, PFC, TEO, V4 | 384 | 491 | 16996 | 2495 | 60 | 12 | 33.9 | yes |
| sub-C31o_ses-230830 | C31o | 190.9 | 3 | MT, PFC, V1, V3a/d, V4 | 384 | 774 | 15645 | 2193 | 60 | 12 | 37.8 | yes |
| sub-C31o_ses-230831 | C31o | 188.9 | 3 | FEF, MST, MT, TEO, V4 | 384 | 584 | 16332 | 2318 | 60 | 12 | 36.7 | yes |
| sub-C31o_ses-230901 | C31o | 199.2 | 3 | MST, MT, PFC, V3a/d, V4 | 384 | 696 | 15337 | 2136 | 60 | 12 | 60.2 | yes |
| sub-V182o_ses-260629 | V182o | 157.4 | 4 | FEF, FST, MST, PFC, TEO | 512 | 293 | 14226 | 1809 | 60 | 12 | 42.0 | yes |
| sub-V182o_ses-260702 | V182o | 148.6 | 4 | FEF, MT, TEO | 512 | 409 | 12372 | 2316 | 48 | 12 | 54.1 | yes |
| sub-V182o_ses-260706 | V182o | 121.7 | 4 | FEF, TEO, V4 | 512 | 212 | 12179 | 2283 | 48 | 12 | 65.2 | yes |
| sub-V182o_ses-260708 | V182o | 142.3 | 4 | FEF, PFC, TEO, V4 | 512 | 332 | 12737 | 2469 | 48 | 12 | 76.6 | yes |
| sub-V182o_ses-260710 | V182o | 126.6 | 4 | FEF, MT, PFC, TEO | 512 | 239 | 12321 | 2327 | 48 | 12 | 83.0 | yes |
| sub-V182o_ses-260713 | V182o | 107.6 | 4 | FEF, MT, PFC, TEO | 512 | 374 | 12448 | 2389 | 48 | 12 | 64.5 | yes |
| sub-V182o_ses-260715 | V182o | 123.4 | 4 | FEF, MT, PFC, TEO | 512 | 480 | 10754 | 1851 | 48 | 12 | 83.4 | yes |
| sub-V182o_ses-260717 | V182o | 120.6 | 4 | FEF, MT, PFC, TEO | 512 | 313 | 11793 | 2106 | 48 | 12 | 84.0 | yes |
| sub-V182o_ses-260722 | V182o | 113.2 | 4 | FEF, MT, PFC, TEO | 512 | 252 | 11441 | 2016 | 48 | 12 | 87.7 | yes |
| sub-V182o_ses-260724 | V182o | 61.7 | 3 | FEF, PFC, V3a/d | 288 | 284 | 9943 | 1576 | 48 | 12 | 67.7 | yes |
| sub-V198o_ses-230629 | V198o | -- | 2 | V1, V2, V3a/d | 256 | 464 | 4163 | 351 | 48 | 12 | -- | yes |
| sub-V198o_ses-230714 | V198o | 127.7 | 2 | V1, V2, V3a/d | 256 | 589 | 16116 | 1810 | 48 | 12 | 49.2 | yes |
| sub-V198o_ses-230719 | V198o | 117.1 | 3 | V1, V2, V3a/d, V4 | 384 | 415 | 14091 | 1462 | 60 | 12 | 58.9 | yes |
| sub-V198o_ses-230720 | V198o | 90.2 | 2 | V1, V2, V3a/d | 256 | 317 | 14454 | 1606 | 48 | 12 | 36.7 | yes |
| sub-V198o_ses-230721 | V198o | 92.9 | 2 | V1, V2, V3a/d | 256 | 277 | 15107 | 1747 | 48 | 12 | 42.6 | yes |


## 2. Totals by animal

| animal | sessions | in_corpus | electrodes | units | tfr_files |
|---|---|---|---|---|---|
| C31o | 8 | 8 | 3072 | 3978 | 492 |
| V182o | 10 | 10 | 4896 | 3188 | 492 |
| V198o | 5 | 5 | 1408 | 2062 | 252 |


## 3. Notes

- `layer %` is the fraction of that session's channels receiving a superficial, middle or deep label from the vFLIP spectrolaminar crossover. It varies from under 30% to over 85% between sessions, and differs systematically between animals, which is why no laminar effect is pooled.
- `in corpus` = no means the session has no `.npy` time-frequency arrays. Those sessions still contribute units to the spiking inventory.
- One probe is excluded from area-resolved analysis: sub-V182o_ses-260724 probe C declares 32 channels while its area slices span 128 and its array holds 128, so its channel-to-area mapping is undeterminable.
