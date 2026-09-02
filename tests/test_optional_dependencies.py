"""Test clean import and feature-use isolation for optional dependencies."""
import importlib
import pytest
import unittest
from unittest.mock import patch

import jnwb
import jnwb.bilinear
import jnwb.nam


class TestOptionalDependencies(unittest.TestCase):
    def test_bilinear_importable_and_runs_without_torch(self):
        """Verify BilinearLogisticRegression works with core numpy + sklearn."""
        import numpy as np
        model = jnwb.bilinear.BilinearLogisticRegression(rank=2, n_iter=5)
        X = np.random.randn(20, 5, 10)
        y = np.random.choice([0, 1], size=20)
        model.fit(X, y)
        preds = model.predict(X)
        self.assertEqual(len(preds), 20)

    def test_nam_feature_use_error_when_torch_unavailable(self):
        """Verify nam functions raise informative error when torch is missing."""
        with patch("jnwb.nam._TORCH_AVAILABLE", False):
            with pytest.raises(ImportError, match="jnwb.nam requires PyTorch"):
                jnwb.nam.LaminarNAM(num_units=8, time_samples=50)

            with pytest.raises(ImportError, match="jnwb.nam requires PyTorch"):
                jnwb.nam.unit_importance(None, None)

            with pytest.raises(ImportError, match="jnwb.nam requires PyTorch"):
                jnwb.nam.predict(None, None)

            with pytest.raises(ImportError, match="jnwb.nam requires PyTorch"):
                jnwb.nam.train_nam(None, None, None, None, None)
