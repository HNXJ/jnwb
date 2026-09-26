"""Statements on the method and troubleshooting pages, each held against the code it describes.

Every test here reads the statement off the page and checks it against a call, a signature or
a return value, so a page edit that makes the statement false fails, and so does a code change
that makes the page stale. None derives its expected value from the introspection it checks
without also reading the page.
"""
from __future__ import annotations

import ast
import inspect
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"


def _page(name: str) -> str:
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Whitespace collapsed, so a statement survives being re-wrapped."""
    return " ".join(text.split())


def _table_row(text: str, first_cell: str) -> list[str]:
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells and cells[0] == first_cell:
            return cells
    raise AssertionError(f"no table row starting with {first_cell!r}")


def _ticked(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


# --------------------------------------------------------------- vflip_from_lfp composition


def test_vflip_from_lfp_equals_the_composition_the_specification_writes():
    """The row wrote `compute_psd(lfp, fs)`, whose default `axis=0` runs over channels on the
    channel-major input `vflip_from_lfp` takes. The composition is executed as written."""
    row = _table_row(_page("docs/10_operation_specifications.md"), "`vflip_from_lfp`")
    match = re.search(r"`compute_psd\(([^)]*)\) -> vflip\(psd, freqs\)`", " ".join(row))
    assert match, "the vflip_from_lfp row no longer writes its composition"
    args = [a.strip() for a in match.group(1).split(",")]
    assert args[:2] == ["lfp", "fs"], args
    kwargs = {k.strip(): ast.literal_eval(v) for k, v in (a.split("=") for a in args[2:])}

    from jnwb.testing.synth import synth_laminar_motif

    receipt = synth_laminar_motif(n_channels=16, n_samples=3000, rng=3)
    lfp, fs = receipt.lfp, receipt.fs
    freqs, psd = jnwb.compute_psd(lfp, fs, **kwargs)
    composed = jnwb.vflip(psd, freqs).to_dict()
    direct = jnwb.vflip_from_lfp(lfp, fs).to_dict()
    assert composed.keys() == direct.keys()
    for key, value in direct.items():
        if isinstance(value, np.ndarray):
            np.testing.assert_array_equal(composed[key], value, err_msg=key)
        elif isinstance(value, float) and np.isnan(value):
            assert np.isnan(composed[key]), key
        else:
            assert composed[key] == value, key


# --------------------------------------------------------------- missing `codes` column


def _nwb_without_codes():
    import pynwb
    from pynwb.epoch import TimeIntervals

    nwb = pynwb.NWBFile(session_description="no codes", identifier="no-codes",
                        session_start_time=datetime(2020, 1, 1, tzinfo=timezone.utc))
    table = TimeIntervals(name="trials_without_codes", description="no code column")
    table.add_row(start_time=1.5, stop_time=2.5)
    table.add_row(start_time=3.5, stop_time=4.5)
    nwb.add_time_intervals(table)
    return nwb


def test_only_events_warns_on_a_table_without_a_codes_column():
    nwb = _nwb_without_codes()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        onsets = jnwb.event_onsets(nwb)
    np.testing.assert_allclose(onsets, [1.5, 3.5])
    with pytest.warns(UserWarning, match="No 'codes' column"):
        jnwb.events(nwb)

    row = _table_row(_page("docs/errors.md"), "No `codes` column")
    assert _ticked(row[1]) == ["events"], row[1]
    for name in ("README.md", "docs/errors.md", "docs/common_mistakes.md"):
        text = _flat(_page(name))
        assert "`event_onsets`" in text and "`events`" in text, name
        for stale in ("no `codes` column returns the onsets and warns",
                      "no `codes` column returns its onsets and warns",
                      "the onsets are returned with a warning"):
            assert stale not in text, f"{name} still says {stale!r}"


# --------------------------------------------------------------- accepted `rng` types


def _public_rng_parameters():
    for name in sorted(jnwb.__all__):
        obj = getattr(jnwb, name, None)
        members = []
        if inspect.isclass(obj):
            for mname, meth in sorted(vars(obj).items()):
                if not mname.startswith("_"):
                    fn = meth.__func__ if isinstance(meth, (staticmethod, classmethod)) else meth
                    if callable(fn):
                        members.append((f"{name}.{mname}", fn))
        elif callable(obj):
            members.append((name, obj))
        for qualname, fn in members:
            try:
                param = inspect.signature(fn).parameters.get("rng")
            except (TypeError, ValueError):
                continue
            if param is not None:
                yield qualname, param


def _annotation(param) -> str:
    ann = param.annotation
    return ann if isinstance(ann, str) else getattr(ann, "__name__", repr(ann))


def _signature_sets():
    generator_only, int_only = set(), set()
    for qualname, param in _public_rng_parameters():
        ann = _annotation(param)
        if ann in ("np.random.Generator", "Generator"):
            generator_only.add(qualname)
        elif ann == "int":
            int_only.add(qualname)
    return generator_only, int_only


def test_the_specification_names_every_restricted_rng_surface():
    generator_only, int_only = _signature_sets()
    assert generator_only and int_only, "the signature walk found nothing"
    page = _page("docs/10_operation_specifications.md")
    gen_row = _table_row(page, "a `np.random.Generator` only")
    int_row = _table_row(page, "an `int` only")
    assert set(_ticked(gen_row[1])) == generator_only
    assert set(_ticked(int_row[1])) == int_only
    stats_page = _page("docs/07_statistical_inference_and_nulls.md")
    stats_row = next(
        cells for line in stats_page.splitlines() if line.startswith("| `permute_labels`")
        for cells in [[c.strip() for c in line.strip("|").split("|")]]
    )
    assert set(_ticked(stats_row[0])) == generator_only
    assert stats_row[1] == "a `Generator` only"
    assert _ticked(_table_row(stats_page, "`build_permutation_plan`")[0]) == sorted(int_only)


def _restricted_calls():
    a = np.random.default_rng(1).normal(size=10)
    b = np.random.default_rng(2).normal(size=10)
    return {
        "shuffle_pvalue_paired": lambda r: jnwb.shuffle_pvalue_paired(a, b, 20, r),
        "shuffle_pvalue_unpaired": lambda r: jnwb.shuffle_pvalue_unpaired(a, b, 20, r),
        "paired_fire_prob_test": lambda r: jnwb.paired_fire_prob_test(a > 0, b > 0, 20, 20, r),
        "permute_labels": lambda r: jnwb.permute_labels(np.arange(10), scheme="global", rng=r),
    }


@pytest.mark.parametrize("name", sorted(_restricted_calls()))
def test_a_generator_only_surface_refuses_an_int_and_none(name):
    call = _restricted_calls()[name]
    call(np.random.default_rng(0))
    expected = TypeError if name == "permute_labels" else AttributeError
    for value in (0, None):
        with pytest.raises(expected):
            call(value)


def test_build_permutation_plan_takes_only_an_int():
    labels, groups = np.arange(10) % 2, np.arange(10) // 5
    jnwb.build_permutation_plan(labels, groups, n_permutations=3, rng=4)
    for value in (None, np.random.default_rng(4)):
        with pytest.raises(TypeError):
            jnwb.build_permutation_plan(labels, groups, n_permutations=3, rng=value)


def test_statistical_analysis_accepts_an_int_a_generator_and_none_and_defaults_to_42():
    row = _table_row(_page("docs/07_statistical_inference_and_nulls.md"),
                     "`StatisticalAnalysis` methods")
    assert "an `int` seed, a `Generator`, or `None`" in row[1] and "`42`" in row[1]
    data = np.random.default_rng(5).normal(size=30)
    for value in (7, np.random.default_rng(7), None):
        jnwb.StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=50, rng=value)
    with pytest.raises(TypeError):
        jnwb.StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=50, rng=2.5)
    defaults = {q: p.default for q, p in _public_rng_parameters()
                if q.startswith("StatisticalAnalysis.")}
    assert defaults and all(d == 42 for d in defaults.values()), defaults


# --------------------------------------------------------------- structured returns


def test_the_structured_return_bullet_names_the_one_class_without_mapping_access():
    page = _page("docs/10_operation_specifications.md")
    section = page.split("### 4. Structured Return Types", 1)[1].split("###", 1)[0]
    named = re.search(r"\(e\.g\. ([^)]*)\)", section).group(1)
    classes = {n: getattr(jnwb, n) for n in _ticked(named)}
    assert len(classes) >= 4
    without = {n for n, c in classes.items()
               if not (hasattr(c, "to_dict") and hasattr(c, "__getitem__"))}
    exceptions = set(re.findall(r"`(\w+)` is the exception", section))
    assert without == exceptions == {"JRSAResult"}, (without, exceptions)


# --------------------------------------------------------------- per-iteration seeds


def test_parallel_seeds_are_spawned_per_iteration_from_one_drawn_integer():
    from jnwb._parallel import spawn_seeds

    text = _flat(_page("docs/10_operation_specifications.md"))
    assert "spawn(n_jobs)" not in text
    assert "`np.random.SeedSequence(entropy).spawn(n_iterations)`" in text
    n_iterations = 7
    got = spawn_seeds(np.random.default_rng(5), n_iterations)
    entropy = int(np.random.default_rng(5).integers(0, 2**63 - 1))
    expected = np.random.SeedSequence(entropy).spawn(n_iterations)
    assert len(got) == n_iterations
    for g, e in zip(got, expected):
        np.testing.assert_array_equal(g.generate_state(4), e.generate_state(4))


# --------------------------------------------------------------- compare_session_quality


def test_compare_session_quality_reads_the_columns_the_page_names():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    page = _page("docs/09_decoding_and_visual_qc.md")
    assert "compare_sessions" not in page
    comment = re.search(r"# Multi-session QC comparison bars:(.*?)\nfig_comp", page, re.S)
    assert comment, "the compare_session_quality comment moved"
    text = comment.group(1).replace("#", " ")
    required_part, optional_part = text.split("optionally", 1)
    required = re.findall(r"\b(session_id|snr_mean|total_units|snr_good_rate)\b", required_part)
    optional = re.findall(r"\b(snr_good_rate)\b", optional_part)
    assert required == ["session_id", "snr_mean", "total_units"] and optional == ["snr_good_rate"]

    frame = pd.DataFrame({"session_id": ["a", "b"], "snr_mean": [1.2, 0.4],
                          "total_units": [10, 4]})
    plt.close(jnwb.visual_qc.compare_session_quality(frame))
    plt.close(jnwb.visual_qc.compare_session_quality(frame.assign(snr_good_rate=[0.6, 0.2])))
    for column in required:
        with pytest.raises(KeyError):
            jnwb.visual_qc.compare_session_quality(frame.drop(columns=column))
    plt.close("all")


# --------------------------------------------------------------- layout basis


def test_the_errors_page_lists_every_layout_basis():
    from jnwb.nwb_inspect import _resolve_layout

    produced = {
        _resolve_layout((1000, 64), 64)[1],
        _resolve_layout((64, 1000), None, "TimeSeries")[1],
        _resolve_layout((64, 1000), None, "ElectricalSeries")[1],
        _resolve_layout((64, 1000), None)[1],
    }
    page = _page("docs/errors.md")
    section = page.split("### `ChannelIndexError`", 1)[1].split("\n### ", 1)[0]
    listed = {row.split("|")[1].strip().strip("`") for row in section.splitlines()
              if row.startswith("| `")}
    assert produced == listed == {"electrode_count", "schema", "shape"}, (produced, listed)


# --------------------------------------------------------------- directed matrix


def test_the_network_matrix_is_labelled_directed_and_is_not_antisymmetric():
    page = _page("docs/08_directed_connectivity_and_information.md")
    assert "Net matrix" not in page and 'print("Directed matrix shape:"' in page
    rng = np.random.default_rng(0)
    x = rng.normal(size=400)
    y = np.roll(x, 1) + 0.5 * rng.normal(size=400)
    net = jnwb.directed_network({"A": x, "B": y, "C": rng.normal(size=400)},
                                method="granger", order=2, fdr=False, n_surrogates=0, rng=0)
    m = net["matrix"]
    off = ~np.eye(3, dtype=bool)
    assert not np.allclose(m[off], -m.T[off]), "the matrix is antisymmetric after all"


# --------------------------------------------------------------- testing.synth row


def test_the_synth_row_states_what_each_builder_returns():
    import jnwb.testing.synth as synth

    row = _table_row(_page("docs/10_operation_specifications.md"), "`testing.synth`")
    output = row[5]
    builders = {n for n, f in vars(synth).items()
                if inspect.isfunction(f) and f.__module__ == synth.__name__
                and not n.startswith("_")}
    stated = {}
    for clause in output.split(";"):
        names = re.findall(r"`(synth_\w+|build_\w+)`", clause)
        kind = clause.split(" from ", 1)[0].strip().rstrip(".")
        for n in names:
            stated[n] = kind
    assert set(stated) == builders, (sorted(stated), sorted(builders))
    for name, kind in stated.items():
        ann = str(inspect.signature(getattr(synth, name)).return_annotation)
        if kind == "`np.ndarray`":
            assert ann == "np.ndarray", (name, ann)
        elif kind.startswith("a `"):
            assert ann == kind[3:-1], (name, ann)
        else:
            # Count top-level items of `Tuple[...]`, so `Dict[str, Any]` counts as one.
            inner = ann[len("Tuple["):-1]
            depth, items = 0, 1
            for ch in inner:
                depth += ch == "["
                depth -= ch == "]"
                items += ch == "," and depth == 0
            assert ann.startswith("Tuple[") and items == kind.count(",") + 1, (name, ann, kind)


# --------------------------------------------------------------- jrsa nan_policy


def _nan_sentence():
    text = _flat(_page("docs/03_representational_similarity_jrsa.md"))
    match = re.search(r"leaves nothing: (.*?) raise `ValueError`; (.*?) return `NaN`", text)
    assert match, "the nan_policy statement moved"
    return re.findall(r'`"(\w+)"`', match.group(1)), re.findall(r'`"(\w+)"`', match.group(2))


def _conditions():
    rng = np.random.default_rng(0)
    x1 = rng.normal(size=(6, 10, 40))
    return x1, x1 + rng.normal(size=x1.shape)


@pytest.mark.parametrize("metric", _nan_sentence()[0])
def test_an_empty_condition_raises_for_the_metrics_the_page_names(metric):
    x1, x2 = _conditions()
    x1[2] = np.nan
    with pytest.raises(ValueError):
        jnwb.jrsa(x1, x2, metric=metric, stats=False, rng=0)


@pytest.mark.parametrize("metric", _nan_sentence()[1])
def test_an_empty_condition_is_nan_for_the_metrics_the_page_names(metric):
    x1, x2 = _conditions()
    x1[2] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert np.isnan(float(jnwb.jrsa(x1, x2, metric=metric, stats=False, rng=0).value))


def test_one_nan_sample_drops_that_sample_from_every_condition():
    x1, x2 = _conditions()
    holed = x1.copy()
    holed[2, 3, 7] = np.nan
    got = float(jnwb.jrsa(holed, x2, metric="pearson", stats=False, rng=0).value)
    dropped = float(jnwb.jrsa(np.delete(x1, 7, -1), np.delete(x2, 7, -1),
                              metric="pearson", stats=False, rng=0).value)
    assert got == dropped


# --------------------------------------------------------------- aperiodic sign


def test_the_aperiodic_exponent_is_positive_and_the_tilt_slope_is_negative():
    text = _flat(_page("docs/04_spectral_analysis_and_tfr.md"))
    assert "slope = -exponent" in text
    fit_near = float(re.search(r"`aperiodic_fit` returns that exponent, near ([+-]\d)", text)[1])
    tilt_near = float(re.search(r"`spectral_tilt` returns the slope, near ([+-]\d)", text)[1])

    # The trace of the page's figure: a random walk plus a 10 Hz rhythm.
    fs = 1000.0
    t = np.arange(5000) / fs
    walk = np.cumsum(np.random.default_rng(12).standard_normal(len(t)))
    lfp = (walk - walk.mean()) / walk.std() + 0.8 * np.sin(2 * np.pi * 10.0 * t)
    tilt = jnwb.spectral_tilt(lfp, fs=fs, freq_range=(2.0, 90.0))["exponent"]
    freqs, psd = jnwb.compute_psd(lfp, fs=fs)
    fit = jnwb.aperiodic_fit(freqs[1:], psd[1:], freq_range=(2.0, 90.0), mode="fixed").exponent
    assert abs(tilt - tilt_near) < 0.5, tilt
    assert abs(float(fit) - fit_near) < 0.5, fit
    assert float(fit) > 0 > tilt, (fit, tilt)


# --------------------------------------------------------------- zflip raises


def _zflip_input(n_channels=4, n_samples=2000):
    return np.random.default_rng(1).normal(size=(n_channels, n_samples))


ZFLIP_OK = dict(fs=1000.0, orientation="superficial_to_deep", n_surrogates=0)

ZFLIP_RAISES = {
    "orientation outside the two orders": (_zflip_input(), {"orientation": "up"}),
    "not 2-D": (np.zeros((4, 4, 50)), {}),
    "fewer than 3 channels": (_zflip_input(2), {}),
    "a NaN sample": (np.where(np.eye(4, 2000, 5) > 0, np.nan, _zflip_input()), {}),
    "fs not positive": (_zflip_input(), {"fs": 0.0}),
    "pitch_um not positive": (_zflip_input(), {"pitch_um": -1.0}),
    "freq_range not increasing": (_zflip_input(), {"freq_range": (35.0, 15.0)}),
    "alpha outside (0, 1)": (_zflip_input(), {"alpha": 1.5}),
    "negative n_surrogates": (_zflip_input(), {"n_surrogates": -1}),
    "threshold outside [0, 1]": (_zflip_input(), {"min_wpli": 2.0}),
    "one segment": (_zflip_input(), {"nperseg": 2000, "noverlap": 0}),
}


def _zflip_cell():
    return _table_row(_page("docs/10_operation_specifications.md"), "`zflip`")[6]


def test_the_zflip_row_lists_only_raises_the_code_has():
    cell = _zflip_cell()
    for absent in ("imaginary coherency", "ill-conditioned"):
        assert absent not in cell, f"the zflip row still claims a raise for {absent}"
    for phrase in ("fewer than 3 channels", "NaN or Inf", "fewer than 2 segments",
                   "`TypeError` when `orientation` is omitted"):
        assert phrase in cell, phrase
    with pytest.raises(TypeError):
        jnwb.zflip(_zflip_input(), fs=1000.0)
    # Identical channels have zero imaginary coherency; no raise follows from it.
    same = np.tile(_zflip_input(1), (4, 1))
    jnwb.zflip(same, **ZFLIP_OK)
    narrow = jnwb.zflip(_zflip_input(), **{**ZFLIP_OK, "freq_range": (15.0, 15.5)})
    assert narrow.accepted is False


@pytest.mark.parametrize("case", sorted(ZFLIP_RAISES))
def test_each_listed_zflip_condition_raises(case):
    data, overrides = ZFLIP_RAISES[case]
    with pytest.raises(ValueError):
        jnwb.zflip(data, **{**ZFLIP_OK, **overrides})


# --------------------------------------------------------------- sliding-window p floor


def test_the_sliding_window_recipe_states_the_floor_its_null_imposes():
    page = _page("docs/03_representational_similarity_jrsa.md")
    recipe = page.split("### Sliding Windows", 1)[1].split("## 4.", 1)[0]
    width = int(re.search(r"width, step = (\d+), \d+", recipe)[1])
    lag = int(re.search(r"lag=(\d+)", recipe)[1])
    n = width - lag
    text = _flat(recipe)
    assert f"runs on {n} and p cannot fall below about 1/{n}, which is above 0.05" in text
    assert 1 / n > 0.05

    # x2 is x1 moved back by the lag, so the lagged pairs are identical and the observed
    # value is the largest any shift can give: p sits at the floor.
    x1 = np.random.default_rng(2).normal(size=(12, 10, 50))
    x2 = np.roll(x1, -lag, axis=-1)
    res = jnwb.jrsa(x1, x2, metric="pearson", window=(0, width), lag=lag, rng=0)
    assert res.execution["n_overlap"] == n
    assert res.p > 0.05 and abs(res.p - 1 / n) < 0.03, res.p
