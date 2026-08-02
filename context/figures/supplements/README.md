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
| `../fig05_band_power_hierarchy/svg/` | omission-pooled: one panel per band with all ten areas overlaid, for `all`, `sup`, `mid` or `deep`. This folder's main figure (`fig05.svg`) is now the RXRR-vs-RRRR 5x2 grid, drawn separately by the same script |
| `../fig01_recording_topology_and_paradigm/svg/` | the `full` layout of figure 1 and its two Illustrator sources |
