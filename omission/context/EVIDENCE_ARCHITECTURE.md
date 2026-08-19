# Evidence architecture — omission

**Status:** canonical execution contract. Supersedes `EVIDENCE_ARCHITECTURE_20260809.md`, whose
content is carried forward here with two repairs (corpus count removed; acceptance conditions
restated). Preserved unedited in the pre-reset archive.

**What this file is:** the semantics of evidence — how a measurement becomes a claim and what
each level of claim costs. It is not a procedure list and contains no corpus counts or paths;
those are observations and live in `PROJECT_STATE.md`.

---

## The four quantities that must not be conflated

1. **prevalence** — how many units/channels show an effect
2. **magnitude** — how large the within-site change is
3. **information** — whether condition/identity/position can be decoded
4. **mechanism** — what circuit process caused the change

A broad LFP magnitude effect is not evidence of broad decodable information. Sparse spiking is
not evidence of low information content.

## Claim ladder

| Level | Allowed claim | Minimum evidence | Manuscript status |
|---|---|---|---|
| **L0** observation | a measured variable changed under a named contrast | deterministic extraction + receipt | factual |
| **L1** inference | the change survives the declared inferential hierarchy/null | design-aware model or permutation + named correction family | inferential |
| **L2** integration | SPK/MUAe/LFP differ systematically in omission response | matched definitions + cross-signal comparison | synthesis |
| **L3** interpretation | omission perturbs a predictive cortical state | L0–L2 + controls excluding simpler alternatives | interpretation |
| **L4** mechanism | a feedback/routing/interneuron process causes the effect | causal intervention or validated mechanistic model | hypothesis unless directly tested |

**Stop rule.** Never promote an L3 or L4 sentence because it is narratively consistent with an
L0 or L1 result. This is the failure this contract exists to prevent.

## Canonical evidence chain

```text
raw NWB / validated derived arrays
  → session + trial + event ontology
  → channel/unit addressing
  → signal-specific preprocessing
  → analysis parameter manifest
  → session-level estimate
  → subject-stratified / design-aware inference
  → figure stats receipt
  → claim node
  → manuscript sentence
```

Every main-text quantitative sentence must be traversable backward through this chain. A break
anywhere in it is a stop condition, not a gap to narrate around.

## Receipts

A receipt names the script that read data and wrote the number, the parameters it ran under,
and where its output lives. A number without a receipt is a hypothesis regardless of how many
documents repeat it. A receipt whose check does not test what it claims is worse than none.

## Graph vocabulary

Edges encode **evidence dependencies**, not topic similarity:

| Relation | Direction |
|---|---|
| `derived_from` | result → data/extraction receipt |
| `tested_by` | hypothesis → analysis/null |
| `supports` / `contradicts` | evidence → claim |
| `qualifies` | limitation/control → claim |
| `supersedes` | corrected result → stale result |
| `blocks` | unresolved gate → figure/manuscript claim |

A claim node carries `scope` (signal, condition, window, area, corpus), `inferential_unit`,
`status`, and a concrete receipt. A narrative synthesis is never `confirmed` merely because all
its paths resolve.

## Stop conditions

Surface rather than resolve:

- an unexplained corpus or inventory mismatch between manifest, readiness table, and filesystem;
- a gate whose inputs contradict its outputs;
- a declared canonical module or path that does not exist;
- a figure whose source table is marked confounded or blocked;
- a pooling operation across a boundary that `PROJECT_STATE.md` marks as an assumption.

## Acceptance

This contract is adopted when:

1. `CLAUDE.md` and `PROJECT_STATE.md` both point to it as the evidence gate;
2. the `labyrinth` skill's relation vocabulary is this file's, not the ACMP metric apparatus;
3. a claim node records this contract and links to the current figure gates;
4. the graph validator reports no dangling targets introduced by the adoption;
5. the harness acceptance tests (`ACCEPTANCE_TESTS.md`) pass.

Until all five hold, this file is `proposed`, and where it conflicts with a receipted result in
`PROJECT_STATE.md`, that file wins.
