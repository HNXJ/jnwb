# Blocker fixpoint receipt, 0.2.17 candidate

| Field | Value |
|---|---|
| commit | `aa5c10831c0afed9d781d346fb60de469726acd1` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` section 11 condition 3: an independent blocker-focused pass finds no new release-blocking problem; G-04 (2026-10-19): each advertised scientific claim is checked against the deferred rows |
| scope | One full pass at `88bbc699262c5b82b0a2ec755d5952513aa8ffab`, then a delta review of each later commit up to `aa5c1083`. Every change since `88bbc699` is under `artifacts/` (checked by `git diff --name-only`); no code, test, script or docs file changed |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Full closure pass: advertised claims in README, `docs/` and the changelog checked against the deferred rows (15-11, 12-21, 16-12); stack consistency; changelog entries spot-checked against the code. Not run: float32 NaN conversion, ragged empty block, repair catalog refusal, electrodes-region integrity, processing-table hint, 1-D refusal text | `88bbc699` | CLEAN | 0 |
| Delta review, independent reviewer: open-stack header, A5 row and 12-21 status reconciled | `ad4e68c1` | CLEAN | 0 |
| Delta review: update-log row recording the gate receipts | `d784399` | ACCEPT | 0 |
| Delta review: 17-166 and 17-167 moved from the todo stack to the roadmap as `deferred-0.2.18`; the gate was not changed | `dcfd839` | ACCEPT | 0 |
| Delta review: roadmap wording restored after the move | `4dd60b8e` | ACCEPT | 0 |
| Delta review: 17-144 provenance record (section 7), the 16-12 wording and the store-count corrections: `3b475620`, `8a2d45eb`, `345f139`, `7605b3b3`, `18eb8af9` (artifacts only). Earlier versions were rejected for wording and fixed; the final versions were accepted | `18eb8af9` | ACCEPT | 0 |
| Delta review, independent reviewer (a fresh pass on the uncommitted set, then a delta on its three findings): reopened 17-100, 17-101 and 17-129 (todo sections restored from `d84577ea^`); 17-168 roadmap row removed; 17-99 closed on Hamm's ACCEPT and its plan items entry removed; rulings file `2026-11-25.md`; checklist and open-stack reconciled. First pass REVISE: one major (17-101 text still cited a `memory.md:7` path removed by `12c9fa43`), two minor (D4 row; a rulings-file pointer to a non-existent checklist section). All three fixed; delta ACCEPT | `aa5c1083` | ACCEPT after REVISE | 0 release-blocking |

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
| 17-144-src, the jaxfne isi_cv commits | UNKNOWN; blocks 0.2.17. Own content and reachable alternates of the 322 stores with an unresolvable alternate were checked: none holds the three SHAs; 125 alternate targets are absent here (17-144 evidence, section 7). No recovery route on this machine (no jchat identity; Hamm decides the channel, 2026-11-25); roadmap 16-12 depends on it |
| 13 changelog fragments in `artifacts/changelog.d/` | unassembled; assembly is the release step (`scripts/assemble_changelog.py`, R4) |
| Version | declared 0.2.16; the bump is R4, owner only |

## Receipts

| Check | Result |
|---|---|
| Harness gates | 22 of 22 at `ad4e68c1` (`harness_ad4e68c1.log`); the later commits change artifacts only |
| Full suite | 11145 passed, 163 skipped, 36 xfailed, 0 failed at `ad4e68c1` (`jnwb_suite.sh`; stamp equal to that commit) |
| Complexity gate (A4) | `ruff check --select C901 jnwb/`: all checks passed at `ad4e68c1` |
| Docs | `docs_build.py` strict: exit 0, no WARNING line, at `ad4e68c1` |
| CI on `dev` | `ad4e68c1`: runs 45727251686 and 45727243852 concluded success. `4dd60b8e`: runs 45736611170 and 45736607156 concluded success (read through the public API 2026-11-25) |
| STEP 0 | Run at `aa5c1083` with this receipt on the working tree (`step0_aa5c1083.log`, outside the repository): exit 1 at 0a. The committed receipt still named `18eb8af9` (5 files changed since), so the commit binding failed; this commit sets it to `aa5c1083`. Open at 0a: `17-144-src`; 13 changelog fragments unassembled (R4). Steps 0b to 8 and the suite did not run |
