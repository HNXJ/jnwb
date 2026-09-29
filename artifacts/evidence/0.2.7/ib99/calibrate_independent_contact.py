"""False-accept rate of zflip when one contact carries a signal independent of the others.

A 5-contact 10-40 Hz travelling wave, 2 samples of lag per contact, 8000 samples at 1 kHz.
One contact is replaced by independent unit-SD noise (bandpassed 10-40 Hz, white, or 1/f^2),
seeds 10000-10099. End: contact 0 on odd seeds, contact 4 on even (the critic's layout).
Interior: contact 2 on every seed. Each case is one zflip call with n_surrogates=50 and
rng=0 (the critic's call), or rng=<noise seed> with ``per-seed`` so the 100 surrogate sets
are independent draws rather than one shared set.

Usage: python calibrate_independent_contact.py <tree> [per-seed]
"""
import os
import sys
import warnings

tree = os.path.abspath(sys.argv[1])
sys.path.insert(0, tree)
import numpy as np  # noqa: E402
from scipy import signal  # noqa: E402
import jnwb  # noqa: E402

assert os.path.abspath(jnwb.__file__).startswith(tree), jnwb.__file__
warnings.simplefilter("ignore")
FS = 1000.0
TRUE_TAU = 0.001991  # the critic's normaliser: the clean wave's measured delay, about 2 samples
PER_SEED = len(sys.argv) > 2 and sys.argv[2] == "per-seed"


def lagged(n=8000, seed=11, lags=(0, 2, 4, 6, 8)):
    sos = signal.butter(4, (10, 40), btype="band", fs=FS, output="sos")
    src = signal.sosfiltfilt(sos, np.random.default_rng(seed).standard_normal(n + 400))
    src /= src.std()
    return np.stack([src[400 - L: 400 - L + n] for L in lags])


def noise(kind, g, n):
    if kind == "bandpassed":
        sos = signal.butter(4, (10, 40), btype="band", fs=FS, output="sos")
        x = signal.sosfiltfilt(sos, g.standard_normal(n))
    elif kind == "white":
        x = g.standard_normal(n)
    else:
        X = np.fft.rfft(g.standard_normal(n))
        f = np.fft.rfftfreq(n)
        f[0] = f[1]
        x = np.fft.irfft(X / f, n)
    return x / x.std()


def main():
    base = lagged()
    n = base.shape[1]
    clean = jnwb.zflip(base, FS, orientation="superficial_to_deep", pitch_um=100.0,
                       n_surrogates=50, rng=0)
    print(f"clean wave seed 11: tau={clean.tau_per_channel_s!r} accepted={clean.accepted} "
          f"p={clean.p_value:.4f} ident={clean.adjacent_identifiable.astype(int).tolist()}")
    for where in ("end", "interior"):
        for kind in ("bandpassed", "white", "1/f^2"):
            ident, acc, ratios = 0, 0, []
            for seed in range(100):
                g = np.random.default_rng(10_000 + seed)
                idx = (0 if seed % 2 else 4) if where == "end" else 2
                d = base.copy()
                d[idx] = noise(kind, g, n)
                r = jnwb.zflip(d, FS, orientation="superficial_to_deep", pitch_um=100.0,
                               n_surrogates=50, rng=10_000 + seed if PER_SEED else 0)
                ident += int(r.delay_identifiable)
                if r.accepted:
                    acc += 1
                    ratios.append(round(r.tau_per_channel_s / TRUE_TAU, 2))
            print(f"{where:8s} {kind:10s}: identifiable {ident:3d}/100  accepted {acc:3d}/100  "
                  f"accepted tau/true {sorted(ratios)}")


if __name__ == "__main__":
    main()
