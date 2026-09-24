"""Pages that print a number say what it does not license -- and say it truthfully.

Five pages produced an estimate and stopped: an apparent phase velocity framed as
propagation latency, a cluster p with nothing about what a cluster licenses, a CSD map with
no sign convention, transfer entropy and mutual information with no log base, and a decoder
described as leakage-resistant above a call that holds out no groups.

A test that only greps for the sentence would keep passing when the sentence goes stale, so
each one is checked against the implementation it describes: the unit comes off the result,
the sign convention off the docstring, the absence of `groups` off the signature, and the
cross-modal numbers off a re-run of the documented call.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import numpy as np
import pytest

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"


def _page(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def test_zflip_apparent_velocity_is_not_offered_as_a_conduction_velocity():
    page = _page("02_paths_addressing_metadata.md")
    assert "an *apparent* phase velocity, not a conduction velocity" in page
    assert "volume conduction" in page, "the alternative generators are not named"
    assert "propagation latency" not in page, (
        "the page still frames the delay gradient as propagation latency"
    )


def test_the_cluster_test_page_says_a_cluster_does_not_license_its_own_extent():
    page = _page("07_statistical_inference_and_nulls.md")
    assert "differ *somewhere*" in page
    for word in ("onset", "offset", "peak"):
        assert word in page, f"the extent caveat does not mention the cluster's {word}"


def test_the_csd_sign_convention_on_the_page_matches_the_implementation():
    doc = inspect.getdoc(jnwb.current_source_density_1d)
    assert "Negative values indicate a CURRENT SINK" in doc, (
        "the implementation's sign convention changed; the page below now contradicts it"
    )
    page = _page("04_spectral_analysis_and_tfr.md")
    assert re.search(r"\*negative\* is a current \*\*sink\*\*", page), (
        "docs/04 does not state the CSD sign convention, which is the interpretation"
    )
    assert "A}/\\text{m}^3" in page or "A/m^3" in page


def test_transfer_entropy_is_documented_in_the_unit_it_returns():
    x = np.random.default_rng(0).normal(size=400)
    y = np.random.default_rng(1).normal(size=400)
    res = jnwb.transfer_entropy(x, y, k=1, l=1, delay=1, estimator="quantile", bins=4,
                                n_surrogates=5, rng=0)
    assert res.unit == "bits", f"transfer_entropy now returns {res.unit!r}"
    # Per section, not per page: the mutation that deleted the TE unit survived a page-level
    # check, because the mutual-information paragraph below also says bits.
    page = _page("08_directed_connectivity_and_information.md")
    te_section, _, mi_section = page.partition("## 5. Spike Mutual Information")
    te_section = te_section.split("## 4. Transfer Entropy", 1)[1]
    assert "**bits**" in te_section and "unit='bits'" in te_section, (
        "the transfer entropy section does not state the unit the result carries"
    )
    assert "**bits**" in mi_section, "the mutual information section does not state its unit"
    assert "nats" in te_section, "the page does not distinguish the base it is not using"


def test_the_transfer_entropy_formula_gives_k_to_the_target_and_l_to_the_source():
    """The page wrote `k` on the source past and `l` on the target past; the code does the
    reverse, so a reader who set `k` and `l` from the page ran a different model."""
    doc = inspect.getdoc(jnwb.transfer_entropy)
    assert "k: target history length" in doc and "l: source history length" in doc, (
        "the implementation's history convention changed; the check below now tests nothing"
    )
    page = _page("08_directed_connectivity_and_information.md")
    formula = next(line for line in page.splitlines() if line.startswith("$$T_{X \\to Y}"))
    assert re.findall(r"Y_\{t-1:t-(\w)\}", formula) == ["k", "k"], formula
    assert re.findall(r"X_\{t-u:t-u-(\w)[^}]*\}", formula) == ["l"], formula


def test_the_decoder_page_does_not_promise_group_holdout_from_a_call_that_has_none():
    params = inspect.signature(jnwb.nested_cv_linear_svm).parameters
    assert "groups" not in params, (
        "nested_cv_linear_svm now takes groups; the caveat on docs/09 is stale and should "
        "become an example that passes them"
    )
    page = _page("09_decoding_and_visual_qc.md")
    assert "does not hold out groups" in page
    assert "assign_outer_folds" in page, "the page does not say where the protection is"


def test_the_cross_modal_example_reports_the_numbers_it_actually_produces():
    """The block was `(4, 200)` and called it `channels x time`.

    The reduction reads a 2-D array as `(n_times, n_trials)`, so it correlated four points
    and swept three lags while the page presented it as a 200-sample series. Both the shape
    and the printed numbers are re-derived here from the documented call.
    """
    page = _page("07_statistical_inference_and_nulls.md")
    assert "size=(200, 4)" in page, "the example is not time-major"
    assert "size=(4, 200)" not in page, "the transposed arrays are still on the page"

    tfr = np.random.default_rng(1).normal(size=(200, 4))
    spike = np.random.default_rng(2).normal(size=(200, 4))
    res = jnwb.cross_modal_comparison(tfr, spike, lag_range_ms=(-100, 100), bin_ms=10.0,
                                      rng=0)
    assert res["n_samples"] == 200 and res["n_lags_searched"] == 21
    assert f'# {res["lag_ms"]}, {res["lag_corrected_pvalue"]:.3f}' in page, (
        f"the page's comment does not match the produced "
        f"{res['lag_ms']}, {res['lag_corrected_pvalue']:.3f}"
    )
    assert res["lag_corrected_pvalue"] > 0.05, (
        "the corrected p is significant on independent white noise, which the page reports "
        "as the right answer"
    )


@pytest.mark.parametrize("phrase", ["lag_corrected_pvalue", "lfp_leads_spikes"])
def test_the_lag_sign_and_the_corrected_p_are_both_named(phrase):
    assert phrase in _page("07_statistical_inference_and_nulls.md")


def test_the_statistics_tutorial_declares_the_unit_of_what_it_compares():
    """The one tutorial whose rendered page carried no unit token.

    The other four include scripts that carry Hz, ms, um or seconds; this one compared two
    groups introduced as "firing rates or band power" and reported a mean difference in
    neither.
    """
    script = (REPO_ROOT / "examples" / "tutorials" / "05_statistics.py").read_text(
        encoding="utf-8")
    assert "firing rates in Hz" in script
    assert "difference in Hz" in script
    assert "licenses" in script, "the cluster p is still printed without its caveat"
