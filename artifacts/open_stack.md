# Open stack (jnwb, 2026-11-22)

`dev` at `7ecaf327`: both CI/CD runs at that SHA (45047858353 push, 45047864668 pull_request) completed with success (2026-11-22). Hamm's consolidated ruling of 2026-11-22 (`artifacts/rulings/2026-11-22.md`) ruled every row of the ruling packet.

Open rows: two (2026-11-22). A row leaves by being repaired, shown false, or moved into the todo stack (`AGENTS.md` §11); `git log -- artifacts/open_stack.md` holds earlier rows.

| Id | Open item | Evidence | Owner | Next step |
|---|---|---|---|---|
| 17-144-src | The three isi_cv SHAs for todo 17-144 are unreachable | `E:/cl-jnwb16e` missing; `0e06993c`, `9980f58d`, `5fa63dd3` absent from `D:/repos/jnwb` and from `origin` (`gh api` 422 / fetch couldn't find remote ref), 2026-11-12. 2026-11-18, reported by main-vwin and not re-run by main-jnwb: `git cat-file -e` in every clone and mirror on D: and E: and a read of all 96 `.bundle` files on F:, D: and E: found none of the three; not readable: 2 bundles under `D:/cowork/jaxfne/scratch` (0 refs) and 58 pytest-fixture bundles; not checked: `F:/warehouse` bare repos other than jaxfne's, and any copy outside D:, E: and F: | Hamm / jaxfne-orchestrator | restore the clone or re-push the three commits so they can be picked onto `dev`. Ruled 2026-11-22 (A5, option 1): recovery requested from jaxfne; the row blocks until the commits or equivalent verified results exist; nothing synthetic substitutes |
| 17-152-over | `JNWB_PUSH_OVER_RED=1` lets a branch push pass a tip that has no CI run, as it passes a red run | `scripts/jnwb_push.sh` overrides every exit-1 answer of `scripts/ci_gate.py --tip` (its `case "$gate_rc"`), "no run at the branch tip" among them; `tests/test_jnwb_push.py::test_the_override_pushes_over_a_red_run` pins the red run and no test pins the tip with no run; an unreadable answer (exit 2) is never overridden. Hamm 2026-11-16 re-enabled `CI/CD` alone, so a tip without a run now means a push CI did not test; `dashboard` and `CI` stay `disabled_manually` | Hamm | kept open (Hamm 2026-11-16): the override is not authorized on a tip with no CI run until that case has a regression test and a stated policy; Hamm rules the policy. 2026-11-18 (Hamm): policy unchanged; setting the variable does not make a tip with no successful CI run verified. Behaviour today (`scripts/jnwb_push.sh:108-118`): with the variable set, `git push origin <branch>` runs after any exit-1 gate answer, so the pushed commit can be one CI never tested; only exit 2 (unreadable) refuses. Ruled 2026-11-22 (A3, option 1): the override covers only a completed red run at the tip; missing, pending or unknown CI refuses. Repair in lane `_temp_17-152-hang`; the row leaves when it lands with `test_the_override_refuses_a_tip_with_no_run` |

Cleared 2026-11-22 by Hamm's consolidated ruling (`artifacts/rulings/2026-11-22.md`): repaired `fact-zflip-cite` and `fact-cites-1121` (six fact rows re-cited, each line read at `7ecaf327`); moved to the todo stack `17-147-gate15` (17-147 scripts-2, option 2) and `17-147-hang` (17-154); `17-147-guard` closed on its bounded requirement, the other spellings a known limit in 17-147; moved to the roadmap `OCMA-5` (17-156, `deferred-0.2.20`).

Cleared 2026-11-20: `vflip2-receipt` (`vflip2_separation_0.2.14` regenerated at 0.2.16 with all 400 draws and threshold 22.800214862368193 identical; hash-currency tests added in `tests/test_fusion_agreement.py` and `tests/test_calibration_hash_walker.py`).

Cleared 2026-11-09, the seven rows of the audit of 2026-11-08 at `5bfee7b0` (`artifacts/rulings/2026-11-09.md`): repaired P-217-03 (goal row 12) and P-217-05 (fact S15 narrowed); moved to the todo stack P-217-01 (17-145), P-217-02 and -06 (17-146), P-217-04 and -07 (17-148).

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
