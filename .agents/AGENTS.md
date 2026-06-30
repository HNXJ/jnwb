# Project-Scoped AGENTS.md Context

## Operational Commands for Database Flagger Tracking

1. **Proceed with Progress**:
   - Triggered when the user requests "Proceed with Progress".
   - **Protocol**: 
     - Inspect the repository and check if `progress.json` contains any files scored below 100/100 or with active issues.
     - Systematically resolve each identified issue (by patching the code, running tests, and updating documentation).
     - Once the changes are verified to be correct and all tests pass, move the entry representing that file/item from `progress.json` to `review.json` (they share the identical field schema: `filename`, `purpose`, `score`, `tbis`, `tbds`, `warnings`).
     - Subagents may be defined and delegated to for parallel/background analysis.

2. **Proceed with Review**:
   - Triggered when the user requests "Proceed with Review".
   - **Protocol**:
     - Revise/inspect every item listed in `review.json` to verify correctness and safety.
     - **Verification Actions**:
       - If validation fails, move the item back to `progress.json` with updated notes detailing the revision failure.
       - If validation succeeds (all checks pass), move the item back to `progress.json` updating its score to 100/100 and updating its notes to reflect the verified state.
       - If `review.json` is empty or all files are at 100/100, trigger an automatic critical re-scoring of `progress.json` to identify further potential optimizations, issues, or proposed enhancements.
