# L8 — cross-area coherence (standard + imaginary)

Reads `canonical_pooling_method` from [L0](../L0_pooling_reconciliation/L0_stats.json), same gate
as L1-L7. Node definition mirrors [L7](../L7_cross_area_power_correlation/README.md) (area×layer,
sup/deep only) but rediscovers node coverage against raw NWB files rather than importing L7's
node list, because coherence needs the raw/complex signal, not L7's precomputed power arrays.

**Method**: `jnwb.spectral.imaginary_coherency` reused verbatim for standard magnitude-squared
coherence (`coh_mag_mean`) and the volume-conduction-insensitive imaginary part (`icoh_abs_mean`,
`icoh_mean`) — per spec's own "Critical" instruction to report both, since standard coherence is
inflated by volume conduction and the imaginary part is not. Band-mean phase (not part of
`imaginary_coherency`'s return) computed locally from the same Welch/CSD estimator. One
representative channel per node (same limitation [L6](../L6_volume_conduction_control/README.md)
already states for area-level channels, extended here to node granularity).

## Bugs found and fixed (visual-inspection gate)

1. **Node-key collision** — `sub-V182o_ses-260702` genuinely records FEF on two different
   probes. A bare `f"{area}{layer}"` node key collided the two into indistinguishable labels
   (confirmed on the first real run: `nodes=['FEFsup','FEFdeep','FEFsup','FEFdeep','MTsup',
   'MTdeep']`). Fixed by making every node key probe-qualified (`f"{area}{layer}_{probe}"`),
   always — not conditionally — so labels stay consistent across sessions. **The same latent bug
   was found in [L7](../L7_cross_area_power_correlation/README.md)'s `node_trial_traces`, where it
   was worse: a silent dict-overwrite that actually lost data**, not just an ambiguous label —
   L7's original real run reported only 4 nodes for `sub-V182o_ses-260702` (one probe's FEF data
   silently dropped) when 6 exist. L7 was rerun after the same fix; its correlation matrix and
   significant-pair counts for that session changed materially, and its README/evidence node were
   corrected accordingly — this was a genuine correctness fix in both scripts, not a relabeling.
2. **Clipped/overflowing suptitle** — first render's title string was too wide for the figure at
   the given fontsize and rendered centered *outside* the canvas on both edges (visible as
   truncated text at both the start and end of the sentence). Fixed by wrapping into three
   explicit shorter lines and adjusting `top`/`bottom` margins; re-rendered and re-verified.

## Result (descriptive — no claim asserted in code)

**Every same-probe (same-letter-suffix) node pair, in all three sessions, all bands checked,
shows high standard coherence (coh_mag 0.56–0.89) alongside near-zero imaginary coherency
(icoh_abs 0.02–0.10)** — a gap of 0.31–0.82. This is exactly the spec's own stated signature of
"conducted, not interacting" coupling, and it is completely consistent with what
[L6](../L6_volume_conduction_control/README.md) already found via a different statistic
(zero-lag coupling fraction) and what [L7](../L7_cross_area_power_correlation/README.md) found
via a third (trial-level power correlation): same-probe adjacent-depth pairs look
reference/volume-conduction-dominated across three independent measures.

**Cross-probe pairs are mostly low on both measures** (coh_mag 0.01–0.15, icoh_abs comparably
small or even nominally larger than coh_mag at these very low absolute levels — noise-dominated,
not a real "more lagged than total" reading at this magnitude) — **with one exception**:
`sub-V182o_ses-260715`'s PFC↔FEF cross-probe pairs show elevated standard coherence (0.43–0.47)
with still-low imaginary coherency (0.07–0.12), a smaller but real gap (0.31–0.40). This is the
**same session L7 already flagged as an outlier** (13–15/15 node pairs FDR-significant in every
band there) — cross-validated here from an independent statistic, strengthening the read that
`sub-V182o_ses-260715` carries some session-wide shared signal (not necessarily identical to the
same-probe volume-conduction pattern, but also not ordinary independent-area coupling).

None of this is asserted as a conclusion in code — it is the descriptive pattern the numbers
show, left for the manuscript text to interpret alongside L6/L7.

## Self-test

`python L8_cross_area_coherence.py --test`: spec's own explicit acceptance test — a synthetic
zero-lag common-source signal gives high standard coherence (0.830) and near-zero imaginary
coherency (0.022) — PASS. A genuinely lagged common source gives both high (0.813 / 0.794) —
PASS. Independent noise gives low standard coherence (0.013) — PASS. Determinism also checked.

Outputs: `L8.svg` / `L8.png` / `L8.pdf`, `L8_stats.json`, `L8_manifest.json`.
