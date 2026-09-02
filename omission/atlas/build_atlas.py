"""Build the Analysis 6A atlas -- a static site generated from the canonical public tables.

    canonical reviewed tables  ->  this builder  ->  omission/atlas/_site/  ->  (gh-pages)

The site is a VIEW of canonical evidence, never a new scientific authority. Every number rendered
here is read at build time from omission/atlas/tables/*.csv. Nothing is typed in as a literal, and
nothing is recomputed from NWB, raw LFP, or spike trains -- the builder has no access to them.

Publication is gated by visibility.py and fails closed: an artifact that is not explicitly
labelled `public` is refused, and a declared-public artifact missing from disk is also refused.

Plotly is vendored ONCE into _site/assets/plotly.min.js and referenced by every interactive page,
rather than embedding the ~4.85 MB bundle separately in each file.

Usage:  python omission/atlas/build_atlas.py
"""

from __future__ import annotations

import html
import json
import os
import shutil
import time
import subprocess
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import plotly.offline as po

import visibility as vis

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TABLES = os.path.join(HERE, "tables")
FIGDIR = os.path.join(HERE, "figures")
SITE = os.path.join(HERE, "_site")
FIGSRC = os.path.join(REPO, "omission", "context", "figures", "analysis6a_timing", "svg")

ANALYSIS = "onset-6a"
STATUS = "Reviewed analysis"
STATUS_NOTE = ("Reviewed scientific analysis. Not a finalized manuscript result. "
               "Claims below are session-level unless explicitly marked descriptive.")

PAGES = [
    ("index.html", "Overview"),
    ("spk-timing.html", "SPK timing"),
    ("spk-vs-stimulus.html", "SPK omission vs stimulus"),
    ("lfp-resolvability.html", "LFP frequency &amp; resolvability"),
    ("dsp-support.html", "DSP temporal support"),
    ("session-statistics.html", "Session-level statistics"),
    ("coverage.html", "Coverage &amp; design limits"),
    ("methods.html", "Methods"),
    ("figures.html", "Static figures"),
    ("provenance.html", "Provenance"),
]

CSS = """
:root{--bg:#fbfbfa;--fg:#1a1a1a;--mut:#5b6570;--line:#dfe3e8;--accent:#1f5f8b;
--pos:#0f7b52;--neg:#a33a2c;--warn:#8a6d1f;--card:#fff;}
*{box-sizing:border-box}
body{margin:0;font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
background:var(--bg);color:var(--fg)}
header{background:var(--card);border-bottom:1px solid var(--line);padding:18px 24px}
header h1{margin:0;font-size:18px;letter-spacing:-.01em}
header .sub{color:var(--mut);font-size:13px;margin-top:4px}
.wrap{display:flex;align-items:flex-start;gap:28px;max-width:1180px;margin:0 auto;padding:24px}
nav{flex:0 0 216px;position:sticky;top:24px}
nav a{display:block;padding:7px 10px;color:var(--fg);text-decoration:none;border-radius:6px;
font-size:14px}
nav a:hover{background:#eef1f4}
nav a.on{background:var(--accent);color:#fff}
main{flex:1;min-width:0}
h2{font-size:20px;margin:0 0 4px;letter-spacing:-.01em}
h3{font-size:15px;margin:26px 0 8px;color:var(--accent)}
p{margin:10px 0}
.badge{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11.5px;
font-weight:600;letter-spacing:.02em;vertical-align:middle}
.b-review{background:#fdf3d8;color:var(--warn);border:1px solid #e8d4a0}
.b-pub{background:#dcf0e6;color:var(--pos);border:1px solid #a9d8c2}
.b-desc{background:#eceff2;color:var(--mut);border:1px solid var(--line)}
.card{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:16px 18px;
margin:14px 0}
.key{border-left:3px solid var(--accent)}
.hold{border-left:3px solid var(--warn);background:#fffdf6}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:10px 0}
th,td{border-bottom:1px solid var(--line);padding:6px 9px;text-align:right}
th:first-child,td:first-child{text-align:left}
th{background:#f2f4f6;font-weight:600;color:var(--mut);white-space:nowrap}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
code{background:#eef1f4;padding:1px 5px;border-radius:4px;font-size:12.5px}
.mut{color:var(--mut);font-size:13px}
.stat{font-variant-numeric:tabular-nums;font-weight:600}
.pos{color:var(--pos)}.neg{color:var(--neg)}
figure{margin:14px 0}
figure img{width:100%;border:1px solid var(--line);border-radius:8px;background:#fff}
figcaption{color:var(--mut);font-size:13px;margin-top:7px}
footer{color:var(--mut);font-size:12.5px;border-top:1px solid var(--line);
margin-top:34px;padding-top:14px}
@media(max-width:820px){.wrap{flex-direction:column;padding:16px}nav{position:static;flex:none;
width:100%;display:flex;flex-wrap:wrap;gap:4px}nav a{font-size:13px;padding:5px 9px}}
"""


def shell(body: str, page: str, title: str, plotly_pages: bool = False) -> str:
    nav = "\n".join(
        f'<a href="{h}" class="{"on" if h == page else ""}">{t}</a>' for h, t in PAGES
    )
    js = '<script src="assets/plotly.min.js" charset="utf-8"></script>' if plotly_pages else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} &middot; Analysis 6A</title>
<link rel="stylesheet" href="assets/atlas.css">{js}
</head><body>
<header>
  <h1>Analysis 6A &mdash; onset timing during stimulus omission</h1>
  <div class="sub">Macaque multi-area laminar electrophysiology &middot;
  <span class="badge b-review">{STATUS}</span></div>
</header>
<div class="wrap"><nav>{nav}</nav><main>
{body}
<footer>Generated from canonical public tables. The site is a view of canonical evidence, not a
new scientific authority: if a value here disagrees with its source table, the site is wrong.
See <a href="provenance.html">Provenance</a>.</footer>
</main></div></body></html>
"""


def table_html(df: pd.DataFrame, floatfmt: str = "{:g}") -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    rows = []
    for _, r in df.iterrows():
        cells = []
        for v in r:
            if isinstance(v, float) and pd.notna(v):
                cells.append(f"<td>{floatfmt.format(v)}</td>")
            elif pd.isna(v):
                cells.append('<td class="mut">&mdash;</td>')
            else:
                cells.append(f"<td>{html.escape(str(v))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return ('<div class="scroll"><table><thead><tr>' + head + "</tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></div>")


def _unescape_strings(obj):
    """Recursively decode HTML named entities in every string of a figure spec.

    Plotly's text renderer understands a small HTML subset (<b>, <i>, <sub>, <sup>, <br>) but does
    NOT decode named entities: a title written as "A1 &middot; ..." renders the literal text
    "A1 &middot; ...". The surrounding page prose is real HTML and legitimately uses entities, so
    rather than maintaining two escaping conventions by hand -- which had already produced literal
    "&middot;" in every chart title and "&plusmn;" in the hover templates -- every figure spec is
    decoded once here, at the single point where figures become HTML.

    Only named/numeric entities are decoded; the markup tags Plotly does support pass through.
    """
    if isinstance(obj, str):
        return html.unescape(obj)
    if isinstance(obj, dict):
        return {k: _unescape_strings(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_unescape_strings(v) for v in obj]
    return obj


def div(fig: go.Figure, div_id: str) -> str:
    """A plotly div with NO embedded bundle -- the shared assets/plotly.min.js serves every page."""
    fig = go.Figure(_unescape_strings(fig.to_plotly_json()))
    return pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id=div_id,
                       config={"displaylogo": False, "responsive": True})


def base_layout(fig: go.Figure, h: int = 470, **kw) -> go.Figure:
    fig.update_layout(
        template="simple_white", height=h, margin=dict(l=64, r=24, t=52, b=56),
        font=dict(family="-apple-system,Segoe UI,Roboto,sans-serif", size=12.5),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), **kw)
    return fig


# =============================================================================================
# Data access -- every page reads the public tables, nothing else.
# =============================================================================================
def load() -> dict[str, pd.DataFrame]:
    need = {
        "spk": "analysis6a_spk_resolved_public.csv",
        "census": "analysis6a_spk_census_public.csv",
        "spk_sess": "analysis6a_spk_session_stats_public.csv",
        "lfp_freq": "analysis6a_lfp_frequency_public.csv",
        "lfp_sess": "analysis6a_lfp_session_stats_public.csv",
        "lfp_cens": "analysis6a_lfp_censoring_public.csv",
        "dsp": "analysis6a_dsp_temporal_support_public.csv",
        "cov": "analysis6a_coverage_public.csv",
        "tests": "analysis6a_session_tests_public.csv",
    }
    out = {}
    for k, fn in need.items():
        vis.assert_publishable(f"tables/{fn}")     # gate every read, not just every copy
        out[k] = pd.read_csv(os.path.join(TABLES, fn))
    return out


def p_of(tests: pd.DataFrame, frag: str) -> pd.Series:
    hit = tests[tests.test.str.contains(frag, case=False, regex=False)]
    if len(hit) != 1:
        raise SystemExit(f"FAIL: expected exactly one test row matching {frag!r}, got {len(hit)}")
    return hit.iloc[0]


def stage_figures() -> None:
    """Stage the frozen SVGs into atlas/figures/ with identifiers anonymised.

    The scientific content of A-D is NOT rebuilt: geometry, data, statistics and annotations are
    carried through byte-for-byte. The ONLY change is textual -- the figure legends were drawn
    with the recording subject codes and session ids, and those are private. Substituting the
    public labels here means the frozen figure script (which lives in a protected concurrent-work
    path) is never touched, and it keeps every identifier decision in this one build.

    The mapping is RECOMPUTED from the census receipt by the same deterministic function that
    built the tables -- the private map file on disk is never read by the site build.
    """
    from build_public_tables import build_identifier_map

    census = pd.read_csv(os.path.join(REPO, "omission", "artifacts", "data",
                                      "onset6a_corpus_census.csv"))
    submap, sesmap = build_identifier_map(census)
    # Longest keys first: a session id contains its subject code, so substituting the subject
    # first would corrupt the session id it is nested inside.
    subs = sorted({**submap, **sesmap}.items(), key=lambda kv: -len(kv[0]))

    os.makedirs(FIGDIR, exist_ok=True)
    for rel, lab in sorted(vis.ARTIFACTS.items()):
        if not rel.startswith("figures/") or lab != vis.PUBLIC:
            continue
        src = os.path.join(FIGSRC, os.path.basename(rel))
        if not os.path.exists(src):
            raise SystemExit(f"FAIL: declared-public figure not found in the figure tree: {src}")
        svg = open(src, encoding="utf-8").read()
        before = len(svg)
        for private, public in subs:
            svg = svg.replace(private, public)
        if before != len(svg):
            pass  # length changes are expected: public labels are shorter
        for private, _ in subs:
            if private in svg:
                raise SystemExit(
                    f"FAIL: {rel} still contains the private identifier {private!r} after "
                    "substitution -- refusing to stage it")
        with open(os.path.join(HERE, rel), "w", newline="", encoding="utf-8") as fh:
            fh.write(svg)


def write_text(relpath: str, text: str) -> int:
    """Write into _site with LF endings; return byte count."""
    path = os.path.join(SITE, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = text.encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
    return len(data)


def main() -> None:
    import pages  # imported here: pages imports helpers from this module

    # Clear FILES only, never directories. On Windows a directory handle stays open briefly after
    # anything reads the tree (an editor, a local preview server, an antivirus scan), so rmtree
    # fails with WinError 5 *partway through* and leaves a half-deleted site that still looks
    # buildable -- which a verification pass would then happily run against. Unlinking files has
    # no such failure mode, and leftover empty directories are harmless because every file is
    # rewritten below.
    stale = []
    if os.path.isdir(SITE):
        for root, _, names in os.walk(SITE):
            for n in names:
                p = os.path.join(root, n)
                for attempt in range(4):
                    try:
                        os.unlink(p)
                        break
                    except PermissionError:
                        if attempt == 3:
                            stale.append(os.path.relpath(p, SITE))
                        else:
                            time.sleep(0.4)
    if stale:
        raise SystemExit(f"FAIL: could not clear {len(stale)} stale file(s) from _site: "
                         f"{', '.join(stale[:5])}. Close anything reading them and rerun.")
    os.makedirs(SITE, exist_ok=True)

    print("Analysis 6A atlas")
    stage_figures()

    # --- visibility gate, before anything is written -----------------------------------------
    declared = vis.public_artifacts(HERE)
    undeclared = vis.audit_undeclared(HERE)
    print(f"  gate: {len(declared)} declared-public artifacts, all present on disk")
    if undeclared:
        print(f"  gate: {len(undeclared)} undeclared artifact(s) NOT published "
              f"(default '{vis.DEFAULT_VISIBILITY}'): {', '.join(undeclared)}")

    d = load()
    prov = json.load(open(os.path.join(TABLES, "provenance.json")))

    manifest: list[dict] = []

    # --- shared assets: Plotly vendored ONCE --------------------------------------------------
    n = write_text("assets/plotly.min.js", po.get_plotlyjs())
    manifest.append({"path": "assets/plotly.min.js", "bytes": n, "visibility": "public"})
    n = write_text("assets/atlas.css", CSS)
    manifest.append({"path": "assets/atlas.css", "bytes": n, "visibility": "public"})

    # --- copy public artifacts through the gate ----------------------------------------------
    for rel in declared:
        vis.assert_publishable(rel)
        dst = os.path.join(SITE, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(HERE, rel), dst)
        manifest.append({"path": rel, "bytes": os.path.getsize(dst), "visibility": "public"})

    # --- pages ---------------------------------------------------------------------------------
    bodies = {
        "index.html": (pages.overview(d), False),   # overview is tables-only: do not pull the bundle
        "spk-timing.html": (pages.spk_timing(d), True),
        "spk-vs-stimulus.html": (pages.spk_vs_stimulus(d), True),
        "lfp-resolvability.html": (pages.lfp_resolvability(d), True),
        "dsp-support.html": (pages.dsp_support(d), True),
        "session-statistics.html": (pages.session_statistics(d), True),
        "coverage.html": (pages.coverage(d), True),
        "methods.html": (pages.methods(d), False),
        "figures.html": (pages.figures(d), False),
    }
    for fn, title in PAGES:
        if fn == "provenance.html":
            continue
        body, needs_js = bodies[fn]
        n = write_text(fn, shell(body, fn, title.replace("&amp;", "&"), needs_js))
        manifest.append({"path": fn, "bytes": n, "visibility": "public"})

    # provenance last: it reports the manifest of everything else
    n = write_text("provenance.html",
                   shell(pages.provenance(d, prov, sorted(manifest, key=lambda m: m["path"])),
                         "provenance.html", "Provenance", False))
    manifest.append({"path": "provenance.html", "bytes": n, "visibility": "public"})

    mf = sorted(manifest, key=lambda m: m["path"])
    write_text("manifest.json", json.dumps(
        {"analysis": ANALYSIS, "status": STATUS, "source_commit": prov["source_commit"],
         "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "files": mf, "total_bytes": sum(m["bytes"] for m in mf)}, indent=1) + "\n")

    total = sum(m["bytes"] for m in mf)
    print(f"  wrote {len(mf)} files, {total / 1e6:.2f} MB total")
    print(f"  plotly bundle vendored once: {po.get_plotlyjs().__len__() / 1e6:.2f} MB shared "
          f"across {sum(1 for f, _ in PAGES if bodies.get(f, (None, False))[1])} interactive pages")
    print(f"\nPASS: site built at omission/atlas/_site/")


if __name__ == "__main__":
    main()
