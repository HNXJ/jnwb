r"""
Circular grating stimulus icon, as native SVG (not a raster).

Replaces the crude diamond/square raster stripe icons currently baked into the Illustrator
paradigm source (context/figures/fig01_recording_topology_and_paradigm/svg/02_paradigm.svg)
with a clean vector circular grating: a true circular aperture (matching the stimulus info
box's "Radius = 12 vd" -- the real stimulus is a circular patch, not a diamond) containing a
square-wave stripe pattern at a settable spatial frequency and orientation.

Not yet wired into any figure -- this is the icon generator only, rendered standalone for
review. See build_demo() / __main__ for a rendered sample sheet.
"""
from __future__ import annotations

import hashlib
import math
import re


def circular_grating(
    cx: float,
    cy: float,
    r: float,
    n_cycles: float = 4.0,
    orientation_deg: float = 45.0,
    stripe_color: str = "#1a1a1a",
    bg_color: str = "#ffffff",
    duty_cycle: float = 0.5,
    outline: bool = True,
    outline_color: str = "#1a1a1a",
    outline_width: float = 1.2,
    uid: str = "g",
) -> str:
    """One circular grating icon: a plain <circle>, filled with a repeating stripe
    <pattern> instead of a clipped stack of rotated rects. A circle's own fill region IS
    its boundary, so this needs no clipPath at all -- replaces an earlier version that
    built the aperture from ~15-20 individually rotated <rect> stripes inside a
    <clipPath>-clipped <g>, which is not what a grating actually is (a grating is one
    shape with a repeating fill, not a pile of separately-clipped rectangles) and was also
    the source of a real rendering bug: svglib and PyMuPDF's native SVG engine both fail to
    apply circular (non-rect) clipPaths, leaving every stripe unclipped. A pattern fill
    sidesteps that failure mode entirely rather than working around it.
    n_cycles = number of full light+dark stripe pairs across the aperture's diameter.
    duty_cycle = fraction of each cycle that is the stripe (vs background) -- 0.5 gives an
    even square wave, matching the corpus's actual stimuli (project CLAUDE.md: "Contrast =
    0.8", "Spatial freq. = 1 cycle/vd" -- this icon is schematic, not a literal render of
    the physical stimulus, so n_cycles is chosen for legibility at icon size).
    """
    period = (2.0 * r) / n_cycles
    stripe_w = period * duty_cycle
    pat_id = f"pat-{uid}"

    pattern = (
        f'<defs><pattern id="{pat_id}" patternUnits="userSpaceOnUse" '
        f'width="{period:.4f}" height="{period:.4f}" '
        f'patternTransform="rotate({orientation_deg:.2f} {cx:.3f} {cy:.3f})">\n'
        f'<rect width="{period:.4f}" height="{period:.4f}" fill="{bg_color}"/>\n'
        f'<rect width="{stripe_w:.4f}" height="{period:.4f}" fill="{stripe_color}"/>\n'
        f'</pattern></defs>\n'
    )
    g = (pattern +
        f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" fill="url(#{pat_id})"/>\n'
    )
    if outline:
        g += (f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" fill="none" '
             f'stroke="{outline_color}" stroke-width="{outline_width}"/>\n')
    return g


# Stimulus-identity convention, locked 2026-07-30: A-family stimuli (AAAB/AXAB/AAXB/AAAX)
# drawn at 45 deg, B-family (BBBA/BXBA/BBXA/BBBX) at 135 deg (orthogonal to A, maximally
# discriminable at a glance), both at 4 cycles across the aperture. R-family (RRRR/RXRR/RRXR/
# RRRX) has no fixed orientation here -- "R" is the random-control family by construction, so
# a single fixed orientation would misrepresent it as a third identity rather than a mix of
# the other two; pass an explicit orientation per R icon instead of using IDENTITY_ORIENTATION_DEG.
IDENTITY_ORIENTATION_DEG = {"A": 45.0, "B": 135.0}
IDENTITY_N_CYCLES = 4.0


def identity_grating(identity: str, cx: float, cy: float, r: float, uid: str, **kwargs) -> str:
    """circular_grating() pre-set to the locked A/B orientation convention above. identity
    must be 'A' or 'B' -- R has no fixed orientation, see IDENTITY_ORIENTATION_DEG's comment."""
    if identity not in IDENTITY_ORIENTATION_DEG:
        raise ValueError(f"identity_grating() only defines A/B, got {identity!r} -- R-family "
                         "icons need an explicit orientation via circular_grating() directly")
    return circular_grating(cx, cy, r, n_cycles=IDENTITY_N_CYCLES,
                            orientation_deg=IDENTITY_ORIENTATION_DEG[identity], uid=uid, **kwargs)


def omission_marker(cx: float, cy: float, r: float, color: str = "#d4000b") -> str:
    """Dashed-circle placeholder for an omitted stimulus (matches the existing paradigm
    figure's "(Omission scene)" dashed marker), as a circular-aperture-consistent companion
    to circular_grating() -- same radius convention, so it drops into the same icon slot."""
    return (f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" fill="none" '
           f'stroke="{color}" stroke-width="1.4" stroke-dasharray="4,3"/>')


# R-family (RRRR/RXRR/RRXR/RRRX) representation. Corrected 2026-07-31 (user): "R" does NOT
# mean each trial gets its own random orientation angle -- R means P(identity=A) = P(identity
# =B) = 0.5 per trial. So each R icon is drawn at EXACTLY one of the two real identity
# orientations (45deg or 135deg, IDENTITY_ORIENTATION_DEG), chosen per cell by a deterministic
# 50/50 draw (sha256-based, see _seeded_ab_choice) -- not a third, continuous "random angle"
# family, which would misrepresent the actual design. Muted grey (not the A/B black) keeps R
# cells visually distinct as "identity drawn at random" while the drawn grating itself is a
# real A or B stimulus, exactly as presented on an R trial.
R_COLOR = "#8a8a8a"


def _seeded_ab_choice(uid: str) -> str:
    """Deterministic 50/50 choice between 'A' and 'B' derived from uid alone -- reproducible
    across runs without depending on global RNG state or call order."""
    digest = hashlib.sha256(uid.encode("utf-8")).hexdigest()
    frac = int(digest[:8], 16) / 0xFFFFFFFF
    return "A" if frac < 0.5 else "B"

# Sized 2026-07-31 to fit fig01's Panel C at a legible shared width alongside Panel A/B --
# the first pass (CELL_R=18 etc, sized for the standalone grating_panel_c.svg demo) produced
# a panel too tall relative to its width (height:width 1.67) for fig01's page-height budget,
# forcing the whole figure down to 55% of the text column's width. These values bring Panel
# C's own aspect down to ~1.09, close enough to Panel A/B's own ~0.56 that the shared-width
# solve in fig01_recording_topology_and_paradigm.py lands near 75% of the text column, in
# line with the pre-vector raster version's 76%.
CELL_R = 10.0          # icon radius inside each grid cell
CELL_GAP = 6.0          # gap between adjacent icons in a row
ROW_GAP = 3.0           # gap between rows within one box (standard or omission)
BOX_GAP = 6.0           # gap between the standard box and the omission box
GRID_GAP = 10.0         # gap between Block type 1/2/3
LABEL_H = 11.0          # space for each box's own percentage label


def _icon(cell, cx, cy, r, uid):
    if cell == "omit":
        return omission_marker(cx, cy, r)
    if cell == "R":
        drawn = _seeded_ab_choice(uid)
        return circular_grating(cx, cy, r, n_cycles=IDENTITY_N_CYCLES,
                                orientation_deg=IDENTITY_ORIENTATION_DEG[drawn],
                                stripe_color=R_COLOR, outline_color=R_COLOR, uid=uid)
    return identity_grating(cell, cx, cy, r, uid=uid)


def _grid_box(x0, y0, width, cell_rows, box_color, label_text, mark_char, mark_positions,
             uid_prefix):
    """One bordered box (standard or omission) -- cell_rows is a list of 4-cell rows, each
    cell 'A'/'B'/'R'/'omit'. mark_positions[i] gives the column index to draw mark_char next
    to in row i (or None), matching the original figure's */# glyphs beside the omitted icon.
    uid_prefix must be unique to the caller (block title + box kind) -- every icon's clipPath
    id is derived from it, and duplicate ids across separate <g> groups in the SAME document
    resolve to whichever definition appears first, silently misapplying that first icon's clip
    circle to every later icon sharing the id (confirmed 2026-07-31: block_type_row() calling
    _grid_box() with the bare literal "Standard trials"/"Omission trials" for all three block
    types produced colliding ids across rows before this parameter was added)."""
    n_rows = len(cell_rows)
    row_h = 2 * CELL_R
    box_h = LABEL_H + n_rows * row_h + (n_rows - 1) * ROW_GAP + 6
    parts = [f'<text x="{x0 + width/2:.1f}" y="{y0 + 11:.1f}" font-size="10.5" '
            f'font-family="Arial" fill="#1414c8" text-anchor="middle">{label_text}</text>']
    parts.append(f'<rect x="{x0:.2f}" y="{y0 + LABEL_H:.2f}" width="{width:.2f}" '
                f'height="{box_h - LABEL_H:.2f}" fill="none" stroke="{box_color}" '
                f'stroke-width="1.1"/>')
    cell_w = width / 4.0
    for ri, cells in enumerate(cell_rows):
        cy = y0 + LABEL_H + 3 + ri * (row_h + ROW_GAP) + CELL_R
        for ci, cell in enumerate(cells):
            cx = x0 + ci * cell_w + cell_w / 2.0
            parts.append(_icon(cell, cx, cy, CELL_R, uid=f"{uid_prefix}-{ri}-{ci}"))
            if mark_positions and mark_positions[ri] == ci:
                parts.append(f'<text x="{cx + CELL_R * 0.5:.1f}" y="{cy - CELL_R * 0.6:.1f}" '
                            f'font-size="12" font-family="Arial">{mark_char}</text>')
    return "\n".join(parts), box_h


def block_type_row(x0, y0, width, title, standard_cells, omission_rows, mark_char,
                   std_label="Standard trials (70%)", om_label="Omission trials (30%)"):
    """One full block-type row: title, standard box (1 row), omission box (3 rows).
    omission_rows: list of (cells, omit_col_index). std_label/om_label default to the A/B
    families' own percentages (70/30, matching the original Illustrator figure's labels);
    the RRRR (random-control) call below overrides both to 50/50."""
    parts = [f'<text x="{x0:.1f}" y="{y0 + 12:.1f}" font-size="13" font-weight="bold" '
            f'font-family="Arial" fill="#1414c8">{title}</text>']
    uid_base = re.sub(r'[^A-Za-z0-9]+', '-', title).strip('-')
    y = y0 + 20
    std_svg, std_h = _grid_box(x0, y, width, [standard_cells], "#1a9e5a",
                              std_label, None, [None], uid_prefix=f"{uid_base}-std")
    parts.append(std_svg)
    y += std_h + BOX_GAP
    om_cells = [r[0] for r in omission_rows]
    om_marks = [r[1] for r in omission_rows]
    om_svg, om_h = _grid_box(x0, y, width, om_cells, "#d4000b",
                            om_label, mark_char, om_marks, uid_prefix=f"{uid_base}-om")
    parts.append(om_svg)
    y += om_h
    return "\n".join(parts), y - y0


def panel_c_fragment(width: float, x0: float = 10.0, y0: float = 10.0) -> tuple[str, float]:
    """The three block-type rows' content only (no outer <svg>/background) -- factored out
    of build_panel_c() so fig01_recording_topology_and_paradigm.py can embed it directly as a
    <g> inside the assembled figure instead of placing a whole standalone SVG document.
    Returns (joined SVG fragment, total content height from y0).

    Laid out as THREE COLUMNS (block types 1/2/3 side by side), not three stacked full-width
    rows -- changed 2026-07-31 (user: "too much whitespace", target a 6:5 width:height figure)
    since three full-width rows makes panel C tall and narrow, exactly wrong for a landscape
    canvas. Column width forces shorter titles/labels than the stacked version used (no room
    for "Block type 3 (RRRR, random control)" or "Standard random control trials (50%)" at
    140pt column width, 13pt/10.5pt fonts) -- shortened without dropping any information
    (percentages and the RRRR/random-control identity are still both stated, just tighter)."""
    colw = (width - 2 * GRID_GAP) / 3.0
    parts = []

    g1, h1 = block_type_row(x0, y0, colw, "1: AAAB",
                            ["A", "A", "A", "B"],
                            [(["A", "omit", "A", "B"], 1),
                             (["A", "A", "omit", "B"], 2),
                             (["A", "A", "A", "omit"], 3)], "*",
                            std_label="Standard (70%)", om_label="Omission (30%)")
    parts.append(g1)

    g2, h2 = block_type_row(x0 + colw + GRID_GAP, y0, colw, "2: BBBA",
                            ["B", "B", "B", "A"],
                            [(["B", "omit", "B", "A"], 1),
                             (["B", "B", "omit", "A"], 2),
                             (["B", "B", "B", "omit"], 3)], "*",
                            std_label="Standard (70%)", om_label="Omission (30%)")
    parts.append(g2)

    g3, h3 = block_type_row(x0 + 2 * (colw + GRID_GAP), y0, colw, "3: RRRR (random)",
                            ["R", "R", "R", "R"],
                            [(["R", "omit", "R", "R"], 1),
                             (["R", "R", "omit", "R"], 2),
                             (["R", "R", "R", "omit"], 3)], "#",
                            std_label="Standard (50%)", om_label="Omission (50%)")
    parts.append(g3)

    h = max(h1, h2, h3)
    return "\n".join(parts), h + 10.0


def build_panel_c(out_path: str, width: float = 440.0) -> None:
    """The definitive vector replacement for fig01 Panel C: three full-width block-type rows
    (AAAB-family, BBBA-family, RRRR-family), each a standard box + a 3-variant omission box,
    built entirely from circular_grating()/omission_marker() -- no raster crop of the old
    Illustrator source. Percentages (70/30 for A and B, 50/50 for R) match the original
    figure's own labels. Standalone-review wrapper around panel_c_fragment()."""
    content, height = panel_c_fragment(width)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width + 20:.1f}" '
          f'height="{height:.1f}" viewBox="0 0 {width + 20:.1f} {height:.1f}">\n'
          f'<rect width="{width + 20:.1f}" height="{height:.1f}" fill="#ffffff"/>\n'
          + content + "\n</svg>\n")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {out_path}  {width + 20:.0f}x{height:.0f}")


def build_demo(out_path: str) -> None:
    """Render a sample sheet: orientation and spatial-frequency variants, plus the omission
    marker, so the icon can be reviewed before it replaces anything in a real figure."""
    icons = []
    r = 40.0
    x = r + 10
    y = r + 10
    row_gap = 2 * r + 30

    # Row 1: orientation sweep at fixed n_cycles
    for i, orient in enumerate([0, 45, 90, 135]):
        cx = x + i * (2 * r + 20)
        icons.append(circular_grating(cx, y, r, n_cycles=4, orientation_deg=orient,
                                      uid=f"orient{i}"))
        icons.append(f'<text x="{cx:.1f}" y="{y + r + 16:.1f}" font-size="10" '
                    f'text-anchor="middle" font-family="Arial">{orient} deg</text>')

    # Row 2: spatial-frequency sweep at fixed 45-degree orientation
    y2 = y + row_gap
    for i, nc in enumerate([2, 4, 6, 8]):
        cx = x + i * (2 * r + 20)
        icons.append(circular_grating(cx, y2, r, n_cycles=nc, orientation_deg=45,
                                      uid=f"freq{i}"))
        icons.append(f'<text x="{cx:.1f}" y="{y2 + r + 16:.1f}" font-size="10" '
                    f'text-anchor="middle" font-family="Arial">{nc} cycles</text>')

    # Row 3: the omission marker next to a real grating, same size/slot
    y3 = y2 + row_gap
    icons.append(circular_grating(x, y3, r, n_cycles=4, orientation_deg=45, uid="real"))
    icons.append(f'<text x="{x:.1f}" y="{y3 + r + 16:.1f}" font-size="10" '
                f'text-anchor="middle" font-family="Arial">real</text>')
    cx2 = x + (2 * r + 20)
    icons.append(omission_marker(cx2, y3, r))
    icons.append(f'<text x="{cx2:.1f}" y="{y3 + r + 16:.1f}" font-size="10" '
                f'text-anchor="middle" font-family="Arial">omitted</text>')

    width = 4 * (2 * r + 20) + 20
    height = y3 + r + 30
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
          f'viewBox="0 0 {width} {height}">\n<rect width="{width}" height="{height}" '
          f'fill="#fafafa"/>\n' + "\n".join(icons) + "\n</svg>\n")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {out_path}  {width:.0f}x{height:.0f}")


def build_identity_demo(out_path: str) -> None:
    """Preview the locked A(45deg)/B(135deg), 4-cycle convention in context: two trial
    sequences (AAAB and AXAB, the standard and one omission variant of the A family), so the
    icons can be reviewed as they would actually appear in a sequence, not just in isolation."""
    icons = []
    r = 30.0
    gap = 2 * r + 16
    x0 = r + 10

    def row(y, cells, row_label):
        icons.append(f'<text x="6" y="{y + 4:.1f}" font-size="11" font-family="Arial" '
                    f'font-weight="bold">{row_label}</text>')
        for i, cell in enumerate(cells):
            cx = x0 + 70 + i * gap
            if cell == "omit":
                icons.append(omission_marker(cx, y, r))
            else:
                icons.append(identity_grating(cell, cx, y, r, uid=f"{row_label}-{i}"))

    y = r + 14
    row(y, ["A", "A", "A", "B"], "AAAB")
    y += gap
    row(y, ["A", "omit", "A", "B"], "AXAB")
    y += gap
    row(y, ["B", "B", "B", "A"], "BBBA")
    y += gap
    row(y, ["B", "omit", "B", "A"], "BXBA")

    width = x0 + 70 + 4 * gap
    height = y + r + 14
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
          f'viewBox="0 0 {width} {height}">\n<rect width="{width}" height="{height}" '
          f'fill="#fafafa"/>\n' + "\n".join(icons) + "\n</svg>\n")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {out_path}  {width:.0f}x{height:.0f}")


if __name__ == "__main__":
    build_demo("grating_demo.svg")
    build_identity_demo("grating_identity_demo.svg")
    build_panel_c("grating_panel_c.svg")
