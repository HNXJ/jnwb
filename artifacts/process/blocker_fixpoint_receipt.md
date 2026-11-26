# Blocker fixpoint receipt, 0.2.17 candidate

| Field | Value |
|---|---|
| commit | `4dd60b8e8ada2e8d7faf30739bb419fa47269a91` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` section 11 condition 3: an independent blocker-focused pass finds no new release-blocking problem; G-04 (2026-10-19): each advertised scientific claim is checked against the deferred rows |
| scope | One full pass at `88bbc699262c5b82b0a2ec755d5952513aa8ffab`, then a delta review of each later commit up to `4dd60b8e`. Every change since `88bbc699` is under `artifacts/` (four files, checked by `git diff --name-only`); no code, test, script or docs file changed |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Full closure pass: advertised claims in README, `docs/` and the changelog checked against the deferred rows (15-11, 12-21, 16-12); stack consistency; changelog entries spot-checked against the code. Not run: float32 NaN conversion, ragged empty block, repair catalog refusal, electrodes-region integrity, processing-table hint, 1-D refusal text | `88bbc699` | CLEAN | 0 |
| Delta review, independent reviewer: open-stack header, A5 row and 12-21 status reconciled | `ad4e68c1` | CLEAN | 0 |
| Delta review: update-log row recording the gate receipts | `d784399` | ACCEPT | 0 |
| Delta review: 17-166 and 17-167 moved from the todo stack to the roadmap as `deferred-0.2.18`; the gate was not changed | `dcfd839` | ACCEPT | 0 |
| Delta review: roadmap wording restored after the move | `4dd60b8e` | ACCEPT | 0 |

## Stale statements found by the full pass

| Statement | Status |
|---|---|
| `artifacts/process/release_checklist.md` A5 row: "six todo items labelled deferred-0.2.17 ... 7 violations" | repaired at `ad4e68c1` |
| `artifacts/roadmap.md` row 12-21: delay and direction "wait for a broadband jaxfne field" | repaired at `ad4e68c1`; the row stays open for the delay estimand |
| `artifacts/open_stack.md` header: `dev` at `68995c90` | repaired at `ad4e68c1` |
| `README.md:50` and `jnwb/__init__.py:14` read 0.2.16 | open: the version bump is R4, owner only |
| `README.md:22` (roadmap 17-167, N1) | open: `deferred-0.2.18`, waits on Hamm's wording |

## Open at this commit

| Item | State |
|---|---|
| 17-144-src, the jaxfne isi_cv commits | UNKNOWN; blocks 0.2.17. Recovery request drafted for Hamm to post; roadmap 16-12 depends on it |
| 13 changelog fragments in `artifacts/changelog.d/` | unassembled; assembly is the release step (`scripts/assemble_changelog.py`, R4) |
| Version | declared 0.2.16; the bump is R4, owner only |

## Receipts

| Check | Result |
|---|---|
| Harness gates | 22 of 22 at `ad4e68c1` (`harness_ad4e68c1.log`); the later commits change artifacts only |
| Full suite | 11145 passed, 163 skipped, 36 xfailed, 0 failed at `ad4e68c1` (`jnwb_suite.sh`; stamp equal to that commit) |
| Complexity gate (A4) | `ruff check --select C901 jnwb/`: all checks passed at `ad4e68c1` |
| Docs | `docs_build.py` strict: exit 0, no WARNING line, at `ad4e68c1` |
| CI on `dev` | `ad4e68c1`: runs 45727251686 and 45727243852 concluded success. `4dd60b8e`: runs 45736611170 and 45736607156 were in progress when this receipt was written; the push waits on them |
| STEP 0 | `release_gate.py` exit 1 at 0a at `4dd60b8e` (`step0_C3.log`): `17-144-src` open; the receipt names an older commit, which this file corrects; 13 changelog fragments unassembled. Steps 0b to 8 and the suite did not run |
