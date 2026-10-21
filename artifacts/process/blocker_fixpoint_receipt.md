# Blocker fixpoint receipt, 0.2.13

| Field | Value |
|---|---|
| commit | `701dad711d2e0a3648551fc7c4f531715379deff` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` section 11 condition 3: the terminating condition is an independent blocker-focused pass that finds no new release-blocking problem; G-04 (2026-10-19): each advertised scientific claim is checked against the deferred rows; next-cycle observations become `deferred-0.2.14` entries |
| pass | Independent reviewers, none of whom wrote what they reviewed: two closure passes over `v0.2.12..4490eaad` (Muse, read-only; Haiku 5.5 at xhigh, with probes), a Muse review of the repairs to `3b43b449`, and the dispatcher's byte check of the archived changelog block |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Closure pass (Muse) over `v0.2.12..4490eaad`: the four blocker classes of the packet, refusal and numeric repairs read in the code, docs against signatures, G-04 over 12 advertised claims, every added symbol in `CHANGELOG.md` and `docs/api.md` | `4490eaad` | PASS; one formatting slip (the `fuse_laminar_anchors` line lacked its path span) | 0; repaired in `4fd41718` |
| Closure pass (Haiku 5.5, xhigh) over the same delta: G-04 over all 38 deferred roadmap rows (301 matched lines), 148 `docs/api.md` rows against `inspect.signature`, 70 probe results across five scripts | `4490eaad` | DEFECT claimed on two rows: (1) the CSD changelog line said NaN or infinite inputs are refused; the code refuses a non-finite `pitch_um` or `conductivity_s_per_m`, not a non-finite array, so the line overclaimed; (2) "18 of 100 noise-only" was called unsourced | (1) the line reworded in `4fd41718` and `3b43b449`, the code unchanged; (2) shown false: `artifacts/evidence/0.2.12/vflip2_simulation.md:21`, null row, 100 probes, 18 accepted, ruled 2026-10-14 |
| Haiku G-04 note: the 14 core-text claim cells of `docs/references.md` rest on no abstract | `4490eaad` | not a blocker: the cells state what jnwb follows from a textbook, a reading; roadmap 16-11 holds the full-text check | 0 |
| Haiku G-04 note: result-record claims near rows 16-05 to 16-07 | `4490eaad` | the per-function record lines hold in the code; one summary line made the library-wide S10 claim (row below) | 0 here; 1 claim cut below |
| Muse review of `4490eaad..3b43b449` (the checkpoint repairs: changelog archive move, CSD and fuse lines, the expired `gpu_pca` record, the `docs/laminar.md` path, the peak-memory record), 20 of 95 `[0.2.13]` lines against the code | `3b43b449` | PASS | 0 |
| Dispatcher: the 0.2.6.1 and 0.2.6 block removed from `CHANGELOG.md` at `4490eaad` occurs once, byte for byte, in `artifacts/archive/changelog_0.1.0-0.2.9.md` (41,922 bytes) | `3b43b449` | PASS | 0 |
| Dispatcher, G-04 on the Haiku pass's result-record note: `docs/07_statistical_inference_and_nulls.md:3` said permutations run under a named exchangeability scheme, which is fact S10 across the library, and roadmap 16-05 (the S10 scan) is deferred; the per-function lines (`jrsa`'s `execution["null"]`, Granger's `surrogate_seed_entropy`, `permute_labels`' required `scheme`) were read in the code and hold | `ceccdcb9` | the claim cut to label permutation, as G-04 rules | 0; repaired in `d9af4264` |
| CI on `main` at the merge `09355a7d`: every test leg failed one test, `test_it_reports_worktrees_branches_the_dev_run_and_open_defect_classes`, which asserted a `dev` row; a `main` checkout has no local `dev`. Dispatcher: on a single-branch clone of `main` the old test fails and the repaired one, asserting the checked-out branch, passes | `701dad71` | DEFECT in the test, not the package | 0 in the package; repaired in `701dad71` |

`3b43b449..a6ed14c3` also reruns the curation calibration under the declared 0.2.13 (estimator `a7069e76ec6d3429`, counts unchanged), merges `proposal/spike-qc-pt-skill` at `75193730` (four files under `artifacts/evidence/0.2.9/spike_qc_pt_skill/`, none shipped; its draft renamed `proposed_skill.md` in `a6ed14c3` so the one-skill-tree test still sees one tree), and points the eta-squared test at the changelog archive, where its 0.2.6 entry moved.

## Receipts at `a6ed14c3`

| Check | Result |
|---|---|
| Harness gates | 22 of 22 passed |
| Full suite | 9042 passed, 62 skipped, 38 xfailed, 0 failed (`jnwb_suite.sh`, stamp equal to the commit) |
| Docs build | strict MkDocs build passed at `d9af4264`; `d9af4264..a6ed14c3` changes no page |
| Peak-memory record | `jnwb_version` 0.2.13, measured at `4490eaad`; every operation within 3.4 MiB of 0.2.12 |
| Release gate | STEPs 0a to 0d passed at `09355a7d`; STEP 0e and later need CI on `main` at the merge that carries this receipt |
| NOT RUN | the CUDA constant-channel test |
