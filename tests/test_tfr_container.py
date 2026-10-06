"""The `ComplexTFR` container checks the device it records."""

import numpy as np
import pytest

import jnwb


def _fields(**overrides):
    tfr = jnwb.complex_tfr(np.random.default_rng(0).standard_normal(256), fs=1000.0,
                           freqs=np.array([20.0, 40.0]))
    fields = dict(z=tfr.z, freqs=tfr.freqs, times=tfr.times, coi_mask=tfr.coi_mask, fs=tfr.fs,
                  n_cycles=tfr.n_cycles, normalization=tfr.normalization, device=tfr.device)
    fields.update(overrides)
    return fields


@pytest.mark.parametrize("device", ["cpu", "cuda", "metal"])
def test_a_known_device_is_accepted(device):
    assert jnwb.ComplexTFR(**_fields(device=device)).device == device


@pytest.mark.parametrize("device", ["gpu", "CUDA", "", None, 0])
def test_any_other_device_is_refused(device):
    """Any string was accepted, so a hand-built container could carry a false record (P-257)."""
    with pytest.raises(ValueError, match="ComplexTFR.device must be one of"):
        jnwb.ComplexTFR(**_fields(device=device))


def test_complex_tfr_records_a_device_the_check_accepts():
    assert jnwb.ComplexTFR(**_fields()).device == "cpu"
