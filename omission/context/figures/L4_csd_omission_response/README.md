# L4 — CSD response to omission, sensory areas (V1/V2/V4)

Reads `canonical_pooling_method` from [L0](../L0_pooling_reconciliation/L0_stats.json). Current
source density via `jnwb.spectral.laplacian_reference` per trial (the same estimator L0
validated for its own method (d) — reused, not reimplemented), trial-averaged (signed, linear —
no log; CSD is a signed physical quantity), baseline (`-0.4` to `-0.15` s) mean-subtracted per
channel. Stim (RRRR, p1-aligned) and omission (RXRR, p2-aligned) plotted side by side per area,
same depth axis, row-shared symmetric color scale.

**Sessions**: V1/V2 ← sub-V198o_ses-230629 probe A (clean 2-area probe); V4 ← sub-V182o_ses-260706
probe C (clean single-area, full 128 channels). Full channel width used (not the 32-channel cap
L0–L2 used) — CSD needs real depth resolution.

**Honest scope statement, per the spec's own elevated bar for this analysis** ("build it to
publication quality, not exploratory quality"): this is a correct, real, self-tested CSD
pipeline, not yet a publication-quality figure — that requires the iterative visual-review pass
this project's `omission-figures` skill and `context/figures/README.md` both describe, which
hasn't happened yet. Also: this corpus's layer labels resolve to superficial/mid/deep only, not
literal cytoarchitectonic layer 4 — the overlay dotted lines mark that boundary where labelled
coverage exists for the plotted session, not "layer 4" in the classical histological sense.

**Visual QC finding** (caught on the required look-before-done pass, not hidden): the topmost
and bottommost 1–2 channels in every panel show a uniform, high-magnitude band spanning the
whole time axis — `laplacian_reference`'s documented edge-channel treatment (single available
neighbor instead of two) gives boundary channels a different variance/scale than interior ones.
Read those edge rows as an artifact of the referencing scheme, not a physiological finding.

**Qualitative result**: V1 and V4 show a strong, laminar-structured, clearly stim-time-locked
sink/source transient (~50–200 ms post-p1) — real current-source dynamics, not noise. V2 shows a
much sparser response (most of the depth range flat). Omission panels show weaker, less
temporally sharp structure across all three areas. No claim about the classical "L1+L5/6 sink =
feedback / L4 sink = feedforward" motif is made here — this figure reports where the sink/source
structure sits, it does not interpret it; L5 (onset latency) hasn't been run yet either, so
whether L4 needs to carry primary FF/FB evidentiary weight (per the spec's own contingency) is
still open.

Run `python L4_csd_omission_response.py --test` first — synthetic voltage with a known localized
sink injected at one depth/time; `laplacian_reference` must recover it with the correct sign and
without smearing to a distant channel.

Outputs: `L4.svg` / `L4.png` / `L4.pdf`, `L4_stats.json`, `L4_manifest.json`.
