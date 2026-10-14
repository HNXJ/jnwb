# Blocker fixpoint receipt, 0.2.12

| Field | Value |
|---|---|
| commit | `72543425a492ab7f6715aae146fe600bc2ff047a` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` section 11 condition 3: the terminating condition is an independent blocker-focused pass that finds no new release-blocking problem; next-cycle observations become `deferred-0.2.13` entries |
| pass | Independent reviewers, none of whom wrote what they reviewed: two closure passes over `v0.2.11..c0d96dc9` (Muse and Opus), a verifier (Opus) over the repairs to `0c4c6bb5`, a verifier (Haiku) over the repair of what that verifier found, and a verifier (Haiku) over the repair of CI's one failure on `bafcbbca` |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Closure pass (Muse) over `v0.2.11..c0d96dc9` (268 files): scope against the 2026-10-12 to 10-14 rulings, the laminar code and docstrings, the `[0.2.12]` changelog, release mechanics, docs and skill rows | `c0d96dc9` | DEFECT: `skills/jnwb-laminar/SKILL.md` gave `motif_quality="absent"` below any cut; the tiers are fixed at 6 and 12 | repaired in `2a7c4198` |
| Closure pass (Opus) over the same delta: STEP 0a probed through `check_release_readiness`, `vflip2` probed on 40 seeds and at `omega_cut=12`, the changelog against `git diff v0.2.11`, workflow SHA pins | `c0d96dc9` | DEFECT: 15-11's `Release:` field shared a line, so STEP 0a read it as required; `docs/laminar.md` asserted recovery of the generator's crossover (8 of 40 seeds within one contact); 14-05 deferred with no ruling; the skill line above | repaired in `7f521e6e`; 14-05 and the five-release window ruled in `0c4c6bb5`; next-cycle findings are roadmap 15-13 to 15-15 |
| Verifier (Opus) over `c0d96dc9..0c4c6bb5`: each repair against the code, the `xflip` null at both versions (omnibus p 0.004975 -> 0.726368 at `rng=0`) | `0c4c6bb5` | DEFECT: the `zflip` row's unescaped `\|` split its cell and the new rows failed five docs tests; `curate_and_label`'s xFLIP p-values moved (0.666667 -> 0.705882) without a `[results change]` line; `CHANGELOG.md` omitted 0.2.5 from the archived releases | repaired in `bafcbbca` |
| Verifier (Haiku) over `0c4c6bb5..bafcbbca`: five docs and changelog test files alone (58, 54, 11, 18 and 2 passed), cell counts of the three rows (9 of 9), `vflip2` and `vflip2_from_lfp` parameters against `inspect.signature` (0 mismatches), `VFlip2Result` mapping access, the 0.2.5 archive | `bafcbbca` | PASS | 0 |
| CI on `bafcbbca`, installed-wheel leg | `bafcbbca` | DEFECT: `test_the_evidence_table_matches_the_script_on_the_power_example` imports `scripts/vflip2_sensitivity.py`, whose guard refused a jnwb from site-packages (1 failed, 8521 passed) | repaired in `cbd7e824` |
| Verifier (Haiku) over `cbd7e824`: the diff touches only the script; the guard accepts the import from `JNWB_EXPECTED_PACKAGE_ROOT`, as CI sets it to purelib, refuses another root, and is unchanged with the variable unset; the test file alone (3 passed); the other script guards tests reach | `cbd7e824` | PASS | 0; two guards no test reaches in that leg are roadmap 15-16 |

`cbd7e824..72543425` adds only roadmap row 15-16.

## Receipts at `cbd7e824`

| Check | Result |
|---|---|
| Harness gates | 22 of 22 passed |
| Full suite | 8558 passed, 58 skipped, 36 xfailed, 0 failed (`jnwb_suite.sh`, stamp equal to the commit) |
| Peak-memory record | `jnwb_version` 0.2.12, measured on a clean tree at `6bbdcb2a`; later commits change under `jnwb/` only the `VFlip2Result.omega` docstring |
| Release gate | STEPs 0a to 0d passed at `adf256e1`; STEP 0e and later need CI on the commit that records this receipt |
| NOT RUN | the CUDA constant-channel test |
