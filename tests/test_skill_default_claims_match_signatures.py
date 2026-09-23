"""Every default a skill states in prose is checked against the live signature.

P-99: routing rows are bound to `inspect.signature`, but a default quoted in a skill's prose sat
outside that check -- `max_trial_fraction` (0.5), which bounds how much `repair_lfp_trials` may
alter, among them. A prose default goes stale without failing anything.

`CLAIMS` ties each sentence to the parameter it describes, and any mention of a default that no
row covers fails, so a new claim cannot land unchecked.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import jnwb

SKILLS = Path(__file__).resolve().parents[1] / "skills"
NO_DEFAULT = inspect.Parameter.empty
S = jnwb.StatisticalAnalysis

#: (skill, phrase in its SKILL.md, callable, parameter, stated default). A callable of None
#: marks a claim about the whole surface, checked by `_n_jobs_is_one_everywhere`.
CLAIMS = [
    ("jnwb-connectivity", "the default is not the lag search", jnwb.cross_modal_comparison,
     "bin_ms", None),
    ("jnwb-lfp-spectral", "`normalize` defaults to **True**", jnwb.band_power, "normalize", True),
    ("jnwb-lfp-spectral", "`how` is keyword-only and has no default", jnwb.aggregate_to_db,
     "how", NO_DEFAULT),
    ("jnwb-lfp-spectral", "`max_trial_fraction` argument (default 0.5)", jnwb.repair_lfp_trials,
     "max_trial_fraction", 0.5),
    ("jnwb-nwb-data", "(default column `codes`)", jnwb.events, "code_column", "codes"),
    ("jnwb-nwb-data", "(default column `codes`)", jnwb.event_onsets, "code_column", "codes"),
    ("jnwb-population", "`n_splits` has no default", jnwb.nested_cv_linear_svm, "n_splits",
     NO_DEFAULT),
    ("jnwb-statistics", "the default runs two and spends two", S.exploratory_compare, "test",
     "both"),
    ("jnwb-statistics", "By default it performs two tests", S.exploratory_compare, "test", "both"),
    ("jnwb", "The default is 1 everywhere", None, "n_jobs", 1),
]

_MENTION = re.compile(r"\bdefaults?\b|\bby default\b", re.IGNORECASE)


def _holds(fn, param: str, expected) -> bool:
    default = inspect.signature(fn).parameters[param].default
    if expected is NO_DEFAULT:
        return default is NO_DEFAULT
    return default is not NO_DEFAULT and default == expected


def _n_jobs_is_one_everywhere() -> bool:
    defaults = []
    for name in jnwb.__all__:
        obj = getattr(jnwb, name)
        members = [getattr(obj, m) for m in dir(obj) if not m.startswith("_")] if inspect.isclass(
            obj
        ) else []
        for target in [obj, *members]:
            try:
                parameters = inspect.signature(target).parameters
            except (TypeError, ValueError):
                continue
            if "n_jobs" in parameters:
                defaults.append(parameters["n_jobs"].default)
    return len(defaults) >= 3 and all(d == 1 for d in defaults)


def _uncovered(text: str, phrases: list[str]) -> list[str]:
    return [
        f"{n}: {line.strip()[:120]}"
        for n, line in enumerate(text.splitlines(), 1)
        if _MENTION.search(line.replace("default_rng", ""))
        and not any(p in line for p in phrases)
    ]


def test_every_default_a_skill_states_is_the_signature_default():
    wrong, phrases = [], {}
    for skill, phrase, fn, param, expected in CLAIMS:
        phrases.setdefault(skill, []).append(phrase)
        if phrase not in (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8"):
            wrong.append(f"{skill} no longer says {phrase!r}; update its CLAIMS row")
        elif not (_n_jobs_is_one_everywhere() if fn is None else _holds(fn, param, expected)):
            wrong.append(f"{skill}: {phrase!r} disagrees with the signature of {param}")
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        found = _uncovered(skill_md.read_text(encoding="utf-8"), phrases.get(skill_md.parent.name, []))
        wrong += [f"{skill_md.parent.name}:{f} has no CLAIMS row" for f in found]
    assert not wrong, wrong


def test_the_check_fails_on_a_wrong_or_unregistered_default():
    def repair(x, max_trial_fraction=0.4, *, how):
        return x

    assert not _holds(repair, "max_trial_fraction", 0.5)
    assert not _holds(repair, "x", None), "a required parameter has no default"
    assert _holds(repair, "how", NO_DEFAULT)
    assert _uncovered("`order` defaults to 5.\nrng = np.random.default_rng(0)\n", []) == [
        "1: `order` defaults to 5."
    ]
