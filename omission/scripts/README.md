# `scripts/` — one-off analysis and aggregation scripts

**Purpose:** standalone, runnable analysis code. Each script reads from `jnwb_ext`/`jnwb` and
raw/derived data, writes to `../outputs/`.

**Owns:** current analysis scripts at the top level; `archive_oneoff/` for one-shot scripts kept
for provenance (not meant to be re-run as part of a current pipeline); `historical/confounded/`
for scripts quarantined 2026-08-10 for invalid/ungrouped cross-validation — **do not use as
empirical sources**, see `../artifacts/.lab/agent-harness-audit-20260810.json`.

**Fragile path assumption — read before moving anything in this tree:** most scripts resolve the
repo root via `Path(__file__).resolve().parents[N]`, where `N` depends on nesting depth from
`scripts/` (`parents[1]` for a script directly in `scripts/`, `parents[2]` for one level deeper
such as `archive_oneoff/` or `historical/confounded/`). This is why `scripts/`'s internal
structure was left untouched during the 2026-08-24 `omission/` reorganization: changing any
script's directory depth silently breaks its `REPO_ROOT`/`REPO` resolution unless the
`parents[N]` index is updated to match. If a script needs to move, update its index in the same
change and verify with `python <script>.py --help` or an equivalent dry run before considering
the move complete.

**Does not own:** generated outputs (`../outputs/`) or scientific state (`../context/PROJECT_STATE.md`).
