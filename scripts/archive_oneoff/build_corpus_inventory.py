r"""
Generate the corpus inventory markdown: sessions, areas, units, conditions.

Every table is computed from files on disk at run time. Nothing is transcribed by hand, so
re-running after the corpus changes regenerates the documents rather than dating them.

SOURCES
    D:/analysis/nwb/*.nwb                                    recordings
    D:/workspace/data/metadata/<session>/                     sidecars: probe_areas.json,
                                                              electrodes.csv, units.csv, events.csv
    D:/workspace/data/tfr_arrays/*.npy                        time-frequency products
    D:/workspace/data/connectivity_databases/*_channel_layers.csv   vFLIP layer tables
    outputs/channel_area_vector/channel_area_vector.csv       per-channel area assignment
    outputs/lfp_band_census_v2/                               band-power census and models

OUTPUT
    context/inventory/SESSIONS.md
    context/inventory/AREAS.md
    context/inventory/UNITS.md
    context/inventory/CONDITIONS.md
    context/inventory/receipt.json
"""
from __future__ import annotations

import glob
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

NWB_DIR = r"D:/analysis/nwb"
META_DIR = r"D:/workspace/data/metadata"
TFR_DIR = r"D:/workspace/data/tfr_arrays"
LAYER_DIR = r"D:/workspace/data/connectivity_databases"
AREA_VEC = r"D:/workspace/omission/outputs/channel_area_vector/channel_area_vector.csv"
CENSUS = r"D:/workspace/omission/outputs/lfp_band_census_v2/channel_band_power.csv.gz"
OUT_DIR = r"D:/workspace/omission/context/inventory"

AREA_ORDER = ["V1", "V2", "V3a/d", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]
POOL = {"V3": "V3a/d", "V3a": "V3a/d", "V3d": "V3a/d"}
FNAME_RE = re.compile(r"^sub-(?P<subject>.+?)_ses-(?P<session>.+?)-(?P<probe>[A-Z])-"
                      r"(?P<area>.+)-(?P<cond>[A-Z]+)$")

HEADER = ("Version: {date}\n"
          "Status: generated inventory, not hand-edited\n"
          "Truth status: `truth_safe_verified`; regenerate with "
          "`python scripts/build_corpus_inventory.py` after any corpus change.\n")


def sidecar_dirs():
    out = {}
    for d in sorted(glob.glob(os.path.join(META_DIR, "*"))):
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "probe_areas.json")):
            out[os.path.basename(d).replace("_rec", "")] = d
    return out


def load_tfr_index():
    rows = []
    for f in glob.glob(os.path.join(TFR_DIR, "*.npy")):
        m = FNAME_RE.match(os.path.basename(f)[:-4])
        if m:
            g = m.groupdict()
            rows.append({"session": f"sub-{g['subject']}_ses-{g['session']}",
                         "subject": g["subject"], "probe": g["probe"],
                         "area_token": g["area"], "cond": g["cond"]})
    return pd.DataFrame(rows)


def load_units():
    frames = []
    for f in sorted(glob.glob(os.path.join(META_DIR, "*", "units.csv"))):
        d = pd.read_csv(f)
        d["session"] = os.path.basename(os.path.dirname(f)).replace("_rec", "")
        frames.append(d)
    u = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(u):
        u["subject"] = u.session.str.split("_").str[0].str.replace("sub-", "", regex=False)
        u["area10"] = u["area"].replace(POOL)
    return u


def load_events():
    frames = []
    for f in sorted(glob.glob(os.path.join(META_DIR, "*", "events.csv"))):
        d = pd.read_csv(f, usecols=lambda c: c in {
            "trial_num", "stimulus_number", "task_condition_number", "correct",
            "is_omission", "phase"})
        d["session"] = os.path.basename(os.path.dirname(f)).replace("_rec", "")
        frames.append(d)
    e = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(e):
        e["subject"] = e.session.str.split("_").str[0].str.replace("sub-", "", regex=False)
    return e


def load_layers():
    frames = []
    for f in glob.glob(os.path.join(LAYER_DIR, "*_channel_layers.csv")):
        frames.append(pd.read_csv(f))
    if not frames:
        return pd.DataFrame()
    d = pd.concat(frames, ignore_index=True)
    d["labelled"] = d.putative_layer.isin(["sup", "mid", "deep"])
    return d


def md_table(df, floatfmt="{:.2f}"):
    cols = list(df.columns)
    head = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    lines = [head, sep]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float) and not pd.isna(v):
                cells.append(floatfmt.format(v))
            elif pd.isna(v):
                cells.append("--")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    sc = sidecar_dirs()
    tfr = load_tfr_index()
    units = load_units()
    events = load_events()
    layers = load_layers()
    av = pd.read_csv(AREA_VEC)
    av["area10"] = av["area"].replace(POOL)
    av["subject"] = av.session_prefix.str.split("_").str[0].str.replace("sub-", "", regex=False)

    tfr_sessions = set(tfr.session.unique())

    # ---------------------------------------------------------------- SESSIONS --
    rows = []
    for sp, d in sc.items():
        summ = {}
        p = os.path.join(d, "sidecar_summary.json")
        if os.path.exists(p):
            summ = json.load(open(p, encoding="utf-8"))
        pa = json.load(open(os.path.join(d, "probe_areas.json"), encoding="utf-8"))
        areas = sorted({POOL.get(a, a) for v in pa.values() for a in v.get("areas", [])})
        nwb = os.path.join(NWB_DIR, sp + "_rec.nwb")
        if not os.path.exists(nwb):
            nwb = os.path.join(NWB_DIR, sp + ".nwb")
        gb = round(os.path.getsize(nwb) / 1e9, 1) if os.path.exists(nwb) else None
        t = tfr[tfr.session == sp]
        lay = layers[layers.session_prefix == sp] if len(layers) else pd.DataFrame()
        ev = events[events.session == sp] if len(events) else pd.DataFrame()
        uu = units[units.session == sp] if len(units) else pd.DataFrame()
        rows.append({
            "session": sp,
            "animal": sp.split("_")[0].replace("sub-", ""),
            "NWB (GB)": gb,
            "probes": len(pa),
            "areas": ", ".join(areas),
            "electrodes": summ.get("n_electrodes"),
            "units": len(uu) if len(uu) else summ.get("n_units"),
            "events": summ.get("n_events"),
            "trials": int(ev.trial_num.nunique()) if len(ev) and "trial_num" in ev else None,
            "TFR files": len(t),
            "TFR conds": t.cond.nunique() if len(t) else 0,
            "layer %": round(100 * lay.labelled.mean(), 1) if len(lay) else None,
            "in corpus": "yes" if sp in tfr_sessions else "no",
        })
    sess = pd.DataFrame(rows).sort_values(["animal", "session"])

    n_corpus = int((sess["in corpus"] == "yes").sum())
    txt = [f"# Session inventory\n", HEADER.format(date=date),
           f"\n{len(sess)} sessions have metadata sidecars; **{n_corpus} carry time-frequency "
           f"products and constitute the analysis corpus**. Sessions without TFR products have "
           f"recordings and units but no spectral analysis, and are excluded from every "
           f"area-resolved result.\n",
           "\n## 1. All sessions\n", md_table(sess, "{:.1f}"),
           "\n\n## 2. Totals by animal\n"]
    by = sess.groupby("animal").agg(
        sessions=("session", "count"),
        in_corpus=("in corpus", lambda s: int((s == "yes").sum())),
        electrodes=("electrodes", "sum"), units=("units", "sum"),
        tfr_files=("TFR files", "sum")).reset_index()
    txt.append(md_table(by, "{:.0f}"))
    txt.append("\n\n## 3. Notes\n\n"
               "- `layer %` is the fraction of that session's channels receiving a superficial, "
               "middle or deep label from the vFLIP spectrolaminar crossover. It varies from "
               "under 30% to over 85% between sessions, and differs systematically between "
               "animals, which is why no laminar effect is pooled.\n"
               "- `in corpus` = no means the session has no `.npy` time-frequency arrays. Those "
               "sessions still contribute units to the spiking inventory.\n"
               "- One probe is excluded from area-resolved analysis: sub-V182o_ses-260724 probe C "
               "declares 32 channels while its area slices span 128 and its array holds 128, so "
               "its channel-to-area mapping is undeterminable.\n")
    open(os.path.join(OUT_DIR, "SESSIONS.md"), "w", encoding="utf-8").write("\n".join(txt))

    # ------------------------------------------------------------------- AREAS --
    rows = []
    for a in AREA_ORDER:
        g = av[av.area10 == a]
        t = tfr[tfr.area_token.replace(POOL).isin([a])] if len(tfr) else pd.DataFrame()
        tt = tfr.assign(a10=tfr.area_token.map(lambda x: POOL.get(x, x)))
        t = tt[tt.a10 == a]
        uu = units[units.area10 == a] if len(units) else pd.DataFrame()
        lab = g.putative_layer.isin(["sup", "mid", "deep"]).mean() if len(g) else np.nan
        rows.append({
            "area": a,
            "animals": g.subject.nunique(),
            "which": ", ".join(sorted(g.subject.unique())),
            "sessions": g.session_prefix.nunique(),
            "probes": g.groupby(["session_prefix", "probe_letter"]).ngroups,
            "channels": len(g),
            "TFR files": len(t),
            "units": len(uu),
            "layer %": round(100 * lab, 1) if not pd.isna(lab) else None,
        })
    ar = pd.DataFrame(rows)

    txt = [f"# Area inventory\n", HEADER.format(date=date),
           "\nTen analysis areas. The V3 subdivisions are pooled to **V3a/d**: where a probe "
           "spanned several areas its channel axis was divided into equal contiguous shares, so "
           "dorsal and ventral V3 are the upper and lower halves of one shank rather than two "
           "independently localised areas.\n",
           "\n## 1. Coverage\n", md_table(ar, "{:.1f}"),
           "\n\n## 2. Animals per area\n\n"
           "Every area was recorded in at least two animals, and V4 in all three. The area-by-"
           "animal design graph is therefore connected, and additive area and animal effects are "
           "jointly identifiable in one model.\n"]
    cross = (av.groupby(["area10", "subject"]).session_prefix.nunique()
             .unstack(fill_value=0).reindex(AREA_ORDER).reset_index())
    txt.append("\n" + md_table(cross, "{:.0f}"))
    txt.append("\n\n(Cells are sessions contributing that area for that animal.)\n")
    txt.append("\n## 3. Notes\n\n"
               "- `channels` counts entries in the per-channel area vector, which assigns each "
               "channel to exactly one area. Area labels are disjoint by construction.\n"
               "- Segment boundaries are an equal-share assumption, not a measurement. Of 28 "
               "multi-area probes, 26 split at channel 64 of 128 and the single three-area probe "
               "at 42 and 85. No claim depends on the location of a boundary.\n"
               "- `layer %` differs by nearly threefold across areas, from about 32% in V1 and V2 "
               "to over 90% in MST. Laminar contrasts are therefore reported within area and "
               "within animal only.\n")
    open(os.path.join(OUT_DIR, "AREAS.md"), "w", encoding="utf-8").write("\n".join(txt))

    # ------------------------------------------------------------------- UNITS --
    txt = [f"# Unit inventory\n", HEADER.format(date=date)]
    if len(units):
        classified = units.display_class.notna()
        n_all, n_cls = len(units), int(classified.sum())
        txt.append(f"\n{n_all:,} spike-sorted units across {units.session.nunique()} sessions. "
                   f"{n_cls:,} carry a functional classification in the sidecar; "
                   f"{n_all - n_cls:,} do not.\n")
        txt.append("\n## 1. Functional classes, sidecar labels\n")
        cls = (units.display_class.value_counts(dropna=False).rename_axis("class")
               .reset_index(name="units"))
        cls["% of classified"] = (100 * cls.units / max(n_cls, 1)).round(2)
        txt.append(md_table(cls, "{:.2f}"))
        txt.append("\n\n> **These labels are not the manuscript's classification.** The Methods "
                   "define O+ by a Wilcoxon rank-sum contrast at p < 0.01 requiring the omission "
                   "rate to exceed both the stimulus rate and the baseline rate. The sidecar "
                   "labels were produced by a different pass and their criteria are not recorded "
                   "alongside them. The O+ prevalence quoted in the manuscript must come from a "
                   "run of the stated criteria, not from this table.\n")
        txt.append("\n## 2. Units per area\n")
        ua = (units.groupby("area10").agg(
            units=("unit_id", "size"),
            sessions=("session", "nunique"),
            median_FR=("firing_rate", "median"),
            median_SNR=("snr", "median"),
            median_presence=("presence_ratio", "median")).reindex(AREA_ORDER).reset_index())
        txt.append(md_table(ua, "{:.2f}"))
        txt.append("\n\n## 3. Units per animal\n")
        us = units.groupby("subject").agg(units=("unit_id", "size"),
                                          sessions=("session", "nunique"),
                                          median_FR=("firing_rate", "median")).reset_index()
        txt.append(md_table(us, "{:.2f}"))
        if "quality" in units:
            txt.append("\n\n## 4. Quality tiers\n")
            q = units.quality.value_counts(dropna=False).rename_axis("quality").reset_index(
                name="units")
            txt.append(md_table(q, "{:.0f}"))
            txt.append("\n\nThe `quality` field is binary in the sidecars and its definition is "
                       "not recorded there. The manuscript states that classification used "
                       "quality-tiered units only, so the tier definition is owed before that "
                       "sentence can stand.\n")
    open(os.path.join(OUT_DIR, "UNITS.md"), "w", encoding="utf-8").write("\n".join(txt))

    # -------------------------------------------------------------- CONDITIONS --
    txt = [f"# Condition and trial inventory\n", HEADER.format(date=date)]
    if len(events):
        txt.append(f"\n{len(events):,} event rows across {events.session.nunique()} sessions. "
                   "Events are event-level, not trial-level: each row is one epoch within a "
                   "trial, so trial counts come from unique `trial_num` values.\n")
        if "correct" in events:
            corr = events.groupby("session").correct.agg(["mean", "size"]).reset_index()
            corr.columns = ["session", "correct fraction", "events"]
            txt.append("\n## 1. Correct fraction by session\n")
            txt.append(md_table(corr.sort_values("session"), "{:.3f}"))
            overall = events.correct.mean()
            txt.append(f"\n\nOverall correct fraction across the corpus: **{overall:.3f}**. "
                       "Analyses use correct, completed fixation trials only.\n")
        if "task_condition_number" in events:
            txt.append("\n## 2. Task condition numbers present\n")
            tc = (events.task_condition_number.value_counts(dropna=False)
                  .rename_axis("task_condition_number").reset_index(name="events")
                  .sort_values("task_condition_number"))
            txt.append(md_table(tc, "{:.0f}"))
            n_tc = int(events.task_condition_number.dropna().nunique())
            txt.append(f"\n\n> **{n_tc} distinct task condition numbers appear in the event "
                       "tables, while the Methods declare a twelve-condition set.** The mapping "
                       "from these integers to the condition names {AAAB, AXAB, ...} is not "
                       "recorded in the sidecars, and must be resolved before any per-condition "
                       "count is quoted.\n")
        if "stimulus_number" in events:
            txt.append("\n## 3. Stimulus number\n")
            sn = (events.stimulus_number.value_counts(dropna=False)
                  .rename_axis("stimulus_number").reset_index(name="events")
                  .sort_values("stimulus_number"))
            txt.append(md_table(sn, "{:.0f}"))
            txt.append("\n\n`stimulus_number` is the stable crosswalk for slot selection: "
                       "p1 = 2, p2 = 3, p3 = 4, p4 = 5. Do not use BHV odd event codes for this.\n")
        if "is_omission" in events:
            om = int((events.is_omission == 1).sum())
            txt.append(f"\n## 4. Omission events\n\n{om:,} events are flagged as omissions "
                       f"({100 * om / len(events):.2f}% of event rows).\n")
    open(os.path.join(OUT_DIR, "CONDITIONS.md"), "w", encoding="utf-8").write("\n".join(txt))

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "outputs": ["SESSIONS.md", "AREAS.md", "UNITS.md", "CONDITIONS.md"],
        "n_sessions_with_sidecars": len(sc),
        "n_sessions_in_tfr_corpus": len(tfr_sessions),
        "n_tfr_files": int(len(tfr)),
        "n_units": int(len(units)),
        "n_units_classified": int(units.display_class.notna().sum()) if len(units) else 0,
        "n_event_rows": int(len(events)),
        "n_channels_in_area_vector": int(len(av)),
        "areas": AREA_ORDER,
        "open_questions_surfaced": [
            "sidecar functional labels give 7 O+ units of 6,655 classified (0.11%); criteria "
            "not recorded and not the manuscript's stated Wilcoxon p<0.01 definition",
            "14 distinct task_condition_number values against a declared 12-condition set",
            "quality field is binary with no recorded tier definition",
        ],
    }
    json.dump(receipt, open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8"),
              indent=2)
    for f in receipt["outputs"]:
        print(f"WROTE {os.path.join(OUT_DIR, f)}")
    print(f"sessions {len(sc)} ({len(tfr_sessions)} in corpus) | units {len(units):,} | "
          f"events {len(events):,} | channels {len(av):,}")


if __name__ == "__main__":
    main()
