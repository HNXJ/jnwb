r"""
Assemble manuscript Figure 1 from isolated, tightly-cropped sub-panel artifacts, using FIXED
absolute constants (margins, gaps, icon size) plus RELATIVE offsets computed from them --
NOT a system of aspect-ratio equations solved for a shared width (the previous two approaches
this script used). User, 2026-07-31: "use fixed + relative coordination."

ARTIFACTS (built once by build_parts.py, not re-derived here)
    artifacts/madelane.png    brain + area labels, no title/panel-label (raster, trimmed)
    artifacts/dbc128.png      probe schematic (raster, trimmed)
    artifacts/grating45.svg   ONE circular-grating icon at 45deg ("A" identity), tightly cropped
    artifacts/grating135.svg  ONE circular-grating icon at 135deg ("B" identity), tightly cropped

PANELS
    A = artifacts/madelane.png, placed at a FIXED width; height follows from the image's own
        aspect ratio (relative). Title + panel label "a" are native text, not baked into the
        image.
    B = artifacts/dbc128.png ONLY -- probe schematic, same fixed height as panel A, centered
        in its own column (2026-08-21: fact text and species icon removed).
    C = the three block-type grids (AAAB/BBBA/RRRR), as three columns, built by placing
        grating45.svg/grating135.svg repeatedly on a FIXED cell grid (CELL_W/ROW_H/ICON_R are
        all fixed constants; column and row positions are RELATIVE offsets from those
        constants, not solved). R-family cells reuse the same two icon files through a shared
        greyscale SVG filter (grating_filter()) rather than needing separate grey artifacts --
        R means a 50/50 draw between the two REAL identities (P(A)=P(B)=0.5), never a third
        orientation (see _seeded_ab_choice below, same rule fig01 has used since 2026-07-31).

GEOMETRY
    Canvas is fixed at 468 x 390 pt (6:5 width:height, matching the text column width).

OUTPUT
    context/figures/fig01_recording_topology_and_paradigm/fig01.svg
    context/figures/fig01_recording_topology_and_paradigm/fig01.receipt.json
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from PIL import Image

FIG_DIR = os.path.dirname(os.path.abspath(__file__))
ART_DIR = os.path.join(FIG_DIR, "artifacts")
OUT_DIR = FIG_DIR

sys.path.insert(0, os.path.dirname(FIG_DIR))   # context/figures/, holds figstyle.py
from figstyle import SLOT_COLORS, full_trial_ticks  # noqa: E402  -- p1 yellow/p2 pink/p3
                                  # green/p4 blue, the SAME four colors figures 2/3's
                                  # full-trial slot shading already uses (mark_full_trial_axis)
                                  # -- imported, not copied, so the two can't drift apart
                                  # (user, 2026-07-31:
                                  # panel C should be "similar and related to later figures
                                  # which have these colors and shades")

# --- FIXED constants ----------------------------------------------------------------------
CANVAS_W = 468.0
CANVAS_H = 390.0          # 6:5 (user, 2026-07-31)
MARGIN_GAP = 8.0          # gap between major panels (A|B row -> C row)
FONT_FAMILY = "Cambria, Georgia, serif"
FONT_PT = 8.5
TITLE_PT = 11.0

PANEL_A_W = 300.0         # fixed; panel A's height follows from madelane.png's own aspect --
                          # tuned once (250->300) so total canvas height lands near the 6:5
                          # target (390pt at 468pt wide) without solving for it

ICON_R = 12.5             # fixed on-page icon radius -- bumped from 10.5 (2026-07-31, user:
                          # "reduce whitespace"): icons were much smaller than their grid
                          # cells, leaving visibly dead space inside every box
ROW_GAP = 3.0             # fixed gap between stacked rows within one box
BOX_GAP = 6.0             # fixed gap between the standard box and the omission box
COL_GAP = 10.0            # fixed gap between the three block-type columns
LABEL_H = 11.0            # fixed space for each box's own title/percentage label
TITLE_H = 16.0            # fixed space for each column's own "1: AAAB" title

ROW_H = 2 * ICON_R

# Identity convention locked 2026-07-30/31: A=45deg, B=135deg. R-family: 50/50 draw between
# the same two real icons (not a third orientation), rendered desaturated. Deterministic so
# re-running this script reproduces the same figure.
GREY_FILTER_ID = "grey-r"


def _seeded_ab_choice(uid: str) -> str:
    digest = hashlib.sha256(uid.encode("utf-8")).hexdigest()
    frac = int(digest[:8], 16) / 0xFFFFFFFF
    return "A" if frac < 0.5 else "B"


def png_size(name: str) -> tuple[int, int]:
    with Image.open(os.path.join(ART_DIR, name)) as im:
        return im.size


def png_data_uri(name: str) -> str:
    """Base64-embed the PNG directly in fig01.svg -- a relative <image href="artifacts/...">
    was tried first and silently failed to load in the Claude_Browser preview pane (confirmed
    2026-07-31: an absolute file:// href loaded fine, a relative one did not, so the preview
    tool's local-file serving does not resolve relative image hrefs against the SVG's own
    location the way a normal browser tab does). An absolute path is not portable across
    machines/checkouts, so embed the bytes instead -- self-contained, matches how the original
    Illustrator sources already embed their own raster images, and sidesteps path resolution
    entirely."""
    with open(os.path.join(ART_DIR, name), "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


_ICON_CACHE: dict[str, tuple[str, tuple[float, float, float, float]]] = {}


def load_icon(name: str):
    if name not in _ICON_CACHE:
        with open(os.path.join(ART_DIR, name), encoding="utf-8") as fh:
            svg = fh.read()
        import re
        m = re.search(r'viewBox="([\d.\-eE]+)\s+([\d.\-eE]+)\s+([\d.\-eE]+)\s+([\d.\-eE]+)"', svg)
        vb = tuple(float(v) for v in m.groups())
        a = svg.index(">", svg.index("<svg")) + 1
        b = svg.rindex("</svg>")
        _ICON_CACHE[name] = (svg[a:b], vb)
    return _ICON_CACHE[name]


def place_icon(identity: str, cx: float, cy: float, r: float, uid: str, grey: bool = False) -> str:
    """Place one grating icon (identity 'A' or 'B') centred at (cx,cy) with radius r, inlined
    as a nested <svg viewBox> (clips per spec -- see fig01's own history of a bare <g
    transform> NOT clipping). grey=True desaturates it for R-family cells via a shared filter."""
    name = "grating45.svg" if identity == "A" else "grating135.svg"
    content, (vx, vy, vw, vh) = load_icon(name)
    s = (2 * r) / vw
    x, y = cx - r, cy - r
    filt = f' filter="url(#{GREY_FILTER_ID})"' if grey else ""
    return (f'<svg x="{x:.3f}" y="{y:.3f}" width="{2*r:.3f}" height="{2*r:.3f}" '
           f'viewBox="{vx:.3f} {vy:.3f} {vw:.3f} {vh:.3f}"{filt}>\n{content}\n</svg>')


def omission_marker(cx: float, cy: float, r: float) -> str:
    return (f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" fill="none" '
           f'stroke="#d4000b" stroke-width="1.2" stroke-dasharray="3,2.2"/>')


def icon_cell(cell: str, cx: float, cy: float, r: float, uid: str) -> str:
    if cell == "omit":
        return omission_marker(cx, cy, r)
    if cell == "R":
        return place_icon(_seeded_ab_choice(uid), cx, cy, r, uid, grey=True)
    return place_icon(cell, cx, cy, r, uid)


def grid_box(x0: float, y0: float, width: float, cell_rows: list[list[str]], box_color: str,
            label_text: str, mark_char: str | None, mark_positions: list[int | None],
            uid_prefix: str) -> tuple[str, float]:
    n_rows = len(cell_rows)
    box_h = LABEL_H + n_rows * ROW_H + (n_rows - 1) * ROW_GAP + 6.0
    parts = [f'<text x="{x0 + width/2:.1f}" y="{y0 + 9:.1f}" font-size="7.2" '
            f'font-family="Arial" fill="#1414c8" text-anchor="middle">{label_text}</text>',
            f'<rect x="{x0:.2f}" y="{y0 + LABEL_H:.2f}" width="{width:.2f}" '
            f'height="{box_h - LABEL_H:.2f}" fill="none" stroke="{box_color}" stroke-width="1"/>']
    cell_w = width / 4.0
    for ri, cells in enumerate(cell_rows):
        cy = y0 + LABEL_H + 3 + ri * (ROW_H + ROW_GAP) + ICON_R
        for ci, cell in enumerate(cells):
            cx = x0 + ci * cell_w + cell_w / 2.0
            parts.append(icon_cell(cell, cx, cy, ICON_R, uid=f"{uid_prefix}-{ri}-{ci}"))
            if mark_positions and mark_positions[ri] == ci:
                parts.append(f'<text x="{cx + ICON_R * 0.5:.1f}" y="{cy - ICON_R * 0.6:.1f}" '
                            f'font-size="8" font-family="Arial">{mark_char}</text>')
    return "\n".join(parts), box_h


def slot_background(x0: float, y0: float, width: float, height: float) -> str:
    """The p1/p2/p3/p4 SLOT_COLORS bands behind a block column's icon grid -- user, 2026-07-31:
    give panel C "this as its background so it would then both show that screen layout; and be
    similar and related to later figures which have these colors and shades." SLOT_COLORS is
    figstyle.py's own p1-p4 palette (yellow/pink/green/blue), the SAME one figures 2/3's
    full-trial slot shading uses -- drawn BEHIND the grid boxes/icons (caller must emit this
    before them) so the icons stay legible on top. The hatched header strip this originally
    also drew was removed per direct user feedback the same day ("remove that strip")."""
    cell_w = width / 4.0
    parts = []
    for ci, color in enumerate(SLOT_COLORS):
        cx = x0 + ci * cell_w
        parts.append(f'<rect x="{cx:.2f}" y="{y0:.2f}" width="{cell_w:.2f}" '
                    f'height="{height:.2f}" fill="{color}" opacity="0.55"/>')
    return "\n".join(parts)


# Trial-timing tick row under each block column -- user, 2026-07-31, reference image: a
# diagonal-label timeline ("-500ms - fx", "0ms - p1", ... "4124ms - end") repeated under each
# of three dash-dot-separated groups, matching panel C's three block-type columns exactly.
# Labels/order come from figstyle.full_trial_ticks() (not re-derived) so they can't drift from
# figures 2/3's own trial-timing axis. Text color per epoch echoes slot_background()'s own
# p1-p4 SLOT_COLORS family (darkened for legibility as text), grey for delays/fx/end.
TICK_ROW_H = 30.0
TICK_FONT_PT = 4.6
TICK_ROTATE_DEG = 45.0    # POSITIVE -- SVG's y-axis points down, so rotate(+deg) sends text
                          # down-and-right from its anchor, rotate(-deg) sends it up-and-right.
                          # A first pass used -40 and the text climbed back UP into the
                          # omission box above it (confirmed by rendering, 2026-07-31 -- user:
                          # "the times are overlapping with figure"). Always positive here --
                          # asserted, not just commented, so this can't silently regress.
assert 0 < TICK_ROTATE_DEG < 180, "TICK_ROTATE_DEG must stay positive or rotated text climbs " \
    "back up into whatever sits above this row (see comment above)"
EPOCH_TEXT_COLORS = {
    "fx": "#666666", "p1": "#8A6D00", "d1": "#888888", "p2": "#C2185B", "d2": "#888888",
    "p3": "#2E7D32", "d3": "#888888", "p4": "#1565C0", "d4": "#888888", "end": "#888888",
}


def timeline_row(x0: float, y0: float, width: float) -> str:
    """Draws entirely within y in [y0, y0 + TICK_ROW_H] -- the tick line starts AT y0 (the
    caller's reserved top edge for this row) and the rotated label text starts a few pt below
    that and angles further down-and-right, so nothing in this function ever draws above y0
    into whatever the caller placed there."""
    ticks, labels = full_trial_ticks()
    order = ["fx", "p1", "d1", "p2", "d2", "p3", "d3", "p4", "d4", "end"]
    cell_w = width / len(labels)
    parts = []
    for i, (lab, ep) in enumerate(zip(labels, order)):
        cx = x0 + i * cell_w + cell_w / 2.0
        color = EPOCH_TEXT_COLORS[ep]
        text_y = y0 + 6.0
        parts.append(f'<line x1="{cx:.2f}" y1="{y0:.2f}" x2="{cx:.2f}" y2="{text_y:.2f}" '
                    f'stroke="{color}" stroke-width="0.8"/>')
        parts.append(f'<text x="{cx:.2f}" y="{text_y:.2f}" font-size="{TICK_FONT_PT}" '
                    f'font-family="Arial" fill="{color}" '
                    f'transform="rotate({TICK_ROTATE_DEG:.1f} {cx:.2f} {text_y:.2f})">{lab}</text>')
    return "\n".join(parts)


def block_column(x0: float, y0: float, width: float, title: str, standard: list[str],
                 omission_rows: list[tuple[list[str], int]], mark_char: str,
                 std_label: str, om_label: str) -> tuple[str, float]:
    uid_base = title.replace(" ", "").replace(":", "-").replace("(", "").replace(")", "")
    y = y0 + TITLE_H
    std_svg, std_h = grid_box(x0, y, width, [standard], "#1a9e5a", std_label, None,
                             [None], uid_prefix=f"{uid_base}-std")
    om_cells = [r[0] for r in omission_rows]
    om_marks = [r[1] for r in omission_rows]
    om_svg, om_h = grid_box(x0, y + std_h + BOX_GAP, width, om_cells, "#d4000b",
                           om_label, mark_char, om_marks, uid_prefix=f"{uid_base}-om")
    bg_h = std_h + BOX_GAP + om_h
    parts = [
        slot_background(x0, y, width, bg_h),
        f'<text x="{x0:.1f}" y="{y0 + 10:.1f}" font-size="9" font-weight="bold" '
        f'font-family="Arial" fill="#1414c8">{title}</text>',
        std_svg, om_svg,
        timeline_row(x0, y + bg_h + 3.0, width),
    ]
    return "\n".join(parts), (y + bg_h + 3.0 + TICK_ROW_H) - y0


def panel_c(x0: float, y0: float, width: float) -> tuple[str, float]:
    col_w = (width - 2 * COL_GAP) / 3.0
    specs = [
        ("1: AAAB", ["A", "A", "A", "B"],
         [(["A", "omit", "A", "B"], 1), (["A", "A", "omit", "B"], 2), (["A", "A", "A", "omit"], 3)],
         "*", "Standard (70%)", "Omission (30%)"),
        ("2: BBBA", ["B", "B", "B", "A"],
         [(["B", "omit", "B", "A"], 1), (["B", "B", "omit", "A"], 2), (["B", "B", "B", "omit"], 3)],
         "*", "Standard (70%)", "Omission (30%)"),
        ("3: RRRR (random)", ["R", "R", "R", "R"],
         [(["R", "omit", "R", "R"], 1), (["R", "R", "omit", "R"], 2), (["R", "R", "R", "omit"], 3)],
         "#", "Standard (50%)", "Omission (50%)"),
    ]
    parts, heights = [], []
    for i, (title, std, om, mark, sl, ol) in enumerate(specs):
        x = x0 + i * (col_w + COL_GAP)
        svg, h = block_column(x, y0, col_w, title, std, om, mark, sl, ol)
        parts.append(svg)
        heights.append(h)
    max_h = max(heights)
    # Dash-dot dividers between the three block-type columns, matching the reference image's
    # own group separators (user, 2026-07-31) -- span the colored-background region only
    # (y0+TITLE_H to y0+max_h), not the title row above it.
    for i in range(1, 3):
        dx = x0 + i * (col_w + COL_GAP) - COL_GAP / 2.0
        parts.append(f'<line x1="{dx:.2f}" y1="{y0 + TITLE_H:.2f}" x2="{dx:.2f}" '
                    f'y2="{y0 + max_h:.2f}" stroke="#B8860B" stroke-width="1" '
                    f'stroke-dasharray="4,2,1,2"/>')
    return "\n".join(parts), max_h


def label(x, y, txt, size=13):
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-family="{FONT_FAMILY}" '
            f'font-size="{size}" font-weight="bold" fill="#000">{txt}</text>')


def build():
    a_w, a_h = png_size("madelane.png")
    b_w, b_h = png_size("dbc128.png")

    x0 = (CANVAS_W - CANVAS_W) / 2.0  # 0 -- kept for symmetry with earlier revisions
    y = TITLE_H

    # Panel letters (a/b/c) sit in the small gap ABOVE each panel's own content, not on top of
    # it -- placing them at the same y as the panel content (tried first) put "a" over the
    # brain image's own baked "8a & FEF" label and fused "c" into the "1: AAAB" column title
    # (confirmed by rendering, 2026-07-31). PANEL_LETTER_Y sits just above y=TITLE_H, where
    # panels A/B's images start.
    PANEL_LETTER_Y = TITLE_H - 3.0
    parts = [
        f'<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<defs>'
        f'<filter id="{GREY_FILTER_ID}"><feColorMatrix type="saturate" values="0.15"/>'
        f'<feComponentTransfer><feFuncA type="linear" slope="0.85"/></feComponentTransfer>'
        f'</filter>'
        f'</defs>',
        label(2, PANEL_LETTER_Y, "a", size=10),
    ]

    # --- Panel A: brain regions (fixed width, relative height from the image's own aspect) ----
    height_A = PANEL_A_W * (a_h / a_w)
    parts.append(f'<g id="panel-a-recording-topology" inkscape:label="a. recording topology">\n'
                f'<image href="{png_data_uri("madelane.png")}" x="0" y="{y:.3f}" '
                f'width="{PANEL_A_W:.3f}" height="{height_A:.3f}"/>\n</g>')

    # --- Panel B: probe schematic ONLY -- no fact text, no species icon ----------------------
    # 2026-08-21, Hamm: "remove those text and only keep the probe schematic image ; adjust
    # panels to fit in and reduce whitespace without changing the context and aspect of panels
    # a and c." Panel A's own width/aspect (PANEL_A_W, height_A) is untouched, so the probe
    # still renders at height_A (unchanged size/aspect, no distortion) -- with the fact text
    # and species icon gone, the leftover column width (x0_B..CANVAS_W) has nothing else to
    # fill it, so the probe is CENTERED in that column rather than left-anchored against panel
    # A, turning one large asymmetric blank block into balanced margins on both sides.
    x0_B = PANEL_A_W + MARGIN_GAP
    width_B = CANVAS_W - x0_B
    probe_h = height_A
    probe_w = probe_h * (b_w / b_h)
    probe_x = x0_B + (width_B - probe_w) / 2.0
    parts.append(f'{label(x0_B - 2, PANEL_LETTER_Y, "b", size=10)}')
    parts.append(f'<g id="panel-b-probe" inkscape:label="b. probe schematic">\n'
                f'<image href="{png_data_uri("dbc128.png")}" x="{probe_x:.3f}" y="{y:.3f}" '
                f'width="{probe_w:.3f}" height="{probe_h:.3f}"/>\n</g>')
    y += height_A + MARGIN_GAP

    # --- Panel C: the three block-type grids, as three columns, fixed cell grid --------------
    parts.append(label(2, y - 3.0, "c", size=10))
    c_svg, c_h = panel_c(0, y, CANVAS_W)
    parts.append(f'<g id="panel-c-block-type-design" inkscape:label="c. block-type design">\n'
                f'{c_svg}\n</g>')
    y += c_h

    canvas_h = y + 4.0
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" '
           f'xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
           f'width="{CANVAS_W:.2f}pt" height="{canvas_h:.2f}pt" '
           f'viewBox="0 0 {CANVAS_W:.3f} {canvas_h:.3f}">\n' + "\n".join(parts) + "\n</svg>\n")

    out = os.path.join(OUT_DIR, "fig01.svg")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    return out, canvas_h


def main():
    out, h = build()
    print(f"-> {os.path.basename(out)}  canvas {CANVAS_W:.0f} x {h:.0f} pt "
         f"(aspect {CANVAS_W/h:.4f})")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "pipeline": "two-stage: build_parts.py writes artifacts/madelane.png, "
                   "artifacts/dbc128.png (both tightly-trimmed rasters extracted from "
                   "svg/01_recording_topology.svg's own embedded images), and "
                   "artifacts/grating{45,135}.svg (single-icon, tightly cropped). This script "
                   "places the rasters via plain <image> (standard, reliable for PNG) and "
                   "builds panel C by repeating the two grating icons on a FIXED cell grid "
                   "(CELL_W/ROW_H/ICON_R constants) with RELATIVE row/column offsets -- no "
                   "aspect-ratio system is solved.",
        "artifacts": ["madelane.png", "dbc128.png", "grating45.svg", "grating135.svg"],
        "fixed_constants_pt": {"canvas_w": CANVAS_W, "canvas_h_target": CANVAS_H,
                               "panel_a_w": PANEL_A_W, "margin_gap": MARGIN_GAP,
                               "icon_r": ICON_R, "col_gap": COL_GAP},
        "layout": {"total_height_pt": round(h, 2), "aspect_w_over_h": round(CANVAS_W / h, 4)},
        "note": "2026-07-31: rewritten to fixed+relative coordination (user request) after the "
                "two prior approaches this same day (aspect-equation solve, then artifact-"
                "viewBox inlining) both proved slow to reason about or had their own bugs. "
                "R-family icons reuse grating45.svg/grating135.svg through a shared greyscale "
                "SVG filter rather than needing separate grey artifacts -- R means a 50/50 "
                "draw between the two real identities (P(A)=P(B)=0.5), never a third "
                "orientation. See README.md for full history.",
    }
    with open(os.path.join(OUT_DIR, "fig01.receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print("receipt ->", os.path.join(OUT_DIR, "fig01.receipt.json"))


if __name__ == "__main__":
    main()
