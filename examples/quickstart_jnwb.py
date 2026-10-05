"""Runnable tour of the `jnwb` public API, rendered as one figure.

    python examples/quickstart_jnwb.py

WHAT THIS IS
    Six primitives from the library, each run on a SIMULATED signal whose ground truth is known,
    so every panel can show what the function recovered NEXT TO what it should have recovered.
    That makes it a smoke test as well as documentation: if a panel stops matching its ground
    truth, something in the library moved.

WHY SIMULATED, AND HOW IT IS MARKED
    Real NWB recordings are not distributable with the repo, and a documentation figure must run
    for anyone who has just cloned it. Every panel is therefore generated from synthetic data and
    is labelled SIMULATED in the figure itself, per this repo's rule that synthetic content is
    never presented as measured. No number here is an empirical result about any dataset.

STYLE
    Palette, fonts, size tiers, line widths and the figure width come from
    `docs/figure_style.py`, the module every documentation figure uses, so the script runs from
    a checkout.

OUTPUT
    examples/figures/jnwb_quickstart.{svg,png} and jnwb_quickstart.dark.png. Two runs write the
    same bytes: the SVG carries no date and its element ids come from a fixed salt.
"""
from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

# Python puts THIS directory on sys.path, not the repository root, so a plain
# `import jnwb` resolves to whatever happens to be installed. Running this file from a
# checkout while an older jnwb sits in site-packages renders a figure of that older
# library, and every panel still says CORRECT. Prefer the checkout this file belongs to.
# A run that is deliberately qualifying an installed copy says so with
# JNWB_EXPECTED_PACKAGE_ROOT, and then this guard stands aside.
_CHECKOUT = Path(__file__).resolve().parents[1]
if not os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") and (
    _CHECKOUT / "jnwb" / "__init__.py"
).exists():
    sys.path.insert(0, str(_CHECKOUT))
if str(_CHECKOUT / "docs") not in sys.path:
    sys.path.append(str(_CHECKOUT / "docs"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

import figure_style as style             # noqa: E402
import jnwb                              # noqa: E402

FS = 1000.0
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
#: Seeds the SVG element ids, so two runs write the same file.
SVG_SALT = "jnwb-quickstart"

#: Ink per theme. The figure is drawn on a transparent background twice: the light theme writes
#: jnwb_quickstart.{svg,png} and the dark theme jnwb_quickstart.dark.png. Series colours are not
#: here: they come from `docs/figure_style.py`, one palette for both themes.
THEMES = {
    "light": {"FG": "#2d2d2d", "FG2": "#555555", "FG3": "#2d2d2d", "FAINT": "#8a8a8a",
              "stem": "jnwb_quickstart", "formats": ("svg", "png")},
    "dark": {"FG": "#e0e0e0", "FG2": "#bbbbbb", "FG3": "#cccccc", "FAINT": "#707070",
             "stem": "jnwb_quickstart.dark", "formats": ("png",)},
}
COLOURS = ("FG", "FG2", "FG3", "FAINT")
FG, FG2, FG3, FAINT = (THEMES["light"][k] for k in COLOURS)


def _signed(value: float) -> str:
    """One decimal with its sign, and zero printed as +0.0 rather than -0.0."""
    return style.num(round(value, 1) + 0.0, "+.1f")


def _label_bars(ax, values, text) -> None:
    """Write `text(v)` just above each bar, or above zero for a negative bar."""
    for i, v in enumerate(values):
        ax.annotate(text(v), xy=(i, max(v, 0.0)), xytext=(0, 2), textcoords="offset points",
                    ha="center", va="bottom", fontsize=style.SMALL, color=FG3)


def _headroom(ax, share: float) -> None:
    """Raise the top of the y axis by `share` of its span, so a legend sits above the data."""
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi + share * (hi - lo))


def panel_artifact(ax) -> str:
    """Trial-segmented artifact detection and repair: jnwb.repair_lfp_trials."""
    rng = np.random.default_rng(0)
    n_trials, n_ch, n_t = 40, 8, 600
    t = np.arange(n_t)
    seg = rng.normal(0, 1, (n_trials, n_ch, n_t))
    seg += 2.0 * np.sin(2 * np.pi * 10 * t / FS)                 # a shared 10 Hz rhythm
    hit, width = [7, 19, 31], 30                                 # synchronous transients
    for i in hit:
        seg[i, :, 300:300 + width] += 40.0
    repaired, frac, diag = jnwb.repair_lfp_trials(seg, times_ms=t, z_thresh=6.0)

    # `frac` is the fraction of (trial, time) CELLS flagged, not of trials. Comparing it to
    # len(hit)/n_trials is a units error -- it looked like a detection failure on first write.
    expected = len(hit) * width
    touched = [int(i) for i in np.flatnonzero(np.abs(seg - repaired).max(axis=(1, 2)) > 1.0)]

    ax.plot(t, seg[hit[0], 0], color=style.VARIABLE["observed"], lw=style.LW_THIN,
            label="raw (artifact injected)")
    ax.plot(t, repaired[hit[0], 0], color=style.SERIES[0], lw=style.LW_THIN,
            label="after repair_lfp_trials")
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("LFP (a.u.)")
    _headroom(ax, 0.45)
    ax.legend(frameon=False, loc="upper left")
    ok = diag["n_flagged_cells"] == expected and touched == hit
    return (f"flagged {diag['n_flagged_cells']} of {expected} injected (trial, time) cells in "
            f"trials {touched} ({'EXACT' if ok else 'MISMATCH'}); peak synchrony z = "
            f"{diag['synchrony_z_max']:.0f}")


def panel_band_power(ax) -> str:
    """Band-limited power against a baseline: jnwb.band_power + jnwb.CANONICAL_BANDS."""
    rng = np.random.default_rng(1)
    injected_hz = 22.0
    t = np.arange(4000) / FS
    base = rng.normal(0, 1, t.size)
    boost = base + 3.0 * np.sin(2 * np.pi * injected_hz * t)     # a real beta increase
    names = list(jnwb.CANONICAL_BANDS)
    db = [
        jnwb.band_power(boost, fs=FS, freq_range=jnwb.CANONICAL_BANDS[b], baseline=base)
        for b in names
    ]
    ax.bar(range(len(names)), db, color=style.SERIES[0], width=0.62)
    ax.axhline(0, color=FG2, lw=style.LW_THIN)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([n.replace("_", "\n") for n in names])
    _label_bars(ax, db, _signed)
    ax.set_ylabel("power vs baseline (dB)")
    ax.set_ylim(min(0, min(db)) - 1, max(db) * 1.25)
    top = int(np.argmax(db))
    win = names[top]
    # The label sits over the empty bars left of the largest one, and its arrow meets that
    # bar's left edge below its value label.
    ax.annotate(f"{injected_hz:.0f} Hz injected here", xy=(top - 0.31, db[top] * 0.75),
                xytext=(top - 0.55, max(db) * 0.95), ha="right", va="center",
                fontsize=style.SMALL, color=FG,
                arrowprops=dict(arrowstyle="->", color=style.VARIABLE["truth"], lw=style.LW_THIN))
    return f"largest increase in {win} ({'CORRECT' if win == 'beta' else 'UNEXPECTED'})"


def panel_onset(ax) -> str:
    """Causal smoothing and a causality-bounded onset fit: causal_exp_smooth, fit_exponential_onset."""
    rng = np.random.default_rng(2)
    bin_ms, t0_true, tau_true = 5.0, 120.0, 25.0
    t = np.arange(-500.0, 500.0, bin_ms)
    rate = 5.0 + 20.0 * np.where(t >= t0_true, 1 - np.exp(-(t - t0_true) / tau_true), 0.0)
    noisy = rate + rng.normal(0, 1.5, t.size)
    sm = jnwb.causal_exp_smooth(noisy, bin_ms=bin_ms, tau_ms=30.0)
    fit = jnwb.fit_exponential_onset(t, sm, t0_bounds_ms=(0.0, None))

    ax.plot(t, noisy, color=FAINT, lw=style.LW_THIN, label="simulated rate")
    ax.plot(t, sm, color=style.VARIABLE["smoothed"], lw=style.LW, label="causal_exp_smooth")
    ax.axvline(t0_true, color=style.VARIABLE["truth"], lw=style.LW_THIN, ls="--",
               label="true $t_0$")
    ax.axvline(fit["t0"], color=style.VARIABLE["fitted"], lw=style.LW_THIN, label="fitted $t_0$")
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("rate (Hz)")
    # Upper left: before the onset the rate sits at its floor, so the key fits there.
    ax.legend(frameon=False, loc="upper left")
    return (f"true $t_0$ {t0_true:.0f} ms, fitted {fit['t0']:.0f} ms: within "
            f"{abs(fit['t0'] - t0_true):.0f} ms, $R^2$ = {fit['r2']:.2f}")


def panel_permutation(ax) -> str:
    """Why a null needs an exchangeability scheme: jnwb.permute_labels."""
    rng = np.random.default_rng(3)
    n_g, per = 12, 20
    groups = np.repeat(np.arange(n_g), per)
    y = np.repeat(rng.integers(0, 2, n_g), per)        # label is constant WITHIN a group
    x = y + rng.normal(0, 1.0, y.size)                 # a signal that tracks the label

    def acc(labels):                                   # a deliberately naive ungrouped readout
        return max((x > thr).astype(int).__eq__(labels).mean() for thr in np.linspace(-1, 2, 40))

    glob = [acc(jnwb.permute_labels(y, scheme="global", rng=rng)) for _ in range(300)]
    bins = np.linspace(0.4, 1.0, 26)
    ax.hist(glob, bins=bins, color=FAINT, label='scheme="global"')
    ax.axvline(acc(y), color=style.VARIABLE["observed"], lw=style.LW, label="observed")

    # The point of this panel used to be a histogram of the within-group null sitting
    # on a single value. jnwb will not produce that null any more: with one label per
    # group every permutation is the identity, so the "null" is a point mass and any
    # p-value from it is 1.0 by construction. The refusal states the same lesson more
    # strongly than the degenerate histogram did, so its own first sentence is the caption.
    try:
        within = [acc(jnwb.permute_labels(y, groups=groups, scheme="within_group",
                                          rng=rng)) for _ in range(300)]
        ax.hist(within, bins=bins, color=style.SERIES[0], alpha=0.75,
                label='scheme="within_group"')
        caption = ("a within-group null on group-constant labels cannot move; the "
                   "global null can, and would look significant")
    except ValueError as refusal:
        caption = (f"refused: {str(refusal).split('. ')[0]}. The global null does move, "
                   "and would look significant")
    ax.set_xlabel("readout accuracy under the null")
    ax.set_ylabel("permutations")
    _headroom(ax, 0.6)
    ax.legend(frameon=False, loc="upper left")
    return caption


def panel_connectivity(ax) -> str:
    """Directed influence with a known direction: jnwb.granger."""
    rng = np.random.default_rng(4)
    n = 4000
    x = np.zeros(n)
    y = np.zeros(n)
    for i in range(2, n):                              # x drives y with a 2-sample delay
        x[i] = 0.55 * x[i - 1] + rng.normal(0, 1)
        y[i] = 0.35 * y[i - 1] + 0.60 * x[i - 2] + rng.normal(0, 1)
    r = jnwb.granger(x, y, order="auto")
    ax.bar([0, 1], [r.x_to_y, r.y_to_x], color=list(style.SERIES[:2]), width=0.55)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["X $\\rightarrow$ Y\n(true direction)", "Y $\\rightarrow$ X"])
    _label_bars(ax, (r.x_to_y, r.y_to_x), lambda v: style.num(v, ".3f"))
    ax.set_ylabel(f"Granger influence ({r.unit})")
    ax.set_ylim(0, max(r.x_to_y, r.y_to_x) * 1.20)
    ok = r.x_to_y > r.y_to_x
    return (f"net = {style.num(r.net, '+.3f')} in the simulated direction "
            f"({'CORRECT' if ok else 'WRONG DIRECTION'})")


def panel_decoding(ax) -> str:
    """Nested cross-validated decoding against its own majority baseline: nested_cv_linear_svm."""
    rng = np.random.default_rng(5)
    n, d = 200, 20
    labels = rng.integers(0, 2, n)
    X_sig = rng.normal(0, 1, (n, d)) + labels[:, None] * 0.9     # separable
    X_nul = rng.normal(0, 1, (n, d))                             # nothing to decode
    a = jnwb.nested_cv_linear_svm(X_sig, labels, n_splits=5)
    b = jnwb.nested_cv_linear_svm(X_nul, labels, n_splits=5)
    ax.bar([0, 1], [a["accuracy"], b["accuracy"]], color=list(style.SERIES[:2]),
           width=0.55)
    ax.axhline(a["majority_baseline_accuracy"], color=style.VARIABLE["baseline"],
               lw=style.LW_THIN, ls="--", label="majority baseline")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["signal present", "no signal"])
    ax.set_ylabel("accuracy")
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, loc="upper right")
    return (f"{a['accuracy']:.2f} with signal vs {b['accuracy']:.2f} without; "
            "the baseline is returned, never assumed to be 0.5")


PANELS = [
    ("Artifact detection and repair", "jnwb.repair_lfp_trials", panel_artifact),
    ("Band-limited power", "jnwb.band_power + CANONICAL_BANDS", panel_band_power),
    ("Onset latency", "jnwb.causal_exp_smooth + fit_exponential_onset", panel_onset),
    ("Nulls need an exchangeability scheme", "jnwb.permute_labels", panel_permutation),
    ("Directed connectivity", "jnwb.granger", panel_connectivity),
    ("Population decoding", "jnwb.nested_cv_linear_svm", panel_decoding),
]
#: Characters per caption line, for a caption as wide as its panel.
CAPTION_WIDTH = 48


def main() -> None:
    # Which jnwb is this? Run as `python examples/quickstart_jnwb.py`, Python puts
    # `examples/` on sys.path and not the repository root, so `import jnwb` resolves to
    # whatever is installed rather than to the checkout this file sits in. Printing it
    # turns a silent substitution into a visible one.
    print(f"jnwb {jnwb.__version__} from {os.path.dirname(jnwb.__file__)}")
    os.makedirs(OUT, exist_ok=True)
    global FG, FG2, FG3, FAINT
    for theme in THEMES.values():
        FG, FG2, FG3, FAINT = (theme[k] for k in COLOURS)
        style.apply()
        plt.rcParams.update({"svg.fonttype": "none", "svg.hashsalt": SVG_SALT,
                             "text.color": FG, "axes.labelcolor": FG, "axes.titlecolor": FG,
                             "xtick.color": FG, "ytick.color": FG, "axes.edgecolor": FG2,
                             "legend.labelcolor": FG})
        fig, axes = plt.subplots(3, 2, figsize=(style.WIDTH, 11.0), dpi=style.DPI)
        fig.subplots_adjust(hspace=1.1, wspace=0.34, left=0.09, right=0.98, top=0.89,
                            bottom=0.08)

        for ax, letter, (title, api, fn) in zip(axes.ravel(), "ABCDEF", PANELS):
            caption = fn(ax)
            style.panel_title(ax, letter, f"{title}\n{api}", fontsize=style.LABEL)
            # Below the x-axis label, whatever its height, and as wide as the panel.
            ax.annotate("\n".join(textwrap.wrap(caption, CAPTION_WIDTH)), xy=(0.0, 0.0),
                        xycoords=("axes fraction", ax.xaxis.label), xytext=(0, -3),
                        textcoords="offset points", ha="left", va="top",
                        fontsize=style.SMALL, color=FG2)
            print(f"  {api:44s} {caption}")

        fig.suptitle("jnwb quickstart - six operations, each checked against a known ground truth",
                     fontsize=style.TITLE, y=0.975)
        fig.text(0.5, 0.945, "ALL DATA ON THIS FIGURE IS SIMULATED. No panel is an empirical "
                             "result about any recording.", ha="center", fontsize=style.LABEL,
                 color=FG, style="italic")
        for ext in theme["formats"]:
            p = os.path.join(OUT, f"{theme['stem']}.{ext}")
            # An SVG records its creation date unless told not to; a PNG records none.
            fig.savefig(p, dpi=style.DPI, metadata={"Date": None} if ext == "svg" else None)
            print(f"wrote {p}")
        plt.close(fig)


if __name__ == "__main__":
    main()
