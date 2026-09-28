"""Smoke-test an installed jnwb: the version, the exports, and a few representative calls.

Run it with the interpreter of the environment under test, from outside the checkout, so that
``import jnwb`` resolves to the installed package:

    python /path/to/scripts/smoke_installed.py --expected-version 0.2.7 --not-under "$GITHUB_WORKSPACE"

The package is expected without extras: an optional submodule must name its extra rather than
resolve. Exits non-zero on the first failed check.
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
    if args.not_under is not None and args.not_under.resolve() in location.parents:
        raise SystemExit(f"FAIL: jnwb was imported from {location}, inside {args.not_under}; "
                         "the installed package is not the one under test")

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

    # Representative installed-package workflows across modules.
    import numpy as np

    rng = np.random.default_rng(42)
    tfr = jnwb.complex_tfr(rng.normal(size=500), fs=1000.0, freqs=np.linspace(10, 40, 4))
    assert tfr.shape == (4, 500)
    freqs, psd = jnwb.compute_multitaper_psd(rng.normal(size=512), fs=1000.0)
    assert len(freqs) == len(psd)
    filt = jnwb.bandpass_filter(rng.normal(size=500), fs=1000.0, low_cut=8.0, high_cut=40.0)
    assert filt.shape == (500,)
    ppc = jnwb.pairwise_phase_consistency(rng.uniform(-np.pi, np.pi, 40))
    assert np.isfinite(ppc)
    print(f"PASS: installed jnwb {jnwb.__version__} verified in a clean environment")
    return 0


if __name__ == "__main__":
    sys.exit(main())
