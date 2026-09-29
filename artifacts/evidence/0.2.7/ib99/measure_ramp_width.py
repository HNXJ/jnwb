"""Where round-off ramps and offset signals sit against zflip's linear-in-time width.

The ratio is the rms residual of a row's least-squares line in eps of its largest
magnitude, the quantity zflip compares against 1000. Prints the range for exact
(linspace-style) ramps, for cumsum-built ramps, and for a unit-SD signal on large offsets.

Usage: python measure_ramp_width.py <tree>
"""
import os
import sys

tree = os.path.abspath(sys.argv[1])
sys.path.insert(0, tree)
import numpy as np  # noqa: E402
import jnwb  # noqa: E402
from jnwb import laminar  # noqa: E402

assert os.path.abspath(jnwb.__file__).startswith(tree), jnwb.__file__
EPS = np.finfo(float).eps


def ratio(x):
    t = np.arange(x.size, dtype=float)
    t -= t.mean()
    c = x - x.mean()
    r = c - (c @ t / (t @ t)) * t
    return np.sqrt(np.mean(r ** 2)) / (EPS * np.max(np.abs(x)))


def main():
    g = np.random.default_rng(0)
    exact, cums = [], []
    for _ in range(2000):
        n = int(10 ** g.uniform(3, 5))
        s = 10 ** g.uniform(-6, 6) * g.choice([-1, 1])
        o = 10 ** g.uniform(-6, 6) * g.choice([-1, 1])
        t = np.arange(n, dtype=float)
        exact.append(ratio(o + s * t / n))
        cums.append(ratio(o + np.cumsum(np.full(n, s / n))))
    print(f"exact ramps  (2000, n 1e3-1e5, slope/offset 1e-6-1e6): ratio "
          f"{min(exact):.3g} to {max(exact):.3g}")
    print(f"cumsum ramps (same draws):                            ratio "
          f"{min(cums):.3g} to {max(cums):.3g}")
    for n in (1000, 4000, 8000, 16000, 32000, 100000):
        vals = []
        for _ in range(300):
            s = 10 ** g.uniform(-6, 6) * g.choice([-1, 1])
            o = 10 ** g.uniform(-6, 6) * g.choice([-1, 1])
            vals.append(ratio(o + np.cumsum(np.full(n, s / n))))
        print(f"cumsum ramps n={n:6d} (300 draws): ratio max {max(vals):.3g}, "
              f"above 1000: {sum(v > 1000 for v in vals)}")
    x = 3.0 + np.cumsum(np.full(8000, 0.1))
    print(f"3.0 + cumsum(full(8000, 0.1)): ratio {ratio(x):.4g}, "
          f"refused {bool(laminar._linear_to_roundoff(x[None])[0])}")
    s = g.standard_normal(8000)
    s /= s.std()
    for off in (1e10, 1e11, 1e12):
        y = s + off
        print(f"unit-SD signal on offset {off:.0e}: ratio {ratio(y):.4g}, "
              f"refused {bool(laminar._linear_to_roundoff(y[None])[0])}")


if __name__ == "__main__":
    main()
