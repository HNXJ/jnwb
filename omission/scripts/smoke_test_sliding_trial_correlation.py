r"""
One-session smoke test: within-trial sliding-window correlation between two LFP channels,
band power, +-200ms window / 10ms step, real (trial-matched) vs a trial-mismatch shuffle null.
Not a figure -- validates the design and measures real per-pair/per-window cost before
committing to a full corpus run.

DESIGN (per user spec, 2026-08-05)
    For trial K: corr(channel_N_power[trial K, window w], channel_M_power[trial K, window w])
    across a battery of sliding windows w. This is NOT the earlier per-window-scalar-then-
    across-trials design -- it is a same-trial, within-trial-time sliding correlation.
    Null: for each window, correlate channel_N[trial K] against channel_M[trial J != K]
    (mismatched trial pairing) -- breaks the true within-trial coupling while preserving each
    channel's own trial-to-trial structure, same logic as omission.jnwb_ext.connectivity._surrogate_source.

CHANNEL SELECTION ("good" channels, not arbitrary depth-spaced)
    Per area, rank channels by a band-averaged SNR-like score computed from the EXISTING
    channel_band_power_v2 census (no new computation): mean over the 5 bands of
    |db_mid_omirel| / (db_mid_omirel_sd / sqrt(n_trials)) -- a per-channel, per-band t-like
    magnitude, averaged across bands. Top-K per area are the "good" channels.
"""
from __future__ import annotations

import re
import time

import numpy as np
import pandas as pd
from jnwb import paths as _P

TFR_DIR = _P.tfr_dir()
CENSUS = _P.REPO_ROOT / "outputs/lfp_band_census_v2/channel_band_power.csv.gz"
AREA_VEC = _P.REPO_ROOT / "outputs/channel_area_vector/channel_area_vector.csv"

FREQS_HZ = np.arange(3, 201, 2)
N_TIMES_SRC = 500
T0_SRC_MS, BIN_MS = -1000.0, 10.0
BETA = (14, 30)
WIN_HALF_MS = 200.0          # +-200ms
STEP_MS = 10.0
COND = "RXRR"
N_SHUFFLE = 200

FNAME_RE = re.compile(r"^sub-(?P<subject>.+?)_ses-(?P<session>.+?)-(?P<probe>[A-Z])-"
                      r"(?P<area>.+)-(?P<cond>[A-Z]+)$")


def good_channels(session_prefix, area, k=8):
    df = pd.read_csv(CENSUS)
    sub = df[(df.session_prefix == session_prefix) & (df.area == area)].copy()
    sub["t_like"] = sub["db_mid_omirel"].abs() / (sub["db_mid_omirel_sd"] /
                                                  np.sqrt(sub["n_trials"].clip(lower=1)))
    score = sub.groupby("channel")["t_like"].mean().sort_values(ascending=False)
    return score.index[:k].to_numpy()


def band_power_trace(arr_mm, chans, band, i0, i1):
    """Per-trial band power at native 10ms resolution, selected channels, window [i0,i1)."""
    f0, f1 = np.searchsorted(FREQS_HZ, band[0]), np.searchsorted(FREQS_HZ, band[1])
    block = np.asarray(arr_mm[:, chans, f0:f1, i0:i1], dtype=np.float64)  # (tr, ch, f, t)
    return block.mean(axis=2)  # (tr, ch, t)


def _sliding_windows(a, win_len, step_bins, win_half_bins, n_t):
    """a: (n_series, n_t) -> (n_series, n_windows, win_len) view via stride tricks, one
    window per step position (no python loop over windows)."""
    centers = np.arange(win_half_bins, n_t - win_half_bins, step_bins)
    starts = centers - win_half_bins
    # advanced-index gather: (n_series, n_windows, win_len)
    idx = starts[:, None] + np.arange(win_len)[None, :]
    return a[:, idx], centers


def _normalize(w):
    """Center and L2-normalize the last axis so correlation reduces to a dot product --
    computed ONCE per signal, never recomputed per shuffle (the earlier version recomputed
    x's mean/norm inside every one of N_SHUFFLE calls, pure waste since x never changes)."""
    m = w - w.mean(axis=-1, keepdims=True)
    norm = np.sqrt((m ** 2).sum(axis=-1, keepdims=True))
    return np.divide(m, norm, out=np.zeros_like(m), where=norm > 0), (norm[..., 0] > 0)


def _corr_and_null(xw, yw, n_shuffle=N_SHUFFLE, seed=0):
    """Shared core: xw, yw are already-gathered (n_trials, n_windows, win_len) arrays --
    'windows' may be sliding time-window positions (sliding_corr_same_trial) or lag offsets
    (lagged_corr_same_trial); the einsum/shuffle math is identical either way. Vectorized
    across windows AND shuffles at once via a single einsum dot-product on pre-normalized
    windows (a per-window, per-shuffle python loop, and even a naive broadcast-and-recompute
    version, both measured too slow to scale to this project's full pair/session count -- same
    lesson this codebase already learned once for a different estimator, see
    fig06_band_power_coupling's README "vectorized across all shuffles" note). Returns
    (n_trials, n_windows) real trial-matched correlation and (n_shuffle, n_windows) null built
    from mismatched trial pairs."""
    xn, xok = _normalize(xw)   # (tr, nw, L), (tr, nw)
    yn, yok = _normalize(yw)

    real = np.einsum("twl,twl->tw", xn, yn)
    # near-zero-variance windows are already zero-vectors from _normalize, so their dot
    # product is exactly 0, not NaN -- rare (flat window) and negligible for a mean/z-score,
    # not worth the indexing complexity of an explicit NaN mask here.

    n_tr = xw.shape[0]
    rng = np.random.default_rng(seed)
    idx = np.arange(n_tr)
    perms = np.empty((n_shuffle, n_tr), dtype=int)
    for s in range(n_shuffle):
        p = rng.permutation(n_tr)
        fixed = p == idx
        if fixed.any():
            fixed_idx = idx[fixed]
            p[fixed_idx] = np.roll(p[fixed_idx], 1) if fixed_idx.size > 1 else \
                idx[(fixed_idx[0] + 1) % n_tr]
        perms[s] = p
    yn_shuf = yn[perms]                                     # (S, tr, nw, L)
    null_per_trial = np.einsum("twl,stwl->stw", xn, yn_shuf)  # (S, tr, nw)
    null = np.nanmean(null_per_trial, axis=1)                # (S, nw)
    return real, null


def sliding_corr_same_trial(x, y, win_half_bins, step_bins):
    """x, y: (n_trials, n_times). Same window position, held-fixed lag=0, slid across trial
    time -- answers "does coupling strength change over the trial." See lagged_corr_same_trial
    for the complementary question ("does one signal lead the other")."""
    n_tr, n_t = x.shape
    win_len = 2 * win_half_bins
    xw, centers = _sliding_windows(x, win_len, step_bins, win_half_bins, n_t)  # (tr, nw, L)
    yw, _ = _sliding_windows(y, win_len, step_bins, win_half_bins, n_t)
    real, null = _corr_and_null(xw, yw)
    return real, null, centers


def lagged_corr_same_trial(x, y, win_len_core, pad_bins, lag_step_bins=1,
                           n_shuffle=N_SHUFFLE, seed=0):
    """x, y: (n_trials, win_len_core + 2*pad_bins) -- x and y must already include pad_bins of
    extra margin on each side of the analysis window, fetched by the caller (e.g. a wider
    bin_spikes() window), so a shifted y never runs off the edge of what was extracted.

    Held FIXED: x's own window, the analysis window itself (win_len_core bins, centered in the
    padded trace). Slides instead: y's window, by lag in
    [-pad_bins*BIN_MS, +pad_bins*BIN_MS] relative to x, in lag_step_bins steps. A peak at
    lag > 0 means y at a LATER time resembles x now -- x's activity leads y's; lag < 0 means
    y leads x. Same trial-mismatch shuffle null as sliding_corr_same_trial, reusing the same
    einsum/normalize core (_corr_and_null) -- only how the window array is gathered differs.

    Returns (n_trials, n_lags) real, (n_shuffle, n_lags) null, and the lags array (in bins).
    """
    n_tr, n_t = x.shape
    lags = np.arange(-pad_bins, pad_bins + 1, lag_step_bins)
    x_core = x[:, pad_bins:pad_bins + win_len_core]                  # (tr, L), lag-independent
    xw = np.broadcast_to(x_core[:, None, :], (n_tr, len(lags), win_len_core)).copy()
    starts = pad_bins + lags                                        # (n_lags,)
    idx = starts[:, None] + np.arange(win_len_core)[None, :]         # (n_lags, L)
    yw = y[:, idx]                                                   # (tr, n_lags, L)
    real, null = _corr_and_null(xw, yw, n_shuffle, seed)
    return real, null, lags


def main():
    av = pd.read_csv(AREA_VEC)
    session = av.session_prefix.iloc[0]
    print("test session:", session)

    within_area = "V1"
    between_areas = ("V1", "PFC")

    seg = {}
    for (sp, pl, a), g in av.groupby(["session_prefix", "probe_letter", "area"]):
        seg[(sp, pl, a)] = g.sort_values("channel")["channel"].to_numpy()

    import glob, os
    files = {}
    for f in glob.glob(os.path.join(TFR_DIR, f"sub-*{session.split('sub-')[1]}*-{COND}.npy")):
        m = FNAME_RE.match(os.path.basename(f)[:-4])
        if m:
            files[(m["probe"], m["area"])] = f
    print("files found:", list(files.keys())[:10])

    gc_v1 = good_channels(session, within_area, k=8)
    print(f"good {within_area} channels:", gc_v1)

    # load one file covering V1
    v1_files = [f for (pl, a), f in files.items() if a == within_area or a in ("V3", "V3a", "V3d") == False and a == within_area]
    v1_file = next((f for (pl, a), f in files.items() if a == within_area), None)
    if v1_file is None:
        print("no V1 file for this session/cond; aborting smoke test")
        return
    arr = np.load(v1_file, mmap_mode="r")
    print("arr shape", arr.shape)

    win_half_bins = int(round(WIN_HALF_MS / BIN_MS))
    step_bins = int(round(STEP_MS / BIN_MS))
    i0, i1 = 0, min(arr.shape[3], 300)  # first 3000ms for the smoke test

    t0 = time.time()
    x = band_power_trace(arr, [gc_v1[0]], BETA, i0, i1)[:, 0, :]
    y = band_power_trace(arr, [gc_v1[1]], BETA, i0, i1)[:, 0, :]
    real, null, centers = sliding_corr_same_trial(x, y, win_half_bins, step_bins)
    elapsed = time.time() - t0
    print(f"within-area pair: {real.shape[0]} trials, {len(centers)} windows, {elapsed:.2f}s")
    print("mean real corr per window (first 5):", np.nanmean(real, axis=0)[:5])
    print("null mean/std (first 5):", null.mean(axis=0)[:5], null.std(axis=0)[:5])
    z = (np.nanmean(real, axis=0) - null.mean(axis=0)) / null.std(axis=0)
    print("z-score range:", np.nanmin(z), np.nanmax(z))


if __name__ == "__main__":
    main()
