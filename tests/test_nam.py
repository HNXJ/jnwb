"""`jnwb.nam.train_nam` seeds its own draws and leaves torch's global random state alone."""
from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from jnwb.nam import LaminarNAM, train_nam  # noqa: E402


def _data(seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(60, 3, 8)).astype(np.float32)
    y = rng.integers(0, 3, 60)
    return X[:40], y[:40], X[40:], y[40:]


def _train(seed):
    torch.manual_seed(123)  # the model's initial weights, fixed by the test
    model = LaminarNAM(3, 8, n_classes=3)
    out = train_nam(model, *_data(), max_epochs=5, patience=5, seed=seed)
    return out, [p.detach().clone() for p in model.parameters()]


def test_training_leaves_the_global_random_state_as_it_found_it():
    torch.manual_seed(7)
    before = torch.get_rng_state()
    model = LaminarNAM(3, 8, n_classes=3)
    after_init = torch.get_rng_state()
    assert not torch.equal(before, after_init)  # the probe sees global draws at all
    train_nam(model, *_data(), max_epochs=3, patience=3, seed=0)
    assert torch.equal(torch.get_rng_state(), after_init)


def test_the_seed_still_reproduces_training_and_a_different_seed_changes_it():
    (a, wa), (b, wb), (c, wc) = _train(0), _train(0), _train(1)
    assert a == b and all(torch.equal(x, y) for x, y in zip(wa, wb))
    assert not all(torch.equal(x, y) for x, y in zip(wa, wc))
