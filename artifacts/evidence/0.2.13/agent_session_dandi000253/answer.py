"""Blind analysis of examples/data/dandi000253_excerpt.nwb with the jnwb library.

Prints one line per question, Q1: to Q5:, to stdout. Diagnostics go to stderr.
Run from the checkout: cd C:/workspace/jnwb && python <this file>
A script run by path imports the installed jnwb unless the checkout is put first on sys.path.
"""

import sys
import warnings
from collections import Counter

sys.path.insert(0, "C:/workspace/jnwb")
sys.dont_write_bytecode = True  # keep the read-only checkout free of new __pycache__ files

import numpy as np

import jnwb

PATH = "C:/workspace/jnwb/examples/data/dandi000253_excerpt.nwb"
CONTAINER = "probe_1_lfp"
SERIES = "probe_1_lfp_window"
PARAMS = ["orientation", "contrast", "spatial_frequency", "temporal_frequency"]
PRE_S = (-0.45, -0.05)
POST_S = (0.05, 0.45)
WIN_S = (-0.5, 0.5)
HIGH_GAMMA = jnwb.CANONICAL_BANDS["high_gamma"]


def in_window(t_axis, lo, hi):
    return (t_axis >= lo - 1e-9) & (t_axis <= hi + 1e-9)


def band_db(epochs, t_axis, rate):
    pre_sel = in_window(t_axis, *PRE_S)
    post_sel = in_window(t_axis, *POST_S)
    assert pre_sel.sum() == 500 and post_sel.sum() == 500, (pre_sel.sum(), post_sel.sum())
    assert np.isfinite(epochs).all(), "epochs contain NaN"
    p_pre = np.array([jnwb.band_power(e[pre_sel], fs=rate, freq_range=HIGH_GAMMA, normalize=False)
                      for e in epochs])
    p_post = np.array([jnwb.band_power(e[post_sel], fs=rate, freq_range=HIGH_GAMMA, normalize=False)
                       for e in epochs])
    rom = float(jnwb.aggregate_to_db(p_post, p_pre, how="ratio_of_means", aggregate_over=0))
    mor = float(jnwb.aggregate_to_db(p_post, p_pre, how="mean_of_ratios", aggregate_over=0))
    return rom, mor, len(epochs)


def main():
    table = jnwb.resolve_interval_table(PATH, table=None)
    info = jnwb.inspect(PATH)

    with jnwb.nwb_read_io(PATH) as io:
        nwb = io.read()
        udf = nwb.units.to_dataframe()
        gt = nwb.intervals[table].to_dataframe()
        lfp = nwb.acquisition[CONTAINER]
        ts_start = np.asarray(lfp.electrical_series["probe_1_lfp_start"].timestamps[:], dtype=float)
        ts_end = np.asarray(lfp.electrical_series["probe_1_lfp_end"].timestamps[:], dtype=float)
        win_series = lfp.electrical_series[SERIES]
        ts_win = np.asarray(win_series.timestamps[:], dtype=float)
        win = np.asarray(win_series.data[:], dtype=float)
        region = np.asarray(win_series.electrodes.data[:], dtype=int)
        electrodes = nwb.electrodes.to_dataframe()
        obs = np.asarray(nwb.units["obs_intervals"][0], dtype=float)
        stored_rate = getattr(win_series, "rate", None)
        stored_start = getattr(win_series, "starting_time", None)
        ts_unit_label = getattr(win_series, "timestamps_unit", None)

    # Q1: units and the source quality label
    n_units = len(udf)
    quality_counts = Counter(udf["quality"].tolist())
    audit = jnwb.audit_units(udf, stable_labels=("good",))
    n_good = int(audit["quality_distribution"]["good_count"])
    assert n_good == quality_counts["good"], (n_good, quality_counts)
    assert n_units == sum(quality_counts.values())
    print(f"Q1: units={n_units}; quality 'good'={n_good} "
          f"(source labels {dict(quality_counts)}; no cut-off applied)")

    # Q2: sampling rate, derived from the file's timestamps and the units obs intervals (seconds)
    obs = obs[np.argsort(obs[:, 0])]
    onsets_all = gt["start_time"].to_numpy()
    mid = [i for i, row in enumerate(obs) if row[0] <= onsets_all[0] <= row[1]]
    assert len(mid) == 1, mid
    mid = mid[0]
    obs_start_len = obs[0, 1] - obs[0, 0]
    obs_end_len = obs[2, 1] - obs[2, 0]
    rate_start = len(ts_start) / obs_start_len
    rate_end = len(ts_end) / obs_end_len
    assert abs(rate_start - rate_end) < 1e-6, (rate_start, rate_end)
    rate = rate_start
    steps_start = np.unique(np.diff(ts_start))
    steps_win = np.unique(np.diff(ts_win))
    assert steps_start.size == 1 and steps_win.size == 1, (steps_start, steps_win)
    ticks_per_sample = float(steps_start[0])
    assert float(steps_win[0]) == ticks_per_sample
    ticks_per_s = ticks_per_sample * rate
    offset_start = obs[0, 0] - ts_start[0] / ticks_per_s
    offset_end = obs[2, 0] - ts_end[0] / ticks_per_s
    window_t0 = offset_start + ts_win[0] / ticks_per_s
    window_t1 = offset_start + ts_win[-1] / ticks_per_s
    window_pad_err = (window_t0 - (obs[mid, 0] - 0.5), window_t1 - (obs[mid, 1] + 0.5))
    print(f"Q2: stored rate {stored_rate!r}, starting_time {stored_start!r}; the series stores "
          f"timestamps labelled {ts_unit_label!r} that run to {ts_win[-1]:.0f}, i.e. 30 kHz ticks. "
          f"Derived {rate:.1f} Hz = {len(ts_start)} samples / {obs_start_len:.3f} s obs interval "
          f"(end segment {rate_end:.1f} Hz); {ticks_per_sample:.0f} ticks per sample at "
          f"{ticks_per_s:.0f} ticks/s")
    print(f"diag Q2: offset_start={offset_start:.6f} s, offset_end={offset_end:.6f} s, "
          f"drift={1e3 * (offset_end - offset_start):.2f} ms; window vs obs interval "
          f"{obs[mid, 0]:.5f}-{obs[mid, 1]:.5f} padded 0.5 s: err "
          f"{1e3 * window_pad_err[0]:.3f} / {1e3 * window_pad_err[1]:.3f} ms; "
          f"file time_unit {info['time_unit']!r}", file=sys.stderr)

    # Q3: grating rows, drawn gratings versus rows with no parameters
    param_vals = gt[PARAMS]
    drawn = param_vals.notna().all(axis=1).to_numpy()
    blank = param_vals.isna().all(axis=1).to_numpy()
    assert np.all(drawn ^ blank), "a row is neither fully drawn nor fully blank"
    ev = jnwb.events(PATH, table=table, code_column=None)
    assert np.allclose(ev.onsets, onsets_all), "events onsets differ from start_time"
    n_rows, n_drawn, n_blank = len(gt), int(drawn.sum()), int(blank.sum())
    names = Counter(gt["stimulus_name"].tolist())
    print(f"Q3: rows={n_rows}; drawn gratings={n_drawn} (orientation, contrast, spatial and temporal "
          f"frequency all set); {n_blank} rows with all four NaN; stimulus_name {dict(names)} "
          f"does not separate them")

    # Q4: high-gamma band change, drawn gratings only, per VISpm channel
    chan_rows = electrodes.iloc[region]
    chan_ids = chan_rows.index.to_numpy()
    chan_loc = chan_rows["location"].astype(str).tolist()
    cortical = [k for k, loc in enumerate(chan_loc) if loc.startswith("VISpm")]
    assert cortical, "no VISpm channel in the excerpt"
    onsets = onsets_all[drawn]
    results = []
    for k in cortical:
        ep_win, t_axis, _ = jnwb.epoch_continuous(
            win[:, k], onsets - window_t0, win_s=WIN_S, fs=rate, boundary_policy="error",
            return_indices=True)
        rom, mor, n = band_db(ep_win, t_axis, rate)
        results.append((chan_ids[k], chan_loc[k], rom, mor, n))
        # alternative clock: the window's first sample at the obs interval start
        alt_t0 = obs[mid, 0]
        ep_alt, t_alt, _ = jnwb.epoch_continuous(
            win[:, k], onsets - alt_t0, win_s=WIN_S, fs=rate, boundary_policy="error",
            return_indices=True)
        rom_alt, mor_alt, _ = band_db(ep_alt, t_alt, rate)
        print(f"diag Q4 ch{chan_ids[k]} {chan_loc[k]}: mean_of_ratios {mor:+.2f} dB; "
              f"alt-anchor ratio_of_means {rom_alt:+.2f} dB, mean_of_ratios {mor_alt:+.2f} dB",
              file=sys.stderr)
    q4_parts = "; ".join(f"{cid} {loc} {rom:+.2f}" for cid, loc, rom, _, _ in results)
    print(f"Q4: high gamma {HIGH_GAMMA[0]:.0f}-{HIGH_GAMMA[1]:.0f} Hz, ratio_of_means over "
          f"{results[0][4]} drawn gratings, post {POST_S} vs pre {PRE_S} s, dB per channel: "
          f"{q4_parts}")

    # Q5: refusals and warnings the skills gave on this file
    refusals = []
    for name in (CONTAINER, SERIES):
        try:
            jnwb.acquisition_channel(PATH, name=name, channel=0)
            refusals.append(f"acquisition_channel({name!r}) returned data")
        except Exception as exc:  # noqa: BLE001
            refusals.append(f"acquisition_channel({name!r}) -> {type(exc).__name__}")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            jnwb.events(PATH, table=table)
            refusals.append("events(default code_column='codes') -> no refusal")
        except Exception as exc:  # noqa: BLE001
            refusals.append(f"events(default code_column='codes') -> {type(exc).__name__}")
    n_warn = len(caught)
    print(f"Q5: refused: {'; '.join(refusals)}; events default warnings {n_warn}; "
          f"time_unit {info['time_unit']!r} conflicts with the tick-valued timestamps, so the rate "
          f"and offset come from the obs intervals; blank rows not named (no documented code); "
          f"quality is a source label, not a cut-off")


if __name__ == "__main__":
    main()
