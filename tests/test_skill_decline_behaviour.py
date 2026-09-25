"""A skill routes to an operation or it declines, and the routed call says which.

Four outcomes, each settled by a real call into jnwb on small synthetic arrays:

    supported  the routed call runs and returns the documented value
    request    missing input is requested: the call raises and names what is missing
    failure    a non-identifiable result is reported as a failure -- a raise, a rejection
               flag, or NaN/None with a flag -- never as a plausible number
    decline    an unsupported claim is declined: the call raises, or the skill text declines
               the claim and the routed call exposes no output that could carry it

Every skill on disk is either tested for an outcome here or listed in ``NOT_REQUIRED`` with
the reason it needs none; ``test_every_skill_outcome_is_tested_or_excused`` holds the two
together. ``test_a_row_states_the_undefined_case`` covers calls that once returned a finite
value for a case with no estimate: each now returns NaN with its flag, and the routing row
states that value; when the code changes, the row and this test change with it.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import jnwb

SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"
OUTCOMES = ("supported", "request", "failure", "decline")

_ROUTER = (
    "routes to the domain skills and runs no operation of its own; each outcome is tested at "
    "the skill it routes to"
)
_PROCESS = "governs how changes to this repository are made and routes to no jnwb operation"

NOT_REQUIRED: dict[tuple[str, str], str] = {
    **{("jnwb", o): _ROUTER for o in OUTCOMES},
    **{("jnwb-fact-action", o): _PROCESS for o in OUTCOMES},
    ("jnwb-figures", "request"): (
        "its routes draw arrays and axes the caller already holds; no scientific input can be "
        "missing"
    ),
    ("jnwb-figures", "failure"): "it estimates nothing, so there is no estimate to fail",
    ("jnwb-figures", "decline"): (
        "it draws values and states no inference; a figure's barred claim is sealed through "
        "jnwb-landmark-viz"
    ),
    ("jnwb-landmark-viz", "failure"): "it renders values the caller computed and estimates nothing",
}

CASES: dict[tuple[str, str], object] = {}


def case(skill: str, outcome: str):
    def register(fn):
        assert (skill, outcome) not in CASES, (skill, outcome)
        CASES[(skill, outcome)] = fn
        return fn

    return register


def skill_text(name: str) -> str:
    """The skill's text with every run of whitespace collapsed, so line wrapping is irrelevant."""
    raw = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", raw)


def assert_states(skill: str, *phrases: str) -> None:
    text = skill_text(skill)
    missing = [p for p in phrases if p not in text]
    assert not missing, f"skills/{skill}/SKILL.md no longer states {missing}"


def _propagating_lfp(n_channels=8, n=2000, lag=2, noise=0.05, seed=0):
    """Broadband source reaching each deeper contact ``lag`` samples later."""
    rng = np.random.default_rng(seed)
    src = rng.normal(size=n + lag * n_channels)
    off = lag * n_channels
    lfp = np.stack([src[off - k * lag: off - k * lag + n] for k in range(n_channels)])
    return lfp + noise * rng.normal(size=lfp.shape)


def _directed_pair(seed=0, n=1000):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    y = np.zeros(n)
    y[1:] = 0.5 * x[:-1] + 0.5 * rng.normal(size=n - 1)
    return x, y


def _nwb():
    from jnwb.testing.nwb_fixtures import build_synth_nwb, canonical_co_resident_options

    return build_synth_nwb(canonical_co_resident_options())


def _canvas():
    pytest.importorskip("plotly")
    import jnwb.vis as jviz

    return jviz, jviz.PlotlyPublicationCanvas(layout="1col", height_mm=60, rows=1, cols=1, tags=[["A"]])


def _spectrolaminar(crossover_depth=None):
    jviz, canvas = _canvas()
    rng = np.random.default_rng(0)
    kwargs = {} if crossover_depth is None else {"crossover_depth": crossover_depth}
    jviz.laminar.plot_spectrolaminar_map(
        canvas=canvas, row=0, col=0, rel_power=rng.random((20, 8)),
        freqs=np.arange(1, 21), depths=np.linspace(0.0, 1.0, 8), depth_unit="relative", **kwargs,
    )
    notes = [a.text for a in canvas.fig.layout.annotations if "Crossover" in (a.text or "")]
    return canvas, notes


# --------------------------------------------------------------------------------- spiking


@case("jnwb-spiking", "supported")
def _():
    t = np.arange(0.0, 300.0, 1.0)
    fit = jnwb.fit_exponential_onset(t, np.where(t >= 100.0, 10.0, 1.0), t0_bounds_ms=(0.0, 250.0))
    assert fit["bound_status"] is None
    assert abs(fit["t0"] - 100.0) < 2.0


@case("jnwb-spiking", "request")
def _():
    with pytest.raises(ValueError, match="requires window_s"):
        jnwb.bin_spikes(np.array([0.1, 0.2]))


@case("jnwb-spiking", "failure")
def _():
    # The onset lies below the permitted range, so the fit stops at the bound and says so.
    t = np.arange(0.0, 300.0, 1.0)
    fit = jnwb.fit_exponential_onset(t, np.where(t >= 100.0, 10.0, 1.0), t0_bounds_ms=(150.0, 250.0))
    assert fit["bound_status"] == "lower"
    assert fit["t0"] == pytest.approx(150.0)


@case("jnwb-spiking", "decline")
def _():
    # An onset latency is never read off an acausal trace: the skill says so, the smoother
    # returns a bare trace with no latency in it, and the trace rises before the step does.
    assert_states("jnwb-spiking", "never measure an onset latency on a smoothed trace")
    step = np.r_[np.zeros(50), np.ones(50)]
    smooth = jnwb.gaussian_smooth_rate(step, bin_ms=1.0, sigma_ms=5.0)
    assert type(smooth) is np.ndarray and smooth.shape == step.shape
    assert smooth[45:50].min() > 0.0
    assert np.all(jnwb.causal_exp_smooth(step, bin_ms=1.0, tau_ms=5.0)[:50] == 0.0)


# ----------------------------------------------------------------------------- lfp-spectral


@case("jnwb-lfp-spectral", "supported")
def _():
    # 2 samples at 1 kHz per 100 um contact: 2 ms per channel, 0.05 m/s apparent velocity.
    res = jnwb.zflip(_propagating_lfp(), orientation="superficial_to_deep", fs=1000.0, pitch_um=100.0, n_surrogates=39)
    assert res.accepted and res.directionality == "superficial_to_deep"
    assert res.apparent_velocity_m_s == pytest.approx(0.05, rel=0.05)


@case("jnwb-lfp-spectral", "request")
def _():
    trace = np.random.default_rng(0).normal(size=2000)
    with pytest.raises(ValueError, match="requires a non-empty baseline"):
        jnwb.band_power(trace, fs=1000.0, freq_range=(13.0, 30.0))


@case("jnwb-lfp-spectral", "failure")
def _():
    # Propagating, but the deepest contact carries the source under noise of equal power: six
    # pairs pass the linearity gate and the last fails, so no delay exists for the shaft --
    # even though the six good pairs alone would give a clean, plausible velocity.
    lfp = _propagating_lfp()
    lfp[-1] += np.random.default_rng(5).normal(size=lfp.shape[1])
    res = jnwb.zflip(lfp, orientation="superficial_to_deep", fs=1000.0, pitch_um=100.0, n_surrogates=39)
    assert list(res.adjacent_identifiable) == [True] * 6 + [False]
    assert not res.accepted and not res.delay_identifiable
    assert res.directionality == "unidentifiable" and res.apparent_velocity_m_s is None
    assert res.rejection_reason == "Phase-frequency relation failed linear identifiability gate"
    vf = jnwb.vflip(np.ones((16, 200)), np.linspace(1.0, 200.0, 200))
    assert not vf.accepted and vf.crossover_contact is None


@case("jnwb-lfp-spectral", "decline")
def _():
    assert_states("jnwb-lfp-spectral", "so it carries no direction", "not a conduction velocity")
    x, y = _directed_pair()
    ab, ba = jnwb.wpli(x, y, fs=1000.0), jnwb.wpli(y, x, fs=1000.0)
    assert ab["wpli"] >= 0.0 and ab["wpli"] == pytest.approx(ba["wpli"])
    assert not [k for k in ab if re.search(r"direct|lead|lag|sign", k)]
    fields = jnwb.ZFlipResult.__dataclass_fields__
    assert not [f for f in fields if "conduction" in f]


# ----------------------------------------------------------------------------- connectivity


@case("jnwb-connectivity", "supported")
def _():
    x, y = _directed_pair()
    res = jnwb.granger(x, y, order=2, n_surrogates=39, rng=0)
    assert res.x_to_y > 100 * res.y_to_x
    assert res.p_x_to_y == pytest.approx(1 / 40)


@case("jnwb-connectivity", "request")
def _():
    s = np.sort(np.random.default_rng(0).uniform(0.0, 10.0, 50))
    with pytest.raises(ValueError, match="requires time_window_s"):
        jnwb.spike_mutual_information(s, s + 0.001)


@case("jnwb-connectivity", "failure")
def _():
    x, y = _directed_pair()
    res = jnwb.phase_slope_index(x, y, fs=1000.0, bands=(19.5, 20.5))
    band = res.per_band["band"]
    assert band["n_freq_bins"] == 1 and np.isnan(band["value"])
    assert res.diagnostics["ok_for_interpretation"] is False
    assert any("psi_undefined" in w for w in res.diagnostics["warnings"])


@case("jnwb-connectivity", "decline")
def _():
    assert_states(
        "jnwb-connectivity",
        "Unsigned coupling magnitude (e.g. wPLI $\\ge 0$) does not determine propagation direction",
    )
    x, y = _directed_pair()
    with pytest.raises(ValueError, match="Unknown method='wpli'"):
        jnwb.directed_connectivity(x, y, method="wpli")
    # Without a bin width no lag can be converted to samples, so no lag is claimed.
    rng = np.random.default_rng(0)
    out = jnwb.cross_modal_comparison(rng.normal(size=(50, 10)), rng.normal(size=(50, 10)))
    assert "lag_corrected_pvalue" not in out and out["lag_ms"] == 0.0
    assert out["interpretation"].startswith("Zero-lag")


# ------------------------------------------------------------------------------- statistics


@case("jnwb-statistics", "supported")
def _():
    from scipy import stats

    rng = np.random.default_rng(0)
    g1, g2 = rng.normal(1.0, 1.0, 20), rng.normal(0.0, 1.0, 20)
    res = jnwb.StatisticalAnalysis.exploratory_compare(g1, g2, n_bootstrap=200)
    assert res["parametric"]["pval"] == pytest.approx(stats.ttest_ind(g1, g2).pvalue)
    assert res["correction"] == "none"


@case("jnwb-statistics", "request")
def _():
    y = np.array([0, 1] * 5)
    with pytest.raises(TypeError, match="scheme"):
        jnwb.permute_labels(y, rng=np.random.default_rng(0))
    with pytest.raises(ValueError, match="requires groups"):
        jnwb.permute_labels(y, scheme="within_group", rng=np.random.default_rng(0))
    with pytest.raises(TypeError, match="explicit numpy.random.Generator"):
        jnwb.permute_labels(y, scheme="global", rng=0)


@case("jnwb-statistics", "failure")
def _():
    with pytest.warns(Warning):
        res = jnwb.StatisticalAnalysis.exploratory_correlate(
            np.ones(10), np.random.default_rng(0).normal(size=10)
        )
    for block in ("parametric", "non_parametric"):
        assert np.isnan(res[block]["statistic"]) and np.isnan(res[block]["pval"])
        assert np.isnan(res[block]["df"])
    assert res["significant_parametric"] is False and res["significant_nonparametric"] is False
    # A defined correlation keeps its integer degrees of freedom.
    defined = jnwb.StatisticalAnalysis.exploratory_correlate(np.arange(10.0), np.arange(10.0) ** 2)
    for block in ("parametric", "non_parametric"):
        assert type(defined[block]["df"]) is int and defined[block]["df"] == 8


@case("jnwb-statistics", "decline")
def _():
    assert_states(
        "jnwb-statistics",
        "the cluster's onset, offset, peak and width are not estimates",
    )
    rng = np.random.default_rng(0)
    res = jnwb.cluster_permutation_test(
        rng.normal(size=(10, 30)), rng.normal(size=(10, 30)) + 1.5, n_permutations=50, rng=0
    )
    assert res["clusters"]
    for cluster in res["clusters"]:
        assert set(cluster) == {"statistic", "p_value", "mask"}


# ------------------------------------------------------------------------------- population


@case("jnwb-population", "supported")
def _():
    rng = np.random.default_rng(0)
    labels = np.array([0] * 20 + [1] * 20)
    X = rng.normal(size=(40, 10))
    X[labels == 1] += 1.5
    res = jnwb.nested_cv_linear_svm(X, labels, n_splits=3)
    assert res["accuracy"] >= 0.9 > res["majority_baseline_accuracy"]


@case("jnwb-population", "request")
def _():
    raster = np.random.default_rng(0).normal(size=(5, 4, 6))
    with pytest.raises(ValueError, match="spatial metadata"):
        jnwb.build_representation_ladder(raster, modality="LFP")


@case("jnwb-population", "failure")
def _():
    X = np.random.default_rng(0).normal(size=(12, 4))
    res = jnwb.nested_cv_linear_svm(X, np.zeros(12, dtype=int), n_splits=3)
    assert res["status"] == "insufficient_classes_for_cv" and np.isnan(res["accuracy"])
    trials = pd.DataFrame({
        "trial_id": range(4), "session": "s", "analysis": "a", "slot_key": "k", "cycle": 0,
    })
    folds = jnwb.assign_outer_folds(trials)
    assert set(folds["outer_fold"]) == {-1}
    assert set(folds["outer_fold_status"]) == {"insufficient_groups"}


@case("jnwb-population", "decline")
def _():
    assert_states("jnwb-population", "it takes no `groups` and no fold column, so it cannot hold out whole blocks")
    rng = np.random.default_rng(0)
    with pytest.raises(TypeError, match="groups"):
        jnwb.nested_cv_linear_svm(
            rng.normal(size=(12, 4)), np.array([0, 1] * 6), n_splits=3, groups=np.arange(12) % 3
        )


# --------------------------------------------------------------------------------- nwb-data


@case("jnwb-nwb-data", "supported")
def _():
    from jnwb.testing.nwb_fixtures import TASK_TABLE

    nwb, receipt = _nwb()
    np.testing.assert_array_equal(jnwb.event_onsets(nwb, table=TASK_TABLE), receipt.task_onsets_s)


@case("jnwb-nwb-data", "request")
def _():
    from jnwb.nwb_events import AmbiguousIntervalTableError

    nwb, _receipt = _nwb()
    with pytest.raises(AmbiguousIntervalTableError, match="Pass table="):
        jnwb.event_onsets(nwb)


@case("jnwb-nwb-data", "failure")
def _():
    electrodes = pd.DataFrame({"location": ["V1"], "group_name": ["probeA"]}, index=[0])
    assert jnwb.map_peak_channel_to_area(0, electrodes) == "V1"
    assert jnwb.map_peak_channel_to_area(0, electrodes.drop(columns="location")) is None


@case("jnwb-nwb-data", "decline")
def _():
    from pynwb.ecephys import ElectricalSeries

    assert_states("jnwb-nwb-data", "is refused rather than given a rate")
    nwb, receipt = _nwb()
    region = nwb.create_electrode_table_region(list(range(receipt.n_channels)), "all")
    nwb.add_acquisition(ElectricalSeries(
        name="stamped", data=np.zeros((200, receipt.n_channels)), electrodes=region,
        timestamps=np.arange(1, 201) * 0.001,
    ))
    with pytest.raises(Exception, match="has no constant sampling rate"):
        jnwb.acquisition_channel(nwb, name="stamped")
    entry = [a for a in jnwb.inspect(nwb)["acquisitions"] if a["name"] == "stamped"]
    assert entry and entry[0]["rate_hz"] is None


# ---------------------------------------------------------------------------------- figures


@case("jnwb-figures", "supported")
def _():
    onsets = np.arange(5.0)
    drawn = jnwb.resample_onsets(onsets, target_n=12, rng=0)
    assert drawn.shape == (12,) and set(drawn) <= set(onsets)


# ---------------------------------------------------------------------------- landmark-viz


@case("jnwb-landmark-viz", "supported")
def _():
    canvas, notes = _spectrolaminar(crossover_depth=0.5)
    assert len(canvas.fig.data) == 2 and notes == ["<b>Crossover (0.5)</b>"]


@case("jnwb-landmark-viz", "request")
def _(tmp_path):
    _jviz, canvas = _canvas()
    argument = {
        "QUESTION": "q", "DATA": "d", "ESTIMAND": "e", "INFERENCE UNIT": "i", "RESULT": "r",
        "LICENSED CLAIM": "l", "SOURCE ARTIFACTS": ["a.h5"],
    }
    with pytest.raises(ValueError, match="'BARRED CLAIM' must be a non-empty string"):
        canvas.save_and_seal(tmp_path, "fig", argument)
    assert list(tmp_path.iterdir()) == []


@case("jnwb-landmark-viz", "decline")
def _():
    assert_states("jnwb-landmark-viz", "No depth is drawn unless the caller passes one")
    canvas, notes = _spectrolaminar()
    assert len(canvas.fig.data) == 1 and notes == []


# ------------------------------------------------------------------------------------ tests


def test_every_skill_outcome_is_tested_or_excused():
    on_disk = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}
    named = {s for s, _ in CASES} | {s for s, _ in NOT_REQUIRED}
    assert named == on_disk, f"skills without a row here: {sorted(on_disk - named)}; " \
                             f"rows naming no skill: {sorted(named - on_disk)}"
    for skill in sorted(on_disk):
        for outcome in OUTCOMES:
            key = (skill, outcome)
            assert (key in CASES) != (key in NOT_REQUIRED), (
                f"{skill}/{outcome} must be tested or excused, and not both"
            )
    assert all(len(reason) > 20 for reason in NOT_REQUIRED.values())


@pytest.mark.parametrize("key", sorted(CASES), ids=lambda k: f"{k[0]}-{k[1]}")
def test_outcome(key, request):
    fn = CASES[key]
    if fn.__code__.co_argcount:
        fn(request.getfixturevalue("tmp_path"))
    else:
        fn()


def _psi_with_no_slope():
    x, y = _directed_pair()
    res = jnwb.phase_slope_index(x, y, fs=1000.0, bands=(19.5, 20.5))
    # A band that has a slope still counts when another band has none.
    mixed = jnwb.phase_slope_index(x, y, fs=1000.0, bands={"a": (19.5, 20.5), "beta": (13.0, 30.0)})
    assert np.isfinite(mixed.net) and mixed.net == mixed.per_band["beta"]["value"]
    values = {"net": res.net, "x_to_y": res.x_to_y, "y_to_x": res.y_to_x}
    return values, {"ok_for_interpretation": res.diagnostics["ok_for_interpretation"]}


def _pli_with_no_spikes():
    rng = np.random.default_rng(0)
    out = jnwb.phase_locking_index(np.array([]), rng.uniform(-np.pi, np.pi, 1000), np.arange(1000) / 1000.0)
    values = {k: out[k] for k in ("pli", "peak_to_mean_contrast", "preferred_phase", "rayleigh_z", "rayleigh_pvalue")}
    return values, {"n_spikes": out["n_spikes"]}


def _compare_with_an_empty_group():
    from scipy import stats

    # One value against twenty is a defined test, and keeps its numbers.
    one, twenty = np.array([5.0]), np.arange(20.0)
    defined = jnwb.StatisticalAnalysis.exploratory_compare(one, twenty, n_bootstrap=50)["parametric"]
    t = stats.ttest_ind(one, twenty)
    assert defined["pval"] == pytest.approx(t.pvalue)
    assert defined["effect_size"] == pytest.approx(t.statistic * np.sqrt(1 / 1 + 1 / 20))
    assert type(defined["df"]) is int and defined["df"] == 19

    res = jnwb.StatisticalAnalysis.confirmatory_compare(
        np.array([]), twenty, hypothesis="the groups differ", n_bootstrap=50
    )
    values = {
        f"{block}.{key}": res[block][key]
        for block in ("parametric", "non_parametric") for key in ("statistic", "pval")
    }
    values.update(effect_size=res["parametric"]["effect_size"], df=res["parametric"]["df"],
                  q_parametric=res["q_parametric"], q_nonparametric=res["q_nonparametric"])
    # Paired groups whose every difference is zero leave the signed-rank test no rank.
    paired = jnwb.StatisticalAnalysis.exploratory_compare(
        np.arange(5.0), np.arange(5.0), paired=True, n_bootstrap=50
    )
    values.update({f"paired.{k}": paired["non_parametric"][k] for k in ("statistic", "pval")})
    flags = {k: res[k] for k in ("n1", "significant_parametric", "significant_nonparametric",
                                 "confirmed_parametric", "confirmed_nonparametric")}
    return values, flags


def _r2_with_one_class():
    res = jnwb.shuffle_r2_ci(np.zeros(20), np.random.default_rng(0).normal(size=20), n_shuffle=50)
    values = {k: v for k, v in res.items() if k != "n_shuffle"}
    return values, {"n_shuffle": res["n_shuffle"]}


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(
    "skill, phrase, call, flags",
    [
        ("jnwb-connectivity", "When no band has a slope, `net`, `x_to_y` and `y_to_x` are NaN",
         _psi_with_no_slope, {"ok_for_interpretation": False}),
        ("jnwb-spiking",
         "`n_spikes` is 0 and `pli`, `preferred_phase`, `rayleigh_z` and `rayleigh_pvalue` are NaN",
         _pli_with_no_spikes, {"n_spikes": 0}),
        ("jnwb-statistics",
         "the test it cannot support reads `statistic` and `pval` NaN, and its `significant_*` "
         "flag is False",
         _compare_with_an_empty_group,
         {"n1": 0, "significant_parametric": False, "significant_nonparametric": False,
          "confirmed_parametric": False, "confirmed_nonparametric": False}),
        ("jnwb-statistics", "A single-class label or a constant score has no $R^2$",
         _r2_with_one_class, {"n_shuffle": 50}),
    ],
    ids=["psi-net", "pli-no-spikes", "compare-empty-group", "r2-one-class"],
)
def test_a_row_states_the_undefined_case(skill, phrase, call, flags):
    """A case with no estimate returns NaN in every value field, with its flag; the row says so."""
    assert_states(skill, phrase)
    values, observed_flags = call()
    finite = {k: v for k, v in values.items() if not np.isnan(v)}
    assert not finite, f"no estimate exists, yet {finite} is reported; the {skill} row states NaN"
    assert observed_flags == flags
