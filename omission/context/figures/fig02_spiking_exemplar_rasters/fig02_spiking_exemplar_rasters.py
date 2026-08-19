r"""
Figure 2: 4x4 raster grid -- one named area per response type, across the R-family conditions.

WHY THIS FIGURE EXISTS IN THIS FORM
    The asset previously staged as figure 2 has no generating code anywhere in this
    repository (see this directory's git history). This script reproduces a fixed reference
    layout with real spikes.

      Columns   S+ from V1, S- from V3a/d, O+ from V4, O++ from FEF -- one exemplar unit per
                (response type, area) pair, both fixed by the caption, not chosen from
                whichever area happens to have the strongest unit. If the named area has no
                qualifying unit, that column is a hard error, not a silent fallback.
      Rows      the four R-family conditions -- RRRR (no omission), RXRR, RRXR, RRRX (omission
                at slot 2, 3, 4). R is the maximum-entropy family: the omitted identity is
                equally likely A or B by design, so these rows are not confounded by a unit
                simply preferring one stimulus identity.
      Each cell a raster only (trials 0-40), sharing an x-axis in ms from p1 onset (t = 0).
                16 panels total, 4x4 -- no rate-trace row; that summary lives in fig03's
                population-level trace panels instead of being repeated per exemplar here.

    S+/S- come from outputs/classification/grand_s_and_o_units.csv (r_Splus/r_Sminus against
    the standard-sequence rate, is_Splus/is_Sminus flags) -- a legacy classifier, run before
    the Q1 peak/trough conjunction now used for the O+/O-/O++/O-- classes reported everywhere
    else in this figure set (fig03, fig05). O+/O++ here are Q1-conjunction exemplars from the
    current grand table, for consistency with those figures; S+/S- retain their legacy
    definition because no corrected replacement exists yet. This is stated so the two
    vocabularies are never silently treated as the same test.

EPOCH COLOUR CODING
    Each of the four presentation slots gets its own colour in sequence -- p1 yellow, p2
    pink, p3 green, p4 blue -- rather than one colour for "a real stimulus". Delays are left
    unshaded. The omitted slot is not colour-shaded; it is marked with a vertical dashed red
    line labelled "Omit", because in an omission trial that slot is visually identical to a
    delay and shading it the same as a real presentation would misrepresent the display.

OUTPUT
    svg/fig02_grid.{svg,png}     -- the 4x4 raster grid
    fig02.svg                   -- the assembled main figure (same panel)
    svg/fig02_receipt.json
    svg/fig02_stats.md, .csv    -- see the note inside: no test is fitted here by design
"""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, r"D:/workspace/omission")
from figstyle import (AREA_POOL, EPOCH_ONSETS_MS, FULL_TRIAL_WIN, full_trial_ticks,
                      mark_full_trial_axis, save)
from svgassemble import assemble
from figstats import write

import omission as oa
from omission.jnwb_ext.unit_classification import precompute_condition_onsets

GRAND_TABLE = r"D:/workspace/omission/outputs/classification/omission_grand_units.csv"
LEGACY_TABLE = r"D:/workspace/omission/outputs/classification/grand_s_and_o_units.csv"
NWB_DIR = r"D:/analysis/nwb"
FIG_DIR = os.path.join(HERE, "svg")

CONDS = ["RRRR", "RXRR", "RRXR", "RRRX"]           # rows
OMIT_SLOT = {"RRRR": None, "RXRR": 2, "RRXR": 3, "RRRX": 4}
# columns: (label prefix, legend colour, selector key, REQUIRED area). The area is fixed by
# the caption -- not "preferred with a fallback" -- so a missing candidate is a hard error.
COLUMNS = [("S+ Unit", "#1B9E5A", "Splus", "V1"),
          ("S- Unit", "#B5651D", "Sminus", "V3a/d"),
          ("O+ Unit", "#1F5FD9", "Oplus", "V4"),
          ("O++ Unit", "#7A0177", "Oplusplus", "FEF")]
NCOL = len(COLUMNS)

WIN = FULL_TRIAL_WIN
RASTER_TRIALS = 40


def pick_column(required_area, key, legacy, grand):
    """One exemplar per column, restricted to `required_area`. Empty pool -> None (hard error
    upstream): the area is fixed by the figure's caption, not a preference with a fallback."""
    if key == "Oplus":
        g = grand[grand.omission_class.isin(["O+", "O++"]) & (grand.area10 == required_area)]
        if g.empty:
            return None
        r = g.reindex(g.q1_effect_hz.abs().sort_values(ascending=False).index).iloc[0]
        return {"session": r.session, "unit_row": int(r.unit_row),
               "area": r.area10 if isinstance(r.area10, str) else r.area,
               "score": float(r.q1_effect_hz), "score_name": "q1 slot - flanks (Hz)"}

    if key == "Oplusplus":
        # Manual override: unit 51, FEF, sub-C31o_ses-230823 -- picked by inspection for a more
        # visually legible omission response than the automated |q1_effect_hz| ranking's top
        # candidate. Not itself classified O++ (omission_class == "ns"); kept for display only,
        # score reported for provenance, not as a ranking criterion.
        override = grand[(grand.session == "sub-C31o_ses-230823") & (grand.unit_row == 51) &
                         (grand.area10 == required_area)]
        if not override.empty:
            r = override.iloc[0]
            return {"session": r.session, "unit_row": int(r.unit_row),
                   "area": r.area10 if isinstance(r.area10, str) else r.area,
                   "score": float(r.q1_effect_hz), "score_name": "q1 slot - flanks (Hz), "
                   "manual pick (not top-ranked O++, chosen for visible omission response)"}

        g = grand[(grand.omission_class == "O++") & (grand.area10 == required_area)]
        if g.empty:
            return None
        r = g.reindex(g.q1_effect_hz.abs().sort_values(ascending=False).index).iloc[0]
        return {"session": r.session, "unit_row": int(r.unit_row),
               "area": r.area10 if isinstance(r.area10, str) else r.area,
               "score": float(r.q1_effect_hz), "score_name": "q1 slot - flanks (Hz)"}

    # S+/S-: the legacy table's area column carries raw labels (V3, V3a, V3d), not the pooled
    # "V3a/d" the O-family and every other figure use -- pool it the same way before filtering,
    # or a V3a/d request against this table silently matches nothing.
    legacy_area = legacy.area.replace(AREA_POOL)
    flag = f"is_{key}"
    g = legacy[(legacy[flag] == True) & (legacy_area == required_area)]  # noqa: E712
    if g.empty:
        return None
    r = g.reindex(g[f"r_{key}"].abs().sort_values(ascending=False).index).iloc[0]
    return {"session": r.session_prefix, "unit_row": int(r.unit_row_idx), "area": required_area,
           "score": float(r[f"r_{key}"]), "score_name": f"r_{key} vs standard sequence"}


PSTH_BIN_MS = 20.0
COND_COLORS = {"RRRR": "black", "RXRR": "#E377C2", "RRXR": "#2CA02C", "RRRX": "#1F5FD9"}


def compute_psth(st, onsets, win_ms, bin_ms=PSTH_BIN_MS):
    """Mean firing rate (Hz) +- SEM across trials, one point per bin, pooling all `onsets`."""
    edges = np.arange(win_ms[0], win_ms[1] + bin_ms, bin_ms)
    centers = edges[:-1] + bin_ms / 2.0
    if onsets.size == 0:
        return centers, np.zeros_like(centers), np.zeros_like(centers)
    counts = np.zeros((onsets.size, edges.size - 1))
    for i, t0 in enumerate(onsets):
        s = (st[(st >= t0 + win_ms[0] / 1000.0) & (st < t0 + win_ms[1] / 1000.0)] - t0) * 1000.0
        counts[i], _ = np.histogram(s, bins=edges)
    rate = counts / (bin_ms / 1000.0)
    mean = rate.mean(axis=0)
    sem = rate.std(axis=0, ddof=1) / np.sqrt(rate.shape[0]) if rate.shape[0] > 1 \
        else np.zeros_like(mean)
    return centers, mean, sem


def draw_figure(cells):
    """cells: dict[(row_cond, col_idx)] -> {st, onsets, area, unit_row}. 4x4 raster grid plus
    one PSTH row per column (pooled across all four R-family conditions, mean +- SEM)."""
    nrows = len(CONDS) + 1
    fig, axes = plt.subplots(nrows, NCOL, figsize=(3.0 * NCOL + 1.5, 8.6),
                             gridspec_kw={"hspace": 0.12, "wspace": 0.14,
                                          "height_ratios": [1, 1, 1, 1, 0.7]})

    ticks, labels = full_trial_ticks()
    col_colors = [c for _, c, _, _ in COLUMNS]

    rng = np.random.default_rng(0)
    for ri, cond in enumerate(CONDS):
        slot = OMIT_SLOT[cond]
        for ci in range(NCOL):
            info = cells[(cond, ci)]
            ax = axes[ri, ci]
            mark_full_trial_axis(ax, WIN, omit_slot=slot)

            st, onsets = info["st"], info["onsets"]
            if onsets.size == RASTER_TRIALS:
                show = onsets
            elif onsets.size > RASTER_TRIALS:
                show = onsets[np.linspace(0, onsets.size - 1, RASTER_TRIALS).astype(int)]
            elif COLUMNS[ci][0] == "S- Unit" and onsets.size > 0:
                # S- has fewer than 40 available trials in some conditions; resample with
                # replacement so every S- panel still shows exactly 40 trial rows.
                show = rng.choice(onsets, size=RASTER_TRIALS, replace=True)
            else:
                show = onsets
            for i, t0 in enumerate(show):
                s = (st[(st >= t0 + WIN[0] / 1000.0) & (st < t0 + WIN[1] / 1000.0)] - t0) * 1000.0
                ax.plot(s, np.full(s.size, i), "|", color="black", ms=2.4, mew=0.6,
                       zorder=3)
            ax.set_ylim(0, RASTER_TRIALS)
            if ci == 0:
                ax.set_ylabel(cond, fontsize=8, fontweight="bold")
            ax.set_xticks(ticks)
            ax.tick_params(axis="x", top=False, labeltop=False, bottom=False,
                           labelbottom=False)
            ax.text(0.01, 0.97, f"unit {info['unit_row']}", transform=ax.transAxes,
                   fontsize=7, va="top", ha="left", fontweight="bold")

    for ci in range(NCOL):
        ax = axes[len(CONDS), ci]
        # Same slot shading as the rasters above, no single omit marker (the four overlaid
        # conditions omit different slots) -- shading alone is enough to show the timing lines
        # up with the raster grid. Thin black dashed lines mark each stimulus onset.
        mark_full_trial_axis(ax, WIN, omit_slot=None)
        for slot in ("p1", "p2", "p3", "p4"):
            ax.axvline(EPOCH_ONSETS_MS[slot], color="black", ls="--", lw=0.7, zorder=4)
        for cond in CONDS:
            info = cells[(cond, ci)]
            centers, mean, sem = compute_psth(info["st"], info["onsets"], WIN)
            c = COND_COLORS[cond]
            ax.plot(centers, mean, color=c, lw=1.1, zorder=3, label=cond)
            ax.fill_between(centers, mean - sem, mean + sem, color=c, alpha=0.25,
                            linewidth=0, zorder=2)
        ax.set_xlim(WIN)
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, rotation=55, fontsize=6, ha="right")
        ax.tick_params(axis="x", bottom=True, labelbottom=True, labelsize=6)
        if ci == 0:
            ax.set_ylabel("Rate\n(Hz)", fontsize=8, fontweight="bold")
        if ci == NCOL - 1:
            ax.legend(fontsize=5, loc="upper left", frameon=False, handlelength=1.2)

    for ax in axes.flat:
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.tight_layout(rect=[0.01, 0.02, 1.0, 0.955])

    # Column titles centered on each column's actual axes span (post-layout), placed directly
    # above the grid -- close to row 0 rather than floating in unused figure margin.
    for ci, (label, color, key, area) in enumerate(COLUMNS):
        pos = axes[0, ci].get_position()
        xc = (pos.x0 + pos.x1) / 2.0
        fig.text(xc, pos.y1 + 0.012, f"{label} ({area})", ha="center",
                 fontsize=12, fontweight="bold", color=color)
    return fig


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    grand = pd.read_csv(GRAND_TABLE)
    grand["area10"] = grand["area10"].fillna(grand["area"])
    legacy = pd.read_csv(LEGACY_TABLE)

    picks = {}
    for ci, (label, color, key, area) in enumerate(COLUMNS):
        p = pick_column(area, key, legacy, grand)
        if p is None:
            raise SystemExit(f"no candidate available for column '{label}' in {area} "
                             f"({key}) -- this column's area is fixed by the figure spec, "
                             "there is no fallback")
        picks[ci] = p

    sessions_needed = {p["session"] for p in picks.values()}
    spikes, onsets_by_session = {}, {}
    for s in sessions_needed:
        path = os.path.join(NWB_DIR, s + "_rec.nwb")
        if not os.path.exists(path):
            path = os.path.join(NWB_DIR, s + ".nwb")
        sess = oa.read(path)
        onsets_by_session[s] = precompute_condition_onsets(sess, correct_only=True)
        spikes[s] = sess

    cells = {}
    for ci, p in picks.items():
        sess = spikes[p["session"]]
        st = np.sort(np.asarray(sess.get_spike_times(p["unit_row"]), float))
        on = onsets_by_session[p["session"]]
        for cond in CONDS:
            cells[(cond, ci)] = {"st": st, "onsets": np.asarray(on.get(cond, []), float),
                                 "area": p["area"], "unit_row": p["unit_row"]}

    fig = draw_figure(cells)
    path = save(fig, FIG_DIR, "fig02_grid")
    plt.close(fig)

    out, w, h = assemble([path], os.path.join(HERE, "fig02.svg"), ncol=1, letters=False)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    write([], FIG_DIR, "fig02",
         "Figure 2 -- exemplar rasters: statistics",
         preamble="No inferential test is reported here by design: each column is a single "
                  "named unit, selected as the strongest example of its type, and n = 1 "
                  "supports no test. S+/S- are the legacy grand_s_and_o_units.csv classifier "
                  "(r_Splus/r_Sminus against the standard sequence); O+ is the corrected Q1 "
                  "peak/trough conjunction from omission_grand_units.csv. These are two "
                  "different classifiers and are not pooled or compared statistically against "
                  "each other here. The population-level test of the omission question is in "
                  "context/figures/fig03_unit_census/svg/fig03_stats.md, family "
                  "'fig03_questions'.")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "grand_table": GRAND_TABLE, "legacy_table": LEGACY_TABLE, "nwb_dir": NWB_DIR,
        "layout": "rows = RRRR/RXRR/RRXR/RRRX (R-family, maximum entropy); columns = "
                  "S+(V1)/S-(V3a/d)/O+(V4)/O++(FEF); each cell = raster only, <=40 trials "
                  "shown; 16 panels, 4x4",
        "column_classifiers": {"S+": "legacy grand_s_and_o_units.csv is_Splus/r_Splus, "
                                     "ranked by |r_Splus|, restricted to V1",
                               "S-": "legacy grand_s_and_o_units.csv is_Sminus/r_Sminus, "
                                     "ranked by |r_Sminus|, restricted to V3a/d (pooling "
                                     "the legacy table's raw V3/V3a/V3d labels)",
                               "O+": "current omission_grand_units.csv Q1 conjunction, "
                                     "class in {O+, O++}, ranked by |q1_effect_hz|, "
                                     "restricted to V4",
                               "O++": "current omission_grand_units.csv Q1 conjunction, "
                                      "class == O++, ranked by |q1_effect_hz|, restricted "
                                      "to FEF"},
        "selection": "highest |score| within the named area's pool; a column's area is "
                     "fixed by the figure spec -- no cross-area fallback",
        "trials": "correct trials only", "alignment": "p1 onset (t = 0)",
        "window_ms": list(WIN), "raster_trials_shown": RASTER_TRIALS,
        "exemplars": {COLUMNS[ci][0]: {**picks[ci], "unit_row": picks[ci]["unit_row"]}
                     for ci in picks},
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "matplotlib": matplotlib.__version__},
    }
    with open(os.path.join(FIG_DIR, "fig02_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    for ci, p in picks.items():
        print(f"{COLUMNS[ci][0]:>14}  {p['session']} u{p['unit_row']:<5} {p['area']:<6} "
             f"{p['score_name']} = {p['score']:+.3f}")


if __name__ == "__main__":
    main()
