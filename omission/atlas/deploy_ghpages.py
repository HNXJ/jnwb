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

ROOT_INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>jnwb analysis atlas</title>
<style>
:root{color-scheme:light}
body{margin:0;font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
background:#fbfbfa;color:#1a1a1a}
.w{max-width:720px;margin:0 auto;padding:56px 24px}
h1{font-size:22px;margin:0 0 6px;letter-spacing:-.01em}
p{color:#5b6570}
a.card{display:block;text-decoration:none;color:inherit;background:#fff;border:1px solid #dfe3e8;
border-left:3px solid #1f5f8b;border-radius:9px;padding:16px 18px;margin:18px 0}
a.card:hover{border-color:#1f5f8b}
a.card h2{font-size:16px;margin:0 0 4px;color:#1f5f8b}
a.card p{margin:0;font-size:13.5px}
.badge{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11.5px;font-weight:600;
background:#fdf3d8;color:#8a6d1f;border:1px solid #e8d4a0;margin-top:8px}
footer{color:#5b6570;font-size:12.5px;border-top:1px solid #dfe3e8;margin-top:34px;padding-top:14px}
</style></head><body><div class="w">
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
</div></body></html>
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
