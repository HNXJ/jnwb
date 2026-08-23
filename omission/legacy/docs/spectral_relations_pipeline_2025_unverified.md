# Spectral-relations pipeline (2025-06/2026-06) — Q1/Q2/Q3 findings NOT reproduced

**Extracted 2026-08-22** from `legacy/markdowns/CLAUDE.md`'s "Spectral Relations & Network
Analysis" section during repository normalization. That section stated three "Key Findings"
(Q1 band-network structure, Q2 spike/LFP cross-modal consistency, Q3 a Theta→Alpha→Beta→Gamma
temporal-lead hierarchy) as established facts. **Checked against the pipeline's own surviving
output** (`omission/outputs/spectral_relations_pipeline/`, local-only/gitignored) before writing
anything into current evidence, per doctrine ("no claim without a receipt"). Verdict: **do not
promote any of the three findings** — the underlying computation does not support them.

## What the outputs actually show

- **Q1 (spectral band networks): zero correlations computed.**
  `q1_execution.log` ends with `Q1 Complete: 0 correlations computed`; no
  `q1_spectral_networks_full.csv` (or any Q1 results file) exists. The claimed "Key Finding"
  ("Alpha and Beta bands show strongest inter-area correlations; ~73% of significant networks
  are condition-specific") has no data behind it in this run.

- **Q3 (lead-time / temporal hierarchy): degenerate output, not a real cross-correlation
  result.** `results/q3_lead_times.csv` (300 rows) has `correlation` clustered at ~1.0 for
  every row (1.0 to 1.03, never lower) and `lag_ms` taking only the values {0, 1, 2} — not the
  documented ±500 ms search range. This is not consistent with a genuine cross-band lead-time
  analysis; it reads as a computation that never actually varied its inputs (e.g. comparing a
  signal to itself, or an unshifted/no-op lag search). The claimed "Key Finding" (a
  Theta(-30ms)→Alpha(-10ms)→Beta(0ms)→Gamma(+30ms) progression) is not supported by this file.

- **Q2 (spike networks): real, executed data — but its comparative claim is unverifiable.**
  `results/q2_spike_networks.csv` has 66,309 rows of plausible-looking spike-pair correlations,
  p-values, FDR-corrected p-values, and cross-correlation lags — this file looks like a genuine
  completed computation, unlike Q1/Q3. However the doc's "Key Finding" for Q2 is a **cross-modal**
  claim ("~67% cross-modal consistency; LFP leads spikes by 5-15ms") that requires comparing
  Q2's spike networks against Q1's LFP networks. Since Q1 produced zero output, there is nothing
  to compare Q2 against — the cross-modal claim cannot have been computed from these artifacts,
  regardless of whether Q2's own numbers are individually trustworthy.

## Disposition

None of the three "Key Findings" are written into `omission/context/PROJECT_STATE.md` or any
other current-evidence file — they do not meet the bar. This file exists so the prior claim and
the reason it doesn't survive scrutiny remain discoverable, rather than silently disappearing
when the doctrine wrapper (`legacy/markdowns/CLAUDE.md`) was marked superseded.

If this analysis is worth re-running: the pipeline scripts themselves
(`scripts/spectral_relations_pipeline.py`, `scripts/spectral_network_visualizations.py`) and the
skill file referenced by the old doctrine (`.agents/skills/spectral-relations-pipeline/SKILL.md`)
no longer exist anywhere in the current tree — only the output artifacts and this doc's own
methodology description (in `omission/outputs/spectral_relations_pipeline/PIPELINE_EXECUTION_SUMMARY.md`,
also gitignored/local-only) survive. A re-run would need to be rebuilt from that methodology
description, not resumed from existing code.
