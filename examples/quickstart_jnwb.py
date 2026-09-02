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

    For real results computed from real recordings, see the `omission/` example project.

OUTPUT
    examples/figures/jnwb_quickstart.{svg,png}
"""
from __future__ import annotations

import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

import jnwb                              # noqa: E402

FS = 1000.0
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
ACCENT, TRUTH, BAD = "#08306B", "#1B7837", "#8B0000"


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

    ax.plot(t, seg[hit[0], 0], color=BAD, lw=0.8, label="raw (artifact injected)")
    ax.plot(t, repaired[hit[0], 0], color=ACCENT, lw=0.9, label="after repair_lfp_trials")
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("LFP (a.u.)")
    ax.legend(frameon=False, fontsize=6.5, loc="upper left")
    ok = diag["n_flagged_cells"] == expected and touched == hit
    return (f"flagged {diag['n_flagged_cells']} of {expected} injected (trial, time) cells in "
            f"trials {touched} ({'EXACT' if ok else 'MISMATCH'}); peak synchrony z = "
            f"{diag['synchrony_z_max']:.0f}")


def panel_band_power(ax) -> str:
    """Band-limited power against a baseline: jnwb.band_power + jnwb.CANONICAL_BANDS."""
    rng = np.random.default_rng(1)
    t = np.arange(4000) / FS
    base = rng.normal(0, 1, t.size)
    boost = base + 3.0 * np.sin(2 * np.pi * 22.0 * t)            # a real beta increase
    names = list(jnwb.CANONICAL_BANDS)
    db = [jnwb.band_power(boost, FS, jnwb.CANONICAL_BANDS[b], baseline=base) for b in names]
    cols = ["#0000EE", "#EE0000", "#FF8C00", "#FF00FF", "#00A000"]
    ax.bar(range(len(names)), db, color=cols, width=0.62)
    ax.axhline(0, color="#444444", lw=0.8)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([n.replace("_", "\n") for n in names], fontsize=6.5)
    for i, v in enumerate(db):
        ax.text(i, v + 0.5, f"{v:+.1f}", ha="center", fontsize=6.2, color="#333333")
    ax.set_ylabel("power vs baseline (dB)")
    ax.set_ylim(min(0, min(db)) - 1, max(db) * 1.22)
    win = names[int(np.argmax(db))]
    ax.annotate("22 Hz injected here", xy=(2, db[2]), xytext=(2.6, max(db) * 0.75),
                fontsize=6.5, color=TRUTH,
                arrowprops=dict(arrowstyle="->", color=TRUTH, lw=0.8))
    return f"largest increase in {win} ({'CORRECT' if win == 'beta' else 'UNEXPECTED'})"


def panel_onset(ax) -> str:
    """Causal smoothing and a causality-bounded onset fit: causal_exp_smooth, fit_exponential_onset."""
    rng = np.random.default_rng(2)
    bin_ms, t0_true, tau_true = 5.0, 120.0, 25.0
    t = np.arange(-300.0, 500.0, bin_ms)
    rate = 5.0 + 20.0 * np.where(t >= t0_true, 1 - np.exp(-(t - t0_true) / tau_true), 0.0)
    noisy = rate + rng.normal(0, 1.5, t.size)
    sm = jnwb.causal_exp_smooth(noisy, bin_ms=bin_ms, tau_ms=30.0)
    fit = jnwb.fit_exponential_onset(t, sm, t0_bounds=(0.0, None))

    ax.plot(t, noisy, color="#BBBBBB", lw=0.7, label="simulated rate")
    ax.plot(t, sm, color=ACCENT, lw=1.4, label="causal_exp_smooth")
    ax.axvline(t0_true, color=TRUTH, lw=1.2, ls="--", label=f"true onset {t0_true:.0f} ms")
    ax.axvline(fit["t0"], color=BAD, lw=1.2, label=f"fitted $t_0$ {fit['t0']:.0f} ms")
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("rate (Hz)")
    ax.legend(frameon=False, fontsize=6.2, loc="upper left")
    return f"recovered $t_0$ within {abs(fit['t0'] - t0_true):.0f} ms, $R^2$ = {fit['r2']:.2f}"


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
    within = [acc(jnwb.permute_labels(y, groups=groups, scheme="within_group", rng=rng))
              for _ in range(300)]
    bins = np.linspace(0.4, 1.0, 26)
    ax.hist(glob, bins=bins, color="#BBBBBB", label='scheme="global"')
    ax.hist(within, bins=bins, color=BAD, alpha=0.75, label='scheme="within_group"')
    ax.axvline(acc(y), color=TRUTH, lw=1.4, label="observed")
    ax.set_xlabel("readout accuracy under the null")
    ax.set_ylabel("permutations")
    ax.legend(frameon=False, fontsize=6.2, loc="upper left")
    return ("a within-group null on group-constant labels cannot move; the global null can, "
            "and would look significant")


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
    ax.bar([0, 1], [r.x_to_y, r.y_to_x], color=[ACCENT, "#BBBBBB"], width=0.55)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["X $\\rightarrow$ Y\n(true direction)", "Y $\\rightarrow$ X"], fontsize=7)
    for i, v in enumerate((r.x_to_y, r.y_to_x)):
        ax.text(i, v + max(r.x_to_y, 1e-3) * 0.03, f"{v:.3f}", ha="center", fontsize=6.5,
                color="#333333")
    ax.set_ylabel("Granger influence")
    ax.set_ylim(0, max(r.x_to_y, r.y_to_x) * 1.20)
    ok = r.x_to_y > r.y_to_x
    return (f"net = {r.net:+.3f} in the simulated direction "
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
    ax.bar([0, 1], [a["accuracy"], b["accuracy"]], color=[ACCENT, "#BBBBBB"], width=0.55)
    ax.axhline(a["majority_baseline_accuracy"], color=TRUTH, lw=1.3, ls="--",
               label="majority baseline")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["signal present", "no signal"], fontsize=7)
    ax.set_ylabel("accuracy")
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, fontsize=6.5, loc="lower right")
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


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.titlesize": 8.5,
                         "svg.fonttype": "none", "axes.linewidth": 0.8})
    fig, axes = plt.subplots(2, 3, figsize=(11.0, 6.8))
    fig.subplots_adjust(hspace=0.70, wspace=0.30, left=0.06, right=0.985, top=0.855, bottom=0.155)

    for ax, (title, api, fn) in zip(axes.ravel(), PANELS):
        caption = fn(ax)
        ax.set_title(f"{title}\n{api}", loc="left", fontsize=8, color="#222222")
        ax.text(0.0, -0.28, "\n".join(textwrap.wrap(caption, 62)), transform=ax.transAxes,
                fontsize=6.4, color="#444444", va="top")
        print(f"  {api:44s} {caption}")

    fig.suptitle("jnwb quickstart - six primitives, each checked against a known ground truth",
                 fontsize=12, y=0.965)
    fig.text(0.5, 0.917, "ALL DATA ON THIS FIGURE IS SIMULATED. No panel is an empirical result "
                         "about any recording.", ha="center", fontsize=8, color=BAD, style="italic")
    for ext in ("svg", "png"):
        p = os.path.join(OUT, f"jnwb_quickstart.{ext}")
        fig.savefig(p, dpi=200)
        print(f"wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
