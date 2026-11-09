# Open stack (jnwb, 2026-11-08)

Open rows: seven, from the audit of 2026-11-08 at `5bfee7b0` (`artifacts/evidence/0.2.17/audit_2026-11-08.md`), each waiting on Hamm. A row leaves by being repaired, shown false, or moved into the todo stack (`AGENTS.md` §11); `git log -- artifacts/open_stack.md` holds the rows of earlier dates.

| Id | Open item | Evidence | Owner | Next step |
|---|---|---|---|---|
| P-217-01 | `events(path)` with `table` omitted ignores processing-module interval tables (io-2) | `nwb_events.py:124` collects processing names for the message only; a processing-only file raises "No interval tables found" | Hamm | the omitted-table rule is public behaviour: include processing tables, or reword the error; then a todo item |
| P-217-02 | ESS truncation is credited to Geyer (1992) while the code sums single lags (stats-1) | `statistics/_autocorrelation.py:17,55-57`, `docs/references.md:94`; ruled lag rule `artifacts/rulings/2026-10-19.md:39`; AR(2) repro: ESS 20000 against 15000 closed form | Hamm | keep the ruled rule and drop the Geyer attribution, or adopt the pair rule (ESS values change) |
| P-217-03 | Goal row 12 lists 3.12 to 3.14 while 3.15 is supported (state-2) | `goal.md:26`; `pyproject.toml:26`, `README.md:43` | Hamm | proposed text: 3.12, 3.13, 3.14 and 3.15 (3.15 excluded on Windows until h5py ships cp315) |
| P-217-04 | Goal row 1 says `README.md` links `artifacts/agents.md`; it does not (state-3) | `goal.md:15`; no such link in `README.md` | Hamm | add the link to `README.md`, or reword the goal's check |
| P-217-05 | Fact S15 reads HELD while its holder checks only the exclusion list (state-5) | `fact_stack.md:88`; `scripts/fact_gate.py:497-500` | Hamm | narrow S15's predicate, or add a holder for method citations |
| P-217-06 | `StatisticalAnalysis.ALPHA_FDR` is a public alias nothing reads (stats-3) | `statistics/_analysis.py:89`; `git grep ALPHA_FDR` finds only that line | Hamm | remove it (public API: a changelog `removed` entry), or keep it |
| P-217-07 | README's `granger` examples pass no `signal_class`, which now warns (docs-2) | `README.md:151` | Hamm | name the class of the synthetic arrays (proposed: `lfp`); then the examples pass it |

Cleared 2026-10-25, the 40 rows of the audit of ac8736ff (`git show e00e8664:artifacts/open_stack.md`):

- Moved to the todo stack as 17-09 to 17-56, section "Audit of 2026-10-25", one defect per item (O-1 to O-5, O-7 to O-16, O-19 to O-26, O-32 to O-36, O-38 to O-41).
- Folded into existing items, whose text now carries them: O-27 (12-05, 09-07, 12-06, 07-05, 11-07, 12-11, 16-18, 15-22 rewritten), O-28 (the Accept clauses of 11-07, 11-09, 11-03, 12-07), O-29 (15-20 and 12-05), O-37 (17-01).
- Repaired with its item: O-30 (16-10, the I3 scan, landed 2026-10-25).
- Repaired: O-6 (both handoff notes moved outside the repository, hashes checked, ruled 2026-10-25); O-31 (S9's row names its holder's scope, ruled 2026-10-25; non-finite inputs became todo 17-24, done 2026-10-31).
- Moved to the roadmap: O-17 (roadmap 17-07, into the todo stack when 0.2.15 opened, `b2a3e85a`).
- Shown false: the `waveform_index_dtype` refusal (the repair casts to uint8, so refusing values above 255 is correct); FM-16 (path misses inside dated rulings are records).

Opened and closed 2026-10-23: P-CI-1, CI red on `dev` at 18457f3a. Every test leg failed on `fig37_verify_written_nwb` (panel B counted pynwb's embedded schema datasets, whose number changes by release). Repaired in 2543f72f; the run on 93ab6a82 is green on every leg.

Verified closed, not open: the v0.2.14 tag re-cut (`refs/tags/v0.2.14` peels to 58a2b92e, which is `main`); the agent files point at `scripts/`.

Audit of 2026-11-02 (seven models at `7ca5b9a6`): no open row; its findings went to the todo stack as 17-83 to 17-105.

Swept 2026-11-06 at `3fb5f94b`: GitHub holds 0 open issues and 0 open pull requests (#35 to #40 closed); the remote holds `main`, `dev` and `gh-pages` only; CI/CD run 42290674337 is green; no row opens.

Moved 2026-11-06 by the release plan (ruled 2026-11-05, `artifacts/process/release_plan.json`;
`AGENTS.md` §11): P-216-25 to todo 17-128 (docstrings, constants) and roadmap 17-130 (names);
P-216-26 to todo 17-129; to the roadmap P-216-24 (17-131), -32 (17-132), -08 (17-133) and -15
to -22 (17-134 to 17-141). No row is open.

## Moved at 0.2.16 (audit of 2026-11-02, eight Haiku 5.5 auditors at `9fd2b4bd`)

Lenses: pending items (low), language and code style (medium), flags and confusions (high), flow (xhigh), debugging and jarness rules (max). Each row was re-checked by grep or by reading the cited lines; findings a todo item already holds (17-75, 17-77, 17-82) are not repeated, and the rejected ones are listed in the commit message of `9f4ee85b`.

Moved to the todo stack by the lane ruling of 2026-11-02: P-216-02 (17-112), -03 (17-111), -04 (17-113), -09 (17-114), -13 (17-115), -14 (17-116), -27 (17-107), -28 (17-108), -29 (17-109), -30 (into 17-83), -31 (17-110). Repaired in the todo stack: -10 (lanes by file set), -11 (Writes and Blocked by of 17-79, 17-85, 17-93), -12 (a lane is a linked worktree), -23 (the dead `Waits:` field, the 17-71 cite and the §5 pointer). Moved by the rulings of 2026-11-03: -34 (17-118), -39 (17-119), -41 (17-120); repaired: -42 (17-80, provenance).
