"""Statements on the method and troubleshooting pages, each held against the code it describes.

Every test here reads the statement off the page and checks it against a call, a signature or
a return value, so an edit that makes a pinned statement false fails, and so does a code change
that makes the page stale. Where parsing a sentence is impractical the sentence is pinned whole:
rewording it then fails the test, and the new wording has to be checked against the same
behaviour before the pin moves. None derives its expected value from the introspection it
checks without also reading the page.
"""
from __future__ import annotations

import ast
import importlib
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
    with pytest.warns(UserWarning, match="No 'codes' column") as record:
        jnwb.events(nwb)
    assert "Columns: [" in str(record[0].message), "the warning no longer names the columns"

    row = _table_row(_page("docs/errors.md"), "No `codes` column")
    assert _ticked(row[1]) == ["events"], row[1]
    assert row[2] == "The onsets, without codes. `event_onsets` returns them without the warning"
    # Each page's sentence, pinned whole: a reworded sentence is re-checked here by a reader
    # against the behaviour above rather than passing on a keyword.
    stated = {
        "README.md": "On a table with no `codes` column, `events` returns the onsets and warns; "
                     "`event_onsets` without `codes=` returns them silently.",
        "docs/errors.md": "`events` returns them with a warning that names the columns, and "
                          "`event_onsets` without `codes=` returns them without one.",
        "docs/common_mistakes.md": "on a table with no `codes` column, `events` returns its "
                                   "onsets and warns that it found no codes.",
    }
    for name, sentence in stated.items():
        assert sentence in _flat(_page(name)), f"{name} no longer states: {sentence}"


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


def _synth_rng_builders():
    import jnwb.testing.synth as synth

    return {f"synth.{n}": f for n, f in vars(synth).items()
            if inspect.isfunction(f) and f.__module__ == synth.__name__
            and not n.startswith("_") and "rng" in inspect.signature(f).parameters}


def _stochastic_surfaces() -> set[str]:
    """Every public function with an `rng` parameter, from signatures alone."""
    return {q for q, _ in _public_rng_parameters()} | set(_synth_rng_builders())


RNG_TABLE_ROWS = {
    "strict": "an `int` seed, a `Generator`, or `None`",
    "default_rng": "whatever `np.random.default_rng` takes: an `int` seed, a `Generator`, `None`, "
                   "a `SeedSequence`, a bit generator, a list of ints, or a `bool`",
    "generator": "a `np.random.Generator` only",
    "int": "an `int` only",
}


def _row_functions(cell: str) -> set[str]:
    names = set()
    for name in _ticked(cell):
        if name == "StatisticalAnalysis":
            names |= {q for q, _ in _public_rng_parameters()
                      if q.startswith("StatisticalAnalysis.")}
        elif name == "testing.synth":
            names |= set(_synth_rng_builders())
        else:
            names.add(name)
    return names


def _rng_rows():
    page = _page("docs/10_operation_specifications.md")
    return {key: _table_row(page, first) for key, first in RNG_TABLE_ROWS.items()}


def test_the_rng_table_places_every_stochastic_function_in_exactly_one_row():
    surfaces = _stochastic_surfaces()
    assert len(surfaces) >= 25, f"the signature walk found only {len(surfaces)}"
    rows = {key: _row_functions(cells[1]) for key, cells in _rng_rows().items()}
    placed = [name for names in rows.values() for name in names]
    assert len(placed) == len(set(placed)), "a function sits in two rows"
    assert set(placed) == surfaces, (sorted(surfaces - set(placed)), sorted(set(placed) - surfaces))
    assert set(_rng_probes()) == surfaces, "a stochastic function has no probe below"
    for qualname, param in _public_rng_parameters():
        ann = _annotation(param)
        if qualname in rows["generator"]:
            assert ann == "np.random.Generator", (qualname, ann)
        if qualname in rows["int"]:
            assert ann == "int", (qualname, ann)


def _rng_probes():
    """One minimal call per stochastic function, large enough that it draws from `rng`."""
    import jnwb.testing.synth as synth

    g = np.random.default_rng(9)
    a, b = g.normal(size=30), g.normal(size=30)
    x8, y8 = g.normal(size=(8, 20)), g.normal(size=(8, 20))
    s1, s2 = g.normal(size=4000), g.normal(size=4000)
    t1, t2 = g.normal(size=1000), g.normal(size=1000)
    m1, m2 = g.normal(size=(200, 4)), g.normal(size=(200, 4))
    j1, j2 = g.normal(size=(6, 5, 30)), g.normal(size=(6, 5, 30))
    xs, labs = g.normal(size=(40, 5)), np.arange(40) % 2
    x6, z4 = g.normal(size=(6, 200)), g.normal(size=(4, 2000))
    sa = jnwb.StatisticalAnalysis
    return {
        "StatisticalAnalysis.bootstrap_ci": lambda r: sa.bootstrap_ci(a, n_bootstrap=20, rng=r),
        "StatisticalAnalysis.compare_groups": lambda r: sa.compare_groups(a, b, n_bootstrap=20,
                                                                          rng=r),
        "StatisticalAnalysis.exact_sign_flip": lambda r: sa.exact_sign_flip(a, n_mc=20, rng=r),
        "StatisticalAnalysis.permutation_test": lambda r: sa.permutation_test(
            a, b, n_permutations=20, rng=r),
        "cluster_permutation_test": lambda r: jnwb.cluster_permutation_test(
            x8, y8, n_permutations=20, rng=r),
        "cross_area_coherence": lambda r: jnwb.cross_area_coherence(
            s1, s2, fs=1000.0, freq_bands="canonical", n_surrogates=5, rng=r),
        "cross_modal_comparison": lambda r: jnwb.cross_modal_comparison(
            m1, m2, lag_range_ms=(-50, 50), bin_ms=10.0, n_permutations=20, rng=r),
        "exact_sign_flip": lambda r: jnwb.exact_sign_flip(a, n_mc=20, rng=r),
        "granger": lambda r: jnwb.granger(t1, t2, order=2, n_surrogates=5, rng=r),
        "granger_spectral": lambda r: jnwb.granger_spectral(t1, t2, fs=100.0, order=2,
                                                            n_surrogates=5, rng=r),
        "jrsa": lambda r: jnwb.jrsa(j1, j2, metric="pearson", permutations=20, rng=r),
        "nested_cv_linear_svm": lambda r: jnwb.nested_cv_linear_svm(xs, labs, 3, rng=r),
        "phase_slope_index": lambda r: jnwb.phase_slope_index(
            t1, t2, fs=100.0, bands=(10.0, 30.0), n_surrogates=5, rng=r),
        "resample_onsets": lambda r: jnwb.resample_onsets(np.arange(10.0), target_n=20, rng=r),
        "shuffle_r2_ci": lambda r: jnwb.shuffle_r2_ci(a, a + b, n_shuffle=10, rng=r),
        "transfer_entropy": lambda r: jnwb.transfer_entropy(t1[:300], t2[:300], n_surrogates=5,
                                                            rng=r),
        "xflip": lambda r: jnwb.xflip(x6, n_surrogates=5, rng=r),
        "zflip": lambda r: jnwb.zflip(z4, 1000.0, orientation="superficial_to_deep",
                                      n_surrogates=5, rng=r),
        "shuffle_pvalue_paired": lambda r: jnwb.shuffle_pvalue_paired(a, b, 20, r),
        "shuffle_pvalue_unpaired": lambda r: jnwb.shuffle_pvalue_unpaired(a, b, 20, r),
        "paired_fire_prob_test": lambda r: jnwb.paired_fire_prob_test(a > 0, b > 0, 20, 20, r),
        "permute_labels": lambda r: jnwb.permute_labels(np.arange(10), scheme="global", rng=r),
        "build_permutation_plan": lambda r: jnwb.build_permutation_plan(
            np.arange(10) % 2, np.arange(10) // 5, n_permutations=3, rng=r),
        "synth.synth_white_noise": lambda r: synth.synth_white_noise(10, rng=r),
        "synth.synth_ar_noise": lambda r: synth.synth_ar_noise(50, tau_s=0.01, rng=r),
        "synth.synth_periodic_response": lambda r: synth.synth_periodic_response(2, 50, 1000.0,
                                                                                 rng=r),
        "synth.synth_correlation_blocks": lambda r: synth.synth_correlation_blocks(
            [2, 2], n_samples=50, rng=r),
        "synth.synth_phase_gradient": lambda r: synth.synth_phase_gradient(3, 100, 1000.0, rng=r),
        "synth.synth_unequal_groups": lambda r: synth.synth_unequal_groups(3, 4, 2, rng=r),
        "synth.synth_laminar_motif": lambda r: synth.synth_laminar_motif(16, 2000, rng=r),
    }


#: How each kind of value is spelled in the table, and one instance of it.
RNG_KINDS = {
    "`int`": lambda: 3,
    "`Generator`": lambda: np.random.default_rng(3),
    "`None`": lambda: None,
    "`SeedSequence`": lambda: np.random.SeedSequence(3),
    "bit generator": lambda: np.random.PCG64(3),
    "list": lambda: [1, 2],
    "`bool`": lambda: True,
    "`float`": lambda: 2.5,
}


@pytest.mark.parametrize("row_key", ["strict", "default_rng"])
def test_each_rng_row_accepts_and_refuses_what_it_says(row_key):
    """Every kind of value appears in exactly one of the row's two cells; each named as
    accepted is accepted by every function of the row, each in the other cell raises
    `TypeError` from every one."""
    cells = _rng_rows()[row_key]
    accepted_cell, refused_cell = cells[0], cells[2]
    probes = _rng_probes()
    wrong = []
    for kind, make in RNG_KINDS.items():
        where = (kind in accepted_cell, kind in refused_cell)
        assert where in ((True, False), (False, True)), f"{kind!r} in {row_key}: {where}"
        for name in sorted(_row_functions(cells[1])):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    probes[name](make())
                    outcome = "accepted"
                except TypeError:
                    outcome = "TypeError"
            expected = "accepted" if where[0] else "TypeError"
            if outcome != expected:
                wrong.append(f"{name} with {kind}: {outcome}, the page says {expected}")
    assert not wrong, "\n".join(wrong)


def test_a_generator_only_surface_refuses_an_int_and_none():
    cells = _rng_rows()["generator"]
    assert cells[2] == "`TypeError` from `permute_labels`; `AttributeError` from the other three"
    probes = _rng_probes()
    for name in sorted(_row_functions(cells[1])):
        probes[name](np.random.default_rng(0))
        expected = TypeError if name == "permute_labels" else AttributeError
        for value in (0, None):
            with pytest.raises(expected):
                probes[name](value)


def test_build_permutation_plan_takes_only_an_int():
    cells = _rng_rows()["int"]
    assert cells[2] == "`TypeError`"
    call = _rng_probes()["build_permutation_plan"]
    call(4)
    for value in (None, np.random.default_rng(4), 2.5):
        with pytest.raises(TypeError):
            call(value)


def test_the_statistics_page_states_the_default_seed_and_links_the_table():
    text = _flat(_page("docs/07_statistical_inference_and_nulls.md"))
    assert "The `StatisticalAnalysis` methods default to the seed `42`." in text
    assert "(10_operation_specifications.md#1-rng-convention)" in text
    defaults = {q: p.default for q, p in _public_rng_parameters()
                if q.startswith("StatisticalAnalysis.")}
    assert len(defaults) == 4 and all(d == 42 for d in defaults.values()), defaults


# --------------------------------------------------------------- structured returns


def _result_class(name):
    import jnwb.testing.synth as synth

    obj = getattr(jnwb, name, None) or getattr(synth, name, None)
    return obj if inspect.isclass(obj) else None


def test_the_structured_return_bullet_splits_every_result_class_by_mapping_access():
    """The classes are the ones the operation table returns plus the bullet's examples; each
    must be in the mapping list or the attribute-only list, as the class actually is."""
    page = _page("docs/10_operation_specifications.md")
    table = page.split("\n## 2. Operation Specifications\n", 1)[1]
    returned = {n for line in table.splitlines() if line.startswith("| `")
                for n in _ticked(line.strip("|").split("|")[5])
                if re.fullmatch(r"[A-Z]\w+", n) and _result_class(n)}
    section = page.split("### 4. Structured Return Types", 1)[1].split("###", 1)[0]
    examples = set(_ticked(re.search(r"\(e\.g\. ([^)]*)\)", section).group(1)))
    classes = returned | examples
    assert {"ProbeGeometry", "SynthLaminarReceipt", "VFlipResult"} <= returned, returned
    flat = _flat(section)
    mapping = set(_ticked(re.search(r"- ((?:`\w+`(?:, | and ))+`\w+`) implement `\.to_dict\(\)`",
                                    flat).group(1)))
    attribute_only = set(_ticked(re.search(r"serialize\. (.*?) are attribute-only", flat).group(1)))
    live_mapping = {n for n in classes
                    if hasattr(_result_class(n), "to_dict")
                    and hasattr(_result_class(n), "__getitem__")}
    assert mapping == live_mapping, (sorted(mapping), sorted(live_mapping))
    assert attribute_only == classes - live_mapping, (sorted(attribute_only),
                                                      sorted(classes - live_mapping))
    for name in attribute_only:
        cls = _result_class(name)
        assert not hasattr(cls, "to_dict") and not hasattr(cls, "__getitem__"), name


# --------------------------------------------------------------- per-iteration seeds


def _recorded_items(monkeypatch, module, call):
    """The items each `parallel_map` call in `module` received while `call` ran."""
    import importlib

    mod = importlib.import_module(module)
    original, seen = mod.parallel_map, []

    def recording(fn, items, *args, **kwargs):
        seen.append(list(items))
        return original(fn, items, *args, **kwargs)

    monkeypatch.setattr(mod, "parallel_map", recording)
    call()
    return seen


def test_every_parallel_draw_is_made_before_the_workers_start(monkeypatch):
    """The property (identical at every `n_jobs`) is exercised by `tests/test_parallel.py`;
    this pins the mechanism each row names: what the workers are handed is already drawn."""
    from jnwb._parallel import spawn_seeds

    page = _page("docs/10_operation_specifications.md")
    flat = _flat(page)
    assert ("a result computed across workers is fixed by iteration index and identical at "
            "every `n_jobs`, because every draw an iteration needs is made from the caller's "
            "`rng` before any worker starts") in flat
    rows = {cells[0]: cells[1] for line in page.splitlines()
            if line.startswith("| `") and line.count("|") == 3
            for cells in [[c.strip() for c in line.strip().strip("|").split("|")]]}
    assert set(rows) == {"`cluster_permutation_test`", "`jrsa`", "`cross_area_coherence`"}, rows

    # cluster_permutation_test: the workers get spawn_seeds(rng, n_permutations).
    cell = rows["`cluster_permutation_test`"]
    assert "`jnwb._parallel.spawn_seeds`" in cell
    assert "`np.random.SeedSequence(entropy).spawn(n_permutations)`" in cell
    x = np.random.default_rng(1).normal(size=(8, 20))
    seen = _recorded_items(monkeypatch, "jnwb.statistics", lambda: jnwb.cluster_permutation_test(
        x, x + 0.1, n_permutations=12, rng=np.random.default_rng(5)))
    entropy = int(np.random.default_rng(5).integers(0, 2**63 - 1))
    expected = np.random.SeedSequence(entropy).spawn(12)
    got = seen[0]
    assert len(got) == 12
    for g, e in zip(got, expected):
        np.testing.assert_array_equal(g.generate_state(4), e.generate_state(4))
    reference = spawn_seeds(np.random.default_rng(5), 12)
    np.testing.assert_array_equal(reference[3].generate_state(4), got[3].generate_state(4))

    # jrsa: one integer seed per permutation.
    assert rows["`jrsa`"] == "one integer seed per permutation"
    j = np.random.default_rng(2).normal(size=(6, 5, 30))
    seen = _recorded_items(monkeypatch, "jnwb.jrsa", lambda: jnwb.jrsa(
        j, j[::-1], metric="pearson", permutations=15, rng=0))
    assert len(seen) == 1 and len(seen[0]) == 15
    assert all(isinstance(s, (int, np.integer)) for s in seen[0]), seen[0][:3]

    # cross_area_coherence: every surrogate shift, drawn from rng.
    assert rows["`cross_area_coherence`"] == "every surrogate shift"
    s = np.random.default_rng(3).normal(size=(2, 4000))
    seen = _recorded_items(monkeypatch, "jnwb.spectral", lambda: jnwb.cross_area_coherence(
        s[0], s[1], fs=1000.0, freq_bands="canonical", n_surrogates=6, rng=11))
    shifts = np.random.default_rng(11).integers(1, 4000 - 1, size=6)
    assert [int(v) for v in seen[0]] == [int(v) for v in shifts]


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

    assert "snr_good_rate (a fraction, 0 to 1)" in text.replace("\n", " ").replace("  ", " ")

    frame = pd.DataFrame({"session_id": ["a", "b"], "snr_mean": [1.2, 0.4],
                          "total_units": [10, 4]})
    plt.close(jnwb.visual_qc.compare_session_quality(frame))
    # A fraction in, a percentage drawn: 0.6 is a bar of height 60.
    fig = jnwb.visual_qc.compare_session_quality(frame.assign(snr_good_rate=[0.6, 0.2]))
    heights = [p.get_height() for p in fig.axes[2].patches]
    assert np.allclose(heights, [60.0, 20.0]), heights
    plt.close(fig)
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


def test_the_network_matrix_is_directed_with_the_orientation_the_page_states():
    page = _page("docs/08_directed_connectivity_and_information.md")
    assert "Net matrix" not in page and 'print("Directed matrix shape:"' in page
    stated = re.search(r"# M\[i, j\]: influence of ([ij]) on ([ij])", page)
    assert stated, "the orientation comment moved"
    source, target = stated.groups()
    rng = np.random.default_rng(0)
    x = rng.normal(size=400)
    y = np.roll(x, 1) + 0.5 * rng.normal(size=400)          # A drives B
    net = jnwb.directed_network({"A": x, "B": y, "C": rng.normal(size=400)},
                                method="granger", order=2, fdr=False, n_surrogates=0, rng=0)
    m = net["matrix"]
    a, b = net["labels"].index("A"), net["labels"].index("B")
    index = {"i": a, "j": b} if (source, target) == ("i", "j") else {"i": b, "j": a}
    assert m[index["i"], index["j"]] > 10 * m[index["j"], index["i"]], m
    off = ~np.eye(3, dtype=bool)
    assert not np.allclose(m[off], -m.T[off]), "the matrix reads as a net matrix"


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


def _conditions():
    rng = np.random.default_rng(0)
    x1 = rng.normal(size=(6, 10, 40))
    return x1, x1 + rng.normal(size=x1.shape)


def test_the_page_says_every_metric_raises_when_no_sample_remains():
    text = _flat(_page("docs/03_representational_similarity_jrsa.md"))
    assert "if none remain, every metric raises `ValueError`" in text, "the nan_policy statement moved"


@pytest.mark.parametrize("metric", sorted(importlib.import_module("jnwb.jrsa")._METRIC_DISPATCH))
def test_an_empty_condition_raises_for_every_metric(metric):
    x1, x2 = _conditions()
    x1[2] = np.nan
    with pytest.raises(ValueError):
        jnwb.jrsa(x1, x2, metric=metric, stats=False, rng=0)


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
                   "`TypeError` when `orientation` is omitted",
                   "Fewer than 3 frequency bins in `freq_range` returns `accepted=False`."):
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
