# B helper (claude-haiku-5-5), verbatim

## Report 1

Helper report, item 17-103. Read-only; no files changed; acceptance not run.

Baseline: HEAD = ac995ddee147c4d6aa78ba15ecda7a998cd70a00; no diff to .github/CONTRIBUTING.md against baseline.

Claim table (checked 3 of 3):

| Claim | CONTRIBUTING.md now | Tree | Verdict |
|---|---|---|---|
| Allowlist home | :343 "The authoritative list is `ALLOWED_ROOT_DIRS` / `ALLOWED_ROOT_FILES` in `scripts/harness_gate.py`, enforced by Gate 4." | Defined at scripts/gates/boundary.py:335 (`ALLOWED_ROOT_DIRS = SOURCE_ROOT_DIRS \| EPHEMERAL_ROOT_DIRS \| TOOL_ROOT_DIRS`) and :336 (`ALLOWED_ROOT_FILES = {`). harness_gate.py:77-78 only imports them. | Stale: points at the importer, not the definer. |
| artifacts/ entries | :350-356 lists todo_stack.md, benchmarks/, scratch/ | Tracked top-level entries: 18 (10 trees: agents, archive, benchmarks, changelog.d, evidence, process, ref, rulings, showcases, skills; 8 blobs). Item says "nine": tree says 10. artifacts/scratch does not exist on disk; `.gitignore:31` (`scratch/`) matches it. No tracked artifacts/ entry is ignored (`check-ignore --no-index`, all 18 not-ignored). | Stale; item's "nine" differs from tree's 10. |
| Peak margin | :117 "the 0.2.7 peak plus 25%" | scripts/measure_peak_memory.py:50 `PEAK_MARGIN = 0.25`; :49 `PEAK_BASELINE_0_2_7_MIB = 404.7`; :51 threshold = 505.875 MiB. | Correct. |
| Growth limit (missing) | not stated | scripts/release_gate.py:1609 `PEAK_MEMORY_GROWTH_FRACTION = 0.20`; :1610 `PEAK_MEMORY_GROWTH_FLOOR_MIB = 5.0`; used at :1685 (growth must be above 20% of previous and at least 5 MiB to need a CHANGELOG reason). | Omission. |

Line numbers in the item (:117, :343, :350-356) match the file. Item line refs (boundary.py:335-336) match the tree.

Unresolved: the item's "nine folders" versus the tree's 10 tracked folders (tree wins; the report should say so). Whether to name `harness_gate.py` as re-exporter or `boundary.py` as home is a wording call for the writer.

