# Defect classes

The classes of defect that independent review has found in this repository's work, counted. A
review names the class of each finding; the dispatcher adds the instance here. The file is how the
harness learns: a class seen twice gets a mechanical check or a rule (`artifacts/cooperation.md`
"Routing and learning"), and the tier that missed it is raised until the check lands.

| Class | Seen | Instances | Caught by | Repair | Status |
|---|---|---|---|---|---|
| test-narrower-than-fix: a test covers part of a repair, so a mutant of the rest survives | 1 | 08-10 Ljung-Box sums (2026-09-29) | verifier, mutant | the test compares every numeric leaf | repaired; history in P-37 |
| rewrite-drops-obligation: a rewrite of a rule file loses a rule or its timing, and the mapping calls it kept | 2 | 08-06 D1 "before its first write", D2 "before and after a change" (2026-09-29) | verifier, old-against-new reading | restored | gate proposed: 09-07 |
| ruling-cited-not-recorded: a file cites "Ruled <date>" for a ruling the dated rulings file lacks | 1 | 08-06 D4 (2026-09-29) | verifier | recorded in `artifacts/rulings/2026-09-29.md` | gate proposed: 09-07 |
| second-home-contradiction: a ruling changes a rule in one file and a copy elsewhere keeps the old rule | 2 | pooling in `CONTRIBUTING.md` and `docs/01` (D3); `CONTRIBUTING.md` invariant 4 against fact S2 (2026-09-29) | verifier, lane report | 08-07 | gate proposed: 09-07 |
| inferred-cause-wrong: a proposal states an inferred cause that measurement contradicts | 1 | E-2, the solve against the dot product (2026-09-29) | actor, measurement | cause measured before repair | watch |
| undeclared-write-set: a lane writes outside its item's Writes | 2 | 08-06 D6; 08-07 work that needed files outside its Writes (2026-09-29) | verifier, actor report | Writes widened by the integrator | rule: an actor reports a needed path, never writes it |
| tree-read-while-edited: a tree is edited while a suite reads it | 1 | integrator, 2026-09-29 | integrator | suite stopped and rerun | rule in `~/.claude/CLAUDE.md` |
| environment-parity: a local reproduction of a CI leg differs from CI in a plugin, extra or version | 2 | wheel env without pytest-timeout; figures rendered at another Matplotlib minor (2026-09-29) | integrator, lane | flag dropped; one CI leg pinned | watch |
| split-hides-source: a package split moves public defs out of the files a source scan reads, so the scan passes on less | 3 | 10-02: `jnwb/*.py` globs in three tests (verifier); `test_claim_wording` skipping defs of private submodules (full suite, 2026-10-06); `inspect.getsource(jnwb.statistics)` reading only `__init__` (10-01 verifier) | verifier, full suite | recursive globs; a re-exported def counts as public | check: one shared helper that lists every file defining a public symbol, used by each source scan (10-07) |
