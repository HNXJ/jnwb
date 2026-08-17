Version: 2026-08-10
Status: Stage 4A.1 gate receipt
Truth status: `truth_safe_verified_against_receipt`

# Handout 4A.1 — Data access and tensor alignment

This directory records the data-access gate between the Stage 4A design audit and any
Stage 4B decoding. The audit performs no classifier fitting, permutation testing, or model
training.

## 1. Results

- The TFR state is `READINESS_STALE+PRODUCTS_PARTIAL`: the canonical live directory contains
  four arrays, while the 2026-07-26 readiness table reports 792. The old
  `D:/workspace/data/tfr_arrays` path is absent.
- Raw LFP is independently usable for a time-domain Stage 4B path. TFR-backed LFP features
  remain excluded until their provenance is repaired or a new manifest is supplied.
- `jnwb.load_muae_epochs` is the first-class MUAe accessor. It returns
  `(trial, channel, time)` data and preserves deterministic `trial_id` joins, channel/area
  metadata, sampling rate, units, time vector, source paths, and preprocessing state.
- A real-session QC sample from SUA, LFP, and MUAe uses the same omission-relative time vector
  for p2, p3, and p4. In the sample, local `t=0` is sample 10 of a 20-sample window.

## 2. Machine-readable outputs

- `stage4a1_receipt.json` — complete gate receipt, hashes, commands, exclusions, and readiness.
- `tfr_provenance_trace.json` — readiness, generator, live filesystem, and raw-NWB trace.
- `alignment_qc_records.csv` — one record for each signal × p2/p3/p4 QC extraction.
- `alignment_qc_sample.npz` — small materialized QC tensors only; no corpus decoding tensors.
- `tensor_alignment_receipt.json` — canonical offset and no-absolute-time contract checks.

## 3. Scope and stop rule

The QC covers one real session and one area. It validates access and coordinate contracts; it
does not establish corpus-level information content. Stage 4A.1 stops before Stage 4B decoding.
The receipt keeps `TFR_BACKED_LFP_READY=false` while allowing review of the raw-LFP,
MUAe, and SUA gates independently.
