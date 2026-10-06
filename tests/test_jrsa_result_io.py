"""`JRSAResult.summary`, `plot` and `save`, executed on small results.

`save` used to drop data silently: csv kept only the fields that are not arrays, so `value`,
`p`, `q`, `ci` and the null were missing from the file, and npz kept only the arrays, so
`metric`, `parameters` and `execution` (with the seed) were missing. Every field now
round-trips in every format, read back through the private `_result_load`.
"""

from __future__ import annotations

import dataclasses
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

import jnwb  # noqa: E402
from jnwb.jrsa._result import JRSAResult, _result_load  # noqa: E402

FORMATS = ("npz", "json", "csv")


@pytest.fixture(scope="module")
def scalar_result():
    """A real jrsa result: 0-d value, p and q, a 1-D ci and null, seed 7."""
    rng = np.random.default_rng(0)
    x1 = rng.normal(size=(8, 20))
    x2 = x1 + 0.5 * rng.normal(size=(8, 20))
    return jnwb.jrsa(x1, x2, metric="rsa", stats=True, permutations=50, null="iid",
                     bootstrap=20, correction="fdr_bh", rng=7, return_null=True)


@pytest.fixture(scope="module")
def matrix_result():
    """A signed 2-D value, a 3-D ci and a NaN, the shapes csv lays out as blocks."""
    value = np.array([[1.0, -0.25, np.nan], [-0.25, 1.0, 0.5]])
    return JRSAResult(
        value=value, statistic=value * 2, p=np.full((2, 3), 0.04), q=np.full((2, 3), 0.08),
        ci=np.stack([value - 0.1, value + 0.1], axis=-1), metric="pearson",
        axes=(0, 1), aligned_axes=(1,), labels=["a", "b"],
        parameters={"alpha": 0.05, "lag": [0, 1], "correction": "fdr_bh"},
        null_distribution=np.arange(12.0).reshape(2, 3, 2),
        execution={"backend": "numpy", "seed": 11, "runtime": 0.123456789, "n_overlap": 8},
    )


def _assert_same(read, original):
    for f in dataclasses.fields(original):
        want, got = getattr(original, f.name), read[f.name]
        if f.name in ("value", "statistic", "effect", "p", "q", "df", "ci",
                      "null_distribution", "aligned_x1", "aligned_x2") and want is not None:
            np.testing.assert_array_equal(got, want, err_msg=f.name)
            assert np.shape(got) == np.shape(want), f.name
        else:
            assert got == want, f.name


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("which", ["scalar_result", "matrix_result"])
def test_save_round_trips_every_field(which, fmt, request, tmp_path):
    result = request.getfixturevalue(which)
    path = tmp_path / f"r.{fmt}"
    result.save(str(path), fmt=fmt)
    read = _result_load(str(path), fmt)
    _assert_same(read, result)
    assert read["execution"]["seed"] == result.execution["seed"]
    rebuilt = JRSAResult(**read)
    assert rebuilt.metric == result.metric


def test_csv_holds_a_2d_value_as_a_matrix_block(matrix_result, tmp_path):
    path = tmp_path / "r.csv"
    matrix_result.save(str(path), fmt="csv")
    lines = path.read_text().splitlines()
    assert "value.shape,2,3" in lines
    assert "value[1],-0.25,1.0,0.5" in lines
    assert "metric,pearson" in lines


def test_npz_carries_the_other_fields_as_one_json_string(scalar_result, tmp_path):
    path = tmp_path / "r.npz"
    scalar_result.save(str(path), fmt="npz")
    with np.load(path, allow_pickle=False) as z:
        fields = json.loads(str(z["fields_json"]))
    assert fields["metric"] == "rsa"
    assert fields["execution"]["seed"] == 7
    assert fields["parameters"]["random_state"] == 7


# ---------------------------------------------------------------------------
# Files written by 0.2.9 still read
# ---------------------------------------------------------------------------

def _save_0_2_9(result, path, fmt):
    """The body of `_result_save` as released in 0.2.9 (`jnwb/jrsa.py` at tag v0.2.9)."""
    if fmt == "npz":
        payload = {k: v for k, v in result.__dict__.items()
                   if isinstance(v, (np.ndarray, type(None)))}
        np.savez_compressed(path, **{k: v for k, v in payload.items() if v is not None})
    elif fmt == "json":
        def _serial(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return str(obj)
        with open(path, "w") as fh:
            json.dump(result.__dict__, fh, default=_serial, indent=2)
    elif fmt == "csv":
        import csv
        rows = [(k, v) for k, v in result.__dict__.items() if not isinstance(v, np.ndarray)]
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["field", "value"])
            writer.writerows(rows)


@pytest.mark.parametrize("fmt", FORMATS)
def test_a_file_written_by_0_2_9_still_reads(matrix_result, fmt, tmp_path):
    path = tmp_path / f"old.{fmt}"
    _save_0_2_9(matrix_result, str(path), fmt)
    read = _result_load(str(path), fmt)
    if fmt == "npz":  # 0.2.9 wrote the arrays only
        assert set(read) == {"value", "statistic", "p", "q", "ci", "null_distribution"}
        np.testing.assert_array_equal(read["value"], matrix_result.value)
    elif fmt == "csv":  # 0.2.9 wrote the non-array fields only, as Python text
        assert read["metric"] == "pearson"
        assert read["df"] is None and read["aligned_x1"] is None
        assert read["execution"] == str(matrix_result.execution)
    else:
        _assert_same(read, matrix_result)


def test_unknown_format_raises(scalar_result, tmp_path):
    with pytest.raises(ValueError, match="Unknown format"):
        scalar_result.save(str(tmp_path / "r.txt"), fmt="txt")


# ---------------------------------------------------------------------------
# summary and plot
# ---------------------------------------------------------------------------

def test_summary_prints_and_returns_the_fields(scalar_result, capsys):
    text = scalar_result.summary()
    assert capsys.readouterr().out.strip() == text.strip()
    lines = text.splitlines()
    assert lines[0] == "JRSAResult Summary"
    assert f"  metric     : rsa" in lines
    assert f"  p (raw)    : {scalar_result.p}" in lines


def _clim(fig):
    return fig.axes[0].images[0].get_clim()


def test_plot_centres_a_signed_matrix_on_zero(matrix_result):
    fig = matrix_result.plot()
    try:
        assert _clim(fig) == (-1.0, 1.0)
        assert fig.axes[0].images[0].get_cmap().name == "RdBu_r"
    finally:
        plt.close(fig)


def test_plot_leaves_a_one_signed_matrix_autoscaled():
    fig = JRSAResult(value=np.array([[0.2, 0.5], [0.5, 0.9]])).plot()
    try:
        assert _clim(fig) == (0.2, 0.9)
    finally:
        plt.close(fig)


def test_plot_centres_on_the_larger_magnitude_when_the_negative_side_is_larger():
    fig = JRSAResult(value=np.array([[-0.9, 0.1], [0.0, 0.05]])).plot()
    try:
        assert _clim(fig) == (-0.9, 0.9)
    finally:
        plt.close(fig)


def test_json_writes_numpy_integers_as_numbers(tmp_path):
    path = tmp_path / "np_int.json"
    JRSAResult(value=np.array([1.0]), parameters={"a": np.int64(7), "b": np.int32(3)}).save(str(path), fmt="json")
    assert json.loads(path.read_text())["parameters"] == {"a": 7, "b": 3}


def test_plot_kwargs_win_over_the_centring(matrix_result):
    fig = matrix_result.plot(vmin=-0.5, vmax=2.0, cmap="viridis")
    try:
        assert _clim(fig) == (-0.5, 2.0)
        assert fig.axes[0].images[0].get_cmap().name == "viridis"
    finally:
        plt.close(fig)


def test_plot_draws_a_vector_as_a_line():
    fig = JRSAResult(value=np.array([0.1, -0.2, 0.3])).plot()
    try:
        np.testing.assert_array_equal(fig.axes[0].lines[0].get_ydata(), [0.1, -0.2, 0.3])
    finally:
        plt.close(fig)
