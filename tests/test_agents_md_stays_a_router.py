"""`AGENTS.md` may grow; it may not grow a second home for a claim that lives elsewhere.

P-15 read a line count as evidence of a thin-router violation. Measuring it showed the opposite:
436 lines carrying 181 claim-bearing sentences, of which 8 are duplicated and 10 echoed. Length
and duplication turned out to be independent -- the newest and longest section contributed zero
duplicates. So the ratchet here is on duplication, which is the invariant, and not on length,
which is the proxy.

This is also the caller for `scripts/measure_agents_md_duplication.py`. A measurement script that
nothing runs reports on whatever the repository looked like the day someone last ran it by hand.
"""

import contextlib
import importlib.util
import io
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "measure_agents_md_duplication.py"

#: Measured on 2026-09-20 after 06-72, recorded in `artifacts/agents_md_duplication.md`.
#: A ratchet, not a target: it may not rise. Zero is the floor and the target was reached, so
#: from here the ratchet only defends the gain.
BASELINE_DUPLICATED = 0
#: Set to the measurement, not above it: 06-64 found a unit of unclaimed slack here, and slack
#: in a ratchet is a gain someone can give back without the test noticing.
BASELINE_ECHOED = 6

#: The thresholds the baselines are counts *of*. Without pinning these, the counts above are
#: satisfiable by turning a knob: 06-64 demonstrated eight (HIGH, MED) pairs that report fewer
#: duplicates with the text byte-identical and every test green. A threshold change is a decision
#: and must read as a constant edit in a diff, not as a measurement improving.
EXPECTED_HIGH = 0.34
EXPECTED_MED = 0.18


@pytest.fixture(scope="module")
def measurement() -> dict:
    """Run the script and parse its counts, so the test fails when the script does."""
    if not SCRIPT.exists():
        pytest.fail(f"the measurement script is gone: {SCRIPT.relative_to(REPO_ROOT)}")
    done = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert done.returncode == 0, f"the measurement script failed:\n{done.stderr[-2000:]}"
    counts = {}
    for line in done.stdout.splitlines():
        if line.startswith("DUPLICATED"):
            counts["duplicated"] = int(line.split(":")[1].split("(")[0].strip())
        elif line.startswith("ECHOED"):
            counts["echoed"] = int(line.split(":")[1].split("(")[0].strip())
        elif line.startswith("AGENTS.md:"):
            counts["sentences"] = int(line.split(",")[1].split()[0])
        elif line.startswith("ROOT:"):
            counts["root"] = line.split(":", 1)[1].strip()
    missing = {"duplicated", "echoed", "sentences", "root"} - set(counts)
    assert not missing, f"the script's output no longer reports {missing}:\n{done.stdout[:800]}"
    return counts


def test_the_thresholds_the_counts_are_counts_of_are_pinned():
    """A count is meaningless without the threshold it counts above.

    06-64 turned `(0.34, 0.18)` into `(0.40, 0.35)` and watched `duplicated` fall from 8 to 6 with
    `AGENTS.md` byte-identical and all four tests green -- then the "lower the baseline when you
    beat it" test invites banking that as a gain. Reading the constants out of the script makes
    the knob-turn a visible constant edit rather than an improvement.
    """
    spec = importlib.util.spec_from_file_location("_measure_thresholds", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # The script does its work at import time and prints; run it with stdout parked.
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(module)
    assert (module.HIGH, module.MED) == (EXPECTED_HIGH, EXPECTED_MED), (
        f"the measurement thresholds moved to {(module.HIGH, module.MED)}. Every baseline in this "
        "file counts pairs above them, so changing one silently rescales all of them. If the move "
        "is deliberate, update EXPECTED_HIGH/EXPECTED_MED and re-record the baselines together."
    )


def test_the_script_measures_the_tree_it_lives_in(measurement):
    """It hard-coded one machine's checkout, so the ratchet passed with the file under test gone.

    06-64 deleted `AGENTS.md` from a copy and got `4 passed`. `ROOT` is now derived from
    `__file__`; this keeps it derived. Gate 3 covers `scripts/` for the same reason, but a gate and
    a test failing for one defect is the point, not redundancy.
    """
    source = SCRIPT.read_text(encoding="utf-8")
    assert "parents[1]" in source and "pathlib.Path(r\"" not in source, (
        "the measurement script names an absolute path again; it must derive ROOT from __file__"
    )
    assert measurement["root"] == str(REPO_ROOT), (
        f"the script measured {measurement['root']!r}, not the tree under test ({REPO_ROOT})"
    )


def test_the_measurement_still_finds_something_to_measure(measurement):
    """A script that reports zero sentences would pass every ratchet below for the wrong reason."""
    assert measurement["sentences"] >= 100, (
        f"only {measurement['sentences']} claim-bearing sentences found in AGENTS.md; "
        "the sweep is broken, not the file"
    )


def test_duplicated_claims_do_not_increase(measurement):
    """Eight claims have two homes. A ninth is a regression, not a style question."""
    assert measurement["duplicated"] <= BASELINE_DUPLICATED, (
        f"{measurement['duplicated']} duplicated claims against a baseline of "
        f"{BASELINE_DUPLICATED}. Run `python scripts/measure_agents_md_duplication.py` to see "
        "which claim gained a second home, then give it one owner and make the other file point."
    )


def test_echoed_claims_do_not_increase(measurement):
    """The weaker band, ratcheted for the same reason: an echo is a duplicate in progress."""
    assert measurement["echoed"] <= BASELINE_ECHOED, (
        f"{measurement['echoed']} echoed claims against a baseline of {BASELINE_ECHOED}"
    )


def test_the_baseline_is_lowered_when_it_is_beaten(measurement):
    """A ratchet nobody tightens is a ceiling. 06-72 drives these to zero."""
    assert measurement["duplicated"] >= BASELINE_DUPLICATED - 2, (
        f"duplicates dropped to {measurement['duplicated']}; lower BASELINE_DUPLICATED here and "
        "in artifacts/agents_md_duplication.md so the gain cannot be given back silently"
    )
