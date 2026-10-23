# Open stack (jnwb, 2026-10-20)

Empty. A row leaves by being repaired, shown false, or moved into the todo stack (`AGENTS.md` §11); `git log -- artifacts/open_stack.md` holds the rows of earlier dates.

Cleared 2026-10-20, before the 0.2.13 checkpoint:

- Moved, each already a row of `artifacts/roadmap.md`: 11-32 (ruled 2026-10-20, the holder cells point at 16-04 to 16-10); 11-02, 07-05, 09-07, 12-06 and the fact closure group 10-10, 11-06, 09-04, 11-07, 12-11, 11-03, 11-09, 12-08, 12-07 (`deferred-0.2.14`); 12-21 and 14-08 (`deferred-0.2.14`, waiting on outside code); 15-11's second half (`deferred-0.2.15`, ruled 2026-10-19).
- Shown not to be defects: the strict xfails (word-pattern misses are the heuristic's documented limit, the mobile-width ledger a figure-size choice; `tests/test_skill_decline_behaviour.py`, `tests/test_figure_form.py`); the Metal path and the GPU tests, which skip without the hardware and change no number (fact S6).
- Housekeeping, not problems of the release: local branches and worktrees, the `E:/repos/jnwb` rename, and the V3v correction on ses-260724, which belongs to the omission project. The changelog fragments are assembled at checkpoint step 3.
- Audit 2026-10-18 (section F) and the external snapshot audit of 2026-10-19 (section G) closed with no row left; their dispositions are in the commits of 2026-10-18 and 2026-10-19.

Opened 2026-10-23:

| ID | Defect | Check | Release |
|---|---|---|---|
| P-CI-1 | CI is red on `dev` at 18457f3a; every test leg except the dependency floors fails on `fig37_verify_written_nwb.png` and `.dark.png` (0.1445% of pixels differ from the generator's output); the figure passes on the maintainer's machine, so it depends on the library versions or the platform (read from the public Actions API, run 39854420401) | `dev` at the pushed SHA has every required leg green | required-0.2.14 |
