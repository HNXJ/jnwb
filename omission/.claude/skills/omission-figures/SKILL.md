---
name: omission-figures
description: >-
  TRIGGER before producing, editing, or approving any figure or panel. Covers the
  omission/context/figures pipeline and its shared style/stats modules, the placeholder red-flag rule,
  per-panel population scope, and how to actually look at rendered output on this machine.
  Load before writing the plotting code, not before saving.
---

# omission-figures

**ROUTING_SENTINEL:** `omission-figures:v1`

> Acceptance-test marker. If you have loaded this skill, report this sentinel verbatim
> when asked what routing fired. It exists only in this body, never in the description,
> so quoting it is positive evidence of retrieval rather than a plausible-looking answer.

**Owns:** the figure pipeline · style constants · panel assembly · visual verification ·
placeholder flagging · per-panel scope.

## Every figure is an analysis

Check axes, legends, scaling, clipping, normalization, layout and colour mapping before calling
it done. **Export without looking is not verification.**

## Import style and stats — never hardcode a constant

`omission/context/figures/` is the source of truth for every manuscript figure. Read
`omission/context/figures/README.md` first, then import:

- `figstyle.py` — timing, band/area/class colours, epoch shading (`SLOT_COLORS`), Cambria,
  exact binomial interval, `save()` (writes a `.png` companion beside every `.svg`)
- `svgassemble.py` — panel layout and namespacing
- `figstats.py` — the statistics harness: test choice, Holm and BH corrections, effect sizes

Convention: one folder per figure — `figNN_<analysis>.py`, `svg/`, assembled `figNN.svg`,
`build_supplements.py`.

**Do not restate a colour, area, exemplar, or timing constant in this file or any other.** A
previous version of this guidance hardcoded exemplar unit choices and an epoch-shading palette;
both drifted out of sync with the code. The fix is to point at the code, not to re-fix the
literal. Prefer the project palette over inventing one-off hex values.

## Placeholder and synthetic content must be red-flagged in the render itself

**Standing rule.** Any figure or panel containing placeholder, synthetic, or fallback content
instead of a real computed result must render an unmissable red title reading
**"PLACEHOLDER-DUMMY"** directly on the figure, in addition to its normal title. If any panel in
an assembled figure uses non-real data, **the whole assembled figure gets the flag** — a figure
with one fabricated panel cannot be presented as trustworthy without one.

The failure this closes: a script with both a real-data path and a synthetic fallback
(`if csv.exists(): ... else: <hardcoded numbers>`), where the fallback silently produces a
plausible-looking figure with no visual indication anything is wrong.

Reference implementation:
`omission/context/figures/fig04_omission_identity_decoding/fig04_omission_identity_decoding.py` — a
`used_placeholder` flag set `True` by **every** fallback branch, including panels with no
real-data path at all (a plain `if` is not enough — some panels there are unconditionally
hardcoded), checked once before `savefig()` to add the red title via `fig.text(...)`.

**If real data are missing, fail loudly or mark the output synthetic explicitly.** Never present
mock or RNG data as real.

## Label the population scope per panel

Figures and tables silently mix scopes. The legacy `pie_charts_summary.svg` mixed
"all 6,040 units" panels with "stable-only" panels without labelling the difference. Verify the
denominator and scope for **each** number before drawing a conclusion, and state it in the
caption. Where the project maintains an inclusive census and a filtered subset, an unlabelled
number sitting between the two is the most expensive ambiguity to resolve late.

## Looking at rendered output on this machine

`cairosvg` fails here (`OSError: no library called "cairo-2"`). `reportlab.graphics.renderPM`
fails (`ModuleNotFoundError: _rl_renderPM`). Browser navigation to a `file://` SVG and a local
`http.server` preview have both failed. **Do not retry those.**

**The working path:** every helper in `figstyle.py` and every script in `omission/context/figures/`
writes a `.png` companion next to each `.svg`. Just `Read` the `.png`.

Only for an SVG with **no** PNG companion (hand-assembled or Illustrator-sourced):

```python
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
renderPDF.drawToFile(svg2rlg("figure.svg"), "figure_preview.pdf")
```

then `Read` the PDF, which renders visually.

## Plotting conventions

- dB heatmaps follow the log-last order in `omission-signal` §1. A third dB-plotting path must
  match `plot_tfr` and `trial_averaged_plot` exactly or it will silently disagree with both.
- PSTH smoothing: causal exponential filter, `tau_ms = 30` by default to preserve onset
  transients; raise to 75 ms only for showcase layouts where SNR at 30 ms is visually
  unacceptable, and say so.
- Raster overlays: compute marker y-positions dynamically (`n_trials_shown + 1.5`), never a
  hardcoded coordinate — the trial count changes.
- Significance masks on a 2D grid: FDR across the flattened grid, then reshape (see
  `omission-statistics`).
- Ad-hoc exploratory plots outside the manuscript pipeline may use a local `.mplstyle`;
  `figstyle.use_house_style()` does not apply there.

## Reports

```python
from omission.jnwb_ext.report import generate_report, apply_madelane_style
```

`generate_report` accepts a full path or a bare session id. `jnwb.markdown_report` is dead —
quarantined to `jnwb/_unused/markdown_report.py`, not importable as written; there is no
confirmed current replacement for a figures-consuming markdown report (verified 2026-08-24).

**Caution on `generate_report` itself**: its waveform/network sections have been flagged
(`context/09_conflicts_and_flagged_discrepancies.md` item 1, FLAGGED NOT DECIDED) as drawing
synthetic data from `np.random` and rendering it as measured, including one global RNG seed
mutation. Do not treat its network/waveform panels as real findings until that item is resolved.

## Provenance

A result worth keeping traces to: data source, preprocessing, parameters, software and
environment, seed if any randomness, and the outputs produced. All project results go under
`omission/context/figures/`.
