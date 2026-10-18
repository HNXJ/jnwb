"""Measure the computational order of jnwb exports as a fitted exponent in one named parameter.

Each spec calls one export at four or five sizes spanning at least a decade of its parameter.
Per size: the inputs are built outside the timed region, one untimed warm-up call runs, then
``--repeats`` timed calls with garbage collection disabled; the median is kept. The exponent is
the least-squares slope of log(median) on log(size), and ``r2`` is that fit's coefficient of
determination. Raw medians are printed beside every exponent.

Method, as ``artifacts/evidence/0.2.6/computational_order.md`` section 2 states it:

* BLAS/OpenMP pools are pinned to one thread with ``threadpoolctl.threadpool_limits(1)``, and the
  pin is verified: setting ``OMP_NUM_THREADS`` alone left 24 threads live on the machine this was
  calibrated on, and thread parallelism that grows with size suppresses the exponent.
* Sweeps run serially. Two at once contend for cores and corrupt both.
* ``jnwb`` is imported from the checkout this script sits in, and that is asserted: a copy in
  site-packages would otherwise be timed silently.
* ``--calibrate`` runs workloads of exactly known order first, so the method error on this host
  is on the record beside the result.

Usage::

    python scripts/measure_order.py --list
    python scripts/measure_order.py "phase_slope_index[n_samples_jackknife]" --repeats 5
    python scripts/measure_order.py --calibrate --json out.json
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Sequence

import numpy as np
import threadpoolctl

ROOT = Path(__file__).resolve().parents[1]


def import_checkout_jnwb():
    """Import jnwb from this checkout, or refuse. Called by ``main``, never at import time.

    Importing this module must not touch ``sys.path``: a test that imports it while qualifying an
    installed jnwb would otherwise start timing, or testing, the checkout instead.
    """
    # Under JNWB_EXPECTED_PACKAGE_ROOT the checkout goes last, so the copy it names wins.
    if os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT"):
        if str(ROOT) not in sys.path:
            sys.path.append(str(ROOT))
    elif str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import jnwb

    expected = Path(os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") or ROOT).resolve()
    if expected not in Path(jnwb.__file__).resolve().parents:
        raise SystemExit(f"jnwb imported from {jnwb.__file__}, not from {expected}; refusing to time it")
    return jnwb


class Spec(NamedTuple):
    parameter: str
    sizes: Sequence[int]
    #: Pinned values of every other input, stated so the row can be read without the code.
    held: str
    #: size -> zero-argument callable. Everything it closes over is built before timing.
    build: Callable[[int, Path], Callable[[], object]]


def _psi(jackknife: bool) -> Callable[[int, Path], Callable[[], object]]:
    def build(n: int, _tmp: Path) -> Callable[[], object]:
        import jnwb

        rng = np.random.default_rng(0)
        x = rng.normal(size=n)
        y = np.roll(x, 5) + rng.normal(size=n)
        return lambda: jnwb.phase_slope_index(
            x, y, fs=1000.0, nperseg=256, jackknife=jackknife, n_surrogates=0
        )

    return build


def _npz(n_file: int, n_slice: int, at_end: bool, tmp: Path) -> Callable[[], object]:
    import jnwb

    path = tmp / f"stored_{n_file}.npz"
    if not path.exists():
        np.savez(path, a=np.random.default_rng(0).normal(size=n_file))
    lo = n_file - n_slice if at_end else 0
    sl = (slice(lo, lo + n_slice),)
    return lambda: jnwb.stream_npz_array(path, "a", slice_tuple=sl)


def _fleiss(n: int) -> Callable[[], object]:
    import jnwb

    table = np.random.default_rng(0).multinomial(6, [0.4, 0.2, 0.2, 0.1, 0.1], size=n)
    return lambda: jnwb.fleiss_kappa(table)


def _spiking(n_bins: int, which: str) -> Callable[[], object]:
    import jnwb

    rng = np.random.default_rng(0)
    end = n_bins / 1000.0
    units = [np.sort(rng.uniform(0.0, end, 2000)) for _ in range(8)]
    if which == "correlation":
        return lambda: jnwb.spike_count_correlation(units, (0.0, end), bin_ms=1.0)
    return lambda: jnwb.network_burst_index(units, (0.0, end), bin_ms=1.0, threshold_hz=5000.0,
                                            min_duration_ms=3.0)


def _curation(which: str, n: int) -> Callable[[], object]:
    import jnwb

    rng = np.random.default_rng(0)
    if which == "detect":
        data = rng.standard_normal((16, 1, n))
        return lambda: jnwb.detect_bad_channels(data, 500.0)
    if which == "interpolate":
        data = rng.standard_normal((n, 64))
        bad = np.zeros(n, dtype=bool)
        bad[2::5] = True
        return lambda: jnwb.interpolate_channel_runs(data, bad)
    if which == "csd":
        erp = rng.standard_normal((n, 200))
        times = np.arange(200, dtype=float) - 50.0
        return lambda: jnwb.evoked_csd_sink(erp, times, pitch_um=25.0)
    if which == "fuse":
        windows = rng.normal(600.0, 20.0, n)
        return lambda: jnwb.fuse_laminar_anchors(vflip_um=600.0, window_um=windows,
                                                 consistency_deep=0.9, consistency_superficial=0.9)
    lfp = rng.standard_normal((16, n, 500))
    return lambda: jnwb.curate_and_label(lfp, 500.0, pitch_um=25.0, compute_xflip=False)


def _fano(n_trials: int) -> Callable[[], object]:
    import jnwb

    rng = np.random.default_rng(0)
    onsets = np.arange(n_trials, dtype=float)
    units = [np.sort(rng.uniform(0.0, float(n_trials), 5 * n_trials)) for _ in range(8)]
    return lambda: jnwb.fano_factor(units, onsets, (0.0, 0.5), summary="mean")


def _trough(n: int) -> np.ndarray:
    """A (16, n) mean waveform: one trough of width n/20 at sample n/2, on channel 8 only."""
    t = np.arange(n, dtype=float)
    w = np.zeros((16, n))
    w[8] = -np.exp(-((t - n / 2) ** 2) / (2 * (n / 20) ** 2))
    return w


def _halfwidth(n: int, _tmp: Path) -> Callable[[], object]:
    from jnwb import unit_quality as uq

    w = _trough(n)
    assert np.isfinite(uq.waveform_halfwidth(w, 30_000.0)), "fixture must cross the half level"
    return lambda: uq.waveform_halfwidth(w, 30_000.0)


def _slope(n: int, _tmp: Path) -> Callable[[], object]:
    from jnwb import unit_quality as uq

    w = _trough(n)
    assert np.isfinite(uq.repolarization_slope(w, 30_000.0)), "fixture must leave a fit window"
    return lambda: uq.repolarization_slope(w, 30_000.0)


def _spread(n_channels: int, _tmp: Path) -> Callable[[], object]:
    from jnwb import unit_quality as uq

    scale = np.exp(-((np.arange(n_channels) - n_channels // 2) ** 2) / (2 * 4.0 ** 2))
    t = np.arange(60, dtype=float)
    w = scale[:, None] * (-np.exp(-((t - 20) ** 2) / (2 * 4.0 ** 2)))[None, :]
    assert np.isfinite(uq.waveform_spread(w, site_spacing_um=20.0)), "fixture must have sites"
    return lambda: uq.waveform_spread(w, site_spacing_um=20.0)


def _vflip2(n_channels: int, _tmp: Path) -> Callable[[], object]:
    """A probe with the spectrolaminar motif: gamma peaks a quarter down, alpha-beta at three quarters."""
    import jnwb

    freqs = np.arange(1, 151, dtype=float)
    depth = np.linspace(0.0, 1.0, n_channels)
    gamma = np.exp(-0.5 * ((depth - 0.25) / 0.12) ** 2)[:, None] * np.exp(-0.5 * ((freqs - 80) / 25) ** 2)
    beta = np.exp(-0.5 * ((depth - 0.75) / 0.12) ** 2)[:, None] * np.exp(-0.5 * ((freqs - 18) / 8) ** 2)
    psd = freqs ** -1.5 * (1.0 + 3.0 * (0.05 * gamma + beta))
    psd = psd * np.random.default_rng(0).lognormal(0.0, 0.05, psd.shape)
    assert jnwb.vflip2(psd, freqs, contact_spacing=100.0).omega is not None, "fixture must find a window"
    return lambda: jnwb.vflip2(psd, freqs, contact_spacing=100.0)


def _vflip2_from_lfp(n_samples: int, _tmp: Path) -> Callable[[], object]:
    """White-noise continuous LFP on 8 channels at 1000 Hz, cut into 1 s trials."""
    import jnwb

    lfp = np.random.default_rng(0).normal(size=(8, n_samples))
    assert isinstance(jnwb.vflip2_from_lfp(lfp[:, :1000], 1000, contact_spacing=100.0),
                      jnwb.VFlip2Result), "fixture must run"
    return lambda: jnwb.vflip2_from_lfp(lfp, 1000, contact_spacing=100.0)


def _cutoff(n: int, _tmp: Path) -> Callable[[], object]:
    from jnwb import unit_quality as uq

    amplitudes = np.random.default_rng(0).normal(size=n)
    assert 0.0 <= uq.amplitude_cutoff(amplitudes) <= 0.5, "fixture must give a cut-off"
    return lambda: uq.amplitude_cutoff(amplitudes)


SPECS: Dict[str, Spec] = {
    "phase_slope_index[n_samples]": Spec(
        "n_samples", (60_000, 200_000, 700_000, 2_000_000, 4_000_000),
        "1-D pair, fs=1000, nperseg=256, noverlap=128, bands=None, jackknife=False, n_surrogates=0",
        _psi(jackknife=False),
    ),
    "phase_slope_index[n_samples_jackknife]": Spec(
        "n_samples", (5_000, 12_000, 22_000, 35_000, 50_000),
        "1-D pair, fs=1000, nperseg=256, noverlap=128, bands=None, jackknife=True (default), "
        "n_surrogates=0",
        _psi(jackknife=True),
    ),
    "stream_npz_array[n_elements_in_file]": Spec(
        "n_elements_in_file", (100_000, 1_000_000, 4_000_000, 16_000_000),
        "float64, 1-D, ZIP_STORED (np.savez), the last 1000 elements",
        lambda n, tmp: _npz(n, 1000, True, tmp),
    ),
    "stream_npz_array[n_elements_sliced]": Spec(
        "n_elements_sliced", (1_000, 10_000, 100_000, 1_000_000, 4_000_000),
        "float64, 1-D, ZIP_STORED (np.savez), 4e6 elements in the file, the first k elements",
        lambda k, tmp: _npz(4_000_000, k, False, tmp),
    ),
    "fleiss_kappa[n_items]": Spec(
        "n_items", (10_000, 100_000, 1_000_000, 4_000_000),
        "5 categories, 6 raters per item, multinomial counts",
        lambda n, _tmp: _fleiss(n),
    ),
    "spike_count_correlation[n_bins]": Spec(
        "n_bins", (10_000, 100_000, 1_000_000, 4_000_000),
        "8 units, 2000 uniform spikes each, bin_ms=1, window (0, n_bins ms)",
        lambda n, _tmp: _spiking(n, "correlation"),
    ),
    "network_burst_index[n_bins]": Spec(
        "n_bins", (10_000, 100_000, 1_000_000, 4_000_000),
        "8 units, 2000 uniform spikes each, bin_ms=1, threshold_hz=5000, min_duration_ms=3",
        lambda n, _tmp: _spiking(n, "burst"),
    ),
    "fano_factor[n_trials]": Spec(
        "n_trials", (1_000, 10_000, 100_000, 1_000_000),
        "8 units, 5 uniform spikes per unit per 1 s trial, window (0, 0.5) s, summary='mean'",
        lambda n, _tmp: _fano(n),
    ),
    "detect_bad_channels[n_samples]": Spec(
        "n_samples", (10_000, 100_000, 1_000_000, 4_000_000),
        "16 contacts, 1 epoch, white noise, fs=500 Hz, defaults",
        lambda n, _tmp: _curation("detect", n),
    ),
    "interpolate_channel_runs[n_channels]": Spec(
        "n_channels", (1_000, 10_000, 100_000, 1_000_000),
        "64 trailing samples, every fifth contact bad (runs of 1), max_run=3",
        lambda n, _tmp: _curation("interpolate", n),
    ),
    "evoked_csd_sink[n_channels]": Spec(
        "n_channels", (100, 1_000, 10_000, 100_000),
        "200 time samples at 1 ms, white-noise potential, pitch_um=25, defaults",
        lambda n, _tmp: _curation("csd", n),
    ),
    "vflip2[n_channels]": Spec(
        "n_channels", (16, 32, 64, 160),
        "150 bins at 1 Hz, contact_spacing=100 um (window step 1, shortest window 6), motif probe",
        _vflip2,
    ),
    "vflip2_from_lfp[n_samples]": Spec(
        "n_samples", (100_000, 400_000, 1_600_000, 6_400_000),
        "8 channels of white noise at fs=1000 (1 s trials, 1024-point FFT), contact_spacing=100 um",
        _vflip2_from_lfp,
    ),
    "fuse_laminar_anchors[n_windows]": Spec(
        "n_windows", (1_000, 10_000, 100_000, 1_000_000),
        "vflip_um=600, windows N(600, 20), both consistencies 0.9, defaults",
        lambda n, _tmp: _curation("fuse", n),
    ),
    "curate_and_label[n_epochs]": Spec(
        "n_epochs", (8, 32, 128, 512),
        "16 contacts, 500 samples per epoch, white noise (grade F), fs=500 Hz, compute_xflip=False",
        lambda n, _tmp: _curation("curate", n),
    ),
    # Admissible bounds, read from the function bodies in jnwb/unit_quality.py. The n log n of
    # the two samples specs is the FFT of scipy.signal.resample over m = int(n * 200 / 82)
    # samples; the channel passes (isfinite, max, min) are O(C * n) with C = 16 fixed.
    "waveform_halfwidth[n_samples]": Spec(
        "n_samples", (1_000, 10_000, 100_000, 1_000_000),
        "16 channels, one trough of width n/20 at sample n/2 on channel 8 only, fs=30000, "
        "upsampling_factor=200/82 (default); admissible O(n log n)",
        _halfwidth,
    ),
    "repolarization_slope[n_samples]": Spec(
        "n_samples", (1_000, 10_000, 100_000, 1_000_000),
        "as waveform_halfwidth, window_samples=20 (default); the fit is a constant 20 samples, "
        "so admissible O(n log n)",
        _slope,
    ),
    # The sites are a fixed set of 17 channels (site_range 16, site_step 2), so the only term
    # that grows is the channel passes over C * n with n = 60 held: admissible O(C).
    "waveform_spread[n_channels]": Spec(
        "n_channels", (100, 1_000, 10_000, 100_000),
        "60 samples, trough at sample 20 (width 4), channel scale Gaussian centred on the middle "
        "channel (width 4), site_spacing_um=20, defaults; admissible O(C)",
        _spread,
    ),
    # One pass over the amplitudes (asarray, isfinite, np.histogram with 500 uniform bins); the
    # smoothing and the search run over 500 bins whatever N is: admissible O(N).
    "amplitude_cutoff[n_amplitudes]": Spec(
        "n_amplitudes", (100_000, 1_000_000, 4_000_000, 10_000_000),
        "standard normal amplitudes, default_rng(0), num_histogram_bins=500, "
        "histogram_smoothing_value=3 (defaults); admissible O(N)",
        _cutoff,
    ),
}


def _py_double_loop(n: int, _tmp: Path) -> Callable[[], object]:
    def run() -> int:
        s = 0
        for i in range(n):
            for j in range(n):
                s += i ^ j
        return s

    return run


def _matmul(n: int, _tmp: Path) -> Callable[[], object]:
    a = np.random.default_rng(0).normal(size=(n, n))
    return lambda: a @ a


def _add(n: int, _tmp: Path) -> Callable[[], object]:
    a = np.random.default_rng(0).normal(size=n)
    return lambda: np.add(a, a)


#: Workloads whose order is known exactly; the fitted error on them bounds the method error.
CALIBRATION: Dict[str, tuple] = {
    # Starts above 1e6: below it the operands sit in cache and the per-element cost is lower.
    "np.add": (1.0, Spec("n", (1_000_000, 3_000_000, 10_000_000, 30_000_000), "float64", _add)),
    "python double loop": (2.0, Spec("n", (100, 300, 1000), "int xor", _py_double_loop)),
    "np.matmul": (3.0, Spec("n", (200, 400, 1000, 2048), "float64 square", _matmul)),
}


def pin_threads() -> threadpoolctl.threadpool_limits:
    limiter = threadpoolctl.threadpool_limits(limits=1)
    live = [p for p in threadpoolctl.threadpool_info() if p.get("num_threads") != 1]
    if live:
        raise SystemExit(f"thread pools still unpinned after threadpool_limits(1): {live}")
    return limiter


def time_call(fn: Callable[[], object], repeats: int) -> float:
    fn()
    samples = []
    for _ in range(repeats):
        gc.disable()
        try:
            t0 = time.perf_counter()
            fn()
            samples.append(time.perf_counter() - t0)
        finally:
            gc.enable()
    return statistics.median(samples)


def fit(sizes: Sequence[int], medians: Sequence[float]) -> Dict[str, float]:
    lx = np.log(np.asarray(sizes, dtype=float))
    ly = np.log(np.asarray(medians, dtype=float))
    slope, intercept = np.polyfit(lx, ly, 1)
    resid = ly - (slope * lx + intercept)
    ss_tot = float(np.sum((ly - ly.mean()) ** 2))
    r2 = 1.0 - float(np.sum(resid**2)) / ss_tot if ss_tot > 0 else float("nan")
    return {"exp": float(slope), "r2": r2, "t_span": float(max(medians) / min(medians))}


def sweep(name: str, spec: Spec, repeats: int, sizes: Sequence[int] | None, tmp: Path) -> Dict:
    sizes = tuple(sizes or spec.sizes)
    if max(sizes) < 10 * min(sizes):
        raise SystemExit(f"{name}: sizes {sizes} span less than a decade")
    medians = []
    for n in sizes:
        fn = spec.build(n, tmp)
        medians.append(time_call(fn, repeats))
        del fn
    row = {"spec": name, "parameter": spec.parameter, "held": spec.held,
           "sizes": list(sizes), "median_s": medians, "repeats": repeats}
    row.update(fit(sizes, medians))
    return row


def markdown(row: Dict) -> str:
    ms = ", ".join(f"{1e3 * t:.4g}" for t in row["median_s"])
    sizes = ", ".join(str(s) for s in row["sizes"])
    return (f"| `{row['spec']}` | {row['parameter']} | {sizes} | {ms} | {row['exp']:+.2f} | "
            f"{row['r2']:.3f} | {row['t_span']:.0f}x |")


def provenance(jnwb) -> Dict[str, object]:
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain",
                                     "--untracked-files=no"], capture_output=True, text=True,
                                    check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        head, dirty = "unknown", None
    return {
        "commit": head, "tracked_changes": dirty, "jnwb_file": jnwb.__file__,
        "python": sys.version.split()[0], "numpy": np.__version__,
        "machine": platform.machine(), "processor": platform.processor(),
        "platform": platform.platform(), "logical_cpus": os.cpu_count(),
        "thread_pools": [(p.get("internal_api"), p.get("num_threads"))
                         for p in threadpoolctl.threadpool_info()],
        "timing": "median of repeats after one untimed warm-up, gc disabled, perf_counter",
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("specs", nargs="*", help="spec names; default: all")
    ap.add_argument("--list", action="store_true", help="print the spec names and exit")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--sizes", type=lambda s: [int(float(v)) for v in s.split(",")],
                    help="comma-separated size ladder overriding the spec's")
    ap.add_argument("--calibrate", action="store_true", help="run the known-order workloads first")
    ap.add_argument("--json", type=Path, help="also write every row and the provenance here")
    args = ap.parse_args(argv)

    jnwb = import_checkout_jnwb()
    if args.list:
        print(f"jnwb: {jnwb.__file__}")
        for name, spec in SPECS.items():
            print(f"{name}: {spec.held}")
        return 0
    unknown = [s for s in args.specs if s not in SPECS]
    if unknown:
        ap.error(f"unknown spec(s) {unknown}; see --list")

    limiter = pin_threads()
    try:
        prov = provenance(jnwb)
        print(json.dumps(prov, indent=1))
        rows: List[Dict] = []
        with tempfile.TemporaryDirectory() as tmp:
            if args.calibrate:
                for name, (true_order, spec) in CALIBRATION.items():
                    row = sweep(name, spec, args.repeats, None, Path(tmp))
                    row["true_order"] = true_order
                    rows.append(row)
                    print(f"calibration {name}: true {true_order:+.2f}, fitted {row['exp']:+.2f}, "
                          f"error {abs(row['exp'] - true_order):.2f}")
            for name in args.specs or list(SPECS):
                row = sweep(name, SPECS[name], args.repeats, args.sizes, Path(tmp))
                rows.append(row)
                print(markdown(row))
                sys.stdout.flush()
    finally:
        limiter.restore_original_limits()
    if args.json:
        args.json.write_text(json.dumps({"provenance": prov, "rows": rows}, indent=1),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
