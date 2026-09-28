"""Measure the peak resident memory of a fixed set of representative operations.

Each operation runs in a fresh interpreter, so one operation's peak cannot hide under
another's. The child builds its inputs from a fixed seed, resets its peak resident set size to
its current one where the platform allows it, reads both, runs the operation once, and reads
the peak again. ``added_mib`` is the peak during the operation minus the resident size before
it; ``peak_mib`` is the process's whole peak. ``control_256mib`` allocates and touches 256 MiB
and nothing else, so its ``added_mib`` shows the instrument resolves an allocation of known size.

``added_is`` says what ``added_mib`` is, because the peak is resettable only on Linux:

| Platform | Source | ``added_is`` |
|---|---|---|
| Linux | ``VmRSS``/``VmHWM`` in ``/proc/self/status``, peak reset through ``/proc/self/clear_refs`` | ``exact`` |
| Windows | ``WorkingSetSize``/``PeakWorkingSetSize``, which cannot be reset | ``exact`` when the peak rose during the operation, else ``upper bound``: the operation stayed below the peak the imports and inputs reached |
| macOS, or Linux without ``/proc`` | ``ru_maxrss`` alone, no current size | ``lower bound``: memory reused below the earlier peak is not seen |

``ru_maxrss`` is only a fallback. On Linux it also carries the peak of the process that spawned
the child, because ``exec`` keeps the pre-exec high-water mark: under a large parent it reports
no growth at all.

No threshold is applied: the record is the cost measured before a release. The release gate
runs this without ``--write``; the committed record is refreshed before the closure pass.

    python scripts/measure_peak_memory.py            # print the record
    python scripts/measure_peak_memory.py --write    # also write artifacts/benchmarks/peak_memory.json
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORD_PATH = REPO_ROOT / "artifacts" / "benchmarks" / "peak_memory.json"
MIB = 2 ** 20
CONTROL_BYTES = 256 * MIB
PROC_STATUS = "/proc/self/status"
PROC_CLEAR_REFS = "/proc/self/clear_refs"


def _proc_status_bytes() -> Optional[Tuple[int, int]]:
    """``(VmRSS, VmHWM)`` in bytes from ``/proc/self/status``, or None where it is absent."""
    try:
        with open(PROC_STATUS, encoding="ascii") as fh:
            fields = dict(line.split(":", 1) for line in fh if ":" in line)
        # The file says "kB" and means KiB.
        return int(fields["VmRSS"].split()[0]) * 1024, int(fields["VmHWM"].split()[0]) * 1024
    except (OSError, KeyError, ValueError):
        return None


def reset_peak() -> bool:
    """Reset this process's peak resident size to its current one; False where impossible.

    Linux only: writing 5 to ``/proc/self/clear_refs`` resets ``VmHWM`` (kernel 4.0 on).
    Windows has no reset for ``PeakWorkingSetSize``, and ``ru_maxrss`` has none anywhere.
    """
    if not sys.platform.startswith("linux") or _proc_status_bytes() is None:
        return False
    try:
        with open(PROC_CLEAR_REFS, "wb") as fh:
            fh.write(b"5")
    except OSError:
        return False
    return True


def resident_bytes() -> Tuple[Optional[int], int]:
    """``(current, peak)`` resident set size of this process in bytes; current is None when
    only ``ru_maxrss`` is available."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        get_info = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if not get_info(handle, ctypes.byref(counters), counters.cb):
            raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
        return int(counters.WorkingSetSize), int(counters.PeakWorkingSetSize)
    status = _proc_status_bytes()
    if status is not None:
        return status
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return None, int(peak) if sys.platform == "darwin" else int(peak) * 1024  # Linux: KiB


def sample(run: Callable[[], object]) -> dict:
    """Run ``run`` once and return the resident sizes around it, in bytes."""
    _, peak_start = resident_bytes()
    reset = reset_peak()
    current, before = resident_bytes()
    run()
    _, after = resident_bytes()
    return {"peak_start": peak_start, "reset": reset, "current": current,
            "before": before, "after": after}


def added_bytes(s: dict) -> Tuple[int, str]:
    """What the operation added above the resident size before it, and what that number is."""
    if s["current"] is None:
        return s["after"] - s["before"], "lower bound"
    if s["reset"] or s["after"] > s["before"]:
        return s["after"] - s["current"], "exact"
    return s["before"] - s["current"], "upper bound"


def _control(rng):
    import numpy as np

    def run():
        block = np.ones(CONTROL_BYTES // 8)
        return float(block[::4096].sum())

    return run


def _complex_tfr(rng):
    import numpy as np
    import jnwb

    data = rng.normal(size=(16, 4000))
    return lambda: jnwb.complex_tfr(data, fs=1000.0, freqs=np.linspace(4.0, 80.0, 40))


def _multitaper_psd(rng):
    import jnwb

    data = rng.normal(size=(64, 8192))
    return lambda: jnwb.compute_multitaper_psd(data, fs=1000.0)


def _bandpass_filter(rng):
    import jnwb

    data = rng.normal(size=(64, 60000))
    return lambda: jnwb.bandpass_filter(data, fs=1000.0, low_cut=8.0, high_cut=40.0)


def _wpli(rng):
    import jnwb

    x, y = rng.normal(size=(2, 600000))
    return lambda: jnwb.wpli(x, y, fs=1000.0)


def _cluster_permutation_test(rng):
    import jnwb

    x, y = rng.normal(size=(2, 20, 500))
    return lambda: jnwb.cluster_permutation_test(x, y, n_permutations=200, rng=0)


def _jrsa(rng):
    import jnwb

    x1, x2 = rng.normal(size=(2, 200, 40))
    return lambda: jnwb.jrsa(x1, x2, permutations=200, null="iid", rng=0)


#: The fixed set. Adding, removing or resizing one changes what the record measures, so the
#: record names the set it was taken with.
OPERATIONS: Dict[str, Callable] = {
    "control_256mib": _control,
    "complex_tfr_16x4000_40freqs": _complex_tfr,
    "compute_multitaper_psd_64x8192": _multitaper_psd,
    "bandpass_filter_64x60000": _bandpass_filter,
    "wpli_600000": _wpli,
    "cluster_permutation_test_20x500_200perm": _cluster_permutation_test,
    "jrsa_200x40_200perm": _jrsa,
}


def _child(name: str, prepeak_mib: int = 0) -> None:
    """Run one operation in this process and print its resident sizes around it, as JSON.

    ``prepeak_mib`` touches and frees that much first, so a test can put the peak above the
    operation's before it runs, as a large import would.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import numpy as np
    import jnwb

    run = OPERATIONS[name](np.random.default_rng(0))
    if prepeak_mib:
        block = b"\x01" * (prepeak_mib * MIB)
        del block
    out = sample(run)
    out.update(jnwb=jnwb.__file__, version=jnwb.__version__)
    print(json.dumps(out))


def measure(name: str, prepeak_mib: int = 0) -> Dict[str, object]:
    """``{"peak_mib", "added_mib", "added_is"}`` for one operation, from a process of its own."""
    command = [sys.executable, str(Path(__file__).resolve()), "--child", name]
    if prepeak_mib:
        command += ["--prepeak-mib", str(prepeak_mib)]
    proc = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{name} failed in its child process:\n{proc.stderr[-2000:]}")
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    package = Path(out["jnwb"]).resolve()
    if REPO_ROOT not in package.parents:
        raise RuntimeError(f"{name} measured jnwb from {package}, not from this checkout")
    added, added_is = added_bytes(out)
    return {"peak_mib": round(max(out["peak_start"], out["after"]) / MIB, 1),
            "added_mib": round(added / MIB, 1),
            "added_is": added_is,
            "version": out["version"]}


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def build_record() -> dict:
    rows = {name: measure(name) for name in OPERATIONS}
    versions = {row.pop("version") for row in rows.values()}
    if len(versions) != 1:
        raise RuntimeError(f"the children imported different jnwb versions: {versions}")
    head = _git("rev-parse", "HEAD") or None
    return {
        "jnwb_version": versions.pop(),
        "commit": head,
        "working_tree_clean": (_git("status", "--porcelain") == "") if head else None,
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
        "unit": "MiB",
        "operations": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help=f"write {RECORD_PATH.name}")
    parser.add_argument("--child", choices=sorted(OPERATIONS), help=argparse.SUPPRESS)
    parser.add_argument("--prepeak-mib", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child:
        _child(args.child, args.prepeak_mib)
        return 0
    record = build_record()
    width = max(map(len, OPERATIONS))
    print(f"Peak RSS, jnwb {record['jnwb_version']}, Python {record['python']}, "
          f"{record['platform']}")
    for name, row in record["operations"].items():
        print(f"  {name:<{width}}  peak {row['peak_mib']:8.1f} MiB  "
              f"added {row['added_mib']:8.1f} MiB ({row['added_is']})")
    if args.write:
        RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RECORD_PATH, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, indent=2) + "\n")
        print(f"wrote {RECORD_PATH.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
