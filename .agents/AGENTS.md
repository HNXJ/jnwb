# Project-Scoped AGENTS.md Context

## Identity & Timezone
- **User**: Nejath (CST/CDT, UTC-6/-5)
- **Role**: Systems neuroscience researcher (electrophysiology, NWB, spike and LFP analysis).

## Engineering Operating Rules
Operating style is strictly governed by `RULE[user_global]` (verification-first, minimal patches, receipts required, stop on ambiguity, zero hype language).

## Environment & Projects
- **Python**: 3.10+ (NumPy, SciPy, Pandas, PyNWB, PyTorch, CuPy, JAX, pytest).
- **Filesystem**: `D:/workspace/` (Git repos), `D:/analysis/nwb/` (NWB data files).
- **Active Projects**: `omission`, `the_pipeline`, `biophys`, `gamma`.

## The Developer Tracking System
Every repository MUST maintain a tracking registry inside the `artifacts/developer/` directory containing three JSON database files:
1. `progress.json`: The complete status table of all repo files. Schema: `filename`, `purpose`, `score` (out of 100), `tbis` (To Be Implemented), `tbds` (To Be Determined), `warnings`.
2. `review.json`: Identical schema as `progress.json`. Tracks completed actions awaiting review.
3. `plan.json` (or `plans.json`): Brainstormed plans, priorities, and proposed enhancements.

A rendered Markdown report summarizing the status must be kept at `artifacts/progress_report.md`.

### Scoring Rubric (Out of 100)
- **100**: Fully completed. Core code is implemented, documented, and verified with passing unit/integration tests. Imports are optimized.
- **80-90**: Implemented and functional. Core features work and basic tests pass, but minor edge cases, docstrings, or advanced validations are pending.
- **50-70**: Partially implemented or in-progress. File structure is present, but active TODOs (`tbis` or `tbds` fields) remain, or validation is incomplete.
- **<50**: Skeleton code or placeholder. Critical logic is missing, untested, or experiencing runtime/compile-time errors.

## Leveraging Workspace Skills
- Before writing custom code or scripts for data analysis, check if specialized skills exist under `.agents/skills/` (e.g., `jnwb-core`, `jnwb-spiking`, `jnwb-tfr`, `jnwb-statistics`, `jnwb-visualization`).
- Prioritize using canonical classes and functions (e.g., `UnitAnalyzer`, `TFRAnalyzer`, `StatisticalAnalysis`, `population_by_area`).
- If custom scripts are needed, import and extend these existing libraries rather than replicating their functionality.

## Context Inheritance & Hierarchy
- The workspace-specific context file `.agents/AGENTS.md` inherits from the global context `C:\Users\nejath\.gemini\config\AGENTS.md`.
- Workspace contexts may specialize path directories, project scopes, or active project configurations but must not contradict global engineering principles. Keep global and workspace context files in sync.

## Permanent Flagger Actions
Whenever the user issues one of these command phrases, adhere strictly to the following protocols:

### 1. "Proceed with Planning"
- **Flow**: `plan.json` -> `progress.json`
- **Protocol**: Load the brainstormed items from `plan.json`. Inspect the codebase and translate active plans into specific file-level items inside `progress.json` by adding placeholder entries, re-scoring existing files, or updating their `tbis`/`tbds`/`warnings` and todos.

### 2. "Proceed with Progress"
- **Flow**: `progress.json` -> `review.json`
- **Protocol**: Load `progress.json` and locate files with score < 100/100 or pending notes. Systematically implement the required changes (delegating large/parallel tasks to sub-agents if needed). Run testing to verify correctness. Once resolved and verified, move the file's database entry from `progress.json` to `review.json` (using identical schemas).

### 3. "Proceed with Review"
- **Flow**: `review.json` -> `progress.json`, `plan.json`
- **Protocol**: Inspect every item in `review.json` to validate correctness:
  - **Case A (Pass)**: If verified as correct, move the item back to `progress.json` with a score of 100/100 and clean warning/TBI/TBD fields. Log new ideas or extension features in `plan.json` if applicable.
  - **Case B (Fail)**: If it requires re-action, move the item back to `progress.json` with a reduced score and detailed notes explaining the failure.
  - **Case C (New Issue)**: If review reveals a separate issue, update `progress.json` and `plan.json` respectively.
  - **Case D (Empty Review)**: If `review.json` is empty, run a critical re-scoring of `progress.json` to identify further optimizations.

### 4. "Proceed with Brainstorm"
- **Protocol**: Review `plan.json` and other codebase files to outline long-term refactoring strategies, documentation enhancements, library memory/skill reforms, or new experimental paradigms. Append brainstorm outputs back to `plan.json`.
