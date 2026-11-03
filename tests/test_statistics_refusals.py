"""Trial-count arguments that the statistics helpers refuse instead of silently accepting.

Each bad value must raise a ValueError naming the argument and the value. The control drives a
valid value and pins its output: a refusal that fires on every input fails the control.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest

from jnwb.statistics import assign_subblock_quartiles

START_TIMES = [0.5, 0.1, 0.9, 0.3, 0.7]


def _df():
    return pd.DataFrame({"start_time": START_TIMES})


class TestAssignSubblockQuartilesRefusesBadCount:
    @pytest.mark.parametrize("n_quantiles", [0, -1])
    def test_fewer_than_one_bucket_is_refused(self, n_quantiles):
        with pytest.raises(ValueError, match=rf"n_quantiles must be an integer >= 1; got {n_quantiles}$"):
            assign_subblock_quartiles(_df(), n_quantiles=n_quantiles)

    @pytest.mark.parametrize("n_quantiles", [4.0, 4.5, True])
    def test_non_integer_is_refused(self, n_quantiles):
        with pytest.raises(ValueError, match=re.escape(f"n_quantiles must be an integer >= 1; got {n_quantiles!r}")):
            assign_subblock_quartiles(_df(), n_quantiles=n_quantiles)

    def test_valid_count_returns_pinned_buckets(self):
        # Temporal order is rows 1, 3, 0, 4, 2; with edges 0, 1, 2, 3, 5 the buckets are
        # row 1 -> 0, row 3 -> 1, row 0 -> 2, rows 4 and 2 -> 3.
        q = assign_subblock_quartiles(_df(), n_quantiles=4)
        assert set(q.tolist()) == {0, 1, 2, 3}, "fixture must fill all four buckets"
        np.testing.assert_array_equal(q, [2, 0, 3, 1, 3])
