"""The build job's archive manifest check, run from the workspace root (cwd)."""
import pathlib
import sys
import tarfile
import zipfile

sys.path.insert(0, ".")
from scripts.release_gate import forbidden_entries  # noqa: E402

whl = list(pathlib.Path("dist").glob("*.whl"))[0]
with zipfile.ZipFile(whl, "r") as z:
    problems = ["wheel: " + p for p in forbidden_entries(z.namelist())]
sdist = list(pathlib.Path("dist").glob("*.tar.gz"))[0]
with tarfile.open(sdist, "r:gz") as t:
    problems += ["sdist: " + p for p in forbidden_entries(t.getnames())]
if problems:
    for problem in problems:
        print("ERROR: " + problem)
    sys.exit(1)
print("PASS: Distribution manifests clean.")
