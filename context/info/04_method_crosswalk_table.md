# Method crosswalk table

| Source | Signal | Method | Output | Omission adaptation |
|---|---|---|---|---|
| Nitzan 2025 | Spiking | omission PSTH + fit | sorted PSTHs, rasters, slope distributions | use p2/p3/p4-local windows |
| Nitzan 2025 | Spiking | ridge regression / CCA | prediction matrices | subtract PSTH, compare stimulus vs omission |
| Nitzan 2025 | LFP | decoding + CSD | accuracy curves, sink/source plots | test omission decodability and sink/source absence |
| Nitzan 2025 | Spiking/LFP | clustering + connectivity | cluster heatmaps, CCGs | cluster omission motifs and local wiring |
| van Kerkoerle 2014 | MUA/LFP | laminar power + coherence | power spectra, laminar profiles | compare omission to stimulus and baseline |
| van Kerkoerle 2014 | LFP | phase + Granger | directionality plots | test whether omission changes directed coordination |
| Mendoza-Halliday 2024 | LFP | relative power map | spectrolaminar maps | use as layer fingerprint for omission LFP |
| Repo notes | Spiking | SVM + PCA | decoding curves, trajectories | decode identity and omission timing |
| Repo notes | LFP | STFT/wavelets + dB | TFR heatmaps, band traces | omission-local windows and baseline normalization |
| Repo notes | Spiking/LFP | RSA/CKA | RDMs, similarity heatmaps | compare omission, stimulus, delay, all-time |
