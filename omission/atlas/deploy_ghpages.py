"""Stage the verified atlas into an ISOLATED deployment worktree for gh-pages.

Deployment never runs from the shared working tree. Three staging collisions between concurrent
agent sessions on 2026-09-02 (29ed345, 9211b31, 2af5f86 -- the last one broke the committed docs
build) established that a shared index cannot be made safe by prose discipline alone, so the
deployment target is a dedicated `git worktree` checked out at a specific verified commit.

This script does NOT rebuild the site and does NOT rerun any scientific estimation. It copies the
already-verified bytes of omission/atlas/_site/ and proves they are the ones that were verified by
recomputing the site fingerprint before and after the copy.

It also does NOT push. Pushing is a separate, explicit act.

Usage:
    python omission/atlas/deploy_ghpages.py <deployment-worktree-path> <expected-site-sha256>
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "_site"
SUBPATH = "analyses/onset-6a"          # the published URL path, matching docs/12_*.md

# Header/footer markup and tokens are kept byte-identical to omission/atlas/build_atlas.py's
# HNXJ_SHELL_CSS/hnxj_header()/HNXJ_FOOTER and to hnxj.github.io's own shell CSS -- this file
# stays a self-contained string (per the module's "does not rebuild the site" contract) rather
# than importing build_atlas, so the three copies must be kept in sync by hand if any one changes.
ROOT_INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>jnwb analysis atlas</title>
<style>
:root{color-scheme:light;--bg:#fbfbfa;--fg:#1a1a1a;--mut:#5b6570;--line:#dfe3e8;--accent:#1f5f8b}
body{margin:0;font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
background:var(--bg);color:var(--fg)}
.hnxj-bar{background:var(--fg);color:#fff}
.hnxj-bar-inner{max-width:720px;margin:0 auto;padding:0 24px;display:flex;align-items:center;
gap:22px;height:44px;font-size:13.5px;flex-wrap:wrap}
.hnxj-bar-inner a{color:#c7ccd1;text-decoration:none}
.hnxj-bar-inner a:first-child{color:#fff;font-weight:700;letter-spacing:.02em;margin-right:4px}
.hnxj-bar-inner a:hover{color:#fff}
.hnxj-bar-inner a.active{color:#fff;border-bottom:2px solid var(--accent);padding-bottom:2px}
.w{max-width:720px;margin:0 auto;padding:40px 24px 56px}
h1{font-size:22px;margin:0 0 6px;letter-spacing:-.01em}
p{color:var(--mut)}
a.card{display:block;text-decoration:none;color:inherit;background:#fff;border:1px solid var(--line);
border-left:3px solid var(--accent);border-radius:9px;padding:16px 18px;margin:18px 0}
a.card:hover{border-color:var(--accent)}
a.card h2{font-size:16px;margin:0 0 4px;color:var(--accent)}
a.card p{margin:0;font-size:13.5px}
.badge{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11.5px;font-weight:600;
background:#fdf3d8;color:#8a6d1f;border:1px solid #e8d4a0;margin-top:8px}
footer{color:var(--mut);font-size:12.5px;border-top:1px solid var(--line);margin-top:34px;padding-top:14px}
.hnxj-foot{border-top:1px solid var(--line);margin-top:8px}
.hnxj-foot-inner{max-width:720px;margin:0 auto;padding:16px 24px;display:flex;flex-wrap:wrap;
gap:16px;font-size:12.5px}
.hnxj-foot-inner a{color:var(--mut);text-decoration:none}
.hnxj-foot-inner a:hover{color:var(--accent)}
</style></head><body>
<div class="hnxj-bar"><div class="hnxj-bar-inner">
<a href="https://hnxj.github.io/">HNXJ</a>
<a href="https://hnxj.github.io/jaxfne/">JaxFNE</a>
<a href="https://hnxj.github.io/jnwb/" class="active">jnwb</a>
<a href="https://hnxj.github.io/labyrinth/">Labyrinth</a>
<a href="https://hnxj.github.io/#analyses">Analyses</a>
</div></div>
<div class="w">
<h1>jnwb analysis atlas</h1>
<p>Generated analysis interfaces built from reviewed public tables. Package documentation lives
separately on <a href="https://jnwb.readthedocs.io/">Read the Docs</a>.</p>
<a class="card" href="analyses/onset-6a/">
  <h2>Analysis 6A &mdash; onset timing during stimulus omission</h2>
  <p>Which changes first during stimulus omission, the local field potential or spiking?
  Macaque multi-area laminar electrophysiology.</p>
  <span class="badge">Exploratory analysis &middot; not publication-final</span>
</a>
<footer>Each atlas is a view of canonical evidence, not a new scientific authority. No raw data,
recording identifiers, or trial-level signals are published.</footer>
</div>
<div class="hnxj-foot"><div class="hnxj-foot-inner">
<a href="https://hnxj.github.io/">HNXJ</a>
<a href="https://hnxj.github.io/jaxfne/">JaxFNE</a>
<a href="https://hnxj.github.io/jnwb/">jnwb</a>
<a href="https://hnxj.github.io/labyrinth/">Labyrinth</a>
<a href="https://github.com/hnxj">GitHub</a>
<a href="https://hnxj.github.io/#analyses">Analyses</a>
</div></div>
</body></html>
"""


def fingerprint(root: Path) -> tuple[str, int, int]:
    ent = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            data = p.read_bytes()
            ent.append((rel, len(data), hashlib.sha256(data).hexdigest()))
    ent.sort()
    agg = hashlib.sha256("\n".join(f"{r} {s} {h}" for r, s, h in ent).encode()).hexdigest()
    return agg, len(ent), sum(e[1] for e in ent)


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    wt, expected = Path(sys.argv[1]).resolve(), sys.argv[2]

    if not SITE.is_dir():
        sys.exit("FAIL: no built site. Run build_atlas.py and verify_site.py first.")
    if not wt.is_dir():
        sys.exit(f"FAIL: deployment worktree does not exist: {wt}")
    if wt == HERE.parent.parent:
        sys.exit("FAIL: refusing to deploy from the shared working tree.")

    got, nfiles, nbytes = fingerprint(SITE)
    print(f"source _site: {nfiles} files, {nbytes:,} bytes")
    print(f"  fingerprint {got}")
    if got != expected:
        sys.exit(f"FAIL: _site fingerprint does not match the verified value.\n"
                 f"  expected {expected}\n  got      {got}\n"
                 "The bytes about to be published are not the bytes that were verified.")
    print("  MATCHES the verified fingerprint")

    dest = wt / SUBPATH
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SITE, dest)

    back, n2, b2 = fingerprint(dest)
    if back != got:
        sys.exit(f"FAIL: copied tree fingerprint {back} != source {got}")
    print(f"copied -> {SUBPATH}/  ({n2} files, {b2:,} bytes, fingerprint preserved)")

    # .nojekyll: without it GitHub Pages runs Jekyll, which silently drops paths beginning with
    # an underscore and can rewrite others. The atlas has no underscore paths today, but relying
    # on that is a latent trap for any future asset.
    (wt / ".nojekyll").write_text("", newline="\n")
    (wt / "index.html").write_text(ROOT_INDEX, encoding="utf-8", newline="\n")
    print("wrote .nojekyll and root index.html")

    st = subprocess.run(["git", "status", "--porcelain"], cwd=wt,
                        capture_output=True, text=True, check=True).stdout
    print(f"\ndeployment worktree has {len(st.splitlines())} changed path(s), staged by name below")


if __name__ == "__main__":
    main()
