"""Hand-kept process records, checked against their own counts and against the files that cite them.

Checks, each run by a harness gate (`scripts/harness_gate.py`):

* The defect-class ledger (`artifacts/process/defect_classes.md`): each row's Seen count equals
  its number of ';'-separated instances.
* Every "Ruled <date>" citation under `artifacts/`, frozen receipts excepted, names a date that a
  dated file under `artifacts/rulings/` records, or a date before the first dated file that
  `history.md` holds.
* A mapping table (a table with "Old location" and "Where now" columns) keeps the obligation
  words of its old rule file: "before", "after", "never", "must" and "only" in an old clause must
  appear in the closest clause of the draft its preamble names. Clauses are aligned as
  `scripts/obligation_diff.py` aligns them.
* A dated row may name a phrase it forbids, as a cell `Forbidden: "<phrase>"`; the phrase must not
  appear in tracked text outside the dated, archived and evidence trees.
* The generated rows of `artifacts/state.md` (worktrees, local branches, open defect classes)
  appear in it verbatim, so the file is stale or edited by hand when they do not. The newest dev
  run row is named there but not compared: it changes between runs.

Matching a citation to its row inside a dated file stays a review step: a citation names a date.
The state rows come from this checkout's git data, as the generator writes them.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from scripts import reconstruct_state as _state
from scripts.obligation_diff import WORD, clauses

REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path("artifacts/process/defect_classes.md")
DATED_DIR = Path("artifacts/rulings")
HISTORY = DATED_DIR / "history.md"
STATE = Path("artifacts/state.md")
#: Receipts are dated and frozen; they cite what was true when written.
FROZEN = ("artifacts/evidence/", "artifacts/archive/", "artifacts/benchmarks/")
CITATION = re.compile(r"\b[Rr]uled (?:on )?(20\d\d-\d\d-\d\d)")
#: The words a rewrite must keep: a rule that says "before" or "never" must still say it.
OBLIGATION_WORDS = frozenset({"before", "after", "never", "must", "only"})
#: A mapping table's preamble names its old file and the commit it was read at, then its draft.
OLD_FILE = re.compile(r"Old file:\s*`([^`]+)`\s+at\s+`([0-9a-fA-F]{7,40})`")
DRAFT = re.compile(r"Draft:\s*`([^`]+)`")
FORBIDDEN = re.compile(r'Forbidden:\s*"([^"]+)"')
#: Tracked text under these trees is not searched for a forbidden phrase.
NOT_SEARCHED = ("artifacts/rulings", "artifacts/archive", "artifacts/evidence")


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


def _git_show(rev: str, path: str) -> Optional[str]:
    """The text of ``path`` at commit ``rev``, or None when this repository cannot read it."""
    done = subprocess.run(["git", "-C", str(REPO_ROOT), "show", f"{rev}:{path}"],
                          capture_output=True)
    return done.stdout.decode("utf-8") if done.returncode == 0 else None


def _is_mapping_header(line: str) -> bool:
    return line.lstrip().startswith("|") and {"Old location", "Where now"} <= set(_cells(line))


def mapping_tables(root: Path = REPO_ROOT) -> List[Tuple[str, Optional[str], Optional[str],
                                                         Optional[str]]]:
    """(table file, old commit, old file, draft) for each mapping table under ``artifacts/``.

    A preamble field it does not name is None, and the check reports that rather than passing.
    """
    found = []
    for path in sorted((root / "artifacts").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if not any(_is_mapping_header(line) for line in text.splitlines()):
            continue
        old = OLD_FILE.search(text)
        draft = DRAFT.search(text)
        found.append((path.relative_to(root).as_posix(),
                      old.group(2) if old else None,
                      old.group(1) if old else None,
                      draft.group(1) if draft else None))
    return found


def obligation_losses(old: str, new: str) -> Tuple[int, List[Tuple[List[str], str, str]]]:
    """(old clauses carrying an obligation word, the words each lost clause lacks with its old
    clause and its closest new clause).

    An old clause that appears exactly in the new text is kept. Any other is compared with the new
    clause that shares the most words with it, as scripts/obligation_diff.py compares them.
    """
    new_clauses = clauses(new)
    exact = set(new_clauses)
    new_words = [(set(WORD.findall(c)), c) for c in new_clauses]
    read = 0
    lost = []
    for clause in clauses(old):
        words = set(WORD.findall(clause))
        needed = words & OBLIGATION_WORDS
        if not needed:
            continue
        read += 1
        if clause in exact:
            continue
        _, best = max(((len(words & w) / len(words | w), c) for w, c in new_words),
                      default=(0.0, ""))
        missing = sorted(needed - set(WORD.findall(best)))
        if missing:
            lost.append((missing, clause, best))
    return read, lost


def mapping_check(root: Path = REPO_ROOT,
                  read_old: Callable[[str, str], Optional[str]] = _git_show,
                  ) -> Tuple[int, int, List[str]]:
    """(mapping tables, obligation clauses read, violations) for each mapping table under root.

    ``read_old`` returns the old file at a commit, or None when it cannot be read. A table that
    names no old file, or whose old file or draft cannot be read, is a violation, never a pass.
    """
    tables = read = 0
    found: List[str] = []
    for table, rev, old_path, draft in mapping_tables(root):
        tables += 1
        unnamed = [name for name, value in (("old file", old_path), ("old commit", rev),
                                            ("draft", draft)) if not value]
        if unnamed:
            found.append(f"{table} names no {' or '.join(unnamed)} in its preamble, so its "
                         "obligation words cannot be read")
            continue
        old = read_old(rev, old_path)
        if old is None:
            found.append(f"{table}: {old_path} at {rev} cannot be read, so its obligation words "
                         "cannot be shown kept")
            continue
        if not (root / draft).is_file():
            found.append(f"{table}: draft {draft} is absent from the tree")
            continue
        count, lost = obligation_losses(old, (root / draft).read_text(encoding="utf-8"))
        read += count
        found += [f"{table}: {', '.join(missing)} lost from '{clause[:100]}' "
                  f"(closest new clause: '{best[:100]}')" for missing, clause, best in lost]
    return tables, read, found


def forbidden_in(text: str) -> List[str]:
    """The phrases a row names as forbidden: each cell ``Forbidden: "<phrase>"``."""
    return FORBIDDEN.findall(text)


def forbidden_sources(root: Path = REPO_ROOT) -> List[Tuple[str, str]]:
    """(dated file, phrase) for each phrase a dated file names as forbidden."""
    return [(path.relative_to(root).as_posix(), phrase)
            for path in sorted((root / DATED_DIR).glob("20*.md"))
            for phrase in forbidden_in(path.read_text(encoding="utf-8"))]


def forbidden_violations(sources: List[Tuple[str, str]], rev: Optional[str] = None,
                         root: Path = REPO_ROOT) -> List[str]:
    """Each line of tracked text that holds a named phrase, outside the trees NOT_SEARCHED.

    ``git grep`` reads tracked files only, of ``rev`` when it is given, so an untracked file is not
    searched. A grep that cannot read the tree is reported, not passed.
    """
    found: List[str] = []
    for source, phrase in sources:
        cmd = ["git", "-C", str(root), "grep", "-n", "-I", "-F", "-e", phrase]
        if rev:
            cmd.append(rev)
        cmd += ["--", ".", *(f":(exclude){tree}" for tree in NOT_SEARCHED)]
        done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if done.returncode not in (0, 1):  # git grep exits 1 for no match
            found.append(f"{source}: git grep could not read the tree for {phrase!r}: "
                         f"{done.stderr.strip()}")
            continue
        found += [f"{line} holds the phrase that {source} forbids: {phrase!r}"
                  for line in done.stdout.splitlines()]
    return found


def examined_counts(root: Path = REPO_ROOT) -> Tuple[int, int, int]:
    """(mapping tables, obligation clauses, forbidden phrases) the checks read; the PASS line names
    them, so a check that read nothing does not pass as if it had checked something."""
    tables, read, _ = mapping_check(root)
    return tables, read, len(forbidden_sources(root))
