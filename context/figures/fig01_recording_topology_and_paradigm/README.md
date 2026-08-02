# Figure 1 — recording topology, hardware, and experimental design

**Current design, 2026-07-31.** Three panels: **A** = brain regions (lateral view + area
labels). **B** = probe schematic + recording/behavioral hardware facts (native text, not baked
into any artifact). **C** = the three block-type experimental-design grids (AAAB/BBBA/RRRR), as
three columns, built from two single-icon vector artifacts. Canvas lands close to 6:5
(width:height) from fixed panel/icon sizing, not solved for exactly.

## Whitespace/alignment pass (2026-07-31, after the artifact re-cut above)

User: "objects are now good, but there are some misalignments, whitespace, and overlaps."
Three fixes, no architecture change:
- **Panel B height now matches panel A exactly.** `probe_h` was computed as
  `height_A - facts_block_h - 4.0` (an arbitrary 4pt fudge) — the actual bottom of panel B's
  content (probe image + gap + wrapped fact text) landed about 5.5pt below panel A's own
  bottom edge. Changed the fudge to `FACT_LINE_H` (the real gap already used between the image
  and the first fact line), so `probe_h + FACT_LINE_H + facts_block_h == height_A` exactly.
- **Probe image centered, not left-aligned, within panel B's column.** The probe schematic is
  tall and narrow (aspect ≈0.39), so at its natural width it never fills panel B's allocated
  column width — left-aligning it (previous behavior) dumped ALL the resulting slack on the
  right as one lopsided gap; centering splits it evenly on both sides.
- **`ICON_R` raised from 10.5 to 12.5.** Panel C's icons were much smaller than their grid
  cells, leaving visibly dead space inside every Standard/Omission box. Bigger icons fill the
  cells better and, as a side effect, brought the canvas aspect to 468x392pt (1.194) — closer
  to the 6:5 (1.2) target than any previous pass, without solving for it directly.

## Probe sized to fill panel B, text moved beside it (2026-07-31, after the pass above)

User: "the probe is too small... make it same height as panel a and instead fit the text in
between so whitespace gets reduced." The previous pass shrank the probe to leave room for fact
text stacked BELOW it; now the probe is drawn at `height_A` exactly (matching panel A, no
separate sizing/alignment logic needed) and the fact text is placed in whatever width is left
over BESIDE it (`text_x0 = x0_B + probe_w + 6.0`), wrapped narrower (16 lines now, was 9) and
comfortably within `height_A`'s vertical budget.

## Timeline row overlap bug, fixed same day it was added (2026-07-31)

The first version of `timeline_row()` used `transform="rotate(-40 cx cy)"` for the diagonal
labels. SVG's y-axis points DOWN, so a negative rotation sends text UP-and-right from its
anchor, not down-and-right — the labels climbed back up into the omission box sitting right
above them instead of staying in the blank space reserved below. This was shipped without an
actual browser screenshot confirming it (the preview pane was down at the time) and the user
caught it directly: "the times are overlapping with figure... you should be smart enough to
know that those timings should be visible, not nested in." Fixed by using a POSITIVE rotation
(`TICK_ROTATE_DEG = 45.0`, asserted `> 0` in code, not just commented, so this can't silently
regress) and confirmed via an actual Claude_Browser screenshot before calling it done. See the
user-facing lesson saved to this session's persistent memory (`feedback_figure_no_overlap_
default.md`): figure elements default to no whitespace AND no overlap/nesting unless asked,
and rotated-element placement must be verified by rendering, not by reasoning about the
transform's sign.

## Trial-timing timeline row added under each panel C column (2026-07-31)

User supplied a reference image: a diagonal-label timeline ("-500ms - fx", "0ms - p1", ...,
"4124ms - end") repeated under each of three dash-dot-separated groups, asking for it to "show
the sequence timing of presentations and delays." This maps directly onto panel C's three
block-type columns (already dash-dot separated). Implemented as `timeline_row()`, called from
`block_column()` right after the omission box: 10 rotated (-40deg) tick labels per column, at
`TICK_FONT_PT = 4.6`, evenly spaced across the column width. Labels and their ms values come
from `figstyle.full_trial_ticks()` (imported, not re-derived), so they can't drift from figures
2/3's own trial-timing axis. Text color per epoch echoes `slot_background()`'s own p1-p4
`SLOT_COLORS` family, darkened for legibility as text (`EPOCH_TEXT_COLORS`); delays/fx/end are
grey. Canvas grew from 392pt to 421pt tall (aspect 1.19 -> 1.11) to fit the new row — expected
given real content was added, not chased back toward 6:5.

## Macaque icon added to panel B (2026-07-31)

`artifacts/macaque.png` (user-supplied, previously unused -- see History) is now placed in
panel B's bottom-right corner, fixed width `MACAQUE_ICON_W = 26.0`pt, height from its own
aspect ratio, right-aligned 2pt from the canvas edge and bottom-aligned 2pt above panel B's own
bottom edge (`y + height_A`).

## Panel B text tightened (2026-07-31, after the grouping above)

User: "make panel b whitespace less; reduce the font size of its text and bring it leftwards."
`FACT_FONT_PT` 7.0→6.0, `FACT_HEADER_PT` 7.5→6.5, `FACT_LINE_H` 9.5→7.5, and the gap between
the probe image and its text (`PROBE_TEXT_GAP`) 6.0→2.0 -- text now starts closer to the probe
and wraps to fewer lines (15, was 18) since the smaller, closer-set text has more available
width per line.

## Panel B facts rewritten, grouped (2026-07-31)

User dictated a full replacement for `PANEL_B_FACTS` directly, restructured into four bold
section headers (Probe / Recording hardware / Behavioral control / Screen) each with 2-4 short
detail lines, rather than one flat wrapped-paragraph list. `PANEL_B_FACTS` is now
`list[tuple[str, list[str]]]`; `render_fact_groups()` draws each header bold and its details
plain-indented, with a small gap between groups. Some of the dictated content (Monkeylogic 2,
EyelinkSR eye tracker, VPXX projector, 1080P 120Hz, the ONE/TWO 40µm/25µm probe-spacing split)
supersedes the previous NWB/manuscript-draft-sourced version below and has not been
independently cross-checked against those sources — taken as authoritative from the user's own
direct dictation of their setup, per the same standard the earlier version's own sourcing
comment was held to.

## Panel C background: p1-p4 slot colors + screen-hatch header (2026-07-31)

User supplied a reference image (a repeating pattern of a hatched grey header bar over four
pastel vertical bands, in three dash-dot-separated groups) and asked for it as panel C's
background, "so it would then both show that screen layout, and be similar and related to
later figures which have these colors and shades." The four pastel colors are EXACTLY
`figstyle.py`'s own `SLOT_COLORS` (`["#FFF3B0", "#F6C9E0", "#BFE6C6", "#C9D6F2"]` — p1 yellow,
p2 pink, p3 green, p4 blue), the same palette `mark_full_trial_axis()` already uses for
full-trial slot shading in figures 2/3 — imported directly (`from figstyle import
SLOT_COLORS`), not copied, so the two can't drift apart.

Implemented in `slot_background()`: four `SLOT_COLORS` bands (opacity 0.55) spanning the full
height of each block column's Standard+Omission boxes, drawn BEHIND the grid boxes/icons (must
be emitted first in the column's own part list) so the icons and box borders stay legible on
top. Dash-dot gold dividers (`#B8860B`) between the three block-type columns match the
reference image's own group separators. An initial version also drew a hatched grey header
strip above the color bands (reusing the grating icons' own 45deg-stripe pattern to stand in
for "a stimulus is on screen here") — removed the same day per direct user feedback ("remove
that strip"); `HEADER_H`/`HATCH_ID` and the associated `<pattern>` def are gone from the script
entirely, not just unused.

## Pipeline (2026-07-31, current — third revision this date)

Two stages, split so day-to-day figure edits don't re-run slow, hard-to-verify source-cropping
logic (user: "why is it taking so long"):

1. **`build_parts.py`** — run once per source change, not every figure edit. Writes four
   tightly-cropped artifacts to `artifacts/` (user, 2026-07-31: "crop each artifact correctly
   so it would only include the object"):
   - `madelane.png` — brain + area labels, no title, no panel "a" label. This is the SAME
     raster already embedded in `svg/01_recording_topology.svg` (area labels are baked pixels,
     not separate vector text) — extracted via its own base64 `<image>` data and trimmed
     against a white background (trim was a no-op: the source embed already has no padding).
   - `dbc128.png` — the probe schematic, extracted and trimmed the same way.
   - `grating45.svg` / `grating135.svg` — ONE `circular_grating()` icon each (the "A"/"B"
     identity orientations), tightly cropped to its own bounding circle via `viewBox` (no
     surrounding canvas). `context/figures/grating.py` still owns `circular_grating()` itself;
     these two files are the only things built from it now — `panel_c_fragment()` and
     `build_panel_c()` are no longer used by this figure (see below).
2. **`fig01_recording_topology_and_paradigm.py`** — the assembler, using FIXED absolute
   constants (`PANEL_A_W`, `ICON_R`, `COL_GAP`, margins, etc.) plus RELATIVE offsets computed
   from them (user, 2026-07-31: "use fixed + relative coordination") instead of solving a
   system of aspect-ratio equations for a shared width (the previous two approaches this same
   date both did that, and both were slow to reason about). Panels A/B are placed as plain
   `<image>` (their own fixed width; height follows from each PNG's own aspect ratio — that
   part IS relative, not fixed, since a raster's aspect ratio is a property of the file, not a
   free parameter). Panel C is built by repeating `grating45.svg`/`grating135.svg` on a fixed
   icon-radius/row-height/column-gap grid — three columns, each a green "Standard" box (1 row)
   and a red "Omission" box (3 rows), exactly as before, just placed directly rather than via a
   `panel_c_fragment()` blob.

### Image embedding: base64, not a path reference

`<image href="artifacts/madelane.png">` (a relative path) rendered blank in the Claude_Browser
preview pane, even though the browser's own network log showed a 200 OK for that exact file —
confirmed 2026-07-31 that an ABSOLUTE `file:///...` href loaded correctly in the same pane, so
the preview tool's local-file serving does not resolve relative `<image>` hrefs against the
SVG's own location the way a normal browser tab does. An absolute path isn't portable across
machines/checkouts, so `png_data_uri()` embeds each PNG's bytes directly as a `data:image/png;
base64,...` href instead — self-contained, and exactly how the original Illustrator sources
already embed their own raster images, so this isn't a new pattern for this repo.

### R-family icons: no third artifact

R-family cells reuse `grating45.svg`/`grating135.svg` through a shared SVG `<filter>`
(desaturate + a touch of transparency) rather than needing dedicated grey files — **R means a
50/50 draw between the two REAL identities (P(A)=P(B)=0.5), never a third orientation** (user
correction, see "What changed and why" below). `_seeded_ab_choice()` in the assembler picks A
or B deterministically per cell (sha256 of the cell's own uid), so re-running the script
reproduces the same figure.

### Approaches tried and dropped, all 2026-07-31 (for when this needs touching again)

Three different placement techniques were tried in one day, in this order, each fixing a real
bug the last one had:
1. `<image href="artifacts/panel_x.svg">` (whole-panel SVG artifacts referenced by path):
   svglib ignored the `<image>`'s `width`/`height` and rendered each artifact at native (huge)
   size, wildly overlapping its neighbours; local file:// SVG-referencing-SVG via `<image>` is
   also a known Chromium security restriction independent of that bug.
2. Inlining a whole-panel SVG artifact via a bare `<g transform="translate(...) scale(...)">`
   (no wrapping `<svg>`): this drops the artifact's own crop entirely, since `viewBox`-based
   clipping only happens on an `<svg>` element and a bare `<g>` isn't one — the FULL, unclipped
   source content rendered at the placement's scale/position. Confirmed by rendering: an
   unrelated pie-chart summary panel from later in `01_recording_topology.svg` bled through
   underneath panels A and B, extending down into panel C.
3. **Current**: panels A/B are now plain raster PNGs (no crop-at-placement-time problem to
   have, since `build_parts.py` already trimmed them to exactly their own content), and panel C
   is built from two tiny single-icon SVGs placed directly on a fixed grid rather than one big
   pre-assembled blob artifact — sidesteps the whole class of "inlining loses the crop" bugs
   above by not needing to inline and re-crop a large composite artifact at all.

## What changed and why (most recent first)

- **Artifacts re-cut to one-object-each, fixed+relative assembly.** Previous artifacts
  (`panel_a_brain.svg`, `panel_b_probe.svg`, `panel_c_blocks.svg`) each held a whole panel's
  worth of content and needed crop-preserving inlining logic to place (see "Approaches tried
  and dropped" above). Replaced with `madelane.png` (brain+areas only), `dbc128.png` (probe
  only), and `grating45.svg`/`grating135.svg` (one icon each) — see Pipeline above.
- **Panel C: rows → columns, close to 6:5 aspect.** User feedback 2026-07-31 ("too much
  whitespace... should be W:H 6:5"): three full-width stacked rows made panel C tall and
  narrow, exactly wrong for a landscape canvas. Panel C is now three columns; `PANEL_A_W` and
  `ICON_R` were tuned once (not solved) to land the resulting canvas near 468x390pt (6:5) —
  current output is 468x376pt (aspect 1.245 vs the 1.2 target, close enough without
  reintroducing an equation solve).
- **Grating icon technique rewritten.** `circular_grating()` (`grating.py`) was originally
  ~15-20 individually rotated `<rect>` stripes inside a `<clipPath>`-clipped `<g>` — user
  feedback 2026-07-31: "grating is a simple circle; what you made is a bunch of rectangles."
  Rewritten as a plain `<circle>` filled with a repeating stripe `<pattern>` — a circle's own
  fill region IS its boundary, no clipPath needed. Confirmed correct in a real browser render.
- **R-family icon semantics corrected.** User correction 2026-07-31: "R (random) means P(A) =
  P(B) = 0.5; not random directions." An earlier pass drew each R-family icon at its own
  continuous pseudo-random orientation, inventing a family that doesn't exist in the paradigm.
  Fixed as described above (shared filter + 50/50 A/B draw).
- **Panel C content and percentages verified against the user's own reference image**
  (2026-07-31, a clean re-render of the original `02_paradigm.svg` panels a-f the user supplied
  directly): box labels read "Standard (70%)" / "Omission (30%)" for A/B, "Standard (50%)" /
  "Omission (50%)" for R — shortened from that source's own longer labels ("Standard trials
  (70%)", "Standard random control trials (50%)") to fit the column width, percentages
  unchanged.
- **Panel B fact-line wrapping.** `PANEL_B_FACTS` lines are native `<text>`, not clipped to
  panel B's own (narrow) width — the longest line once ran off the page's right margin uncut.
  `wrap_text()` (greedy word-wrap against an average-glyph-width estimate) wraps every fact
  line to the actual available width.
- **Two leftover live `<text>` elements were stripped from `01_recording_topology.svg`** in the
  prior (whole-panel-artifact) pipeline revision, both redundant with panel B's own new content
  and colliding with it: a two-line caption ("Monkeylogic-NIMH (Behavioral control) / INTAN-RHD
  (Recording Hardware)") and a vertical label ("Diagnostic BioChips (DBC) 128-channel laminar
  probes"). Now moot: `madelane.png`/`dbc128.png` are extracted directly from each image's own
  base64 payload, which never included that live text to begin with.
- **Panel A** is brain regions only — the probe schematic moved to B (user request, 2026-07-30,
  to make A visually smaller/less dominant relative to the rest of the figure).
- **Panel B facts, sourced (not invented):**
  - 128-ch DiagnosticBioChips laminar probes, 30 kHz acquisition (Intan RHD) — stated verbatim
    in `context/drafts/omission-a-draft-v1.md` and `omission-a-draft-v2.md`.
  - LFP stored at 1000 Hz — independently confirmed from NWB data (`median(diff(timestamps))`
    on `acquisition/probe_0_lfp`, `sub-C31o_ses-230816_rec.nwb`), 2026-07-30.
  - Behavioral control: Monkeylogic (NIMH) — already stated in the paradigm source.
  - Eye position tracked — `acquisition/eye_1_tracking` channel confirmed present in NWB; no
    specific device/brand is recorded in NWB metadata, so none is named.
  - Screen distance/size/resolution — read directly from
    `intervals/omission_glo_passive/{distance_to_screen,screen_width,screen_height,
    screen_res_width,screen_res_height}`: 1130 / 1000 x 550 / 1920x1080. No unit attribute is
    stored on these fields — reported as raw config values with units marked unconfirmed.
- **The S+/S-/O+ functional-group trace mockup and the trial-timeline diagram
  (fx-p1-d1-p2...) are both dropped from this figure** (2026-07-30 choices, not since
  reinstated) — the trace mockup was never real data (real population traces live in figure
  3's RXRR template trace panel).

## Rendering caveat

`cairosvg` is broken on this machine (missing native cairo library) and `svglib`'s own PNG
backend also fails (`_rl_renderPM` missing) — `fig01.png` is produced via `svglib` → PDF →
`pymupdf` (PDF → PNG) instead. **`fig01.svg` itself, opened in a real browser, is the
authoritative rendering.** `svglib` has repeatedly proven unreliable for THIS figure's specific
feature set across several earlier pipeline revisions (`<pattern>` fills not applied, non-rect
`clipPath`s not applied, nested-`<svg>` viewports not clipped) — the current pipeline no longer
depends on any of those three features at placement time (plain `<image>` for panels A/B, tiny
single-icon inlined `<svg>` for panel C's grid), so `fig01.png` should be more trustworthy than
prior revisions, but has not been re-verified against `svglib`'s specific quirks as thoroughly
as the SVG itself has against a real browser — treat any `fig01.png`/`fig01.svg` visual
disagreement as evidence about `svglib`, not about `fig01.svg`, unless independently confirmed
otherwise.

## History

- 2026-07-30: panel C was three crops of a single flattened raster `<image>` in
  `02_paradigm.svg` (1650x1492 source px covering all three grids; AAAB/BBBA side by side,
  RRRR below both). Empirically-tuned crop boundaries left small artifacts (a few px of the
  trial-timeline diagram's tail bleeding into the AB row). Fully superseded 2026-07-31 by the
  native-vector approach above — none of this raster-crop machinery remains.
- `svg/UNUSABLE...` equivalents: the S+/S-/O+ functional-group trace panel that used to sit in
  `02_paradigm.svg`'s bottom-right quadrant was a mockup, not real data (flagged by the user
  2026-07-29 with a red X annotation directly on the rendered figure) — real population traces
  now live in figure 3's RXRR template trace panel.
- 2026-07-29: two-panel "A over B" layout, panel A shrunk via `PANEL_A_HEIGHT_SCALE`, panel B's
  trace mockup excluded via an L-shaped clip. Superseded by the three-panel redesign
  (2026-07-30), itself since revised as described above.

## Output

Run `build_parts.py` first (writes `artifacts/madelane.png`, `artifacts/dbc128.png`,
`artifacts/grating45.svg`, `artifacts/grating135.svg`), then
`fig01_recording_topology_and_paradigm.py` (assembles those artifacts plus the user-supplied
`artifacts/macaque.png`, writes `fig01.svg`, `fig01.png` — see rendering caveat above — and
`fig01.receipt.json`).
