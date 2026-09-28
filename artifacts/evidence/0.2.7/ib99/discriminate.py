"""Show each new zflip test fails on the code it guards against, then restore in bytes.

Variants of jnwb/laminar.py, each run against the three new tests:
  pristine      the file at the baseline commit (no per-pair surrogate test)
  width_1       _LINEAR_ROUNDOFF_EPS = 1.0
  width_1e6     _LINEAR_ROUNDOFF_EPS = 1e6
  no_pair_gate  the repaired file with the per-pair gate line removed
The selector is first run on the repaired file and must pass.

Usage: python discriminate.py <tree> <baseline-commit>
"""
import hashlib
import os
import subprocess
import sys

tree = os.path.abspath(sys.argv[1])
base = sys.argv[2]
target = os.path.join(tree, "jnwb", "laminar.py")
TESTS = [
    "tests/test_zflip.py::test_zflip_a_cumsum_built_ramp_is_refused_as_linear_in_time",
    "tests/test_zflip.py::test_zflip_a_signal_on_a_large_offset_is_not_refused_as_linear_in_time",
    "tests/test_zflip.py::"
    "test_zflip_a_contact_independent_of_the_others_is_refused_by_its_pair_surrogates",
]
WIDTH = b"_LINEAR_ROUNDOFF_EPS = 1000.0"
GATE = b"        adj_identifiable &= pair_p <= alpha\n"  # laminar.py is LF


def sha(b):
    return hashlib.sha256(b).hexdigest()


def replace_once(src, old, new):
    assert src.count(old) == 1, (old, src.count(old))
    out = src.replace(old, new)
    assert out.count(new) >= 1 and out != src
    return out


def run(name):
    out = {}
    for t in TESTS:
        r = subprocess.run([sys.executable, "-m", "pytest", t, "-q", "-p", "no:cacheprovider"],
                           cwd=tree, capture_output=True, text=True)
        last = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
        out[t.split("::")[1]] = (r.returncode, last)
    print(f"--- {name}")
    for k, (rc, last) in out.items():
        print(f"  rc={rc} {k}: {last}")


def main():
    with open(target, "rb") as f:
        repaired = f.read()
    h0 = sha(repaired)
    pristine = subprocess.run(["git", "-C", tree, "show", f"{base}:jnwb/laminar.py"],
                              capture_output=True, check=True).stdout
    variants = {
        "pristine": pristine,
        "width_1": replace_once(repaired, WIDTH, b"_LINEAR_ROUNDOFF_EPS = 1.0"),
        "width_1e6": replace_once(repaired, WIDTH, b"_LINEAR_ROUNDOFF_EPS = 1e6"),
        "no_pair_gate": replace_once(repaired, GATE, b"        pass\n"),
    }
    try:
        run("repaired (must pass)")
        for name, body in variants.items():
            with open(target, "wb") as f:
                f.write(body)
            run(name)
    finally:
        with open(target, "wb") as f:
            f.write(repaired)
    with open(target, "rb") as f:
        h1 = sha(f.read())
    print(f"restore: {h0} -> {h1} {'OK' if h0 == h1 else 'MISMATCH'}")


if __name__ == "__main__":
    main()
