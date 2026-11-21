# Solmind 0.2.17 — deep review and autonomous execution plan

**Status:** PROPOSED, read-only remote audit; not independently executed. **Baseline:** `HNXJ/jnwb@dev@0feb6fa9a071516987bf0a642d732f7b461a850f`. **Planning branch:** `_temp_solmind`. **Goal:** close 0.2.17 “Thinning and matching” while preserving every scientific estimand and all 12 standing owner goals. Canonical authority: `AGENTS.md`, `artifacts/direction.md`, `artifacts/goal.md`, `artifacts/fact_stack.md`, `artifacts/rulings/standing.md`, and `artifacts/process/release_plan.json`. Do not edit owner-controlled goal/facts/rulings. This file is a temporary planning overlay, not a second live todo stack.

## Review and score

0/100 = 0.2.17 just opened, no mandatory item independently verified. 100/100 = every frozen 0.2.17 required item and mandatory release gate passes at the release SHA, no open blocker, non-writer ACCEPT, and owner-authorized publication complete. **Current verified completion score: UNKNOWN**: no exact-SHA suite, gate, full release checklist evaluation or independent review was executed in this audit. **Verification coverage: 0/100 in this review** (not an assertion that previously reported work failed). A fabricated numerical progress score is forbidden. Build a scored item ledger from the canonical 19 release-plan IDs and any subsequently owner-ruled required items, with frozen equal weights only if Hamm approves; otherwise report `n verified / n required` with UNKNOWN, not a pseudo-100.

**Checklist completeness:** 0.2.17 release-plan scope identifies 19 IDs (15-11,12-21,16-12,17-94/95/96/97/99/100/101/102/104/127/128/129/142/144/147/150). The active todo also contains 17-151, absent from that scope list; classify as an unapproved additive release criterion unless owner rules inclusion. No item-by-item exact-SHA PASS ledger exists in this audit. Release gate, full suite, CI, docs, wheel smoke, mutation evidence and independent reviewer must be included as mandatory gates, not hidden as progress points. The historical release plan is proposed; do not amend its weights or scope unilaterally.

**Risk:** The current remote has seven branches (`main`, `dev`, `gh-pages`, `HNXJ-patch-1`, `_temp_mainjnwb_handoff`, `_temp_ocma8_pilot`, `_temp_readme_definition`); the last four conflict with the standing three-branch target. Audit their unique contents before deleting. `artifacts/open_stack.md` currently reports seven open rows, including an unsafe CI-tip override, a guard coverage gap, an intermittently hanging full suite, an ineffective Gate 15 check, unreachable isi_cv commits, owner-only fact citations, and OCMA rulings. The earlier 2026-11-13 context audit's “two open rows” is stale. The generated `artifacts/state.md` is intentionally untracked and must be reconstructed locally, not invented or committed.

## Prioritized execution queue

Rows are bounded packets. “Closing evidence” is proposed, not an observed PASS. Before execution add baseline SHA, read/write scope, exact native command, expected time, falsifier, and negative control to each worker packet. Native todo item IDs and acceptance checks remain authoritative.

| ID | Priority | Role | Work | Read/write focus | Closing evidence | Estimate |
|---|---|---|---|---|---|---|
| SM-01 | P0 | keeper | Reconcile live dev SHA, todo, roadmap, open and release plan | artifacts/{todo_stack,roadmap,open_stack}.md; artifacts/process/release_plan.json | Exact 0.2.17 item coverage and ownership matrix | 1h |
| SM-02 | P0 | checker | Run baseline harness gate, full suite and generated state check | scripts/harness_gate.py; tests/; scripts/reconstruct_state.py | SHA-bound stdout/rc and missing-host UNKNOWN | 2h+ |
| SM-03 | P0 | reviewer | Inspect CI matrix and current tip statuses | workflow.yml; scripts/ci_gate.py | Every claimed interpreter/host mapped to observed CI run | 1h |
| SM-04 | P0 | keeper | Audit temporary branches for unique work before retirement | HNXJ-patch-1; _temp_mainjnwb_handoff; _temp_ocma8_pilot; _temp_readme_definition | Compare/ancestry/diff and disposition, no deletion without preservation | 2h |
| SM-05 | P0 | worker | Close 17-147 push-guard bypasses with red-first tests | scripts/push_guard.py; tests/test_push_guard.py | Adversarial shell variants denied, allowed cases retained | 3h |
| SM-06 | P0 | keeper | Prepare ruling packet for 17-152-over no-CI-tip override | scripts/jnwb_push.sh; tests/test_jnwb_push.py | Explicit owner ruling; until then no override used | 30m |
| SM-07 | P0 | worker | Diagnose intermittent suite hang using test identity capture | scripts/jnwb_suite.sh; test runners | Named hanging test and reproduction or UNKNOWN | 3h |
| SM-08 | P0 | keeper | Prepare Gate 15 zero-mapping-table policy decision | scripts/learning_gate.py; tests/test_learning_gate.py | Owner rules remove check or enforce nonempty with valid table | 30m |
| SM-09 | P0 | worker | Recover 17-144 isi_cv commits or reconstruct from independent source | todo 17-144; missing SHAs; external mirrors | Exact commit recovery or independently tested replacement | 4h |
| SM-10 | P1 | worker | Complete 17-94 one-home helpers in package | jnwb/ | No duplicate behavior; public import and numerical parity | 4h |
| SM-11 | P1 | worker | Complete 17-95 script/test helper consolidation | scripts/; tests/ | Identical outputs and fewer duplicate implementations | 4h |
| SM-12 | P1 | worker | Complete 17-96 unused code/constants audit | jnwb/; tests/ | Reference scan, removals and full regression | 2h |
| SM-13 | P1 | worker | Complete 17-97 process-named test consolidation | tests/ | Test coverage and fault sensitivity preserved | 3h |
| SM-14 | P1 | worker | Complete 17-104 oversized structures with stable import paths | jnwb/; tests/ | Public __module__/exports and behavior unchanged | 4h |
| SM-15 | P1 | worker | Complete 17-127 fact graph performance | scripts/build_fact_graph.py | Identical graph/holder verdict; timed baseline improvement | 3h |
| SM-16 | P1 | worker | Complete 17-142 stale pointers and duplicated helpers | jnwb/; scripts/; tests/ | No live references broken; behavioral regression green | 2h |
| SM-17 | P1 | worker | Complete 17-150 AST scan for nonfinite sign guards | scripts/learning_gate.py; tests/ | Positive and planted NaN guard cases fail/pass correctly | 2h |
| SM-18 | P1 | worker | Complete 17-101 local-only dependency audit | scripts/; artifacts/ | Fresh clone has all required runtime dependencies or declared refusal | 2h |
| SM-19 | P1 | worker | Complete 17-102 showcase/calibration reachability audit | artifacts/showcases/; artifacts/benchmarks/ | Keep cited receipts; prune only verified unreferenced content | 2h |
| SM-20 | P1 | worker | Complete 17-99 canonical invariant documentation homes | AGENTS.md; docs/; artifacts/ | No contradictory duplicate normative text; owner files untouched | 3h |
| SM-21 | P1 | worker | Complete 17-100 docs/examples thinning | docs/; examples/ | Measured word/file reduction; no lost public claims, links or runnable examples | 4h |
| SM-22 | P1 | worker | Complete 17-128 docstrings/constants style matching | jnwb/; tests/ | No unit/meaning loss; style and regression gates | 2h |
| SM-23 | P1 | worker | Complete 17-129 writing-style and abbreviation pass | docs/; README.md | Author style, no unnecessary abbreviations, public claims source-traced | 3h |
| SM-24 | P1 | worker | Complete 17-151 AI-assisted research direction docs after dependencies | README.md; docs/ | No unsupported autonomous feature claim; researcher entry preserved | 2h |
| SM-25 | P1 | keeper | Obtain OCMA-5 four card-spec decisions without blocking unrelated work | artifacts/process/ocma_card_specs/ | One owner ruling per card; no card code before ruling | owner |
| SM-26 | P1 | worker | Validate 15-11 vFLIP2 on independent Bastos simulation | external simulation; artifacts/evidence/ | Provenance, planted positive/null and honest recovered effect | host/data |
| SM-27 | P1 | worker | Validate 12-21 delay/direction on broadband JaxFNE field | external jaxfne receipt; tests/ | Independent known-delay and null oracle, correct sign/units | host/data |
| SM-28 | P1 | worker | Validate 16-12 dashboard real-data cards independently | dashboard; artifacts/evidence/ | Source-pinned receipts independent of jnwb output and correct status | host/data |
| SM-29 | P0 | reviewer | Audit public surface four-face agreement and missing semantic dimensions | jnwb/__init__.py; docs/api.md; skills/; tests/ | Every supported capability routes and refuses correctly; exceptions explicit | 4h |
| SM-30 | P0 | keeper | Resolve all release-required open rows without silent deferral | artifacts/open_stack.md; todo_stack.md | 0 open at release; dispositions with owner rulings and receipts | variable |
| SM-31 | P0 | checker | Run exact-candidate harness, suite, docs and release gates | scripts/harness_gate.py; release_gate.py; docs_build.py | 0 failures on immutable SHA, wheel install and performance budget | 3h+ |
| SM-32 | P0 | reviewer | Independent blocker-focused release review and mutation checks | diff; frozen_validated.json; release receipts | ACCEPT; defects repaired or owner-ruling documented | 2h |
| SM-33 | P0 | keeper | Prepare changelog, version, wheel/sdist and candidate hashes | artifacts/changelog.d; release scripts | Reproducible candidate and consistent version, no private leaks | 2h |
| SM-34 | P0 | owner | Approve exact SHA before main/tag/PyPI publication | release candidate receipt | Explicit Hamm authorization; publication independently verified | owner |

## Checklist completeness / decision register

- **C1 Release authority:** The 0.2.17 scope is a proposed `release_plan.json` row, and the todo's 17-151 is additional. Resolve inclusion before counting it. Do not add an unapproved release criterion.
- **C2 Evidence:** Require per-ID receipt, source SHA, test command, result, independent verifier and negative/mutant test where meaningful. An agent report is evidence, not authority.
- **C3 Integration:** Protect frozen function hashes and API identity; prove before/after semantics for merges. Documentation compression must not remove unique scientific content.
- **C4 Release:** Open stack empty by legitimate dispositions, all mandatory tests/gates green, CI on exact SHA, no untested wheel surface, owner publication approval.
- **C5 Scope:** 0.2.18+ items in roadmap remain deferred unless a concrete 0.2.17 release-blocking defect or Hamm ruling requires them.
- **C6 External sources:** Unavailable Bastos simulation, JaxFNE broadband field or independently generated dashboard receipts = BLOCKED/UNKNOWN, never synthetic PASS.
- **C7 Process:** `JNWB_PUSH_OVER_RED` is not an authorization; do not bypass CI-tip verification. A GitHub connector write does not execute local hooks; planning-only pushes must be identified as such.

## Execution graph and autonomy

Wave A (SM-01..09, 29): reconcile scope, baseline and safety first; submit owner decision packets, continue independent tasks. Wave B (SM-10..19, 26..28): independent code/validation lanes, no more than three including reviewers, one writer per file set. Wave C (SM-20..24): docs after dependency repairs. Wave D (SM-30..34): close open rows, exact-SHA release checks, reviewer, owner publication.

Lead is accountable for science, integration and scoring; workers write bounded diffs, checker executes gates, non-writer reviewer independently verifies. Use existing Jarness roles; do not create jnwb-specific agent copies. For each task: inspect -> baseline red/falsifier -> smallest repair -> test green -> inspect siblings -> independent review -> reconcile canonical todo/open -> commit/push under existing authority -> receipt. Stop dependents only; continue ready work. Two failures require new approach. Work >15 min unresolved becomes todo with closing check.

**Native commands:** `python -m pytest tests/ -q`, `python scripts/harness_gate.py`, `python scripts/docs_build.py`, `python scripts/release_gate.py`, `python scripts/reconstruct_state.py --check`. Execute via repository's `scripts/jnwb_suite.sh` and `scripts/jnwb_push.sh` wrappers where applicable. No claims of execution in this planning review.

**Terminal states:** `READY_FOR_OWNER_GO` = exact candidate SHA passes all prepublication gates, independent ACCEPT, zero open blocker and no mandatory UNKNOWN; `PUBLISHED` = owner approved SHA, release artifacts and PyPI verified; `BLOCKED` = no authorized ready work, with exact decision packet. The 100/100 anchor above includes publication under the existing jnwb release completion convention; prepublication readiness is reported separately.

## Immediate agent handoff

Read latest Jarness main `rules/start.md`; then JNWB `AGENTS.md`, `artifacts/agents.md`, `direction.md`, `goal.md`, `fact_stack.md`, generated state, open/todo, release plan and relevant skills. Start SM-01..04 read-only. No public API or scientific assumption changes without Hamm. Preserve remote changes; `_temp_solmind` is a temporary planning exception, to be integrated and retired only after independent review. No `main` or `dev` modification in this planning task.
