# Omission-a evidence architecture and claim gates

Version: 2026-08-09
Status: proposed canonical execution contract; apply after agent verification against the live working tree
Truth status: `truth_safe_unverified` until receipts named below resolve on the implementing machine

## Purpose

This document converts the manuscript story into an auditable dependency graph. It does not replace `context/docs/CONTEXT.md`; it constrains how plans, figures, Labyrinth claims, and manuscript prose may advance.

The protected empirical question is not whether omission has one universal sign. The current repo evidence instead separates four quantities that must not be conflated:

1. **prevalence** — how many units/channels show an effect;
2. **magnitude** — how large the within-site change is;
3. **information** — whether condition/identity/position can be decoded;
4. **mechanism** — what circuit process caused the change.

A broad LFP magnitude effect is not evidence of broad decodable information, and sparse spiking is not evidence of low information content.

## Claim ladder

| Level | Allowed claim | Minimum evidence | Manuscript status |
|---|---|---|---|
| L0 observation | a measured variable changed under a named contrast | deterministic extraction + receipt | factual |
| L1 inference | the change survives the declared inferential hierarchy/null | session-aware model/permutation + correction family | inferential |
| L2 integration | SPK/MUAe/LFP differ systematically in omission response | matched definitions + cross-signal comparison | synthesis |
| L3 interpretation | omission perturbs a predictive cortical state | L0-L2 + controls excluding simpler alternatives | interpretation |
| L4 mechanism | feedback/routing/interneuron process causes the effect | causal intervention or validated mechanistic model | hypothesis unless directly tested |

Stop rule: never promote an L3/L4 sentence because it is narratively consistent with an L0/L1 result.

## Canonical evidence chain

```text
raw NWB / validated derived arrays
  -> session + trial + event ontology
  -> channel/unit addressing
  -> signal-specific preprocessing
  -> analysis parameter manifest
  -> session-level estimate
  -> subject-stratified / design-aware inference
  -> figure stats receipt
  -> Labyrinth claim node
  -> manuscript sentence
```

Every main-text quantitative sentence should be traversable backward through this chain.

## Corpus and ontology gates

- The current live context reports **3 macaques**, 21 NWB sessions, and 23 TFR sessions. Older N=2 source documents are historical inputs, not current corpus truth.
- `nwb.intervals["omission_glo_passive"]` is event-level. Trial construction must use the validated event/trial crosswalk; `stimulus_number` is the stable slot selector.
- Keep p1-relative and omission-relative coordinates explicit. An omission-centered analysis must record the omitted slot and transformation from p1 time.
- Correct trials are the default inclusion set unless a figure explicitly states otherwise.
- SPK/SUA, MUAe, and LFP are separate signal classes and must never be pooled into a generic neural response.

## Addressing gate

For units, require the auditable chain:

```text
unit row/index -> peak/anchor channel -> electrode/probe -> channel-area map -> canonical analysis area
```

Use `jnwb.addressing.map_peak_channel_to_area()` where applicable. Do not infer area from filenames when a channel map exists.

For analog data, filename area tokens are not sufficient because precomputed TFR files may contain the full 128-channel probe array under multiple area labels. Apply the disjoint `channel_area_vector.csv` segmentation before area aggregation.

The equal-half/equal-third segmentation is an anatomical assumption, not a measured boundary. Any area-level anatomical interpretation must state this limitation. V3a/V3d must be pooled to V3 for inference under the current mapping doctrine.

## Spectral gate

Canonical bands are fixed to the current house standard unless the entire affected analysis is refit:

- theta 4-8 Hz
- alpha 8-14 Hz
- beta 14-30 Hz
- low gamma 30-50 Hz
- high gamma 50-80 Hz

Baseline: -250 to -50 ms relative to omission onset, per trial/channel/frequency.

Canonical estimator order for the current TFR products:

```text
raw power -> power/baseline ratio -> aggregate ratios -> 10*log10(aggregate ratio)
```

Do not average dB values for the headline estimator. Any legacy dB-averaged product is superseded unless explicitly used as a sensitivity analysis.

Report both omission windows where relevant: 0..531 ms (omitted slot) and 531..1000 ms (post-omission delay).

## Statistical gate

- The session is the default inferential unit for LFP population claims.
- Subject is stratified/fixed where needed; with three subjects, do not claim a well-identified subject random-effect variance.
- Area and subject are partially/confounded by the recording design; area coefficients require design-aware qualification.
- Benjamini-Hochberg controls FDR, not FWER. Name each correction family.
- Channel-level fits are descriptive/sensitivity analyses unless the dependence structure is explicitly modeled.
- Every classifier must report eligible N, inclusion criteria, null construction, cross-validation grouping, and whether labels can leak through sequence/cycle structure.

## Figure-specific gates

### Figure 3 — unit census

Do not reuse the synthetic census lineage. Recompute S+/S-/O+/O-/X/null from the current three-subject unit table. Record windows, trial minimums, test, effect-size rule, multiplicity correction, and position-stability rule. The headline O+ prevalence remains open until this is done.

### Figure 4 — omission identity decoding

The 2026-08-08 audit supersedes the 2026-08-06 statement that source CSVs do not exist. `_v2` tables exist, but their random-CV estimate is confounded and the cycle-deconfounded result is approximately chance. Do not merely repoint the plotting script and present the v2 0.601 accuracy as the finding.

Acceptance requires:

1. rerun after the p4 label fix with provenance;
2. grouped/cycle-safe CV that prevents sequence-cycle leakage;
3. corpus-scale permutation null (not the n_perm=5 single-session smoke run);
4. no hardcoded scientific values in rendered panels;
5. a stats receipt mapping every panel to its source table and null;
6. headline wording determined from the deconfounded result, even if null.

### Figure 5 — hierarchy/band-power models

Preserve the distinction between descriptive channel-level effects and session-level Model F. Report the V3-vs-V1 result with subject/design qualification and current BH implementation. Do not restore the older synthetic OR/CI lineage.

### Figure 6 — TFR

Use empirical ratio-based products and current bands. Verify area segmentation before averaging. A visual heatmap is descriptive unless its corresponding window/band statistic has a session-level receipt.

### Figure 7 — firing x LFP coupling

Before interpreting coupling as routing, establish the exact statistic and its sampling unit. If spike counts differ between conditions, use matched-count resampling or a count-robust estimator where applicable. Separate association from directionality/causality.

## Labyrinth graph policy for scientific claims

Create graph edges around **evidence dependencies**, not only topic similarity. Recommended relations:

- `derived_from`: result -> data/extraction receipt
- `tested_by`: hypothesis -> analysis/null
- `supports` / `contradicts`: evidence -> claim
- `qualifies`: limitation/control -> claim
- `supersedes`: corrected result -> stale result
- `blocks`: unresolved gate -> figure/manuscript claim

A claim node should carry `scope` (signal, condition, window, area, corpus), `inferential_unit`, `status`, and a concrete receipt. Do not mark a narrative synthesis `confirmed` solely because all paths resolve.

## Acceptance

This contract is adopted when:

1. `CONTEXT.md` links to it as the evidence/claim gate;
2. `REVISION_PLAN.md` reflects the 2026-08-08 Figure 4 correction;
3. the active Labyrinth backlog contains the evidence-consolidation tasks below;
4. a Labyrinth node records this contract and links it to the Figure 4 audit and current context;
5. the graph compiler/validator reports no new dangling targets introduced by these changes.
