# References

Sources for the methods jnwb implements. Each DOI below resolved on Crossref on 2026-09-10,
and the two books were checked on Open Library. The docstrings of the listed functions cite
the same entries.

## Signal processing

Filtering, convolution, sampling, the discrete Fourier transform and windowing follow the
treatment in these two books.

- Oppenheim, A. V., & Willsky, A. S. *Signals and Systems*. First published 1983.
- Oppenheim, A. V., & Schafer, R. W. *Discrete-Time Signal Processing*. ISBN 978-0-13-198842-2.
- Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power spectra:
  a method based on time averaging over short, modified periodograms. *IEEE Transactions on
  Audio and Electroacoustics*. [doi:10.1109/TAU.1967.1161901](https://doi.org/10.1109/TAU.1967.1161901)
  — `compute_psd`, `band_power`, `spectral_tilt`, `harmonic_analysis`, `imaginary_coherency`,
  `cross_area_coherence`.
- Torrence, C., & Compo, G. P. (1998). A practical guide to wavelet analysis. *Bulletin of the
  American Meteorological Society*.
  [doi:10.1175/1520-0477(1998)079<0061:APGTWA>2.0.CO;2](https://doi.org/10.1175/1520-0477(1998)079%3C0061:APGTWA%3E2.0.CO;2)
  — `complex_tfr` (Morlet transform and cone of influence; jnwb sets the cone at `coi_sigma`
  wavelet standard deviations).

## Coherence and phase

- Nolte, G., et al. (2004). Identifying true brain interaction from EEG data using the
  imaginary part of coherency. *Clinical Neurophysiology*.
  [doi:10.1016/j.clinph.2004.04.029](https://doi.org/10.1016/j.clinph.2004.04.029)
  — `imaginary_coherency`.
- Vinck, M., et al. (2010). The pairwise phase consistency: a bias-free measure of rhythmic
  neuronal synchronization. *NeuroImage*.
  [doi:10.1016/j.neuroimage.2010.01.073](https://doi.org/10.1016/j.neuroimage.2010.01.073)
  — `pairwise_phase_consistency`.

## Directed connectivity

- Granger, C. W. J. (1969). Investigating causal relations by econometric models and
  cross-spectral methods. *Econometrica*. [doi:10.2307/1912791](https://doi.org/10.2307/1912791)
  — `granger`, `granger_causality`.
- Geweke, J. (1982). Measurement of linear dependence and feedback between multiple time series.
  *Journal of the American Statistical Association*.
  [doi:10.1080/01621459.1982.10477803](https://doi.org/10.1080/01621459.1982.10477803)
  — `granger`, `granger_spectral`.
- Nolte, G., et al. (2008). Robustly estimating the flow direction of information in complex
  physical systems. *Physical Review Letters*.
  [doi:10.1103/PhysRevLett.100.234101](https://doi.org/10.1103/PhysRevLett.100.234101)
  — `phase_slope_index`.
- Schreiber, T. (2000). Measuring information transfer. *Physical Review Letters*.
  [doi:10.1103/PhysRevLett.85.461](https://doi.org/10.1103/PhysRevLett.85.461)
  — `transfer_entropy`.

## Statistics

- Maris, E., & Oostenveld, R. (2007). Nonparametric statistical testing of EEG- and MEG-data.
  *Journal of Neuroscience Methods*.
  [doi:10.1016/j.jneumeth.2007.03.024](https://doi.org/10.1016/j.jneumeth.2007.03.024)
  — `cluster_permutation_test`.
- Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: a practical and
  powerful approach to multiple testing. *Journal of the Royal Statistical Society Series B*.
  [doi:10.1111/j.2517-6161.1995.tb02031.x](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)
  — `StatisticalAnalysis.fdr_correct`, the `q_matrix` of `directed_network`.

## Representational analysis

- Kriegeskorte, N., et al. (2008). Representational similarity analysis: connecting the branches
  of systems neuroscience. *Frontiers in Systems Neuroscience*.
  [doi:10.3389/neuro.06.004.2008](https://doi.org/10.3389/neuro.06.004.2008)
  — `jrsa(metric='rsa')`.
- Gretton, A., et al. (2005). Measuring statistical dependence with Hilbert-Schmidt norms.
  *Lecture Notes in Computer Science*. [doi:10.1007/11564089_7](https://doi.org/10.1007/11564089_7)
  — `jrsa(metric='hsic')`.

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
