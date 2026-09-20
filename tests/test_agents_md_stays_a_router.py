"""`AGENTS.md` may grow; it may not grow a second home for a claim that lives elsewhere.

P-15 read a line count as evidence of a thin-router violation. Measuring it showed the opposite:
436 lines carrying 181 claim-bearing sentences, of which 8 are duplicated and 10 echoed. Length
and duplication turned out to be independent -- the newest and longest section contributed zero
duplicates. So the ratchet here is on duplication, which is the invariant, and not on length,
which is the proxy.

This is also the caller for `scripts/measure_agents_md_duplication.py`. A measurement script that
nothing runs reports on whatever the repository looked like the day someone last ran it by hand.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "measure_agents_md_duplication.py"

#: What the measurement returned on 2026-09-19, recorded in `artifacts/agents_md_duplication.md`.
#: A ratchet, not a target: 06-72 drives it to zero, and until then it may not rise.
BASELINE_DUPLICATED = 8
BASELINE_ECHOED = 10


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
    missing = {"duplicated", "echoed", "sentences"} - set(counts)
    assert not missing, f"the script's output no longer reports {missing}:\n{done.stdout[:800]}"
    return counts


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
