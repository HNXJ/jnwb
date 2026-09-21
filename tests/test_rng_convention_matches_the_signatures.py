"""06-102 / P-73: the documented RNG convention, held against the live signatures.

Two convention texts prescribed `rng: Optional[Union[np.random.Generator, int]] = None`.
Measured against the package: 19 of 23 `rng` parameters on the public API deliberately do
not present `None`, because putting the seed in the signature **was** the 05-35 repair --
five functions declared `rng=None` and then ran `np.random.default_rng(42)` with no way for
a caller to learn the seed, so two calls a caller believed were independent shared one null.
`jnwb/_rng.py` records it. The prose was stale; the signatures are correct.

The prose edit alone has a shelf life, so this module pins the two to each other.

**Independence.** The documented form is stated here as a literal (`OLD_FORM`,
`PRESENTS_NONE`, `FRESH_ENTROPY`) and separately parsed off the prose. Neither is derived
from `inspect.signature`. A check that read its expected value out of the same introspection
it validates would agree with itself under every corruption, which is the defect class this
cycle keeps producing.

**The one deviation, stated precisely.** `cross_area_coherence` declares `rng=None` against
the convention and resolves it to `np.random.SeedSequence(42)`. It is **not** an 05-35
survivor: 05-35's defect was a *silent* fixed seed, and this function discloses the entropy
it used through `surrogate_seed_entropy` in its return value (`jnwb/spectral.py:725`,
documented at `:670`). A caller can learn the seed; they just cannot read it off the
signature, which is where this repository's convention puts it. Weaker than 05-35, and real.

**Why this module exists when `test_rng_control.py` already guards 05-35.** That module
cannot see this deviation, for three independent reasons, each closed by a different
assertion here:

1. Its `SEEDED` tuple is hand-maintained and never names `cross_area_coherence`, so its
   signature check never covered it. Closed by `test_exactly_these_four_present_none`,
   which enumerates every `rng` parameter from `jnwb.__all__` rather than from a list a
   contributor must remember to extend, and by `test_the_walk_reaches_the_rng_parameters`,
   which fails if that enumeration ever collapses.
2. Its body scan reads only `statistics.py` and `decoding.py`, and this function lives in
   `spectral.py`. Closed by the same walk, which is module-agnostic: it reaches whatever
   the public API exports, wherever it is defined.
3. Its regex `default_rng\\((\\d+)\\)` cannot match `default_rng(seed_sequence)` however many
   modules it scans. Closed by
   `test_cross_area_coherence_deviates_from_the_convention_but_discloses_its_seed`, which
   detects the fixed seed by *calling the function twice*, so no spelling of the source
   evades it.

**What would make each check below pass while the rule it names is violated.**

- The public-symbol walk yields nothing, so "every rng parameter conforms" is vacuous.
  Held by `test_the_walk_reaches_the_rng_parameters`, which requires the known count.
- The prose scan reads an empty or missing file and finds no stale form. Held by
  `test_the_prose_files_are_readable_and_nonempty`.
- The stale-form matcher never matches anything, so no text can ever fail it. Held by
  `test_the_stale_form_matcher_can_fire`, which runs it against the string it hunts.
- The exception list is read as a tolerance ("at most four may present None"), so a new
  `rng=None` slips in. Held by `test_exactly_these_four_present_none`, an equality: under
  a subset assertion in either direction the drift survives.
- The deviation gets blessed as a legitimate `None`. Held by
  `test_cross_area_coherence_shows_its_seed_in_the_signature`, a strict xfail that fails
  the day the signature is brought into line, forcing these lists and both convention
  texts to be updated together rather than left stale.
- A name is added to `FRESH_ENTROPY` and is reported as verified without ever being
  called, because the probe dispatch falls through to another function. Held by
  `test_every_fresh_entropy_function_has_its_own_probe`. This one is not hypothetical:
  the first version of this module had that fallback, and the mutant that added
  `cross_area_coherence` to `FRESH_ENTROPY` survived until the dispatch was made explicit.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import numpy as np
import pytest

import jnwb
from jnwb._rng import Default

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
SPEC_PAGE = REPO_ROOT / "docs" / "10_operation_specifications.md"
PROSE_FILES = (CONTRIBUTING, SPEC_PAGE)

# --- the documented convention, stated here and nowhere derived from introspection ------

#: The form both texts used to prescribe. Re-adopting it reintroduces 05-35.
OLD_FORM = re.compile(
    r"rng:\s*Optional\[\s*Union\[\s*(?:np\.random\.)?Generator\s*,\s*int\s*\]\s*\]\s*=\s*None"
)

#: Every public `rng` parameter whose default presents `None` to the caller.
PRESENTS_NONE = frozenset(
    {"cross_area_coherence", "cross_modal_comparison", "jrsa", "xflip"}
)

#: Of those, the ones where `None` resolves to fresh OS entropy, which is the contract.
FRESH_ENTROPY = frozenset({"cross_modal_comparison", "jrsa", "xflip"})

#: The one that presents `None`, resolves it to a fixed seed, and hands that seed back in
#: its return value instead of showing it in the signature.
DISCLOSED_FIXED_SEED = "cross_area_coherence"

#: The key `cross_area_coherence` discloses its seed through.
DISCLOSURE_KEY = "surrogate_seed_entropy"

EXPECTED_TOTAL = 23


def _public_callables():
    for name in sorted(jnwb.__all__):
        obj = getattr(jnwb, name, None)
        if obj is None:
            continue
        if inspect.isclass(obj):
            for mname, meth in sorted(vars(obj).items()):
                if mname.startswith("_"):
                    continue
                fn = meth.__func__ if isinstance(meth, (staticmethod, classmethod)) else meth
                if callable(fn):
                    yield f"{name}.{mname}", fn
        elif callable(obj):
            yield name, obj


def _rng_parameters():
    """(qualname, default) for every `rng` parameter on the public API."""
    out = []
    for qualname, fn in _public_callables():
        try:
            sig = inspect.signature(fn)
        except (ValueError, TypeError):
            continue
        param = sig.parameters.get("rng")
        if param is not None:
            out.append((qualname, param.default))
    return out


def _presents_none(default) -> bool:
    """What `inspect.signature` shows the caller.

    `jnwb._rng.Default` reports the value it stands for, so `Default(None)` renders as
    `None` in the signature without being `None`. A reader sees `rng=None` either way, so
    the convention is about what is rendered.
    """
    return default is not inspect.Parameter.empty and repr(default) == "None"


def _coherence_inputs():
    seed = np.random.default_rng(13)
    return seed.normal(size=4000), seed.normal(size=4000)


COHERENCE_KW = dict(fs=1000.0, n_surrogates=10, freq_bands="canonical")


# --- the checks that keep the checks honest ---------------------------------------------


def test_the_walk_reaches_the_rng_parameters():
    rows = _rng_parameters()
    assert len(rows) == EXPECTED_TOTAL, (
        f"expected {EXPECTED_TOTAL} rng parameters on the public API, walked {len(rows)}. "
        "If the API genuinely changed, update EXPECTED_TOTAL; if the walk broke, every "
        "other assertion in this module just became vacuous."
    )


def test_the_prose_files_are_readable_and_nonempty():
    for path in PROSE_FILES:
        assert path.is_file(), f"{path.name} is named as a convention text and is gone"
        assert len(path.read_text(encoding="utf-8")) > 500, f"{path.name} is empty or truncated"


def test_the_stale_form_matcher_can_fire():
    """A matcher that cannot match makes every prose check below trivially green."""
    assert OLD_FORM.search("rng: Optional[Union[np.random.Generator, int]] = None")
    assert OLD_FORM.search("rng: Optional[Union[Generator, int]] = None")
    assert not OLD_FORM.search("rng: RNGLike = DEFAULT_SEED")


# --- acceptance 1: no convention text prescribes a form the package does not use --------


@pytest.mark.parametrize("path", PROSE_FILES, ids=lambda p: p.name)
def test_no_convention_text_prescribes_the_retired_form(path):
    text = path.read_text(encoding="utf-8")
    hits = [
        f"line {i}: {ln.strip()}"
        for i, ln in enumerate(text.splitlines(), 1)
        if OLD_FORM.search(ln) and "testing.synth" not in ln
    ]
    assert not hits, (
        f"{path.name} still prescribes `rng: Optional[Union[Generator, int]] = None`, the form "
        f"05-35 repaired away: {hits}"
    )


# --- acceptance 2 and 3: documented exception set == live signatures --------------------


def test_exactly_these_four_present_none():
    """Equality, not a ceiling. A tolerance in either direction lets drift through, and
    this enumeration is what covers the functions a hand-maintained list would omit."""
    live = {q for q, d in _rng_parameters() if _presents_none(d)}
    assert live == set(PRESENTS_NONE), (
        f"the set of public rng parameters presenting None has moved.\n"
        f"  documented: {sorted(PRESENTS_NONE)}\n"
        f"  live      : {sorted(live)}\n"
        "Update this module and both convention texts together, or the prose is stale again."
    )


def test_the_other_nineteen_show_the_seed_they_will_use():
    others = [(q, d) for q, d in _rng_parameters() if not _presents_none(d)]
    assert len(others) == EXPECTED_TOTAL - len(PRESENTS_NONE)
    for qualname, default in others:
        if default is inspect.Parameter.empty:
            continue  # no default at all: the caller must choose, which is also explicit
        value = default.value if isinstance(default, Default) else default
        assert isinstance(value, (int, np.integer)) or repr(default) == "<required>", (
            f"{qualname}: rng default {default!r} neither shows a seed nor demands one"
        )


def test_the_spec_page_names_every_function_whose_rng_default_is_none():
    """Parsed off the prose, compared against the literals above -- two independent sources."""
    text = SPEC_PAGE.read_text(encoding="utf-8")
    expected = FRESH_ENTROPY | {DISCLOSED_FIXED_SEED}
    named = {n for n in expected if f"`{n}`" in text}
    assert named == expected, (
        "the RNG section of the specification page no longer names every function whose "
        f"rng default is None; missing {sorted(expected - named)}"
    )


# --- acceptance 2: each exception checked, not asserted ---------------------------------


def _probe_xflip():
    data = np.random.default_rng(11).normal(size=(12, 3000))
    return (
        dict(jnwb.xflip(data, n_surrogates=30, rng=None).p_values),
        dict(jnwb.xflip(data, n_surrogates=30, rng=None).p_values),
    )


def _probe_jrsa():
    seed = np.random.default_rng(11)
    a, b = seed.normal(size=(40, 6)), seed.normal(size=(40, 6))
    return (
        np.asarray(jnwb.jrsa(a, b, stats=True, permutations=200, rng=None).p).tolist(),
        np.asarray(jnwb.jrsa(a, b, stats=True, permutations=200, rng=None).p).tolist(),
    )


def _probe_cross_modal_comparison():
    seed = np.random.default_rng(11)
    u, v = seed.normal(size=300), seed.normal(size=300)
    key = "lag_corrected_pvalue"
    return (
        jnwb.cross_modal_comparison(u, v, bin_ms=10.0, rng=None)[key],
        jnwb.cross_modal_comparison(u, v, bin_ms=10.0, rng=None)[key],
    )


#: One probe per function. A name without its own probe is not exercised, so the mapping is
#: explicit rather than a dispatch with a fallback branch.
FRESH_PROBES = {
    "cross_modal_comparison": _probe_cross_modal_comparison,
    "jrsa": _probe_jrsa,
    "xflip": _probe_xflip,
}


def test_every_fresh_entropy_function_has_its_own_probe():
    """Caught by mutation: the earlier form dispatched on the name with a trailing `else`,
    so adding a name to `FRESH_ENTROPY` re-ran `cross_modal_comparison` under the new
    name and passed without ever calling the function it claimed to test."""
    assert set(FRESH_PROBES) == set(FRESH_ENTROPY), (
        "FRESH_ENTROPY and FRESH_PROBES disagree; a name without a probe would be reported "
        f"as verified without being called: {set(FRESH_ENTROPY) ^ set(FRESH_PROBES)}"
    )


@pytest.mark.parametrize("name", sorted(FRESH_PROBES))
def test_none_really_means_fresh_entropy(name):
    """Two calls with `rng=None` must disagree, or `None` is a fixed seed in disguise."""
    one, two = FRESH_PROBES[name]()
    assert one != two, (
        f"{name}: two rng=None calls agreed exactly, so None resolves to a fixed seed"
    )


def test_cross_area_coherence_deviates_from_the_convention_but_discloses_its_seed():
    """The deviation pinned in full, so it cannot quietly become something else.

    Three facts, and all three are the current truth: the signature presents `None`; the
    resolution is a fixed seed, caught by calling twice rather than by reading the source;
    and the seed reaches the caller in the return value. The third is what separates this
    from 05-35, where the seed was unknowable.
    """
    default = inspect.signature(jnwb.cross_area_coherence).parameters["rng"].default
    assert _presents_none(default), "cross_area_coherence no longer presents rng=None"

    a, b = _coherence_inputs()
    one = jnwb.cross_area_coherence(a, b, rng=None, **COHERENCE_KW)
    two = jnwb.cross_area_coherence(a, b, rng=None, **COHERENCE_KW)
    assert one["band_significance"] == two["band_significance"], (
        "cross_area_coherence now draws fresh entropy for rng=None; it has joined "
        "FRESH_ENTROPY and this module and both convention texts need updating"
    )
    assert one[DISCLOSURE_KEY] == 42 == two[DISCLOSURE_KEY], (
        f"the seed is no longer disclosed through {DISCLOSURE_KEY}; without that this "
        "would be a silent fixed seed, which is the 05-35 defect rather than a deviation"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Convention: the default seed is visible in the signature. cross_area_coherence "
        "declares rng=None and resolves np.random.SeedSequence(42) at spectral.py:706-710, "
        "disclosing the entropy through surrogate_seed_entropy in its return instead. When "
        "the signature is brought into line this xpasses, and strict mode then fails so "
        "PRESENTS_NONE, FRESH_ENTROPY and both convention texts are updated together."
    ),
)
def test_cross_area_coherence_shows_its_seed_in_the_signature():
    default = inspect.signature(jnwb.cross_area_coherence).parameters["rng"].default
    assert not _presents_none(default)
