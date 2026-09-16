"""Deterministic Release Gate for jnwb.

Pipeline:
  0. Required release/test tooling is present in the active environment
  1. Full test suite execution (pytest tests/)
  2. Harness pre-flight gates
  3. Clean distribution build (sdist + wheel)
  4. Manifest & forbidden-content inspection (no _unused, no omission, no artifacts)
  5. Distribution metadata & README validation (twine check)
  6. Isolated environment wheel installation & pip check
  7. Installed-package smoke verification without omission

Exits 0 on complete verified success; non-zero otherwise.
"""

import os
import sys
import shutil
import tempfile
import pathlib
import zipfile
import tarfile
import subprocess
import logging
import re
from typing import List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("release_gate")

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


#: Extras whose tooling must be present for release qualification to mean anything. ``docs`` is
#: included because tests/ contains a strict MkDocs build assertion: without it the suite does
#: not fail, it reports a *different* result, which is worse.
REQUIRED_EXTRAS = ("test", "docs")


_VERSION_RE = re.compile(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def jnwb_source_version() -> str:
    """The version the source tree declares, parsed textually.

    Read rather than imported: the gate compares the *source* declaration against what the
    built wheel reports, so importing the package under test would make the comparison
    tautological. Pinning the expected version as a literal here is the same drift failure
    class the documentation gates exist to prevent.
    """
    init = REPO_ROOT / "jnwb" / "__init__.py"
    match = _VERSION_RE.search(init.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError(f"could not parse __version__ from {init}")
    return match.group(1)


def declared_extra_requirements(extras=REQUIRED_EXTRAS) -> List[str]:
    """Distribution names pyproject.toml declares for the given extras."""
    import re
    import tomllib

    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        pyproject = tomllib.load(fh)
    optional = pyproject.get("project", {}).get("optional-dependencies", {})

    names: List[str] = []
    for extra in extras:
        for spec in optional.get(extra, []):
            if spec.lstrip().startswith("jnwb["):
                continue                      # self-referential aggregate (the `all` extra)
            name = re.split(r"[<>=!~\[;\s]", spec.strip(), maxsplit=1)[0]
            if name and name not in names:
                names.append(name)
    return names


def verify_declared_environment(extras=REQUIRED_EXTRAS) -> List[str]:
    """Return declared tooling distributions absent from the RUNNING interpreter.

    Release qualification must inspect the environment it claims to qualify. The supported-Python
    contract lives in pyproject.toml and CI (which installs ``.[test,docs]`` on every matrix
    leg) -- not in whatever happens to be installed on the machine invoking this script. An
    interpreter missing declared tooling does not fail loudly; it silently produces a different
    and better-looking result, because a test that cannot import its tool reports one failure
    rather than exercising the surface it was written for.

    This is not hypothetical: an RC audit measured "1 failed, 1021 passed" against a receipt of
    "1026 passed, 1 skipped" purely because the invoking 3.12 interpreter lacked the declared
    ``docs`` tooling. Both numbers were honest; only one described the declared environment.

    Scope, deliberately narrow: this is a PRESENCE check on the distributions named by the
    extras -- it answers "is the tooling installed here at all". It does NOT prove every
    dependency constraint is satisfied, does not read version specifiers, and does not detect a
    conflicting or broken dependency graph. ``pip check`` in STEP 6, run against the isolated
    wheel installation, remains the authoritative installed-distribution consistency check. Use
    this to stop a qualification run that would measure the wrong environment, not as evidence
    that the environment is fully correct.
    """
    from importlib.metadata import PackageNotFoundError, distribution

    missing: List[str] = []
    for name in declared_extra_requirements(extras):
        try:
            distribution(name)
        except PackageNotFoundError:
            missing.append(name)
    return missing


def run_cmd(cmd: list[str], cwd: pathlib.Path = REPO_ROOT) -> None:
    log.info(f"Executing: {' '.join(cmd)} (cwd={cwd})")
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if res.returncode != 0:
        log.error(f"Command failed with code {res.returncode}:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        sys.exit(res.returncode)
    if res.stdout.strip():
        log.info(res.stdout.strip())


def _api_md_check_commands() -> List[List[str]]:
    """Return generate_api_md --check commands for the current and floor interpreters."""
    api_script = str(REPO_ROOT / "scripts" / "generate_api_md.py")
    commands = [[sys.executable, api_script, "--check"]]
    if sys.version_info[:2] != (3, 12):
        py_launcher = shutil.which("py")
        if py_launcher is not None:
            commands.append([py_launcher, "-3.12", api_script, "--check"])
    return commands


def main() -> None:
    log.info("=== STEP 0: Checking required release/test tooling in the active environment ===")
    missing = verify_declared_environment()
    if missing:
        log.error(
            "This interpreter (%s, Python %s) is missing required tooling: %s",
            sys.executable, ".".join(str(v) for v in sys.version_info[:3]), ", ".join(missing))
        log.error("Release qualification would measure an unprovisioned environment. Provision it:")
        log.error('    "%s" -m pip install ".[%s]"', sys.executable, ",".join(REQUIRED_EXTRAS))
        sys.exit(1)
    log.info(
        "PASS: required release/test tooling from [%s] is importable on Python %s "
        "(presence check; pip check in STEP 6 verifies dependency consistency).",
        ",".join(REQUIRED_EXTRAS), ".".join(str(v) for v in sys.version_info[:3]))

    log.info("=== STEP 1: Running full test suite ===")
    run_cmd([sys.executable, "-m", "pytest", "-v", "tests/"])

    log.info("=== STEP 2: Running harness pre-flight verification gate ===")
    run_cmd([sys.executable, str(REPO_ROOT / "scripts" / "harness_gate.py")])

    for cmd in _api_md_check_commands():
        label = "current interpreter" if cmd[0] == sys.executable else "Python 3.12 floor"
        log.info(f"=== STEP 2b: API docs generator drift check ({label}) ===")
        run_cmd(cmd)

    with tempfile.TemporaryDirectory() as tmpdir:
        staging_dir = pathlib.Path(tmpdir)
        dist_dir = staging_dir / "dist"
        dist_dir.mkdir()

        log.info(f"=== STEP 3: Building sdist and wheel in staging directory: {dist_dir} ===")
        run_cmd([sys.executable, "-m", "build", "--outdir", str(dist_dir), str(REPO_ROOT)])

        wheels = list(dist_dir.glob("*.whl"))
        sdists = list(dist_dir.glob("*.tar.gz"))
        if not wheels or not sdists:
            log.error("Build failed to produce wheel or sdist!")
            sys.exit(1)

        whl = wheels[0]
        sdist = sdists[0]
        log.info(f"Produced wheel: {whl.name} ({whl.stat().st_size:,} bytes)")
        log.info(f"Produced sdist: {sdist.name} ({sdist.stat().st_size:,} bytes)")

        log.info("=== STEP 4: Inspecting archive manifests ===")
        forbidden = [
            "omission", "_unused", ".lab", "outputs", "artifacts", ".git", "__pycache__",
            "/tests/", "/scripts/",
        ]

        with zipfile.ZipFile(whl, "r") as z:
            whl_files = z.namelist()
            for f in forbidden:
                hits = [n for n in whl_files if f in n]
                if hits:
                    log.error(f"Forbidden entry {f} found in wheel: {hits}")
                    sys.exit(1)
        log.info("PASS: Wheel archive contains zero forbidden entries (no _unused, no omission).")

        with tarfile.open(sdist, "r:gz") as t:
            sdist_files = t.getnames()
            for f in forbidden:
                hits = [n for n in sdist_files if f in n]
                if hits:
                    log.error(f"Forbidden entry {f} found in sdist: {hits}")
                    sys.exit(1)
        log.info("PASS: Sdist archive contains zero forbidden entries (no _unused, no omission).")

        log.info("=== STEP 5: Validating metadata with twine ===")
        run_cmd([sys.executable, "-m", "twine", "check", str(whl), str(sdist)])

        log.info("=== STEP 6: Creating isolated venv for wheel installation ===")
        venv_dir = staging_dir / "isolated_venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

        if sys.platform == "win32":
            venv_python = str(venv_dir / "Scripts" / "python.exe")
        else:
            venv_python = str(venv_dir / "bin" / "python")

        log.info(f"Installing wheel {whl} into isolated environment...")
        # `python -m pip`, not the pip executable: on Windows pip refuses to replace its
        # own running .exe and exits 1, which failed this gate before it tested anything.
        subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([venv_python, "-m", "pip", "install", str(whl)], check=True)

        log.info("Checking package dependencies with pip check...")
        check_res = subprocess.run([venv_python, "-m", "pip", "check"], capture_output=True, text=True)
        if check_res.returncode != 0:
            log.error(f"pip check failed: {check_res.stderr}\n{check_res.stdout}")
            sys.exit(check_res.returncode)
        log.info("PASS: pip check verified zero broken requirements.")

        log.info("=== STEP 7: Executing installed-package smoke tests outside repository ===")
        smoke_script = staging_dir / "smoke_test.py"
        smoke_script.write_text(f"EXPECTED_VERSION = {jnwb_source_version()!r}\n" + """
import sys
import pathlib
import numpy as np
import pandas as pd

cwd = pathlib.Path.cwd()
assert 'jnwb' not in cwd.name, f'CWD must be outside repository, got {cwd}'

# 1. Verify omission is absent
try:
    import omission
    raise RuntimeError('FAIL: omission is unexpectedly importable!')
except ModuleNotFoundError:
    print('PASS: omission is strictly absent and unimportable.')

# 2. Import jnwb
import jnwb
print(f'PASS: import jnwb successful from {jnwb.__file__}')
print(f'      jnwb.__version__ = {jnwb.__version__}')
assert jnwb.__version__ == EXPECTED_VERSION, (
    f'Installed wheel reports {jnwb.__version__}, source declares {EXPECTED_VERSION}')
pkg = pathlib.Path(jnwb.__file__).resolve()
assert 'site-packages' in str(pkg) or 'dist-packages' in str(pkg), f'expected installed location, got {pkg}'
out_dir = jnwb.paths.outputs_dir()
assert 'site-packages' not in str(out_dir) and 'dist-packages' not in str(out_dir)

# 3. Test all exported symbols in __all__
for sym in jnwb.__all__:
    assert hasattr(jnwb, sym), f'Missing symbol: {sym}'
print(f'PASS: All {len(jnwb.__all__)} symbols in jnwb.__all__ resolved.')

# 4. Workflows
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

# Spectral & TFR
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

# Statistics, decoding, connectivity, artifact
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
elec = pd.DataFrame({'location': ['V1, V2', 'V1, V2'], 'group_name': ['probeA', 'probeA']}, index=[0, 1])
assert jnwb.map_peak_channel_to_area(0, elec) == 'V1'

# 5. NWB discovery, processing LFP, calibration, and epoching (0.1.8 contract)
import pathlib
import tempfile
from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    TASK_TABLE,
    canonical_co_resident_options,
    processing_lfp_options,
    write_synth_nwb,
)
# Top-level acquisition test
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

# epoch_continuous primitive & drop retained indices
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

# 6. 0.2.1 additions: aperiodic_fit, relative_power, exact stats, stream_npz_array, probe_geometry
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

# 7. 0.2.4 additions: wpli, zflip, rdm
# `wpli` returns a dict, so `hasattr` is always False on it; and the debiased key is
# `wpli_debiased_sq`, not `wpli_debiased`. Check the keys and their contracts.
wpli_res = jnwb.wpli(sig[:500], sig[500:], fs=1000.0, freq_range=(10.0, 40.0))
assert set(wpli_res) == {'wpli', 'wpli_debiased_sq', 'freqs', 'wpli_spectrum', 'n_segments', 'n_freqs'}
assert 0.0 <= wpli_res['wpli'] <= 1.0, wpli_res['wpli']
assert -1.0 <= wpli_res['wpli_debiased_sq'] <= 1.0, wpli_res['wpli_debiased_sq']
assert wpli_res['freqs'].shape == wpli_res['wpli_spectrum'].shape
assert 1 <= wpli_res['n_freqs'] <= wpli_res['freqs'].size
assert wpli_res['n_segments'] >= 2

zflip_res = jnwb.zflip(rng.normal(size=(8, 1000)), fs=1000.0, pitch_um=20.0, freq_range=(15.0, 35.0), seed=42)
assert isinstance(zflip_res.delay_identifiable, bool) and isinstance(zflip_res.accepted, bool)
# White noise carries no travelling wave: the estimator must decline it and say why.
assert zflip_res.accepted is False and zflip_res.rejection_reason

# `rdm` returns a CONDENSED vector by default; the square form is condensed=False.
condensed = jnwb.rdm(rng.normal(size=(10, 20)), metric="correlation")
assert condensed.shape == (45,), condensed.shape
square = jnwb.rdm(rng.normal(size=(10, 20)), metric="correlation", condensed=False)
assert square.shape == (10, 10), square.shape
assert np.allclose(square, square.T) and np.allclose(np.diag(square), 0.0)
rho_rdm, p_rdm = jnwb.rdm_similarity(condensed, condensed, metric="spearman")
assert np.isclose(rho_rdm, 1.0)

# 8. Viz
jnwb.setup_vector_graphics()

print('ALL SMOKE VERIFICATIONS PASSED IN ISOLATED WHEEL ENVIRONMENT.')
""", encoding="utf-8")

        res = subprocess.run([venv_python, str(smoke_script)], cwd=str(staging_dir), capture_output=True, text=True)
        if res.returncode != 0:
            log.error(f"Smoke test failed in isolated environment:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
            sys.exit(res.returncode)
        log.info(res.stdout.strip())

        log.info("=== STEP 8: Executing tutorials against the installed wheel ===")
        tutorials = sorted((REPO_ROOT / "examples" / "tutorials").glob("[0-9][0-9]_*.py"))
        if not tutorials:
            log.error("No numbered tutorials found; 0.2.4-03 cannot be verified.")
            sys.exit(1)
        # PYTHONPATH is stripped and the CWD is the staging directory, so a tutorial that
        # only runs from the source tree fails here instead of passing by checkout proximity.
        tutorial_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        for tutorial in tutorials:
            res = subprocess.run(
                [venv_python, str(tutorial)], cwd=str(staging_dir),
                env=tutorial_env, capture_output=True, text=True)
            if res.returncode != 0:
                log.error("Tutorial %s failed against the installed wheel:\nSTDOUT:\n%s\nSTDERR:\n%s",
                          tutorial.name, res.stdout, res.stderr)
                sys.exit(res.returncode)
            log.info("PASS: %s executed against the installed wheel.", tutorial.name)
        log.info("PASS: all %d tutorials ran against the installed artifact.", len(tutorials))

    log.info("=============================================================")
    log.info("=== RELEASE GATE VERIFIED: DISTRIBUTABLE PACKAGE READY ===")
    log.info("=============================================================")


if __name__ == "__main__":
    main()
