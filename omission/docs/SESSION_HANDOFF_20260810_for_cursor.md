# Session Handoff — 2026-08-10 — for continuation in Cursor

**Repo**: `C:\workspace\omission` · **Branch**: `dev` · **HEAD**: `1e67054` (pushed, CI green)
**All work below is committed and pushed.** Nothing local/uncommitted to carry over.

This document is a self-contained brief for picking this work up in a fresh Cursor session —
it assumes no memory of the Claude Code conversation that produced it.

---

## 1. What happened, in order

1. **NWB corpus compression** (fp32 + chunking + gzip) — 22/22 sessions converted, verified,
   originals deleted. `jnwb/compression.py`, `jnwb.compress_fp32`. Not relevant to current work,
   mentioned for completeness.
2. **TFR plotting bug fix** — `jnwb/session.py`'s `plot_tfr` was labeled "dB re baseline" but
   never took a `log10` (raw subtraction). Fixed; `trial_averaged_plot` had a matching
   axis-order + baseline-window bug, also fixed. Both now agree exactly (verified numerically).
3. **fig04 evidence-gate rework** (a separate agent, "Luna," committed by the user's request) —
   replaced synthetic/hardcoded Figure 4 panels with a leakage-safe renderer that fails loudly
   instead of falling back to placeholder data.
4. **Full agent-harness audit** ("Handout 1", `artifacts/.lab/agent-harness-audit-20260810.json`,
   `docs/agent_harness_audit_20260810.md`) — found systemic problems: 12 of 14 decoding scripts
   used invalid/ungrouped cross-validation; a permutation-null exchangeability bug; retracted
   census numbers (421/8597 = 4.90% O+) still live in executable code; the harness's own skill
   tree had silently forked and drifted; doctrine documented in `CONTEXT.md` wasn't reaching the
   skills an agent would actually consult.
5. **Harness repair** ("Handout 2", commit `2b7b4cf`) — fixed all of the above. See §3 below for
   the durable artifacts this left behind.
6. **Runtime re-audit** ("Handout 2.5", commit `1b52315`) — independently verified (via a fresh,
   blind subagent — not just re-reading the same edit) that the repaired skills actually get
   retrieved correctly for realistic prompts. Found and fixed 3 more retrieval-layer gaps.
   Reproduced the known chance-compatible baseline on a small subset. Full suite green.
7. **Frozen experiment specification** ("Handout 3", commit `1e67054`,
   `docs/handout_3_structured_identity_experiment_v1_spec.md`) — a specification for the next
   scientific step (structured population decoding of omitted stimulus identity). **No code, no
   training exists yet.** Requires explicit human sign-off before implementation starts.

---

## 2. Current scientific state (do not restate anything different)

- **Flattened omitted-identity decoding is chance-compatible** under grouped (leave-one-cycle-out)
  cross-validation. The earlier 0.601 accuracy figure is a **confound** (ungrouped CV let
  same-cycle trials leak between train/test) — **permanently retracted, never cite as a finding.**
- **Presented-stimulus identity is the positive control** (expected to be trivially decodable;
  not yet re-run on the corrected fold machinery — see Handout 3 §4.4).
- **O+ prevalence (421/8597 = 4.90%) is retracted synthetic data.** The real order of magnitude
  on a two-subject screen was ~0.4%; the three-subject figure is explicitly unresolved
  ("the only headline number still owed" — `context/docs/CONTEXT.md` line 326). Never state
  4.90% as current.
- **Structured population coding of omitted identity is an open hypothesis**, not yet tested
  under valid methodology. `SAFE_TO_RUN_STRUCTURED_DECODING = YES` per the Handout 2.5 gate,
  accepted by the project's science lead — but implementation has **not started**; Handout 3 is
  a specification only.

---

## 3. Durable artifacts this session left behind (use these, don't rebuild them)

| What | Where | Use it for |
|---|---|---|
| Canonical exchangeability-scheme permutation primitive | `jnwb/permutation.py` | Any permutation null on grouped data. `permute_labels(y, groups=..., scheme="within_group"/"global", rng=...)` — scheme is mandatory, no default. |
| Canonical trial ontology | `jnwb/trial_ontology.py` | Deriving `sequence_family`/`omission_position`/`preceding_identity`/`expected_identity`/`presented_identity` from any of the 12 condition codes. Never hand-parse `"AXAB"`-style strings again — that's exactly how the 2026-08-06 p4 A/B label swap bug happened. |
| Validated omitted-identity decoding pipeline | `scripts/compute_omission_identity_leakage_safe.py` | The only currently-trusted decode implementation. Leave-one-cycle-out CV, in-fold balancing/scaling, within-cycle-exchangeable permutation null. |
| Validated deconfounded decoding (alternate path) | `jnwb.omission_identity.decode_identity_cycle_deconfound` via `scripts/compute_omission_identity_cycle_deconfound_v3.py` | Per-cycle mean-centered LOCO decode. Its permutation null was buggy (global, not grouped) until this session — now fixed. |
| Quarantined/invalid decoding scripts (12 of them) | `scripts/historical/confounded/` | **Do not use, do not import.** Each has `scientific_status = "invalid_for_inference"`. Preserved as forensic evidence, not deleted. `tests/test_quarantine_enforcement.py` will fail CI if anything live imports from here. |
| Quarantined hardcoded-synthetic-data scripts | `scripts/historical/synthetic/` | Same — do not use. Contains the literal retracted census arrays. |
| Quarantined reproducibility notebook | `notebooks/historical/reproducibility_master_pipeline.{py,ipynb}` | Asserts the retracted 4.90% census as "PASS". Do not run as a current check. |
| Labyrinth graph validator | `scripts/validate_labyrinth_claim_status.py` | Flags any `.lab/*.json` node still `status:"confirmed"` despite being contradicted/superseded by another confirmed node. **23 known, pre-existing backlog violations exist** (`python scripts/validate_labyrinth_claim_status.py` to list them) — deliberately left untriaged this session; a real but separate cleanup task. |
| Single canonical skill source | `.claude/skills/` (14 skills, now git-tracked — `.agents/skills/` was retired, do not recreate it) | Read these before writing any analysis code in a domain they cover. `nwb-analysis-forms/SKILL.md` §7 specifically covers omitted-identity decoding and was heavily rewritten this session. |
| Frozen next-step specification | `docs/handout_3_structured_identity_experiment_v1_spec.md` + `artifacts/.lab/handout-3-structured-identity-experiment-v1-spec-20260810.json` | Read fully before writing any structured-decoding code. **Unsigned — needs explicit human sign-off before implementation.** |

---

## 4. What NOT to do

- Do not resurrect the 0.601 accuracy figure, or `scripts/historical/confounded/*.py`'s output,
  as evidence of anything.
- Do not state 421/8597/4.90% as a current O+ prevalence figure.
- Do not hand-parse condition-code strings (`"AXAB"` etc.) — use `jnwb.trial_ontology`.
- Do not write a bare `rng.permutation(y)` anywhere in the omission-identity decoding domain —
  use `jnwb.permutation.permute_labels` with an explicit `scheme`.
- Do not start implementing Structured Identity Experiment v1 (CNNs, MLPs, structured models,
  any training) without first getting explicit sign-off on
  `docs/handout_3_structured_identity_experiment_v1_spec.md` from the project's science lead
  ("Sol", if that name means something in your context — otherwise: whoever owns the scientific
  decisions here).
- Do not recreate `.agents/skills/` — `.claude/skills/` is now the single tracked source.
- Per a separate standing instruction from Hamm (2026-08-10): **all new results/outputs go under
  `context/figures/`** until further notice — not `outputs/`, not script-local directories.

## 5. What's plausible next

1. Get sign-off on Handout 3, or iterate on the spec if changes are needed (it's versioned —
   a change after sign-off is `v1.1`/`v2`, not a silent edit).
2. If signed off: implement the pieces the spec requires that don't exist yet — the structural
   ablations (§9.2), the SPK permutation-equivariant/metadata-ordered representation (§4.3), and
   the positive-control decoder rebuilt on the shared fold machinery (§4.4) — before any model
   training.
3. Separately, and lower priority: triage the 23-item Labyrinth validator backlog
   (`python scripts/validate_labyrinth_claim_status.py`) — explicitly deferred this session, not
   forgotten.

## 6. Verifying this state yourself

```bash
cd C:\workspace\omission
git log --oneline -5          # should show 1e67054 at HEAD
python -m pytest tests/ -q    # should show ~377 passed, 0 failed, 43 skipped
python scripts/validate_labyrinth_claim_status.py   # 23 known violations, not a regression
```
