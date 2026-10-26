"""Hand-kept process records, checked against their own counts and against the files that cite them.

Three checks, each run by a harness gate (`scripts/harness_gate.py`):

* The defect-class ledger (`artifacts/process/defect_classes.md`): each row's Seen count equals
  its number of ';'-separated instances.
* Every "Ruled <date>" citation under `artifacts/`, frozen receipts excepted, names a date that a
  dated file under `artifacts/rulings/` records, or a date before the first dated file that
  `history.md` holds.
* The generated rows of `artifacts/state.md` (worktrees, local branches, open defect classes)
  appear in it verbatim, so the file is stale or edited by hand when they do not.

Matching a citation to its row inside a dated file stays a review step: a citation names a date.
The state rows come from this checkout's git data, as the generator writes them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from scripts import reconstruct_state as _state

REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path("artifacts/process/defect_classes.md")
DATED_DIR = Path("artifacts/rulings")
HISTORY = DATED_DIR / "history.md"
STATE = Path("artifacts/state.md")
#: Receipts are dated and frozen; they cite what was true when written.
FROZEN = ("artifacts/evidence/", "artifacts/archive/", "artifacts/benchmarks/")
CITATION = re.compile(r"\b[Rr]uled (?:on )?(20\d\d-\d\d-\d\d)")


def _cells(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def ledger_rows(text: str) -> List[Tuple[str, int, int]]:
    """(class, Seen, instance count) for each ledger row whose Seen cell is a number."""
    rows = []
    for line in text.splitlines():
        cells = _cells(line)
        if len(cells) < 3 or not cells[1].isdigit():
            continue
        instances = [part for part in re.split(r";\s*", cells[2]) if part]
        rows.append((cells[0].split(":")[0], int(cells[1]), len(instances)))
    return rows


def ledger_violations(root: Path = REPO_ROOT) -> List[str]:
    """Rows whose Seen count differs from their instances; a missing or empty ledger fails."""
    path = root / LEDGER
    if not path.is_file():
        return [f"{LEDGER.as_posix()} is absent, so its counts cannot be shown to match"]
    rows = ledger_rows(path.read_text(encoding="utf-8"))
    if not rows:
        return [f"{LEDGER.as_posix()} holds no row with a Seen count, so nothing was recounted"]
    return [f"{name}: Seen {seen}, {count} instances (separate instances with ';')"
            for name, seen, count in rows if seen != count]


def _artifact_texts(root: Path) -> Dict[str, str]:
    texts = {}
    for path in sorted((root / "artifacts").rglob("*.md")):
        name = path.relative_to(root).as_posix()
        if not name.startswith(FROZEN):
            texts[name] = path.read_text(encoding="utf-8")
    return texts


def citations(root: Path = REPO_ROOT) -> List[Tuple[str, str]]:
    """(file, date) for each "Ruled <date>" citation in the artifacts that are not frozen."""
    found = {(name, date) for name, text in _artifact_texts(root).items()
             for date in CITATION.findall(text)}
    return sorted(found)


def citation_violations(root: Path = REPO_ROOT) -> List[str]:
    """Citations of a date no dated file records; no dated file or no citation is a finding."""
    dated = {path.stem for path in (root / DATED_DIR).glob("20*.md")}
    if not dated:
        return [f"no dated file under {DATED_DIR.as_posix()}/, so no citation is shown recorded"]
    cited = citations(root)
    if not cited:
        return ["no citation read under artifacts/, so the pattern would pass anything"]
    history = (root / HISTORY).read_text(encoding="utf-8") if (root / HISTORY).is_file() else ""
    first = min(dated)
    return [f"{name} cites {date}, which no dated file under {DATED_DIR.as_posix()}/ records"
            for name, date in cited
            if date not in dated and not (date < first and date in history)]


def generated_rows() -> List[str]:
    """The state rows this checkout's git data generates: worktrees, branches, open classes."""
    return [*_state.worktree_rows(), *_state.branch_rows(),
            f"| Open defect classes | {_state.open_defect_classes()} |"]


def unnamed_rows(text: str, rows: Iterable[str]) -> List[str]:
    """Each generated row the state text does not carry verbatim."""
    return [f"{STATE.as_posix()} does not carry the generated row {row!r}: it is stale or was "
            "edited by hand. Run: python scripts/reconstruct_state.py"
            for row in rows if row not in text]


def awareness_violations(root: Path = REPO_ROOT) -> List[str]:
    """The state file's generated rows; an absent file passes, as gate 20 reads it (untracked)."""
    path = root / STATE
    if not path.is_file():
        return []
    return unnamed_rows(path.read_text(encoding="utf-8"), generated_rows())
