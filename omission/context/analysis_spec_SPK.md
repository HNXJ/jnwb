# Omission Paper — Spiking-Primary Analysis Spec

For: Claude Code coder agent (spiking track)
Companion spec: `analysis_spec_LFP.md` (LFP track) — read §0.6 before touching anything cross-modal.

> **Repo-reconciliation note added 2026-08-16, not part of the original spec text below.**
> Checked against this repo's actual corpus before any implementation started:
> - Spec says "2 monkeys (Ivan + 1)"; the corpus on disk has 3 subjects (`C31o`, `V182o`,
>   `V198o`) and no "Ivan" appears anywhere in the repo — awaiting Hamm's mapping of which
>   subject code "Ivan" refers to (and whether the third subject is in- or out-of-scope for
>   this track) before S1 can report per-monkey numbers.
> - Spec's area list (`V1, V2, V3, V4, TEO, MT, MST, FEF, 8A, PFC`) does not match this repo's
>   canonical `figstyle.AREA_ORDER` (`V1, V2, V3a/d, V4, MT, MST, TEO, FST, FEF, PFC`) — `8A`
>   is not present anywhere in this repo; `FST` is not in the spec's list; `V3` here is pooled
>   as `V3a/d`. Not yet reconciled.
> - Spec's "stable" unit criterion (presence>=0.98, FR<100Hz at any 1s, SNR>0.5) is stricter
>   than this repo's current implementation (`scripts/compute_unit_trial_presence.py`:
>   `trial_presence_fraction > 0.98` only, no firing-rate ceiling or SNR gate). S1 needs to
>   decide whether to extend the existing criterion or the spec describes an intended-but-
>   unbuilt one.
> No `analysis_spec_LFP.md` companion has been provided/found in this repo yet.

## §0 Conventions (read before writing code)

0.1 Data contract. MaDeLaNe laminar recordings, oGLO task, 2 monkeys (Ivan + 1). Spike data
from Kilosort. Confirm the on-disk schema before coding.

* Areas: V1, V2, V3, V4, TEO, MT, MST, FEF, 8A, PFC (per-session availability varies)
* Conditions: `stim`, `omission`, `fixation` (fx), `offset`
* Unit response classes: S+ (stim-positive), S− (stim-negative), O+ (omission-responsive),
  O++ (strongly omission-responsive)
* Unit quality classes: stable (presence ≥ 0.98, FR < 100 Hz at any 1 s, SNR > 0.5), MUA
  (KS-flagged), unstable (silent or died mid-session)

0.2 Preprocessing already settled. Artifact rejection = 6× RMS, ~40/960 trials removed on
average. Reuse, report per-session counts.

0.3 Sorter version. This manuscript uses the existing KS2 sort. KS4 is an mGLO-track decision
and is explicitly out of scope — do not re-sort oGLO. If any analysis appears to require KS4,
stop and flag rather than re-sorting.

0.4 Every analysis emits three artifacts: figure (PDF+PNG, 300 dpi), `<id>_stats.json` (every
number appearing in figure or prose), `<id>_manifest.json` (inputs, git SHA, seed, n
units/trials/sessions, exclusions). No manuscript claim without a stats JSON.

0.5 Determinism. Explicit seeds everywhere. Same seed → byte-identical stats JSON. Test it.

0.6 Tests. Compact and fast: (a) synthetic ground-truth case with analytically known answer,
(b) shape/NaN/edge guards, (c) determinism. Seconds, not minutes — small synthetic arrays.

0.7 Cross-track ownership.

* This spec owns spike-triggered and spike→LFP-prediction analyses (S13, S14).
* LFP spec owns analyses where LFP conditions spiking (L11) and owns the spike-field
  coherence implementation (L12) — import it, do not reimplement. One convention, one
  implementation.

0.8 Repo hygiene. `dev` branch, frequent commits and pushes, clean root, strict `.gitignore`
on datasets/media.

0.9 Do not conclude. Output discriminating statistics with CIs. Where hypotheses compete,
report the quantity — not the verdict.

## §1 SPK-only

### S1 — Unit inclusion criteria rework [BLOCKER — do first]

Problem: Fixation was used as a baseline, so units that fire strongly during fixation and
during omission were rejected as non-selective. This systematically removed genuine omission
units.

Method: Replace baseline-contrast selection with a likelihood-of-firing criterion: P(unit
fires | omission) vs P(unit fires | random event drawn from the trial timeline). Be more
inclusive of `unstable` and `MUA` units — but tag them, never silently pool them with
`stable`.

Output: New unit inventory per class per area per quality tier. Explicit table: units gained,
units lost, units unchanged vs the old criterion.

Acceptance: Old and new criteria both computed and compared. Every downstream analysis reads
the new classification from a single canonical file. Every figure caption states which
criterion produced it.

Why this is first: S2, S4, S5, S6, S7, S8, S10, S11, and LFP-spec L11 all operate on these
populations. Running any of them before S1 means running them twice.

Tests: Synthetic unit that fires at high constant rate during both fixation and omission must
be retained by the new criterion and rejected by the old — this is the exact failure mode
being fixed, so it is the ground-truth case.

### S2 — Population responses by class (Fig 3)

Method: Population PSTHs for S+, S−, O+ per area, stim and omission. Normalise per unit before
averaging (z-score to fixation), otherwise high-rate units dominate.

Output: Class × area PSTH grid, CI bootstrapped over sessions, not trials.

### S3 — Example unit rasters (Fig 2)

Method: Representative rasters + PSTH for S+, S−, O+. Include the Ivan ramping omission unit.
Add a stimulus-negative example. Produce a separate raster set for Kari.

Acceptance: Selection rule for "representative" stated in the stats JSON (e.g. nearest-to-
class-median on the selectivity index) — not hand-picked. Hand-picked examples are a reviewer
target.

### S4 — Pool O+ and O++

Method: Combine and re-plot the population response. Prior expectation is that the pooled
response resembles O+ since O+ is the larger group.

Output: Three-panel comparison: O+, O++, pooled — with n for each.

Acceptance: If pooled ≈ O+ purely because of group size, state the n-weighting explicitly so
the plot is not over-read.

### S5 — Cross-area spiking onset latency [THESIS FALSIFIER — high priority]

Method: Forward smoothing only. Acausal smoothing leaks response backward in time and will
manufacture spurious early onsets — this is the single most likely way to get the wrong FF/FB
answer. Fit exponential onset slope per area. Bootstrap onset CI over sessions.

Output: Onset ± CI per area ordered by hierarchy level; pairwise onset-difference matrix with
CIs.

Discriminates: H1 low→high (V1 leads, feedforward) / H2 high→low (FEF/PFC leads, feedback) /
H3 simultaneous.

Standing observation to test: FEF and V4 currently appear earliest in both monkeys. V4 leading
is not obviously consistent with a pure top-down account — treat a V4-early result as a real
finding to explain, not noise to smooth away.

Acceptance: If pairwise CIs overlap zero, set `discriminating: false` in the stats JSON and
say so plainly. A non-result here is a legitimate and reportable outcome; it promotes CSD (LFP
spec L4) to primary evidence.

Tests: Known injected lags recovered within tolerance; synthetic zero-lag case returns
`discriminating: false`.

### S6 — S+ / S− directionality controls

Method: Apply S5 identically to S+ (predicted feedforward: low areas lead) and S− populations.

Rationale: This is the positive control. If S+ does not show the expected feedforward latency
ordering, the latency method itself is not working and the O+ result cannot be trusted either.

Acceptance: Report S+ result before interpreting the O+ result. Method validation precedes
inference.

### S7 — Laminar assignment of responsive units

Method: Assign each S+, S−, O+ unit to a cortical layer from the laminar alignment. Compute
class × layer distribution per area, tested against the layer distribution of all recorded
units (the correct null — not uniform).

Rationale: Feedback terminates in L1 and L5/6; feedforward originates in L2/3 and terminates
in L4. Laminar origin of omission units is direct FF/FB evidence.

Output: Class × layer proportion per area with CI, plus the all-units baseline distribution on
the same axes.

Promotion rule: If S5 returns `discriminating: false`, this becomes primary evidence — build
to publication quality.

### S8 — Cell type: fast- vs broad-spiking

Method: KS-reported waveforms are incorrect — do not use them. Recompute waveform metrics
(trough-to-peak, half-width, repolarisation slope) from the raw/filtered data for each unit,
then curate manually. Cluster into narrow (putative inhibitory) vs broad (putative
excitatory).

Output: Waveform metric scatter with cluster assignment; response-class composition by cell
type per area.

Acceptance: Bimodality of the metric distribution tested and reported — if the distribution is
not bimodal, a hard narrow/broad split is not justified and should be reported as a continuum
instead.

Note: Depends on manual curation, not on KS4. Do not re-sort.

### S9 — Hierarchy composition (Fig 3 bars)

Method: Proportion of each response class per area, ordered by hierarchy level. Separate bars
for stim and omission — combined bars let the stim response drown the omission response
visually.

Output: Stacked or grouped bars with binomial CIs; also report proportions by quality tier
(stable / MUA / unstable) so inclusiveness changes from S1 are visible.

## §2 SPK–SPK

### S10 — Spike-count correlation across area × layer

Method: Noise correlations between units across all area×layer nodes, computed separately for
stim and omission windows. Critical: Noise correlation is strongly biased by firing rate, and
omission-window rates will be lower than stim-window rates. Rate-match by subsampling before
comparing conditions. An uncorrected condition difference is a rate artifact.

Output: Node × node correlation matrix per condition + difference matrix, FDR-corrected.

### S11 — Directed spike–spike influence

Method: Cross-correlogram peak latency, plus GC and/or MI between area×layer population rates,
both directions reported separately.

Caution: GC on spike trains is sensitive to rate and SNR differences across conditions and
areas. Include a rate-matched control; without it the asymmetry is uninterpretable.

Output: Directed asymmetry index per pair with CI, stim vs omission.

### S12 — Kappa synchrony

Method: Chance-corrected synchrony (κ = (P_S − P_E)/(1 − P_E)) across units, within and across
areas, stim vs omission. Complements S10 for categorical/state-based coordination.

Output: κ per area pair per condition with CI.

## §3 SPK → LFP (spiking as predictor)

### S13 — Spike-triggered LFP average

Method: STA of local and distant LFP triggered on spikes of each response class, stim vs
omission. Critical: STA amplitude scales with spike count — rate-match across conditions
before comparing. Also subtract the condition-average LFP, or the STA will simply recover the
stimulus-evoked potential.

Output: STA waveform per class × source area × target area × condition.

Tests: Synthetic spikes independent of the field must yield a flat STA after correction, at
both high and low rates.

### S14 — Predict laminar LFP from multi-area spiking

Method: Replication of the Nitzan/Buzsáki approach Andre shared (Aug 13): train a model to
reconstruct laminar LFP from distributed multi-area spiking; use attribution to identify which
units disproportionately drive the prediction.

Rationale: This directly addresses the paper's core dissociation — higher-order areas spike,
sensory areas show LFP. If sensory LFP during omission is predictable from higher-order
spiking but not local spiking, that is strong, quantitative top-down evidence and is arguably
the single most compelling analysis available for this manuscript.

Output: Reconstruction accuracy per band and per layer; attribution weight per source area and
unit class.

Acceptance: Report accuracy for high-frequency components too — the original finds these are
poorly predicted. If your model predicts gamma well, suspect leakage before celebrating.

Scope warning: This is the largest single item in either spec. Treat as a stretch goal; do not
let it block Figures 2–7.

## §4 Deferred (2nd paper / SfN — do not build unless asked)

* S15 ANN classification of omitted stimulus identity (A vs B vs R)
* S16 timing-order table across stim, omission, fixation, offset
* S17 pupil/eye-jitter correlation with firing

## §5 Execution order

```
S1  ─────────────────────────► blocks S2,S4,S5,S6,S7,S8,S10,S11 and LFP L11
 ├─ S2, S3, S9
 ├─ S6 ──► validates method ──► S5  ◄── run the control BEFORE trusting the result
 ├─ S4
 ├─ S7, S8
 ├─ S10 ──► S11, S12
 └─ S13, S14 (stretch)
```

Session summary stats (total units, units per area, trial counts, S+/S−/O+ counts per monkey)
fall out of S1 — emit them as a standalone table for Figure 1 and Methods.

Final gate: visually inspect every rendered figure for clipped axes, overlapping labels,
unreadable scales, out-of-frame elements. Do not trust that the code ran — look at the PDF.
