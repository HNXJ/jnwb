# Agent Harness Audit — 2026-08-10

Read-only audit per Sol's Handout 1. No scientific analysis code was modified during this
phase. Produced by Claude Code, using four parallel read-only research passes (instruction
precedence, stale-fact sweep, skills-vs-doctrine, tooling friction) plus direct reading of the
14 decoding scripts and the core `jnwb/omission_identity.py` module by the compiling agent.

## Preflight — state has already drifted from the assumed baseline

Sol's handout assumed:
```
branch: nwb-fp32-compression-pipeline
baseline SHA: a37694ee10e1feb893249b123e744e14fab065cc
known pre-existing dirty file: artifacts/.lab/nwb-conversion-v1-reference-corruption-caught-20260808.json
```

Re-run, per instruction not to assume this is unchanged:
```
branch: dev
HEAD: 067de20ea63c93e20e25601854ffe5c634e38bc0
git status --short: (empty — clean)
python --version: Python 3.14.3
```

`nwb-fp32-compression-pipeline` no longer exists as a branch — it was merged into `dev` earlier
today as part of a branch-consolidation task, and the "known dirty file" is now committed and
clean. This is exactly the kind of drift Sol's handout anticipated by requiring a fresh
preflight rather than trusting the prompt; noted here so nothing downstream assumes the old
state.

---

## Section A — Agent surface inventory (summary; full detail in receipts below)

- `.agents/AGENTS.md` + 13 skills under `.agents/skills/*/SKILL.md` — tracked, called "canonical."
- `CLAUDE.md` (repo root) — tracked, always-loaded pointer/dispatcher, not full doctrine.
- `.claude/` (settings, 14 skills including `lab-graph-export` with no `.agents` counterpart) —
  **entirely gitignored**. Untracked, invisible to git history and PR review.
- No `memory/`/`memories/` directory anywhere in the repo.
- `context/docs/CONTEXT.md` (363 lines) — self-declared authoritative, not auto-loaded.
- `artifacts/.lab/` — 383 files (378 confirmed by the memory-audit pass), heterogeneous naming
  convention, schema v3.
- `pyproject.toml` declares package `omission`/`jnwb`; a second, vestigial `setup.py` at repo
  root declares a **different** package (`pypeline`) with a different, narrower dependency set.
- `.cursor/rules/*.mdc` (3 files, `alwaysApply: true`) — Cursor-only doctrine fork.
- `jnwb/mcp_server/` — an MCP server implementation living inside the analysis package; already
  flagged as misplaced by `AGENTS.md`'s own dead-code register.
- No `.claude/hooks`, no `commands/`. Only CI automation: `.github/workflows/tests.yml`.

## Section B — Instruction precedence: assumed chain vs. actual behavior

Assumed chain (Sol's handout): `global harness → repo AGENTS/CLAUDE → project context → skill →
figure-specific instructions → Labyrinth evidence → task prompt`.

**Actual observed precedence differs in four ways:**

1. Only `~/.claude/CLAUDE.md` (global) and repo-root `CLAUDE.md` auto-load every session.
   `AGENTS.md` (called "canonical") and `CONTEXT.md` (called "authoritative," "read this
   first") are **not auto-loaded** — reachable only if the agent follows a textual pointer
   inside `CLAUDE.md`, which is an instruction, not a harness-enforced include.
2. "Skill" is not one layer — it is **two divergent copies** (`.agents/skills/`, tracked, called
   "reference-only"; `.claude/skills/`, gitignored, called "authoritative for loading"). Direct
   `diff` on `labyrinth-protocol/SKILL.md` alone shows 348 of ~450 combined lines differ. Most
   other skill pairs also differ in line count; only `jnwb-jrsa` and `match-my-writing-style`
   are byte-identical.
3. "Labyrinth evidence" sits near the end of the assumed chain; CLAUDE.md's actual stated
   posture ("consult before you answer, on every turn, by default") puts it much earlier if
   followed — but this is a behavioral directive with no harness enforcement, so whether it's
   followed turn-to-turn is unverifiable by static inspection.
4. The assumed chain has no branch for the Cursor/Gemini fork. CLAUDE.md itself documents that
   fork operates at ~0.02 textual similarity to the Claude-facing global doctrine and actively
   contradicts it on at least one point (the "v15 four-engine model").

**Direct conflicts found** (full quotes in the raw research-agent output; summarized):
- `pyproject.toml` vs `setup.py`: two different package identities/dependency sets for the same repo.
- The file `AGENTS.md` calls authoritative-for-loading (`.claude/skills/`) is the one git can't
  track or diff, while the tracked copy (`.agents/skills/`) is declared "reference only" — the
  drift-detection mechanism (git history) is pointed at the wrong side of the fork.
- `.gitignore:112` is a malformed single line (`​.claude/	.claude/skills/labyrinth-protocol/SKILL.md`,
  tab-separated) that reads as an attempt to un-ignore one file but has no effect — everything
  under `.claude/` remains ignored, including the file the line appears to name.

## Section C — Memory audit and stale-fact sweep

**What "memory" means operationally:** four mechanisms, materially different guarantees.
`context/docs/CONTEXT.md` is the best-behaved — dated, self-declared authoritative, and
structurally built around retraction (§8 "Superseded claims — do not restore" is exactly the
numbers this audit was asked to check, each marked Synthetic/Never fitted/Not reproduced).
`artifacts/.lab/*.json` (378 nodes) has the schema primitives for supersession (`supersedes`,
`contradicts`, `corrects` edge relations all in real use) but **does not enforce them onto the
target node's own `status` field** — of 378 nodes, `status` values are `confirmed` (354),
`null` (13), `provisional` (3), `unconfirmed` (3), `resolved` (1), `open` (1), and **zero**
`retracted`. A node can be the explicit target of a `contradicts` edge and still read
`status: "confirmed"`, `issues: []` indefinitely.

**Concrete proof of the gap:** `census_provenance_synthetic_finding_20260728.json` (status
`confirmed`, severity `critical`) explicitly says node `analysis-clopper-pearson-confidence-
intervals` "should be demoted" because its inputs are the hardcoded, retracted census counts.
That demotion never happened — three sibling nodes
(`analysis-hierarchical-inference-mixed-effects.json`,
`analysis-exploratory-vs-headline-evidence-hierarchy.json`,
`analysis-clopper-pearson-confidence-intervals.json`) still read `status: "confirmed"`,
`issues: []`, and still assert 421/8,597 = 4.90% as fact.

**Full stale-fact sweep results** (search terms Sol specified):

| Term | Verdict |
|---|---|
| N=2 | Mixed — correctly historical-flagged in `CONTEXT.md`, `EVIDENCE_ARCHITECTURE_20260809.md`, current draft v3 (clean, zero hits); **unlabeled** in `artifacts/.lab/analysis-hierarchical-inference-mixed-effects.json:11` (status confirmed) |
| 16 sessions | NOT-FOUND anywhere |
| 17 sessions | Mostly CURRENT (this is the real TFR-corpus size per CLAUDE.md's own stated pre/post-growth distinction); draft-v3 has 4 occurrences under an explicit "must be re-derived from the 23-session corpus" comment — labeled, not yet actioned |
| 4.9% / 421/8597 / 8597 | **P0.** Correctly retracted in `CONTEXT.md`, draft-v3, draft-v2. **Unlabeled and live** in `jnwb/unit_classification.py:539` (library docstring), `notebooks/reproducibility_master_pipeline.py`/`.ipynb` (asserts + prints "PASS" for the retracted numbers, referenced from README, not archived), and three `status:"confirmed"` Labyrinth nodes despite an existing unactioned `contradicts` edge |
| 8736 channels | Correctly retracted in `CONTEXT.md`. Unlabeled in `scripts/build_clean_publication_figures.py:208` (though separately named-and-banned in `CLAUDE.md:220-221`) and `scripts/generate_publication_figures.py` (output asset renamed `UNUSABLE_*`, but script itself not inline-flagged) |
| V3a/V3d pooling | CORRECT in the live GLMM script (`fit_omission_band_power_glmm.py`, pools to "V3a/d"); a separate census script (`compute_real_channel_band_power_census.py`) deliberately keeps them split for tabulation, with no inline warning against a downstream consumer misusing that as independent statistical rows |
| AAAB described as "random" | **P1, unlabeled.** `context/drafts/04_draft_biorxiv_markdown.md:118` calls AAAB "the random control sequence" (RRRR is the actual random condition, correctly used two lines later) — looks like a copy-paste error, and this file is still listed by CONTEXT.md as a live manuscript-voice source |
| 0.60 / 0.601 omission identity | Extremely well-governed — every live occurrence correctly labels it confounded/diagnostic-only, nowhere found accepted as a positive result |
| 75% omission decoding | NOT-FOUND |
| random CV accepted for Fig 4 | NOT-FOUND as an acceptance — actively and consistently rejected everywhere, enforced at the renderer-code level (fails loud on missing leakage-safe inputs) |
| "universal" beta/low-frequency | NOT-FOUND anywhere |
| "Figure 4 is 100% synthetic" | **P1.** `context/figures/INVENTORY.md:48` (auto-generated file) still carries this in a section heading; stale relative to the 2026-08-08 evidence-architecture update where `_v2` tables now exist (confounded, not absent) — the auto-generator wasn't re-run after the underlying state changed |

## Section D — Skills vs. required scientific doctrines

Full per-skill breakdown (9 questions × 15 skills) is preserved in the research-agent transcript
underlying this report; the load-bearing findings:

**Doctrine coverage table** (doctrine → covering skill / ABSENT):

| Doctrine | Status |
|---|---|
| SPK ≠ MUAe ≠ LFP | PARTIAL — listed as separate streams, never explicitly forbidden to conflate |
| p1-relative ≠ omission-relative timing | PARTIAL (`nwb-analysis-forms`, framed as window-leak) |
| trial/unit ≠ session as inferential unit | COVERED (`match-my-writing-style`, `jnwb-functional-connectivity`) |
| prevalence ≠ magnitude ≠ information ≠ mechanism | **ABSENT** as a named four-way taxonomy anywhere |
| random CV invalid for omission-identity inference | COVERED (`nwb-analysis-forms`) |
| cycle/group leakage controlled | COVERED for omission-identity specifically; **absent** from `jnwb-statistics`/`jnwb-jrsa`'s generic permutation APIs |
| HP/early-stopping inside training folds only | PARTIAL — covered for NAM pruning only, not asserted repo-wide |
| test folds never used for early stopping | PARTIAL/ABSENT — implied, not named |
| permutation nulls respect exchangeability/grouping | COVERED in `jnwb-functional-connectivity`; **ABSENT** from `jnwb-statistics.permutation_test` and `jnwb-jrsa.jrsa(permutations=...)` — exactly the two generic APIs most likely to be misused this way |
| hardcoded/fallback panels forbidden | Strongest, most-repeated doctrine in the set (4+ skills); the concrete `PLACEHOLDER-DUMMY` enforcement mechanism from CLAUDE.md is not referenced in any skill, including `jnwb-visualization` |
| null results acceptable | COVERED, explicitly (`match-my-writing-style`) |
| receipts outrank prose | COVERED, multiply and strongly (`labyrinth-protocol`: "No receipt, no claim"; `lab-graph-export`; `match-my-writing-style`) |
| canonical area-addressing API | COVERED, with a named prior incident (`jnwb-core`) |
| V3a/V3d pooling convention | COVERED in `match-my-writing-style` only — **not restated in any `jnwb-*` analysis skill** an agent doing the actual analysis would consult |
| **TFR ratio-before-log10/dB** | **P0 root-cause finding.** Covered once, in `match-my-writing-style` (a prose-style skill). **Totally absent from `jnwb-tfr` and `jnwb-visualization`** — the two skills that actually compute/plot dB TFR values. This directly explains how the `plot_tfr` dB-averaging bug (found and fixed earlier today, see receipt below) went unnoticed: the skill that should have prevented it doesn't state the rule. |

**Skill-tree divergence** confirmed independently of Section B: `.claude/skills/` and
`.agents/skills/` differ in line count for every pair except two; this is a doctrine violation
by the project's own standard, instantiated inside the skill library itself.

## Section E — Tooling friction (no blocking findings)

| # | Category | Severity | Finding |
|---|---|---|---|
| 1 | Python version | friction | Session runs 3.14.3; CI only tests 3.11; `pyproject.toml` has no upper bound |
| 2 | Windows/POSIX-HDF5 | friction | Correctly handled in `jnwb/compression.py` (uses `posixpath`, not `pathlib`, for internal HDF5 paths) but the lesson isn't written into `CLAUDE.md` or any skill — a future script could repeat it |
| 3 | bash-assumption | cosmetic | No `&&` chaining or bash-only syntax found; all scripts invoked via `python scripts/foo.py` |
| 4 | stale-default-path | cosmetic (resolved) | `jnwb/paths.py` currently correct and verified against the live filesystem; git history shows it drifted wrong twice in one day (2026-08-08) before landing correct — no automated guard against recurrence |
| 5 | test collection | cosmetic | `pytest --collect-only` → 326 tests collected cleanly under 3.14.3, no warnings |
| 6 | JSON serialization | friction | No shared numpy-safe JSON encoder; manual per-callsite casting only |
| 7 | determinism | friction, low | Mixed legacy `np.random.seed(42)` vs. modern `default_rng` pattern; no torch seeding found (torch is optional) |
| 8 | schema validation | friction | `schema_version` stamped on write, never asserted on read; no validator script for `.lab/` nodes |

No `blocks-work` severity findings in this section.

## Sections F–J — Readiness for the structured-decoding problem

**F. Flat vs. structured representation.** The repo currently has exactly one methodologically
valid flat-representation pipeline (`scripts/compute_omission_identity_leakage_safe.py`, SPK
only, leave-one-cycle-out CV, in-fold balancing/scaling, within-cycle-exchangeable permutation
null, no hardcoded accept/reject threshold) and its outputs **have not yet been computed** —
`D:/analysis` contains no `outputs/classification/omission_identity_leakage_safe_*` files as of
this audit. There is no structured (unit×time / channel×time) representation code anywhere in
the repo yet. This matches Sol's stated position exactly: the next design is an open hypothesis,
not started.

**G. Confound decomposition.** Trial tables (`_trial_table` in `compute_omission_identity_
leakage_safe.py`) preserve `condition` (full sequence-family string, e.g. "AXAB") and
`cycle_id`, and session/subject are tracked at the outer loop level — but `preceding_identity`,
`sequence_family`, and `omission_position` are **not materialized as explicit, reusable
columns**. They have been re-derived ad hoc three separate times already: the v2 block-number
confound diagnosis, the v3 cycle-detection fix, and the Aug-6 p4 label-swap fix
(`jnwb/omission_identity.py:37-44` — every p4-specific number computed before that fix is
self-documented as "unreliable until rerun," direct evidence that ground-truth-label
construction has had real, previously-uncaught bugs on this exact pipeline).

**H. Deep-learning-specific leakage audit — the headline finding of this audit.**
Swept all 14 decoding scripts in `scripts/` for the checklist Sol specified
(`fit_transform`/`StratifiedKFold`/`train_test_split`/`shuffle=True`/no `groups=`):

- **Valid (2 of 14):** `compute_omission_identity_leakage_safe.py` (grouped LOCO, in-fold
  balancing and scaling, exchangeable within-cycle null); `jnwb/omission_identity.py`'s
  `decode_identity_cycle_deconfound` used by `compute_omission_identity_cycle_deconfound_v3.py`
  (grouped LOCO for the observed statistic, in-fold scaling).
- **Invalid (11 of 14):** `decode_fig04_v4_area_ranking.py` through `v9_nam.py` (6 scripts),
  `decode_splus_pfc_single_session_step1/2/12_balanced.py` (3 scripts),
  `decode_lfp_1d_positive_control_and_omission.py`, `compute_omission_identity_encoding.py`, and
  `compute_omission_identity_encoding_v2.py` — all use either `StratifiedKFold(shuffle=True)`
  (random, ungrouped) or `train_test_split(stratify=y, ...)` with **no `groups=` parameter
  anywhere in any of them**. `compute_omission_identity_encoding.py:115,136` and
  `compute_omission_identity_encoding_v2.py:325` additionally call
  `StandardScaler().fit_transform(X)` on the **full dataset before** `cross_val_score` —
  classic preprocessing leakage, and this concretely explains the mechanism behind the
  already-known-confounded 0.601 accuracy number cited throughout the repo's own doctrine.
  **None of these 11 scripts are archived** (no `archive_oneoff/` prefix, no inline deprecation
  header) — they sit live in `scripts/`, filenames alone (`v4`...`v9`) give no signal of
  validity, and a future agent could rerun any of them and present the output as current
  evidence with no code-level warning to stop it.
- **A second, distinct leakage-adjacent bug, found by direct inspection**:
  `decode_identity_cycle_deconfound` (`jnwb/omission_identity.py:551-554`) correctly uses
  leave-one-cycle-out CV to compute the observed A-vs-B accuracy, but its permutation null
  (line 554: `y_perm = rng.permutation(yab)`) is a **naive global permutation across all
  trials, ignoring cycle membership** — unlike `compute_omission_identity_leakage_safe.py`'s
  `_within_cycle_permutation`, which correctly preserves per-cycle class counts. This creates
  an asymmetry: the test statistic respects the grouping structure the whole cycle-based design
  exists to protect, but the null distribution it's compared against does not. This does not
  obviously overturn the ~0.495 chance-compatible conclusion (a naive/too-liberal null would, if
  anything, make it *harder* to find that result non-significant by chance-inflation reasoning
  — but this direction is asserted, not proven, and should not be trusted without checking) —
  it should be fixed before this specific script's null is reused for any positive claim.

**I. No hardcoded minimum-training-accuracy criterion.** Swept the full repo
(`train(ing)?[_ ]?(accuracy|acc)\s*(must|should|>=|>)`, `minimum.{0,20}accuracy`,
`accuracy.{0,20}threshold`) — zero matches in project code (one unrelated hit inside the
vendored `sklearn` library). Clean.

**J. Falsification controls.** Label permutation, cycle-aware label permutation, and structured
vs. flattened comparison all have working precedent in the repo (the two valid scripts above).
Unit-order and channel-order permutation, time-bin permutation, within-trial scrambling,
capacity-matched MLP control, and the presented-identity positive control have **no existing
implementation** to build from — all would be new code for the structured-decoding skill.

---

## Section K — Findings, classified

Full findings table (33 items) is in the paired lab-graph node
`artifacts/.lab/agent-harness-audit-20260810.json`, each tagged ACCEPT / FOLLOW-UP / PATCH /
REPRODUCE / REJECT with P0-P3 priority. Highest-priority items only, here:

### P0 — could invalidate inference
1. `notebooks/reproducibility_master_pipeline.py`/`.ipynb` assert-and-print "PASS" for the
   retracted 4.90%/421/8,597 census as a reproducibility check. **REPRODUCE→PATCH.**
2. `jnwb/unit_classification.py:539` states the retracted 4.90% figure as current fact in a
   live, imported docstring. **PATCH.**
3. Three Labyrinth graph nodes stuck at `status:"confirmed"` despite an existing, unactioned
   `contradicts` edge naming them for demotion — a structural defect in how supersession is
   enforced, not just a stale fact. **PATCH** (both the three nodes and, ideally, the schema's
   enforcement gap).
4. 11 of 14 decoding scripts use invalid random/ungrouped CV; 2 of those additionally leak via
   pre-split scaler fitting. None archived or inline-flagged. **PATCH** (archive or header-flag
   all 11; do not delete — Conservation).
5. `decode_identity_cycle_deconfound`'s permutation null ignores cycle grouping while its
   observed statistic respects it. **PATCH** before this script's null is used for any future
   positive claim.
6. The TFR log-order rule and the CV/permutation-grouping rule are documented in doctrine but
   absent from the exact skills (`jnwb-tfr`, `jnwb-visualization`, `jnwb-statistics`,
   `jnwb-jrsa`) that would apply them — root cause of at least one already-shipped bug (the
   `plot_tfr` dB-averaging defect found and fixed earlier today: `jnwb/session.py`, see
   `artifacts/.lab/session-py-tfr-plot-baseline-bugs-20260810.json`). **PATCH** (this is
   exactly what Handout 2's skill updates should close).
7. Retracted 8,736-channel figure still live, unflagged, in
   `scripts/build_clean_publication_figures.py`/`generate_publication_figures.py`.
   **FOLLOW-UP** (partially mitigated already by CLAUDE.md's ban + renamed output asset).

### P1 — substantial reproducibility/scientific friction
8. `.claude/` (the harness-loaded skill/settings tree) is entirely gitignored — untracked,
   invisible to git history and PR review; the `.gitignore` line that appears to carve out an
   exception is syntactically inert. **PATCH.**
9. `.agents/skills/` and `.claude/skills/` have already drifted substantially with no enforced
   sync. **PATCH or FOLLOW-UP** (decide single source of truth, fix or remove the sync script).
10. `pyproject.toml` and `setup.py` declare two different, conflicting packages. **FOLLOW-UP.**
11. `context/drafts/04_draft_biorxiv_markdown.md:118` mislabels AAAB as the random control
    sequence in a file still listed as a live manuscript-voice source. **PATCH** (one-line fix).
12. `context/figures/INVENTORY.md:48` — auto-generated heading stale relative to the current
    fig04 state. **REPRODUCE** (re-run the generator).
13. Confound-decomposition variables not materialized as explicit trial-table columns; derived
    ad hoc three times already. **FOLLOW-UP** (belongs in the structured-decoding skill's first
    pipeline stage, per Sol's proposed workflow).
14. No skill addresses "unit order has no biological topology" for a future SPK CNN — Sol's own
    flagged concern, currently unaddressed anywhere in the repo. **FOLLOW-UP** (Handout 2).

### P2/P3 — efficiency and cleanup
15-24. Python-version test gap, JSON-serialization encoder gap, mixed seeding patterns,
inconsistent hardcode-warning coverage across skills, no `.lab/` schema validator, POSIX-HDF5
lesson undocumented outside one file, heterogeneous `.lab/` naming convention, `legacy/
markdowns/CLAUDE.md` already-marked-stale (no action needed). Full list with receipts in the
paired JSON node.

---

## Verdicts

```
SAFE_TO_PATCH_AGENT = YES
SAFE_TO_RUN_STRUCTURED_DECODING = NO
```

**SAFE_TO_PATCH_AGENT = YES**, with conditions. Nothing found in this audit makes adding the
compact project-memory block and a new `structured-decoding` skill (Handout 2) itself risky —
that patch touches only agent-facing instruction files, not scientific analysis code. The patch
should specifically incorporate: (a) the unit-order-has-no-topology warning for SPK, (b) an
explicit cross-reference of the TFR log-order rule into `jnwb-tfr`/`jnwb-visualization`, (c) an
explicit cross-reference of the CV/permutation-grouping requirement into
`jnwb-statistics`/`jnwb-jrsa`, and (d) a pointer to the 11 invalid-CV decode scripts so the new
skill's model ladder doesn't accidentally treat one as a template. The `.claude/`-gitignore and
skill-tree-drift findings (P1 #8-9) should be resolved as part of or immediately after this
patch, since they determine whether the patch itself will be reviewable/diffable going forward.

**SAFE_TO_RUN_STRUCTURED_DECODING = NO.** Multiple P0 blockers stand independent of the agent
patch: the leakage-safe flat baseline hasn't been run to completion yet (no outputs exist to
compare a structured model against); confound-decomposition variables aren't materialized;
the deconfound script's permutation null has a real, uncharacterized asymmetry; retracted
census numbers are still live in executable, imported code that a careless "reproducibility
check" could reintroduce; and no falsification-control infrastructure (unit/channel/time
permutation, capacity-matched MLP control, structural ablation) exists yet to distinguish
"nonlinearity helped" from "structure helped," which is exactly the confound Sol's Handout G/J
warns the eventual CNN-vs-linear comparison must not conflate. This matches Sol's own explicit
instruction not to start structured decoding yet — this audit found concrete, additional reasons
that instruction is correct, not just formal ones.

## Receipts
- Full section-by-section raw research output: preserved in this session's transcript (four
  parallel Explore-agent passes + direct file reads of all 14 decoding scripts and
  `jnwb/omission_identity.py` by the compiling agent).
- Structured findings graph: `artifacts/.lab/agent-harness-audit-20260810.json`.
- The `plot_tfr` dB-averaging bug referenced in P0 #6 above: fixed earlier today, receipt at
  `artifacts/.lab/session-py-tfr-plot-baseline-bugs-20260810.json`, verified via numerical
  cross-check between `plot_tfr` and `trial_averaged_plot` (max abs diff 0.0 after the fix) and
  full pytest suite (283 passed, 0 failed at the time).

---

## Addendum — Handout 2 executed (2026-08-10, same day)

Sol reviewed the Handout 1 findings above and narrowed the originally-proposed Handout 2 to a
substrate-repair pass only, explicitly deferring structured decoding. That narrowed Handout 2
was executed in full:

- **P0 fixed**: 12 invalid-CV decoding scripts (corrected count — the original P0 finding above
  said "11 of 14"; re-verification during Handout 2 found `compute_omission_identity_encoding.py`
  was also invalid via a non-grouped `cv=3` integer fold plus pre-split scaler fitting, making it
  12 of 14) plus 2 hardcoded-synthetic-census figure scripts quarantined to
  `scripts/historical/{confounded,synthetic}/`, each with a machine-readable
  `scientific_status = "invalid_for_inference"` header and an enforcement test
  (`tests/test_quarantine_enforcement.py`) blocking any live import. A canonical
  `jnwb.permutation.permute_labels(scheme=...)` primitive was built and
  `decode_identity_cycle_deconfound`'s naive global-permutation null was fixed to respect cycle
  grouping. Executable dependence on the retracted 421/8597/4.90% census was removed from
  `notebooks/reproducibility_master_pipeline.py`/`.ipynb`, `jnwb/unit_classification.py`, and
  `scripts/build_oplusplus_census.py` (`tests/test_no_retracted_census_in_live_code.py` guards
  this going forward).
- **P1 fixed**: the skill tree was consolidated to one tracked canonical source
  (`.claude/skills/`, un-gitignored and tracked directly; `.agents/skills/` — which had already
  drifted 348 of ~450 combined lines apart on one skill and contained stale pre-2026-08-08 paths
  — was retired, recoverable via git history). TFR log-order and CV-grouping doctrine was
  injected directly into `jnwb-tfr`, `jnwb-visualization`, `jnwb-statistics`, and `jnwb-jrsa`. A
  canonical trial ontology (`jnwb/trial_ontology.py`) now derives `sequence_family`,
  `omission_position`, `preceding_identity`, `expected_identity`, and `presented_identity` from
  condition codes in one place, unit-tested against all 12 codes including the historically-
  buggy p4 A/B pair, cross-checked against `jnwb.omission_identity.OMISSION_IDENTITY_CONDITIONS`.
- **P2 addressed**: a Labyrinth validator (`scripts/validate_labyrinth_claim_status.py`) now
  detects nodes/claims still `status: "confirmed"` despite being the target of a
  `contradicts`/`supersedes` edge from a confirmed source. The 3 known-bad nodes from the
  original audit were fixed (`status` → `retracted`, with a receipt). Running the validator
  against the full 376-file corpus surfaced **23 further, previously-unknown violations and 2
  dangling edges** — durably recorded as a new claim
  (`claim-labyrinth-validator-built-and-3-known-nodes-fixed`) rather than silently resolved or
  dropped; triaging all 23 is explicitly out of scope for this pass and is left as a backlog item.
- **All four of Sol's acceptance tests** were added and pass: (1)
  `tests/test_cv_grouping_acceptance.py` demonstrates on synthetic data that random CV inflates
  a pure cycle-level confound to >85% apparent accuracy while grouped LOCO CV correctly reports
  chance (~30–70%); (2) the same file shows the within-cycle permutation null is calibrated on
  pure-noise synthetic data (observed statistic within 3 null SDs of the null mean); (3)
  `tests/test_trial_ontology.py` (42 tests) covers all 12 condition codes, explicitly asserting
  both p4 A/B directions; (4) `tests/test_no_retracted_census_in_live_code.py` confirms zero
  live hits of 421/8597/4.90% outside explicitly historical/quarantined locations.
- Full suite after all changes: **377 passed, 0 failed, 43 skipped.**

Updated verdict (see `artifacts/.lab/agent-harness-audit-20260810.json` `verdict` field for the
full statement):

```
SAFE_TO_PATCH_AGENT = completed
SAFE_TO_RUN_EXISTING_DECODING = leakage-safe paths only
SAFE_TO_RUN_STRUCTURED_DECODING = NO   (deliberately unchanged)
```

Per Sol's explicit instruction, structured decoding remains blocked, and no CNN architecture,
dropout, model capacity, window, or area-wise structured-decoding work was touched in this pass.
Sol's proposed Handout 2.5 (an independent re-audit proving the *runtime* agent actually
retrieves the corrected doctrine, not just that the doctrine text now exists) has not been
started.
