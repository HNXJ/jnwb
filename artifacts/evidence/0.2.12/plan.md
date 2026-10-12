# 0.2.12 plan

Drafted 2026-10-12 after the 0.2.11 release; Hamm ruled all three decisions below as proposed the
same day (`artifacts/rulings/2026-10-12.md`). The stacks stay the record (`artifacts/todo_stack.md`,
`artifacts/roadmap.md`).

## Scope today

| Where | Items | Count |
|---|---|---|
| Todo stack | 12-14, 12-16, 12-17, 12-18, 12-19, 12-20, 12-21 | 7 |
| Roadmap, `deferred-0.2.12` | 12-15, 12-09, 12-01, 12-02, 12-03, 12-05, 12-04, 12-08, 09-07, 12-07, 12-06, 12-10, 11-09, 12-11, 11-07, 10-10, 11-06, 09-04, 11-32, 12-13, 12-12 | 21 |

28 items is more than one cycle; the cut below keeps 12 and moves 16.

## Proposed theme: consumers first

Work that omission and jaxfne asked for, and the release tooling that showed defects during the
0.2.11 release.

| Lane | Items, in order | Why in 0.2.12 |
|---|---|---|
| U consumer API | 12-18, 12-19 | omission JNWB-012 and its causal smoother; both wait on Hamm's signatures |
| P install | 12-20 | omission holds its upgrade on the pandas downgrade |
| J ground truth | 12-21 | meet 204dfdaa item 8; waits on jaxfne's excerpt |
| C changelog | 12-14, 12-17 | one changelog template across repos (meet 204dfdaa item 6); the dashboard republishes it |
| R release tooling | 12-16, 12-09, 12-02, 12-03 | STEP 8 imported the checkout and the umap floor had no wheel in 0.2.11; the parser and CI items close the rest |
| Q closure findings | 12-15, 12-12 | next-cycle findings of the 0.2.11 closure pass |

## Proposed for 0.2.13

| Items | Why they wait |
|---|---|
| 10-10, 11-06, 09-04, 11-32, 11-07, 12-11, 11-09 | the fact-scan cluster: each waits on another or on a ruling (rulings 2026-10-11), and nothing public claims these facts |
| 12-01, 12-05, 12-06, 12-04, 12-07, 12-08, 09-07 | harness refactors after 12-09 and 12-02; process evidence only, no shipped behaviour |
| 12-13 | its deprecations need a release of notice; `align_mode` is removed in 0.2.13 anyway |
| 12-10 | new coverage of tested operations |

## Decisions that are Hamm's

1. The 0.2.12 theme, and whether the 0.2.13 list above moves.
2. The signatures of 12-18 (`map_peak_channel_to_layer(units_df, curation)`) and 12-19 (a causal
   Gaussian that returns the smoothed rate and its mean lag in bins; edge-padded).
3. Whether the meet 204dfdaa changelog template (agent proposal) becomes the rule 12-17 enforces.

## Notes

- The dashboard (hnxj.github.io/jnwb) rebuilds on every push to `main`; `release_gate.py` does not
  cover it, its own workflow check does.
- JNWB-013 (length-1 device attributes) closed on omission's side 2026-10-12: its repaired NWBs
  store those attributes as scalars (h5py, all 10 sub-V182o files); jnwb runs no test for it.
