# Omission implementation blueprint

## Timing
Use the canonical sequence:
fx, p1, d1, p2, d2, p3, d3, p4, d4.

Omission families:
- p2: AXAB, BXBA, RXRR
- p3: AAXB, BBXA, RRXR
- p4: AAAX, BBBX, RRRX

## Spiking
- Build PSTHs per omission family.
- Use omission time relative to the expected missing slot.
- Compare omission to the preceding delay and the matched stimulus windows.
- Fit linear and sigmoidal models before calling an area ramp-like or step-like.
- Decode identity and omission timing with a linear SVM.
- Use PCA for state-space trajectories.

## LFP / spectral
- Compute TFR on omission-local windows.
- Normalize to a late pre-omission delay baseline.
- Collapse to theta, alpha, beta, low gamma, high gamma.
- Keep trial structure until after normalization.
- Do layer-specific summaries whenever CSD or layer labels exist.

## Spike-field coupling
- Use PPC or matched-spike methods when omission firing is sparse.
- Compare pre-omission, omission, and post-omission windows.
- Control for low spike counts.

## Connectivity / second-order structure
- Ridge regression and CCA for area-to-area interaction.
- RSA/CKA for representational geometry.
- Jitter-corrected CCGs for local wiring.

## Best practice
- One canonical timing map.
- One canonical unit-quality policy.
- One canonical TFR function.
- One canonical omission-family classifier.
- One canonical figure style.
