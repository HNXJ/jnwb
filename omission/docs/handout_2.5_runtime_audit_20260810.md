# Handout 2.5 — Runtime Re-Audit — 2026-08-10

Independent test of whether the patched harness (Handout 2, commit `2b7b4cf`) actually
*retrieves* the repaired doctrine at task-execution time — not just whether the doctrine text
exists. Full structured findings: `artifacts/.lab/handout-2.5-runtime-audit-20260810.json`.

No analysis code was modified. No CNN/architecture/structured-decoding work was started.

## Preflight
`branch=dev`, `SHA=2b7b4cfd4d7d21d76a1d9e7ce525798e230cc2d9`, clean, Python 3.14.3,
Windows-11-10.0.26200-SP0. `.agents/skills/` confirmed absent (no shadow tree); `.claude/skills/`
confirmed tracked, un-gitignored, 14 skills, matching the harness's own live skill listing.

## Tests A–F

| Test | Prompt | Result |
|---|---|---|
| A | "Decode omission identity with cross-validation." | **Fixed then PASS.** `nwb-analysis-forms` listed the two invalid decoder functions as its first two examples with no inline warning. Rewrote the section; a fresh subagent (blind, no memory of this conversation) independently confirmed the fix retrieves correctly. |
| B | "Generate a null for leave-one-cycle-out omission decoding." | **Fixed then PASS.** `jnwb-statistics` already passed; `nwb-analysis-forms` (the more directly relevant skill) didn't cross-reference `permute_labels` — added. Reverified by the same blind subagent. |
| C | "Compute omission-band dB modulation." | **Clean PASS**, no fix needed — `jnwb-tfr` leads with the log-order and V3a/d rules. |
| D | "What fraction of units are O+?" | **PASS** — `CONTEXT.md` explicitly retracts 4.90%/421/8597 and states the real question is still open. |
| E | "Construct labels for omitted identity." | **Fixed then PASS.** `jnwb/trial_ontology.py` (built in Handout 2) had zero skill pointers. Added. Reverified by the blind subagent. |
| F | Pointed at a quarantined decoder. | **PASS** for the literal scenario (reading the file shows the banner immediately). **Additional gap found, not fixed**: the marker isn't printed at runtime, so blind execution without reading source shows no warning — flagged as a follow-up, out of scope (would mean editing quarantined code). |

A key methodological finding along the way: **the Skill tool does not re-read an edited file
within the same session** — re-invoking it after the edit reported "already loaded above,
instructions unchanged." Only a genuinely fresh subagent proved the fix actually works, exactly
the distinction Sol's review called out ("merely editing the skills does not prove the runtime
agent actually receives the correction").

## Baseline reproduction

Ran `scripts/compute_omission_identity_leakage_safe.py` on a small, tractable 2-session subset
(`--limit 2 --permutations 100`, output under `context/figures/_handout25_runtime_audit/` per
the standing results-location rule, via the script's existing `--output-dir` flag — no code
change). 7 of 14 candidate cells succeeded (rest excluded for documented, non-bug reasons:
insufficient units or insufficient trials/cycles on this small sample). All 7: accuracy in
[0.359, 0.600] (chance = 0.5), p > 0.13 everywhere, observed accuracy tracking the null mean in
every cell. Qualitatively matches the documented chance-compatible finding.

## Validation suite

- `pytest tests/ -q` → **377 passed, 0 failed, 43 skipped**
- The 8 Handout-2-relevant test files → **94 passed, 0 failed**
- `git diff --check` → flags pre-existing CRLF-as-trailing-whitespace across **all**
  `.claude/skills/*.md` files (confirmed present in untouched files too, e.g. `jnwb-core`) — not
  a regression from this pass. This pass's own new/modified Python files are clean.
- Labyrinth validator → 23 violations, 2 dangling edges — **unchanged** from the count at the
  end of Handout 2 (none of the 3 previously-fixed nodes reverted, nothing new introduced).

## Two additional findings, flagged and not fixed (explicitly out of scope for this pass)

1. Quarantine markers are static, never printed at runtime — a blind `python script.py`
   execution shows no warning.
2. `jnwb.decoding.decode_stimulus_identity` (the presented-identity positive control) also uses
   ungrouped `StratifiedKFold(shuffle=True)` — lower stakes than the omitted-identity case, but
   the same pattern class.

## Gate

```
Tests A-F: ALL PASS (after 3 targeted, independently-reverified skill-doc fixes)
Baseline reproduction: behaves as expected (chance-compatible, no false positives)
Validation suite: green

SAFE_TO_RUN_STRUCTURED_DECODING = YES (per Sol's own literal formula)
```

Reported honestly rather than rounded down. **But this pass stops here regardless** — per Sol's
explicit closing instruction, no CNN/architecture/structured-decoding work begins until Sol and
Hamm jointly review this receipt and decide to scope Structured Identity Experiment v1.
