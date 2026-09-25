"""Tutorial 09: Open data end to end -- inspect, derive the clock, analyze, verify, plot.

Run: python examples/tutorials/09_open_data.py [figure_dir]

Reads `examples/data/dandi000253_excerpt.nwb`, a committed excerpt of DANDI 000253 (Allen
Institute OpenScope, Global/Local Oddball project, CC-BY-4.0,
https://doi.org/10.48324/dandi.000253/0.240503.0152), built from the published assets by
`scripts/build_open_data_excerpt.py`. The figure is written to `figure_dir` when one is given.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# This file is run from a checkout, so prefer that checkout over any installed jnwb:
# Python puts this directory on sys.path, not the repository root. A run that is
# deliberately qualifying an installed copy says so with JNWB_EXPECTED_PACKAGE_ROOT,
# and then this guard stands aside.
_CHECKOUT = Path(__file__).resolve().parents[2]
if not os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") and (
    _CHECKOUT / "jnwb" / "__init__.py"
).exists():
    sys.path.insert(0, str(_CHECKOUT))

import jnwb

EXCERPT = _CHECKOUT / "examples" / "data" / "dandi000253_excerpt.nwb"
PROVENANCE = EXCERPT.with_name("dandi000253_excerpt.provenance.json")

LFP_CONTAINER = "probe_1_lfp"
SEGMENTS = ("start", "window", "end")      # series probe_1_lfp_<segment>
GRATINGS = "init_grating_presentations"
CORTEX = "VISpm"                           # location prefix of the cortical contacts

# The offset of the LFP clock is known to +-10 ms (see the page). Every check below is held to
# that bound, and nothing here reads an LFP latency finer than it.
OFFSET_BOUND_S = 0.010
XCORR_MAX_LAG_S = 0.050

PSTH_WIN_MS = (-250.0, 750.0)
BIN_MS = 10.0
BASELINE_MS = (-100.0, 0.0)
RESPONSE_MS = (30.0, 130.0)
BAND = jnwb.CANONICAL_BANDS["high_gamma"]
PRE_S = (-0.45, -0.05)                     # gray screen before the grating
POST_S = (0.05, 0.45)                      # grating on screen


class ClockCheckError(RuntimeError):
    """The derived LFP clock disagrees with the spikes by more than the stated bound."""


@dataclass(frozen=True)
class Clock:
    """Map from LFP timestamp ticks to seconds on the spike clock, derived from the file."""

    tick_step: float      # ticks between consecutive LFP samples
    tick_rate: float      # ticks per second of the spike clock
    first_tick: float     # timestamp of the recording's first LFP sample
    offset_s: float       # spike-clock time of that sample

    @property
    def fs_hz(self) -> float:
        return self.tick_rate / self.tick_step

    def seconds(self, ticks) -> np.ndarray:
        return self.offset_s + (np.asarray(ticks, dtype=np.float64) - self.first_tick) / self.tick_rate


def read_excerpt(path: Path) -> dict:
    """Everything the analysis needs, as plain arrays, read in one pass."""
    from pynwb import NWBHDF5IO

    with NWBHDF5IO(str(path), "r") as io:
        nwb = io.read()
        electrodes = nwb.electrodes.to_dataframe()
        units = nwb.units.to_dataframe()
        container = nwb.acquisition[LFP_CONTAINER]
        lfp = {}
        for name in SEGMENTS:
            series = container.electrical_series[f"{LFP_CONTAINER}_{name}"]
            lfp[name] = {
                "data": np.asarray(series.data[:], dtype=np.float64) * series.conversion,
                "ticks": np.asarray(series.timestamps[:], dtype=np.float64),
                "timestamps_unit": series.timestamps_unit,
                "rate": series.rate,
            }
        channel_ids = np.asarray(container.electrical_series[f"{LFP_CONTAINER}_window"]
                                 .electrodes.to_dataframe().index)
    return {
        "electrodes": electrodes,
        "trains": [np.asarray(t, dtype=np.float64) for t in units["spike_times"]],
        "obs_intervals": [np.asarray(o, dtype=np.float64) for o in units["obs_intervals"]],
        "peak_channel_id": units["peak_channel_id"].to_numpy(),
        "quality": units["quality"].astype(str).to_numpy(),
        "lfp": lfp,
        "channel_ids": channel_ids,
    }


def derive_clock(lfp: dict, trains: list) -> Clock:
    """Tick step from the timestamps; tick rate from the recording's span on both clocks.

    The LFP timestamps are integer ticks labeled seconds. The start and end series hold the
    recording's first and last LFP sample, and the spikes include the probe's first and last
    spike, so both spans cover the whole session and neither depends on how the excerpt was cut.
    """
    steps = {float(s) for seg in lfp.values() for s in np.unique(np.diff(seg["ticks"]))}
    if len(steps) != 1:
        raise ClockCheckError(f"LFP timestamps are not uniformly stepped: {sorted(steps)[:5]}")
    tick_step = steps.pop()
    first_tick = float(lfp["start"]["ticks"][0])
    tick_span = float(lfp["end"]["ticks"][-1]) - first_tick
    spikes = np.concatenate([t for t in trains if t.size])
    first_spike, last_spike = float(spikes.min()), float(spikes.max())
    return Clock(
        tick_step=tick_step,
        tick_rate=tick_span / (last_spike - first_spike),
        first_tick=first_tick,
        offset_s=first_spike,   # the recording starts within a millisecond of its first spike
    )


def xcorr_lag(trace: np.ndarray, times_s: np.ndarray, spikes: np.ndarray, fs: float) -> tuple:
    """Lag (s) of the extreme spike-count x LFP correlation within +-XCORR_MAX_LAG_S.

    A positive lag means the LFP sample carrying the coupling sits later than `times_s` says.
    """
    edges = np.r_[times_s, times_s[-1] + 1.0 / fs] - 0.5 / fs
    counts = np.histogram(spikes, bins=edges)[0].astype(np.float64)
    c = (counts - counts.mean()) / counts.std()
    x = (trace - trace.mean()) / trace.std()
    m = int(round(XCORR_MAX_LAG_S * fs))
    n = x.size
    lags = np.arange(-m, m + 1)
    r = np.array([np.mean(c[max(0, k):n + min(0, k)] * x[max(0, -k):n - max(0, k)]) for k in lags])
    best = int(np.argmax(np.abs(r)))
    return lags[best] / fs, float(r[best])


def check_clock(clock: Clock, data: dict, good: np.ndarray) -> dict:
    """Refine the offset by spike-LFP cross-correlation in all three segments.

    The coupling channel is the one with the strongest correlation in the analysis window; the
    same channel is then used at the start and end of the recording. Agreement of the three lags
    within the bound checks the offset and, because they sit 9000 s apart, the tick rate.
    """
    spikes = np.sort(np.concatenate([t for t, g in zip(data["trains"], good) if g]))
    window = data["lfp"]["window"]
    t_win = clock.seconds(window["ticks"])
    per_channel = [xcorr_lag(window["data"][:, j], t_win, spikes, clock.fs_hz)
                   for j in range(window["data"].shape[1])]
    channel = int(np.argmax([abs(r) for _, r in per_channel]))
    lags = {}
    for name in SEGMENTS:
        seg = data["lfp"][name]
        lags[name] = xcorr_lag(seg["data"][:, channel], clock.seconds(seg["ticks"]), spikes,
                               clock.fs_hz)
    worst = max(abs(lag) for lag, _ in lags.values())
    if worst > OFFSET_BOUND_S:
        raise ClockCheckError(
            f"spike-LFP lag {worst * 1e3:.1f} ms exceeds the {OFFSET_BOUND_S * 1e3:.0f} ms bound "
            f"(lags {', '.join(f'{k} {v[0] * 1e3:+.1f} ms' for k, v in lags.items())})"
        )
    return {"channel_id": int(data["channel_ids"][channel]), "lags_s": lags}


def location_of(peak_channel_id, electrodes) -> str:
    # A join on the electrode id. The locations here are atlas labels such as 'VISpm2/3',
    # which name one layer. jnwb.map_peak_channel_to_area keeps such a label whole but still
    # splits a label such as 'VISp6a/b', so a plain join is used for these labels.
    return str(electrodes.loc[int(peak_channel_id), "location"])


def psth_by_layer(data: dict, onsets: np.ndarray, good: np.ndarray) -> dict:
    lo_s = onsets.min() + PSTH_WIN_MS[0] / 1e3
    hi_s = onsets.max() + PSTH_WIN_MS[1] / 1e3
    layers: dict = {}
    for train, obs, pk, g in zip(data["trains"], data["obs_intervals"], data["peak_channel_id"], good):
        where = location_of(pk, data["electrodes"])
        if not (g and where.startswith(CORTEX)):
            continue
        # An excerpt keeps spikes only inside its observation intervals. A PSTH over time the
        # unit was not observed would read the gap as silence.
        if not any(a <= lo_s and hi_s <= b for a, b in obs):
            raise ValueError(f"PSTH window [{lo_s:.2f}, {hi_s:.2f}] s is outside {obs.tolist()}")
        t_ms, rate, _ = jnwb.raster_psth(train, onsets, win_ms=PSTH_WIN_MS, bin_ms=BIN_MS)
        layers.setdefault(where, []).append(rate)
    out = {}
    base = (t_ms >= BASELINE_MS[0]) & (t_ms < BASELINE_MS[1])
    resp = (t_ms >= RESPONSE_MS[0]) & (t_ms < RESPONSE_MS[1])
    for where, rates in sorted(layers.items()):
        mean = np.mean(rates, axis=0)
        out[where] = {"n_units": len(rates), "rate_hz": mean,
                      "baseline_hz": float(mean[base].mean()),
                      "response_hz": float(mean[resp].mean())}
    return {"t_ms": t_ms, "layers": out}


def band_power_by_channel(data: dict, clock: Clock, onsets: np.ndarray) -> dict:
    window = data["lfp"]["window"]
    t0 = float(clock.seconds(window["ticks"][:1])[0])
    local = onsets - t0                    # seconds from the segment's first sample
    powers = {}
    for name, win in (("pre", PRE_S), ("post", POST_S)):
        epochs, _ = jnwb.epoch_continuous(window["data"], local, win_s=win, fs=clock.fs_hz,
                                          boundary_policy="error")
        powers[name] = np.array([[jnwb.band_power(epochs[i, :, j], fs=clock.fs_hz,
                                                  freq_range=BAND, normalize=False)
                                  for j in range(epochs.shape[2])]
                                 for i in range(epochs.shape[0])])
        n_samples = epochs.shape[1]
    # Trial-averaged power over trial-averaged baseline, per channel; decibels taken once.
    db = jnwb.aggregate_to_db(powers["post"], powers["pre"], how="ratio_of_means",
                              aggregate_over=0)
    el = data["electrodes"].loc[data["channel_ids"]]
    return {"db": np.asarray(db), "channel_ids": data["channel_ids"],
            "location": el["location"].astype(str).to_numpy(),
            "depth_um": el["probe_vertical_position"].to_numpy(dtype=float),
            "epoch_n_samples": int(n_samples), "n_trials": int(powers["post"].shape[0])}


def analyze(path: Path = EXCERPT) -> dict:
    data = read_excerpt(path)
    good = data["quality"] == "good"
    clock = derive_clock(data["lfp"], data["trains"])
    check = check_clock(clock, data, good)

    events = jnwb.events(path, table=GRATINGS, code_column="orientation")
    orientation = np.asarray(events.codes, dtype=np.float64)
    onsets = events.onsets[np.isfinite(orientation)]   # NaN rows: no grating was drawn

    return {
        "clock": clock,
        "check": check,
        "n_units": len(data["trains"]),
        "n_good": int(good.sum()),
        "n_onsets": int(onsets.size),
        "n_rows": int(orientation.size),
        "last_tick": float(data["lfp"]["end"]["ticks"][-1]),
        "timestamps_unit": data["lfp"]["window"]["timestamps_unit"],
        "stored_rate": data["lfp"]["window"]["rate"],
        "psth": psth_by_layer(data, onsets, good),
        "lfp": band_power_by_channel(data, clock, onsets),
    }


def plot(res: dict, out_dir: Path) -> list:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    jnwb.setup_vector_graphics()
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]   # fixed categorical order
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(9.0, 3.6), constrained_layout=True)
    t_ms = res["psth"]["t_ms"]
    for color, (where, layer) in zip(colors, res["psth"]["layers"].items()):
        label = f"{where} (n={layer['n_units']})"
        ax_a.plot(t_ms, layer["rate_hz"], color=color, lw=2, label=label)
        ax_a.annotate(where, (t_ms[-1], layer["rate_hz"][-1]), xytext=(4, 0),
                      textcoords="offset points", va="center", fontsize=8, color="#333333")
    ax_a.axvspan(0, 500, color="#e8e8e8", zorder=0, lw=0)
    ax_a.set(xlabel="Time from grating onset (ms)", ylabel="Rate (Hz)",
             title="A  PSTH of good units by layer")
    ax_a.legend(frameon=False, fontsize=8, loc="upper left")
    lf = res["lfp"]
    ax_b.plot(lf["db"], lf["depth_um"], color=colors[0], lw=2, marker="o", ms=5)
    for db, depth, where in zip(lf["db"], lf["depth_um"], lf["location"]):
        ax_b.annotate(where, (db, depth), xytext=(6, 0), textcoords="offset points",
                      va="center", fontsize=8, color="#333333")
    ax_b.axvline(0.0, color="#999999", lw=1)
    ax_b.set(xlabel=f"{BAND[0]:.0f}-{BAND[1]:.0f} Hz power, grating vs gray (dB)",
             ylabel="Contact position on probe (µm)", title="B  LFP band power by depth")
    for ax in (ax_a, ax_b):
        ax.spines[["top", "right"]].set_visible(False)
    jnwb.save_figure_suite([fig], out_dir, "09_open_data", dpi=150, formats=["png"])
    plt.close(fig)
    return sorted(Path(out_dir).glob("09_open_data_page*.png"))


def main() -> None:
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    ds = provenance["dandiset"]
    print(f"Data: {ds['name']}, {ds['identifier']} v{ds['version']}, {ds['license']}")
    print(f"Cite: https://doi.org/{ds['doi']}")

    # 1. Inspect before selecting. The LFP container holds three series and reports no rate,
    #    because the file stores timestamps rather than a sampling rate.
    info = jnwb.inspect(EXCERPT)
    for acq in info["acquisitions"]:
        print(f"Continuous: {acq['name']} series={acq['series']} rate_hz={acq['rate_hz']}")
    print(f"Units: {info['units']['n_rows']} rows; interval tables: "
          f"{[t['name'] for t in info['interval_tables']]}")

    res = analyze(EXCERPT)
    clock = res["clock"]

    # 2. The clock, derived from the file.
    print(f"LFP timestamps are labeled '{res['timestamps_unit']}', stored rate={res['stored_rate']}, "
          f"step {clock.tick_step:g} per sample")
    print(f"Tick rate {clock.tick_rate:.3f} per s; LFP rate {clock.fs_hz:.4f} Hz; "
          f"first sample at {clock.offset_s:.4f} s")
    for name, (lag, r) in res["check"]["lags_s"].items():
        print(f"  spike-LFP lag in {name} segment: {lag * 1e3:+.1f} ms (r={r:+.3f}, "
              f"electrode {res['check']['channel_id']})")
    declared = provenance["source_values"]["declared_rates_hz"]["electrode_group_lfp_sampling_rate_hz"]
    last_sample = (res["last_tick"] - clock.first_tick) / clock.tick_step
    drift_ms = last_sample * (1.0 / declared - 1.0 / clock.fs_hz) * 1e3
    print(f"The source metadata declares {declared:g} Hz; at that rate the last sample would sit "
          f"{abs(drift_ms):.1f} ms {'earlier' if drift_ms < 0 else 'later'} than the derived "
          f"clock puts it")

    # 3. Verify, then report.
    layers = res["psth"]["layers"]
    assert layers, "no good cortical units in the excerpt"
    for where, layer in layers.items():
        print(f"{where:>9}: {layer['n_units']:3d} units, baseline {layer['baseline_hz']:.2f} Hz, "
              f"response {layer['response_hz']:.2f} Hz")
    pooled_base = sum(v["baseline_hz"] * v["n_units"] for v in layers.values())
    pooled_resp = sum(v["response_hz"] * v["n_units"] for v in layers.values())
    assert pooled_resp > pooled_base, "cortical units do not respond to the gratings"
    lf = res["lfp"]
    assert np.all(np.isfinite(lf["db"])), "band power is not finite"
    for cid, where, db in zip(lf["channel_ids"], lf["location"], lf["db"]):
        print(f"  electrode {cid} {where:>9}: {db:+.2f} dB")
    print(f"{res['n_onsets']} grating onsets of {res['n_rows']} rows; "
          f"{lf['n_trials']} trials x {lf['epoch_n_samples']} samples per LFP epoch")

    # 4. Plot.
    if len(sys.argv) > 1:
        paths = plot(res, Path(sys.argv[1]))
        print(f"Figure: {[str(p) for p in paths]}")
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = plot(res, Path(tmpdir))
            assert paths, "no figure was written"
            print("Figure rendered; pass a directory to keep it")


if __name__ == "__main__":
    main()
