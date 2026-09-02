"""Derive the canonical public Analysis 6A tables from frozen receipts.

Reads ONLY the receipts already written under omission/artifacts/data/ -- never NWB, never raw
signals. Emits a small set of publication-safe CSVs under omission/atlas/tables/ plus a private
identifier mapping under omission/atlas/_private/ that is git-ignored and must never reach the
generated site.

Scientific content is NOT recomputed here. Every number is carried through from its receipt; this
script selects columns, renames identifiers, and reconciles counts. If a reconciliation assertion
fires, the receipts and the published tables disagree and the build stops.

IDENTIFIER POLICY (decided 2026-09-02 from evidence, not default)
    The publication-facing draft (omission/context/drafts/04_draft_biorxiv_markdown.md) contains
    zero occurrences of C31o / V182o / V198o and names the animals only as "Subjects (Macaques,
    N=2, age 11 and 17)". There is therefore no established public subject-identifier convention
    to preserve, so subjects AND sessions both take deterministic anonymous labels.

    The mapping is deterministic (sorted order), which means it is invertible by anyone who
    already knows the underlying codes. That is acceptable: the codes themselves are not
    published anywhere in this repo's public surface. It is NOT a cryptographic de-identification
    and is not claimed to be one.

Usage:  python omission/atlas/build_public_tables.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
RECEIPTS = os.path.join(REPO, "omission", "artifacts", "data")
FIGSRC = os.path.join(REPO, "omission", "context", "figures", "analysis6a_timing", "svg")
TABLES = os.path.join(HERE, "tables")
PRIVATE = os.path.join(HERE, "_private")

# ---------------------------------------------------------------------------------------------
# Frozen expectations. These are the claim state Analysis 6A is sealed at. A public table that
# does not reproduce them is a defect in the table, never a reason to edit the number.
# ---------------------------------------------------------------------------------------------
EXPECT = {
    "spk_total": 4130,
    "spk_detected": 637,
    "spk_resolved": 187,
    "spk_with_dt": 139,
    "spk_dt_gt_50": 96,
    "spk_dt_positive": 104,
    "lfp_cells": 1820,
    "lfp_resolved": 114,
}


def _receipt(name: str) -> str:
    p = os.path.join(RECEIPTS, name)
    if not os.path.exists(p):
        raise SystemExit(f"FAIL: required receipt missing: {name}")
    return p


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(df: pd.DataFrame, name: str) -> str:
    """Write a public table with LF endings and a stable column order."""
    path = os.path.join(TABLES, name)
    csv = df.to_csv(index=False, lineterminator="\n")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(csv)
    print(f"  wrote {name:<44s} {len(df):>5d} rows  {len(df.columns):>2d} cols")
    return path


def build_identifier_map(census: pd.DataFrame) -> tuple[dict, dict]:
    """Deterministic anonymous labels. Subjects M1.. by sorted code; sessions S01.. by sorted
    (subject, session) so the numbering is stable across reruns and independent of file order."""
    subs = sorted(census.subject.unique())
    submap = {s: f"M{i + 1}" for i, s in enumerate(subs)}
    pairs = sorted({(r.subject, r.session) for r in census.itertuples()})
    sesmap = {ses: f"S{i + 1:02d}" for i, (_, ses) in enumerate(pairs)}
    return submap, sesmap


def main() -> None:
    os.makedirs(TABLES, exist_ok=True)
    os.makedirs(PRIVATE, exist_ok=True)

    print("Analysis 6A -- canonical public tables")
    print(f"  receipts: omission/artifacts/data/")

    census = pd.read_csv(_receipt("onset6a_corpus_census.csv"))
    submap, sesmap = build_identifier_map(census)

    def pub(df: pd.DataFrame) -> pd.DataFrame:
        """Replace private identifiers with public labels and drop the private columns."""
        out = df.copy()
        out["subject_public"] = out.subject.map(submap)
        out["session_public"] = out.session.map(sesmap)
        if out.subject_public.isna().any() or out.session_public.isna().any():
            raise SystemExit("FAIL: an identifier had no public label -- refusing to emit")
        return out.drop(columns=["subject", "session"])

    # ----------------------------------------------------------------------------------------
    # 1. SPK resolved units  (Figures A2, A3)
    # ----------------------------------------------------------------------------------------
    ru = pd.read_csv(_receipt("onset6a_corpus_resolved_units.csv"))
    assert len(ru) == EXPECT["spk_resolved"], f"resolved units drifted: {len(ru)}"
    ru = pub(ru)
    # A unit index is only meaningful inside its session; make the public id session-scoped so it
    # cannot be joined back to anything and cannot be mistaken for a corpus-wide unit number.
    ru = ru.sort_values(["session_public", "unit"]).reset_index(drop=True)
    ru["unit_public"] = ru.groupby("session_public").cumcount().add(1)
    ru["unit_public"] = ru.session_public + "-U" + ru.unit_public.astype(str).str.zfill(3)
    spk = ru[[
        "unit_public", "subject_public", "session_public", "area", "unit_class",
        "T_om", "T_om_boot_sd", "om_sign", "om_estimator_spread", "T_om_censored",
        "T_stim", "stim_sign", "dT_om_minus_stim", "dT_boot_sd", "dT_gt_50",
    ]].rename(columns={"dT_om_minus_stim": "dT_ms", "om_sign": "om_sign_numeric"})
    spk["om_direction"] = spk.om_sign_numeric.map({1.0: "increase", -1.0: "decrease"})
    spk = spk.drop(columns=["om_sign_numeric"])
    n_dt = int(spk.dT_ms.notna().sum())
    n_pos = int((spk.dT_ms > 0).sum())
    n_50 = int(spk.dT_gt_50.sum())
    assert n_dt == EXPECT["spk_with_dt"], f"dT-defined drifted: {n_dt}"
    assert n_pos == EXPECT["spk_dt_positive"], f"dT>0 drifted: {n_pos}"
    assert n_50 == EXPECT["spk_dt_gt_50"], f"|dT|>50 drifted: {n_50}"
    p1 = _write(spk, "analysis6a_spk_resolved_public.csv")

    # ----------------------------------------------------------------------------------------
    # 2. SPK census funnel  (Figure A1) -- per session, so the funnel is auditable
    # ----------------------------------------------------------------------------------------
    cen = pub(census)
    funnel = cen[[
        "subject_public", "session_public", "spk_total", "detected", "resolved",
        "dT_gt_50", "resolved_up", "resolved_down",
    ]].rename(columns={
        "spk_total": "n_units_eligible",
        "detected": "n_omission_detected",     # the receipt's "resolved" column means DETECTED
        "resolved": "n_latency_resolved",      # this is the true resolved count
        "dT_gt_50": "n_abs_dT_gt_50",
    }).sort_values("session_public").reset_index(drop=True)
    assert funnel.n_units_eligible.sum() == EXPECT["spk_total"]
    assert funnel.n_omission_detected.sum() == EXPECT["spk_detected"]
    assert funnel.n_latency_resolved.sum() == EXPECT["spk_resolved"]
    assert funnel.n_abs_dT_gt_50.sum() == EXPECT["spk_dt_gt_50"]
    p2 = _write(funnel, "analysis6a_spk_census_public.csv")

    # ----------------------------------------------------------------------------------------
    # 3. SPK session-level statistics  (Figure C1, C3)
    # ----------------------------------------------------------------------------------------
    st = pub(pd.read_csv(_receipt("onset6a_session_sign_timing.csv")))
    st = st[["subject_public", "session_public", "n_up", "n_down",
             "median_up", "median_down", "D_s", "eligible"]]
    dt = pub(pd.read_csv(_receipt("onset6a_session_dT.csv")))
    dt = dt[["subject_public", "session_public", "n_units_with_dT",
             "median_dT", "frac_dT_pos", "D_s", "eligible"]]
    sess = st.merge(dt, on=["subject_public", "session_public"], how="outer",
                    suffixes=("_signtiming", "_dT")).sort_values("session_public")
    p3 = _write(sess.reset_index(drop=True), "analysis6a_spk_session_stats_public.csv")

    # ----------------------------------------------------------------------------------------
    # 4. LFP resolvability by frequency  (Figure B1, B4)
    # ----------------------------------------------------------------------------------------
    lf = pd.read_csv(_receipt("onset6a_corpus_lfp_by_freq.csv"))
    assert lf.cells.sum() == EXPECT["lfp_cells"], f"LFP census drifted: {lf.cells.sum()}"
    assert lf.resolved.sum() == EXPECT["lfp_resolved"], f"LFP resolved drifted: {lf.resolved.sum()}"
    lf = lf.rename(columns={
        "cells": "n_cells", "resolved": "n_resolved", "pct": "pct_resolved",
        "cp_lo": "cp95_lo", "cp_hi": "cp95_hi",
        "n_dec": "n_resolved_decrease", "n_inc": "n_resolved_increase",
        "median_spread_unres": "median_estimator_spread_unresolved_ms",
        "median_T_om": "median_T_om_ms",
    })
    p4 = _write(lf, "analysis6a_lfp_frequency_public.csv")

    # ----------------------------------------------------------------------------------------
    # 5. LFP session-level LOW vs HIGH  (Figure B2, C2)
    # ----------------------------------------------------------------------------------------
    lh = pub(pd.read_csv(_receipt("onset6a_session_lfp_lowhigh.csv")))
    lh = lh[["subject_public", "session_public", "n_low_cells", "n_high_cells",
             "res_low", "res_high", "r_low_pct", "r_high_pct", "D_s_pct"]]
    p5 = _write(lh.sort_values("session_public").reset_index(drop=True),
                "analysis6a_lfp_session_stats_public.csv")

    # ----------------------------------------------------------------------------------------
    # 6. LFP censoring / boundary pinning  (Figure B4)
    # ----------------------------------------------------------------------------------------
    pin = pd.read_csv(_receipt("onset6a_corpus_lfp_pinning.csv")).rename(columns={
        "resolved": "n_resolved", "at_bound": "n_at_lower_bound",
        "le_20ms": "n_le_20ms", "frac_le_20ms": "frac_le_20ms",
        "median_T_om_unpinned": "median_T_om_unpinned_ms",
    })
    p6 = _write(pin, "analysis6a_lfp_censoring_public.csv")

    # ----------------------------------------------------------------------------------------
    # 7. DSP transform temporal support  (Figure B3) -- from the figure's own frozen source table
    # ----------------------------------------------------------------------------------------
    sup = pd.read_csv(os.path.join(FIGSRC, "fig6a_B3_source_transform_support.csv"))
    p7 = _write(sup, "analysis6a_dsp_temporal_support_public.csv")

    # ----------------------------------------------------------------------------------------
    # 8. Coverage / design  (Figure D)
    # ----------------------------------------------------------------------------------------
    up = pd.read_csv(_receipt("onset6a_corpus_units_pooled.csv"))
    assert len(up) == EXPECT["spk_total"], f"pooled units drifted: {len(up)}"
    up = pub(up)
    cov = (up.groupby(["subject_public", "session_public", "area"])
             .size().rename("n_units_eligible").reset_index())
    p8 = _write(cov, "analysis6a_coverage_public.csv")

    # ----------------------------------------------------------------------------------------
    # 9. Headline statistics  (every number the site is allowed to display as a claim)
    # ----------------------------------------------------------------------------------------
    slt = json.load(open(_receipt("onset6a_session_level_tests.json")))
    # Holm is READ from the receipt, never typed. An earlier version of this script carried the
    # rounded literal 1.7e-4 here; independent verification flagged it. A displayed value that no
    # script computed from data is exactly the failure mode the project's first tripwire names,
    # and rounding it by hand also silently hid which family the correction belongs to.
    # `holm_adjusted` is the m=2 family {test1, test2}; the receipt separately records an m=3
    # family, which is a DIFFERENT correction and must not be substituted for this one.
    holm_family = slt["holm_adjusted"]
    rows = []
    for key, label, holm_key in (
        ("test1", "SPK increase-vs-decrease timing (session sign x timing)",
         "test1_spk_sign_timing"),
        ("test2", "LFP HIGH-minus-LOW temporal resolvability", "test2_lfp_low_vs_high"),
        ("test3_dT", "SPK omission-minus-stimulus latency shift", None),
    ):
        t = slt[key]
        holm = holm_family[holm_key] if holm_key in holm_family else None
        rows.append({
            "test": label,
            "n_sessions": t["n_sessions"],
            "n_nonzero_sessions": t["n_nonzero"],
            "median_D": t["median_D"],
            "signflip_exact_p": t["signflip_exact_p"],
            "n_permutations_enumerated": t["n_permutations_enumerated"],
            "holm_p": holm if holm is not None else "",
            "wilcoxon_p_secondary": t["wilcoxon_p_approx"],
            "sign_test_p_secondary": t["sign_test_p"],
        })
    p9 = _write(pd.DataFrame(rows), "analysis6a_session_tests_public.csv")

    # ----------------------------------------------------------------------------------------
    # Private mapping -- untracked, and never read by the site builder.
    # ----------------------------------------------------------------------------------------
    mp = os.path.join(PRIVATE, "identifier_map.json")
    with open(mp, "w", newline="", encoding="utf-8") as fh:
        json.dump({"subjects": submap, "sessions": sesmap,
                   "note": "PRIVATE. Never publish. Not read by build_atlas.py."},
                  fh, indent=1)
        fh.write("\n")
    print(f"  wrote _private/identifier_map.json  ({len(submap)} subjects, {len(sesmap)} sessions)"
          "  [GIT-IGNORED]")

    # ----------------------------------------------------------------------------------------
    # Provenance
    # ----------------------------------------------------------------------------------------
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, check=True,
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = "unknown"
    paths = [p1, p2, p3, p4, p5, p6, p7, p8, p9]
    prov = {
        "analysis": "onset-6a",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_commit": sha,
        "builder": "omission/atlas/build_public_tables.py",
        "identifier_policy": "subjects and sessions anonymized (no public convention in draft)",
        "tables": {os.path.basename(p): {"sha256": _sha256(p),
                                         "rows": sum(1 for _ in open(p)) - 1} for p in paths},
    }
    pp = os.path.join(TABLES, "provenance.json")
    with open(pp, "w", newline="", encoding="utf-8") as fh:
        json.dump(prov, fh, indent=1)
        fh.write("\n")
    print(f"  wrote tables/provenance.json  (commit {sha[:8]})")
    print(f"\nPASS: 9 canonical public tables reconcile with receipts.")


if __name__ == "__main__":
    main()
