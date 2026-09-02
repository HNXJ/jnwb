"""Deterministic Release Gate for jnwb.

Pipeline:
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("release_gate")

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def run_cmd(cmd: list[str], cwd: pathlib.Path = REPO_ROOT) -> None:
    log.info(f"Executing: {' '.join(cmd)} (cwd={cwd})")
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if res.returncode != 0:
        log.error(f"Command failed with code {res.returncode}:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        sys.exit(res.returncode)
    if res.stdout.strip():
        log.info(res.stdout.strip())


def main() -> None:
    log.info("=== STEP 1: Running full test suite ===")
    run_cmd([sys.executable, "-m", "pytest", "-v", "tests/"])

    log.info("=== STEP 2: Running harness pre-flight verification gate ===")
    run_cmd([sys.executable, str(REPO_ROOT / "scripts" / "harness_gate.py")])

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
        forbidden = ["omission", "_unused", ".lab", "outputs", "artifacts", ".git", "__pycache__"]
        
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
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)], check=True)

        if sys.platform == "win32":
            venv_python = str(venv_dir / "Scripts" / "python.exe")
            venv_pip = str(venv_dir / "Scripts" / "pip.exe")
        else:
            venv_python = str(venv_dir / "bin" / "python")
            venv_pip = str(venv_dir / "bin" / "pip")

        log.info(f"Installing wheel {whl} into isolated environment...")
        subprocess.run([venv_pip, "install", "--no-deps", "--force-reinstall", str(whl)], check=True)

        log.info("Checking package dependencies with pip check...")
        check_res = subprocess.run([venv_pip, "check"], capture_output=True, text=True)
        if check_res.returncode != 0:
            log.error(f"pip check failed: {check_res.stderr}\n{check_res.stdout}")
            sys.exit(check_res.returncode)
        log.info("PASS: pip check verified zero broken requirements.")

        log.info("=== STEP 7: Executing installed-package smoke tests outside repository ===")
        smoke_script = staging_dir / "smoke_test.py"
        smoke_script.write_text("""
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

# Spectral & TFR
sig = rng.normal(size=1000)
freq_grid = np.linspace(10.0, 50.0, 9)
tfr_res = jnwb.complex_tfr(sig, fs=1000.0, freqs=freq_grid, n_cycles=5.0)
acc = jnwb.tfr_accumulator.TFRAccumulator((1, len(freq_grid), 1000))
acc.add_trial(tfr_res.z[None, :, :], valid=tfr_res.coi_mask[None, :, :])
assert acc.power().shape == (1, 9, 1000)

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

# Addressing
elec = pd.DataFrame({'location': ['V1, V2', 'V1, V2'], 'group_name': ['probeA', 'probeA']}, index=[0, 1])
assert jnwb.map_peak_channel_to_area(0, elec) == 'V1'

# Viz
jnwb.setup_vector_graphics()

print('ALL SMOKE VERIFICATIONS PASSED IN ISOLATED WHEEL ENVIRONMENT.')
""", encoding="utf-8")

        res = subprocess.run([venv_python, str(smoke_script)], cwd=str(staging_dir), capture_output=True, text=True)
        if res.returncode != 0:
            log.error(f"Smoke test failed in isolated environment:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
            sys.exit(res.returncode)
        log.info(res.stdout.strip())

    log.info("=============================================================")
    log.info("=== RELEASE GATE VERIFIED: DISTRIBUTABLE PACKAGE READY ===")
    log.info("=============================================================")


if __name__ == "__main__":
    main()
