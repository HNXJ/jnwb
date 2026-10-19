"""`docs/api.md` lists the experimental submodules apart, with no stability promise."""
from __future__ import annotations

from pathlib import Path

import jnwb
from scripts.generate_api_md import EXPERIMENTAL_SUBMODULES, generate_api_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_the_experimental_submodules_stay_outside_all():
    assert EXPERIMENTAL_SUBMODULES == ("bilinear", "nam")
    assert not set(EXPERIMENTAL_SUBMODULES) & set(jnwb.__all__)


def test_the_page_lists_them_after_the_public_surface_with_no_stability_promise():
    text = generate_api_markdown(REPO_ROOT)
    head, sep, section = text.partition("## Experimental")
    assert sep, "the page has no Experimental section"
    assert "no stability promise" in section
    for name in EXPERIMENTAL_SUBMODULES:
        assert f"| jnwb.{name} | module |" in section
        assert f"| jnwb.{name} |" not in head
