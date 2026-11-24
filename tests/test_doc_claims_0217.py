"""Public-doc claims pinned to the code they describe (0.2.17 documentation findings).

Each test checks one sentence a reader would act on. The doc side is read from the file, so an
edit that drifts from the code fails here.

* ``fuse_laminar_anchors`` agreement vocabulary (docs/10_operation_specifications.md): the set of
  quoted values in the op-spec row equals the set the function can return.
* ``imaginary_coherency`` sign: positive for a lead below pi, negative beyond it.
* hardware-channel-first lookup (docs/common_mistakes.md): a table with ``hardware_channel``
  resolves a peak by that column, not by the identifier column.
* ``repair_lfp_trials`` has no condition argument (docs/05_artifact_detection_and_repair.md).
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import jnwb
from jnwb.addressing import map_peak_channel_to_area
from jnwb.artifact_repair import repair_lfp_trials
from jnwb.laminar_curation import VFLIP2_VFLIP_AGREEMENT_T_CONTACTS as T

ROOT = Path(__file__).resolve().parents[1]
OPSPEC = ROOT / "docs" / "10_operation_specifications.md"
REPAIR_DOC = ROOT / "docs" / "05_artifact_detection_and_repair.md"

WIN = np.array([600.0, 610.0, 590.0, 605.0])
A_KW = dict(window_um=WIN, consistency_deep=0.9, consistency_superficial=0.8)


def _doc_row(path: Path, start: str) -> str:
    rows = [line for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith(start)]
    assert len(rows) == 1, f"expected one doc row starting {start!r}, found {len(rows)}"
    return rows[0]


def test_fuse_agreement_vocabulary_in_the_op_spec_is_the_code_vocabulary():
    # Reachable values, from inputs that exercise each branch of the agreement rule.
    reachable = {
        jnwb.fuse_laminar_anchors(vflip2_um=0.0, vflip_um=0.0, contact_spacing_um=1.0,
                                  **A_KW)["agreement"],
        jnwb.fuse_laminar_anchors(vflip2_um=T + 1.0, vflip_um=0.0, contact_spacing_um=1.0,
                                  **A_KW)["agreement"],
        jnwb.fuse_laminar_anchors(vflip2_um=0.0, vflip_um=0.0, **A_KW)["agreement"],
        jnwb.fuse_laminar_anchors(vflip2_um=0.0, **A_KW)["agreement"],
    }
    assert reachable == {"agree", "disagree", "unresolved"}
    row = _doc_row(OPSPEC, "| `fuse_laminar_anchors`")
    quoted = set(re.findall(r"'(agree|disagree|unresolved|unavailable)'", row))
    assert quoted == reachable, f"op-spec row quotes {sorted(quoted)}, code returns {sorted(reachable)}"


def test_imaginary_coherency_sign_holds_below_pi_and_reverses_beyond_it():
    rng = np.random.default_rng(3)
    fs = 500.0
    x = rng.standard_normal(40_000)
    spectrum = np.fft.rfft(x)

    def lagged(phase):
        # y lags x by ``phase`` at every frequency, so x leads y; the fixture is a pure lag.
        return np.fft.irfft(spectrum * np.exp(-1j * phase), n=x.size)

    below = jnwb.imaginary_coherency(x, lagged(0.5), fs=fs, freq_range=(5.0, 80.0),
                                     signal_class="lfp")
    beyond = jnwb.imaginary_coherency(x, lagged(4.0), fs=fs, freq_range=(5.0, 80.0),
                                      signal_class="lfp")
    assert below["icoh_mean"] > 0, below
    assert beyond["icoh_mean"] < 0, beyond
    for path in ("docs/architecture.md", "docs/coherence_and_tfr.md"):
        text = (ROOT / path).read_text(encoding="utf-8")
        assert re.search(r"below\s+pi", text), f"{path} states the sign without the pi condition"


def _electrodes(hardware, areas, group_name=None):
    df = pd.DataFrame({"channel_id": [0, 1, 2], "hardware_channel": hardware,
                       "location": areas})
    if group_name is not None:
        df["group_name"] = group_name
    return df


def test_a_peak_is_resolved_by_hardware_channel_not_by_identifier():
    df = _electrodes(hardware=[10, 11, 12], areas=["V1", "V2", "V4"])
    # Peak 10 names the hardware channel of row 0, whatever its channel_id.
    assert map_peak_channel_to_area(10, df) == "V1"
    # Peak 1 is the channel_id of row 1, but the table searches hardware_channel only.
    assert map_peak_channel_to_area(1, df) is None


def test_hardware_channel_minus_one_is_no_channel():
    df = _electrodes(hardware=[-1, 11, 12], areas=["V1", "V2", "V4"])
    assert map_peak_channel_to_area(-1, df) is None


def test_a_hardware_channel_on_two_probes_resolves_to_none():
    df = _electrodes(hardware=[10, 10, 12], areas=["V1", "V2", "V4"],
                     group_name=["probeA", "probeB", "probeA"])
    with pytest.warns(UserWarning, match="2 probes"):
        assert map_peak_channel_to_area(10, df) is None


def test_repair_takes_no_condition_and_the_doc_says_so():
    params = inspect.signature(repair_lfp_trials).parameters
    assert not [name for name in params if "condition" in name.lower()]
    text = REPAIR_DOC.read_text(encoding="utf-8")
    assert "There is no condition matching" in text
    assert "condition-matched" not in text
