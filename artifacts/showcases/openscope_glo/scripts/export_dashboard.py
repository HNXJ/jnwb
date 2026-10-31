"""Build the #openscope-glo dashboard record and its figures from stored tables and receipts.

Usage: python scripts/export_dashboard.py
Writes export/openscope_glo.json and export/figures/<id>.png plus <id>.dark.png. Reads only
local files; every plotted value comes from a results table or receipt in this repository.
"""
import hashlib
import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
R = REPO / "results"
OUT = REPO / "export"
FIG = OUT / "figures"
AREAS = ["VISp", "VISl", "VISrl", "VISal", "VISpm", "VISam"]
# Dashboard tokens (C:/workspace/jnwb scripts/dashboard/index.html, :root and dark).
THEMES = {
    "light": {"bg": "#ffffff", "text": "#1b1f24", "muted": "#5b6573", "border": "#dde1e6",
              "series": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#5b6573"]},
    "dark": {"bg": "#0f1216", "text": "#e6e9ee", "muted": "#9aa4b2", "border": "#2a313a",
             "series": ["#56B4E9", "#E69F00", "#009E73", "#CC79A7", "#9aa4b2"]},
}
DANDI_URL = "https://dandiarchive.org/dandiset/000253/0.240503.0152"
PAPER_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC11741236/"
CODE_LOC = "local git repository C:/workspace/jnwb-showcase (not public)"
ORIGIN = {"kind": "showcase", "author": "HNXJ", "issue": None}


def replication(report, scope, verdict, seed, note):
    """One independent rerun of an entry, dated by the commit that holds its report."""
    date = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%cs", "--", str(report)],
                          capture_output=True, text=True, check=True).stdout.strip()
    return {"by": "independent rerun with separate code", "date": date, "scope": scope,
            "verdict": verdict, "seed": seed, "report_sha256": sha(report), "note": note}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_head():
    head = (REPO / ".git" / "HEAD").read_text().strip()
    ref = head.split(" ", 1)[1] if head.startswith("ref:") else None
    return (REPO / ".git" / ref).read_text().strip() if ref else head


def style(ax, t):
    ax.set_facecolor(t["bg"])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(t["muted"])
    ax.tick_params(colors=t["text"], labelsize=9)
    ax.yaxis.label.set_color(t["text"])
    ax.xaxis.label.set_color(t["text"])
    ax.title.set_color(t["text"])
    ax.axhline(0, color=t["muted"], lw=0.8, zorder=0)


def forest(series, ylabel, title, name, offsets=None):
    """series: list of (label, DataFrame with area, mean, lo, hi). One panel, areas on x."""
    paths = {}
    for theme, t in THEMES.items():
        fig, ax = plt.subplots(figsize=(7.5, 3.4), dpi=150)
        fig.patch.set_facecolor(t["bg"])
        n = len(series)
        w = 0.8 / n
        for k, (lab, df) in enumerate(series):
            df = df.set_index("area").reindex(AREAS)
            x = [i - 0.4 + w * (k + 0.5) for i in range(len(AREAS))]
            ax.errorbar(x, df["mean"], yerr=[df["mean"] - df["lo"], df["hi"] - df["mean"]], fmt="o", ms=4,
                        color=t["series"][k], ecolor=t["series"][k], elinewidth=1.2, capsize=0, label=lab)
        ax.set_xticks(range(len(AREAS)), AREAS)
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=10, loc="left", color=t["text"])
        style(ax, t)
        leg = ax.legend(fontsize=8, frameon=False, ncol=min(n, 3), loc="upper left", bbox_to_anchor=(0, -0.12))
        for txt in leg.get_texts():
            txt.set_color(t["text"])
        fig.tight_layout()
        p = FIG / (f"{name}.png" if theme == "light" else f"{name}.dark.png")
        fig.savefig(p, facecolor=t["bg"])
        plt.close(fig)
        paths[theme] = p
    return paths


def s1_series(d):
    c = pd.read_csv(d / "confirmatory.csv")
    dr = pd.read_csv(d / "drift.csv")
    out = []
    for key, lab in (("C1_main_vs_random_xxxx", "C1 main − random"), ("C2_main_vs_seq_xxxx", "C2 main − sequenced"),
                     ("C3_random_vs_seq_xxxx", "C3 random − sequenced"), ("C4_random_vs_seq_yyyy", "C4 yyyy random − sequenced")):
        s = c[(c.contrast == key) & c.p.notna()]
        out.append((lab, s.rename(columns={"mean_hz": "mean", "ci_lo": "lo", "ci_hi": "hi"})[["area", "mean", "lo", "hi"]]))
    s = dr[dr.mean_hz.notna()] if "mean_hz" in dr else dr
    out.append(("D main 1 − main 2 (drift)", s.rename(columns={"mean_hz": "mean", "ci_lo": "lo", "ci_hi": "hi"})[["area", "mean", "lo", "hi"]]))
    return c, out


def fmt_q(c):
    return f"{c.q.min():.2f}"


def assets_used(sessions):
    recs = [json.loads(line) for line in open(REPO / "receipts" / "download_000253_ogen.jsonl")]
    return [{"asset_id": r["asset_id"], "sha256": r["dandi_sha256"]} for r in recs
            if Path(r["path"]).name.split("_")[1].removeprefix("ses-") in sessions]


def rel(p):
    """A figure's file name: jnwb reads figures from the folder beside the record."""
    return Path(p).relative_to(FIG).as_posix()


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    head = git_head()
    sessions = sorted(json.load(open(R / "s2v2" / "receipt.json"))["inputs"])
    data_assets = assets_used(sessions)
    common = {"species": "mouse", "relation_to_published": (
        "Uses DANDI 000253, the data of PMC11741236. The paper and its Extended Data show no xxxx "
        "comparison across main, randomized and sequenced contexts and no context decoding "
        "(PUBLISHED_VS_PROPOSED.md)."),
        "links": [{"label": "DANDI 000253 0.240503.0152", "url": DANDI_URL},
                  {"label": "Paper (PMC11741236)", "url": PAPER_URL}]}
    entries = []

    # Showcase 1, filtered (primary, preregistered).
    c, ser = s1_series(R / "s1")
    figs = forest(ser, "Δ(P4 − P3) contrast, Hz", "Showcase 1, responsive units (preregistered)", "glo_s1_responsive")
    tested = c[c.p.notna()]
    entries.append({
        "id": "glo_s1_responsive", "title": "Identical xxxx sequence in three contexts: responsive units",
        "question": "Does the P4 − P3 response to the identical xxxx sequence differ between the main, randomized and sequenced contexts?",
        **{k: common[k] for k in ("relation_to_published", "species")}, "status": "verified",
        "dandi": {"id": "000253", "version": "0.240503.0152", "assets": data_assets},
        "jnwb": {"commit": json.load(open(R / "s1" / "receipt.json"))["jnwb_commit"],
                 "functions": ["nwb_read_io", "filter_by_criteria", "unit_spike_times", "compute_response_metrics",
                               "classify_response_significance", "bin_spikes", "rate_in_window", "exact_sign_flip", "fdr_correct"]},
        "figures": [{"light": rel(figs["light"]), "dark": rel(figs["dark"]),
                     "caption": "Contrasts C1–C4 and drift D per area: mean over mice of the per-mouse median over responsive units.",
                     "units": "Hz", "controls": "drift contrast D (main 1 − main 2)",
                     "uncertainty": "95 % percentile bootstrap over mice (10,000 draws, seed 20261012)"}],
        "result": (f"No contrast passes the preregistered test in any of {len(tested)} tested area × contrast cells "
                   f"(exact sign-flip over mice, BH; smallest p {tested.p.min():.3f}, smallest q {fmt_q(tested)}). "
                   "VISam not tested (5 mice)."),
        "interpretation": ("Every contrast is not distinguishable from zero at this resolution. Bootstrap CIs lie within about "
                           "±1 Hz in VISp, VISl and VISal and reach about 1.7 Hz in VISrl and 1.38 Hz in VISpm; this is not an "
                           "equivalence test. The drift contrast is of the same size, so no context effect is identified either way."),
        "limitations": [
            "Responsiveness was decided on P1 (always x), so the population is x-selected; C4 (yyyy) is measured in units chosen for x.",
            "Context is confounded with time and state (block order fixed, running speed differs between contexts).",
            "With 8 and 7 mice, VISrl and VISpm reach q < 0.05 only if 3 or 6 other cells reject first.",
            "The spike–stimulus clock check is not independent of the stimulus table.",
            "Session 1186358749 follows a different block design and is excluded."],
        "code": {"location": CODE_LOC, "commit": head},
        "receipts": [{"name": "results/s1/receipt.json", "sha256": sha(R / "s1" / "receipt.json")},
                     {"name": "results/s1/confirmatory.csv", "sha256": sha(R / "s1" / "confirmatory.csv")},
                     {"name": "PREREGISTRATION.md", "sha256": sha(REPO / "PREREGISTRATION.md")}],
        "origin": ORIGIN,
        "replications": [replication(
            REPO / "_verify_xhigh" / "item6_compare.txt", "every confirmatory cell, recomputed from the NWB files",
            "reproduces", "20261012",
            "288 of 297 checks match; the 7 mismatches were statements in the write-up, since corrected")],
        "links": common["links"]})

    # Showcase 1, all quality units (exploratory selection check).
    c, ser = s1_series(R / "s1_allunits_exploratory")
    figs = forest(ser, "Δ(P4 − P3) contrast, Hz", "Showcase 1, all quality units (exploratory)", "glo_s1_allunits")
    tested = c[c.p.notna()]
    entries.append({
        "id": "glo_s1_allunits", "title": "Identical xxxx sequence in three contexts: all quality units (selection check)",
        "question": "Does the responsiveness filter change the showcase 1 result?",
        **{k: common[k] for k in ("relation_to_published", "species")}, "status": "exploratory",
        "dandi": {"id": "000253", "version": "0.240503.0152", "assets": data_assets},
        "jnwb": {"commit": json.load(open(R / "s1_allunits_exploratory" / "receipt.json"))["jnwb_commit"],
                 "functions": ["nwb_read_io", "filter_by_criteria", "unit_spike_times", "bin_spikes", "rate_in_window",
                               "exact_sign_flip", "fdr_correct"]},
        "figures": [{"light": rel(figs["light"]), "dark": rel(figs["dark"]),
                     "caption": "As the primary figure, over all quality units in visual areas (post hoc).",
                     "units": "Hz", "controls": "drift contrast D (main 1 − main 2)",
                     "uncertainty": "95 % percentile bootstrap over mice (10,000 draws, one generator seeded 20261012, consumed in table order)"}],
        "result": (f"No cell passes q < 0.05 among {len(tested)} cells (smallest p {tested.p.min():.3f}, smallest q {fmt_q(tested)}); "
                   f"CI bounds lie within ±{tested[['ci_lo', 'ci_hi']].abs().max().max():.1f} Hz."),
        "interpretation": "The responsiveness filter does not change the conclusion; not an equivalence test.",
        "limitations": [
            "Added after the preregistration; exploratory.",
            "Medians include non-responsive units.",
            "CI bounds depend on the bootstrap seed and cell order (VISpm C2 lower bound 0.013–0.017 across seeds).",
            "Independent check reproduced the C2 cells only."],
        "code": {"location": CODE_LOC, "commit": head},
        "receipts": [{"name": "results/s1_allunits_exploratory/receipt.json", "sha256": sha(R / "s1_allunits_exploratory" / "receipt.json")},
                     {"name": "results/s1_allunits_exploratory/confirmatory.csv", "sha256": sha(R / "s1_allunits_exploratory" / "confirmatory.csv")}],
        "origin": ORIGIN,
        "replications": [replication(
            REPO / "_verify_rev2" / "_temp_s1_c2.json", "the C2 cells only", "reproduces", "20261012",
            "the other contrasts were not rerun")],
        "links": common["links"]})

    # Showcase 2, version 2.
    fa, fb = pd.read_csv(R / "s2v2" / "family_A.csv"), pd.read_csv(R / "s2v2" / "family_B.csv")
    ren = {"ci_lo": "lo", "ci_hi": "hi"}
    ser = [("A_P4 − majority baseline", fa[fa.onset == "P4"].rename(columns=ren)[["area", "mean", "lo", "hi"]]),
           ("A_P3 − majority baseline", fa[fa.onset == "P3"].rename(columns=ren)[["area", "mean", "lo", "hi"]]),
           ("A_P4 − A_P3", fb.rename(columns=ren)[["area", "mean", "lo", "hi"]])]
    figs = forest(ser, "accuracy difference", "Showcase 2 v2: context decoding, block-position adjusted", "glo_s2v2")
    auc = pd.read_csv(R / "s2v2" / "auc.csv")
    entries.append({
        "id": "glo_s2v2", "title": "Decoding context from the identical xxxx response (preregistered version 2)",
        "question": "Is main 2 vs sequenced context decodable from responses to the identical xxxx sequence, above the majority baseline and beyond linear drift, and more at P4 than at P3?",
        # Verified: independent rerun of the decoding, _verify_s2v2/.
        **{k: common[k] for k in ("relation_to_published", "species")}, "status": "verified",
        "dandi": {"id": "000253", "version": "0.240503.0152", "assets": data_assets},
        "jnwb": {"commit": json.load(open(R / "s2v2" / "receipt.json"))["jnwb_commit"],
                 "functions": ["nwb_read_io", "filter_by_criteria", "bin_spikes", "nested_cv_linear_svm", "exact_sign_flip", "fdr_correct"]},
        "figures": [{"light": rel(figs["light"]), "dark": rel(figs["dark"]),
                     "caption": "Linear-SVM accuracy minus the majority baseline at P4 and P3, and A_P4 − A_P3, per area; features residualised on block position.",
                     "units": "fraction correct", "controls": "majority baseline on the same folds; block-position covariate",
                     "uncertainty": "95 % percentile bootstrap over mice (10,000 draws, seed 20261012)"}],
        "result": (f"No area decodes context above the majority baseline at P4 or P3 (smallest q {fa.q.min():.2f}; "
                   f"{int((fa['mean'] < 0).sum())} of {len(fa)} means negative), and no P4 − P3 gain (smallest q {fb.q.min():.2f}). "
                   f"AUC {min(auc.auc_P4.min(), auc.auc_P3.min()):.2f}–{max(auc.auc_P4.max(), auc.auc_P3.max()):.2f}."),
        "interpretation": ("With linear block-position drift removed, context is not decodable above the majority baseline; "
                           "a context effect that ramps linearly with block position would be removed with the drift."),
        "limitations": [
            "The sequenced blocks all precede the main-2 blocks, so the adjustment removes any context difference a linear trend explains.",
            "The VISal nominal P4 − P3 gain (p 0.047, q 0.28) depends on the seed: at seed 20261013 it is −0.015 (p 0.51).",
            "Session 1186358749 excluded (no main 2)."],
        "code": {"location": CODE_LOC, "commit": head},
        "receipts": [{"name": "results/s2v2/receipt.json", "sha256": sha(R / "s2v2" / "receipt.json")},
                     {"name": "results/s2v2/family_A.csv", "sha256": sha(R / "s2v2" / "family_A.csv")},
                     {"name": "results/s2v2/family_B.csv", "sha256": sha(R / "s2v2" / "family_B.csv")},
                     {"name": "PREREGISTRATION_S2_v2.md", "sha256": sha(REPO / "PREREGISTRATION_S2_v2.md")}],
        "origin": ORIGIN,
        "replications": [
            replication(REPO / "_verify_s2v2" / "_temp_report_tables_all.txt",
                        "decoding in all six areas; per-session scores, family means and p", "reproduces", "20261012",
                        "0 of 11 fields per area differ by more than 1e-6"),
            replication(REPO / "_verify_s2v2" / "_temp_report_tables_all.txt",
                        "the same decoding at a second seed, all six areas", "reproduces", "20261013",
                        "no cell reaches p < 0.13; the VISal gain is −0.015 (p 0.51) against +0.042 (p 0.047)")],
        "links": common["links"]})

    # LFP clock, the two independently reproduced probes.
    rows = []
    probe_assets = [json.loads(line) for line in open(REPO / "receipts" / "download_000253_probe_lfp.jsonl")]
    for ses in ("1232959154", "1203581890"):
        r = json.load(open(REPO / "receipts" / f"lfp_clock_sta_{ses}_probe-1.json"))
        v = r["versions"]["0.240923.1441"]
        if "same_asset_as" in v:
            v = r["versions"][v["same_asset_as"]]
        for w in ("early", "late"):
            win = v["windows"][w]
            rows.append({"area": f"{ses} {w}", "mean": win["median_offset_ms"],
                         "lo": win["range_offset_ms"][0], "hi": win["range_offset_ms"][1]})
    df = pd.DataFrame(rows)
    paths = {}
    for theme, t in THEMES.items():
        fig, ax = plt.subplots(figsize=(6.0, 3.0), dpi=150)
        fig.patch.set_facecolor(t["bg"])
        ax.errorbar(range(len(df)), df["mean"], yerr=[df["mean"] - df["lo"], df["hi"] - df["mean"]], fmt="o", ms=5,
                    color=t["series"][0], ecolor=t["series"][0], elinewidth=1.2)
        for y in (-0.8, 0.8):
            ax.axhline(y, color=t["muted"], lw=0.8, ls="--")
        ax.set_xticks(range(len(df)), df["area"], fontsize=8)
        ax.set_ylabel("LFP time − spike time, ms")
        ax.set_title("LFP clock offset, probe 1 (stored seconds); dashed: ±1 sample", fontsize=10, loc="left", color=t["text"])
        style(ax, t)
        fig.tight_layout()
        p = FIG / ("glo_lfp_clock.png" if theme == "light" else "glo_lfp_clock.dark.png")
        fig.savefig(p, facecolor=t["bg"])
        plt.close(fig)
        paths[theme] = p
    ogen = assets_used({"1232959154", "1203581890"})
    entries.append({
        "id": "glo_lfp_clock", "title": "LFP clock offset of two replaced-version probe files",
        "question": "Is the stored-seconds LFP time axis of 000253 0.240923.1441 aligned to the spike clock within one sample (0.8 ms)?",
        "relation_to_published": "Data check for a proposed LFP showcase; the paper reports no such check.",
        "species": "mouse", "status": "verified",
        "dandi": {"id": "000253", "version": "0.240923.1441",
                  "assets": [{"asset_id": a["asset_id"], "sha256": a["dandi_sha256"]} for a in probe_assets] + ogen},
        "jnwb": {"commit": json.load(open(REPO / "receipts" / "lfp_clock_sta_1232959154_probe-1.json"))["jnwb_commit"],
                 "functions": ["bandpass_filter"]},
        "figures": [{"light": rel(paths["light"]), "dark": rel(paths["dark"]),
                     "caption": "Median spike-triggered LFP trough lag over units, early and late 70-s windows; bars span the units' range.",
                     "units": "ms", "controls": "independent check recovers a 5.0 ms spike-time shift at 4.95–4.97 ms",
                     "uncertainty": "range across units (9–12 per window)"}],
        "result": (f"Probe 1 of 1232959154: {df['mean'][0]:.2f} ms early and {df['mean'][1]:.2f} ms late, constant over the "
                   "session (independent check −9.73 and −9.76 ms). Probe 1 of 1203581890: within 0.8 ms "
                   f"({df['mean'][2]:.2f} and {df['mean'][3]:.2f} ms; independent check +0.24 and +0.28 ms)."),
        "interpretation": "Stored seconds are within one sample in one probe and offset by a constant about 10 ms in the other, so each probe needs this check before band power.",
        "limitations": [
            "The delay from a spike to its LFP-band trough cannot be separated from the clock offset.",
            "17–21 % of units have a positive-dominant STA (independent check).",
            "Two probes reproduced; four others tested remotely remain unverified; the remote reads went beyond the Gate B authorisation.",
            "The 1203581890 probe file was not replaced between versions."],
        "code": {"location": CODE_LOC, "commit": head},
        "receipts": [{"name": f"receipts/lfp_clock_sta_{s}_probe-1.json", "sha256": sha(REPO / "receipts" / f"lfp_clock_sta_{s}_probe-1.json")}
                     for s in ("1232959154", "1203581890")]
                    + [{"name": "receipts/download_000253_probe_lfp.jsonl", "sha256": sha(REPO / "receipts" / "download_000253_probe_lfp.jsonl")}],
        "origin": ORIGIN,
        "replications": [replication(
            REPO / "_verify_clock" / "_temp_check.log", "both probes, early and late windows, from the downloaded files",
            "reproduces", None,
            "−9.73 and −9.76 ms in 1232959154; +0.24 and +0.28 ms in 1203581890; each within one sample (0.8 ms) of the showcase value")],
        "links": [{"label": "DANDI 000253 0.240923.1441",
                   "url": DANDI_URL.replace("0.240503.0152", "0.240923.1441")}]})

    json.dump({"entries": entries}, open(OUT / "openscope_glo.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    for e in entries:
        print(e["id"], e["status"], e["figures"][0]["light"], e["result"])


if __name__ == "__main__":
    main()
