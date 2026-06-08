# Project: Omission (V1-PFC Predictive Routing)

## Key Mandates
- **Windows OS Execution Hygiene**: Use PowerShell syntax (`;` instead of `&&`) in win32.
- **Atomic VCS Mandate**: Group logical tasks; do not push after every minor write.
- **Analytical Command Center**: All Phase 4-5 outputs must be compatible with high-density terminal visualization. Note: The interactive React/Vite dashboard is removed from Git tracking and ignored.

## 1. Authoritative Topology
All analytical and instructional operations MUST align with the **Figure Registry** (`src/analysis/registry.py`). This is the only source of truth for metadata and module mapping.

### Canonical Directories
- **Source**: [src/](file:///D:/workspace/omission/src/)
  - `src/analysis/`: Core primitives (IO, Signal Conditioning, Visualization).
  - `src/fxxx_.../`: Modular figure packages (Analysis + Plotting).
- **Instructional / Skills**: [docs/skills/](file:///D:/workspace/omission/docs/skills/) (Primary Skill Store).
- **Output**: `../outputs/oglo-8figs/` (Repo-relative resolution required, git-ignored).
- **Tests**: [tests/](file:///D:/workspace/omission/tests/) (Validation suite).

## 2. Analytical Mandates
1. **Convergence Truth**: Do not reference `src/core/*` or `src/utils/*`. These are legacy/stale artifacts.
2. **Registry-Driven**: All new figures must be registered in `FigureRegistry` before execution.
3. **Decentralized Execution**: All scripts must resolve paths relative to the repository root. No hardcoded absolute drive letters in canonical code.
4. **Stable-Plus Constraint**: Restrict operations to vetted 'Stable-Plus' population (FR>1Hz, SNR>0.8, 100% trial presence).

## 3. Aesthetic Protocol (Madelane Golden Dark)
- **Primary Color**: `#CFB87C` (Gold) for Sinks / Target signals.
- **Secondary Color**: `#9400D3` (Violet) for Sources / Omission signals.
- **Background**: ALWAYS `#FFFFFF` (Pure White) for paper space.
- **Library**: Plotly (HTML interactive export only).

## 4. Skills
Refer to [docs/skills/](file:///D:/workspace/omission/docs/skills/) for executable operator contracts. All conceptual notes in `context/skills/` are legacy.

## 5. Doctrines
### 5.1 Evidence and Receipt Doctrine
- All analysis steps must generate verifiable evidence artifacts (e.g., logs, manifest JSON) and retain them alongside code for reproducibility.
- Receipts must include repository SHA, branch, and execution timestamps.

### 5.2 Git Provenance Doctrine
- Every change is recorded with full commit SHA, branch name, and remote status (or `none_configured`).
- Repositories must never be in a dirty state when producing final reports.

### 5.3 Omission Phase Gating Doctrine
- Phases may only advance after successful THETA receipt validation of the preceding phase.
- Gate checks include manifest integrity, output path conformity, and runtime error absence.

### 5.4 NWB/PyNWB Doctrine
- NWB files must be accessed via `NWBHDF5IO` with explicit close handling.
- File paths are supplied via the `OMISSION_NWB_PATH` environment variable; absolute paths are prohibited in code.

### 5.5 Manifest Doctrine
- Each notebook emits a manifest JSON containing `repo_sha`, `repo_branch`, `run_root`, and artifact hashes.
- Manifest files must reside under `outputs/runs/<full_repo_sha>_<nwb_hash_prefix>/`.

### 5.6 Omission Task Doctrine
- Task definitions must be enumerated in `task.md` with clear progress markers and optional sub‑tasks.
- Tasks are bounded to a single phase and must not cross phase boundaries.

### 5.7 THETA Reporting Doctrine
- THETA reports summarize execution receipts, validate all manifest fields, and confirm output path schemas.
- Reports are the final gate before proceeding to the next phase.

# Doctrines verified - all seven sections present
