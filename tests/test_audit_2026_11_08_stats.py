"""Statistics and decoding claims and refusals, each failing before its repair.

- fdr_correct docstring: the count of class-to-module forwarding pairs.
- jrsa comment: the rsa.py line it cites holds the sentence it quotes.
- nested_cv_linear_svm: fewer than two outer splits is refused by name before any fold is built.
"""

import re
from pathlib import Path

import numpy as np
import pytest

import jnwb
from jnwb.decoding import nested_cv_linear_svm
from jnwb.statistics import _analysis

PKG = Path(jnwb.__file__).resolve().parent


def _trials():
    rng = np.random.default_rng(0)
    return rng.normal(size=(20, 3)), np.repeat([0, 1], 10)


def test_fdr_docstring_counts_the_forwarding_pairs():
    pairs = sorted(
        name for name in vars(_analysis.StatisticalAnalysis)
        if not name.startswith("_") and callable(vars(_analysis).get(name))
    )
    assert pairs == ["clopper_pearson", "exact_sign_flip", "fdr_correct", "mann_whitney_p_floor"]
    assert "The other three module/class pairs" in " ".join(_analysis.fdr_correct.__doc__.split())


def test_jrsa_comment_cites_the_rsa_line_that_holds_the_sentence():
    lines = (PKG / "jrsa" / "__init__.py").read_text(encoding="utf-8").splitlines()
    rsa_lines = (PKG / "rsa.py").read_text(encoding="utf-8").splitlines()
    cites = []
    for i, line in enumerate(lines):
        match = re.search(r"rsa\.py:(\d+)", line)
        if match and "valid test of RDM" in " ".join(lines[i:i + 3]):
            cites.append(int(match.group(1)))
    assert cites, "no rsa.py pointer sits beside the RDM sentence; the check examined nothing"
    for n in cites:
        assert "valid test of RDM relatedness" in rsa_lines[n - 1], f"rsa.py:{n} does not hold the sentence"


@pytest.mark.parametrize("n_splits", [0, 1])
def test_nested_cv_refuses_fewer_than_two_splits_by_name(n_splits):
    X, labels = _trials()
    with pytest.raises(ValueError, match="nested_cv_linear_svm"):
        nested_cv_linear_svm(X, labels, n_splits=n_splits)


def test_nested_cv_two_splits_still_runs():
    X, labels = _trials()
    assert nested_cv_linear_svm(X, labels, n_splits=2)["status"] == "success"


def test_alpha_fdr_warns_on_access():
    from jnwb.statistics._analysis import StatisticalAnalysis

    with pytest.warns(DeprecationWarning, match="ALPHA_FDR"):
        assert StatisticalAnalysis.ALPHA_FDR == StatisticalAnalysis.ALPHA
