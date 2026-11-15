# eval evaluator (claude-sonnet-5-5), verbatim

## Report 1

Tree facts (read at baseline): ALLOWED_ROOT_DIRS/FILES are at scripts/gates/boundary.py:335-336. Gate 4 is check_root_allowlist (boundary.py:350), registered in scripts/harness_gate.py:330. Tracked artifacts/ has 10 folders (agents, archive, benchmarks, changelog.d, evidence, process, ref, rulings, showcases, skills) and 8 files. The item's "nine folders" differs from the tree; the tree wins. scratch/ is not tracked and is only in .gitignore:31. PEAK_MARGIN=0.25 (measure_peak_memory.py:50). The 20% and 5 MiB growth limit is PEAK_MEMORY_GROWTH_FRACTION and PEAK_MEMORY_GROWTH_FLOOR_MIB (release_gate.py:1609-1610), checked by peak_memory_growth_violations (:1647), which check_release_readiness calls (:2006). Both attempts touch only .github/CONTRIBUTING.md.

**Attempt X (jnwb_pilot_A)**
- CONTRIBUTING.md:120 (growth limit sentence): no defect. The 20%, 5 MiB, constant names, "previous release" and the CHANGELOG exception all match the code. It names constants, not the function (the item asks only for the defining symbol).
- :343: no defect. `scripts/gates/boundary.py` is correct. The added "(`scripts/harness_gate.py`)" for Gate 4 is true.
- :350-372 tree: every path exists and the list is complete (10 folders, 8 files, scratch kept). Defects:
  - style: the new entries have no `#` comment, unlike the existing entries.
  - style: todo_stack.md was moved out of first position by the alphabetical re-sort. This is cosmetic, with no meaning change.
  - style: the list is longer than the prose around it, which is a design choice.
- Style, minor: the :120 sentence is one very long line, in a document wrapped at about 100 columns.
- No scope, wrong-pointer, wrong-value, meaning-change or incomplete defects.

**Attempt Y (jnwb_pilot_B)**
- :120 growth limit: no defect. It names both constants, gives the values, and names `peak_memory_growth_violations` and `check_release_readiness`; all resolve.
- :343: no defect. It correctly drops `harness_gate.py` as the home and keeps "enforced by Gate 4".
- Tree block:
  - meaning-change (minor/borderline): the `artifacts/scratch/` line was deleted. The Rule at :357 still tells contributors to use `artifacts/scratch/`, and the folder is gitignored, not tracked. The listing no longer shows a location the document still instructs.
  - incomplete: the 8 root files (agents.md, direction.md, fact_stack.md, goal.md, memory.md, open_stack.md, roadmap.md, and the existing todo_stack.md) are listed only for todo_stack.md. The item says only "three entries of nine folders", so the folder list is complete (10 tracked). This is borderline and I do not count it against Y.
  - style: the new comments are plausible. I checked agents, archive, changelog.d, evidence, process, ref, rulings, showcases and skills against the tree and they are accurate.
- Style, minor: the :120 sentence is also one very long line.
- No wrong-pointer, wrong-value or scope defects.

**One line per attempt**
- X: style ×3 (minor); no wrong-pointer, wrong-value, meaning-change, scope or incomplete defects. ACCEPT.
- Y: meaning-change ×1 (scratch entry removed while the Rule still points at it); style ×1; incomplete ×0 to 1 (root files, borderline). ACCEPT only if the scratch line is restored; as written, REVISE (minor).

Neither report can state the "nine folders" discrepancy from the diff alone. The diffs do not show whether either attempt reported it, and I did not see their reports.

