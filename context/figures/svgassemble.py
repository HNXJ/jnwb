r"""
Assemble panel SVGs into one figure SVG.

WHY THIS EXISTS
    Every figure directory holds many panels in svg/ and exactly one assembled figNN.svg.
    The assembly must be reproducible from the panels, which means it is code, not an
    Illustrator session -- the hand-editing pass happens afterwards, on the assembled file,
    and only for template matching.

    Two exports dropped into one document collide on ids and on CSS class names, and the
    second silently overwrites the first. `namespace()` prefixes both. This is the same
    failure that produced 404 duplicate ids in the first figure-1 build.

    This module owns no analysis and draws nothing. Figure scripts import `assemble()`;
    supplements are built from it by `build_supplements.py`.
"""
from __future__ import annotations

import os
import re

FONT_FAMILY = "Cambria, Georgia, serif"
PT_PER_IN = 72.0
PAGE_W, PAGE_H = 8.5 * PT_PER_IN, 11.0 * PT_PER_IN
TEXT_W = PAGE_W - 2 * PT_PER_IN        # 468 pt, the one-inch-margin text column


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def viewbox(svg: str):
    m = re.search(r'viewBox="([\d.\-eE]+)\s+([\d.\-eE]+)\s+([\d.\-eE]+)\s+([\d.\-eE]+)"', svg)
    if m:
        return tuple(float(v) for v in m.groups())
    w = re.search(r'\swidth="([\d.]+)(pt|px|in)?"', svg)
    h = re.search(r'\sheight="([\d.]+)(pt|px|in)?"', svg)
    if not (w and h):
        raise ValueError("panel has neither viewBox nor width/height")
    return (0.0, 0.0, float(w.group(1)), float(h.group(1)))


def namespace(svg: str, pfx: str) -> str:
    """Prefix every id and CSS class so two panels cannot overwrite each other."""
    # One pass over the document, not one pass per id. The Illustrator panels carry several
    # hundred ids in seven megabytes of markup, and a substitution per id is quadratic enough
    # to look like a hang.
    ids = set(re.findall(r'\bid="([^"]+)"', svg))
    if ids:
        alt = "|".join(re.escape(i) for i in sorted(ids, key=len, reverse=True))
        svg = re.sub(rf'\bid="({alt})"', lambda m: f'id="{pfx}{m.group(1)}"', svg)
        svg = re.sub(rf'url\(#({alt})\)', lambda m: f'url(#{pfx}{m.group(1)})', svg)
        svg = re.sub(rf'(\bxlink:href|\bhref)="#({alt})"',
                     lambda m: f'{m.group(1)}="#{pfx}{m.group(2)}"', svg)

    def style_sub(m):
        # Every class selector, not a known-prefix subset. The class ATTRIBUTE rewriter below
        # prefixes all tokens unconditionally, so a selector left unprefixed here would stop
        # matching and the panel would silently lose its styling.
        body = re.sub(r'\.([A-Za-z_][\w-]*)', lambda c: f'.{pfx}{c.group(1)}', m.group(2))
        return m.group(1) + body + m.group(3)

    svg = re.sub(r'(<style[^>]*>)(.*?)(</style>)', style_sub, svg, flags=re.S)
    svg = re.sub(r'class="([^"]+)"',
                 lambda m: 'class="' + " ".join(pfx + c for c in m.group(1).split()) + '"',
                 svg)
    return svg


def inner(svg: str) -> str:
    a = svg.index(">", svg.index("<svg")) + 1
    return svg[a:svg.rindex("</svg>")]


def _label(x, y, txt, size=11):
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-family="{FONT_FAMILY}" font-size="{size}" '
            f'font-weight="bold" fill="#000">{txt}</text>')


def assemble(panels, out_path, ncol=1, width=TEXT_W, gap=10.0, letters=True,
             letter_size=11, panel_names=None, label_inset=False):
    """Lay panels out on a grid, left to right then top to bottom, and write one SVG.

    panels        paths to the panel SVGs, in reading order
    ncol          columns; each column is (width - gap*(ncol-1)) / ncol wide
    letters       draw a, b, c ... at each panel's top-left
    panel_names   optional group ids, one per panel, so the assembly stays navigable in
                  Illustrator; defaults to the panel file stems
    label_inset   draw the letter inside the panel's own top-left corner instead of a
                  dedicated strip above it -- no `head` row reserved, tighter stacking

    Panels keep their own aspect ratio. Each row is as tall as its tallest panel.
    Returns (out_path, canvas_width, canvas_height).
    """
    if not panels:
        raise ValueError("no panels to assemble")
    names = panel_names or [os.path.splitext(os.path.basename(p))[0] for p in panels]
    cw = (width - gap * (ncol - 1)) / ncol
    head = 0 if (label_inset or not letters) else letter_size + 3

    bodies, heights = [], []
    for i, p in enumerate(panels):
        s = namespace(_read(p), f"p{i}-")
        _, vy, vw, vh, = viewbox(s)
        scale = cw / vw
        bodies.append((inner(s), vy, scale, names[i]))
        heights.append(vh * scale + head)

    rows = [heights[r:r + ncol] for r in range(0, len(heights), ncol)]
    row_h = [max(r) for r in rows]
    total_h = sum(row_h) + gap * (len(rows) - 1)

    out = [f'<?xml version="1.0" encoding="utf-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'version="1.1" width="{width:.3f}pt" height="{total_h:.3f}pt" '
           f'viewBox="0 0 {width:.3f} {total_h:.3f}">']
    y = 0.0
    for r, rh in enumerate(row_h):
        for c in range(ncol):
            k = r * ncol + c
            if k >= len(bodies):
                break
            body, vy, scale, name = bodies[k]
            x = c * (cw + gap)
            if letters:
                lx = x + 2.0 if label_inset else x
                out.append(_label(lx, y + letter_size, chr(97 + k), letter_size))
            out.append(f'<g id="{name}" transform="translate({x:.3f},{y + head:.3f}) '
                       f'scale({scale:.6f}) translate(0,{-vy:.3f})">')
            out.append(body)
            out.append('</g>')
        y += rh + gap
    out.append('</svg>')

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    return out_path, width, total_h
