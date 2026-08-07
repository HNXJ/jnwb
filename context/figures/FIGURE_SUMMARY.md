Version: 2026-08-06 (renumbered)
Status: canonical source draft / research note
Truth status: `truth_safe_unverified`; verify against live repo manifests before submission.

# Omission-a: main-figure summary table

**RENUMBERED 2026-08-06** — see `README.md`'s Status table for the full rationale.
`figS24_omission_identity_decoding` promoted to fig04; old fig04 (TFR) moved to fig06; old
fig06 (SPK-SPK) demoted to supplement (`spk_spk_coupling_supplement/`). Revision scores added
per figure — see `REVISION_PLAN.md` for the plan built from them.

One row per main figure (1-7). Supplements are not itemized here — see `README.md`'s per-figure
table and `INVENTORY.md` (auto-generated) for those. Every number below traces to a script and a
receipt named in that figure's own `README.md`; none is restated from memory without checking.

| # | Title | Headline method | Corrected result | Unit of inference | Status | Revision score |
|---|---|---|---|---|---|---|
| 1 | Recording topology and paradigm | Schematic (MaDeLaNe hardware, 10-area topology, AAAB/BBBA/RRRR block design) | No inferential claim — descriptive only | — | Locked | **90/100 (semi-final)** |
| 2 | Spiking exemplar rasters | Four named single-unit exemplars (S+/S-/O+/O++), spec-fixed to V1/V3a-d/V4/FEF | No inferential claim by design (n=1 per column) | unit (descriptive only) | Locked | **100/100 (final)** |
| 3 | Unit census | Q1-Q4 classifier proportions (Clopper-Pearson), area × composition χ², omission-effect-size contrasts across S+/S-/O+/Other, + 2026-08-06 UMAP embedding subpanel | 490/8,592 units (5.7%) peak/trough at omitted slot (P_holm=1.3e-59); area predicts S/O composition (Cramér's V=0.199, P≈0); UMAP: silhouette=0.039, permutation P=0.0010 | unit (8,592 screened, 21 sessions, 3 animals); session counts printed per area panel | Not locked | **80/100 (revision on subplots needed)** |
| 4 | Omission identity decoding & spatial "GLMM" encoding | Noise-controlled decoding (SVC + StratifiedKFold + permutation null) across time/slot/area, plus a mislabeled single-level logistic-regression "GLMM" | **CONFIRMED currently 100% synthetic** — none of the 3 source CSVs exist on disk; every panel renders from hardcoded fallback arrays, not a real fit | none — no real result exists yet | **PROMOTED 2026-08-06**, not locked | **70/100 (new promoted result, details to be discussed)** |
| 5 | LFP band-power hierarchy, subject-controlled GLMM | MixedLM (REML), area vs V1 (+ V4, + PFC rows), subject additive fixed effect, session random intercept | **2/45 survive Holm** (FEF +0.57dB, PFC +0.53dB, both low-gamma, P_holm=0.0076/0.0088); 11/45 BH-FDR | session (23 sessions, 3 subjects) | Semi-finalized (2026-08-06) | **60/100 (minor revision on subplots needed)** |
| 6 | V1/V3a-d/TEO/PFC time-frequency, RXRR vs RRRR | Paired within-session dB contrast, 4 areas × 5 bands | **0/20 survive Holm-Bonferroni** (smallest P_holm=0.068, V1 low-gamma); laminar splits fully null (10/10, P_holm=1.0) | session (paired) | **RENUMBERED 2026-08-06** (was fig04); Not locked (stale lock predates 2026-08-04 rework) | **50/100 (moderate revision on subplots needed)** |
| 7 | Population firing rate × LFP band power | Trial-matched correlation (hit-rate) + GLMM on per-session Z, 5 functional groups (S+/S-/O+/O++/Other) × 10 areas × 5 bands × 3 condition groups | **19/480 survive Holm** at hit-rate stage; GLMM: band dominant (high/low gamma≫theta/alpha/beta, P_holm<1e-5), O+ *less* coupled than Other/S+ (P_holm=1.6e-5/5.4e-5), MT≠FEF/PFC/TEO, no condition-group effect; PPC (supplement) fully null 0/60 | session (pool-after-testing hit-rate) | Semi-finalized (2026-08-06) | **10/100 (major revision)** |

**Demoted to supplement 2026-08-06**: SPK-SPK lead/lag population correlation (was fig06).
Trial-matched correlation, ±100ms lag axis, (area, functional-type) population nodes,
trial-mismatch shuffle null. **4/12,033 survive Holm** (all within ±10ms of lag 0 — no lead/lag
delay evidence); Granger (supplement) fully null 0/27; NB rate-ratio (supplement) 30/13,790
Holm. See `spk_spk_coupling_supplement/README.md`.

## Reading notes

- **"Corrected result"** always names which correction (Holm-Bonferroni = FWER, BH-FDR = false
  discovery rate) and the family size the correction was run over — never a bare p-value.
- **Figure 6 (TFR, formerly fig04) is a fully-documented main-figure null** (0/20 Holm) —
  reported plainly, not hidden, per this project's own doctrine that a null result gets a
  headline too. The SPK-SPK directed-Granger null (0/27) that used to sit alongside it as
  main-figure fig06 is now inside the demoted `spk_spk_coupling_supplement/`.
- **Figure 5 and 7 are the two figures carrying this paper's positive, corrected, group-level
  claims** — the frontal/low-gamma omission effect (fig 5) and the population rate/band-power
  coupling with its band-dominance and O+-decoupling structure (fig 7). **Figure 4 currently
  carries no real claim at all** — it renders entirely from synthetic fallback data (see its
  row above and `fig04_omission_identity_decoding/README.md`).
- **"Status" is the project's own lock convention** (`README.md`'s hand-maintained table): a
  figure re-run from scratch reproducing identical numbers, visually reviewed, and snapshotted
  as `fig0N_finalized.*` counts as "semi-finalized" — short of a full lock, since follow-up work
  (fig05's own supplement family, fig06/7's newer additions) hasn't had the same final pass yet.
- Figures 1-2 are locked from an earlier pass and unchanged since. Figures 3-4 are real,
  receipted analyses that have not yet been through a lock review pass — not a quality
  judgment, just a pending step.
