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

VERSION_IN_PROSE = re.compile(r"\b0\.\d+\.\d+\b")


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
    ("docs/03_representational_similarity_jrsa.md", "From 0.2.7 `null=`"),
    ("docs/03_representational_similarity_jrsa.md", "is planned for 0.2.7."),
}


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
