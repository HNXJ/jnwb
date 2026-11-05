# Open stack (jnwb, 2026-11-02)

Open rows: the two sections at the end (0.2.16, 2026-11-02). A row leaves by being repaired, shown false, or moved into the todo stack (`AGENTS.md` §11); `git log -- artifacts/open_stack.md` holds the rows of earlier dates.

Cleared 2026-10-25, the 40 rows of the audit of ac8736ff (`git show e00e8664:artifacts/open_stack.md`):

- Moved to the todo stack as 17-09 to 17-56, section "Audit of 2026-10-25", one defect per item (O-1 to O-5, O-7 to O-16, O-19 to O-26, O-32 to O-36, O-38 to O-41).
- Folded into existing items, whose text now carries them: O-27 (12-05, 09-07, 12-06, 07-05, 11-07, 12-11, 16-18, 15-22 rewritten), O-28 (the Accept clauses of 11-07, 11-09, 11-03, 12-07), O-29 (15-20 and 12-05), O-37 (17-01).
- Repaired with its item: O-30 (16-10, the I3 scan, landed 2026-10-25).
- Repaired: O-6 (both handoff notes moved outside the repository, hashes checked, ruled 2026-10-25); O-31 (S9's row names its holder's scope, ruled 2026-10-25; non-finite inputs became todo 17-24, done 2026-10-31).
- Moved to the roadmap: O-17 (roadmap 17-07, into the todo stack when 0.2.15 opened, `b2a3e85a`).
- Shown false: the `waveform_index_dtype` refusal (the repair casts to uint8, so refusing values above 255 is correct); FM-16 (path misses inside dated rulings are records).

Opened and closed 2026-10-23: P-CI-1, CI red on `dev` at 18457f3a. Every test leg failed on `fig37_verify_written_nwb` (panel B counted pynwb's embedded schema datasets, whose number changes by release). Repaired in 2543f72f; the run on 93ab6a82 is green on every leg.

## Open at 0.2.15 (added 2026-10-28, read-only audit at 6640f4a3)

Each row was checked against its file on 2026-10-28; the keeper commits this section.

| Id | Open item | Evidence | Owner | Next step |
|---|---|---|---|---|

Verified closed, not open: the v0.2.14 tag re-cut (`refs/tags/v0.2.14` peels to 58a2b92e, which is `main`); the agent files point at `scripts/`.

Audit of 2026-11-02 (seven models at `7ca5b9a6`): no open row; its findings went to the todo stack as 17-83 to 17-105.

## Open at 0.2.16 (GitHub issues, 2026-11-02)

Each issue's own repro was run on `dev` at `9fa0833a` (jnwb 0.2.15 from the checkout). #34 reproduced fixed (dae675a9, v0.2.15) and was closed on GitHub.

| Id | Open item | Evidence | Owner | Next step |
|---|---|---|---|---|
| P-216-06 | hnxj/jnwb#40: proposal, a profile-driven `jnwb.lab` certification framework with lab profiles outside jnwb | the draft branch `lab-validate-bastoslab` is local only; no ruling or roadmap row names it | Hamm | Hamm rules scope (AGENTS.md §4.3: no corpus convention in jnwb) |

## Open at 0.2.16 (audit of 2026-11-02, eight Haiku 5.5 auditors at `9fd2b4bd`)

Lenses: pending items (low), language and code style (medium), flags and confusions (high), flow (xhigh), debugging and jarness rules (max). Each row was re-checked by grep or by reading the cited lines; findings a todo item already holds (17-75, 17-77, 17-82) are not repeated, and the rejected ones are listed in the commit message of `9f4ee85b`.

Moved to the todo stack by the lane ruling of 2026-11-02: P-216-02 (17-112), -03 (17-111), -04 (17-113), -09 (17-114), -13 (17-115), -14 (17-116), -27 (17-107), -28 (17-108), -29 (17-109), -30 (into 17-83), -31 (17-110). Repaired in the todo stack: -10 (lanes by file set), -11 (Writes and Blocked by of 17-79, 17-85, 17-93), -12 (a lane is a linked worktree), -23 (the dead `Waits:` field, the 17-71 cite and the §5 pointer). Moved by the rulings of 2026-11-03: -34 (17-118), -39 (17-119), -41 (17-120); repaired: -42 (17-80, provenance).

| Id | Open item | Evidence | Owner | Next step |
|---|---|---|---|---|
| P-216-08 | Tests that skip on every CI leg: the `validate` extra (`test_nwb_validate.py:75,84`), torch and jax (`test_nam.py:7`, `test_metadata.py:1108`), the Dryad parity data (`test_vflip2_from_lfp.py:27-31`, home and `E:` defaults), the Chromium theme test (`test_figure_theme_in_chromium.py:50`), omission (`test_addressing.py:581`), commit replay in a shallow checkout (`test_learning_gate.py:158-162`), GPU | `workflow.yml:157,273,312` install `.[test,docs,vis,wavemap]`; `workflow.yml` sets no `fetch-depth`; `dashboard.yml:59` selects one other test; `pytest tests/test_nwb_validate.py -rs`: 2 skipped | keeper; Hamm for torch, jax, GPU, omission and the Dryad reference | each skip runs on one leg, fails under a `JNWB_REQUIRE_*` switch, or is listed as declared; closes on a PASSED line in a CI log |
| P-216-15 | Pairs of repository rules that disagree: baseline mismatch fast-forwards or stops; one integrator writes `dev` or any contributor pushes directly; who edits the todo and open stacks; two lane return formats; changelog fragments or the integrator's `CHANGELOG.md`; loop letters P R G S (G undefined) or F R A V S; a one-test or five-test extension rule; defaults in skills forbidden or registered | `AGENTS.md:51` vs `fact-action SKILL.md:83`; `standing.md:17` vs `CONTRIBUTING.md:55,391`; `AGENTS.md:38-39` vs `cooperation.md:21-22`; `fact-action SKILL.md:107-118` vs `cooperation.md:31-32`; `AGENTS.md:19` vs `todo_stack.md:15`; `AGENTS.md:49-52` vs `fact-action SKILL.md:32`; `CONTRIBUTING.md:153` vs `direction.md:63-68`; `direction.md:41` vs `CONTRIBUTING.md:299-300` | Hamm | one ruling per pair; the other file points to it |
| P-216-16 | `AGENTS.md` §11 is cited by numbered condition, but its text has no numbers; the numbered text is in `standing.md` | `CONTRIBUTING.md:110`, `goal.md:22,25`, `release_gate.py:1644,1951`, `process/blocker_fixpoint_receipt.md:7`; `standing.md:153-171` | keeper | the cites point at `standing.md` §11; check: each "condition N" resolves where it points |
| P-216-17 | Stale rows in Hamm's files: standing reads the corpus on `D:` (it is on `F:/nwb-omission`), keeps only `main`, `dev` and `gh-pages` on the remote while `_temp_` branches are pushed by ruling, calls 0.2.14 the current cycle, and gives `preflight(question)` one argument; the 2026-10-24 writer set is not in the todo stack's execution table; `goal.md:19` cites roadmap rows 07-21 and 07-22 (absent) and gives gate 6's scope without `tests/`; `goal.md` keeps the closed 0.2.14 table | `standing.md:20,21,23,136`; `ls /d/` has no `nwb-omission`; `rulings/2026-10-31.md:26,28`; `jnwb/ontology.py:441`; `todo_stack.md:13`; `fact_stack.md:41` (B2) | Hamm | joins 17-77 |
| P-216-18 | jnwb's stack form departs from the jarness hygiene template: `state.md` is ignored while check in reads it; ids `17-NN`, `P-216-NN` and letter-digit facts against T-, P-, F-; 19 goal rows against a cap of 10; `roadmap.md` is a second deferred stack; 11 extra `artifacts/` entries; root holds 11 files and 9 folders against caps 4 and 6; "lane" has three meanings; Blocked by holds prose; role descriptions lack "Use when" and "Not for". `artifacts_check.py --status` prints 0 for every jnwb stack (a jarness defect) | `.gitignore:169`; `AGENTS.md:36`; `artifacts_check.py <tree> --status`; `git ls-tree --name-only HEAD` | Hamm; jarness keeper for `--status` | Hamm rules the project form or adopts the template |
| P-216-19 | The repository relies on local files: `jnwb_push.sh` runs CI helpers from `~/.claude/bin`; the mistake log is in auto memory (`rulings/2026-10-06.md:40`); `memory.md:8` cites a log that is gone; verifications go to jchat (`AGENTS.md:116`). Same class as 17-101 | `scripts/jnwb_push.sh:25-28`; `scripts/jnwb_suite.sh` reads the suite lock from `~/.claude/bin` when present (17-116) | Hamm | vendor the helpers or name the dependency; move the mistake lines into `memory.md` |
| P-216-20 | `AGENTS.md` rules against jarness: §8 keeps originals (`:93`) where jarness deletes a superseded note; §9's rule on unverified text (`:97`) names no scope, where jarness tags inferred claims in replies; dead lines: the `docs/` fallback (:45), the `problem_stack.md` pointer (:42), the global reset rule repeated (:51) | `AGENTS.md:42,45,51,93,97` | Hamm for §8 and §9; keeper for the dead lines | Hamm scopes §8 and §9 |
| P-216-21 | One concept, two names: reviewer and verifier; integrator and keeper; the retired "problem" slot in the fact-action skill; the scratch folder (`artifacts/scratch/` against the ignored `artifacts/_temp/`); the check order (`CONTRIBUTING.md:60` against `:383-389`) | `todo_stack.md:15`; `cooperation.md:4,85`; `fact-action SKILL.md:16,18`; `CONTRIBUTING.md:354-357`; `.gitignore:184` | keeper | one name each; check: grep finds the other name only in history |
| P-216-22 | Flow steps with no performer or check: the Prepare step's `state.md` regeneration, the Seal step's "verify the sync", a check that a lane's diff stays inside its Writes; an `artifacts/`-only push runs no test | `AGENTS.md:51-52`; `scripts/verify_lane.py`; `scripts/jnwb_push.sh:3-4,17-24` | Hamm for the `artifacts/` exemption (AGENTS §6) and the Seal wording | the `state.md` and Writes checks landed in 17-117; Hamm rules the exemption and the Seal wording |
| P-216-24 | `gaussian_smooth_rate` offers no `nan_policy=`; the comment calling the question undecided left in 17-110 | `jnwb/spiking.py` `gaussian_smooth_rate` | Hamm (a `nan_policy=` argument) | Hamm rules the argument |
| P-216-25 | Code departs from `match-code-style`: 17 public functions raise without a Raises section; filtering docstrings lack units and Args; 17 time and frequency parameters lack unit suffixes; `window` has four meanings and the bin concept four names; `fs` beside `sampling_rate`; unnamed band constants in `_vflip2.py`; 98 uncited float defaults and 43 tolerance literals (`_psd.py:216` `fundamental_freq * 0.1`) | the auditor's list, spot-checked at `filtering.py` (no Raises or Args) and `_psd.py:216` | keeper for docstrings and constants; Hamm for names (public API) | 0.2.17 item; names wait for Hamm |
| P-216-26 | Prose departs from `match-writing-style`: sentences over 40 words in 12 skills, `AGENTS.md` (:5, :51, :85, :93, :105), `CONTRIBUTING.md` (:72-88, :107-127, :417-428; em dashes on 15 lines), README and quickstart; "behaviour" and "behavior" both occur | the auditor's line list | keeper for docs; Hamm for `skills/`, `AGENTS.md` and the spelling | 0.2.17 item with 17-99 and 17-100 |
| P-216-32 | Estimand choices no ruling names: the response z uses `np.std` with ddof 0 (z inflated by sqrt(n/(n-1)); Fano and CV use ddof 1); `detect_trial_cycles` takes the median gap with zero gaps included, so duplicate starts set the threshold to 0; `laplacian_reference` returns rows in input order, `bipolar_reference` in depth order | `jnwb/spiking.py:191`, `:969`; `jnwb/statistics/_trials.py:33-34`; `jnwb/spectral/_reference.py:79,86,142` | Hamm | one ruling each, then a todo item |
