import pytest
from pathlib import Path

import jnwb as oa

NWB_PATH = "D:/analysis/nwb/short-nwb/sub-C31o_ses-230630_rec.nwb"


def _skip_if_missing():
    if not Path(NWB_PATH).exists():
        pytest.skip("Real test-session NWB file is missing.")


def test_session_specific_matches_rec_suffixed_stem_to_precompute_filenames():
    # Regression test: session.nwb_path.stem for a "..._rec.nwb" file is
    # "sub-C31o_ses-230630_rec", but scripts/precompute_tfr_arrays.py strips
    # the trailing "_rec" when naming its .npy outputs (session_prefix_from_nwb).
    # session_specific=True previously compared the untrimmed stem against
    # trimmed filenames and never matched, always raising
    # "No preprocessed TFR files found for area V1 in ...".
    _skip_if_missing()
    sess = oa.read(NWB_PATH)

    res = sess.lfp_tfr_trace_suite_omission(area="V1", layer="deep", session_specific=True)

    assert res["status"] == "completed"
    assert len(res["figure"].axes) > 0


def test_session_specific_false_still_works_as_before():
    _skip_if_missing()
    sess = oa.read(NWB_PATH)

    res = sess.lfp_tfr_trace_suite_omission(area="V1", layer="deep", session_specific=False)

    assert res["status"] == "completed"
