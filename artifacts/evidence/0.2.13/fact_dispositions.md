# Dispositions of the 32 UNHELD facts

Ruled 2026-10-15 (`artifacts/rulings/2026-10-15.md`, fact schedule): every UNHELD fact carries a disposition, an owner or dependency, an evidence requirement and a target cycle; none is counted HELD here. `python scripts/fact_gate.py` at `4aa486a2`: HELD 11, UNHELD 32, VIOLATED 0. Probes are a read-only sweep of that tree; "not probed" means no cheap probe could show a violation.

Dispositions: **shipped** (a shipped claim depends on it; investigated now), **0.2.13** (its holder lands in 0.2.13 and verifies it before release), **ruling** (the holder waits on a ruling or an external input; the dependency is kept). No fact was found duplicated or superseded.

| Fact | Holder | Disposition | Probe at `4aa486a2` | Evidence that moves it to HELD | Target |
|---|---|---|---|---|---|
| B2 | `gate:6`, 12-07 | shipped, escalated | `jnwb/paths.py:87-89` ships the deprecated `OMISSION_*` environment names, against `docs/architecture.md:119` ("it names no study, session or condition"); session labels in `tests/test_metadata.py` and `tests/test_trajectory.py`; gate 6 skips `tests/` | Hamm's choice: the architecture claim names the deprecated names as its exception, or the names are removed; then gate 6 reads `tests/` | 0.2.13 |
| R7 | 12-07 | shipped, repaired | `.github/CONTRIBUTING.md:12` said six legs on Ubuntu and Windows; the matrix runs seven, Windows without 3.15 (`.github/workflows/workflow.yml:92-94`) | the sentence now states the matrix; 12-07's check that the prose follows the matrix | 0.2.13 |
| B3 | 11-06 | 0.2.13 | 8 public callables default `window=` with no cited reason, `xflip` and `zflip` (0.2.12) among them | a cited reason per default, as 11-06 accepts | 0.2.13 |
| I1 | 10-10 | 0.2.13 | no declarations module; no numeric operation declares signature types | 10-10's declarations and their check | 0.2.13 |
| I2 | 10-10 | 0.2.13, with 15-17 | `xflip`'s `surrogate_method='auto'` resolves by input form and `n_samples` and records nothing | 15-17's `null_method`, then 10-10 | 0.2.13 |
| I3 | 10-10 | 0.2.13 | not probed | 10-10's acceptance | 0.2.13 |
| S1 | 11-07 | 0.2.13 | no violation: `tests/test_figure_form.py:1292` (2 passed) covers two generators only | the scan over every generator, with its planted case | 0.2.13 |
| S5 | 11-07 | 0.2.13 | 20 draws without an `rng`-named parameter: `random_state` in `jnwb/bilinear.py`, per-iteration seed helpers in `jnwb/jrsa/_inference.py` and `jnwb/statistics/_cluster.py`, a fixed jitter seed in `jnwb/visual_qc.py:318`, and scripts; `np.random.seed(0)` at `tests/test_decoding.py:105`. No shipped number found irreproducible | the S5 scan, with a ruled reading of `random_state` and of seed helpers fed from an `rng` | 0.2.13 |
| S2 | 11-07 | ruling | `jnwb/spectral/_psd.py:389`, `:558`: the mean of log10 power in the R-squared denominator of a log-log fit; no dB average of an estimate found | Hamm's reading of clause 1 (roadmap 11-07) | 0.2.13 |
| S7 | 12-11 | ruling | not probed | the S7 scan with its planted case, once a criterion for a retyped rule is ruled (12-11) | 0.2.13 |
| S8 | 09-04 | 0.2.13 | not probed | 09-04's claim-class text check | 0.2.13 |
| S9 | 09-04 | 0.2.13 | candidates: `np.nan_to_num`, `dropna`, `fillna` in `jnwb/metadata.py`, `jnwb/analyzers.py`, `jnwb/visual_qc.py`, `jnwb/laminar_curation.py:764`; `xflip`'s fill of a zero-variance channel never reaches a result (refused at `jnwb/laminar/_xflip.py:740-757`) | each site classified: a mask, a refusal or a substituted value | 0.2.13 |
| S10 | 09-04 | 0.2.13 | no violation: docstrings name the exchangeability scheme (`jnwb/statistics/_cluster.py:59`) | 09-04's check | 0.2.13 |
| S11 | 09-04 | 0.2.13 | not probed | 09-04's check | 0.2.13 |
| S12 | 09-04 | 0.2.13 | not probed | 09-04's check | 0.2.13 |
| S13 | 09-04 | 0.2.13 | no violation (grep; `zflip`'s gate at `jnwb/laminar/_zflip.py:653`) | 09-04's check | 0.2.13 |
| S14 | 09-04 | 0.2.13 | no violation: 11 hits, all negated | 09-04's check | 0.2.13 |
| K4 | 09-04 | 0.2.13 | candidate: `skills/jnwb-statistics/SKILL.md:17` (`draw_manifest`, `label_digest`) | 09-04's check | 0.2.13 |
| K5 | 11-09 | 0.2.13 | candidate: `jnwb-landmark-viz`, `jnwb-paradigm`, `jnwb-qc` and `jnwb-laminar` ship while 11-09 reads "no shipped behaviour" | 11-09's K1 and K5 report per skill | 0.2.13 |
| R2 | 12-07 | 0.2.13 | the workflow installs nothing from PyPI after `publish-pypi` (`.github/workflows/workflow.yml:579-660`); 0.2.12 was installed from PyPI by hand in a fresh venv, `smoke_installed.py` PASS (2026-10-15) | an automated post-publication install, or a recorded receipt per release | 0.2.13 |
| R5 | 12-07 | ruling | no violation for v0.2.12 (CI on `main` and on the tag passed); the fact reads "on main", the ruling and the CI qualifier accept a `dev` run | Hamm settles which run qualifies | 0.2.13 |
| D1, D3 to D10 | 11-03 | ruling | not probed | 11-03, after the public API rulings of 07-21 and 07-22 | 0.2.13 |
| D2 | 11-03 | ruling | `repair_ragged_index` writes NWB (`jnwb/nwb_integrity.py:252-262`, `:351`) with no declared mutation category; `docs/repairing_nwb.md` documents the write, so no public claim is false | 07-21's mutation API ruling, then 11-03 | 0.2.13 |
| D11 | 11-03 | ruling | candidate: `dtype` on `TFRAccumulator` and `complex_tfr`; the identity constant names device, backend and `n_jobs` only | 11-03 | 0.2.13 |

## Open

- Holders that name items whose text does not name them back (D4 to D11, I2, I3, S9 to S14, K4): roadmap 11-32 ("Holders that name their work") holds this.
- S5 counts 17 sites in roadmap 11-07 and 20 in this probe; 11-07 recounts when it opens.
