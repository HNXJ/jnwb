"""A bare `rng.permutation(y)` inside grouped omission-identity decoding is exactly the bug
this project already shipped once (omission.jnwb_ext.omission_identity.decode_identity_cycle_deconfound's
null ignored cycle grouping -- see artifacts/.lab/agent-harness-audit-20260810.json,
claim-p0-deconfound-null-ignores-cycle-grouping). Every label-permutation call in the
omission-identity decoding domain must go through jnwb.permutation.permute_labels, which forces
an explicit scheme, so this cannot recur silently under a different filename.

Scoped to the omission-identity decoding domain specifically (jnwb/omission_identity.py, the
scripts/*.py that build on it, and its quarantined historical siblings), not the whole repo --
jnwb/connectivity.py and jnwb/statistics.py have their own, separately-audited, within-session
shuffle-null conventions (see .claude/skills/jnwb-functional-connectivity/SKILL.md) that this
test does not police.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Files where a permutation call operates on omission-identity-style labels under a grouped/
# cycle-aware CV scheme, and must therefore go through permute_labels instead of a bare
# rng.permutation(...) / np.random.permutation(...).
SCOPED_FILES = [
    REPO_ROOT / "jnwb" / "omission_identity.py",
    REPO_ROOT / "jnwb" / "structured_identity.py",
    REPO_ROOT / "jnwb" / "structured_identity_m2a.py",
    REPO_ROOT / "scripts" / "compute_omission_identity_leakage_safe.py",
    REPO_ROOT / "scripts" / "compute_omission_identity_cycle_deconfound_v3.py",
    REPO_ROOT / "scripts" / "run_structured_identity_milestone2a.py",
]

# A bare call is one of these patterns appearing OUTSIDE jnwb/permutation.py itself.
BARE_PERMUTATION_RE = re.compile(r"\b\w*rng\w*\.permutation\(")


def _bare_permutation_lines(path: Path) -> list[tuple[int, str]]:
    if not path.is_file():
        return []
    hits = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if BARE_PERMUTATION_RE.search(line):
            hits.append((lineno, stripped))
    return hits


class TestNoBarePermutationInScopedDecodingFiles:
    @pytest.mark.parametrize("path", SCOPED_FILES, ids=lambda p: p.name)
    def test_no_bare_rng_permutation(self, path):
        hits = _bare_permutation_lines(path)
        # jnwb/permutation.py's own scheme="global" branch is the one legitimate bare call in
        # the whole scoped set; everything else scoped here does grouped/cycle-aware CV and
        # must route through permute_labels(..., scheme=...).
        assert not hits, (
            f"{path.relative_to(REPO_ROOT)} has bare rng.permutation(...) call(s) outside "
            f"jnwb.permutation.permute_labels: {hits}. Grouped omission-identity decoding must "
            f"name an explicit exchangeability scheme -- see jnwb/permutation.py."
        )

    def test_permutation_primitive_itself_is_the_only_global_scheme_site(self):
        """Sanity check the lint pattern actually fires -- a known-bare call should be caught."""
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("y_perm = rng.permutation(y)\n")
            tmp_path = Path(f.name)
        try:
            hits = _bare_permutation_lines(tmp_path)
            assert hits, "lint pattern failed to catch a known-bare rng.permutation(y) call"
        finally:
            tmp_path.unlink()
