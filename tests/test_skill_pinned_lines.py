"""Skill sentences pinned to the code they describe. Each test reads the skill file itself.

Each test fails when its skill line reverts to the 0.2.16 wording (checked by restoring the old
file, running these tests, and restoring the new file).
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import jnwb

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def _text(rel: str) -> str:
    """The file as one line of single-spaced words, so wrapped sentences compare whole."""
    return " ".join((SKILLS / rel).read_text(encoding="utf-8").split())


def test_population_signature_in_skill_matches_code_order():
    text = _text("jnwb-population/SKILL.md")
    m = re.search(r"`jnwb\.compute_population_trajectory\(([^)]*)\)`", text)
    assert m, "the skill must state the compute_population_trajectory signature"
    stated = [tok.split("=")[0].strip() for tok in m.group(1).split(",") if tok.strip() != "*"]
    actual = [p.name for p in inspect.signature(jnwb.compute_population_trajectory).parameters.values()]
    assert stated == actual, f"skill signature {stated} != code {actual}"


def test_spiking_pli_is_the_biased_histogram_contrast_and_points_to_ppc():
    text = _text("jnwb-spiking/SKILL.md")
    assert "`peak_to_mean_contrast` (alias `pli`) is a histogram contrast" in text
    assert "sample-count bias of about 1/sqrt(N) under noise" in text
    assert "use `jnwb.pairwise_phase_consistency`" in text
    assert callable(jnwb.pairwise_phase_consistency)


def test_coupling_sign_condition_and_psi_clause_match_the_docstring():
    text = _text("jnwb-lfp-spectral/references/coupling.md")
    assert ("`icoh_mean` is signed: positive means `x` leads when the wrapped lag phase is in "
            "(0, pi); in (pi, 2pi) the sign reverses") in text
    assert "`phase_slope_index` is positive when `x` leads, with no such reversal." in text
    assert "positive means `x` leads wherever" not in text
    doc = " ".join(inspect.getdoc(jnwb.imaginary_coherency).split())
    assert "wherever the lag's phase is below pi" in doc
