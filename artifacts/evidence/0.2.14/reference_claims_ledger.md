# Reference claim ledger

One line per claim cell of `docs/references.md`. `tests/test_reference_claims_ledger.py` recounts
the cells with the page's table reader and requires these lines.

A claim cell is the second column of each body row of each table on the page: the column headed
Result implemented, What jnwb follows from it, Result reproduced or Pitfall stated. Header and
separator rows are not cells. The Data format bullets sit outside a table, so they are not cells.
A cell's key is its section (the `##` heading) and its reference cell's text through the first
`(YYYY)`.

The page had 83 body rows at the 2026-10-20 reference check (commit 00947a48) and 93 now; the 10
rows added since have no grade from that check.

Verdicts: `cut` is a claim narrowed to what the title, abstract and code decide, as the commit
messages use the word. `reworded` is a claim a commit narrowed or rephrased. `confirmed` is a claim
the full text confirms. `kept` is a core text kept by ruling, with no full-text check. `unrecorded`
is a cell no record gives a verdict for. The 2026-10-23 ruling counts 7 claims confirmed and names
no cell, so those 7 are among the `unrecorded` lines unless a later record names them.

Source read names the commit whose diff of the cell was read, or the ruling, or `none`. A cell read against its text names the URL read and the quote (at most 15 words) that decides it; `none: <what was tried>` when no text was reachable or the text cannot decide the claim.

- claim cells: 93
- cut: 60
- reworded: 6
- confirmed: 11
- kept: 14
- unrecorded: 2

| Section | Reference | Column | Verdict | Source read |
|---|---|---|---|---|
| Signal processing | Welch, P. D. (1967) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Signal processing | Thomson, D. J. (1982) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Signal processing | Torrence, C., & Compo, G. P. (1998) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Signal processing | Donoghue, T., et al. (2020) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Signal processing | Virtanen, P., et al. (2020) | claim | confirmed | https://www.nature.com/articles/s41592-019-0686-2 "Functionality includes convolution and correlation, splines, filtering and filter design" |
| Laminar analysis | Mendoza-Halliday, D., et al. (2024) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Laminar analysis | Bastos, A. M., et al. (2018) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Laminar analysis | Bastos, A. M., et al. (2021) | claim | confirmed | https://elifesciences.org/articles/60824 "The cross-over between the relative power of the gamma and alpha-beta bands was used" |
| Laminar analysis | Mitzdorf, U. (1985) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Laminar analysis | Nicholson, C., & Freeman, J. A. (1975) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Laminar analysis | Major, A. J., et al. (2025) | claim | reworded | https://pmc.ncbi.nlm.nih.gov/articles/PMC13504716/ "The algorithm identifies low- and high-frequency ranges with maximal laminar power gradients" |
| Laminar analysis | Mendoza-Halliday, D., et al. (2023) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Coherence and phase | Nolte, G., et al. (2004) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Coherence and phase | Vinck, M., et al. (2011) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Coherence and phase | Vinck, M., et al. (2010) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Coherence and phase | Dahlhaus, R. (2000) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Coherence and phase | Maris, E., Schoffelen, J.-M., & Fries, P. (2007) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Coherence and phase | Bastos, A. M., et al. (2020) | claim | reworded | 84ba900b diff: claim narrowed (commit: Bastos 2020 narrowed) |
| Coherence and phase | Berens, P. (2009) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Directed connectivity | Granger, C. W. J. (1969) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Directed connectivity | Geweke, J. (1982) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Directed connectivity | Geweke, J. F. (1984) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Directed connectivity | Lütkepohl, H. (2005) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Directed connectivity | Nolte, G., et al. (2008) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Directed connectivity | Schreiber, T. (2000) | claim | confirmed | https://arxiv.org/pdf/nlin/0001042 (preprint; PRL text not reachable) "by which we deﬁne the transfer entropy" |
| Directed connectivity | Marschinski, R., & Kantz, H. (2002) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Directed connectivity | Wilson, G. T. (1972) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Directed connectivity | Dhamala, M., Rangarajan, G., & Ding, M. (2008) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Directed connectivity | Haufe, S., Nikulin, V. V., Müller, K.-R., & Nolte, G. (2013) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Directed connectivity | Winkler, I., Panknin, D., Bartz, D., Müller, K.-R., & Haufe, S. (2016) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Information measures | Shannon, C. E. (1948) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Statistics | Maris, E., & Oostenveld, R. (2007) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Statistics | Phipson, B., & Smyth, G. K. (2010) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Statistics | Benjamini, Y., & Hochberg, Y. (1995) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Statistics | Benjamini, Y., & Yekutieli, D. (2001) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Statistics | Przyborowski, J., & Wilenski, H. (1940) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Statistics | Clopper, C. J., & Pearson, E. S. (1934) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Statistics | Pitman, E. J. G. (1937) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Statistics | Mann, H. B., & Whitney, D. R. (1947) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Statistics | Efron, B. (1979) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Statistics | Geyer, C. J. (1992) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Spiking population measures | Fleiss, J. L. (1971) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Spiking population measures | Cohen, M. R., & Kohn, A. (2011) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Spiking population measures | de la Rocha, J., Doiron, B., Shea-Brown, E., Josić, K., & Reyes, A. (2007) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Spiking population measures | Churchland, M. M., et al. (2010) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Spiking population measures | Wagenaar, D. A., Pine, J., & Potter, S. M. (2006) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Spiking population measures | Gerstein, G. L., & Kiang, N. Y.-S. (1960) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Spiking population measures | Nawrot, M. P., Aertsen, A., & Rotter, S. (1999) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Unit quality | Siegle, J. H., et al. (2021) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Unit quality | Jia, X., et al. (2019) | claim | cut | 84ba900b diff: claim cut to what the abstract and the code decide |
| Unit quality | Shinomoto, S., et al. (2009) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Unit quality | Hill, D. N., Mehta, S. B., & Kleinfeld, D. (2011) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Unit quality | Llobet, V., Wyngaard, A., & Barbour, B. (2022) | claim | reworded | https://www.biorxiv.org/content/10.1101/2022.02.08.479192v1.full "We shall use the estimate for random contamination of Eq. (3)" |
| Unit quality | Cohen, J. (1960) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Waveform clustering | Lee, E. K., et al. (2021) | claim | confirmed | https://elifesciences.org/articles/67490 "extracted for a duration of 1.6 ms with a pre-trough period of 0.4 ms" |
| Waveform clustering | Lee, K., Carr, N., Perliss, A., & Chandrasekaran, C. (2023) | claim | reworded | https://pmc.ncbi.nlm.nih.gov/articles/PMC10220268/ "Normalize the array by dividing each value by the maximum value in each row" |
| Waveform clustering | McInnes, L., Healy, J., & Melville, J. (2018) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Waveform clustering | Blondel, V. D., Guillaume, J.-L., Lambiotte, R., & Lefebvre, E. (2008) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Waveform clustering | Lambiotte, R., Delvenne, J.-C., & Barahona, M. (2008) | claim | reworded | https://arxiv.org/pdf/0812.1770 "is equivalent up to a linear transformation to the tuneable Hamiltonian" |
| Representational analysis | Kriegeskorte, N., et al. (2008) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Representational analysis | Gretton, A., et al. (2005) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Representational analysis | Kornblith, S., et al. (2019) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Representational analysis | Robert, P., & Escoufier, Y. (1976) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Representational analysis | Székely, G. J., Rizzo, M. L., & Bakirov, N. K. (2007) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Representational analysis | Cunningham, J. P., & Yu, B. M. (2014) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Representational analysis | Varma, S., & Simon, R. (2006) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Representational analysis | Cortes, C., & Vapnik, V. (1995) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Artifact detection and repair | Bigdely-Shamlo, N., et al. (2015) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Artifact detection and repair | Leys, C., et al. (2013) | claim | cut | 3ba28202 diff: claim cut to what the title, abstract and code decide |
| Core texts | Oppenheim, A. V., & Willsky, A. S. (1997) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Oppenheim, A. V., & Schafer, R. W. (2010) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Percival, D. B., & Walden, A. T. (1993) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Bendat, J. S., & Piersol, A. G. (2010) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Mitra, P., & Bokil, H. (2007) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Cohen, M. X. (2014) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Nunez, P. L., & Srinivasan, R. (2005) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Grün, S., & Rotter, S. (2010) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Efron, B., & Tibshirani, R. J. (1993) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Good, P. I. (2004) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Cover, T. M., & Thomas, J. A. (2005) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Hastie, T., Tibshirani, R., & Friedman, J. (2009) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Fisher, N. I. (1993) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Core texts | Mardia, K. V., & Jupp, P. E. (2000) | claim | kept | ruling 2026-10-23 (keep the 14 core texts); todo row 11 |
| Studies jnwb reproduces | Fleiss, J. L. (1971) | claim | unrecorded | none: doi.apa.org returned 403; the Europe PMC record has no abstract |
| Studies jnwb reproduces | Hill, D. N., Mehta, S. B., & Kleinfeld, D. (2011) | claim | confirmed | https://pmc.ncbi.nlm.nih.gov/articles/PMC3123734/ "an observation of r = 20 refractory period violations yields an estimate of" |
| Studies jnwb reproduces | Major, A. J., et al. (2025) | claim | confirmed | receipts tests/fixtures/vflip2_matlab_reference.json (e5c56bcf; source vFLIP2.m, dryad_version 8, 2025-11-04) and tests/fixtures/vflip2_from_lfp_matlab_reference.json (fc942bd5): "run in MATLAB R2024a on seeded synthetic laminar LFP"; the cited tests pass at 4c192be9 |
| Studies jnwb reproduces | Siegle, J. H., et al. (2021) | claim | confirmed | receipt artifacts/evidence/0.2.9/unit_qc_inventory.md (b48bd9a7; section D, read at 919992748a53): "Agreement with the source functions, run on the same inputs with no correction factor"; tests/test_unit_quality.py (6893ef47) pins the values; the "(Jia et al.)" attribution is unchecked, since neither paper was read |
| Pitfalls | Bastos, A. M., & Schoffelen, J.-M. (2016) | claim | confirmed | https://www.frontiersin.org/journals/systems-neuroscience/articles/10.3389/fnsys.2015.00175/full "which is inherently unbiased, such as PPC" |
| Pitfalls | Vezoli, J., et al. (2021) | claim | confirmed | https://pmc.ncbi.nlm.nih.gov/articles/PMC8639786/ "excluding sites within a 2-mm radius to avoid residual volume conduction effects" |
| Pitfalls | Friston, K. J., et al. (2014) | claim | reworded | 00947a48 diff: claim reworded to what the abstract says (Friston 2014 row) |
| Pitfalls | Barnett, L., & Seth, A. K. (2011) | claim | confirmed | Europe PMC abstract (PMID 21864571; ScienceDirect 403) https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:%2210.1016/j.jneumeth.2011.08.010%22&format=json&resultType=core "as a consequence of large increases in empirical model order induced by filtering" |
| Pitfalls | Nejat, H., & Hajipour Sardouie, S. (2021) | claim | unrecorded | none: ieeexplore returned 418 and the doi.org landing 202 with no body; Europe PMC has no record |
| Data format | Rübel, O., Tritt, A., Ly, R., Dichter, B. K., Ghosh, S., Niu, L., Baker, P., Soltesz, I., Ng, L., Svoboda, K., Frank, L., & Bouchard, K. E. (2022) | claim | confirmed | https://elifesciences.org/articles/78362 "allow convenient interfaces for writing and reading data according to the NWB schema" |
