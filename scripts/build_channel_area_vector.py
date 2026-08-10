r"""
Step 3a -- consolidated per-channel area vector for the TFR corpus, with a partition audit.

WHY THIS EXISTS
    scripts/archive_oneoff/precompute_tfr_arrays.py writes, for a probe spanning k areas,
    k FILES THAT ARE THE SAME 128-CHANNEL ARRAY under k different area tokens:

        "Build full-probe TFR once per condition, then save per area label
         (same array; naming uses each area token ...)"

    Any analysis that groups those files by their filename area token is therefore
    comparing a probe against itself. See artifacts/.lab/tfr_area_label_aliasing_blocker_20260728.

THE FIX (specified in context/drafts/04_draft_biorxiv_markdown.md Methods)
    "When a probe was assigned to multiple areas, its ordered channel axis was partitioned
     into contiguous segments corresponding to those listed areas."

    That partition already exists in the sidecars as probe_areas.json -> channel_slices,
    and is already materialized per channel in electrodes.csv (columns area, area_slot).
    This script consolidates it across the corpus, verifies the two agree, and -- the part
    that matters for the manuscript -- AUDITS HOW THE BOUNDARIES WERE SET.

OUTPUTS
    outputs/channel_area_vector/channel_area_vector.csv    one row per (session, probe, channel)
    outputs/channel_area_vector/receipt.json               provenance, counts, partition audit
"""
from __future__ import annotations

import glob
import json
import os
import platform
import re
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from jnwb import paths as _P

META_DIR = _P.meta_dir()
TFR_DIR = _P.tfr_dir()
LAYER_DIR = str(_P.conndb_dir())
OUT_DIR = _P.REPO_ROOT / "outputs/channel_area_vector"

FNAME_RE = re.compile(r"^sub-(?P<subject>.+?)_ses-(?P<session>.+?)-(?P<probe>[A-Z])-"
                      r"(?P<area>.+)-(?P<cond>[A-Z]+)$")
PROBE_LETTER = {"probe_0_lfp": "A", "probe_1_lfp": "B", "probe_2_lfp": "C", "probe_3_lfp": "D"}


def tfr_corpus_index() -> pd.DataFrame:
    """(session_prefix, probe_letter, area_token) actually present in the TFR corpus."""
    rows = []
    for f in glob.glob(os.path.join(TFR_DIR, "*.npy")):
        m = FNAME_RE.match(os.path.basename(f)[:-4])
        if m:
            g = m.groupdict()
            rows.append({"session_prefix": f"sub-{g['subject']}_ses-{g['session']}",
                         "probe_letter": g["probe"], "area_token": g["area"]})
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def sidecar_dir_for(session_prefix: str) -> str | None:
    for cand in (f"{session_prefix}_rec", session_prefix):
        p = os.path.join(META_DIR, cand)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "probe_areas.json")):
            return p
    return None


def load_layers() -> pd.DataFrame:
    """vFLIP putative layers, if scripts/archive_oneoff/build_channel_layer_mapping.py has run."""
    frames = []
    for f in glob.glob(os.path.join(LAYER_DIR, "*_channel_layers.csv")):
        d = pd.read_csv(f)
        d["probe_letter"] = d["lfp_key"].map(PROBE_LETTER)
        frames.append(d[["session_prefix", "probe_letter", "channel_idx", "putative_layer",
                         "crossover_channel", "fit_omega"]])
    if not frames:
        return pd.DataFrame(columns=["session_prefix", "probe_letter", "channel_idx",
                                     "putative_layer", "crossover_channel", "fit_omega"])
    return pd.concat(frames, ignore_index=True)


def main() -> pd.DataFrame:
    os.makedirs(OUT_DIR, exist_ok=True)
    corpus = tfr_corpus_index()
    sessions = sorted(corpus["session_prefix"].unique())

    rows, audit, missing = [], [], []
    for sp in sessions:
        sdir = sidecar_dir_for(sp)
        if sdir is None:
            missing.append({"session_prefix": sp, "reason": "no probe_areas.json sidecar"})
            continue
        pa = json.load(open(os.path.join(sdir, "probe_areas.json"), encoding="utf-8"))
        elec_path = os.path.join(sdir, "electrodes.csv")
        elec = pd.read_csv(elec_path) if os.path.exists(elec_path) else None

        for pname, info in pa.items():
            letter = PROBE_LETTER.get(info.get("lfp_key"), pname[-1])
            n_ch = int(info.get("n_channels", 128))
            slices = info.get("channel_slices", {})
            areas = list(info.get("areas", []))

            # --- partition audit -------------------------------------------------
            bounds = sorted((v["start"], v["stop"], a) for a, v in slices.items())
            covers = (len(bounds) > 0 and bounds[0][0] == 0 and bounds[-1][1] == n_ch
                      and all(bounds[i][1] == bounds[i + 1][0] for i in range(len(bounds) - 1)))
            widths = [b[1] - b[0] for b in bounds]
            equal = np.array_split(np.arange(n_ch), len(bounds)) if bounds else []
            is_equal_split = bool(bounds) and widths == [len(e) for e in equal]
            audit.append({
                "session_prefix": sp, "probe_letter": letter,
                "location_raw": info.get("location_raw"), "n_areas": len(bounds),
                "n_channels": n_ch, "contiguous_and_complete": covers,
                "segment_widths": widths, "equals_uniform_split": is_equal_split,
                "boundaries": [b[1] for b in bounds[:-1]],
            })

            # A probe whose declared channel count disagrees with the span its own area
            # slices cover has no determinable channel-to-area mapping: the slices were laid
            # out against a different channel count than the one recorded. Silently capping
            # them would assign channels to an area on the strength of two contradictory
            # statements. Such probes are excluded from the area vector and reported.
            slice_max = max((int(s["stop"]) for s in slices.values()), default=0)
            if slices and slice_max != n_ch:
                missing.append({"session_prefix": sp, "probe": letter,
                                "reason": f"channel-count conflict: n_channels={n_ch} but area "
                                          f"slices span {slice_max}; mapping undeterminable, "
                                          f"probe excluded"})
                continue

            for a, sl in slices.items():
                for ch in range(int(sl["start"]), min(int(sl["stop"]), n_ch)):
                    rows.append({"session_prefix": sp, "probe_letter": letter,
                                 "channel": ch, "area": a,
                                 "seg_start": int(sl["start"]), "seg_stop": int(sl["stop"]),
                                 "seg_width": int(sl["stop"]) - int(sl["start"]),
                                 "n_areas_on_probe": len(slices),
                                 "location_raw": info.get("location_raw")})

            # --- cross-check against electrodes.csv ------------------------------
            if elec is not None and "probe" in elec.columns:
                sub = elec[elec["probe"] == pname]
                for a, sl in slices.items():
                    seg = sub[(sub["local_idx"] >= sl["start"]) & (sub["local_idx"] < sl["stop"])]
                    bad = int((seg["area"] != a).sum())
                    if bad:
                        missing.append({"session_prefix": sp, "probe": letter, "area": a,
                                        "reason": f"{bad} electrodes.csv rows disagree with slice"})

    df = pd.DataFrame(rows).sort_values(["session_prefix", "probe_letter", "channel"])
    layers = load_layers()
    df = df.merge(layers.rename(columns={"channel_idx": "channel"}),
                  on=["session_prefix", "probe_letter", "channel"], how="left")

    # every (session, probe, area) token in the TFR corpus must resolve to >=1 channel
    have = set(map(tuple, df[["session_prefix", "probe_letter", "area"]].drop_duplicates().values))
    want = set(map(tuple, corpus[["session_prefix", "probe_letter", "area_token"]].values))
    unresolved = sorted(want - have)

    aud = pd.DataFrame(audit)
    out_csv = os.path.join(OUT_DIR, "channel_area_vector.csv")
    df.to_csv(out_csv, index=False)
    aud.to_csv(os.path.join(OUT_DIR, "partition_audit.csv"), index=False)

    n_multi = int((aud["n_areas"] > 1).sum())
    n_multi_uniform = int(((aud["n_areas"] > 1) & aud["equals_uniform_split"]).sum())
    # Two different things, previously conflated. vFLIP writes the literal string "na" for a
    # channel it processed but could not assign, so notna() counts those as covered and
    # measures only "this session has a layer table". The number that matters for any laminar
    # claim is the fraction carrying a real label.
    layer_rows = float(df["putative_layer"].notna().mean()) if len(df) else 0.0
    layer_cov = (float(df["putative_layer"].isin(["sup", "mid", "deep"]).mean())
                 if len(df) else 0.0)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Consolidated per-channel area vector for the TFR corpus; resolves the "
                   "filename-token aliasing recorded in "
                   "artifacts/.lab/tfr_area_label_aliasing_blocker_20260728.json",
        "sources": {
            "partition": f"{META_DIR}/<session>/probe_areas.json -> channel_slices",
            "per_channel_crosscheck": f"{META_DIR}/<session>/electrodes.csv (area, area_slot)",
            "layers": f"{LAYER_DIR}/<session>_channel_layers.csv (vFLIP2 spectrolaminar crossover)",
            "corpus": TFR_DIR,
        },
        "n_sessions_in_tfr_corpus": len(sessions),
        "n_sessions_resolved": int(df["session_prefix"].nunique()),
        "n_probes": int(aud.shape[0]),
        "n_channels": int(len(df)),
        "n_multi_area_probes": n_multi,
        "areas": sorted(df["area"].unique().tolist()),
        "channels_per_area": {k: int(v) for k, v in
                              sorted(Counter(df["area"]).items())},
        "unresolved_area_tokens": [list(u) for u in unresolved],
        "electrodes_crosscheck_disagreements": [m for m in missing if "electrodes" in m["reason"]],
        "sessions_without_sidecar": [m for m in missing if "sidecar" in m["reason"]],
        "probes_excluded_channel_conflict": [m for m in missing if "channel-count" in m["reason"]],
        "PARTITION_AUDIT": {
            "all_partitions_contiguous_and_complete": bool(aud["contiguous_and_complete"].all()),
            "n_multi_area_probes": n_multi,
            "n_multi_area_probes_equal_to_uniform_split": n_multi_uniform,
            "CAVEAT": (
                "The channel->area boundaries in probe_areas.json are NOT anatomically "
                "measured. Where every multi-area probe's boundaries coincide exactly with a "
                "uniform division of the 128-channel axis, the partition is an ASSUMPTION "
                "(equal share per listed area, in listing order), not a measurement. It "
                "removes the aliasing -- segments no longer overlap -- but it does not "
                "establish that a given channel is in the area its label names. Any "
                "area-resolved claim in the manuscript inherits this assumption and must "
                "say so."
            ),
        },
        "layer_source": "vFLIP2 crossover of the alpha/beta-to-gamma transition, fitted per "
                        "area segment on the first 300 s of raw LFP (Welch PSD, nperseg=1024)",
        "layer_rows_present_fraction": round(layer_rows, 4),
        "layer_labelled_fraction": round(layer_cov, 4),
        "layer_coverage_note": "rows_present counts channels whose session has a vFLIP table, "
                               "including those vFLIP marked 'na'; labelled counts only "
                               "sup/mid/deep. Only the second is usable for a laminar claim, "
                               "and it is unbalanced across animals "
                               "(artifacts/.lab/vflip_coverage_imbalance_20260728.json).",
        "layer_label_counts": {str(k): int(v) for k, v in
                               Counter(df["putative_layer"].dropna()).items()},
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "platform": platform.platform()},
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)

    print(f"WROTE {out_csv}  ({len(df):,} channels, {df['session_prefix'].nunique()} sessions)")
    print(f"multi-area probes: {n_multi}; identical to a uniform split: {n_multi_uniform}")
    print(f"unresolved area tokens: {len(unresolved)}")
    print(f"layer rows present: {layer_rows:.1%}  |  real sup/mid/deep labels: {layer_cov:.1%}")
    return df


if __name__ == "__main__":
    main()
