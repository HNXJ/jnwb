"""Publication visibility gate for the analysis atlas.

Every artifact that could reach a public deployment carries exactly one label:

    private  -- never leaves this machine (raw data, identifier maps, machine-local paths)
    review   -- internal scientific review only; the DEFAULT for anything new
    public   -- cleared for the generated GitHub Pages deployment

The gate is FAIL-CLOSED in both directions:

  * an artifact the builder is asked to publish that carries no label is REFUSED
    (absence of a label is never read as permission);
  * an artifact declared here but missing on disk is REFUSED
    (a stale manifest must not silently shrink the site -- registries go stale quietly).

This module is a .py file rather than a JSON/CSV manifest on purpose: the repository .gitignore
ignores *.json and *.csv globally, so a data-format manifest would need a gitignore exception to
be tracked, and an untracked visibility manifest is a gate that does not survive a fresh clone.
"""

from __future__ import annotations

import os

PRIVATE = "private"
REVIEW = "review"
PUBLIC = "public"
LEVELS = (PRIVATE, REVIEW, PUBLIC)

#: Anything not named here is treated as REVIEW (the fail-closed default) and never published.
DEFAULT_VISIBILITY = REVIEW

# ---------------------------------------------------------------------------------------------
# The declared manifest. Paths are relative to omission/atlas/.
#
# Analysis 6A status: REVIEWED SCIENTIFIC ANALYSIS, not a finalized manuscript result. The public
# label here clears an artifact for deployment; it does not promote a claim's scientific standing.
# ---------------------------------------------------------------------------------------------
ARTIFACTS: dict[str, str] = {
    # --- canonical public tables: derived from receipts, identifiers anonymized -------------
    "tables/analysis6a_spk_resolved_public.csv": PUBLIC,
    "tables/analysis6a_spk_census_public.csv": PUBLIC,
    "tables/analysis6a_spk_session_stats_public.csv": PUBLIC,
    "tables/analysis6a_lfp_frequency_public.csv": PUBLIC,
    "tables/analysis6a_lfp_session_stats_public.csv": PUBLIC,
    "tables/analysis6a_lfp_censoring_public.csv": PUBLIC,
    "tables/analysis6a_dsp_temporal_support_public.csv": PUBLIC,
    "tables/analysis6a_coverage_public.csv": PUBLIC,
    "tables/analysis6a_session_tests_public.csv": PUBLIC,
    "tables/provenance.json": PUBLIC,

    # --- static publication figures (SVG only; PNG companions stay local) -------------------
    "figures/fig6a_A_spk_latency.svg": PUBLIC,
    "figures/fig6a_B_lfp_resolvability.svg": PUBLIC,
    "figures/fig6a_C_session_level_tests.svg": PUBLIC,
    "figures/fig6a_D_coverage.svg": PUBLIC,

    # --- private: must never be copied, scanned for explicitly ------------------------------
    "_private/identifier_map.json": PRIVATE,
}

#: Held pending separate scientific authorization -- declared so the gate has an opinion about it
#: rather than silently defaulting, and so a future build cannot publish it by accident.
HELD: dict[str, str] = {
    "figures/fig6a_E_common_axis_spk_vs_lfp.svg": REVIEW,
}


class VisibilityError(RuntimeError):
    """Raised when the gate refuses to publish something."""


def visibility_of(relpath: str) -> str:
    """Return the declared label, or the fail-closed default for an undeclared artifact."""
    rel = relpath.replace(os.sep, "/")
    if rel in ARTIFACTS:
        return ARTIFACTS[rel]
    if rel in HELD:
        return HELD[rel]
    return DEFAULT_VISIBILITY


def assert_publishable(relpath: str) -> None:
    """Refuse anything not explicitly labelled public."""
    v = visibility_of(relpath)
    if v not in LEVELS:
        raise VisibilityError(f"REFUSED: {relpath!r} carries invalid visibility {v!r}")
    if v != PUBLIC:
        raise VisibilityError(
            f"REFUSED: {relpath!r} is {v!r}, not {PUBLIC!r}. "
            "Undeclared artifacts default to 'review' and are never published."
        )


def public_artifacts(root: str) -> list[str]:
    """Every declared-public artifact, verified present on disk.

    A declared artifact missing from disk is an error, not an omission: a stale manifest that
    quietly drops a figure would produce a site that looks complete and is not.
    """
    out, missing = [], []
    for rel, vis in sorted(ARTIFACTS.items()):
        if vis != PUBLIC:
            continue
        if not os.path.exists(os.path.join(root, rel)):
            missing.append(rel)
        else:
            out.append(rel)
    if missing:
        raise VisibilityError(
            "REFUSED: declared-public artifacts are missing from disk: " + ", ".join(missing)
        )
    return out


def audit_undeclared(root: str, scan_dirs=("tables", "figures")) -> list[str]:
    """Files present in the publishable source directories that carry no declaration.

    These are not published (the default is 'review'), but they are reported so a new artifact
    cannot sit unnoticed in a directory the builder reads from.
    """
    found = []
    for d in scan_dirs:
        base = os.path.join(root, d)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            rel = f"{d}/{name}"
            if os.path.isfile(os.path.join(base, name)) and rel not in ARTIFACTS:
                found.append(rel)
    return found
