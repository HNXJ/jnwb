# B reviewer (claude-sonnet-5-5), verbatim

## Report 1

VERDICT: ACCEPT

Pointer 1 resolves. .github/CONTRIBUTING.md:343 now names scripts/gates/boundary.py. ALLOWED_ROOT_DIRS is at boundary.py:335 and ALLOWED_ROOT_FILES at :336. Observed.

Pointer 3 resolves. The new sentence at CONTRIBUTING.md:120 matches scripts/release_gate.py.
- PEAK_MEMORY_GROWTH_FRACTION = 0.20 is at :1609 and PEAK_MEMORY_GROWTH_FLOOR_MIB = 5.0 at :1610.
- peak_memory_growth_violations is defined at :1647 and called at :2006. I did not read the caller to confirm it is check_release_readiness.
- "More than 20% and at least 5 MiB" matches :1685. The CHANGELOG exemption matches the message at :1693.
- The existing 25% statement is untouched.

Pointer 2 resolves, with a count discrepancy. The tree has ten artifacts/ folders, not the item's nine: agents, archive, benchmarks, changelog.d, evidence, process, ref, rulings, showcases, skills. All ten are listed, and todo_stack.md is kept. The report should say the tree wins here.

Only .github/CONTRIBUTING.md changed (git status shows one file). Acceptance, run once: pytest-contributing-readers rc=0 (557 passed, 2 skipped), harness_gate rc=0 (22 of 22 gates executed), ACCEPT_RC=0.

Minor findings:
- CONTRIBUTING.md, tree block near line 362: the diff removes the `scratch/` line. artifacts/scratch/ does not exist in the tree because it is gitignored (.gitignore:31). The "Rule" line below still tells contributors to use artifacts/scratch/, so the tree block and the rule now disagree. This is arguably an alteration. The fix is to keep a `scratch/` line marked gitignored.
- The new one-line folder descriptions are the writer's wording. I did not check them against folder contents. They are not rules.

