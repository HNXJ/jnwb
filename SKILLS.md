# Omission Repository Skills Index

**Repository**: `D:\workspace\omission`  
**Last Updated**: 2026-06-16  
**Status**: Active (4 core skills + legacy stack)

---

## CRITICAL BLOCKING SKILLS (HIGHEST PRIORITY)

### 0. Full-Sequence Epoch Recovery
**Script**: `scripts/recover_full_sequence_epochs.py` (NOT YET CREATED)  
**Purpose**: Extract aligned p1/p2/p3/p4/d1-d4 phases for all 156 session-condition pairs from raw NWB data.  
**Status**: **METHOD_PENDING** → **CRITICAL BLOCKING**  
**Blocking**: Figures 4–10 (all downstream science)  
**Scientific Impact**: Once complete, project readiness jumps from 60→90 in ~30 days

**Why It Matters**:
- All Figure 4–10 analysis depends on aligned epochs
- Epochs are the foundational substrate for TFR, Granger, PAC, ghost signals, state manifolds, SpSAM
- Multi-session consistency is non-negotiable (one bad epoch ruins cross-session averaging)
- Omission science is **phase-specific**: off-by-one-sample can smear 30dB effects

**Key Invariants**:
- Preserve phase ordering (p1: [-250, -50]ms; p2–p4: 250ms windows; d1–d4: 500ms dynamics)
- All sessions → identical (n_trials, 128, 6000) dimensions
- No NaN-padding; fail loudly instead
- Condition-specific alignment (omissions align to omission_time, not stimulus)

**Estimated Effort**: 6 days total
- Phase 1 (single-session): 3 days
- Phase 2 (multi-session): 2 days
- Phase 3 (validation): 1 day

---

## ACTIVE SKILLS

### 1. A4 Trial-Count Validation
**Script**: `scripts/build_trial_count_validation.py`  
**Purpose**: Descriptive analysis of trial counts per session/condition using metadata and filename inventories only.  
**When to Use**:
- Validating data completeness before A5 analysis
- Checking condition balance across families
- Verifying session readiness for downstream analysis

**Key Facts**:
- Extracts trial counts from NWB/NPY array shapes via mmap (no payloads read)
- Generates 5 output files (CSV, JSON, Markdown)
- All 13 sessions ready for A5 ✓
- Truth status: `truth_safe_unverified`

**Related Files**:
- `tests/test_trial_count_validation.py` (10 tests, all pass)
- `reports/analysis_A4_trial_count_validation/` (outputs)

**Usage**:
```bash
python scripts/build_trial_count_validation.py \
  --data-root D:\workspace\data \
  --a3-dir reports/analysis_A3_dataset_census \
  --out-dir reports/analysis_A4_trial_count_validation
```

---

### 2. JNWB Visual QC Suite
**Script**: `scripts/run_jnwb_visual_qc.py`  
**Module**: `jnwb/`  
**Purpose**: NWB-native visual quality control for LFP/spike data across sessions.  
**When to Use**:
- Interactive inspection of analog epochs
- Validating LFP continuity and signal integrity
- Multi-session electrode/unit auditing

**Key Facts**:
- Generates interactive HTML dashboards
- Real NWB data inspection (no synthetic arrays)
- Smoke tests in `tests/test_bounded_signal_slice.py`

**Related Files**:
- `notebooks/03_jnwb_visual_qc.ipynb` (exploration)
- `outputs/jnwb_visual_qc/` (generated dashboards)

---

### 3. Task Taxonomy Validator
**Script**: `scripts/validate_task_taxonomy.py`  
**Purpose**: Validates task condition definitions (AAAB, AXAB, AAXB, etc.) against canonical specifications.  
**When to Use**:
- Pre-analysis validation of condition mappings
- Verifying omission slot assignments (p2/p3/p4)
- Checking matched-control integrity

**Key Facts**:
- 6 core validation checks (all pass)
- Enforces condition family separation (A/B/R)
- Validates matched controls per family
- Output: Markdown validation report

**Related Files**:
- `context/specs/task-specification.md` (canonical task defs)

---

### 4. Figure Registry Auditor
**Script**: `scripts/audit_figure_registry.py`  
**Purpose**: Audits canonical figure registry (f001-f050) for completeness and module existence.  
**When to Use**:
- Pre-pipeline verification
- Checking module presence before analysis runs
- Figure phase assignment validation

**Key Facts**:
- All 50 figures present and verified
- Checks phase assignment correctness
- Validates module directories exist

---

## LEGACY SKILLS (Needing Update)

The `.gemini/skills/` directory contains ~20 legacy skills from earlier development phases:
- `analysis-area-inspection`
- `analysis-behavioral-data-processing`
- `analysis-global-unit-counts-nwb`
- `analysis-lfp-pipeline`
- `analysis-manifest-validation`
- `analysis-neuro-omission-*` (8 variants)
- `analysis-metadata-extraction`
- ... and others

**Status**: These reference the old `D:/drive/omission` path structure and should be migrated to:
1. Update paths: `D:/drive` → `D:\workspace`
2. Link to current module locations in `src/analysis/`
3. Consolidate duplicates (e.g., multiple PAC analysis skills)

**Action**: Use `.gemini/skills/_all_skills_dump.txt` as reference for consolidation.

---

## TOP PRIORITY SKILLS (FROM THETA ASSESSMENT)

These five skills directly unblock scientific bottlenecks. Prioritize in this order:

1. **Full-Sequence Epoch Recovery** ← **HIGHEST PRIORITY** (See above)
2. **SpSAM** (Spike-Spectral Attention Mechanism) — `skills/analysis/spsam.skill` ✓ Created
3. **Figure Roadmap** (Figures 4–10 status tracker) — `skills/figures/figure-roadmap.skill` ✓ Created
4. **Omission Local Windows** (Stimulus-specific analysis windows)
5. **Harmony Validation** (Multi-area coordination metrics)

---

## SKILLS NOT YET DOCUMENTED

### Potential Skills to Formalize
- **SPK/SUA Analysis** (spike unit analysis pipeline) — in `src/f001_theory/`, `src/f002_psth/`, etc.
- **LFP Time-Frequency Routing** — in `src/f005_tfr/`
- **Spectral-Functional Coherence** (SFC) — in `src/f007_sfc/`, `src/f009_individual_sfc/`
- **Laminar Profile Mapping** — in `src/f011_laminar/`, `src/f012_csd_profiling/`
- **Ghost Signal Detection** — in `src/f018_ghost_signals/`
- **PAC (Phase-Amplitude Coupling) Analysis** — in `src/f019_pac_analysis/`
- **NWB Data Availability Auditing** — core data validation
- **Dashboard Payload Builder** (Vite/React) — in `dashboard/`

---

## RECOMMENDED SKILL REFRESH PLAN (FROM THETA ASSESSMENT)

**CRITICAL (Unblock Science)**:
1. ✅ Create `skills/epochs/full-sequence-epoch-recovery.skill` — **HIGHEST PRIORITY** (6 days, unblocks Figs 4–10)
2. ✅ Create `skills/analysis/spsam.skill` — SpSAM mechanism (METHOD_PENDING, depends on epochs)
3. ✅ Create `skills/figures/figure-roadmap.skill` — Figure 4–10 status tracker
4. [ ] Create `skills/analysis/omission-local-windows.skill` — Stimulus-specific analysis windows
5. [ ] Create `skills/analysis/harmony-validation.skill` — Multi-area coordination metrics

**Secondary (Infrastructure)**:
1. [ ] Update `.gemini/skills/` paths: `D:/drive` → `D:\workspace`
2. [ ] Consolidate duplicate behavioral/oculomotor skills (5–6 can merge)
3. [ ] Formalize SPK/SUA skill from f001-f037 modules

**Future (Maintenance)**:
1. [ ] Archive non-essential legacy skills
2. [ ] Create unified "Omission Neural Analysis" meta-skill hierarchy
3. [ ] Reorganize `skills/` into subdirectories (governance, epochs, spiking, lfp, laminar, figures, validation, manuscript)

**Critical Note**: Do NOT create additional behavioral or PAC documentation until epoch recovery is ACTIVE. Scientific readiness remains ~60/100 until then.

---

## HOW TO ADD A NEW SKILL

1. **Create skill file**: `skills/analysis/your-skill-name.skill` or `skills/dashboard/your-skill-name.skill`

2. **Use this template**:
```markdown
# Skill: Your Skill Name

## Context
Brief description of what this skill does in the omission analysis pipeline.

## Invariants
- Key constraint 1
- Key constraint 2

## Procedures

### When to Use
- Use case 1
- Use case 2

### How to Run
```bash
python path/to/script.py --arg1 value1
```

### Example Output
Describe what success looks like.

## Related Skills
- [[skill-name]]
- [[other-skill]]
```

3. **Update this SKILLS.md** file

4. **Add tests** in `tests/test_your_skill.py`

5. **Commit**:
```bash
git add skills/analysis/your-skill.skill SKILLS.md tests/test_your_skill.py
git commit -m "add skill: your skill name"
```

---

## ENVIRONMENT & DEPENDENCIES

**Python**: 3.14  
**Environment Variable**: `$env:OMISSION_DATA_ROOT = D:\workspace\data`  
**Key Modules**:
- `src/analysis/io/loader.py` — unified data loading
- `src/analysis/contracts/` — data validation schemas
- `src/analysis/visualization/` — plotting utilities
- `jnwb/` — JaxNWB integration

**Testing**: All skills should have unit tests in `tests/` directory.

---

## CONTACT & CONTRIBUTION

**Repository Owner**: hnxj  
**Last Auditor**: Claude (2026-06-16)  
**Issues/Updates**: Use git issues or contact directly.

---

**Master Index Status**: [ACTIVE & MAINTAINED]  
Next refresh scheduled: 2026-07-16
