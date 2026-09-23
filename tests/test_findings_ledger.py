"""The 0.2.6 findings ledger resolves every imported review identifier, exactly once.

`artifacts/archive/0.2.5/alignment_review_0.2.5.md` carries 83 findings with stable identifiers of the form
``<dimension>/<id>``. `artifacts/evidence/0.2.6/findings_0.2.6.md` carries an index table mapping each identifier
to one disposition. This module extracts both sets mechanically and asserts they are equal, so a
finding cannot disappear by being dropped from the ledger.

Both identifier sets are parsed from the files. Neither is transcribed here: a hand-copied list
would go stale the moment either file moved.
"""

import pathlib
import re

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
REVIEW_PATH = ROOT_DIR / "artifacts" / "archive" / "0.2.5" / "alignment_review_0.2.5.md"
LEDGER_PATH = ROOT_DIR / "artifacts" / "evidence" / "0.2.6" / "findings_0.2.6.md"

#: The only dispositions the ledger may assign.
DISPOSITIONS = frozenset(
    {"reproduced", "refuted", "stale", "already repaired", "deferred"}
)

#: The review's own header states 31 confirmed + 12 upheld with dissent + 36 unverified + 4
#: refuted. A change to this number is a change to the imported evidence, not to this check.
EXPECTED_FINDING_COUNT = 83

_SECTION_RE = re.compile(r"^## (?P<title>.+?)\s*$")
_FINDING_RE = re.compile(r"^### (?P<identifier>[a-z0-9-]+/[a-z0-9-]+)\s*$")
_INDEX_ROW_RE = re.compile(r"^\|\s*`(?P<identifier>[^`]+)`\s*\|\s*(?P<disposition>[^|]+?)\s*\|\s*$")


def _read(path):
    assert path.exists(), f"missing file: {path}"
    return path.read_text(encoding="utf-8")


def review_identifiers():
    """Every ``### <dimension>/<id>`` heading in the imported review, in file order."""
    found = []
    for line in _read(REVIEW_PATH).splitlines():
        match = _FINDING_RE.match(line)
        if match:
            found.append(match.group("identifier"))
    return found


def ledger_index():
    """The ledger's index table as ``[(identifier, disposition), ...]``, in file order.

    Only rows inside the ``## Index`` section count. Other tables in the file also use
    backticked first cells, and a parser that swept the whole file would read them too.
    """
    rows = []
    in_index = False
    for line in _read(LEDGER_PATH).splitlines():
        section = _SECTION_RE.match(line)
        if section:
            in_index = section.group("title") == "Index"
            continue
        if not in_index:
            continue
        match = _INDEX_ROW_RE.match(line)
        if match:
            rows.append((match.group("identifier"), match.group("disposition")))
    return rows


def ledger_prose_dispositions():
    """``{identifier: disposition}`` from the per-entry prose, not from the index table.

    An entry is ``### <identifier>`` followed by a ``- Disposition: <value>`` line. The value
    runs to the first comma or full stop, so ``deferred, for the reason above`` reads as
    ``deferred``. Entries listed by identifier only, such as the unverified tail, have no prose
    line and do not appear here.
    """
    prose = {}
    current = None
    for line in _read(LEDGER_PATH).splitlines():
        heading = _FINDING_RE.match(line)
        if heading:
            current = heading.group("identifier")
            continue
        if current is None:
            continue
        match = re.match(r"^- Disposition:\s*(?P<disposition>[^,.]+)", line)
        if match:
            prose[current] = match.group("disposition").strip()
            current = None
    return prose


def test_prose_and_index_agree_on_every_disposition():
    """The index is the machine-checked surface; the prose is what a reader believes.

    Nothing related the two, so an index row could say ``reproduced`` while its own entry said
    ``already repaired`` and every check still passed. An independent verifier demonstrated
    exactly that mutation surviving on 2026-09-19.
    """
    index = dict(ledger_index())
    disagreements = sorted(
        f"{identifier}: index says {index[identifier]!r}, entry says {disposition!r}"
        for identifier, disposition in ledger_prose_dispositions().items()
        if identifier in index and index[identifier] != disposition
    )
    assert not disagreements, (
        f"{len(disagreements)} ledger entr(ies) contradict their own index row: {disagreements}"
    )


def test_every_prose_entry_is_in_the_index():
    orphans = sorted(set(ledger_prose_dispositions()) - {i for i, _ in ledger_index()})
    assert not orphans, f"entries with no index row: {orphans}"


def test_review_identifiers_are_extractable_and_unique():
    identifiers = review_identifiers()
    assert len(identifiers) == EXPECTED_FINDING_COUNT, (
        f"expected {EXPECTED_FINDING_COUNT} findings in {REVIEW_PATH.name}, "
        f"parsed {len(identifiers)}"
    )
    duplicates = sorted({i for i in identifiers if identifiers.count(i) > 1})
    assert not duplicates, f"review identifiers are not unique: {duplicates}"


def test_ledger_index_is_parseable_and_unique():
    rows = ledger_index()
    assert rows, f"no index rows parsed from {LEDGER_PATH.name}"
    identifiers = [identifier for identifier, _ in rows]
    duplicates = sorted({i for i in identifiers if identifiers.count(i) > 1})
    assert not duplicates, f"ledger lists an identifier more than once: {duplicates}"


def test_every_disposition_is_one_of_the_five():
    unknown = sorted(
        {
            f"{identifier} -> {disposition!r}"
            for identifier, disposition in ledger_index()
            if disposition not in DISPOSITIONS
        }
    )
    assert not unknown, f"disposition outside the allowed set: {unknown}"


def test_identifier_sets_match():
    """The acceptance condition of todo stack item 06-03.

    Deleting one ledger row fails this; so does adding a row for an identifier the review does
    not carry.
    """
    reviewed = set(review_identifiers())
    ledgered = {identifier for identifier, _ in ledger_index()}

    missing = sorted(reviewed - ledgered)
    invented = sorted(ledgered - reviewed)

    assert not missing, (
        f"{len(missing)} review finding(s) resolve to no disposition in "
        f"{LEDGER_PATH.name}: {missing}"
    )
    assert not invented, (
        f"{len(invented)} ledger row(s) name an identifier absent from "
        f"{REVIEW_PATH.name}: {invented}"
    )
    assert reviewed == ledgered
