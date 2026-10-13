# 0.2.12 plan

Ruled by Hamm on 2026-10-12 (`artifacts/rulings/2026-10-12.md`). The stacks are the record:
`artifacts/todo_stack.md` holds the items and their waves, `artifacts/roadmap.md` the rest.

## Theme: consumers first

Work that omission and jaxfne asked for, and the release tooling that showed defects during the
0.2.11 release. Of the 28 items open after 0.2.11, 12 stay and 16 move to 0.2.13.

| Lane | Items | Why in 0.2.12 |
|---|---|---|
| U consumer API | 12-18, 12-19 | omission JNWB-012 and its causal smoother; signatures ruled 2026-10-12 |
| P install | 12-20 | omission holds its pandas upgrade on hdmf's `pandas<3` |
| J ground truth | 12-21 | meet 204dfdaa item 8; waits on jaxfne's excerpt |
| K, C changelog and docs | 12-14, 12-17 | one changelog template across repositories (meet 204dfdaa item 6), which the dashboard republishes |
| G, R release tooling | 12-16, 12-09, 12-02, 12-03 | STEP 8 imported the checkout and the umap floor had no wheel in 0.2.11; the parser and CI items close the rest |
| Q closure findings | 12-15, 12-12 | next-cycle findings of the 0.2.11 closure pass |

## Moved to 0.2.13

| Items | Why they wait |
|---|---|
| 10-10, 11-06, 09-04, 11-32, 11-07, 12-11, 11-09 | the fact-scan cluster: each waits on another item or on a ruling (rulings 2026-10-11), and nothing public claims these facts |
| 12-01, 12-05, 12-06, 12-04, 12-07, 12-08, 09-07 | harness refactors after 12-09 and 12-02; process evidence only, no shipped behaviour |
| 12-13 | its deprecations need a release of notice; `align_mode` is removed in 0.2.13 anyway |
| 12-10 | new coverage of tested operations |
| 12-22 | shipped skills over 10 KB split into `references/` (added 2026-10-12) |

## Notes

- The dashboard (hnxj.github.io/jnwb) rebuilds on every push to `main`; its own workflow test
  covers it, `release_gate.py` does not.
- The OpenScope GLO showcases (ruled 2026-10-12) are planned in `C:/workspace/jnwb-showcase/`; they
  become stack items only after Hamm approves the plan at Gate B.
- JNWB-013 (length-1 device attributes) closed on omission's side on 2026-10-12: its repaired NWBs
  store those attributes as scalars (h5py, all 10 sub-V182o files); jnwb runs no test for it.
- 12-20's pandas 3 job first ran on dev at `9fd2e7e0` (run 38300465743): success, with every other
  job of the run green.
- Omission runs 0.2.11 (`b5ee25f7`) and offers itself as a consumer test bed: before the 0.2.12 tag,
  send it the candidate commit for its units-table identity gates and the Fig03/Fig04 producers.
