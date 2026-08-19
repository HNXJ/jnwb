r"""Build fig01's isolated sub-panel artifacts (run once per source change, not on every
figure iteration):
    artifacts/madelane.png   -- brain + area labels only (no title, no panel "a" label);
                                 this is the SAME raster already baked into
                                 svg/01_recording_topology.svg (labels are baked pixels, not
                                 separate vector text) -- extracted and trimmed, not redrawn.
    artifacts/dbc128.png     -- the probe schematic image, extracted and trimmed the same way.
    artifacts/grating45.svg  -- ONE circular-grating icon at 45deg (the "A" identity), tightly
                                 cropped to its own bounding circle -- no surrounding canvas.
    artifacts/grating135.svg -- ONE circular-grating icon at 135deg (the "B" identity), same.
Panel C's block-type grid is assembled by fig01_recording_topology_and_paradigm.py directly
from repeated placements of grating45.svg/grating135.svg (fixed cell geometry, relative
row/column offsets) -- there is no more panel_c_blocks.svg blob artifact.
"""
from __future__ import annotations

import base64
import os
import re
import sys

FIG_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(FIG_DIR, "svg")
ART_DIR = os.path.join(FIG_DIR, "artifacts")

sys.path.insert(0, FIG_DIR)
sys.path.insert(0, os.path.dirname(FIG_DIR))   # context/figures/, holds grating.py
from svg_utils import write_standalone
from grating import circular_grating

# 01_recording_topology.svg embeds exactly two raster <image> elements, confirmed by their own
# transform/width/height attributes: brain (index 0, 1526x1026 source px) and probe schematic
# (index 1, 520x1254 source px). Both already have area/component labels baked into the pixels
# -- the figure's live vector <text> (title, panel labels a/b/c) sits OUTSIDE these images
# entirely, so extracting the raw embedded image IS "brain + areas, no title, no panel label"
# with no further cropping needed (confirmed by trimming against a white background below --
# both bboxes come back equal to the full image, i.e. no padding to trim).
IMAGE_INDEX = {"madelane.png": 0, "dbc128.png": 1}


def extract_images():
    svg = open(os.path.join(SRC_DIR, "01_recording_topology.svg"),
              encoding="utf-8", errors="replace").read()
    imgs = list(re.finditer(r'<image[^>]*>', svg))
    from PIL import Image, ImageChops
    for name, idx in IMAGE_INDEX.items():
        href = re.search(r'(?:xlink:href|href)="([^"]+)"', imgs[idx].group(0)).group(1)
        _, b64 = href.split(",", 1)
        raw_path = os.path.join(ART_DIR, f"_raw_{name}")
        with open(raw_path, "wb") as fh:
            fh.write(base64.b64decode(b64))
        im = Image.open(raw_path).convert("RGB")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bbox = ImageChops.difference(im, bg).getbbox()
        im2 = Image.open(raw_path).convert("RGBA")
        (im2.crop(bbox) if bbox else im2).save(os.path.join(ART_DIR, name))
        os.remove(raw_path)
        print(f"wrote {os.path.join(ART_DIR, name)}  {(im2.crop(bbox) if bbox else im2).size}"
             f"  (source image was {im.size}, trim bbox {bbox})")


# Identity convention locked 2026-07-30/31: A=45deg, B=135deg, 4 cycles, grey R-family drawn
# by the assembler as a filtered (desaturated) copy of one of these two -- not a third file.
ICON_R = 40.0   # generous design-space radius; assembler rescales to whatever cell size it needs
ICON_OUTLINE_W = 1.2


def build_grating_icon(orientation_deg: float, out_name: str):
    margin = ICON_OUTLINE_W  # so the outline stroke isn't clipped at the viewBox edge
    content = circular_grating(ICON_R + margin, ICON_R + margin, ICON_R,
                               orientation_deg=orientation_deg, uid=out_name.replace(".svg", ""))
    write_standalone(os.path.join(ART_DIR, out_name), content,
                     0, 0, 2 * (ICON_R + margin), 2 * (ICON_R + margin))


if __name__ == "__main__":
    os.makedirs(ART_DIR, exist_ok=True)
    extract_images()
    build_grating_icon(45.0, "grating45.svg")
    build_grating_icon(135.0, "grating135.svg")
