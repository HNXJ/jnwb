# Condition and trial inventory

Version: 2026-07-28
Status: generated inventory, not hand-edited
Truth status: `truth_safe_verified`; regenerate with `python scripts/build_corpus_inventory.py` after any corpus change.


301,342 event rows across 23 sessions. Events are event-level, not trial-level: each row is one epoch within a trial, so trial counts come from unique `trial_num` values.


## 1. Correct fraction by session

| session | correct fraction | events |
|---|---|---|
| sub-C31o_ses-230630 | 0.748 | 2942 |
| sub-C31o_ses-230816 | 0.591 | 15586 |
| sub-C31o_ses-230818 | 0.601 | 15972 |
| sub-C31o_ses-230823 | 0.522 | 18387 |
| sub-C31o_ses-230825 | 0.565 | 16996 |
| sub-C31o_ses-230830 | 0.614 | 15645 |
| sub-C31o_ses-230831 | 0.588 | 16332 |
| sub-C31o_ses-230901 | 0.631 | 15337 |
| sub-V182o_ses-260629 | 0.541 | 14226 |
| sub-V182o_ses-260702 | 0.621 | 12372 |
| sub-V182o_ses-260706 | 0.631 | 12179 |
| sub-V182o_ses-260708 | 0.603 | 12737 |
| sub-V182o_ses-260710 | 0.623 | 12321 |
| sub-V182o_ses-260713 | 0.617 | 12448 |
| sub-V182o_ses-260715 | 0.714 | 10754 |
| sub-V182o_ses-260717 | 0.651 | 11793 |
| sub-V182o_ses-260722 | 0.671 | 11441 |
| sub-V182o_ses-260724 | 0.772 | 9943 |
| sub-V198o_ses-230629 | 0.862 | 4163 |
| sub-V198o_ses-230714 | 0.774 | 16116 |
| sub-V198o_ses-230719 | 0.818 | 14091 |
| sub-V198o_ses-230720 | 0.797 | 14454 |
| sub-V198o_ses-230721 | 0.763 | 15107 |


Overall correct fraction across the corpus: **0.652**. Analyses use correct, completed fixation trials only.


## 2. Task condition numbers present

| task_condition_number | events |
|---|---|
| 1 | 9308 |
| 2 | 58319 |
| 3 | 10736 |
| 4 | 10085 |
| 5 | 10153 |
| 6 | 10556 |
| 7 | 63724 |
| 8 | 11701 |
| 9 | 11602 |
| 10 | 10872 |
| 11 | 2685 |
| 12 | 2833 |
| 13 | 2685 |
| 14 | 2638 |
| 15 | 2640 |
| 16 | 2293 |
| 17 | 2497 |
| 18 | 2358 |
| 19 | 2366 |
| 20 | 2806 |
| 21 | 2313 |
| 22 | 2322 |
| 23 | 2330 |
| 24 | 2472 |
| 25 | 2287 |
| 26 | 2577 |
| 27 | 2106 |
| 28 | 2214 |
| 29 | 2288 |
| 30 | 2273 |
| 31 | 2206 |
| 32 | 2326 |
| 33 | 2211 |
| 34 | 2304 |
| 35 | 2354 |
| 36 | 2464 |
| 37 | 2314 |
| 38 | 2132 |
| 39 | 2239 |
| 40 | 1990 |
| 41 | 2363 |
| 42 | 2407 |
| 43 | 2184 |
| 44 | 2319 |
| 45 | 2033 |
| 46 | 2307 |
| 47 | 2435 |
| 48 | 2070 |
| 49 | 2078 |
| 50 | 2567 |


> **50 distinct task condition numbers appear in the event tables, while the Methods declare a twelve-condition set.** The mapping from these integers to the condition names {AAAB, AXAB, ...} is not recorded in the sidecars, and must be resolved before any per-condition count is quoted.


## 3. Stimulus number

| stimulus_number | events |
|---|---|
| 1 | 45973 |
| 2 | 34641 |
| 3 | 28897 |
| 4 | 25086 |
| 5 | 22221 |
| -- | 144524 |


`stimulus_number` is the stable crosswalk for slot selection: p1 = 2, p2 = 3, p3 = 4, p4 = 5. Do not use BHV odd event codes for this.


## 4. Omission events

5,207 events are flagged as omissions (1.73% of event rows).
