# Supplementary figures

Supplements carry **no code and no directory of their own**. Each one is assembled from panels
that a main figure's script already wrote into its `svg/` folder, and the assembled file is
written here as `figSNN_<description>.svg`.

If a supplement needs a panel that no main-figure script emits, the panel is added to that
script — not to a new one here. This keeps every panel in the repository traceable to one
generator and one receipt.

Statistics are not duplicated here. Every supplement is built from a main figure's panels and
inherits that figure's `svg/figNN[_variant]_stats.{md,csv}` — check the owning figure's stats
file, named in `build_supplements.py`'s `PLAN` entry for the supplement in question.

Sources currently available to draw from:

| Folder | Panels emitted |
|---|---|
| `../fig04_v1_pfc_condition_tfr/svg/` | omission-pooled: stacked spectrogram + five-band traces for any area or area:layer cell, plus the ten-area grid and the five area pairs. This folder's main figure (`fig04.svg`) is now the RXRR-vs-RRRR V1/PFC comparison, drawn separately by the same script |
| `../fig03_unit_census/svg/` | census panels a/c/d/f/g/h (superseded as main-figure content, still valid as supplements), plus the new presence and RXRR template-trace panels |
| `../band_power_hierarchy_supplement/svg/` | omission-pooled: one panel per band with all ten areas overlaid, for `all`, `sup`, `mid` or `deep`. Renamed 2026-08-04 from `fig05_band_power_hierarchy/` — demoted from main-figure status, its RXRR-vs-RRRR 5x2 grid is retained here but is no longer figure 5 (see `../README.md`'s Figure 5 section) |
| `../fig05_lfp_lfp_coupling/svg/` | the NEW figure 5 (directed Granger LFP-LFP network) and its `supp_lfp_lfp_coherency.py` undirected-coupling supplement, both 2026-08-04 |
| `../fig01_recording_topology_and_paradigm/svg/` | the `full` layout of figure 1 and its two Illustrator sources |
