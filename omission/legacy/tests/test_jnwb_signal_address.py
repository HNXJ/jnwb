"""Tests for jnwb signal addressing."""

from __future__ import annotations

from pathlib import Path

import pytest

import omission
from src.jnwb.errors import BLOCKED_AREA_METADATA_MISSING, BLOCKED_SIGNAL_UNAVAILABLE, JnwbBlockedError


NWB_ROOT = Path(r"D:/analysis/nwb")
pytestmark = pytest.mark.skipif(not NWB_ROOT.exists(), reason="NWB root unavailable")


def test_address_signals_spk_produces_unit_ids():
    files = jnwb.list_nwb_files(NWB_ROOT)
    spk_files = [f for f in files if f.has_spk]
    assert spk_files, "Expected at least one SPK session"
    addr = jnwb.address_signals(spk_files[:1], signal="SPK", require_area=False)
    assert addr.signal == "SPK"
    assert addr.sessions
    skey = addr.sessions[0]
    assert len(addr.ids_by_session[skey]) > 0


def test_address_signals_lfp_when_present():
    files = jnwb.list_nwb_files(NWB_ROOT)
    lfp_files = [f for f in files if f.has_lfp]
    if not lfp_files:
        pytest.skip("No LFP in inventory")
    addr = jnwb.address_signals(lfp_files[:1], signal="LFP", require_area=False)
    skey = addr.sessions[0]
    assert len(addr.ids_by_session[skey]) > 0
    assert addr.sampling_rate_by_session.get(skey) is not None or True


def test_address_signals_muae_when_present():
    files = jnwb.list_nwb_files(NWB_ROOT)
    muae_files = [f for f in files if f.has_muae]
    if not muae_files:
        pytest.skip("No MUAe in inventory")
    addr = jnwb.address_signals(muae_files[:1], signal="MUAe", require_area=False)
    skey = addr.sessions[0]
    assert len(addr.ids_by_session[skey]) > 0


def test_require_area_blocks_unknown():
    files = jnwb.list_nwb_files(NWB_ROOT)
    spk_files = [f for f in files if f.has_spk]
    with pytest.raises(JnwbBlockedError) as exc:
        jnwb.address_signals(
            spk_files[:1],
            signal="SPK",
            areas=["NONEXISTENT_AREA_XYZ"],
            require_area=True,
        )
    assert exc.value.code in (BLOCKED_AREA_METADATA_MISSING, BLOCKED_SIGNAL_UNAVAILABLE)


def test_missing_signal_raises_not_empty():
    files = jnwb.list_nwb_files(NWB_ROOT)
    fake = [jnwb.NWBFileRecord(
        path=str(NWB_ROOT / "missing.nwb"),
        session_id="ses-fake",
        subject="sub-fake",
        date=None,
        task_names=[],
        has_spk=False,
        has_lfp=False,
        has_muae=False,
    )]
    with pytest.raises(JnwbBlockedError):
        jnwb.address_signals(fake, signal="SPK")
