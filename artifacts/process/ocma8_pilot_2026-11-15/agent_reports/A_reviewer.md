# A reviewer (claude-sonnet-5-5), verbatim

## Report 1

VERDICT: REVISE

Pointers 1 and 3 are fixed. Pointer 2 (`artifacts/`) is not touched.

- Pointer 1 (fixed): `.github/CONTRIBUTING.md:343` now names `scripts/gates/boundary.py`, which defines `ALLOWED_ROOT_DIRS` at line 335 and `ALLOWED_ROOT_FILES` at line 336. It names `scripts/harness_gate.py` only as the Gate 4 runner. That is accurate, because `scripts/harness_gate.py:77-78` imports both symbols and `scripts/gates/boundary.py:351` defines Gate 4.
- Pointer 3 (fixed): `.github/CONTRIBUTING.md:120` adds `release_gate.py`'s growth limit. I read these values in the tree:
  - `PEAK_MEMORY_GROWTH_FRACTION = 0.20` at `scripts/release_gate.py:1609`.
  - `PEAK_MEMORY_GROWTH_FLOOR_MIB = 5.0` at line 1610.
  - The comparison is against the previous release's value (lines 1685 and 1633 onward).
  - The CHANGELOG exemption matches (`_names_operation` on the declared version's section).
- Pointer 2 (open): `.github/CONTRIBUTING.md:350-356` still lists three `artifacts/` entries: `todo_stack.md`, `benchmarks/`, `scratch/`.
  - `ls artifacts` shows 10 directories (agents, archive, benchmarks, changelog.d, evidence, process, ref, rulings, showcases, skills), not the nine the item states. The tree wins, so the report should say so.
  - The item's check requires each pointer to resolve, so the item is not closed.
  - To close it, list the real entries or point to an authoritative owner. I did not look for one.
- Scope: `git status` shows only `.github/CONTRIBUTING.md` modified.
- Rule changes: none seen in the added lines. Both additions describe existing gate behaviour.
- Minor: line 120 is a very long single line. This is cosmetic.
- Acceptance (run once, observed): `pytest-contributing-readers rc=0` (557 passed, 2 skipped), `harness_gate rc=0` (22 of 22 gates executed), `ACCEPT_RC=0`.

## Report 2

VERDICT: ACCEPT

All three pointers now resolve to the defining symbol, and the acceptance command passes.

- Pointer 1: `.github/CONTRIBUTING.md:343` names `scripts/gates/boundary.py`, which defines `ALLOWED_ROOT_DIRS` and `ALLOWED_ROOT_FILES` at lines 335-336. `scripts/harness_gate.py` is named only as the Gate 4 runner, and `boundary.py:351` defines Gate 4.
- Pointer 2: the `artifacts/` tree at `.github/CONTRIBUTING.md:350-370` now lists all 10 directories and 7 files that `ls artifacts` shows, with `benchmarks/` and `scratch/` kept. The item said "nine folders" and the tree has 10, so the tree wins.
- Pointer 3: `.github/CONTRIBUTING.md:120` states the 20% limit (`PEAK_MEMORY_GROWTH_FRACTION = 0.20` at `scripts/release_gate.py:1609`) and the 5 MiB floor (`PEAK_MEMORY_GROWTH_FLOOR_MIB = 5.0` at line 1610). The CHANGELOG exemption matches the code in `peak_memory_growth_violations`.
- Scope: `git status` shows only `.github/CONTRIBUTING.md` modified.
- Rules: no rule or obligation was added, removed or altered. The additions describe the existing gate behaviour and list existing entries.
- Minor: `scratch/` is not on disk. The file already described it as gitignored before this change, so I left it.
- Minor: line 120 is a very long line. This is cosmetic.
- Acceptance (run once, observed): `pytest-contributing-readers rc=0` (557 passed, 2 skipped), `harness_gate rc=0` (22 of 22 gates executed), `ACCEPT_RC=0`.

