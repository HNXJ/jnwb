"""Fail-before on baseline sources, then single mutants; every swap restored and hash-verified.

Usage: python failbefore.py
"""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\workspace\jnwb-lanes\g-10-06")
BASE = "32e0a3cc"
SOURCES = [
    "jnwb/connectivity/_psi.py", "jnwb/connectivity/_network.py",
    "jnwb/connectivity/_information.py", "jnwb/jrsa/__init__.py", "jnwb/jrsa/_metrics.py",
    "jnwb/jrsa/_inference.py", "jnwb/jrsa/_stages.py", "jnwb/rsa.py",
]
NEW_TESTS = [
    "tests/test_connectivity.py::TestDirectedEstimatorEdges",
    "tests/test_jrsa_correctness.py::TestARowMetricWindowsTheObservationsByDefault",
    "tests/test_jrsa_correctness.py::TestAnAdimTheResamplingIgnoresIsRefused::"
    "test_after_axis_0_is_reduced_away_the_refusal_reads_axis_1",
    "tests/test_jrsa_correctness.py::TestSimilarityEdges",
    "tests/test_rsa.py::test_a_flat_condition_is_refused_by_name_whatever_its_value",
    "tests/test_adversarial_inputs.py::TestJrsaIsUnitFree::test_backend_cupy_changes_no_number",
    "tests/test_substitution_class_sweep.py::TestTheLiveTreeMatchesTheReviewedBaseline::"
    "test_every_accepted_chain_else_has_a_validator_that_really_rejects",
]
MUTANTS = [
    ("jnwb/connectivity/_psi.py", "_DEFAULT_MIN_SEGMENTS = 20", "_DEFAULT_MIN_SEGMENTS = 7",
     "tests/test_connectivity.py::TestDirectedEstimatorEdges::test_the_default_segment_count"),
    ("jnwb/connectivity/_psi.py", '"psi_freqs": (freqs[:-1] + freqs[1:]) / 2.0',
     '"psi_freqs": freqs[:-1]',
     "tests/test_connectivity.py::TestDirectedEstimatorEdges::"
     "test_psi_freqs_and_the_first_term_are_pinned"),
    ("jnwb/connectivity/_psi.py", "psi_per_freq = np.imag(np.conj(coh_full[:-1]) * coh_full[1:])",
     "psi_per_freq = np.imag(coh_full[:-1] * np.conj(coh_full[1:]))",
     "tests/test_connectivity.py::TestDirectedEstimatorEdges::"
     "test_psi_freqs_and_the_first_term_are_pinned"),
    ("jnwb/jrsa/_stages.py", "(1 if dropped_axis_0 else 0)", "0",
     "tests/test_jrsa_correctness.py::TestAnAdimTheResamplingIgnoresIsRefused::"
     "test_after_axis_0_is_reduced_away_the_refusal_reads_axis_1"),
]


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def pytest(ids, tag):
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                          "-rA", *ids], cwd=ROOT, capture_output=True, text=True)
    lines = [l for l in out.stdout.splitlines()
             if l.startswith(("PASSED", "FAILED", "ERROR")) or " passed" in l or " failed" in l]
    print(f"--- {tag}: rc={out.returncode}")
    for l in lines:
        print("   ", l[:200])
    return out.returncode


def main():
    saved = {p: (ROOT / p).read_bytes() for p in SOURCES}
    hashes = {p: sha(p) for p in SOURCES}
    print("pristine hashes", {p: h[:12] for p, h in hashes.items()})
    assert pytest(NEW_TESTS, "pristine (all new tests must pass)") == 0
    try:
        for p in SOURCES:
            base = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{p}"],
                                  capture_output=True, check=True).stdout
            (ROOT / p).write_bytes(base)
        pytest(NEW_TESTS, f"baseline {BASE} sources")
    finally:
        for p, b in saved.items():
            (ROOT / p).write_bytes(b)
    assert all(sha(p) == hashes[p] for p in SOURCES), "restore mismatch"
    print("restored: all hashes match")
    for path, anchor, repl, test in MUTANTS:
        src = saved[path].decode("utf-8")
        assert src.count(anchor) == 1, (path, anchor)
        try:
            (ROOT / path).write_bytes(src.replace(anchor, repl).encode("utf-8"))
            rc = pytest([test], f"mutant {path}: {anchor[:50]!r} -> {repl[:40]!r}")
            print("    killed" if rc != 0 else "    SURVIVED")
        finally:
            (ROOT / path).write_bytes(saved[path])
        assert sha(path) == hashes[path], "restore mismatch"
    print("restored after mutants: all hashes match")


if __name__ == "__main__":
    main()
