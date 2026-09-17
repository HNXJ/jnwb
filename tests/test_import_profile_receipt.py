"""The import profile must describe this release, and must not measure its own probe.

Two separate failures were shipped together.

The receipt went five releases stale -- ``artifacts/benchmarks/import_profile.txt`` still
announced "jnwb 0.1.6 (111 public symbols)" while 0.2.4 exported 155 -- because nothing
gated it, unlike ``tests/test_vflip_calibration_receipt.py``.

The numbers in it were wrong anyway. The probe started ``tracemalloc`` before its timer,
so the import it timed was an import with allocation tracing switched on. Measured here
over seven interleaved fresh-process repetitions: 7724 ms traced against 2317 ms clean, a
3.33x over-report. Moving the ``tracemalloc.start()`` below the timed region is not a fix
-- it returns a 0.0 MB peak, because the allocations have already happened -- so the
memory measurement now runs in processes of its own.

The version gate covers the release; the symbol count is deliberately not gated, because
a public symbol is added far more often than a release is cut and regenerating the
receipt costs a cold import of about 40 s. A count can therefore be one release stale,
never five.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

import jnwb
from scripts.benchmark_import import (
    BREAKDOWN_PATH,
    MEMORY_PROBE,
    PROBE,
    PROFILE_PATH,
    render,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _profile_text():
    return PROFILE_PATH.read_text(encoding="utf-8")


def test_receipt_and_generator_exist():
    assert (ROOT / "scripts" / "benchmark_import.py").is_file()
    assert PROFILE_PATH.is_file() and BREAKDOWN_PATH.is_file()


def test_the_profile_describes_this_release():
    m = re.search(r"^- jnwb (\S+) \((\d+) public symbols\)", _profile_text(), re.M)
    assert m is not None, "the profile no longer states the version it was generated from"
    assert m.group(1) == jnwb.__version__, (
        f"import_profile.txt was generated from jnwb {m.group(1)}, this is "
        f"{jnwb.__version__}; rerun `python scripts/benchmark_import.py --write`"
    )


def test_the_breakdown_describes_this_release():
    payload = json.loads(BREAKDOWN_PATH.read_text(encoding="utf-8"))
    assert payload["version"] == jnwb.__version__, (
        f"import_breakdown.json was generated from jnwb {payload['version']}, this is "
        f"{jnwb.__version__}; rerun `python scripts/benchmark_import.py --write`"
    )


def test_the_two_receipts_come_from_the_same_run():
    """The profile is rendered from the payload, so the round trip is available and is
    stronger than comparing a number out of each: the committed json must render to the
    committed profile. Whether `--profile` was passed is not recorded in the payload, so
    both renderings are accepted.
    """
    payload = json.loads(BREAKDOWN_PATH.read_text(encoding="utf-8"))
    assert _profile_text() in (render(payload), render(payload, profile=True)), (
        "import_profile.txt is not what import_breakdown.json renders to, so the two "
        "receipts are from different runs; rerun "
        "`python scripts/benchmark_import.py --write`"
    )


def test_the_timing_probe_does_not_instrument_the_import():
    assert "tracemalloc" not in PROBE, (
        "the timing probe traces allocations again; that inflates the import it is "
        "timing by about 3.3x"
    )
    for hook in ("setprofile", "settrace", "importtime"):
        assert hook not in PROBE, f"the timing probe enables {hook}"


def test_memory_is_measured_by_a_probe_that_does_not_time():
    assert "tracemalloc" in MEMORY_PROBE
    assert "perf_counter" not in MEMORY_PROBE, (
        "the memory probe times as well; its import is traced and therefore slow"
    )
    start = MEMORY_PROBE.index("tracemalloc.start()")
    assert start < MEMORY_PROBE.index("import jnwb"), (
        "tracing starts after the import, so the peak it reports is not the import's"
    )


def _time_import(source):
    """Run `source` in a fresh interpreter and return the ms it reports.

    The repo's real bytecode cache is used, so this is a warm import. `check=True`
    surfaces a probe that fails rather than letting it read as a fast one.
    """
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    out = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True, text=True, env=env,
        cwd=tempfile.gettempdir(), check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])["ms"]


REFERENCE = """
import json, time
t0 = time.perf_counter()
import jnwb
print(json.dumps({"ms": (time.perf_counter() - t0) * 1000.0}))
"""


def test_the_probe_agrees_with_an_independent_wall_clock():
    """The static guards above name the instrumentation they know about; this one
    needs no name, but only sees instrumentation that actually costs something.

    The two are complementary, and neither subsumes the other. A no-op
    `sys.setprofile` hook was killed by the static guard while passing this
    comparison, and anything not on the static list is only caught here.

    The margin is wide on both sides: healthy runs differed by at most 1.23x across
    seven repetitions on a contended machine, and the defect this replaces was 3.33x.
    """
    reference = _time_import(REFERENCE)
    shipped = _time_import(PROBE)
    assert reference > 0.0
    assert shipped / reference < 1.6, (
        f"the shipped probe reports {shipped:.0f} ms where an uninstrumented import "
        f"takes {reference:.0f} ms; something in the probe is being measured too"
    )
