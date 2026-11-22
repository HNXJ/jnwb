# Ruling packet, 2026-11-22: the owner's items that block 0.2.17

For Hamm. Each row: what the ruling changes, its acceptance criterion, the evidence, ranked options
(first = recommended). Read at `dev` = `c24898eb`. Release plan: `artifacts/process/release_plan.json`
(0.2.17: 6 scope lines, 19 items, needs "decisions on public names" and "the Bastos lab simulation
code and a broadband jaxfne field"). Gate A1 (`artifacts/process/release_checklist.md`) needs the open
stack empty; a row leaves repaired, shown false, or moved to the todo stack (`AGENTS.md` §11).

## A. Open rows (gate A1: 8 rows)

### A1. `fact-zflip-cite` + `fact-cites-1121`: stale code cites in `artifacts/fact_stack.md`

Changes: line numbers in eight fact rows; no fact's meaning. Criterion: each cite resolves to the
line holding the stated default or behaviour. The fact gate passes with the stale numbers, so it
checks neither the number nor the line.

| Fact line | Default | Cite now | Line it should cite (read at `c24898eb`) |
|---|---|---|---|
| 152 | `band_defs=None` | `analyzers.py:280` | `:268` |
| 168 | `bin_size_ms=10` | `analyzers.py:362` | `:343` |
| 183 | xflip `n_surrogates=200` | `_xflip.py:524`; `:607-609` | `:922`; `:1155-1156` (`p_values["omnibus"] = np.nan` when no surrogates run), `:873` (not significant without surrogates) |
| 184 | zflip `n_surrogates=50` | `_zflip.py:220`; `:256-263` | `:479`; `:515-522` |
| 192 | `directed_network(method='granger')` | `_network.py:111` | `:116` |
| 193 | xflip `method='pearson'` | `_xflip.py:520`; `:585-586` | `:918`; `:1064-1066` (the method check) |

The second cites of rows 183 and 193 are new today: the 2026-11-21 review checked first cites only.
Rows 159-163, 174-175, 185-189 resolve.

Options: (1) apply all, and add todo item: the fact gate reads each cited line and fails when the
row's default literal is absent (defect class seen three times: 17-79 split, 17-128 docstrings,
this review); (2) apply all, no gate; (3) drop line numbers, cite the symbol only.

### A2. `17-147-gate15`: gate 15's mapping check examines zero tables and passes

Changes: whether a check that examines nothing stays. Criterion: gate 15 either fails on zero tables
or has no mapping clause. Evidence: `scripts/learning_gate.py:140` `mapping_tables()` returns `[]`
on the live tree; `tests/test_learning_gate.py:212-214` pins `(0, 0, [])` as a pass. The check
guarded the 09-07 rule migration (`ee5ee68e`, 2026-10-26), which has no table left to check.

Options: (1) delete the mapping clause and its test; git keeps it for the next migration;
(2) zero tables pass only when no commit since the base touched a rule file, else fail;
(3) zero tables fail and a table is added (no migration exists to tabulate).

### A3. `17-152-over`: `JNWB_PUSH_OVER_RED=1` pushes a tip CI never ran on

Changes: the push wrapper's override scope. Criterion: a regression test for the no-run tip and a
stated policy. Evidence: `scripts/jnwb_push.sh:108-118` overrides every exit-1 answer of
`ci_gate.py --tip`, "no run at the tip" included; only exit 2 refuses. Your 2026-11-18 policy: the
variable does not make a tip with no successful run verified.

Options: (1) the override covers only a completed red run; a no-run tip refuses even with it; test
`test_the_override_refuses_a_tip_with_no_run`; (2) also refuse a red run the pushed diff does not
touch; (3) keep, document only.

### A4. `OCMA-5`: four OCMA card drafts await your rulings

Changes: dashboard card content. Criterion: each draft ruled before card code. Evidence: four drafts
under `artifacts/process/ocma_card_specs/`, each `STATUS: draft-awaiting-Hamm`, 2 to 6 flags each:
release mismatch (curation and vflip2 receipts say 0.2.14, generated at 0.2.16 and 0.2.13); no claim
class or schema section for performance and complexity; `synth_laminar_motif` outside
`jnwb.__all__`; "exact SciPy parity" against measured 2.566e-15 to 4.146e-13 relative CPU/CUDA
disagreement; per-function Welch crossings instead of "near 22500 samples".

Options: (1) move `OCMA-5` to the roadmap as `deferred-0.2.20` (the 0.2.20 scope is dashboard
reproductions; no 0.2.17 scope line or item names cards); (2) rule the four drafts now, one at a time.

### A5. `17-144-src`: three isi_cv commits are unreachable (outside input)

Changes: whether 17-144 and its row stay on 0.2.17. Criterion: the three SHAs on `dev`. Evidence:
`0e06993c`, `9980f58d`, `5fa63dd3` absent from every clone, mirror and bundle searched on D:, E:, F:
and `origin` (2026-11-12, 2026-11-18). Per your S6 ruling today, nothing synthetic substitutes.

Options: (1) ask jaxfne-orchestrator to re-push or recompute; the row stays and blocks A1 until then;
(2) re-mark 17-144 and the row `deferred-0.2.18` (S6 then closes at most 3 of 4 in 0.2.17).

### A6. `17-147-guard` and `17-147-hang`: past three days today (`rules/decisions.md` rule 7)

Each must move to the todo stack with its evidence or come to you.

- `17-147-guard`: `scripts/push_guard.py` reads command text, so it denies listed spellings only;
  the push wrapper (`jnwb_push.sh`, CI gate) is the enforcing gate. Options: (1) ruling: the text
  guard stops at the denied set merged in 264ea80d; the remaining spellings are recorded as a known
  limit in 17-147, row closes; (2) move into 17-147 as `required-0.2.17`, one failing-first test per
  spelling (about 25 spellings, some undecidable from text, e.g. `python -c subprocess`).
- `17-147-hang`: two stalls at about 99%, test unnamed. Options: (1) move to the todo stack as an
  item: `jnwb_suite.sh` passes `-o faulthandler_timeout=900`, so a stall dumps every worker's stack;
  closes on the first dump or two clean full runs; (2) keep open until a third stall.

## B. Items waiting on your word (no open row; they block their scope rows)

| Item | Changes | Evidence | Options (first recommended) |
|---|---|---|---|
| 17-99 | Where each invariant lives | `CONTRIBUTING.md:368-380` and `docs/architecture.md:128-171` restate `AGENTS.md` §4 invariants; "never pool" (ruled 2026-09-29) is in 17 tracked files and in no fact row | (1) fact stack is the home: you add a fact row for spikes-and-LFP; the other files link to fact ids; (2) `AGENTS.md` §4 table is the home, files link there |
| 17-101 | Whether tracked rules may cite untracked files | verifier dispatch named only in ignored `.claude/agents/` (`cooperation.md:79`, `standing.md:37`); 15 tracked files cite `scratchpad` or `C:/Users/nejath` paths | (1) rules point to the tracked `artifacts/agents/` roles; path cites stay only in dated records; (2) track `.claude/agents/` |
| 17-102 | Which showcase and calibration files are receipts of record | 14 of 24 `openscope_glo/scripts/` and 8 of 23 `receipts/` (823 KB) named by nothing; `curation_calibration_0.2.13_raw.json` (49,820 lines) named by nothing | (1) the 0.2.20 plan scope already says "Showcase and calibration files reduced to the receipts of record": move 17-102 to 0.2.20; (2) delete the unnamed files in 0.2.17 (git-restorable) |
| 17-128 | Named constants for float defaults | 96 float defaults in `jnwb.__all__` signatures keep literal text; today's ruling keeps their values | (1) narrow the Check to tolerance literals and raise sites; float defaults keep their literal text; (2) name all 96 as constants, values unchanged |
| 17-96 | Three public names | `TFRAnalyzer.LEGACY_VIZ_BANDS` read only by tests; `DEFAULT_BANDS` a third band table; `nwb_read_io(mode=)` accepts one value | under today's ruling: (1) keep all three, deprecate with a warning in 0.2.17, remove in 0.2.18; (2) keep as is, close the item on the other four removals |
| 17-97 | Whether dated evidence records pin test file names | seven laminar test files (`test_vflip2_nuisance`, `_sensitivity`, `_simulation`, `test_xflip_homogeneous_null`, `_nuisance`, `_null_method`, `test_zflip_audit`) are named only by `artifacts/evidence/0.2.15/tiered_ci_plan.md` (per-file durations) and `artifacts/evidence/0.2.14/verification_inventory.md:84` (a node id); slice 1 (`a938713f`) already merged files that `tiered_ci_plan.md` names, treating it as a record of its own version | (1) a dated record cites the tree at its version; merge the seven, records unchanged; (2) keep the seven; 17-97 closes with them named |
| 17-151 | Its release mark | marked `deferred-0.2.17`, absent from the plan's 19 items; today's ruling keeps it off the critical path | (1) re-mark `deferred-0.2.18` |

## C. After these rulings

Agent-executable blockers left for A1 and A2: none beyond applying the rulings; A2 then needs suite
and CI green at the release tip. Gates A3 to A6 are independent of these rulings; their status is
in `artifacts/process/release_checklist.md`.
