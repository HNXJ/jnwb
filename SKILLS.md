# Omission Repository Skills Index

**Repository**: `D:\workspace\omission`  
**Last Updated**: 2026-06-16  
**Status**: Active (4 core skills + legacy stack)

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

## RECOMMENDED SKILL REFRESH PLAN

**Priority 1 (Do Now)**:
1. Update `.gemini/skills/` paths: `D:/drive` → `D:\workspace`
2. Create `skills/analysis/a4-trial-count-validation.skill` (formalizes current A4 work)
3. Create `skills/analysis/jnwb-qc.skill` (formalizes JNWB suite)

**Priority 2 (This Quarter)**:
1. Consolidate duplicate behavioral/oculomotor skills
2. Formalize SPK/SUA skill from f001-f037 modules
3. Create LFP time-frequency routing skill

**Priority 3 (Future)**:
1. Archive non-essential legacy skills
2. Create unified "Omission Neural Analysis" meta-skill hierarchy
3. Add cloud-based skill sharing for reproducibility

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
