# Project: Omission (V1-PFC Predictive Routing)

## 1. Authoritative Topology
All analytical and instructional operations MUST align with the **Figure Registry** (`src/analysis/registry.py`). This is the only source of truth for metadata and module mapping.

### Canonical Directories
- **Source**: `src/`
  - `src/analysis/`: Core primitives (IO, Signal Conditioning, Visualization).
  - `src/fxxx_.../`: Modular figure packages (Analysis + Plotting).
- **Instructional**: `.gemini/skills/` (Primary Skill Store).
- **Output**: `../outputs/oglo-8figs/` (Repo-relative resolution required).
- **Dashboard**: `dashboard/` (Omission Terminal).

## 2. Analytical Mandates
1. **Convergence Truth**: Do not reference `src/core/*` or `src/utils/*`. These are legacy/stale artifacts.
2. **Registry-Driven**: All new figures must be registered in `FigureRegistry` before execution.
3. **Decentralized execution**: All scripts must resolve paths relative to the repository root. No hardcoded absolute drive letters in canonical code.
4. **Stable-Plus Constraint**: Restrict operations to vetted 'Stable-Plus' population (FR>1Hz, SNR>0.8, 100% trial presence).

## 3. Aesthetic Protocol (Madelane Golden Dark)
- **Primary Color**: #CFB87C (Gold) for Sinks / Target signals.
- **Secondary Color**: #9400D3 (Violet) for Sources / Omission signals.
- **Background**: ALWAYS #FFFFFF (Pure White) for paper space.
- **Library**: Plotly (HTML interactive export only).

## 4. Omission Terminal Protocol
The dashboard at `dashboard/` is the authoritative **Neuroscience Terminal**. 
- **Scoreboard Ledger**: High-density monitoring of analysis status and quality scores.
- **Sentinel Audit**: Programmatic verification of figure integrity (Labels, NaN-check, White-bg).
- **Madelane Theme**: Applied consistently across UI and figures.

## 5. Skills
Refer to `.gemini/skills/` for executable operator contracts. These are the ONLY active instructions. All conceptual notes in `context/specs/` are secondary.
