"""A version written into prose goes stale silently; the ones that exist are pinned here.

The 0.2.5 bump moved `jnwb.__version__`, and the suite caught the receipts that carry a
version as data: the import profile, the import breakdown and the `SKILLS_URL` example in
`docs/agents.md` all failed until they were regenerated or corrected. `README.md` said "This
checkout is `0.2.4`" and nothing failed, because no test read it. It was found by grep, which
is not a gate.

These are claims a reader acts on -- someone comparing a clone against what PyPI serves --
so they are checked against `jnwb.__version__` rather than against each other. The last test
is the one that matters over time: it fails when a new prose version claim appears anywhere
in the documentation without being added here, so the next one cannot be missed the same way.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]

# (file, the exact sentence, with the live version substituted in)
PINNED_CLAIMS = [
    ("README.md", "This checkout is `{version}`."),
    ("docs/agents.md",
     "jnwb.SKILLS_URL  # 'https://github.com/HNXJ/jnwb/tree/v{version}/skills'"),
]

# Files whose version mentions are history rather than claims about this release: a changelog
# records what past versions did, and an audit note names the version it audited.
HISTORICAL = {"CHANGELOG.md", "AGENTS.md"}

# Four parts as well as three: with three, a patch release such as 0.2.6.1 read as 0.2.6.
VERSION_IN_PROSE = re.compile(r"\b0\.\d+\.\d+(?:\.\d+)?\b")


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


LIVE = _version_tuple(jnwb.__version__)


@pytest.mark.parametrize("rel,template", PINNED_CLAIMS,
                         ids=[rel for rel, _ in PINNED_CLAIMS])
def test_the_claim_names_the_live_version(rel: str, template: str):
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    expected = template.format(version=jnwb.__version__)
    assert expected in text, (
        f"{rel} does not carry {expected!r}. If the sentence was reworded, update the "
        f"template here; if the version was bumped, update {rel}."
    )


@pytest.mark.parametrize("rel,template", PINNED_CLAIMS,
                         ids=[rel for rel, _ in PINNED_CLAIMS])
def test_the_claim_names_no_other_version(rel: str, template: str):
    """The live sentence being present does not mean a stale one was removed."""
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    live = template.format(version=jnwb.__version__)
    prefix = template.split("{version}")[0].strip()
    stale = []
    for line in text.splitlines():
        if not prefix or prefix not in line:
            continue
        # Remove the live claim before looking, rather than accepting the line because the
        # live claim is somewhere on it: a stale copy on the same line would otherwise be
        # excused by the correct one standing next to it.
        remainder = line.replace(live, "")
        if prefix in remainder or VERSION_IN_PROSE.search(remainder):
            stale.append(line.strip())
    assert not stale, f"{rel} still carries a version claim for another release: {stale}"


# Mentions that are history, not claims about this release, and are correct precisely
# because they name an old version: a deprecation happened in 0.1.7 and stays having
# happened in 0.1.7. Listed one by one rather than matched by a pattern, because "deprecated
# in 0.1.7" and "this checkout is 0.1.7" are the same shape and opposite in meaning.
HISTORICAL_MENTIONS = {
    ("docs/08_directed_connectivity_and_information.md",
     "`granger_causality` (dict return type) is deprecated in 0.1.7"),
    ("docs/install.md", "## Deferred imports (0.1.6+)"),
    ("docs/10_operation_specifications.md", "until 0.2.5 and named the minority"),
    ("docs/03_representational_similarity_jrsa.md", "Before 0.2.6.1 every metric used"),
}

# Mentions of a version not yet released: a plan or a removal date. Each is excused only while
# the live version is below it; once the version reaches it the note is either done, and
# rewritten as history, or late, and the release is not what the note promised.
FORWARD_MENTIONS: dict[tuple[str, str], str] = {}

# The same two lists for string literals in `jnwb/`: docstrings, and the messages a warning or
# an error prints. A mention at or below the live version is history there (a break note, a
# since-note) and is not listed. Above it, a note is either a plan or removal date, which
# expires when the version reaches it, or the record of a change the next release carries,
# which needs no declaration once that release is live.
SOURCE_FORWARD_MENTIONS: dict[tuple[str, str], str] = {}
SOURCE_UNRELEASED_RECORDS = {
    ("jnwb/laminar.py", "INTENTIONAL BREAK (0.2.7)"): "0.2.7",
    ("jnwb/laminar.py", "Before 0.2.7 the"): "0.2.7",
}

# A version after a comparison operator is a dependency requirement, not a jnwb release.
_REQUIREMENT = re.compile(r"(?:[<>=!~]=?)\s*$")


class TestNoUnpinnedProseVersionRemains:
    """The check that survives the next bump, rather than the two sentences that exist now.

    This cannot decide by itself whether a version in prose is stale: a since-note and a
    current-version claim read the same way and only one of them should move on a bump. So
    it pins the set instead. Every mention is either the live version, one of the claims
    above, or an entry in `HISTORICAL_MENTIONS` -- and a new one fails until somebody says
    which it is, which is the step that did not happen for `README.md`.
    """

    @pytest.mark.parametrize("rel", sorted(
        p.relative_to(REPO_ROOT).as_posix()
        for p in [REPO_ROOT / "README.md"] + list(REPO_ROOT.glob("docs/*.md"))
        if p.name not in HISTORICAL))
    def test_every_version_mention_is_live_pinned_or_declared_historical(self, rel: str):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        pinned_lines = {
            template.format(version=jnwb.__version__) for _, template in PINNED_CLAIMS
        }
        known = {snippet for path, snippet in HISTORICAL_MENTIONS if path == rel}
        known |= {snippet for (path, snippet), version in FORWARD_MENTIONS.items()
                  if path == rel and _version_tuple(version) > LIVE}
        offenders = []
        for lineno, line in enumerate(text.splitlines(), 1):
            # What is excused is the pinned text, not the line carrying it. Skipping the
            # whole line let a stale version sitting beside a correct one through both
            # this check and the per-claim one above.
            remainder = line
            for excused in (*pinned_lines, *known):
                remainder = remainder.replace(excused, "")
            for found in VERSION_IN_PROSE.findall(remainder):
                if found != jnwb.__version__:
                    offenders.append((lineno, found, line.strip()[:90]))
        assert not offenders, (
            f"{rel} names a version that is not {jnwb.__version__}: {offenders}. If it is a "
            f"claim about this release, bump it. If it is history -- a deprecation or a "
            f"since-note -- add it to HISTORICAL_MENTIONS."
        )

    def test_every_declared_historical_mention_is_still_there(self):
        """An allowlist outlives what it excuses; this is what stops it silently growing."""
        missing = [
            (rel, snippet) for rel, snippet in sorted(HISTORICAL_MENTIONS)
            if snippet not in (REPO_ROOT / rel).read_text(encoding="utf-8")
        ]
        assert not missing, f"HISTORICAL_MENTIONS excuses text that is gone: {missing}"


def _source_strings() -> dict[str, list[str]]:
    """Every string literal in `jnwb/`, by repository-relative path. f-string pieces count."""
    out: dict[str, list[str]] = {}
    for path in sorted((REPO_ROOT / "jnwb").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        out[path.relative_to(REPO_ROOT).as_posix()] = [
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
    return out


class TestForwardVersionNotesExpire:
    """A note about a release not yet made is true only until that release: "planned for",
    "removed in". It was excused permanently, so it would outlive the release it names."""

    ALL_FORWARD = {**FORWARD_MENTIONS, **SOURCE_FORWARD_MENTIONS}

    @pytest.mark.parametrize("key", sorted(ALL_FORWARD), ids=lambda k: f"{k[0]}:{k[1][:30]}")
    def test_the_named_version_is_still_ahead(self, key):
        version = self.ALL_FORWARD[key]
        assert version in key[1], f"{key} does not name the version it is filed under"
        assert _version_tuple(version) > LIVE, (
            f"{key[0]} still says {key[1]!r}, and the live version is {jnwb.__version__}. "
            f"Do what the note promised and rewrite it as history, or change the promise."
        )

    @pytest.mark.parametrize("key", sorted(SOURCE_UNRELEASED_RECORDS),
                             ids=lambda k: f"{k[0]}:{k[1][:30]}")
    def test_an_unreleased_record_is_declared_only_until_its_release(self, key):
        assert SOURCE_UNRELEASED_RECORDS[key] in key[1]
        assert _version_tuple(SOURCE_UNRELEASED_RECORDS[key]) > LIVE, (
            f"{key} names a released version and needs no declaration; remove the entry."
        )

    def test_every_declared_source_mention_is_still_there(self):
        strings = _source_strings()
        missing = [
            key for key in sorted({**SOURCE_FORWARD_MENTIONS, **SOURCE_UNRELEASED_RECORDS})
            if not any(key[1] in s for s in strings.get(key[0], []))
        ]
        assert not missing, f"declared version mentions no longer in jnwb/: {missing}"

    def test_no_undeclared_future_version_in_a_docstring_or_message(self):
        declared = {**SOURCE_FORWARD_MENTIONS, **SOURCE_UNRELEASED_RECORDS}
        offenders = []
        for rel, strings in _source_strings().items():
            known = [snippet for (path, snippet), version in declared.items()
                     if path == rel and _version_tuple(version) > LIVE]
            for s in strings:
                remainder = s
                for snippet in known:
                    remainder = remainder.replace(snippet, "")
                for m in VERSION_IN_PROSE.finditer(remainder):
                    if _REQUIREMENT.search(remainder[:m.start()]):
                        continue
                    if _version_tuple(m.group()) > LIVE:
                        line = remainder[max(0, m.start() - 40):m.end() + 20]
                        offenders.append((rel, m.group(), " ".join(line.split())))
        assert not offenders, (
            f"version(s) above {jnwb.__version__} in jnwb/ strings that no list declares: "
            f"{offenders}. A plan or removal date goes in SOURCE_FORWARD_MENTIONS; the record "
            f"of a change the next release carries goes in SOURCE_UNRELEASED_RECORDS."
        )

    def test_the_scan_reads_four_part_versions(self):
        """The guard on the pattern itself: 0.2.6.1 is one version, not 0.2.6."""
        assert VERSION_IN_PROSE.findall("since 0.2.6.1, before 0.2.7.") == ["0.2.6.1", "0.2.7"]
