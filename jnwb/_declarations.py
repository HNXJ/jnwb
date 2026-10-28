"""Declared signal types of the spike and LFP operations.

Each entry grounds fact I1: the operations that take or return spikes or LFP declare
their input signal class, estimator, output estimand, unit, and time or index base,
so composition edges can be type-checked. Keys are ``module.qualname`` of the public
callable, the same spelling the fact-graph scans use. ``input_class`` holds one or
both of the two signal classes, never pooled into one: an operation taking both,
such as spike-field coupling, declares both.

``base`` follows the operation's time parameterization: ``"seconds"`` for spike
times in seconds, ``"samples at fs Hz"`` where an ``fs`` rate parameter sets the
time scale, ``"samples, 0-based"`` for array layouts with no rate parameter. Every
value below is read from the function's own signature and docstring; where the
docstring does not state the input class or the output unit, the callable is left
out instead of guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet

__all__ = [
    "DECLARATIONS",
    "Declaration",
]


@dataclass(frozen=True)
class Declaration:
    """The declared signal contract of one public operation."""

    input_class: FrozenSet[str]
    estimator: str
    estimand: str
    unit: str
    base: str


#: The declared operations, keyed by ``module.qualname``. A domain callable with no
#: entry here is undeclared, which the signature scan reports; the reason for each
#: omission is recorded in the report, not guessed into this dict.
DECLARATIONS: Dict[str, Declaration] = {
    # "Autocorrelogram of one spike train"; spike_times in seconds; acg histogram.
    "jnwb.analyzers.UnitAnalyzer.autocorrelogram": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="autocorrelogram",
        estimand="binned spike counts",
        unit="counts",
        base="seconds",
    ),
    # "Mean power spectral density over a frequency band"; dB against a baseline when normalized.
    "jnwb.spectral._decibels.band_power": Declaration(
        input_class=frozenset({"lfp"}),
        estimator="Welch band-mean PSD",
        estimand="mean power spectral density, or its ratio to a baseline",
        unit="input-units^2/Hz, or dB with normalize=True",
        base="samples at fs Hz",
    ),
    # "Bridge spike data into the (n_trials, n_bins) contract"; count or spikes/sec.
    "jnwb.connectivity._trials.bin_spikes": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="binned spike counts",
        estimand="per-bin counts or rates",
        unit="counts or spikes/s",
        base="seconds",
    ),
    # "Compute firing rate and spike count metrics"; rates in spikes/sec, counts, latency.
    "jnwb.spiking.compute_response_metrics": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="peri-stimulus response metrics",
        estimand="baseline/response rates, counts and latency",
        unit="spikes/s, counts and s",
        base="seconds",
    ),
    # "Compute frequency-resolved coherence between two LFP signals"; coherence, unitless.
    "jnwb.spectral._coupling.cross_area_coherence": Declaration(
        input_class=frozenset({"lfp"}),
        estimator="Welch magnitude-squared coherence",
        estimand="inter-area coherence",
        unit="unitless",
        base="samples at fs Hz",
    ),
    # "local field potentials in Volts"; output "in A/m^3"; (n_channels, n_times).
    "jnwb.spectral._reference.current_source_density_1d": Declaration(
        input_class=frozenset({"lfp"}),
        estimator="Poisson-equation CSD",
        estimand="current source density",
        unit="A/m^3",
        base="samples, 0-based",
    ),
    # "Fano factor per unit"; variance over mean; window_s in seconds.
    "jnwb.spiking.fano_factor": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="Fano factor",
        estimand="across-trial count variance over mean",
        unit="unitless",
        base="seconds",
    ),
    # "Input class: one unit's spike times in seconds"; coefficient of variation.
    "jnwb.unit_quality.isi_cv": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="coefficient of variation",
        estimand="ISI variability",
        unit="unitless",
        base="seconds",
    ),
    # "Fraction of spikes inside network bursts"; window_s in seconds.
    "jnwb.spiking.network_burst_index": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="burst fraction",
        estimand="fraction of spikes inside network bursts",
        unit="fraction",
        base="seconds",
    ),
    # Spike times in seconds with LFP phase in radians at LFP timestamps in seconds.
    "jnwb.spiking.phase_locking_index": Declaration(
        input_class=frozenset({"lfp", "spikes"}),
        estimator="circular phase histogram with Rayleigh test",
        estimand="spike-phase coupling",
        unit="unitless with counts and radians",
        base="seconds",
    ),
    # "Input class: one unit's spike times in seconds"; "Unitless, between 0 and 1".
    "jnwb.unit_quality.presence_ratio": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="presence ratio",
        estimand="fraction of blocks holding a spike",
        unit="unitless fraction",
        base="seconds",
    ),
    # "Input class: one unit's spike times in seconds"; "unitless, between 0 and 1/2".
    "jnwb.unit_quality.refractory_contamination": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="Hill contamination estimate",
        estimand="fraction of spikes from a contaminating source",
        unit="unitless",
        base="seconds",
    ),
    # "Mean pairwise Pearson correlation of binned spike counts"; window_s in seconds.
    "jnwb.spiking.spike_count_correlation": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="mean pairwise Pearson correlation",
        estimand="binned spike-count correlation",
        unit="unitless",
        base="seconds",
    ),
    # "Spike times of unit 1 (seconds)"; "Mutual Information (MI) in bits".
    "jnwb.connectivity._information.spike_mutual_information": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="plug-in discrete mutual information",
        estimand="mutual information between binned trains",
        unit="bits",
        base="seconds",
    ),
    # "extracellular potential"; "Curvature array in V/m^2"; (n_channels, n_times).
    "jnwb.spectral._reference.voltage_curvature_1d": Declaration(
        input_class=frozenset({"lfp"}),
        estimator="three-point second difference",
        estimand="spatial voltage curvature",
        unit="V/m^2",
        base="samples, 0-based",
    ),
    # "Input class: the unit's individual spike waveforms"; "The SNR as a float".
    "jnwb.unit_quality.waveform_snr": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="signal-to-noise ratio",
        estimand="single-unit isolation on one channel",
        unit="unitless ratio",
        base="samples, 0-based",
    ),
    # Spike times in seconds; per-trial histogram divided by the bin width in seconds.
    "jnwb.analyzers.UnitAnalyzer.psth": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="peristimulus time histogram with bootstrap CI",
        estimand="trial-averaged firing rate",
        unit="spikes/s",
        base="seconds",
    ),
    # Spike times in seconds; ISI, refractory violations and a Fano factor over 1-s windows.
    "jnwb.analyzers.UnitAnalyzer.quality_metrics": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="ISI, refractory-violation and Fano-factor metrics",
        estimand="single-unit quality",
        unit="percent, unitless and s",
        base="seconds",
    ),
    # Spike times in seconds; each trial's spikes minus its onset, in seconds.
    "jnwb.analyzers.UnitAnalyzer.raster": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="onset-aligned spike times",
        estimand="per-trial spike times relative to onset",
        unit="s",
        base="seconds",
    ),
    # Two spike trains in seconds; discrete MI of binned occupancy, no bias correction.
    "jnwb.connectivity._information.binary_occupancy_mutual_information": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="plug-in discrete mutual information on binned occupancy",
        estimand="mutual information between binned trains",
        unit="bits",
        base="seconds",
    ),
    # Two spike trains in seconds; discrete MI of per-bin counts, no bias correction.
    "jnwb.connectivity._information.spike_count_mutual_information": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="plug-in discrete mutual information on per-bin counts",
        estimand="mutual information between binned trains",
        unit="bits",
        base="seconds",
    ),
    # Spike times in seconds and acquisition ticks; returns the tick-to-seconds map.
    "jnwb.continuous.derive_tick_clock": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="tick span over spike span",
        estimand="map from acquisition ticks to spike-clock seconds",
        unit="ticks/s and s",
        base="seconds",
    ),
    # (n_channels, n_times) LFP voltage at fs Hz; Welch PSD, then vflip.
    "jnwb.laminar._vflip.vflip_from_lfp": Declaration(
        input_class=frozenset({"lfp"}),
        estimator="Welch PSD then vFLIP band-ratio crossover",
        estimand="laminar crossover contact",
        unit="contact index and um",
        base="samples at fs Hz",
    ),
    # (n_channels, n_samples) continuous voltage at fs Hz; Hanning PSD, then vflip2.
    "jnwb.laminar._vflip2.vflip2_from_lfp": Declaration(
        input_class=frozenset({"lfp"}),
        estimator="vFLIP2.m Hanning PSD then vFLIP2 fit",
        estimand="laminar crossover depth",
        unit="mm and contact index",
        base="samples at fs Hz",
    ),
    # (n_channels, n_times) LFP at fs Hz; phase slopes across ordered contacts.
    "jnwb.laminar._zflip.zflip": Declaration(
        input_class=frozenset({"lfp"}),
        estimator="cross-spectral phase slope with wPLI and surrogate gates",
        estimand="depth phase gradient and apparent delay",
        unit="radians/Hz, s and m/s",
        base="samples at fs Hz",
    ),
    # Laminar LFP at fs Hz; bad contacts, anchor and compartment labels.
    "jnwb.laminar_curation.curate_and_label": Declaration(
        input_class=frozenset({"lfp"}),
        estimator="bad-contact curation, vFLIP anchor and graded fusion",
        estimand="per-contact cortical compartment labels",
        unit="labels, grade and um",
        base="samples at fs Hz",
    ),
    # "Welch power spectral density of a plain LFP array"; fs in Hz.
    "jnwb.spectral._psd.compute_psd": Declaration(
        input_class=frozenset({"lfp"}),
        estimator="Welch PSD",
        estimand="power spectral density",
        unit="input-units^2/Hz",
        base="samples at fs Hz",
    ),
    # "Decompose LFP trace into fundamental and harmonic components"; fs in Hz.
    "jnwb.spectral._psd.harmonic_analysis": Declaration(
        input_class=frozenset({"lfp"}),
        estimator="Welch PSD peak and harmonic tracking",
        estimand="fundamental frequency and harmonic powers",
        unit="Hz and input-units^2/Hz",
        base="samples at fs Hz",
    ),
    # "Fit 1/f spectral tilt via linear regression of log10 power versus log10 frequency".
    "jnwb.spectral._psd.spectral_tilt": Declaration(
        input_class=frozenset({"lfp"}),
        estimator="log-log linear regression of the Welch PSD",
        estimand="aperiodic spectral slope",
        unit="unitless slope",
        base="samples at fs Hz",
    ),
    # Sorted spike times in seconds; one boolean per onset for a window in ms.
    "jnwb.statistics._firing.fire_indicator": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="spike presence in a window",
        estimand="whether a unit fired after each onset",
        unit="boolean",
        base="seconds",
    ),
    # Sorted spike times in seconds; True iff a spike falls in the window.
    "jnwb.statistics._firing.fires_in_window": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="spike presence in a window",
        estimand="whether a unit fired after one onset",
        unit="boolean",
        base="seconds",
    ),
    # "Firing rate (Hz)" in a window after an onset; sorted spike times in seconds.
    "jnwb.statistics._firing.rate_in_window": Declaration(
        input_class=frozenset({"spikes"}),
        estimator="spike count over window width",
        estimand="firing rate in one window",
        unit="Hz",
        base="seconds",
    ),
    # A TFR-derived series against a spike-count series, both reduced to 1D.
    "jnwb.statistics._regression.cross_modal_comparison": Declaration(
        input_class=frozenset({"lfp", "spikes"}),
        estimator="lagged correlation with a circular-shift null",
        estimand="correlation between a TFR-derived series and a spike-count series",
        unit="unitless r and p",
        base="samples, 0-based",
    ),
    # Bivariate Granger causality; the statistic is a log variance ratio (nats); no rate parameter.
    "jnwb.connectivity._granger.granger_causality": Declaration(
        input_class=frozenset({"spikes", "lfp"}),
        estimator="bivariate VAR log variance ratio (Granger 1969)",
        estimand="Granger statistic in each direction",
        unit="nats",
        base="samples, 0-based",
    ),
    # All-pairs directed estimators; the unit follows the chosen method, q-values are unitless.
    "jnwb.connectivity._network.directed_network": Declaration(
        input_class=frozenset({"spikes", "lfp"}),
        estimator="all-pairs directed estimators with Benjamini-Hochberg FDR",
        estimand="directed influence matrix with p- and q-values per ordered pair",
        unit="method-dependent; q-values unitless",
        base="method-dependent: samples at fs Hz (psi), samples, 0-based (granger)",
    ),
    # Imaginary part of coherency (Nolte et al. 2004); a ratio of spectra, so unitless; fs in Hz.
    "jnwb.spectral._coupling.imaginary_coherency": Declaration(
        input_class=frozenset({"spikes", "lfp"}),
        estimator="Welch cross-spectrum, imaginary part of coherency (Nolte et al. 2004)",
        estimand="signed and absolute band means of Im(coherency), and mean coherence",
        unit="unitless",
        base="samples at fs Hz",
    ),
}
