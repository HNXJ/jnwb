# Electrophysiological and Behavioral Signal Modalities

This document describes the structured signal streams, recording channels, and electrode configurations in the omission project.

---

## 1. Single-Unit Spiking Activity (SPK / SUA)
Single-unit activity represents the action potentials of isolated individual neurons.
* **Extraction**: Sorted using Kilosort and classified into high-quality single-units vs. multi-unit activity.
* **Quality Metric**: High-quality units (`quality == 1.0` or "good" single units) satisfy strict signal-to-noise ratio (SNR), refractory period violation rates, and trial-by-trial stability criteria.

---

## 2. Multi-Unit Activity (MUA / MUAe)
Multi-unit activity represents the pooled spiking activity of multiple nearby neurons.
* **Extraction**: Indicated by `quality == 0.0` or processed as multi-unit envelope (MUAe) by rectifying and bandpass filtering (300 Hz–3 kHz) high-frequency raw signals.

---

## 3. Local Field Potentials (LFP)
LFPs reflect the aggregate synaptic input and local network oscillations.
* **Sampling Rate**: Resampled to 1000 Hz or 500 Hz for spectral analysis.
* **Verification**: Gated on "Stable-Plus" LFP channels to exclude channels with excessive line noise or impedance drift.

---

## 4. Time-Frequency Representations (TFR)
TFR arrays provide time-resolved power spectral density estimates.
* **Method**: Computed via Multitaper or Wavelet analysis, capturing power across delta/theta (2–8 Hz), alpha (8–14 Hz), beta (15–30 Hz), and gamma (30–80 Hz) bands.
* **Baseline Normalization**: Expressed as decibel (dB) change relative to the pre-stimulus fixation window (`fx`).

---

## 5. Pupil Dynamics & Eye Tracking
* **Pupil Diameter**: Measures autonomic arousal, attention, and surprise during omissions.
* **Saccades / Fixation**: Gated to exclude trials containing eye-movement artifacts.

---

## 6. Electrode Channel Mapping for Dual-Area Probes
Laminar silicon probes often target two distinct cortical regions or layers simultaneously. The canonical probe layout resolves these boundaries as follows:
* **Dual-Area Probe Rule**: 128-channel probes are divided into two equal slices:
  * **Channels 1–64**: Target the first (deepest/lower) area (e.g. Area Y).
  * **Channels 65–128**: Target the second (superficial/upper) area (e.g. Area Z).
* **Canonical Mapping Helper**: `jnwb.addressing.map_peak_channel_to_area` must be used to resolve area boundaries rather than simple string splitting, preventing channel-mislabeling errors.
