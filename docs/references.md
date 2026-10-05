# References

Published sources for the methods jnwb implements. Each row names the result jnwb implements and
the functions that implement it, and each of those functions cites the same DOI in its docstring;
a test holds the two to each other. Every DOI below resolved at doi.org on 2026-09-23 (Lütkepohl
2005 on 2026-09-25, Przyborowski and Wilenski 1940 on 2026-09-26, the unit-quality sources and
the papers by Bastos, Vezoli, Friston, Barnett and their coauthors on 2026-10-04). Each matched
the title, authors and year of its Crossref record, except the arXiv entry, matched to its
DataCite record, and Llobet et al. 2022, matched to bioRxiv's record of its version 1. Where
jnwb departs from the published result, the row and the docstring say how. The
[Pitfalls](#pitfalls) table lists papers that state a pitfall rather than a method jnwb
implements; the functions it names are those the pitfall concerns, and their docstrings do not
cite it.

## Signal processing

Filtering, convolution, sampling, the discrete Fourier transform and windowing follow the
treatment in these two books, checked on Open Library:

- Oppenheim, A. V., & Willsky, A. S. *Signals and Systems*. First published 1983.
- Oppenheim, A. V., & Schafer, R. W. *Discrete-Time Signal Processing*. ISBN 978-0-13-198842-2.

| Reference | Result implemented | Functions |
|---|---|---|
| Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power spectra: a method based on time averaging over short, modified periodograms. *IEEE Transactions on Audio and Electroacoustics* 15(2), 70-73. [doi:10.1109/TAU.1967.1161901](https://doi.org/10.1109/TAU.1967.1161901) | The spectrum as the average of windowed periodograms over overlapping segments | `compute_psd`, `band_power`, `spectral_tilt`, `harmonic_analysis`, `imaginary_coherency`, `cross_area_coherence`, `vflip_from_lfp` |
| Thomson, D. J. (1982). Spectrum estimation and harmonic analysis. *Proceedings of the IEEE* 70(9), 1055-1096. [doi:10.1109/PROC.1982.12433](https://doi.org/10.1109/PROC.1982.12433) | The multitaper estimate: periodograms under orthogonal Slepian (DPSS) tapers, combined across tapers. jnwb averages the K eigenspectra with equal weight | `compute_multitaper_psd` |
| Torrence, C., & Compo, G. P. (1998). A practical guide to wavelet analysis. *Bulletin of the American Meteorological Society* 79(1), 61-78. [doi:10.1175/1520-0477(1998)079<0061:APGTWA>2.0.CO;2](https://doi.org/10.1175/1520-0477(1998)079%3C0061:APGTWA%3E2.0.CO;2) | The Morlet wavelet (section 3b, eq. 1), unit-energy normalization (section 3c, eq. 6; `normalization='energy'`) and the cone of influence (section 3g). The paper draws the cone at the e-folding time $\sqrt{2}\,s$ (Table 1); jnwb's default masks every sample the kernel's zero padding reaches, which is wider, and `coi_sigma=np.sqrt(2)` gives the paper's cone | `complex_tfr`, `morlet_wavelet` |
| Donoghue, T., et al. (2020). Parameterizing neural power spectra into periodic and aperiodic components. *Nature Neuroscience* 23(12), 1655-1665. [doi:10.1038/s41593-020-00744-x](https://doi.org/10.1038/s41593-020-00744-x) | The aperiodic component of Methods eq. 3 (offset $b$, knee $k$, exponent $\chi$); the fixed mode is $k = 0$. jnwb fits it to every bin in the range and does not first remove periodic peaks, as the paper's algorithm does | `aperiodic_fit` |

## Laminar analysis

| Reference | Result implemented | Functions |
|---|---|---|
| Mendoza-Halliday, D., et al. (2024). A ubiquitous spectrolaminar motif of local field potential power across the primate cortex. *Nature Neuroscience* 27(3), 547-560. [doi:10.1038/s41593-023-01554-7](https://doi.org/10.1038/s41593-023-01554-7) | The spectrolaminar motif: gamma relative power peaks in superficial channels, alpha-beta in deep ones, and their crossover marks layer 4. `vflip` tests for that motif; it is not the paper's FLIP or vFLIP procedure, which normalizes by the channel of highest power, fits regressions over a channel range chosen by goodness of fit and, for vFLIP, searches over band pairs | `vflip_from_lfp`, `label_layers` |
| Bastos, A. M., et al. (2018). Laminar recordings in frontal cortex suggest distinct layers for maintenance and control of working memory. *PNAS* 115(5), 1117-1122. [doi:10.1073/pnas.1710323115](https://doi.org/10.1073/pnas.1710323115) | Results, first section, and Fig. 2B: power at each frequency relative to the other contacts, averaged into a low-band (4-22 Hz) and a high-band (58-260 Hz) depth profile, whose crossover lies near the first current source density sink. The paper divides by the largest power across contacts; `vflip` also subtracts the smallest, uses 8-30 Hz and 50-150 Hz by default and rescales each profile before finding the crossing | `vflip_from_lfp` |
| Bastos, A. M., et al. (2021). Neural effects of propofol-induced unconsciousness and its reversal using thalamic stimulation. *eLife* 10, e60824. [doi:10.7554/eLife.60824](https://doi.org/10.7554/eLife.60824) | Materials and methods, "Neural recordings in cortex": the crossover of the gamma and alpha-beta relative power profiles as the estimate of layer 4. The paper gives no normalization for it beyond citing Bastos et al. (2018) and describes no acceptance test; `vflip` rejects a fit whose support score is below `min_support_score` | `vflip_from_lfp` |
| Nicholson, C., & Freeman, J. A. (1975). Theory of current source-density analysis and determination of conductivity tensor for anuran cerebellum. *Journal of Neurophysiology* 38(2), 356-368. [doi:10.1152/jn.1975.38.2.356](https://doi.org/10.1152/jn.1975.38.2.356) | Current source density $-\sigma\,\partial^2\phi/\partial z^2$ in one dimension with homogeneous conductivity, by the three-point second difference. `voltage_curvature_1d` is the difference without $\sigma$ | `current_source_density_1d`, `voltage_curvature_1d` |

## Coherence and phase

| Reference | Result implemented | Functions |
|---|---|---|
| Nolte, G., et al. (2004). Identifying true brain interaction from EEG data using the imaginary part of coherency. *Clinical Neurophysiology* 115(10), 2292-2307. [doi:10.1016/j.clinph.2004.04.029](https://doi.org/10.1016/j.clinph.2004.04.029) | The imaginary part of coherency, on the cross-spectrum `E[X conj(Y)]`, the conjugate of what `scipy.signal.csd` returns. A lead of `x` over `y` gives a positive value, the convention `phase_slope_index` uses | `imaginary_coherency` |
| Vinck, M., et al. (2011). An improved index of phase-synchronization for electrophysiological data in the presence of volume-conduction, noise and sample-size bias. *NeuroImage* 55(4), 1548-1565. [doi:10.1016/j.neuroimage.2011.01.055](https://doi.org/10.1016/j.neuroimage.2011.01.055) | The weighted phase lag index $\lvert \sum \mathrm{Im}\,S \rvert / \sum \lvert \mathrm{Im}\,S \rvert$ over segment cross-spectra $S$, and the debiased estimator of squared wPLI | `wpli`, `zflip` |
| Vinck, M., et al. (2010). The pairwise phase consistency: a bias-free measure of rhythmic neuronal synchronization. *NeuroImage* 51(1), 112-122. [doi:10.1016/j.neuroimage.2010.01.073](https://doi.org/10.1016/j.neuroimage.2010.01.073) | The pairwise phase consistency, the mean cosine of all pairwise phase differences, computed through the resultant as $(\lvert \sum e^{i\theta} \rvert^2 - N) / (N(N-1))$ | `pairwise_phase_consistency` |
| Bastos, A. M., et al. (2020). Layer and rhythm specificity for predictive routing. *PNAS* 117(49), 31459-31469. [doi:10.1073/pnas.2014868117](https://doi.org/10.1073/pnas.2014868117) | Experimental Procedures, "Local Field Potential Power, Coherence, and Granger Causality Analysis": sample-by-sample bipolar differences taken before coherence and Granger causality, because a common reference can make both spurious. The paper subtracts contacts 400 µm apart, `bipolar_reference` adjacent contacts. Its Granger causality is the nonparametric estimate from the multitaper cross-spectral matrix, which jnwb does not implement; `granger_spectral` fits a VAR | `bipolar_reference` |

## Directed connectivity

| Reference | Result implemented | Functions |
|---|---|---|
| Granger, C. W. J. (1969). Investigating causal relations by econometric models and cross-spectral methods. *Econometrica* 37(3), 424. [doi:10.2307/1912791](https://doi.org/10.2307/1912791) | Granger causality: X Granger-predicts Y when the past of X improves the prediction of Y beyond the past of Y, a temporal-lag asymmetry rather than a causal effect | `granger`, `granger_causality` |
| Geweke, J. (1982). Measurement of linear dependence and feedback between multiple time series. *Journal of the American Statistical Association* 77(378), 304-313. [doi:10.1080/01621459.1982.10477803](https://doi.org/10.1080/01621459.1982.10477803) | The measure of linear feedback, the log ratio of restricted to unrestricted residual variance, and its frequency decomposition through the transfer function of the fitted VAR | `granger`, `granger_spectral` |
| Geweke, J. F. (1984). Measures of conditional linear dependence and feedback between time series. *Journal of the American Statistical Association* 79(388), 907-915. [doi:10.1080/01621459.1984.10477110](https://doi.org/10.1080/01621459.1984.10477110) | The conditional measure: the past of Z enters both the restricted and the unrestricted model (`Z=`) | `granger` |
| Lütkepohl, H. (2005). *New Introduction to Multiple Time Series Analysis*. Springer. [doi:10.1007/978-3-540-27752-1](https://doi.org/10.1007/978-3-540-27752-1) | VAR order selection (section 4.3): AIC, HQ and SC from the maximum-likelihood residual variance, every candidate order fitted to the same sample. jnwb scores the equation of the predicted signal rather than the full residual covariance | `granger` |
| Nolte, G., et al. (2008). Robustly estimating the flow direction of information in complex physical systems. *Physical Review Letters* 100(23), 234101. [doi:10.1103/PhysRevLett.100.234101](https://doi.org/10.1103/PhysRevLett.100.234101) | The phase slope index, eq. 3, on the coherency of eq. 4 with the cross-spectrum of eq. 2; positive means X leads Y. `z` is the normalization of eq. 6. The paper's jackknife leaves out one epoch at a time; jnwb's leaves out one Welch segment | `phase_slope_index` |
| Schreiber, T. (2000). Measuring information transfer. *Physical Review Letters* 85(2), 461-464. [doi:10.1103/PhysRevLett.85.461](https://doi.org/10.1103/PhysRevLett.85.461) | Transfer entropy, eq. 4, with target history `k` and source history `l` | `transfer_entropy` |
| Marschinski, R., & Kantz, H. (2002). *The European Physical Journal B* 30(2), 275-281. [doi:10.1140/epjb/e2002-00379-2](https://doi.org/10.1140/epjb/e2002-00379-2) | Effective transfer entropy: the raw value minus the mean over surrogates (`bias_corrected_*`). jnwb's surrogates permute trials or circularly shift the source, keeping its autocorrelation | `transfer_entropy` |

## Statistics

| Reference | Result implemented | Functions |
|---|---|---|
| Maris, E., & Oostenveld, R. (2007). Nonparametric statistical testing of EEG- and MEG-data. *Journal of Neuroscience Methods* 164(1), 177-190. [doi:10.1016/j.jneumeth.2007.03.024](https://doi.org/10.1016/j.jneumeth.2007.03.024) | The cluster-based permutation test: clusters of adjacent points above a threshold, the sum of $t$ within each cluster as its statistic, and significance against the permutation distribution of the largest cluster statistic | `cluster_permutation_test` |
| Phipson, B., & Smyth, G. K. (2010). Permutation p-values should never be zero: calculating exact p-values when permutations are randomly drawn. *Statistical Applications in Genetics and Molecular Biology* 9(1). [doi:10.2202/1544-6115.1585](https://doi.org/10.2202/1544-6115.1585) | The Monte Carlo p-value $(1 + b) / (B + 1)$ over $B$ random permutations | `cluster_permutation_test` |
| Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: a practical and powerful approach to multiple testing. *Journal of the Royal Statistical Society Series B* 57(1), 289-300. [doi:10.1111/j.2517-6161.1995.tb02031.x](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x) | The step-up procedure, returned as adjusted p-values (`method='bh'`, through `scipy.stats.false_discovery_control`) | `fdr_correct`, `StatisticalAnalysis.fdr_correct`, `directed_network` |
| Benjamini, Y., & Yekutieli, D. (2001). The control of the false discovery rate in multiple testing under dependency. *The Annals of Statistics* 29(4). [doi:10.1214/aos/1013699998](https://doi.org/10.1214/aos/1013699998) | The step-up procedure under arbitrary dependence (`method='by'`) | `fdr_correct`, `StatisticalAnalysis.fdr_correct`, `directed_network` |
| Przyborowski, J., & Wilenski, H. (1940). Homogeneity of results in testing samples from Poisson series: with an application to testing clover seed for dodder. *Biometrika* 31(3/4), 313-323. [doi:10.2307/2332612](https://doi.org/10.2307/2332612) | The conditional test of two Poisson counts: given their total $N$, the first is Binomial($N$, $d_r/(d_r+d_b)$) under equal rates, with $d_r$, $d_b$ the exposures. jnwb sums counts and window durations over trials and takes the two-sided p from `scipy.stats.binomtest` | `classify_response_significance` |
| Clopper, C. J., & Pearson, E. S. (1934). The use of confidence or fiducial limits illustrated in the case of the binomial. *Biometrika* 26(4), 404-413. [doi:10.1093/biomet/26.4.404](https://doi.org/10.1093/biomet/26.4.404) | The exact binomial confidence interval, computed from Beta quantiles | `clopper_pearson` |

## Spiking population measures

| Reference | Result implemented | Functions |
|---|---|---|
| Fleiss, J. L. (1971). Measuring nominal scale agreement among many raters. *Psychological Bulletin* 76(5), 378-382. [doi:10.1037/h0031619](https://doi.org/10.1037/h0031619) | Kappa for many raters, $(\bar P - P_e) / (1 - P_e)$ over a table of rater counts per item and category; the paper's 30-patient, six-rater table gives .430 | `fleiss_kappa` |
| Cohen, M. R., & Kohn, A. (2011). Measuring and interpreting neuronal correlations. *Nature Neuroscience* 14(7), 811-819. [doi:10.1038/nn.2842](https://doi.org/10.1038/nn.2842) | The spike-count correlation, the Pearson r of two units' spike counts, whose value depends on the counting window. The paper's $r_{sc}$ is taken across trials; `spike_count_correlation` takes it across time bins of one window, so shared rate changes (signal correlation) raise it too | `spike_count_correlation` |
| Churchland, M. M., et al. (2010). Stimulus onset quenches neural variability: a widespread cortical phenomenon. *Nature Neuroscience* 13(3), 369-378. [doi:10.1038/nn.2501](https://doi.org/10.1038/nn.2501) | The Fano factor per unit, the across-trial variance over the mean of the count in a fixed window, summarised over units | `fano_factor` |
| Wagenaar, D. A., Pine, J., & Potter, S. M. (2006). An extremely rich repertoire of bursting patterns during the development of cortical cultures. *BMC Neuroscience* 7, 11. [doi:10.1186/1471-2202-7-11](https://doi.org/10.1186/1471-2202-7-11) | Network bursts as periods of elevated population activity; jnwb detects them as runs of population rate at or above a threshold for at least a minimum duration and reports the fraction of spikes inside them | `network_burst_index` |

## Unit quality

`waveform_flatness` and `spatial_derivative_sharpness` have no published source; their
thresholds are the caller's.

| Reference | Result implemented | Functions |
|---|---|---|
| Siegle, J. H., et al. (2021). Survey of spiking in the mouse visual system reveals functional hierarchy. *Nature* 592(7852), 86-92. [doi:10.1038/s41586-020-03171-x](https://doi.org/10.1038/s41586-020-03171-x) | Methods, unit quality metrics: the peak channel as the channel of maximum amplitude (peak minus trough); waveform duration as the difference in time between its peak and trough, which the code behind the paper (`calculate_waveform_duration` in `ecephys_spike_sorting`) takes from the larger extremum to the opposite one after it, as `waveform_features` does; SNR as the amplitude over twice the standard deviation of the residual waveforms; presence ratio as the fraction of blocks holding a spike. The paper used 100 equal blocks; `presence_ratio` takes the caller's | `waveform_features`, `waveform_snr`, `presence_ratio` |
| Jia, X., et al. (2019). High-density extracellular probes reveal dendritic backpropagation and facilitate neuron classification. *Journal of Neurophysiology* 121(5), 1831-1847. [doi:10.1152/jn.00680.2018](https://doi.org/10.1152/jn.00680.2018) | The peak-to-trough ratio, the amplitude of the peak over that of the trough, on the channel of largest amplitude | `waveform_features` |
| Shinomoto, S., et al. (2009). Relating neuronal firing patterns to functional differentiation of cerebral cortex. *PLoS Computational Biology* 5(7), e1000433. [doi:10.1371/journal.pcbi.1000433](https://doi.org/10.1371/journal.pcbi.1000433) | The coefficient of variation of the inter-spike intervals, their standard deviation over their mean (eq. 1); jnwb takes the unbiased (`ddof=1`) standard deviation, the variance rule of `fano_factor` | `isi_cv` |
| Hill, D. N., Mehta, S. B., & Kleinfeld, D. (2011). Quality metrics to accompany spike sorting of extracellular signals. *Journal of Neuroscience* 31(24), 8699-8705. [doi:10.1523/JNEUROSCI.0971-11.2011](https://doi.org/10.1523/JNEUROSCI.0971-11.2011) | The fraction $f$ of a unit's spikes from a contaminating source, the smaller root of $r = 2(\tau_R - \tau_C) N^2 (1 - f) f / T$, with $r$ the number of consecutive inter-spike intervals shorter than the refractory period $\tau_R$, $\tau_C$ the censored period, $N$ the spike count and $T$ the recording duration | `refractory_contamination` |
| Llobet, V., Wyngaard, A., & Barbour, B. (2022). Automatic post-processing and merging of multiple spike-sorting analyses with Lussac. *bioRxiv* preprint, version 1. [doi:10.1101/2022.02.08.479192](https://doi.org/10.1101/2022.02.08.479192) | A derivation of the Hill et al. (2011) estimate (eqs. 1 and 4), cited as the derivation only; jnwb computes the estimate as Hill et al. write it, with the plain recording duration | `refractory_contamination` |

## Representational analysis

| Reference | Result implemented | Functions |
|---|---|---|
| Kriegeskorte, N., et al. (2008). Representational similarity analysis: connecting the branches of systems neuroscience. *Frontiers in Systems Neuroscience* 2, 4. [doi:10.3389/neuro.06.004.2008](https://doi.org/10.3389/neuro.06.004.2008) | Dissimilarity matrices of correlation distance ("Step 2"), compared by Spearman rank correlation ("Step 4"); their relatedness is tested by permuting condition labels ("Step 5") | `rdm`, `rdm_similarity`, `jrsa` |
| Gretton, A., et al. (2005). Measuring statistical dependence with Hilbert-Schmidt norms. *Lecture Notes in Computer Science*, 63-77. [doi:10.1007/11564089_7](https://doi.org/10.1007/11564089_7) | The empirical HSIC $(m-1)^{-2}\,\mathrm{tr}(KHLH)$, Definition 2, eq. 9, with a Gaussian kernel (`metric='hsic'`) | `jrsa` |
| Kornblith, S., et al. (2019). Similarity of neural network representations revisited. arXiv:1905.00414. [doi:10.48550/arXiv.1905.00414](https://doi.org/10.48550/arXiv.1905.00414) | Linear CKA $\lVert Y^\top X \rVert_F^2 / (\lVert X^\top X \rVert_F \lVert Y^\top Y \rVert_F)$ on column-centered $X$ and $Y$ (Table 1; CKA is eq. 4) (`metric='cka'`) | `jrsa` |
| Robert, P., & Escoufier, Y. (1976). A unifying tool for linear multivariate statistical methods: the RV-coefficient. *Applied Statistics* 25(3), 257. [doi:10.2307/2347233](https://doi.org/10.2307/2347233) | The RV coefficient (`metric='rv'`). On column-centered data it equals linear CKA, as Kornblith et al. (2019) note in section 3, and jnwb computes both by one formula | `jrsa` |
| Székely, G. J., Rizzo, M. L., & Bakirov, N. K. (2007). Measuring and testing dependence by correlation of distances. *The Annals of Statistics* 35(6). [doi:10.1214/009053607000000505](https://doi.org/10.1214/009053607000000505) | The empirical distance correlation, Definitions 4 and 5, eqs. 2.8-2.10 (`metric='distance_correlation'`). Where the paper sets it to 0 for a constant sample, jnwb returns NaN | `jrsa` |

## Pitfalls

| Reference | Pitfall stated | Functions it concerns |
|---|---|---|
| Bastos, A. M., & Schoffelen, J.-M. (2016). A tutorial review of functional connectivity analysis methods and their interpretational pitfalls. *Frontiers in Systems Neuroscience* 9, 175. [doi:10.3389/fnsys.2015.00175](https://doi.org/10.3389/fnsys.2015.00175) | Five problems, one section each. A common reference adds zero-lag coherence between channels that share it; bipolar derivation removes it. Field spread makes coherence spurious at zero lag; re-referencing, contrasts between conditions and metrics that discard zero-lag interaction reduce it, and each can still mislead. A difference in signal-to-noise ratio between channels creates a Granger asymmetry with no true direction. Common input from an unrecorded source couples two signals; partial coherence and multivariate Granger causality need that source recorded. Coherence, PLV and Granger causality are biased upward by few observations; PPC is not | `bipolar_reference`, `cross_area_coherence`, `imaginary_coherency`, `wpli`, `phase_slope_index`, `pairwise_phase_consistency`, `granger`, `granger_spectral` |
| Vezoli, J., et al. (2021). Brain rhythms define distinct interaction networks with differential dependence on anatomy. *Neuron* 109(23), 3862-3878.e5. [doi:10.1016/j.neuron.2021.09.052](https://doi.org/10.1016/j.neuron.2021.09.052) | STAR Methods, "Quantification and statistical analysis": coherence, power correlation and Granger causality count as significant only above a bias level estimated by randomly pairing epochs, taking the maximum over site pairs. Results, "Different rhythms define distinct FC networks": sites within 2 mm of each other are left out of a site's coherence strength, to avoid residual volume conduction. `cross_area_coherence` builds its null by circular shifts instead, and the paper's Granger causality is nonparametric, which jnwb does not implement | `cross_area_coherence`, `granger_spectral` |
| Friston, K. J., et al. (2014). Granger causality revisited. *NeuroImage* 101, 796-808. [doi:10.1016/j.neuroimage.2014.06.062](https://doi.org/10.1016/j.neuroimage.2014.06.062) | "The effects of dynamical instability and measurement noise": near instability, slowly decaying modes make a finite-order VAR fail and spectral Granger causality unreliable; measurement noise makes both the VAR and the nonparametric estimate fail, weakening the forward influence and creating a backward one | `granger`, `granger_spectral` |
| Barnett, L., & Seth, A. K. (2011). Behaviour of Granger causality under filtering: theoretical invariance and practical application. *Journal of Neuroscience Methods* 201(2), 404-419. [doi:10.1016/j.jneumeth.2011.08.010](https://doi.org/10.1016/j.jneumeth.2011.08.010) | From the abstract: Granger causality of a stationary VAR process is invariant under any invertible filter, so band-pass filtering cannot isolate a band's Granger causality, and in practice it changes the estimate by raising the fitted model order. The alternative is spectral Granger causality integrated over the band; `granger_spectral` reports the band mean | `bandpass_filter`, `granger_spectral` |

## Data format

- Teeters, J. L., et al. (2015). Neurodata Without Borders: creating a common data format for
  neurophysiology. *Neuron*. [doi:10.1016/j.neuron.2015.10.025](https://doi.org/10.1016/j.neuron.2015.10.025)
- Rübel, O., et al. (2022). The Neurodata Without Borders ecosystem for neurophysiological data
  science. *eLife*. [doi:10.7554/eLife.78362](https://doi.org/10.7554/eLife.78362)
- Software: [NWB overview](https://nwb-overview.readthedocs.io/en/latest/),
  [PyNWB](https://pynwb.readthedocs.io/en/stable/), [HDMF](https://hdmf.readthedocs.io/en/stable/),
  [DANDI Archive](https://dandiarchive.org/).

## Computation

- [CuPy](https://docs.cupy.dev/en/stable/) — the GPU path behind `device='cuda'`.
- [joblib](https://joblib.readthedocs.io/en/stable/) — the worker processes behind `n_jobs`.
