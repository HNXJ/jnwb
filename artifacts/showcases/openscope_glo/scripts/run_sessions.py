"""Run a per-session script over all 14 sessions in parallel; one log per session.

Usage: python scripts/run_sessions.py SCRIPT N_PROCESSES [extra args...]
Each session runs as `python SCRIPT SESSION_ID [extra args]` in its own process, so a
failure in one session leaves the others' results in place.
"""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from glo_common import RESULTS, assets

script, n = sys.argv[1], int(sys.argv[2])
extra = sys.argv[3:]
logs = RESULTS / "logs"
logs.mkdir(parents=True, exist_ok=True)
env_note = "_".join([Path(script).stem, *extra])


def run(ses):
    with open(logs / f"{env_note}_{ses}.log", "w") as f:
        rc = subprocess.run([sys.executable, "-u", script, ses, *extra], stdout=f, stderr=subprocess.STDOUT,
                            cwd=Path(__file__).parent).returncode
    print(ses, "rc", rc, flush=True)
    return rc


with ThreadPoolExecutor(n) as ex:
    rcs = list(ex.map(run, sorted(assets())))
print("done", sum(r == 0 for r in rcs), "of", len(rcs), flush=True)
