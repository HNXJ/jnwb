"""
Unit tests for jnwb.complex_tfr module.
Falsifier conditions:
- test_complex_tfr_round_trip passes
- plv_from_complex(z, z) == 1.0
- plv_from_complex(z, -z) < 0.1
"""

import numpy as np
import pytest
import tempfile
import pathlib

from jnwb._unused.complex_tfr import tfr_complex_load, plv_from_complex, imaginary_coherence


def test_complex_tfr_round_trip():
    rng = np.random.default_rng(42)
    re = rng.normal(size=(10, 20, 50))
    im = rng.normal(size=(10, 20, 50))
    z_expected = re + 1j * im

    with tempfile.TemporaryDirectory() as tmpdir:
        re_path = pathlib.Path(tmpdir) / "test.real.npy"
        im_path = pathlib.Path(tmpdir) / "test.imag.npy"
        np.save(re_path, re)
        np.save(im_path, im)

        z_loaded = tfr_complex_load(str(re_path), str(im_path))
        assert z_loaded.dtype == np.complex128
        assert np.allclose(z_loaded, z_expected)


def test_plv_identical_signals():
    rng = np.random.default_rng(42)
    z = rng.normal(size=(5, 100)) + 1j * rng.normal(size=(5, 100))
    plv_same = plv_from_complex(z, z, axis=-1)
    assert pytest.approx(plv_same, abs=1e-5) == 1.0


def test_plv_opposite_signals():
    rng = np.random.default_rng(42)
    # Random phases with zero coherence
    z1 = np.exp(1j * rng.uniform(0, 2 * np.pi, size=(10, 1000)))
    z2 = np.exp(1j * rng.uniform(0, 2 * np.pi, size=(10, 1000)))
    plv_uncorr = plv_from_complex(z1, z2, axis=-1)
    assert plv_uncorr < 0.1


def test_imaginary_coherence_shape():
    rng = np.random.default_rng(42)
    z1 = rng.normal(size=(10, 20, 100)) + 1j * rng.normal(size=(10, 20, 100))
    z2 = rng.normal(size=(10, 20, 100)) + 1j * rng.normal(size=(10, 20, 100))
    icoh = imaginary_coherence(z1, z2, axis=-1)
    assert icoh.shape == (10, 20)
