r"""
Export putative laminar assignment per probe, and attach it to units.

CHANNEL LAYER
    vFLIP2 estimates the spectrolaminar alpha/beta-to-gamma crossover per area segment from
    the Welch PSD of each probe's raw LFP, and labels channels superficial, middle or deep
    relative to it. Segments where the crossover does not converge are left 'na' rather than
    filled in.

UNIT LAYER
    A unit's putative layer is the layer of its peak channel (Hamm, 2026-07-28). The join key
    is (session, probe, local channel index) -- the peak channel expressed in probe-local
    coordinates, not the global electrode id.

COVERAGE IS NOT BALANCED, AND THAT CONSTRAINS USE
    53.9 per cent of channels carry a label, but the rate differs by animal
    (Kruskal-Wallis on per-session coverage H = 12.80, P = 0.0017) and about threefold by
    area. Laminar contrasts are therefore interpretable within an animal and an area, and a
    pooled laminar coefficient is not: it would carry the animal and area differences inside
    it. Each output table reports its own coverage so this cannot be lost downstream.

OUTPUT
    outputs/layers/per_probe/<session>_<probe>.csv     one file per probe of each NWB
    outputs/layers/channel_layers_all.csv              every channel, all sessions
    outputs/layers/unit_layers.csv                     every unit with its peak-channel layer
    outputs/layers/layer_coverage_summary.csv          coverage by session, probe, area, animal
    outputs/layers/receipt.json
"""
from __future__ import annotations

import glob
import json
import os
import platform
from datetime import datetime, timezone

import numpy as np
import pandas as pd

LAYER_DIR = r"D:/workspace/data/connectivity_databases"
META_DIR = r"D:/workspace/data/metadata"
OUT_DIR = r"D:/workspace/omission/outputs/layers"
PROBE_LETTER = {"probe_0_lfp": "A", "probe_1_lfp": "B", "probe_2_lfp": "C", "probe_3_lfp": "D"}
POOL = {"V3": "V3a/d", "V3a": "V3a/d", "V3d": "V3a/d"}
REAL = ("sup", "mid", "deep")


def main():
    os.makedirs(os.path.join(OUT_DIR, "per_probe"), exist_ok=True)

    frames = []
    for f in sorted(glob.glob(os.path.join(LAYER_DIR, "*_channel_layers.csv"))):
        d = pd.read_csv(f)
        d["probe"] = d["lfp_key"].map(PROBE_LETTER)
        frames.append(d)
    if not frames:
        raise SystemExit("no *_channel_layers.csv found -- run build_channel_layer_mapping.py")
    ch = pd.concat(frames, ignore_index=True)
    ch["animal"] = ch.session_prefix.str.split("_").str[0].str.replace("sub-", "", regex=False)
    ch["area10"] = ch["area"].replace(POOL)
    ch["labelled"] = ch.putative_layer.isin(REAL)

    # ---- one CSV per probe of each NWB ------------------------------------------
    written = []
    for (sp, pr), g in ch.groupby(["session_prefix", "probe"]):
        cols = ["session_prefix", "probe", "lfp_key", "channel_idx", "area", "area10",
                "putative_layer", "crossover_channel", "fit_omega", "labelled"]
        out = os.path.join(OUT_DIR, "per_probe", f"{sp}_{pr}.csv")
        g[cols].sort_values("channel_idx").to_csv(out, index=False)
        written.append(os.path.basename(out))
    ch.to_csv(os.path.join(OUT_DIR, "channel_layers_all.csv"), index=False)

    # ---- units: layer of the peak channel ---------------------------------------
    ufr = []
    for f in sorted(glob.glob(os.path.join(META_DIR, "*", "units.csv"))):
        d = pd.read_csv(f)
        d["session_prefix"] = os.path.basename(os.path.dirname(f)).replace("_rec", "")
        ufr.append(d)
    units = pd.concat(ufr, ignore_index=True) if ufr else pd.DataFrame()

    unit_out = pd.DataFrame()
    if len(units):
        units["probe"] = units["probe_id"].astype(str).str.strip().str[-1]
        # local_channel is the probe-local index the layer tables are keyed on
        key = "local_channel" if "local_channel" in units else "peak_channel_id"
        units["_ch"] = pd.to_numeric(units[key], errors="coerce")
        lay = ch[["session_prefix", "probe", "channel_idx", "putative_layer",
                  "crossover_channel", "area10"]].rename(
            columns={"channel_idx": "_ch", "putative_layer": "unit_layer",
                     "area10": "channel_area10"})
        unit_out = units.merge(lay, on=["session_prefix", "probe", "_ch"], how="left")
        unit_out["unit_layer_labelled"] = unit_out.unit_layer.isin(REAL)
        unit_out["area10"] = unit_out["area"].replace(POOL)
        unit_out["animal"] = unit_out.session_prefix.str.split("_").str[0].str.replace(
            "sub-", "", regex=False)
        # waveform duration is the fast/slow-spiking axis; keep it beside the layer
        unit_out.drop(columns=["_ch"]).to_csv(
            os.path.join(OUT_DIR, "unit_layers.csv"), index=False)

    # ---- coverage summaries ------------------------------------------------------
    cov = []
    for keys, name in [(["animal"], "animal"), (["session_prefix"], "session"),
                       (["area10"], "area"), (["session_prefix", "probe"], "probe")]:
        g = ch.groupby(keys).agg(channels=("labelled", "size"),
                                 labelled=("labelled", "sum")).reset_index()
        g["coverage_%"] = (100 * g.labelled / g.channels).round(2)
        g["level"] = name
        cov.append(g)
    cover = pd.concat(cov, ignore_index=True)
    cover.to_csv(os.path.join(OUT_DIR, "layer_coverage_summary.csv"), index=False)

    lab = ch[ch.labelled]
    comp = (pd.crosstab(lab.animal, lab.putative_layer, normalize="index") * 100).round(1)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "method": "vFLIP2 spectrolaminar crossover, per area segment, Welch PSD of the first "
                  "300 s of raw LFP, nperseg=1024",
        "unit_layer_rule": "a unit's putative layer is the layer of its peak channel, joined "
                           "on (session, probe, probe-local channel index)",
        "n_sessions": int(ch.session_prefix.nunique()),
        "n_probes": int(ch.groupby(['session_prefix', 'probe']).ngroups),
        "n_channels": int(len(ch)),
        "n_channels_labelled": int(ch.labelled.sum()),
        "coverage_fraction": round(float(ch.labelled.mean()), 4),
        "coverage_by_animal": {k: round(v, 4) for k, v in
                               ch.groupby("animal").labelled.mean().items()},
        "coverage_by_area": {k: round(v, 4) for k, v in
                             ch.groupby("area10").labelled.mean().items()},
        "layer_composition_among_labelled_pct_by_animal": comp.to_dict(),
        "n_units": int(len(unit_out)),
        "n_units_with_layer": int(unit_out.unit_layer_labelled.sum()) if len(unit_out) else 0,
        "unit_layer_coverage_fraction": (round(float(unit_out.unit_layer_labelled.mean()), 4)
                                         if len(unit_out) else 0.0),
        "per_probe_files": len(written),
        "CAVEAT": "Coverage is unbalanced across animals (H = 12.80, P = 0.0017) and varies "
                  "about threefold across areas. Laminar contrasts must be computed within "
                  "animal and within area; a pooled laminar coefficient would carry those "
                  "differences inside it.",
        "env": {"python": platform.python_version(), "pandas": pd.__version__,
                "numpy": np.__version__},
    }
    json.dump(receipt, open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8"),
              indent=2)

    print(f"per-probe CSVs: {len(written)} in {OUT_DIR}/per_probe/")
    print(f"channels {len(ch):,}  labelled {int(ch.labelled.sum()):,} "
          f"({100*ch.labelled.mean():.1f}%)  across {ch.session_prefix.nunique()} sessions")
    if len(unit_out):
        print(f"units {len(unit_out):,}  with a peak-channel layer "
              f"{int(unit_out.unit_layer_labelled.sum()):,} "
              f"({100*unit_out.unit_layer_labelled.mean():.1f}%)")
        print(unit_out[unit_out.unit_layer_labelled].groupby(
            ["area10", "unit_layer"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
