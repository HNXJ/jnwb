r"""
Compose manuscript Figure 1 from two Illustrator SVGs, without letting them collide.

SOURCES
    01.svg  1281.9 x 1256.172  A: brain with recording areas + DBC probe schematic
                               B: presence-ratio pie      C: firing-rate pie  (6,040 units)
    02.svg  1138.894 x 817.536 sequential visual omission paradigm

WHY THIS IS NOT A CONCATENATION
    Both files are Illustrator exports and both use the default class names cls-1, cls-2, ...
    and the element id Layer_1. Dropping one inside the other silently restyles it: 02's
    .cls-1 would inherit 01's fill. Every id and every CSS class is therefore namespaced per
    source before the two are placed, and every internal reference (url(#..), href="#..",
    xlink:href="#..") is rewritten to match.

LAYOUT
    compact  A (brain + probe) over B (paradigm), at full text width. Fits 594 pt = 8.25 in
             = exactly 75 percent of an 11 in page, leaving the rest of the page for the
             caption. The unit-yield pies are omitted and belong in Extended Data.
    full     A, paradigm, then the two pies as a third row. Needs 811 pt at full width, so
             the whole figure is scaled down to the height budget and no longer spans the
             text column. Produced for comparison.

GEOMETRY
    Page is US Letter, 612 x 792 pt, 1 in margins, so the text column is 468 pt wide.

OUTPUT
    context/figures/fig01_composite_<layout>.svg
    context/figures/fig01_composite.receipt.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone

SRC_DIR = r"G:/My Drive/Drafts/2026_omission_draft/NB-OX/figures"
OUT_DIR = r"D:/workspace/omission/context/figures"

PT_PER_IN = 72.0
TARGET_ASPECT = 4.0 / 5.0        # width : height, as requested
FONT_FAMILY = "Cambria, Georgia, serif"
FONT_PT = 8.5                    # rendered size of every live text run, in points
PAGE_W, PAGE_H = 8.5 * PT_PER_IN, 11.0 * PT_PER_IN
MARGIN = 1.0 * PT_PER_IN
TEXT_W = PAGE_W - 2 * MARGIN                 # 468 pt
BUDGET_H = 0.75 * PAGE_H                     # 594 pt, the "75% of page" request
GAP = 8.0

# fraction of 01.svg's height at which panel A (brain) ends and the pies begin
SPLIT_FRAC = 0.545


def read(name: str) -> str:
    with open(os.path.join(SRC_DIR, name), encoding="utf-8", errors="replace") as fh:
        return fh.read()


def viewbox(svg: str):
    m = re.search(r'viewBox="([\d.\-eE]+)\s+([\d.\-eE]+)\s+([\d.\-eE]+)\s+([\d.\-eE]+)"', svg)
    x, y, w, h = (float(v) for v in m.groups())
    return x, y, w, h


def namespace(svg: str, pfx: str) -> str:
    """Prefix every id and CSS class so two Illustrator exports cannot overwrite each other."""
    ids = set(re.findall(r'\bid="([^"]+)"', svg))

    def esc(s):
        return re.escape(s)

    # ids on elements
    for i in sorted(ids, key=len, reverse=True):
        svg = re.sub(rf'\bid="{esc(i)}"', f'id="{pfx}{i}"', svg)
        svg = re.sub(rf'url\(#{esc(i)}\)', f'url(#{pfx}{i})', svg)
        svg = re.sub(rf'(\bxlink:href|\bhref)="#{esc(i)}"', rf'\1="#{pfx}{i}"', svg)

    # CSS classes: rewrite selectors inside <style> and every class attribute
    def style_sub(m):
        body = re.sub(r'\.(cls-[\w-]+)', lambda c: f'.{pfx}{c.group(1)}', m.group(2))
        return m.group(1) + body + m.group(3)

    svg = re.sub(r'(<style[^>]*>)(.*?)(</style>)', style_sub, svg, flags=re.S)
    svg = re.sub(r'class="([^"]+)"',
                 lambda m: 'class="' + " ".join(pfx + c if c.startswith("cls-") else c
                                                for c in m.group(1).split()) + '"', svg)
    return svg


def restyle_text(svg: str, scale: float) -> tuple[str, int]:
    """Force every LIVE text run to one family and one RENDERED size.

    A panel placed at scale s shrinks its own font-size by s, so to land on FONT_PT in the
    finished figure the source value must be FONT_PT / s. Returns the count of runs touched.

    Only <text> elements can be reached. Labels baked into the embedded PNGs (the brain and
    its area names, the probe schematic, the block-type panels) and labels converted to
    outlines are pixels and paths respectively, and are left exactly as they are.
    """
    src_size = FONT_PT / scale
    n = 0

    def css(m):
        body = re.sub(r'font-family\s*:\s*[^;}]+', f'font-family: {FONT_FAMILY}', m.group(2))
        body = re.sub(r'font-size\s*:\s*[^;}]+', f'font-size: {src_size:.3f}px', body)
        return m.group(1) + body + m.group(3)

    svg = re.sub(r'(<style[^>]*>)(.*?)(</style>)', css, svg, flags=re.S)
    svg = re.sub(r'font-family="[^"]*"', f'font-family="{FONT_FAMILY}"', svg)
    svg = re.sub(r'font-size="[^"]*"', f'font-size="{src_size:.3f}px"', svg)

    def tag(m):
        nonlocal n
        n += 1
        s = m.group(0)
        if "font-family" not in s:
            s = s[:-1] + f' font-family="{FONT_FAMILY}"' + s[-1]
        if "font-size" not in s:
            s = s[:-1] + f' font-size="{src_size:.3f}px"' + s[-1]
        return s

    svg = re.sub(r'<text[^>]*>', tag, svg)
    return svg, n


def inner(svg: str) -> str:
    a = svg.index(">", svg.index("<svg")) + 1
    b = svg.rindex("</svg>")
    return svg[a:b]


def place(content, vb, dst_x, dst_y, dst_w, clip_id=None, src_y=None, src_h=None):
    """Scale a source region to dst_w and translate it to (dst_x, dst_y)."""
    _, vy, vw, vh = vb
    sy = vy if src_y is None else src_y
    sh = vh if src_h is None else src_h
    s = dst_w / vw
    clip = f' clip-path="url(#{clip_id})"' if clip_id else ""
    g = (f'<g transform="translate({dst_x:.3f},{dst_y:.3f}) scale({s:.6f}) '
         f'translate(0,{-sy:.3f})"{clip}>\n{content}\n</g>')
    return g, sh * s


def label(x, y, txt, size=13):
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-family="Cambria,Georgia,serif" '
            f'font-size="{size}" font-weight="bold" fill="#000">{txt}</text>')


def build(layout: str):
    s1, s2 = read("01.svg"), read("02.svg")
    vb1, vb2 = viewbox(s1), viewbox(s2)
    n1, n2 = namespace(s1, "f1-"), namespace(s2, "f2-")
    c1, c2 = inner(n1), inner(n2)
    # 01.svg is placed twice in the 'full' layout (brain region, then the pies). Embedding the
    # same content twice would duplicate all 404 of its ids, and duplicate ids resolve to
    # whichever appears first -- so the second copy would silently borrow the first copy's
    # gradients, clips and glyph definitions. The second placement gets its own prefix.
    c1b = inner(namespace(s1, "f1b-"))

    split_y = vb1[1] + SPLIT_FRAC * vb1[3]
    a_h_src = split_y - vb1[1]
    pies_h_src = (vb1[1] + vb1[3]) - split_y

    rows = [("A", vb1[2], a_h_src), ("B", vb2[2], vb2[3])]
    if layout == "full":
        rows.append(("C", vb1[2], pies_h_src))

    # Canvas is fixed at exactly 4:5. Content is then scaled to whatever width makes the
    # stacked panels fill that height, and centred -- so the aspect ratio is exact rather
    # than approached by trimming.
    canvas_w = TEXT_W
    canvas_h = canvas_w / TARGET_ASPECT
    aspect_sum = sum(h / w for _, w, h in rows)
    width = (canvas_h - GAP * (len(rows) - 1)) / aspect_sum
    scale = width / TEXT_W

    x0 = (canvas_w - width) / 2.0
    parts, defs, y = [], [], 0.0
    n_text = 0

    # panel A: brain + probe, clipped from 01
    sA = width / vb1[2]
    cA, nA = restyle_text(c1, sA)
    n_text += nA
    defs.append(f'<clipPath id="clipA"><rect x="{vb1[0]}" y="{vb1[1]}" '
                f'width="{vb1[2]}" height="{a_h_src}"/></clipPath>')
    g, h = place(cA, vb1, x0, y, width, clip_id="clipA", src_y=vb1[1], src_h=a_h_src)
    parts.append(f'<g id="panel-a-recording-topology" '
                 f'inkscape:label="a. recording topology">\n{g}\n'
                 f'{label(x0 - 2, y + 12, "a")}\n</g>')
    y += h + GAP

    # panel B: paradigm
    sB = width / vb2[2]
    cB, nB = restyle_text(c2, sB)
    n_text += nB
    g, h = place(cB, vb2, x0, y, width)
    parts.append(f'<g id="panel-b-paradigm" inkscape:label="b. omission paradigm">\n{g}\n'
                 f'{label(x0 - 2, y + 12, "b")}\n</g>')
    y += h + GAP

    if layout == "full":
        cC, nC = restyle_text(c1b, sA)
        n_text += nC
        defs.append(f'<clipPath id="clipC"><rect x="{vb1[0]}" y="{split_y}" '
                    f'width="{vb1[2]}" height="{pies_h_src}"/></clipPath>')
        g, h = place(cC, vb1, x0, y, width, clip_id="clipC",
                     src_y=split_y, src_h=pies_h_src)
        parts.append(f'<g id="panel-c-unit-yield" inkscape:label="c. unit yield">\n{g}\n'
                     f'{label(x0 - 2, y + 12, "c")}\n</g>')
        y += h

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" '
           f'xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
           f'width="{canvas_w:.2f}pt" height="{canvas_h:.2f}pt" '
           f'viewBox="0 0 {canvas_w:.3f} {canvas_h:.3f}">\n'
           f'<defs>{"".join(defs)}</defs>\n' + "\n".join(parts) + "\n</svg>\n")

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"fig01_composite_{layout}.svg")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    return out, width, canvas_h, scale, n_text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", choices=["compact", "full", "both"], default="both")
    args = ap.parse_args()

    results = {}
    for lay in (["compact", "full"] if args.layout == "both" else [args.layout]):
        out, w, h, s, ntext = build(lay)
        results[lay] = {
            "file": out,
            "drawn_width_pt": round(w, 2),
            "total_height_pt": round(h, 2),
            "height_in": round(h / PT_PER_IN, 3),
            "fraction_of_page_height": round(h / PAGE_H, 3),
            "fraction_of_text_width": round(w / TEXT_W, 3),
            "downscale_applied": round(s, 4),
            "aspect_w_over_h": round(TEXT_W / h, 4),
            "live_text_runs_restyled": ntext,
        }
        print(f"{lay:8s} -> {os.path.basename(out)}  canvas {TEXT_W:.0f} x {h:.0f} pt "
              f"(aspect {TEXT_W/h:.4f}), content {w:.1f} pt wide, "
              f"{h/PAGE_H:.0%} of page height, {ntext} text runs restyled")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "sources": {"panel_a_and_c": os.path.join(SRC_DIR, "01.svg"),
                    "panel_b": os.path.join(SRC_DIR, "02.svg")},
        "page": {"size": "US Letter 612 x 792 pt", "margin_pt": MARGIN,
                 "text_width_pt": TEXT_W, "height_budget_pt": BUDGET_H},
        "collision_handling": "every id and CSS class namespaced per source (f1-, f2-) "
                              "before placement; both sources are Illustrator exports using "
                              "the same default cls-N names and Layer_1 id",
        "split_fraction_of_01": SPLIT_FRAC,
        "layouts": results,
        "typography": {
            "family": FONT_FAMILY, "rendered_size_pt": FONT_PT,
            "scope": "live <text> elements only",
            "not_reachable": "labels baked into the embedded PNGs (brain area names, sulcal "
                             "labels, probe schematic, block-type panels) and labels converted "
                             "to outlines (pie chart percentages and counts) are pixels and "
                             "paths, and keep their original face. Uniform typography across "
                             "the whole figure requires re-exporting the .ai sources with live "
                             "text, or re-labelling the brain over a label-free image.",
        },
        "objects": "each panel is a named top-level <g> (panel-a-recording-topology, "
                   "panel-b-paradigm, panel-c-unit-yield) carrying an inkscape:label, so the "
                   "panels stay independently selectable and movable in Illustrator/Inkscape; "
                   "nothing is flattened or rasterised by this script",
        "note": "compact omits the unit-yield pies, which are quality-control panels and "
                "belong in Extended Data; full includes them but must shrink below the text "
                "column width to stay inside the 75 percent height budget.",
    }
    with open(os.path.join(OUT_DIR, "fig01_composite.receipt.json"), "w",
              encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print("receipt ->", os.path.join(OUT_DIR, "fig01_composite.receipt.json"))


if __name__ == "__main__":
    main()
