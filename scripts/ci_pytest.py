"""Run the suite as CI does and print one GitHub ``::error`` line per failed test.

The public Actions API serves annotations without a login and job logs only with one, so a red
run names its failing tests there.  The exit status is pytest's own.
Usage: ``python scripts/ci_pytest.py [pytest arguments]``; no arguments runs ``tests/``.
"""
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def failures(path):
    """Return ``(test id, first line of its message)`` for each failed or errored test."""
    out = []
    for case in ET.parse(path).getroot().iter("testcase"):
        for kind in ("failure", "error"):
            node = case.find(kind)
            if node is not None:
                test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
                message = (node.get("message") or node.text or "").strip().splitlines()
                out.append((test_id, message[0] if message else kind))
                break
    return out


def main(argv):
    junit = Path(tempfile.gettempdir()) / "jnwb_ci_junit.xml"
    args = argv[1:] or ["tests/"]
    junit.unlink(missing_ok=True)
    rc = subprocess.call([sys.executable, "-m", "pytest", "-v", "-n", "auto",
                          f"--junitxml={junit}", *args])
    if rc != 0 and junit.exists():
        found = failures(junit)
        for test_id, message in found:
            title = test_id.replace("::", " > ")  # "::" would end the annotation's parameter list
            print(f"::error title={title}::{message[:300]}".replace("\r", " "))
        print(f"{len(found)} failed test(s) annotated")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
