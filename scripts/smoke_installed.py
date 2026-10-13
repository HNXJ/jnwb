"""Smoke-test an installed jnwb: the version, the exports, and a few representative calls.

Run it with the interpreter of the environment under test, from outside the checkout, so that
``import jnwb`` resolves to the installed package:

    python /path/to/scripts/smoke_installed.py --expected-version 0.2.7 --not-under "$GITHUB_WORKSPACE"

The package is expected without extras: an optional submodule must name its extra rather than
resolve. That exports check comes after the location checks, so the suite can run this script
against the checkout and see every workflow check before the refusal. Exits non-zero on the first
failed check.
"""
from __future__ import annotations

import argparse
import pathlib
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--expected-version", required=True,
                        help="the version the installed package must report, exactly")
    parser.add_argument("--not-under", type=pathlib.Path, default=None,
                        help="a directory the imported package must not be inside (the checkout)")
    args = parser.parse_args(argv)

    cwd = pathlib.Path.cwd()
    assert "jnwb" not in cwd.name, f"CWD must be outside repository, got {cwd}"

    try:
        import omission  # noqa: F401
    except ModuleNotFoundError:
        print("PASS: omission is strictly absent and unimportable")
    else:
        raise RuntimeError("omission is unexpectedly importable!")

    import jnwb

    location = pathlib.Path(jnwb.__file__).resolve()
    print("Installed jnwb version:", jnwb.__version__)
    print("Installed location:", location)
    if jnwb.__version__ != args.expected_version:
        raise SystemExit(f"FAIL: installed jnwb is {jnwb.__version__}, expected "
                         f"{args.expected_version}")
    # Representative installed-package workflows across modules.
    import tempfile

    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(42)
    st = np.sort(rng.uniform(0, 10, 50))
    onsets = np.array([1.0, 3.0, 5.0, 7.0])
    tb, rate, sem = jnwb.raster_psth(st, onsets, win_ms=(-100, 300), bin_ms=10.0)
    smooth = jnwb.causal_exp_smooth(rate, bin_ms=10.0, tau_ms=30.0)
    fit = jnwb.fit_exponential_onset(tb, rate, t0_bounds=(0.0, 200.0))
    assert 't0' in fit and 'bound_status' in fit
    ppc = jnwb.pairwise_phase_consistency(rng.uniform(-np.pi, np.pi, 30))
    assert np.isfinite(ppc)
    gs = jnwb.gaussian_smooth_rate(rate, bin_ms=10.0, sigma_ms=20.0)
    assert gs.shape == rate.shape

    # Spectral and time-frequency
    sig = rng.normal(size=1000)
    freq_grid = np.linspace(10.0, 50.0, 9)
    tfr_res = jnwb.complex_tfr(sig, fs=1000.0, freqs=freq_grid, n_cycles=5.0)
    acc = jnwb.TFRAccumulator((1, len(freq_grid), 1000))
    acc.add_trial(tfr_res.z[None, :, :], valid=tfr_res.coi_mask[None, :, :])
    assert acc.power().shape == (1, 9, 1000)
    mt_f, mt_p = jnwb.compute_multitaper_psd(sig, fs=1000.0)
    assert len(mt_f) == len(mt_p)
    filt = jnwb.bandpass_filter(sig, fs=1000.0, low_cut=8.0, high_cut=40.0)
    assert filt.shape == sig.shape
    lfp = rng.normal(size=(6, 200))
    csd = jnwb.current_source_density_1d(lfp, pitch_um=50.0, conductivity_s_per_m=0.3)
    assert csd.shape == (4, 200)

    # Statistics, decoding, connectivity and artifact
    boot = jnwb.StatisticalAnalysis.bootstrap_ci(sig, n_bootstrap=100, rng=rng)
    labels = np.array(['A', 'B', 'A', 'B'])
    shuf = jnwb.permute_labels(labels, scheme='global', rng=rng)
    X = rng.normal(size=(20, 4))
    y = np.repeat([0, 1], 10)
    dec = jnwb.nested_cv_linear_svm(X, y, n_splits=2)
    g_res = jnwb.granger(rng.normal(size=300), rng.normal(size=300), order=2, n_surrogates=5, seed=0)
    corr = jnwb.channel_correlation_matrix(rng.normal(size=(8, 200)))
    rep_lfp, frac, diag = jnwb.repair_lfp_trials(rng.normal(size=(8, 4, 100)))
    clust = jnwb.cluster_permutation_test(
        rng.normal(size=(8, 20)), rng.normal(size=(8, 20)), n_permutations=20, rng=rng,
    )
    masks = [c['mask'].tobytes() for c in clust['clusters']]
    assert len(masks) == len(set(masks))

    # Addressing
    elec = pd.DataFrame({'location': ['V1, V2', 'V1, V2'], 'group_name': ['probeA', 'probeA']},
                        index=[0, 1])
    assert jnwb.map_peak_channel_to_area(0, elec) == 'V1'

    # NWB discovery, processing LFP, calibration and epoching (0.1.8 contract)
    from jnwb.testing.nwb_fixtures import (
        CODE_LABEL_A,
        TASK_TABLE,
        canonical_co_resident_options,
        processing_lfp_options,
        write_synth_nwb,
    )
    nwb_path = pathlib.Path(tempfile.mkdtemp()) / 'wheel_smoke.nwb'
    receipt = write_synth_nwb(nwb_path, canonical_co_resident_options())
    info = jnwb.inspect(nwb_path)
    assert any(t['name'] == TASK_TABLE for t in info['interval_tables'])
    onsets = jnwb.event_onsets(nwb_path, table=TASK_TABLE, codes=[CODE_LABEL_A])
    assert onsets.size == len(receipt.task_onsets_s[::2])
    spikes = jnwb.unit_spike_times(nwb_path, unit_index=0)
    lfp, fs_hz = jnwb.acquisition_channel(nwb_path, name='probe_0_lfp', channel=0)
    assert spikes.size > 0 and lfp.size > 0 and fs_hz == receipt.fs_hz

    # Processing-module LFP discovery and calibrated access
    proc_nwb_path = pathlib.Path(tempfile.mkdtemp()) / 'wheel_proc.nwb'
    proc_receipt = write_synth_nwb(proc_nwb_path, processing_lfp_options())
    proc_info = jnwb.inspect(proc_nwb_path)
    assert len(proc_info['processing_continuous']) > 0
    assert any(p['neurodata_type'] == 'LFP' for p in proc_info['processing_continuous'])
    proc_lfp, proc_fs = jnwb.acquisition_channel(proc_nwb_path, channel=0)
    assert proc_lfp.size > 0 and proc_fs == proc_receipt.fs_hz

    # epoch_continuous primitive and the retained indices of a dropped boundary
    epochs, t_axis, retained = jnwb.epoch_continuous(
        proc_lfp,
        onsets=[0.1, 0.5, 999.0],
        win_s=(-0.05, 0.1),
        fs=proc_fs,
        boundary_policy='drop',
        return_indices=True,
    )
    assert epochs.ndim == 2
    assert epochs.shape[0] == 2
    assert np.array_equal(retained, [0, 1])
    assert len(t_axis) == epochs.shape[1]

    # 0.2.1 additions: aperiodic_fit, relative_power, exact statistics, stream_npz_array, probe_geometry
    f_axis = np.linspace(5.0, 50.0, 46)
    psd_toy = 10.0 ** (2.0 - 1.5 * np.log10(f_axis))
    ap_res = jnwb.aperiodic_fit(f_axis, psd_toy, freq_range=(5.0, 50.0), mode="fixed")
    assert ap_res.accepted is True and np.isclose(ap_res.exponent, 1.5, atol=1e-3)
    rp = jnwb.relative_power(psd_toy * 1.5, psd_toy, model="mean_of_ratios", axis=0)
    assert np.isclose(rp, 1.5)
    obs_m, p_val, p_fl = jnwb.exact_sign_flip([1.0, 2.0, 3.0, 4.0], alternative="greater")
    assert np.isclose(p_val, 0.0625) and np.isclose(p_fl, 0.0625)
    mwp_fl = jnwb.mann_whitney_p_floor(3, 3, alternative="two-sided")
    assert np.isclose(mwp_fl, 0.1)
    cp_ci = jnwb.clopper_pearson(5, 10, alpha=0.05)
    assert len(cp_ci) == 2
    tmp_npz = pathlib.Path(tempfile.mkdtemp()) / 'test_stream.npz'
    arr_raw = np.arange(100, dtype=np.float32).reshape(10, 10)
    np.savez_compressed(tmp_npz, arr=arr_raw)
    streamed = jnwb.stream_npz_array(tmp_npz, 'arr', (slice(0, 5), slice(0, 5)))
    assert np.array_equal(streamed, arr_raw[0:5, 0:5])
    coords_df = pd.DataFrame({'x': [0, 0, 0, 0], 'y': [0, 0, 0, 0], 'z': [0, 20, 40, 60]})
    p_geom = jnwb.probe_geometry(coords_df, units="um", nominal_pitch=20.0, strict_linear=True)
    assert p_geom.is_linear is True and p_geom.is_uniform is True

    # 0.2.4 additions: wpli, zflip, rdm. `wpli` returns a dict, so check its keys and contracts.
    wpli_res = jnwb.wpli(sig[:500], sig[500:], fs=1000.0, freq_range=(10.0, 40.0))
    assert set(wpli_res) == {'wpli', 'wpli_debiased_sq', 'freqs', 'wpli_spectrum', 'n_segments',
                             'n_freqs', 'device_used'}
    assert wpli_res['device_used'] == 'cpu', wpli_res['device_used']
    assert 0.0 <= wpli_res['wpli'] <= 1.0, wpli_res['wpli']
    assert -1.0 <= wpli_res['wpli_debiased_sq'] <= 1.0, wpli_res['wpli_debiased_sq']
    assert wpli_res['freqs'].shape == wpli_res['wpli_spectrum'].shape
    assert 1 <= wpli_res['n_freqs'] <= wpli_res['freqs'].size
    assert wpli_res['n_segments'] >= 2
    zflip_res = jnwb.zflip(rng.normal(size=(8, 1000)), fs=1000.0,
                           orientation="superficial_to_deep", pitch_um=20.0,
                           freq_range=(15.0, 35.0), seed=42)
    assert isinstance(zflip_res.delay_identifiable, bool) and isinstance(zflip_res.accepted, bool)
    # White noise carries no travelling wave: the estimator must decline it and say why.
    assert zflip_res.accepted is False and zflip_res.rejection_reason
    # `rdm` returns a condensed vector by default; the square form is condensed=False.
    condensed = jnwb.rdm(rng.normal(size=(10, 20)), metric="correlation")
    assert condensed.shape == (45,), condensed.shape
    square = jnwb.rdm(rng.normal(size=(10, 20)), metric="correlation", condensed=False)
    assert square.shape == (10, 10), square.shape
    assert np.allclose(square, square.T) and np.allclose(np.diag(square), 0.0)
    rho_rdm, p_rdm = jnwb.rdm_similarity(condensed, condensed, metric="spearman")
    assert np.isclose(rho_rdm, 1.0)

    # Visualisation setup, as the wheel environment ran it
    jnwb.setup_vector_graphics()
    print("PASS: workflow checks completed before the location check")

    # Before the exports check, which needs an installed environment without extras. The suite
    # runs this script against the checkout (tests/test_release_recovery_gates.py) and expects
    # the refusal below, after every check above has run there too.
    if args.not_under is not None and args.not_under.resolve() in location.parents:
        raise SystemExit(f"FAIL: jnwb was imported from {location}, inside {args.not_under}; "
                         "the installed package is not the one under test")
    assert "site-packages" in str(location) or "dist-packages" in str(location), (
        f"expected installed location, got {location}")
    out_dir = jnwb.paths.outputs_dir()
    assert "site-packages" not in str(out_dir) and "dist-packages" not in str(out_dir), out_dir
    print("PASS: jnwb is installed outside the checkout")

    # Installed without extras, so an optional submodule must name its extra, not resolve.
    from jnwb._lazy_exports import OPTIONAL_SUBMODULES

    missing = [s for s in jnwb.__all__ if s not in OPTIONAL_SUBMODULES and not hasattr(jnwb, s)]
    assert not missing, f"Missing exports: {missing}"
    for name, extra in OPTIONAL_SUBMODULES.items():
        try:
            getattr(jnwb, name)
        except ImportError as exc:
            assert f"pip install jnwb[{extra}]" in str(exc), exc
        else:
            raise AssertionError(f"jnwb.{name} resolved without the {extra} extra")
    print(f"PASS: {len(jnwb.__all__)} public exports resolved or name their extra")
    print(f"PASS: installed jnwb {jnwb.__version__} verified in a clean environment")
    return 0


if __name__ == "__main__":
    sys.exit(main())
