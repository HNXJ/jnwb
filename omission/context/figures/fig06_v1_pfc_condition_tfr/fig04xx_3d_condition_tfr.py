r"""
Figure 6 supplement (2026-08-14): true 3-D (time x frequency x power) surface renderings of
the same RXRR-vs-RRRR condition spectrograms fig04_v1_pfc_condition_tfr.py's main figure draws
as 2-D heatmaps, for the same four areas (V1, V3a/d, TEO, PFC).

WHY A SEPARATE SCRIPT, NOT A MODE ON THE MAIN ONE
    A 3-D surface is a different rendering path end to end (mpl_toolkits.mplot3d, a viewing
    angle, no shared colour axis across panels in the same way a 2-D grid's colorbars work) --
    same "own script, same figure directory, additive" convention as fig04xx_pair_stim_
    omission_tfr.py. This does not change fig04.svg or its own panels.

DATA SOURCE
    outputs/condition_tfr_maps_p1d1p2d2p3_v3/maps.npz (scripts/extract_condition_tfr_maps.py,
    renamed 2026-08-22 from extract_condition_tfr_maps_v3.py during normalization) -- the
    CURRENT canonical condition-map extraction. v3 adds cross-trial-median artifact repair over
    v2 and is stated as "current best estimate" in context/PROJECT_STATE.md's 2026-08-14
    resolution note ("RESOLVED 2026-08-14 -- the v2 rerun above still had no trial-level
    artifact rejection"). This supplement previously read v2
    (outputs/condition_tfr_maps_p1d1p2d2p3_v2/maps.npz) directly -- repointed to v3 2026-08-22.
    NOT v1 (outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz, built 2026-08-04 from the
    pre-migration D:/workspace/data/tfr_arrays corpus, marked superseded).

    FIXED 2026-08-22 (was flagged, not fixed, as of the prior pass): fig04_v1_pfc_condition_tfr.py's
    own CONDITION_MAPS constant repointed from a wrong-machine absolute path (reading the
    superseded v1 extraction even if the drive existed) to a repo-relative v3 path via
    jnwb.paths.REPO_ROOT.

MEASURE
    Per session: ratio = sums[i] / counts[i] (POWER RATIO, not yet logged). Grand mean: nanmean
    of per-session ratio maps across sessions (equal session weight, "log last" -- average in
    ratio space, then 10*log10 once), exactly matching draw_condition_spectrogram()'s own
    "grand = to_db(np.nanmean(np.stack(list(sess.values())), axis=0))". No NaN cells were found
    in this corpus for the areas/conditions used here (full 980/980 channel x trial coverage
    checked on V1 RXRR); a defensive NaN check still gates the render so a future gap in
    coverage fails loudly rather than plotting a hole.

DISPLAY
    Cosmetic Gaussian smoothing (gaussian_smooth_2d, imported from fig04_v1_pfc_condition_tfr.py
    rather than re-implemented -- proportional/constant-Q on frequency, epoch-segmented on time,
    same as the 2-D panels) is applied before the mesh is downsampled 2x on both axes (still
    ~50 x 155 quads/panel) purely to keep the SVG mesh a manageable size; no statistic reads
    this smoothed, downsampled array. Colour is per-panel autoscaled (99th percentile of |dB|,
    same rule panel_vlim() uses in the main figure) and applied as flat per-quad facecolors
    (shade=False) so the colour axis reads the same as the 2-D pcolormesh version, not a
    lighting-shaded surface. Frequency axis is manually log-transformed (log2 Hz) with the same
    tick set as the 2-D panels ([4, 8, 14, 30, 50, 80, 150] Hz) -- Axes3D does not reliably
    support set_yscale("log"). The omitted slot (RXRR only) is marked with a single dashed red
    vertical line along the near edge of the surface plus a text label, a deliberately lighter
    marker than the 2-D panels' full epoch shading (drawing shaded epoch planes in 3-D adds
    real complexity for a supplement; the 2-D main figure remains the panel with full epoch
    context).

OUTPUT
    svg/fig04xx_3d_<area>_<cond>.svg/.png -- 8 individual panels (4 areas x RXRR/RRRR)
    fig04xx_3d_condition_tfr.svg/.png -- all 8 assembled into one 4-row x 2-col grid
    svg/fig04xx_3d_receipt.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers the '3d' projection)
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.dirname(HERE)
sys.path.insert(0, FIGDIR)
sys.path.insert(0, HERE)
from figstyle import use_house_style, save as figstyle_save  # noqa: E402
from svgassemble import assemble  # noqa: E402
from jnwb import paths as _P  # noqa: E402
from jnwb.spectral import to_db  # noqa: E402
from fig04_v1_pfc_condition_tfr import (  # noqa: E402
    gaussian_smooth_2d, CONDITION_AREAS, CONDITIONS, CONDITION_WIN, COND_OMIT_SLOT, COND_LABEL,
    SPEC_SMOOTH_TIME_BINS,
)

MAPS_NPZ = str(_P.outputs_dir() / "condition_tfr_maps_p1d1p2d2p3_v3" / "maps.npz")
SVG_DIR = os.path.join(HERE, "svg")

FREQ_TICKS_HZ = [4, 8, 14, 30, 50, 80, 150]
FREQ_STRIDE, TIME_STRIDE = 2, 2       # mesh downsample factor, cosmetic only (post-smoothing)
VIEW_ELEV, VIEW_AZIM = 26, -58


def load_condition_maps():
    """(maps, freqs, times) -- maps[key] is a per-session RATIO array (freq x time), key =
    'session|area|layer|cond'. Mirrors fig04_v1_pfc_condition_tfr.load_condition_maps()'s ratio
    computation exactly, without that module's coverage-threshold masking (not needed here --
    this loader is only ever asked for the RXRR/RRRR condition-map corpus, which has full
    channel x trial coverage throughout the window; see module docstring)."""
    z = np.load(MAPS_NPZ, allow_pickle=True)
    keys = [str(k) for k in z["keys"]]
    sums, counts, freqs, times = z["sums"], z["counts"], z["freqs"], z["times"]
    maps = {}
    for i, k in enumerate(keys):
        with np.errstate(invalid="ignore", divide="ignore"):
            maps[k] = np.where(counts[i] > 0, sums[i] / np.maximum(counts[i], 1), np.nan)
    return maps, freqs, times


def area_cond_sessions(maps, area, cond, layer="all"):
    return {k.split("|")[0]: m for k, m in maps.items()
            if k.split("|")[1] == area and k.split("|")[2] == layer and k.split("|")[3] == cond}


def panel_vlim(grand_db):
    finite = grand_db[np.isfinite(grand_db)]
    if finite.size == 0:
        return (-1.0, 1.0)
    vmax = max(float(np.nanpercentile(np.abs(finite), 99)), 0.5)
    return (-round(vmax, 1), round(vmax, 1))


def draw_3d_panel(area, cond, sess, freqs, times):
    grand_ratio = np.nanmean(np.stack(list(sess.values())), axis=0)
    if not np.isfinite(grand_ratio).all():
        raise ValueError(
            f"{area} {cond}: grand ratio map has non-finite cells -- this loader assumes full "
            "coverage (see module docstring); a real gap needs a coverage mask, not a silent "
            "surface hole.")
    grand_db = to_db(grand_ratio)
    grand_smooth = gaussian_smooth_2d(grand_db, freqs, times, CONDITION_WIN, SPEC_SMOOTH_TIME_BINS)
    vlim = panel_vlim(grand_smooth)

    f_ds = freqs[::FREQ_STRIDE]
    t_ds = times[::TIME_STRIDE]
    z = grand_smooth[::FREQ_STRIDE, ::TIME_STRIDE]
    log_f = np.log2(f_ds)
    X, Y = np.meshgrid(t_ds, log_f)

    cmap = cm.get_cmap("viridis")
    norm = Normalize(vmin=vlim[0], vmax=vlim[1])
    colors = cmap(norm(z))

    fig = plt.figure(figsize=(5.6, 4.6))
    ax = fig.add_subplot(111, projection="3d")
    surf = ax.plot_surface(X, Y, z, facecolors=colors, rstride=1, cstride=1,
                           linewidth=0, antialiased=False, shade=False)
    surf.set_rasterized(True)

    ax.set_xlim(*CONDITION_WIN)
    ax.set_xlabel("Time from p1 onset (ms)", fontsize=8, labelpad=6)
    ax.set_yticks(np.log2(FREQ_TICKS_HZ))
    ax.set_yticklabels([f"{v:g}" for v in FREQ_TICKS_HZ], fontsize=7)
    ax.set_ylabel("Frequency (Hz)", fontsize=8, labelpad=6)
    ax.set_zlim(*vlim)
    ax.set_zlabel("Power change (dB)", fontsize=8, labelpad=2)
    ax.tick_params(labelsize=6.5)
    ax.view_init(elev=VIEW_ELEV, azim=VIEW_AZIM)

    omit_slot = COND_OMIT_SLOT[cond]
    if omit_slot is not None:
        from figstyle import EPOCH_ONSETS_MS
        onset = EPOCH_ONSETS_MS[f"p{omit_slot}"]
        if CONDITION_WIN[0] <= onset <= CONDITION_WIN[1]:
            ax.plot([onset, onset], [log_f[0], log_f[0]], [vlim[0], vlim[1]],
                   color="red", ls="--", lw=1.6, zorder=10)
            ax.text(onset, log_f[0], vlim[1], "  Omit", color="red", fontsize=7, zorder=11)

    m = cm.ScalarMappable(norm=norm, cmap=cmap)
    m.set_array([])
    cb = fig.colorbar(m, ax=ax, shrink=0.62, pad=0.10, fraction=0.05)
    cb.set_label("dB", fontsize=7, rotation=270, labelpad=9)
    cb.ax.tick_params(labelsize=6.5)

    ax.set_title(f"{area}, {COND_LABEL[cond]}  n={len(sess)} sessions", fontsize=9, pad=0)
    fig.tight_layout()
    return fig, len(sess)


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    use_house_style()
    maps, freqs, times = load_condition_maps()

    svgs = []
    n_sessions_report = {}
    for area in CONDITION_AREAS:
        for cond in CONDITIONS:
            sess = area_cond_sessions(maps, area, cond)
            fig, n = draw_3d_panel(area, cond, sess, freqs, times)
            stem = f"fig04xx_3d_{area.replace('/', '')}_{cond}"
            svg_path = figstyle_save(fig, SVG_DIR, stem, dpi=190)
            plt.close(fig)
            svgs.append(svg_path)
            n_sessions_report[f"{area}_{cond}"] = n
            print(f"drew {stem}: n={n} sessions")

    out, w, h = assemble(svgs, os.path.join(HERE, "fig04xx_3d_condition_tfr.svg"),
                         ncol=2, width=11.2 * 72)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "source": MAPS_NPZ,
        "areas": CONDITION_AREAS,
        "conditions": CONDITIONS,
        "window_ms_re_p1": list(CONDITION_WIN),
        "measure": "session-level ratio, nanmean across sessions in ratio space (equal session "
                  "weight), 10*log10 once -- matches draw_condition_spectrogram's own order",
        "display": {
            "smoothing": "gaussian_smooth_2d (proportional freq, epoch-segmented time), "
                        "cosmetic only, reused from fig04_v1_pfc_condition_tfr.py",
            "mesh_downsample": [FREQ_STRIDE, TIME_STRIDE],
            "colour_scale": "per-panel autoscale, 99th percentile of |dB|",
            "view_elev_azim": [VIEW_ELEV, VIEW_AZIM],
        },
        "n_sessions_by_area_cond": n_sessions_report,
    }
    with open(os.path.join(SVG_DIR, "fig04xx_3d_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"WROTE {SVG_DIR}/fig04xx_3d_receipt.json")


if __name__ == "__main__":
    main()
