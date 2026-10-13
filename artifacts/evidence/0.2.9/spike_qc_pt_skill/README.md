# Proposal: a downstream unit-QC and PT skill on jnwb

Status: proposed for Hamm's ruling; on a branch, not on `dev`. Nothing here ships.

`proposed_SKILL.md` (named so it does not load as a skill) and `scripts/` are a downstream study's single-unit curation and peak-to-trough (PT)
classification pipeline for the fourGLO NWB corpus, ported from MATLAB to Python on jnwb. It is a
corpus convention (AGENTS.md section 4), so where it lives is a ruling:

1. Keep it downstream, in the lab repository, and use it only as the source the roadmap row 14-08 asks for in
   `artifacts/evidence/0.2.9/unit_qc_inventory.md` cite (D1 sharpness, D3 polarity, D9 human
   curation).
2. Keep it here under `artifacts/` as a worked example of a downstream skill built on jnwb.
3. Ship it under `skills/`, which needs the study conventions removed from it first.

What the port shows about jnwb, whatever the ruling:

| Finding | Where |
|---|---|
| `waveform_mean` rows in the fourGLO files are in acquisition order while the electrodes table is in depth order, so `probe_geometry` cannot reorder waveforms; a channel map can | `proposed_SKILL.md`, "What comes from jnwb" |
| `waveform_features` `trough_to_peak_ms` (Siegle et al. 2021) and the study's ramp PT are different measures; its docstring already says so | `jnwb/unit_quality.py` `waveform_features` |
| The fourGLO files need `nwb_read_io(..., allow_missing=("session_description",))` | `scripts/spikeqc.py` `collect_units` |

Validation, run 2026-10-06 against the study's saved MATLAB outputs with jnwb 0.2.9 (observed;
the script then had the paths inline, since moved to arguments): selection identical to the
saved index, legacy PT max abs diff 0 with no NaN, identical legacy and corrected-scale splits at
0.34 and 0.4 ms, and one session collected from NWB matching the saved waveforms and metrics.
