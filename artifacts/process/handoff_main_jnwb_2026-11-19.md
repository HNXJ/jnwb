# Handoff: main-jnwb, 2026-11-19 (restart)

For the session that continues jnwb 0.2.17 work. Facts are from this session's receipts; each is observed
unless marked inferred. Earlier handoff: `handoff_main_jnwb_2026-11-18.md`. Score method:
`artifacts/process/release_checklist.md` (tracking artifact, provisional weights, Hamm's rulings stand).

## State

| Item | Value |
|---|---|
| `origin/dev` | `e6baac97` (17-79 landed; pushed through `scripts/jnwb_push.sh`, no bypass) |
| Suite | 11021 passed, 0 failed on `e6baac97`, in the main clone and in the lane clone |
| CI/CD on `e6baac97` | two runs (44601543097, 44601555186): read them first; they were in progress at the last check |
| Stack edits not yet on `dev` | commit `74149db7` on remote `_temp_mainjnwb_stacks` (WIP): 17-79 closed, plan id removed, 17-94 unblocked, two open rows, checklist 12/100. It also sits as a local commit on `dev` in `D:/repos/_work/jnwb_mainjnwb` (local `dev` is one ahead of `origin/dev`) |
| Score | 12/100 verified after that commit lands (17-103, 17-79 closed); gates 0 of 6 complete |

## Do first, in order

1. Read both CI runs on `e6baac97` (`gh run list --branch dev`). Red or cancelled: stop and report; do not claim the closure.
2. In `artifacts/process/release_checklist.md` replace `CI_RESULT_PLACEHOLDER` with the verified result (run ids, conclusion).
3. `python scripts/reconstruct_state.py` (gate 20 file is generated, never committed), then commit the checklist fix with exact paths.
4. Push `dev` only through `bash scripts/jnwb_push.sh /d/repos/_work/jnwb_mainjnwb dev </dev/null`: an artifacts-only push needs no CI in flight and the harness gate. Verify `git ls-remote origin dev`, then CI on the new tip.
5. Clean up: lane branch `_temp_mainjnwb_79psi` (contained in `dev`; worktree `D:/repos/_work/jnwb_l79psi`, check clean first; stop fsmonitor if present) and remote `_temp_mainjnwb_stacks` after step 4. Never change a branch or worktree while a full suite runs (gate 20 reads them).

## What this session did

17-79 closed: `phase_slope_index` 70 to 18, `jrsa` 83 to 16, `vflip` 71 to 17, `xflip` 104 to 28, `zflip` 84 to 19 (AST counter
`D:/tmp/jnwb_orient/_temp_mccabe.py`; the todo's own counter has no producer and gave 67, 93, 71, 109, 80). Each split:
independent differential against the parent over 1112 to 19400 calls, bitwise equal, with planted controls;
independent reviewer ACCEPT. `vflip` and `xflip` changed the source that the curation, vflip and xflip calibration
receipts hash, so those were regenerated: every calibration value identical to pristine, only `estimator_sha256`, the
function list and metadata differ. One substitution-sweep baseline row moved to `_resolve_orientation`. The xflip
unit-factor expression stays in `xflip`'s body so gate 22 (`I2_UNIT_EXCUSED`) still reads it.
Also: the Jynx cleanup Hamm authorized (dev `3d81f0f4`; backup `D:/repos/_backup/jynx_20261119.git` and a bundle;
PR #11 closed; 13 of 14 extra branches deleted; `_temp_seal_20261117` left, another agent pushed to it).

## Open, in order of use

| Id | State |
|---|---|
| Gate A4 | 8 functions above 40 remain by the AST counter (`curate_and_label` 64, `label_layers` 50, `compare_groups` 49, `check_waveform_blocks` 49, `probe_geometry` 49, `vflip2` 46, `_stream_slice` 44, `screen_units_against_labels` 42); no todo item names them; Hamm decides whether 17-79 grows or a new item opens |
| `vflip2-receipt` (main-jnwb) | the `vflip2_separation_0.2.14` receipt hashes changed sources and no test notices; failing-first hash test, then regenerate from pristine and leaf-compare |
| `fact-zflip-cite` (Hamm) | `fact_stack.md:184` cites `_zflip.py:220` and `:256-263`; now `:479` and `:515-522`; propose, never edit the fact stack |
| `17-147-hang` | second recurrence, still no named test; capture the stuck test before killing a stalled run (suspects: wheel and foreign-NWB tests) |
| `17-147-guard`, remainder of 17-147, 17-95 | eligible work |
| Hamm rulings pending | gate 15 (`17-147-gate15`), `17-152-over` policy, `OCMA-5`, 17-151 vs plan, checklist weights, 17-144-src |

Next eligible items: 17-94 (now unblocked), 17-97, 17-98, 17-100, 17-104, remainders of 17-95 and 17-147. Each: failing-first
test, independent `reviewer`, full suite, then `dev` via the wrapper.

## Rules that bit this session

- Full suite on the exact SHA before a push that changes code; the stamp lives in the clone that ran it, so run the suite in the clone you push from.
- A refactor of code that a calibration receipt hashes needs: regenerate from pristine to prove reproduction, regenerate from the split, leaf-compare, write only if values are identical.
- Run a gate that reads a callable's body (gate 22) after the first extraction, not at the end.
- A subagent report is data: re-run its acceptance yourself before accepting.
- No `python -c`, `python -`, heredoc code or `sed -i`. Do not install jnwb into the shared Python (0.2.11 stays).

## Do not

Push `main`, tag, publish, merge or close PR #44, change goal or fact stacks, decide the Hamm rows, push `dev` without the suite and review gates, or force anything.
