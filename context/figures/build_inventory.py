r"""
Build a master inventory of all seven omission-a figures: code, panels, assembled figure,
statistics, supplements, and methodology -- one document a manuscript pass can read instead
of re-deriving from the filesystem each time.

WHY A SCRIPT AND NOT A HAND-WRITTEN DOCUMENT
    A hand-maintained inventory is exactly the kind of registry this project's own doctrine
    warns about: it goes stale the moment a script adds a panel or a stats family and nobody
    remembers to edit the summary too. This walks the actual files on disk and the actual
    PLAN in build_supplements.py every time it runs, so "what's really there" and "what the
    inventory says is there" cannot silently diverge.

USAGE
    python build_inventory.py            writes INVENTORY.md
    python build_inventory.py --check    same walk, exits 1 if any figure's README.md is
                                          missing or any *_stats.md family has zero tests
                                          (used as a pre-submission gate, not part of the
                                          normal figure build)
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_supplements import PLAN, PENDING  # noqa: E402

FIGURES = [
    ("fig01", "fig01_recording_topology_and_paradigm", "Recording topology and paradigm schematic"),
    ("fig02", "fig02_spiking_exemplar_rasters", "Spiking exemplar rasters (4x4: S+/S-/O+/O++ x RRRR/RXRR/RRXR/RRRX)"),
    ("fig03", "fig03_unit_census", "Unit census: presence, functionality, and RXRR template traces by area"),
    ("fig04", "fig04_v1_pfc_condition_tfr", "V1/PFC time-frequency, RXRR vs RRRR"),
    ("fig05", "fig05_band_power_hierarchy", "Band-power hierarchy across all areas, RXRR vs RRRR"),
    ("fig06", "fig06_band_power_coupling", "LFP band-power to band-power coupling matrices"),
    ("fig07", "fig07_lfp_spike_coupling", "Spike-LFP coupling"),
]


def count_by_ext(folder):
    if not os.path.isdir(folder):
        return {}
    counts = {}
    for f in os.listdir(folder):
        if os.path.isfile(os.path.join(folder, f)):
            ext = os.path.splitext(f)[1].lstrip(".") or "(no ext)"
            counts[ext] = counts.get(ext, 0) + 1
    return counts


def svg_dims(path):
    if not os.path.exists(path):
        return None
    try:
        import xml.etree.ElementTree as ET
        r = ET.parse(path).getroot()
        return r.get("width"), r.get("height")
    except Exception as e:
        return f"unreadable ({e})"


def stats_families(svg_dir):
    """Parse every *_stats.md in svg_dir for '## Family: NAME' + 'N tests corrected together'."""
    families = []
    for md in sorted(glob.glob(os.path.join(svg_dir, "*_stats.md"))):
        text = open(md, encoding="utf-8").read()
        for m in re.finditer(
            r"## Family: (\S+)\s*\n\n(\d+) tests? corrected together", text
        ):
            families.append({
                "file": os.path.relpath(md, HERE).replace("\\", "/"),
                "family": m.group(1), "n_tests": int(m.group(2)),
            })
        if not re.search(r"## Family:", text):
            by_design = "no inferential test is reported here by design" in text.lower()
            families.append({
                "file": os.path.relpath(md, HERE).replace("\\", "/"),
                "family": "(no test, by design -- n=1 exemplars, see file)" if by_design
                          else "(unparsed -- no '## Family:' header found)",
                "n_tests": 0, "by_design": by_design,
            })
    return families


def readme_summary(folder):
    path = os.path.join(folder, "README.md")
    if not os.path.exists(path):
        return None
    lines = [l.rstrip() for l in open(path, encoding="utf-8").readlines()]
    # First non-heading, non-blank paragraph.
    para = []
    for l in lines:
        if l.startswith("#") or not l.strip():
            if para:
                break
            continue
        para.append(l.strip())
    return " ".join(para) if para else "(README.md present but no lead paragraph found)"


def supplements_for(folder_prefix):
    """Which figSNN entries in build_supplements.PLAN pull a panel from this figure's svg/?"""
    out = []
    for num, slug, pats, *_ in PLAN:
        if any(p.startswith(folder_prefix) for p in pats):
            out.append(f"figS{num:02d}_{slug}")
    return out


def pending_for(fig_num, fig_dir_name):
    """fig_num is e.g. 'fig06'; PENDING values say 'needs figure 6' or 'fig06_band_power_coupling'."""
    needle = f"figure {fig_num[3:].lstrip('0')}"
    return [k for k, v in PENDING.items() if fig_dir_name in v or needle in v]


def build():
    sections = []
    check_failures = []
    for num, dirname, title in FIGURES:
        folder = os.path.join(HERE, dirname)
        svg_dir = os.path.join(folder, "svg")
        code_files = sorted(glob.glob(os.path.join(folder, f"{dirname}.py")))
        main_svg = os.path.join(folder, f"{num}.svg")
        ext_counts = count_by_ext(svg_dir)
        fams = stats_families(svg_dir)
        readme = readme_summary(folder)
        supp = supplements_for(f"{dirname}/svg")
        pend = pending_for(num, dirname)

        if readme is None:
            check_failures.append(f"{num}: no README.md")
        n_tests_total = sum(f["n_tests"] for f in fams)
        by_design_ok = any(f.get("by_design") for f in fams)
        is_schematic = num == "fig01"  # Illustrator-sourced diagram, no data to test
        if code_files and n_tests_total == 0 and not pend and not by_design_ok and not is_schematic:
            check_failures.append(f"{num}: has code but zero statistical tests recorded")

        lines = [f"## {num} -- {title}", ""]
        lines.append(f"- **Directory:** `{dirname}/`")
        lines.append(f"- **Code:** {'`' + os.path.basename(code_files[0]) + '`' if code_files else '(not written yet)'}")
        if os.path.exists(main_svg):
            dims = svg_dims(main_svg)
            lines.append(f"- **Assembled main figure:** `{num}.svg` ({dims[0]} x {dims[1]})" if isinstance(dims, tuple)
                         else f"- **Assembled main figure:** `{num}.svg` ({dims})")
        else:
            lines.append("- **Assembled main figure:** not built")
        if ext_counts:
            parts = ", ".join(f"{v} .{k}" for k, v in sorted(ext_counts.items()))
            lines.append(f"- **svg/ folder contents:** {parts}")
        else:
            lines.append("- **svg/ folder contents:** empty")
        if fams:
            lines.append("- **Statistics families:**")
            for f in fams:
                unit = "test" if f["n_tests"] == 1 else "tests"
                lines.append(f"  - `{f['family']}` -- {f['n_tests']} {unit} ({f['file']})")
        else:
            lines.append("- **Statistics families:** none recorded")
        if supp:
            lines.append(f"- **Feeds supplements:** {', '.join(supp)} ({len(supp)} total)")
        else:
            lines.append("- **Feeds supplements:** none")
        if pend:
            lines.append(f"- **Pending supplements waiting on this figure:** {', '.join(pend)}")
        lines.append(f"- **Methodology (from README.md):** {readme if readme else '*missing -- add one*'}")
        lines.append("")
        sections.append("\n".join(lines))

    supp_dir = os.path.join(HERE, "supplements")
    n_supp = len(glob.glob(os.path.join(supp_dir, "figS*.svg")))
    header = [
        "# Omission-a figure inventory",
        "",
        "Auto-generated by `build_inventory.py` -- do not hand-edit; re-run the script instead. "
        "Regenerate any time a figure script or `build_supplements.py`'s PLAN changes, so this "
        "never drifts from what is actually on disk.",
        "",
        f"**{len(FIGURES)} main figures, {n_supp} supplements built** "
        f"({len(PENDING)} supplements pending on figures 6/7). "
        "No cap on supplement count -- every panel a figure script emits that doesn't fit the "
        "main figure is a supplement candidate.",
        "",
    ]
    out_path = os.path.join(HERE, "INVENTORY.md")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(header) + "\n" + "\n".join(sections))
    print(f"wrote {out_path}")
    return check_failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                     help="exit 1 if any figure lacks a README.md or has code with zero tests recorded")
    args = ap.parse_args()
    failures = build()
    if args.check:
        if failures:
            print("CHECK FAILED:")
            for f in failures:
                print(" -", f)
            sys.exit(1)
        print("CHECK OK")


if __name__ == "__main__":
    main()
