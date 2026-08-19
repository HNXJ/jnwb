# PRGS Prepare — omission / jnwb, 2026-08-15

**Purpose of this document:** the entry point into this handoff. Reconstructs, does not fix.
Everything downstream (`JNWB_ARCHITECTURE.md`, `JNWB_API_INVENTORY.md`,
`JNWB_TEST_EVIDENCE.md`, `HARNESS_AUDIT.md`, `NEXT_ACTIONS.md`) is cited from here rather than
repeated.

## 1. Live repository

```
repository root: C:\workspace\omission
branch:          dev
HEAD:            47d364ea8cd9f0899bc23b015d4a787f9d0040c4
origin/dev:      04b6a2b710941430fba0c5fba6f8b36f64f75dc8  (local dev is 1 commit ahead, unpushed)
remote:          origin -> git@github.com:HNXJ/omission.git (SSH)
python:          3.14.3 (both system C:\Python314 and project .venv match)
package manager: pip + pyproject.toml (setuptools backend), project venv at .venv/
working tree:    107 uncommitted paths at start of this session (44 untracked, 53 modified,
                 5 added, 5 deleted) — see §2
```

**OBSERVED FACT, important for anyone resuming this repo:** per this user's own standing memory
note (`project_concurrent_cursor_session`), this repository's working tree is shared with
another live agent session. The 107 uncommitted paths at session start were **not created by
this Prepare pass** and were left untouched throughout — see §2.

## 2. Working-tree state at Prepare start — not touched, not attributed to this task

`git status --short` at the start of this session showed 107 paths: modified figures/scripts
across `context/figures/`, `jnwb/`, `scripts/`; 5 new files under `jnwb/_unused/` +
`scripts/archive_oneoff/`; 5 deletions (`jnwb/complex_tfr.py`, `jnwb/markdown_report.py`,
`scripts/compute_real_channel_band_power_census.py`, `scripts/sync_claude_skills.py`,
`context/figures/fig03_unit_census/fig03.png`); 44 untracked paths including 16
`artifacts/.lab/*.json` evidence-graph nodes and several new `context/figures/` directories.
**None of this was created, staged, or committed by this Prepare pass.** It represents
in-progress work from elsewhere (this machine's other session, per the standing memory note,
or a prior session) and is reported here as an observation, not resolved. See `JNWB_ARCHITECTURE.md`
§0/§9 for the one piece of this state (`jnwb/_unused/` move) that bears directly on the jnwb
architecture map.

## 3. Effective harness — summary (full detail: `HARNESS_AUDIT.md`)

No `AGENTS.md` exists (intentionally retired 2026-08-12). Global `CLAUDE.md` → project
`CLAUDE.md` → `PROJECT_STATE.md`/`EVIDENCE_ARCHITECTURE.md` → 9 skills (7 project + 2 user) is
the complete, git-tracked doctrine stack. Two findings worth leading with:

- **`EVIDENCE_ARCHITECTURE.md` is self-declared `proposed`, not adopted** — its own adoption
  checklist requires `context/ACCEPTANCE_TESTS.md`, which does not exist. By the file's own
  text, `PROJECT_STATE.md` wins any conflict until this resolves. (`HARNESS_AUDIT.md` H1)
- **A stale test (`tests/test_skill_tree_consolidation.py`) asserts the pre-2026-08-12 harness
  shape** (≥10 skills, `jnwb-core` present) and fails against the current, intentionally
  reduced 9-skill state. This is the source of both `pytest` failures reported in §4.
  (`HARNESS_AUDIT.md` H3, `JNWB_TEST_EVIDENCE.md`)

Also flagged: a large git-tracked `legacy/` directory (149 files) outside the doctrine
perimeter; an untracked, gitignored `outputs/docs/GEMINI.md` describing an entirely different
(and non-existent) repo layout, machine-local only; no skill covers the test suite itself.

## 4. jnwb architecture — summary (full detail: `JNWB_ARCHITECTURE.md`, `JNWB_API_INVENTORY.md`)

The package is larger and more layered than its own advertised "v1.0.0 public API": the
`jnwb.ontology`/`jnwb.factories` frozen-dataclass layer and the "20 canonical functions" in
`jnwb.functions` have **no confirmed consumers in `scripts/`** — the real, load-bearing API is
direct submodule imports (`jnwb.paths`, `jnwb.sequence_layout`, `jnwb.unit_classification`,
`jnwb.statistics`, `jnwb.connectivity`, `jnwb.omission_identity`, `jnwb.permutation`,
`jnwb.artifact_repair`, `jnwb.spectral`, `jnwb.viz`, `jnwb.structured_identity*`, `jnwb.jrsa`),
used by ~136 of 245 files under `scripts/`.

The ontology/identity layer (`trial_ontology.py`, `omission_identity.py`,
`structured_identity.py`, `structured_identity_m2a.py`) is the most invariant-protective part
of the package — it documents, in-source, two previously-real bugs it now prevents (the
2026-08-06 p4 A/B label swap; the task_block_number contiguous-block misassumption), and two
functions in `omission_identity.py` carry a live, self-declared `"invalid_for_inference"` status
(quarantined, not deleted).

The single highest-severity finding is in `jnwb/report.py`: four report sections run real
statistical tests (`mannwhitneyu`, BH-FDR) on `np.random`-generated synthetic data, tagged with
a non-conforming orange "SIMULATED DATA" pill rather than the project's own mandated red
`PLACEHOLDER-DUMMY` title — while a fifth section in the same file, doing real computation, is
correctly badged, proving this is an inconsistency rather than a missing capability.

## 5. Scientific-semantics classification (task step 4)

| Invariant | Classification | Where |
|---|---|---|
| Event rows treated as trial rows | **enforced** | `trial_ontology.build_trial_ontology` |
| p1-p4 addressing stability | **enforced, one historical violation, fixed and documented** | `omission_identity.py:38-44` |
| Full-sequence vs omission-relative time base distinguishability | **enforced as separate constants; cross-reconciliation unknown** | `structured_identity_m2a.WINDOWS_MS` vs `omission_identity.OMISSION_IDENTITY_CONDITIONS` |
| SPK/MUAe/LFP non-conflation | **enforced at data access; not enforced at the generalized connectivity layer (deliberate)** | `analog.py` vs `connectivity.py` |
| Channel-area segmentation canonical/deterministic | **enforced for ≤2-area probes; weaker ("legacy fallback") for >2-area** | `addressing.py`, `sequence_layout.py:178` |
| Multi-area probes handled explicitly | **enforced** | `addressing.py:55-77`, documented bug fix |
| Unit area via peak/anchor-channel | **enforced, but two coexisting unit-identity conventions coexist (row-position vs `unit_id` column)** | `session.py` vs `omission_identity.py` |
| Tensor dims/units not silently transformed | **mostly enforced; one confirmed axis-identity loss** (`analyzers.compare_conditions` returns flattened p-values with no index back-map) | `analyzers.py:150-165` |
| Empty selections fail visibly | **violated, pervasively, by design choice not oversight** — `session.py`, `spectral.py`, `metadata.py`, `functions.py` default to empty/zero/NaN returns rather than raising | see `JNWB_ARCHITECTURE.md` per-layer failure-behavior rows |
| Condition names/omission positions retain canonical semantics | **enforced, with a documented historical violation (fixed) and two currently-quarantined functions (open)** | `omission_identity.py` |

## 6. Test evidence (task step 6) — summary, full detail `JNWB_TEST_EVIDENCE.md`

`git diff --check` exit 0. `pytest -q --collect-only`: 442 collected, 0 errors.
`pytest -q`: **396 passed, 2 failed, 44 skipped**, 156s. Both failures trace to the one stale
harness-shape test (§3). No coverage tool run; real-NWB-fixture vs. synthetic-fixture split not
enumerated across the 442 tests (open item, `NEXT_ACTIONS.md`).

## 7. jnwb state — scores (task step 7)

Scored out of 100 per category. Each score is a judgment call grounded in the evidence above,
not a formula — treat as ranked ordering more than a precise number.

| Category | Score | Why |
|---|---|---|
| Scientific semantic correctness | 62 | strong invariant-protection in the ontology layer, self-documented bug history and honest limits; undermined by the two coexisting unit-identity conventions and the unreconciled band-edge tables |
| Data-model correctness | 58 | row-position vs `unit_id`-column identity footgun is real and only partially guarded; multi-area channel addressing has an unweighted fallback path for >2-area probes |
| API design | 45 | two competing public surfaces (frozen ontology/factories, 20 canonical functions) both unused by real consumers, while the actually-used API is undocumented as "the" API anywhere; several dead parameters (`by_layer`, `output_dir`) |
| Architecture | 55 | deliberate, documented separation of signal classes at the data layer; deliberate, documented class-agnosticism at the connectivity layer (a real tradeoff, not sloppiness); `jnwb/_unused/` git-incomplete move; two independent Granger implementations |
| Real-data reliability | 50 | pervasive empty/zero/NaN-on-missing-data pattern across the most-used modules (`session.py`, `spectral.py`, `metadata.py`, `functions.py`) makes "no data" and "real near-zero result" indistinguishable in several return values without extra caller-side checking |
| Test quality | 60 | 442 tests, real assertions, no bare-except test anti-patterns found; but 2 failures are stale-harness noise obscuring the real signal, no dedicated test for `omission_identity.py` (699 lines, contains quarantined functions) or `ontology.py`, no coverage measurement |
| Reproducibility/provenance | 66 | strong: `jnwb.paths` centralizes environment drift, `sha256_file`/receipt discipline is real and used, most modules seed RNGs explicitly (seed 42); weak point: `jrsa.py`'s CuPy RNG paths are not seeded from the caller's `random_state`, breaking reproducibility exactly where the rest of the module establishes it |
| Performance | not scored | out of scope for this Prepare pass — no profiling was run; GPU/CPU fallback patterns were catalogued (architecture doc) but not benchmarked |
| Documentation | 52 | docstrings are extensive and often carry real incident history (a genuine strength), but at least one confirmed docstring/code mismatch (`analyzers.py:7` changelog vs. :97-99 actual behavior) and one confirmed stale-column docstring (`metadata.py:44` vs :178-180) |
| Maintainability | 50 | two parallel unused API layers add real cognitive load for a future maintainer; the invariant-protective ontology modules are a maintainability asset, not a liability |

**Overall: ~55/100.** This is not a "broken" package — the parts that matter most scientifically
(condition-code parsing, unit identity, artifact repair, RNG seeding, path resolution) are
carefully built and self-documenting about their own history of bugs. The score is pulled down
by: a large unused "public API" surface presented as canonical, one confirmed
mandated-placeholder-labeling violation (`report.py`), pervasive silent-empty-return behavior in
the most-used modules, and two coexisting incompatible unit-identity conventions.

## 8. P0-P3 findings (evidence in the linked docs; not fixed here)

**P0 (blocker):**
- `jnwb/report.py` fabricates statistical results on synthetic data without the project's
  mandated red `PLACEHOLDER-DUMMY` label (`JNWB_ARCHITECTURE.md` §9).
- `context/EVIDENCE_ARCHITECTURE.md` names a required file (`context/ACCEPTANCE_TESTS.md`) that
  does not exist — the evidence-standing contract this project relies on is not actually
  adopted (`HARNESS_AUDIT.md` H1).

**P1 (important):**
- Two coexisting, incompatible unit-identity conventions (row-position vs `unit_id` column)
  across `session.py`/`ontology.py`/`factories.py` vs `omission_identity.py`
  (`JNWB_ARCHITECTURE.md` §4).
- Two numerically disagreeing "canonical" band-edge tables (`connectivity.CANONICAL_BANDS` vs
  `sequence_layout.BANDS_7`) (`JNWB_ARCHITECTURE.md` §4).
- `jrsa.py`'s `_pearson`/`_spearman`/`_procrustes` fabricate literal null-result values on
  internal computation failure instead of raising/NaN (`JNWB_API_INVENTORY.md`, jrsa row).
- `jrsa.py`'s CuPy RNG paths are unseeded from `random_state` — GPU results not reproducible.
- Two dead public API layers (ontology/factories, 20 canonical functions) with zero confirmed
  `scripts/` consumers, presented as the frozen v1.0.0 public API (`JNWB_ARCHITECTURE.md` §7).
- No dedicated test file for `jnwb/omission_identity.py` (699 lines, two quarantined
  decode functions) or `jnwb/ontology.py`.

**P2 (improvement):**
- Stale `tests/test_skill_tree_consolidation.py` asserting the pre-reset harness shape
  (`HARNESS_AUDIT.md` H3).
- `analyzers.py`'s changelog claims a hard-error behavior the code doesn't actually implement
  (`JNWB_API_INVENTORY.md`, analyzers row).
- Two stale skill docs pointing at `jnwb.complex_tfr`/`jnwb.markdown_report`, paths deleted on
  2026-08-14 (`JNWB_ARCHITECTURE.md` §0).
- `jnwb/_unused/` move is git-incomplete (staged add, unstaged delete)
  (`JNWB_ARCHITECTURE.md` §0/§9).
- 149-file git-tracked `legacy/` directory outside the doctrine perimeter (`HARNESS_AUDIT.md`
  H4).

**P3 (cleanup):**
- Dead parameters `pie_charts(..., by_layer=...)`, `summary_report(..., output_dir=...)`
  (`JNWB_API_INVENTORY.md`, functions row).
- `_acg_pearson` alias name is misleading (doesn't compute Pearson correlation)
  (`JNWB_API_INVENTORY.md`, analyzers row).
- Machine-local, gitignored `outputs/docs/GEMINI.md` describes a nonexistent repo layout
  (`HARNESS_AUDIT.md` H4) — won't propagate but could mislead a session on this machine.

## 9. What this Prepare pass did not do

- Did not fix, refactor, or repair anything found above.
- Did not resolve the concurrent working-tree changes from another session (§2) — left as
  found.
- Did not open `tests/test_jnwb_nwb_integration.py`, `jnwb/viz.py`, or `jnwb/__init__.py`
  end-to-end (see `JNWB_API_INVENTORY.md` "not independently verified this pass").
- Did not re-derive labyrinth graph health (`PROJECT_STATE.md §7` already flags this as owed,
  separately, to the `labyrinth` skill's own workflow).
- Did not run a coverage tool or triage the 44 test skips individually.

See `NEXT_ACTIONS.md` for proposed, **not approved**, next Review→Progress cycles.
