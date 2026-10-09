# jnwb lane G: pitfall tests and four problem rows (2026-10-09)

Session: opencode, workspace `D:\cowork\jnwb`, a fresh clone of `git@github.com:hnxj/jnwb.git`
branch `dev` at `a6b804d2`. Nothing committed or pushed at the time of writing.

## What landed

Six items of `artifacts/todo_stack.md` lane G, as one new file
`tests/test_connectivity_pitfalls.py` (40 tests). The six items were deleted from the todo
stack in the same change, per `AGENTS.md` §2.

| Item | Claim the test holds |
|---|---|
| 10-11 | A shared reference inflates coherence (0.715 -> 0.047) and Granger F (51.99 -> 0.479) on the same pair; `bipolar_reference` cancels it |
| 11-10 | Zero-lag mixing: coherence 0.853 while `icoh_mean` 0.0018, `icoh_abs_mean` 0.0093 and `wpli` 0.0444 stay near zero |
| 11-12 | An unequal-delay common driver: bivariate `f_x_to_y` 548.44 falls to 0.326 when the driver is passed as `Z`, at order 3; at order 2 the removal does not happen |
| 11-13 | PPC and debiased wPLI stay near zero at K = 4, 8, 16, 32 while plain coherence tracks 1/K |
| 11-11 | Two channels that do not couple gain a significant reported direction once one is noisier |
| 11-31 | All nine rows of the `docs/common_mistakes.md` pitfalls table map to a holding class, checked against the table as it reads on disk |

## Evidence

- `python -m pytest tests/test_connectivity_pitfalls.py -q`: 40 passed.
- 18 planted mutants, one per claim, all killed; both mutated files byte-restored after each run.
- `python scripts/harness_gate.py`: 22 of 22 gates PASS.
- Full suite: in flight at the time of writing, no receipt yet.

## PERSISTENCE RISK: pypeline-jnwb-repair-dev's unpushed commits

Unresolved, and needs Hamm.

`pypeline-jnwb-repair-dev` reported commit `614866fb` (#28) and `fb29fa66` (#29) on branch
`pypeline-issues-27-29`, unpushed, in a worktree it named as
`D:\_BL_DATA_PIPELINE\_SCRATCH\jnwb_issues`. That path does not exist on this machine.

Diagnostics on `D:\cowork\jnwb` (diagnostic only; no recovery operation attempted):

| Command | Result |
|---|---|
| `git worktree list --porcelain` | one entry, this clone, `HEAD a6b804d2`, branch `dev` |
| `git branch -avv` | `dev`, `origin/HEAD`, `origin/dev`, `origin/gh-pages`, `origin/main`, `origin/nwb-repair-primitives`; no `pypeline-*` branch |
| `git reflog --all` | 3 entries, all from the clone |
| `git fsck --no-reflogs --unreachable` | no output |
| `git fsck` (with reflogs) | no dangling or unreachable objects |
| `git ls-remote --heads origin` | `dev`, `gh-pages`, `main`, `nwb-repair-primitives` only |

`614866fb` and `fb29fa66` are not valid objects in any jnwb checkout on this PC
(`E:\repos\jnwb`, `E:\repos\_wt_jnwb_c8`, others), and `p-pypeline` on the hub holds no
messages.

**Conclusion:** the commits are not recoverable from this machine. Only a push from the
session holding them, or a `git bundle` exported from that machine, recovers them. Issues
#27-#29 stay assigned to that session. Do not close, reassign or duplicate the
implementation until recoverability is settled.

## Four problem rows, each with a discriminator

Each row records what was measured and what was ruled out, not a reproduction alone.

### P-359 `granger` reports a direction between channels that do not couple

Two independent AR(2) processes with extra noise on one give `p_x_to_y` = 0.005 at order 8
while no direction exists.

- **Not a surrogate-calibration defect.** Against a null that phase-randomises `y`,
  destroying cross-dependence while preserving both marginals, the observed F of 12.70 sits
  against a null mean of 1.93 and a 95th percentile of 3.69. p = 0.005 under both nulls at
  10 of 10 seeds. The predictability is in the data as fitted.
- **It needs the asymmetry.** With matched noise the same pair is silent at every order from
  1 to 20, 10 of 10 seeds.
- **The direction follows the order, not the signal-to-noise ratio.** At order 1 the credit
  runs y to x at 7 of 10 seeds; at every order from 2 to 20 it runs x to y at 9 or 10 of 10;
  reversing the asymmetry removes it at order 8. So `docs/common_mistakes.md:431`'s "the
  better channel appears to lead" does not describe this case.

Whether the underlying predictability is an artefact of unequal observation noise (Smith and
Pigott 2018) or of the VAR fit is **not settled here**.

### P-360 `diagnostics['stationary']` is a VAR eigenvalue flag, not a stationarity test

The key is `bool(spectral_radius < 1.0)` (`jnwb/connectivity/_granger.py:1074`).

| Fixture | ADF p | radius | `stationary` |
|---|---|---|---|
| random walk | 0.0009 | 0.99613 | True |
| AR phi=0.999 | 0.5004 | 0.99860 | True |
| 0.05 Hz drift | 0.0000 | ~1.00000 | build-dependent |
| AR phi=1.002 | 1.0000 | 1.00200 | False |
| stationary AR | 0.0000 | 0.75789 | True |

The slowly decaying mode the row names passes unflagged, and `granger`'s ADF check calls that
same fixture a unit root, so the two estimators disagree. The drift reaches a radius within
float rounding of 1.0, so which side of the strict comparison it lands on is a property of
the linear-algebra stack rather than of the data: the development machine put it 1.6e-15
below (reported `stationary` True), while CI's stack put it at or above 1.0 (reported False).
Either way the placement is within float rounding of the threshold; whether a warning fires
there is build-dependent too (this machine: none; CI: one), so a mode sitting on the boundary
gets no reliable signal at all.
Neither test is reliable alone: the ADF verdict on a random walk flips between the raw series
(p = 0.0009, stationary) and the lagged copy `granger` is actually handed (p = 0.085, unit
root). Only the explosive mode is caught by both. `docs/common_mistakes.md:437` states the
radius rule correctly, so this is a coverage gap, not a false promise.

### P-361 filtering before `granger` is not a band selector

Measured across orders on a VAR(3) pair, raw-to-filtered `f_x_to_y` ratio:

| order | 1 | 2 | 3 | 4 | 6 | 8 | 12 | 20 |
|---|---|---|---|---|---|---|---|---|
| ratio | 6604 | 2075 | 0.666 | 0.498 | 0.449 | 0.577 | 0.730 | 0.725 |

At the true order and above, the invariance broadly holds as Barnett and Seth (2011) state,
including with `zero_phase=False` (0.479). The order-1 and order-2 figures are
misspecification interacting with the filter, so they are **not** evidence against the
invariance. What remains: `order='auto'` moves from 3 to the `max_lag` ceiling of 20, and no
filter recovers a band value (`granger_spectral` `per_band['full']` 0.2976 against
`granger`-filtered 0.2080; 8-60 Hz gives ratio 0.666 and 30-80 Hz gives 0.457).

### P-362 `phase_slope_index` converts a delay asymmetry into a lead

An unrecorded driver reaching `x` after 1 sample and `y` after 4 gives `net` 0.538 and
`p_net` 2.28e-23 with an empty `warnings` list.

- **General, not a fixture artefact.** AR(1) at phi 0.3 to 0.99, white noise and a random
  walk all produce it (p between 4e-24 and 7e-21); delay pairs (1,2), (1,4), (1,8), (2,5),
  (3,10) all produce it; noise from 0.01 to 0.3 all produce it. `net` scales with the delay
  difference: 0.18, 0.54, 1.24.
- **The equal-delay control is clean**: p 0.06 to 0.88, `abs(net)` <= 0.0134. The asymmetry
  is what PSI converts into a lead.
- **Boundary is band occupancy**: a single-frequency driver gives nothing, which
  `_psi.py:202` and `SKILL.md:53` already state; adding broadband power to the same driver
  restores it at p = 2e-14.
- **Vocabulary is already constrained.** `common_mistakes.md:432` names the common-input row
  for phase slope, `:166` lists a common driver with asymmetric conduction delays as what PSI
  cannot rule out, `_psi.py:161,169` and `SKILL.md:29` bind the estimator to lead and forbid
  causal verbs. This is a **cross-reference gap**, not a vocabulary gap: row 435's guard
  column cites only the PSI page, whose section never names unequal-delay common input.

## Disposition

The four rows above moved out of `artifacts/problem_stack.md` into `artifacts/todo_stack.md`
as items 11-37 to 11-40 in the same change, because the live problem stack must hold no row
on `dev`. The items carry the wording-and-coverage work; no estimator is repaired in this commit.

## What is not done

- No estimator repair. These four rows are investigations; the commit adds tests and stack
  entries only.
- The full suite has no receipt yet, so nothing is committed.
- `pypeline-jnwb-repair-dev` #27 is a science check and needs a verifier who is not its
  author. `vwin-claude-sonnet55-jnwb` offered to run it on posted base/head SHAs.