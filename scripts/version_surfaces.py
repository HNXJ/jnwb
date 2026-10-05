"""The places a release version is written, in one list.

`scripts/bump_version.py` rewrites them and `tests/test_prose_version_claims_are_live.py`,
`tests/test_bump_version.py` and `problems()` below check them; none keeps a copy.

- `PINNED_CLAIMS`: sentences in prose that name the checkout version.
- `__version__` and `__release_date__` in `jnwb/__init__.py`.
- the import profile and its breakdown, which `scripts/benchmark_import.py --write` generates.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (file, the exact sentence, with the live version substituted in)
PINNED_CLAIMS = [
    ("README.md", "This checkout is `{version}`."),
    ("docs/agents.md",
     "jnwb.SKILLS_URL  # 'https://github.com/HNXJ/jnwb/tree/v{version}/skills'"),
]

INIT = "jnwb/__init__.py"
VERSION_RE = re.compile(rb"^(__version__ = (['\"]))([^'\"]+)(\2)", re.M)
DATE_RE = re.compile(rb"^(__release_date__ = (['\"]))([^'\"]+)(\2)", re.M)
PROFILE = "artifacts/benchmarks/import_profile.txt"
BREAKDOWN = "artifacts/benchmarks/import_breakdown.json"
PROFILE_RE = re.compile(r"^- jnwb (\S+) \(\d+ public symbols\)", re.M)

# Files whose `jnwb==X.Y.Z` pins gate 10 compares with the package version.
PIN_FILES = ["README.md"]


def read_init(root: Path = REPO_ROOT) -> tuple[str, str]:
    """(`__version__`, `__release_date__`) as written in `root`, without importing it."""
    data = (root / INIT).read_bytes()
    v, d = VERSION_RE.search(data), DATE_RE.search(data)
    if v is None or d is None:
        raise ValueError(f"{INIT} does not bind both __version__ and __release_date__")
    return v.group(3).decode(), d.group(3).decode()


def problems(root: Path = REPO_ROOT) -> list[str]:
    """Every surface of `root` that does not carry the version `root`'s `__init__` states."""
    version, date = read_init(root)
    out = []
    for rel, template in PINNED_CLAIMS:
        text = (root / rel).read_bytes().decode("utf-8")
        if template.format(version=version) not in text:
            out.append(f"{rel} lacks {template.format(version=version)!r}")
    m = PROFILE_RE.search((root / PROFILE).read_text(encoding="utf-8"))
    if m is None or m.group(1) != version:
        out.append(f"{PROFILE} names {m.group(1) if m else None}, not {version}")
    payload = json.loads((root / BREAKDOWN).read_text(encoding="utf-8"))
    if payload.get("version") != version:
        out.append(f"{BREAKDOWN} names {payload.get('version')}, not {version}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        out.append(f"__release_date__ {date!r} is not YYYY-MM-DD")
    return out
