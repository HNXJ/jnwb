"""A skill may not state a safeguard more strongly than the router and `AGENTS.md` state it.

The routing matrices are the text an agent reads instead of the documentation, so an
overclaim there is not a wording slip -- it licenses the conclusion the rest of the repository
spends nine pages forbidding. Two of the three checks below re-run the number the skill now
prints, rather than matching its prose: a caveat that is merely present is not a caveat that
is true.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

import jnwb

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

CALL = re.compile(r"`jnwb\.(?:\w+\.)*(\w+)\(")
# No routing row has a legitimate use for these about volume conduction. "immunity" is
# allowed only under a negation, because the router's own invariant is titled with it.
FORBIDDEN = re.compile(r"\b(robust|immune|immunity|eliminat\w*|remov\w*)\b", re.I)
NEGATED = re.compile(r"\b(no|not|never|without)\b[^.]{0,60}$", re.I)

PHASE_MEASURES = {"wpli", "imaginary_coherency"}


def _rows() -> list[tuple[str, str, set[str]]]:
    out = []
    for page in sorted(SKILLS.rglob("SKILL.md")):
        for line in page.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("- "):
                out.append((page.parent.name, line, set(CALL.findall(line))))
    assert len(out) >= 100, f"only {len(out)} routing rows found; the parser stopped matching"
    return out


def test_no_phase_measure_row_claims_more_than_reduced_sensitivity() -> None:
    rows = [(skill, line) for skill, line, names in _rows() if names & PHASE_MEASURES]
    assert len(rows) >= 2, f"expected rows for {PHASE_MEASURES}, found {len(rows)}"
    for skill, line in rows:
        assert "reduc" in line.lower(), (
            f"{skill}: a phase-lag measure row must say what it reduces sensitivity to: {line}"
        )
        for match in FORBIDDEN.finditer(line):
            prefix = line[: match.start()]
            assert NEGATED.search(prefix), (
                f"{skill}: {match.group(0)!r} claims more than the router's "
                f"'reduce sensitivity ... do not establish immunity': {line}"
            )


def test_narrowband_psi_really_does_report_nothing() -> None:
    """The connectivity skill's verification instruction fails on a band it did not exclude."""
    fs = 1000.0
    t = np.arange(0, 20.0, 1 / fs)
    x = np.sin(2 * np.pi * 20.0 * t)
    y = np.sin(2 * np.pi * 20.0 * (t - 0.010))  # x leads y by 10 ms

    narrow = jnwb.phase_slope_index(x, y, fs, (19.0, 21.0))
    broad = jnwb.phase_slope_index(x, y, fs, (15.0, 30.0))

    assert abs(narrow.net) < 1e-3, f"narrowband PSI is not degenerate here: {narrow.net}"
    assert broad.net > 0, f"broadband PSI lost the direction: {broad.net}"
    assert abs(broad.net) > 100 * abs(narrow.net), (
        f"the two bands are not distinguishable: {narrow.net} vs {broad.net}"
    )

    page = (SKILLS / "jnwb-connectivity" / "SKILL.md").read_text(encoding="utf-8")
    section = page.partition("## 5. Verification")[2]
    assert section.strip(), "the connectivity skill has no verification section"
    assert "frequency bins" in section, (
        "the PSI verification instruction does not require a band with several bins"
    )


@pytest.mark.parametrize("tau_ms, stated_ms", [(25.0, 17), (50.0, 34)])
def test_causal_smoothing_delays_the_onset_by_what_the_skill_states(
    tau_ms: float, stated_ms: int
) -> None:
    """`causal_exp_smooth` is mandated for latency, and it moves the latency."""
    bin_ms = 1.0
    rate = np.zeros(600)
    rate[300:] = 10.0
    smoothed = jnwb.causal_exp_smooth(rate, bin_ms=bin_ms, tau_ms=tau_ms)
    half_rise = float(np.argmax(smoothed >= 5.0)) * bin_ms - 300.0

    assert half_rise == pytest.approx(stated_ms, abs=1.0), (
        f"tau_ms={tau_ms} shifts the half-rise by {half_rise} ms, not the {stated_ms} ms the "
        f"skill states"
    )
    # The analytic law `docs/common_mistakes.md` section 8 gives, on the same run.
    assert half_rise == pytest.approx(tau_ms * np.log(2), abs=1.5)

    page = (SKILLS / "jnwb-spiking" / "SKILL.md").read_text(encoding="utf-8")
    assert f"`tau_ms={tau_ms:.0f}`" in page, f"the skill does not state the tau_ms={tau_ms} case"
    assert f"+{stated_ms}$ ms" in page, f"the skill does not state the {stated_ms} ms shift"
