import numpy as np
import pytest
import h5py
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from precompute_tfr_arrays import _to_numeric, p1_onsets_s


def test_to_numeric_handles_bytes_encoded_columns():
    # Regression test for a real bug found 2026-07-12: some sessions (e.g.
    # sub-C31o_ses-230816/230901) store stimulus_number/correct/
    # task_condition_number as bytes-encoded strings (b'2.0', b'nan') rather
    # than a native numeric dtype - np.isfinite() on the raw bytes array
    # raised TypeError, which silently caused the Jun 19 precompute for
    # these 2 sessions to produce a stale/wrong trial count (370 vs the
    # real 246 for sub-C31o_ses-230816's AAAB condition) rather than
    # failing loudly.
    bytes_arr = np.array([b"1.0", b"2.0", b"nan", b"3.5"], dtype=object)
    result = _to_numeric(bytes_arr)
    assert result.dtype == np.float64
    assert list(result[:2]) == [1.0, 2.0]
    assert np.isnan(result[2])
    assert result[3] == 3.5


def test_to_numeric_passthrough_for_already_numeric_columns():
    arr = np.array([1.0, 2.0, np.nan, 3.5])
    result = _to_numeric(arr)
    assert result.dtype == np.float64
    np.testing.assert_array_equal(result, arr)


def test_p1_onsets_s_matches_real_trial_count_on_bytes_encoded_session():
    # Real regression test against the actual affected session.
    nwb_path = "D:/analysis/nwb/sub-C31o_ses-230816_rec.nwb"
    if not Path(nwb_path).exists():
        pytest.skip("Real test-session NWB file is missing.")

    with h5py.File(nwb_path, "r") as f:
        onsets = p1_onsets_s(f, "AAAB")

    assert len(onsets) == 246
