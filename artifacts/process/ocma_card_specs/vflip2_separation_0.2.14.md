# OCMA card spec: `vflip2_separation_0.2.14`

STATUS: draft-awaiting-Hamm

Drafted 2026-11-12 at jnwb `92d118ea` (ocma plan decision 5). No card code exists for this spec. Hamm rules it before any code.

| Field | Value |
|---|---|
| id | `vflip2_separation_0.2.14` |
| objective | Validation card for the agreement threshold T between the vFLIP and vFLIP2 crossovers, the 95th percentile of the null gap, that `fuse_laminar_anchors` reads as `agree`, `disagree` or `unresolved` (receipt title, "15-18"). Card kind: validation, section `calibration`. |
| reference | UNKNOWN (no DOI in the receipt). Estimator SHA-256 rule: `scripts/calibrate_xflip.py`, shared with `scripts/calibrate_vflip.py` (receipt, Sources). |
| observable | Gap `\|vflip2_crossover - vflip_crossover\|`, in contact spacings (the `separation_contacts` value). Reported: threshold T, the 95th percentile, `22.8002` contact spacings; defined draws 117 of 400; median defined gap `8.3569`; largest `27.2767` (receipt, Result). |
| signal_class | LFP. Synthetic laminar probe: 32 contacts, fs 1000 Hz, pitch 100 um, 8000 samples per draw (receipt, Fixed inputs). No spikes. |
| claim_class | inference: an agreement threshold on the null distribution of the gap. |
| dataset | Synthetic null only: `jnwb.testing.synth_laminar_motif` at `snr_null = 0.0`, `c_crossover = 16` (immaterial at snr 0). 400 draws. Each draw is a successive child of a seeded `rng`. Seed value: UNKNOWN in the markdown (not in Fixed inputs); the raw record `vflip2_separation_0.2.14_raw.json` holds it and was not read (not in this packet's read list). |
| operations[] | `fuse_laminar_anchors` (quoted in `jnwb/__init__.py`); `vflip` (quoted in `jnwb/__init__.py`); `vflip2` (quoted in `jnwb/__init__.py`). Quoted-string match only; `jnwb.__all__` membership is not parsed separately. |
| estimand | The 95th percentile of the defined gap distribution under the null, linear interpolation (`numpy.percentile` default), with gates open. |
| controls[] | Gates open: `vflip_min_support_score = -1e9` and `vflip2_omega_cut = -1e9`, so both crossovers are defined on noise (receipt, Method). Undefined draws counted, not filled in (receipt, Method). No planted probe in this receipt (see Flags). |
| tolerance | UNKNOWN. Receipt gives no acceptance tolerance on T. Percentile 95 (receipt, Fixed inputs). |
| verdict_rule | Receipt rule: `agree` at or below T; `disagree` above T; `unresolved` when the gap is undefined (receipt, Method). |
| writes[] | Proposed, not in receipt: one `validations` entry with `section: "calibration"` in the dashboard data, built by `scripts/build_dashboard.py`. Whether T is also a code constant is UNKNOWN (receipt does not name the code location). |
| receipt path | `artifacts/benchmarks/calibration/vflip2_separation_0.2.14.md` (tracked; last changed by `20900a0a`) |
| sha256 | `5ed16244901d20306ba76b748b395620fca25cb65ce224f48b781fcb019ed940` (hashlib, receipt file) |
| recorded_commit | UNKNOWN. The receipt states declared version 0.2.13 and estimator SHA-256 `b2502142dab9870c` (vFLIP) and `6aa906f40c2de637` (vFLIP2), not a commit (receipt, header). |

## Flags for Hamm (not resolved here)

1. **Release mismatch.** The receipt says it "Qualifies release 0.2.14", its file name says 0.2.14, but its declared version and environment at generation are 0.2.13 (receipt, header and Result). The threshold may describe an estimator build older than 0.2.14. Whether the 0.2.14 estimators carry the same SHA-256 is UNKNOWN (the receipt does not say).
2. **T rests on 117 defined draws.** 283 of 400 draws (71%) are undefined. The percentile is taken over the 117 defined gaps only. The receipt gives no interval on T. Hamm rules whether T needs an interval or more draws.
3. **No known-positive control.** The receipt measures only null behaviour (`snr_null = 0`). It does not show how often a planted crossover reads `agree` at T. The card cannot state the threshold's power.
4. **Gate regime.** The threshold is computed with gates open. The receipt says that with the gates closed, almost no null draw holds both crossovers (receipt, Method). The card must name which gate setting T belongs to. The gate settings of the public default are UNKNOWN (not in receipt).

## Figure (proposed)

UNKNOWN. Candidate: histogram of the defined gaps with T marked, from the raw record. Hamm rules.
