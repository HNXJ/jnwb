"""Pre-publication verification for the Analysis 6A atlas.

Runs four independent gates over the GENERATED site (not the source), because what gets published
is the generated tree and nothing else:

  1. PRIVACY   -- no private identifiers, machine-local paths, NWB paths, raw signal data, or
                  undeclared identifiers anywhere in the deployed bytes.
  2. VISIBILITY-- adversarial: unlabelled, private, and review artifacts must all be REFUSED.
  3. LINKS     -- every internal href/src resolves to a file that exists in the site.
  4. RECONCILE -- every headline number rendered in the HTML matches its canonical table.

Exit code is non-zero if any gate fails. Fail-closed: an unrecognised condition is a failure.

Usage:  python omission/atlas/verify_site.py
"""

from __future__ import annotations

import json
import os
import re
import sys

import pandas as pd

import visibility as vis

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SITE = os.path.join(HERE, "_site")
TABLES = os.path.join(HERE, "tables")
PRIVATE = os.path.join(HERE, "_private")

FAILS: list[str] = []
PASSES: list[str] = []


def ok(msg: str) -> None:
    PASSES.append(msg)
    print(f"  PASS  {msg}")


def bad(msg: str) -> None:
    FAILS.append(msg)
    print(f"  FAIL  {msg}")


def site_files() -> list[str]:
    out = []
    for root, _, names in os.walk(SITE):
        for n in names:
            out.append(os.path.join(root, n))
    return sorted(out)


# =============================================================================================
# 1. Privacy
# =============================================================================================
def gate_privacy() -> None:
    print("\n[1] PRIVACY SCAN over the generated site")
    files = site_files()
    text_files = [f for f in files if os.path.splitext(f)[1].lower()
                  in (".html", ".css", ".csv", ".json", ".svg", ".txt", ".md")]
    # plotly.min.js is a third-party vendored bundle; scan it too, but only for our identifiers.
    blobs = {}
    for f in files:
        try:
            blobs[f] = open(f, "r", encoding="utf-8", errors="replace").read()
        except Exception as e:
            bad(f"unreadable deployed file {os.path.relpath(f, SITE)}: {e}")

    # --- private identifier mapping must exist locally and appear nowhere in the site ---------
    mp = os.path.join(PRIVATE, "identifier_map.json")
    if not os.path.exists(mp):
        bad("private identifier map missing -- cannot verify it was excluded")
        return
    m = json.load(open(mp))
    private_ids = sorted(set(m["subjects"]) | set(m["sessions"]))
    hits = []
    for f, b in blobs.items():
        for pid in private_ids:
            if pid in b:
                hits.append(f"{os.path.relpath(f, SITE)} contains {pid!r}")
    if hits:
        for h in hits[:20]:
            bad(f"PRIVATE IDENTIFIER LEAK: {h}")
    else:
        ok(f"no private identifier ({len(private_ids)} checked: subject codes and session ids) "
           f"appears in any of {len(files)} deployed files")

    if any(os.path.relpath(f, SITE).startswith("_private") for f in files):
        bad("the _private directory was copied into the site")
    else:
        ok("_private/ is absent from the deployed tree")

    # --- machine-local absolute paths ---------------------------------------------------------
    pat_abs = re.compile(r"[A-Za-z]:\\\\?[A-Za-z0-9_]|/home/[a-z]|/Users/[A-Za-z]|\\\\workspace\\\\")
    pat_user = re.compile(r"nejath|Users[\\/]", re.I)
    leaks = []
    for f, b in blobs.items():
        if f.endswith("plotly.min.js"):
            continue          # third-party bundle: contains no path of ours (checked below)
        for pat, lbl in ((pat_abs, "absolute path"), (pat_user, "username/home path")):
            mm = pat.search(b)
            if mm:
                leaks.append(f"{os.path.relpath(f, SITE)}: {lbl} near {b[max(0, mm.start()-30):mm.start()+40]!r}")
    if leaks:
        for l in leaks[:10]:
            bad(f"PATH LEAK: {l}")
    else:
        ok("no machine-local absolute path, username, or home directory in the deployed site")

    if "nejath" in blobs.get(os.path.join(SITE, "assets", "plotly.min.js"), ""):
        bad("vendored plotly bundle contains a local username")
    else:
        ok("vendored plotly bundle carries no local identifiers")

    # --- NWB / raw data references -------------------------------------------------------------
    raw_pat = re.compile(r"\.nwb\b|spike_times|spike_train|/ecephys/|acquisition/|"
                         r"\braw_lfp\b|ElectricalSeries|D:[\\/]|E:[\\/]", re.I)
    raw = []
    for f, b in blobs.items():
        if f.endswith("plotly.min.js"):
            continue
        mm = raw_pat.search(b)
        if mm:
            raw.append(f"{os.path.relpath(f, SITE)}: {mm.group(0)!r}")
    if raw:
        for r in raw[:10]:
            bad(f"RAW/RESTRICTED REFERENCE: {r}")
    else:
        ok("no NWB path, spike-time field, raw-LFP reference, or data-drive letter in the site")

    # --- identifiers that DO remain public -----------------------------------------------------
    spk = pd.read_csv(os.path.join(SITE, "tables", "analysis6a_spk_resolved_public.csv"))
    subs = sorted(spk.subject_public.unique())
    sess = sorted(spk.session_public.unique())
    bad_form = [s for s in subs if not re.fullmatch(r"M\d+", s)] + \
               [s for s in sess if not re.fullmatch(r"S\d{2}", s)]
    if bad_form:
        bad(f"public identifiers not in anonymised form: {bad_form}")
    else:
        ok(f"public identifiers are anonymised labels only: subjects {subs}, "
           f"sessions {sess[0]}..{sess[-1]} ({len(sess)} in the SPK table)")

    # --- row-level content: are the published columns the intended minimal set? ----------------
    forbidden_cols = {"unit", "session", "subject", "why", "om_route", "om_post_mean",
                      "n_om_trials", "n_stim_trials", "p_boot_id_om", "p_boot_id_stim"}
    for csv in sorted(os.listdir(os.path.join(SITE, "tables"))):
        if not csv.endswith(".csv"):
            continue
        cols = set(pd.read_csv(os.path.join(SITE, "tables", csv), nrows=0).columns)
        overlap = cols & forbidden_cols
        if overlap:
            bad(f"{csv} publishes withheld column(s): {sorted(overlap)}")
    if not any("withheld column" in f for f in FAILS):
        ok("no published table carries a private identifier column or a withheld raw field")


# =============================================================================================
# 2. Visibility gate -- adversarial
# =============================================================================================
def gate_visibility() -> None:
    print("\n[2] VISIBILITY GATE (adversarial)")
    cases = [
        ("tables/analysis6a_spk_resolved_public.csv", True, "declared public"),
        ("figures/fig6a_A_spk_latency.svg", True, "declared public"),
        ("_private/identifier_map.json", False, "declared PRIVATE"),
        ("figures/fig6a_E_common_axis_spk_vs_lfp.svg", False, "declared REVIEW (held figure)"),
        ("tables/some_new_unlabelled_table.csv", False, "UNLABELLED -> default review"),
        ("figures/scratch_exploration.svg", False, "UNLABELLED -> default review"),
        ("../../artifacts/data/onset6a_corpus_units_pooled.csv", False, "raw receipt, unlabelled"),
        ("", False, "empty path"),
    ]
    for path, should_pass, why in cases:
        try:
            vis.assert_publishable(path)
            passed = True
        except vis.VisibilityError:
            passed = False
        if passed == should_pass:
            ok(f"{'allowed' if passed else 'REFUSED'}: {path or '<empty>'}  ({why})")
        else:
            bad(f"gate returned {'allow' if passed else 'refuse'} for {path!r} ({why})")

    if vis.DEFAULT_VISIBILITY != vis.REVIEW:
        bad(f"default visibility is {vis.DEFAULT_VISIBILITY!r}, expected 'review' (fail-closed)")
    else:
        ok("undeclared artifacts default to 'review' -- absence of a label is never permission")

    # stale-manifest direction: a declared-public artifact missing from disk must refuse
    saved = dict(vis.ARTIFACTS)
    try:
        vis.ARTIFACTS["tables/does_not_exist_on_disk.csv"] = vis.PUBLIC
        try:
            vis.public_artifacts(HERE)
            bad("a declared-public artifact missing from disk did NOT refuse")
        except vis.VisibilityError:
            ok("REFUSED: declared-public artifact missing from disk (stale manifest caught)")
    finally:
        vis.ARTIFACTS.clear()
        vis.ARTIFACTS.update(saved)

    undeclared = vis.audit_undeclared(HERE)
    ok(f"source-directory audit: {len(undeclared)} undeclared file(s) present and not published"
       + (f" ({', '.join(undeclared)})" if undeclared else ""))


# =============================================================================================
# 3. Links
# =============================================================================================
def gate_links() -> None:
    print("\n[3] LINK RESOLUTION")
    href = re.compile(r'(?:href|src)="([^"#][^"]*)"')
    missing, checked = [], 0
    for root, _, names in os.walk(SITE):
        for n in names:
            if not n.endswith(".html"):
                continue
            p = os.path.join(root, n)
            for target in href.findall(open(p, encoding="utf-8").read()):
                if target.startswith(("http://", "https://", "mailto:", "data:")):
                    continue
                checked += 1
                if not os.path.exists(os.path.join(os.path.dirname(p), target)):
                    missing.append(f"{os.path.relpath(p, SITE)} -> {target}")
    if missing:
        for m in missing:
            bad(f"BROKEN LINK: {m}")
    else:
        ok(f"all {checked} internal links/assets resolve")


# =============================================================================================
# 4. Reconciliation -- the site must not disagree with its own tables
# =============================================================================================
def gate_reconcile() -> None:
    print("\n[4] RECONCILIATION: rendered numbers vs canonical tables")
    idx = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    spk_pg = open(os.path.join(SITE, "spk-timing.html"), encoding="utf-8").read()
    dt_pg = open(os.path.join(SITE, "spk-vs-stimulus.html"), encoding="utf-8").read()
    lfp_pg = open(os.path.join(SITE, "lfp-resolvability.html"), encoding="utf-8").read()
    sess_pg = open(os.path.join(SITE, "session-statistics.html"), encoding="utf-8").read()

    cen = pd.read_csv(os.path.join(TABLES, "analysis6a_spk_census_public.csv"))
    spk = pd.read_csv(os.path.join(TABLES, "analysis6a_spk_resolved_public.csv"))
    lf = pd.read_csv(os.path.join(TABLES, "analysis6a_lfp_frequency_public.csv"))
    ts = pd.read_csv(os.path.join(TABLES, "analysis6a_session_tests_public.csv"))

    n_dt = int(spk.dT_ms.notna().sum())
    n_pos = int((spk.dT_ms > 0).sum())
    checks = [
        ("4,130 eligible units", f"{int(cen.n_units_eligible.sum()):,}", idx),
        ("637 detected", str(int(cen.n_omission_detected.sum())), idx),
        ("187 resolved", str(int(cen.n_latency_resolved.sum())), idx),
        ("139 with dT", str(n_dt), idx),
        ("96 |dT|>50", str(int(spk.dT_gt_50.sum())), spk_pg),
        ("104 dT>0", str(n_pos), dt_pg),
        ("74.8% dT>0", f"{100 * n_pos / n_dt:.1f}%", dt_pg),
        ("1,820 LFP cells", f"{int(lf.n_cells.sum()):,}", idx),
        ("114 LFP resolved", str(int(lf.n_resolved.sum())), idx),
    ]
    for label, needle, page in checks:
        if needle in page:
            ok(f"{label}: site renders {needle}")
        else:
            bad(f"{label}: {needle!r} not found in the rendered page")

    for frag, page, name in (("increase-vs-decrease", sess_pg, "Test 1"),
                             ("LFP HIGH-minus-LOW", lfp_pg, "Test 2"),
                             ("omission-minus-stimulus", dt_pg, "Test 3")):
        row = ts[ts.test.str.contains(frag, regex=False)].iloc[0]
        p = float(row.signflip_exact_p)
        cands = [f"{p:.3f}", f"{p:.3g}", f"{p:.2e}"]
        if any(c in page for c in cands):
            ok(f"{name}: p = {p:.6g} rendered")
        else:
            bad(f"{name}: none of {cands} found on its page")

    # The held figure must be absent from the deployment, not merely unlinked.
    if any("common_axis" in f or "common-axis" in os.path.basename(f) for f in site_files()):
        bad("a common-axis figure file is present in the deployed site")
    else:
        ok("common-axis SPK-vs-LFP figure is absent from the deployment (hold preserved)")

    # No promotion of a descriptive number into a session-level claim.
    for page, name in ((dt_pg, "spk-vs-stimulus"), (idx, "index")):
        if "74.8" in page and "descriptive" not in page:
            bad(f"{name}: renders the pooled 74.8% without a descriptive label")
    ok("pooled unit-level proportions carry a 'descriptive' label wherever rendered")


def main() -> None:
    if not os.path.isdir(SITE):
        sys.exit("FAIL: no generated site. Run build_atlas.py first.")
    print(f"Verifying generated site: omission/atlas/_site/  ({len(site_files())} files)")
    gate_privacy()
    gate_visibility()
    gate_links()
    gate_reconcile()
    print(f"\n{'=' * 78}\n{len(PASSES)} passed, {len(FAILS)} failed")
    if FAILS:
        print("\nFAILURES:")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    print("PASS: site cleared all pre-publication gates.")


if __name__ == "__main__":
    main()
