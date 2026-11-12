# OCMA card spec: `curation_calibration_0.2.14`

STATUS: draft-awaiting-Hamm

Drafted 2026-11-12 at jnwb `92d118ea` (ocma plan decision 5). No card code exists for this spec. Hamm rules it before any code.

| Field | Value |
|---|---|
| id | `curation_calibration_0.2.14` |
| objective | Validation card for the defaults of `curate_and_label`: the planted laminar crossover's recovery rate and the null probes' false-acceptance rate, at the defaults and under a sweep of 15 parameters. Card kind: validation, section `calibration`. |
| reference | UNKNOWN (no DOI or figure in the receipt). Method reference in the receipt: vFLIP's SNR sweep, `artifacts/benchmarks/calibration/vflip_calibration_0.2.4.md`, cited as a reference for vFLIP's own calibration, not a bound. |
| observable | (a) proportion of planted probes with `\|anchor_um - truth_um\| <= 100`, with exact 95% Clopper-Pearson interval; (b) proportion of null probes graded A or B; (c) anchor offset, um, planted probes at defaults. Axis: swept value, as a multiple of the default (0.5, 0.75, 1, 1.5, 2). |
| signal_class | LFP. Synthetic laminar probe, 32 contacts, fs 1000 Hz, pitch 100 um (receipt, Method). No spikes. |
| claim_class | inference: detection and localisation of the crossover contact (recovery and false acceptance). |
| dataset | Synthetic only: `jnwb.testing.synth_laminar_motif` and its null (`snr=0`, same draws). Trials 2784 (planted 1392, null 1392), 24 seeds per cell, 40 epochs of 1000 samples per probe (receipt, Method and Result). Seed list: UNKNOWN in the markdown; the raw record `curation_calibration_0.2.14_raw.json` holds the trials and was not read (not in this packet's read list). |
| operations[] | `curate_and_label` (quoted in `jnwb/__init__.py`); `clopper_pearson` (quoted in `jnwb/__init__.py`). `synth_laminar_motif` is not quoted in `jnwb/__init__.py` (it lives in `jnwb.testing`); the ocma plan requires operations to be `jnwb.__all__` symbols, so it is listed here as a flag, not as an operation. |
| estimand | Probability that the planted anchor lies within one pitch of the truth, `crossover_contact * pitch_um`, at the default arguments; probability of grade A or B on a null probe at the same arguments. |
| controls[] | Null probe at `snr=0` from the same draws (receipt, Method); each parameter swept alone at 0.5x to 2x default; seven plant families (`steady`, `edge`, `lobe`, `silent`, `consistency_a`, `consistency_b`, `dead`) (receipt, Method). |
| tolerance | Recovery: 100 um, one pitch, bound included. Second recovery column: grades A to D only. Intervals: exact two-sided 95% Clopper-Pearson (receipt, Method). |
| verdict_rule | Receipt rule: a default is FLAGGED when it lies outside its stable range. Stable range: values whose recovery interval overlaps the interval of the highest-recovery value and whose false-acceptance interval overlaps the default's (receipt, Method). Receipt result: FLAGGED none. Card-level pass or fail: UNKNOWN (not in receipt). |
| writes[] | Proposed, not in receipt: one `validations` entry with `section: "calibration"` in the dashboard data (`scripts/dashboard/data.schema.json`, `$defs/validation`), built by `scripts/build_dashboard.py`. |
| receipt path | `artifacts/benchmarks/calibration/curation_calibration_0.2.14.md` (tracked; last changed by `cb781455`) |
| sha256 | `7252e6ddf8cf37450e8a148c65aafad7525cfa23fe732e20677333c5dd7029c9` (hashlib, receipt file) |
| recorded_commit | UNKNOWN. The receipt states declared version 0.2.16 and estimator SHA-256 `5a8c30c542be7772`, not a commit (receipt, header and Method). |

## Flags for Hamm (not resolved here)

1. **Release mismatch.** The receipt says it "Qualifies release 0.2.14", and its file name says 0.2.14. Its declared version and environment at generation are 0.2.16 (receipt, header and Result). The card cannot state which release the defaults ship in until this is ruled.
2. **The default row is 7/24 in every parameter table.** The default recovers 7 of 24 (CI [0.126, 0.511]); the nearby steady-family values recover 16 of 24 (CI [0.447, 0.844]). Example: `n_windows` reads 2 to 16/24, 3 to 16/24, 4 (default) to 7/24, 6 to 16/24, 8 to 16/24. The receipt marks these "stable: yes" because the intervals overlap. The overlap is at 0.447 to 0.511, so the stability verdict rests on n = 24 and is sensitive to it.
3. **Whether x1 rows run on their family plant.** The receipt says each parameter runs on the plant that decides it, and that the default is always the x1 row (Method). All 15 x1 rows show the same 7/24 count. The markdown does not show whether the x1 row is run per family. The raw record (`curation_calibration_0.2.14_raw.json`) settles this and is not read here.
4. **Operations.** `synth_laminar_motif` is outside `jnwb.__all__` (see the table). The card needs a ruling on whether the synthetic generator is a card operation.

## Figure (proposed)

UNKNOWN. Receipt has no figure. Candidate: the recovery-rate-by-multiple plot from the Result tables, with CI bars. Hamm rules.
