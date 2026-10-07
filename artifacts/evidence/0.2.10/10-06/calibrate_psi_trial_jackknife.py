"""PSI lead-p rejection rates with the leave-one-trial-out and leave-one-segment-out jackknife (P-227).

Trials of n_times samples at fs 1000 Hz, band 5-100 Hz, default nperseg. Seed s per pair:
  mixing      x = w + 0.5 e1, y = w + 0.5 e2, w white (no lead; zero-lag common source)
  independent x, y white and independent (no coupling)
  lead        x white, y = x delayed 5 samples + 1.0 e per trial (a true lead of x)
'trial' is the shipped rule (one trial left out from 3 trials on). 'segment' forces the old
leave-one-segment-out jackknife on the same data by raising the module's trial threshold.
The rate is P(p_net < 0.05).

Usage: python calibrate_psi_trial_jackknife.py <worktree> <n_seeds> <trials>x<n_times> ...
"""
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor

import numpy as np

WORKTREE = sys.argv[1]
sys.path.insert(0, WORKTREE)
import jnwb  # noqa: E402
from jnwb.connectivity import _psi  # noqa: E402

assert jnwb.__file__.replace("\\", "/").startswith(WORKTREE.replace("\\", "/")), jnwb.__file__

FS, BAND = 1000.0, (5.0, 100.0)
SHIPPED_THRESHOLD = _psi._MIN_TRIALS_FOR_TRIAL_JACKKNIFE


def pair(scenario, n_trials, n_times, seed):
    rng = np.random.default_rng(seed)
    shape = (n_trials, n_times)
    if scenario == "mixing":
        w = rng.normal(size=shape)
        return w + 0.5 * rng.normal(size=shape), w + 0.5 * rng.normal(size=shape)
    if scenario == "independent":
        return rng.normal(size=shape), rng.normal(size=shape)
    x = rng.normal(size=(n_trials, n_times + 5))
    return x[:, 5:], x[:, :-5] + 1.0 * rng.normal(size=shape)


def job(args):
    scenario, n_trials, n_times, unit, seed = args
    _psi._MIN_TRIALS_FOR_TRIAL_JACKKNIFE = SHIPPED_THRESHOLD if unit == "trial" else 10**9
    x, y = pair(scenario, n_trials, n_times, seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        res = jnwb.phase_slope_index(x, y, fs=FS, bands=BAND)
    assert res.params["jackknife_unit"] == unit
    return np.nan if res.p_net is None else res.p_net, res.params["n_segments"]


if __name__ == "__main__":
    n_seeds = int(sys.argv[2])
    shapes = [tuple(int(v) for v in s.split("x")) for s in sys.argv[3:]]
    print("jnwb from", jnwb.__file__)
    print(f"fs={FS} band={BAND} seeds 0..{n_seeds - 1}")
    with ProcessPoolExecutor(12) as ex:
        for scenario in ("mixing", "independent", "lead"):
            for n_trials, n_times in shapes:
                for unit in ("trial", "segment"):
                    out = np.array(list(ex.map(
                        job, [(scenario, n_trials, n_times, unit, s) for s in range(n_seeds)],
                        chunksize=50)))
                    p = out[:, 0]
                    rate = float(np.mean(p < 0.05))
                    se = float(np.sqrt(rate * (1 - rate) / n_seeds))
                    print(f"{scenario:11s} {n_trials:3d}x{n_times:<5d} {unit:7s} "
                          f"segments={int(out[0, 1]):4d} P(p<0.05)={rate:.4f} (se {se:.4f}) "
                          f"undefined={int(np.isnan(p).sum())}")
                    sys.stdout.flush()
    print("rc=0")
