r"""Shared low-level SVG helper for fig01's build_parts.py.

Trimmed 2026-07-31: this module used to also carry namespace()/restyle_text()/read()/
strip_legacy_text() for the whole-panel-artifact pipeline (panel_a_brain.svg/panel_b_probe.svg,
cropped straight out of svg/01_recording_topology.svg with namespacing to avoid id collisions
once inlined). That pipeline was replaced the same day by tightly-cropped single-purpose
artifacts (madelane.png/dbc128.png extracted as raw raster bytes, grating45.svg/grating135.svg
built fresh from grating.circular_grating()) -- none of the removed functions have a caller
left. Only write_standalone() is still used, by build_parts.py's grating-icon builder.
"""
from __future__ import annotations


def write_standalone(out_path: str, content: str, x0: float, y0: float, w: float, h: float,
                     extra_ns: str = "") -> None:
    """Wrap content in its own <svg>, cropped via viewBox alone (no clipPath needed) --
    viewBox="x0 y0 w h" shows exactly that window of content's own coordinate system."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" '
          f'xmlns:xlink="http://www.w3.org/1999/xlink"{extra_ns} '
          f'viewBox="{x0:.3f} {y0:.3f} {w:.3f} {h:.3f}">\n{content}\n</svg>\n')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {out_path}  viewBox {w:.1f}x{h:.1f}")
