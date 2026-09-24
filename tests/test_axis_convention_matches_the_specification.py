"""The axis vocabulary the specification declares must be the one the code uses.

`docs/10_operation_specifications.md` section 5 is consulted precisely when a function's own
docstring is silent, so a wrong line there is worse than no line. Until 0.2.5 it declared one
blanket convention for continuous signals, `(n_times, n_channels)`, and named the minority:
eight of the ten exported functions taking a 2-D continuous signal are channel-major, and
only `compute_psd` (which carries an explicit `axis`) and `epoch_continuous` are not.

A transposed continuous signal is not a loud failure. `laplacian_reference` on a probe with
many channels returns an array of exactly the expected shape whose numbers are a spatial
derivative taken across time, so nothing raises and nothing warns. That is why this is
pinned by executing the functions rather than by reading their docstrings: the docstring is
one more face, and the point of this module is that faces disagree.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import numpy as np
import pytest

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = REPO_ROOT / "docs" / "10_operation_specifications.md"

TIME_AXIS_NAMES = {"n_times", "n_samples", "n_t", "n_timepoints", "n_time"}
CHANNEL_AXIS_NAMES = {"n_channels", "n_ch", "n_contacts", "n_good_channels"}
SHAPE = re.compile(r"\((n_[a-z_]+(?:,\s*n_[a-z_]+)+)\)")

# Named in the specification as the two time-major exceptions.
TIME_MAJOR = ("compute_psd", "epoch_continuous")


def continuous_signal_conventions(docs: dict[str, str]) -> dict[str, set[str]]:
    """Split `docs` by the order each one claims for a channel/time two-tuple.

    Taken from the docstrings rather than from a hand-kept list so that a function added
    later is counted without anyone remembering to add it here.
    """
    conventions: dict[str, set[str]] = {"channel_major": set(), "time_major": set()}
    for name, doc in docs.items():
        for match in SHAPE.finditer(doc or ""):
            axes = [a.strip() for a in match.group(1).split(",")]
            if len(axes) != 2:
                continue
            first, second = axes
            if first in CHANNEL_AXIS_NAMES and second in TIME_AXIS_NAMES:
                conventions["channel_major"].add(name)
            elif first in TIME_AXIS_NAMES and second in CHANNEL_AXIS_NAMES:
                conventions["time_major"].add(name)
    return conventions


def public_docs() -> dict[str, str]:
    out = {}
    for name in jnwb.__all__:
        obj = getattr(jnwb, name, None)
        if callable(obj):
            out[name] = inspect.getdoc(obj) or ""
    return out


def spec_section_5() -> str:
    text = SPEC.read_text(encoding="utf-8")
    start = text.index("### 5. Axis & Dimension Vocabulary")
    return text[start:text.index("### 6.", start)]


class TestTheSweepFindsWhatItIsFor:
    """The live docstrings are consistent, so the split has to be driven over a seed too."""

    def test_it_separates_the_two_orders(self):
        got = continuous_signal_conventions({
            "spatial": "takes (n_channels, n_times)",
            "spectral": "takes (n_times, n_channels)",
        })
        assert got["channel_major"] == {"spatial"}
        assert got["time_major"] == {"spectral"}

    def test_a_function_claiming_both_orders_is_counted_in_both(self):
        """A docstring contradicting itself must not be silently resolved to one side."""
        got = continuous_signal_conventions(
            {"muddled": "input (n_channels, n_times), output (n_times, n_channels)"})
        assert got["channel_major"] == {"muddled"}
        assert got["time_major"] == {"muddled"}

    def test_shapes_naming_neither_axis_are_ignored(self):
        assert continuous_signal_conventions(
            {"other": "(n_trials, n_units) and (n_samples, n_features)"}
        ) == {"channel_major": set(), "time_major": set()}


class TestTheCodeIsChannelMajor:
    """Executed, not read: these assert behaviour that a transposed input would change."""

    def test_bipolar_reference_consumes_the_first_axis(self):
        """Five channels make four adjacent pairs; the time axis passes through."""
        data = np.tile(np.arange(5.0)[:, None], (1, 200))
        assert jnwb.bipolar_reference(data).shape == (4, 200)

    def test_laplacian_reference_differentiates_across_the_first_axis(self):
        """A ramp across channels has zero second difference on the interior channels.

        If axis 0 were time, this array would be constant in time and the interior
        result would be zero for a different reason, so the edges carry the evidence:
        they are the only rows that do not cancel.
        """
        data = np.tile(np.arange(4.0)[:, None], (1, 100))
        out = jnwb.laplacian_reference(data)
        assert out.shape == (4, 100)
        interior = out[1:-1]
        assert np.allclose(interior, 0.0), (
            "the interior of a channel ramp is not flat, so axis 0 is not the channel axis"
        )
        assert not np.allclose(out[0], 0.0) and not np.allclose(out[-1], 0.0)

    def test_compute_psd_reads_time_from_axis_zero_by_default(self):
        """The documented exception, pinned so that the specification's list stays true."""
        rng = np.random.default_rng(0)
        freqs, psd = jnwb.compute_psd(rng.standard_normal((512, 2)), fs=256.0)
        assert psd.shape == (freqs.size, 2)


CHANNEL_MAJOR_PRODUCERS = frozenset({
    "bipolar_reference", "laplacian_reference", "channel_correlation_matrix",
    "current_source_density_1d", "voltage_curvature_1d", "vflip_from_lfp", "xflip", "zflip",
})
TIME_MAJOR_CONSUMERS = frozenset({"compute_psd", "epoch_continuous"})


def _called_name(node: ast.Call):
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def cross_convention_hops(source: str) -> list[tuple[int, str, str]]:
    """Names bound from a channel-major call and passed straight to a time-major one.

    This is the composition form of the specification defect, and the form that produces a
    number rather than an error: `laplacian_reference` returns `(n_channels, n_times)` and
    `compute_psd` reads time from axis 0, so the chain computes a spectrum over as many
    samples as the probe has channels. Both calls are correct alone and a signature check
    passes both. A transpose or an explicit `axis=` on the hop settles it either way.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    produced: dict[str, str] = {}
    hops = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            producer = _called_name(node.value)
            if producer in CHANNEL_MAJOR_PRODUCERS:
                for target in node.targets:
                    names = (target.elts if isinstance(target, ast.Tuple) else [target])
                    for elt in names:
                        if isinstance(elt, ast.Name):
                            produced[elt.id] = producer
        if isinstance(node, ast.Call) and _called_name(node) in TIME_MAJOR_CONSUMERS:
            if any(kw.arg == "axis" for kw in node.keywords):
                continue
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id in produced:
                    hops.append((node.lineno, produced[arg.id], _called_name(node)))
    return hops


class TestTheCompositionSweepFindsWhatItIsFor:
    """Nothing in the repository chains the two, so the sweep is driven over seeds."""

    def test_it_finds_a_bare_hop(self):
        assert cross_convention_hops(
            "import jnwb\n"
            "reref = jnwb.laplacian_reference(lfp)\n"
            "f, p = jnwb.compute_psd(reref, fs=1000.0)\n"
        ) == [(3, "laplacian_reference", "compute_psd")]

    def test_an_explicit_axis_settles_it(self):
        assert cross_convention_hops(
            "import jnwb\n"
            "reref = jnwb.laplacian_reference(lfp)\n"
            "f, p = jnwb.compute_psd(reref, fs=1000.0, axis=-1)\n"
        ) == []

    def test_a_transpose_settles_it(self):
        assert cross_convention_hops(
            "import jnwb\n"
            "reref = jnwb.laplacian_reference(lfp)\n"
            "f, p = jnwb.compute_psd(reref.T, fs=1000.0)\n"
        ) == []

    def test_an_unrelated_call_is_not_a_hop(self):
        assert cross_convention_hops(
            "import jnwb\nf, p = jnwb.compute_psd(raw, fs=1000.0)\n") == []


class TestNoFaceChainsTheTwoConventions:
    @pytest.mark.parametrize("rel", sorted(
        p.relative_to(REPO_ROOT).as_posix()
        for p in list(REPO_ROOT.glob("skills/*/SKILL.md"))
        + list(REPO_ROOT.glob("examples/**/*.py"))
        + list(REPO_ROOT.glob("jnwb/*.py"))))
    def test_it_carries_no_cross_convention_hop(self, rel: str):
        path = REPO_ROOT / rel
        text = path.read_text(encoding="utf-8")
        sources = ([text] if rel.endswith(".py")
                   else re.findall(r"```(?:python|py)\n(.*?)```", text, re.S))
        for source in sources:
            hops = cross_convention_hops(source)
            assert not hops, (
                f"{rel} feeds a channel-major result straight into a time-major argument: "
                f"{hops}. Both calls are right on their own and the result has a plausible "
                f"shape, so nothing else will say so."
            )


class TestTheSpecificationDeclaresTheMajorityConvention:
    def test_the_continuous_signal_line_is_channel_major(self):
        section = spec_section_5()
        line = next(ln for ln in section.splitlines() if "Continuous signals" in ln)
        assert "`(n_channels, n_times)`" in line, (
            f"section 5 declares {line.strip()!r}; the exported functions are "
            f"channel-major and a reader consults this line when a docstring is silent"
        )

    def test_it_names_the_time_major_exceptions(self):
        section = spec_section_5()
        missing = [name for name in TIME_MAJOR if name not in section]
        assert not missing, (
            f"section 5 declares a convention without naming {missing}, which do not "
            f"follow it"
        )

    def test_the_declared_default_is_still_the_majority(self):
        """The claim that makes the line true, checked against the code rather than assumed.

        A coarse backstop, and deliberately so: it fires only on a wholesale shift, not on
        one function changing sides. Flipping a single function leaves seven against three
        and this still passes, which is why the exception list is pinned by equality above
        rather than left to this.
        """
        conventions = continuous_signal_conventions(public_docs())
        channel_major = conventions["channel_major"]
        time_major = conventions["time_major"]
        assert len(channel_major) > len(time_major), (
            f"section 5 declares channel-major as the convention, but {sorted(time_major)} "
            f"are time-major against {sorted(channel_major)}"
        )

    def test_the_time_major_functions_are_exactly_the_ones_listed(self):
        """A new time-major function must be added to the list, not left to the blanket.

        Set equality, not membership. An earlier version asked only whether each
        time-major function was named anywhere in section 5, which every function in the
        channel-major list already is: flipping `channel_correlation_matrix` to time-major
        left that test passing, because the section still contained its name. Equality
        fails in both directions -- a function that becomes time-major, and one of the two
        listed exceptions that stops being one.
        """
        time_major = continuous_signal_conventions(public_docs())["time_major"]
        assert time_major == set(TIME_MAJOR), (
            f"section 5 lists {sorted(TIME_MAJOR)} as the time-major exceptions, but the "
            f"docstrings say {sorted(time_major)}"
        )
