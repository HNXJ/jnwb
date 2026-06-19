# Paper-by-paper parsing of LFP, spiking, and MUAe methods

## Nitzan & Buzsáki 2025
### Spiking
- Omission-aligned PSTHs, sorted by mean omission z-score.
- Example rasters for omission-positive, omission-negative, and null cells.
- Scatter plots of omission response versus stimulus firing and stimulus latency.
- Linear and sigmoidal fits compared via R².
- Multimodal slope distribution used to separate ramping versus step-like areas.
- Cluster analysis on omission-aligned visual cortex response shapes.

### Cross-area interactions
- Cross-validated ridge regression on residual activity after PSTH subtraction.
- Separate models for stimulus and omission trials.
- Area-by-area prediction matrices and delta-prediction summaries.
- CCA used as a confirmatory analysis.

### Decoding
- Multiclass linear decoding of stimulus identity and omitted stimulus identity.
- Time-resolved accuracy curves around omission.
- LFP decoding from spectral power in short windows.
- CSD used to check whether omission has a real sink/source signature.

### Clustering and connectivity
- k-means clustering of omission and surrounding-stimulus responses.
- Cluster validation with a CNN.
- Spontaneous coupling, spike-triggered population response, local LFP coherence.
- Jitter-corrected CCGs for inferred monosynaptic connectivity.

## van Kerkoerle et al. 2014
### Laminar recordings
- 100 µm spaced laminar probes in V1.
- CSD from checkerboard-evoked responses to anchor depth and layer 4C.
- MUA and LFP recorded through all layers.

### Rhythm analysis
- Power spectra in a 150–350 ms post-stimulus window.
- Figure/background comparison.
- Alpha stronger in deep layers / feedback context.
- Gamma stronger in layer 4 and superficial layers / feedforward context.
- LFP-MUA coherence after subtracting the evoked potential.

### Causal tests
- V1-V4 coherence and phase lead-lag.
- Granger causality by direction.
- Microstimulation and receptor-block experiments.

## Mendoza-Halliday / FLIP-vFLIP
### Spectrolaminar motif
- Relative power spectrum per channel.
- Frequency-by-depth maps.
- Gamma peaks superficially; alpha-beta peaks deeply.
- FLIP / vFLIP for layer identification.
- Image similarity analysis and cross-probe averaging.

### Relevance for omission
- Use this as the laminar fingerprint for omission LFP.
- Align omission TFR to CSD or spectrolaminar anchors.
