"""The computational contract gate fails on each seeded violation and reads the live tree.

Each check is exercised on a fixture module written to a temporary directory, never by
editing ``jnwb/``. Every fixture carries a control that satisfies the rule beside the
violation that breaks it, so a check that failed everything would fail its own test.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]
# `scripts` exists only in a checkout; appended, never inserted, so the package under test
# stays whichever installation the session selected.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts import computational_contract_gate as gate  # noqa: E402

FIXTURE = '''
import dataclasses
import warnings

import numpy as np

from jnwb._backend import CPU, CUDA, resolve_device
from jnwb._parallel import parallel_map


def ignores_device(x, device="cpu"):
    return x


def discards_the_answer(x, device="cpu"):
    resolve_device(device, context="discards_the_answer")
    return x


def ignores_n_jobs(x, n_jobs=1):
    return [v for v in x]


def validates_backend_only(x, backend="numpy"):
    if backend not in ("numpy", "cupy"):
        raise ValueError(backend)
    return x


def branches_on_the_answer(x, device="cpu"):
    if resolve_device(device, context="branches_on_the_answer") == CUDA:
        return x
    return x


def declares_cpu_only(x, device="cpu"):
    resolve_device(device, context="declares_cpu_only", supports=(CPU,))
    return x


def _helper(x, device):
    resolved = resolve_device(device, context="through_a_helper")
    return x if resolved == CPU else x


def through_a_helper(x, device="cpu"):
    return _helper(x, device=device)


def maps_in_parallel(x, n_jobs=1):
    return parallel_map(abs, x, n_jobs=n_jobs)


def refuses_and_announces_backend(x, backend="numpy"):
    chosen = str(backend).lower()
    if chosen not in ("numpy", "cupy"):
        raise ValueError(backend)
    if chosen == "cupy":
        warnings.warn("computing in numpy", RuntimeWarning)
    return x


@dataclasses.dataclass(frozen=True)
class Record:
    device: str


def dtype_unregistered(x, dtype=np.float64):
    return np.asarray(x, dtype=dtype)


def dtype_policy_ignores_requests(x, dtype=np.float64):
    return np.asarray(x, dtype=dtype)


def dtype_stated_but_ignored(x, dtype=np.float64):
    return np.asarray(x, dtype=np.float64)


def dtype_refusal_stated_but_absent(x, dtype=None):
    return np.asarray(x, dtype=np.float64)


def dtype_honoured(x, dtype=np.float64):
    return np.asarray(x).astype(dtype)


def dtype_refused(x, dtype=None):
    if dtype is not None and np.dtype(dtype) != np.float64:
        raise ValueError("64-bit only")
    return np.asarray(x, dtype=np.float64)
'''


@pytest.fixture
def fixture_module(tmp_path, monkeypatch):
    name = "contract_gate_fixture"
    path = tmp_path / f"{name}.py"
    path.write_text(textwrap.dedent(FIXTURE), encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _callables(module, names):
    return [(n, getattr(module, n)) for n in names]


def _flagged(violations):
    return {v.split(":")[0] for v in violations}


def test_the_execution_check_fails_on_an_argument_that_selects_nothing(fixture_module):
    seeded = ["ignores_device", "discards_the_answer", "ignores_n_jobs", "validates_backend_only"]
    controls = ["branches_on_the_answer", "declares_cpu_only", "through_a_helper",
                "maps_in_parallel", "refuses_and_announces_backend", "Record"]
    violations, records = gate.check_execution_switch(
        _callables(fixture_module, seeded + controls),
        scope=("jnwb", fixture_module.__name__))
    assert _flagged(violations) == set(seeded), violations
    assert records == ["Record.device"]


def test_the_precision_check_fails_on_a_request_it_ignores(fixture_module):
    mod = fixture_module.__name__
    policy = {
        f"{mod}.dtype_policy_ignores_requests": "always_double",
        f"{mod}.dtype_stated_but_ignored": "by_request",
        f"{mod}.dtype_refusal_stated_but_absent": "double_only",
        f"{mod}.dtype_honoured": "by_request",
        f"{mod}.dtype_refused": "double_only",
    }
    seeded = ["dtype_unregistered", "dtype_policy_ignores_requests", "dtype_stated_but_ignored",
              "dtype_refusal_stated_but_absent"]
    controls = ["dtype_honoured", "dtype_refused"]
    violations, found = gate.check_precision_request(
        _callables(fixture_module, seeded + controls), policy=policy,
        scope=("jnwb", mod))
    assert _flagged(violations) == set(seeded), violations
    assert len(found) == len(seeded + controls)


def test_the_order_check_fails_on_an_export_without_a_recorded_order():
    record = gate.ORDER_RECORD.read_text(encoding="utf-8")
    exports = list(jnwb.__all__)
    rows = [line for line in record.splitlines() if line.startswith("| `wpli` |")]
    assert len(rows) == 1, rows
    without_wpli = record.replace(rows[0] + "\n", "")

    baseline, _ = gate.check_recorded_order(exports, record)
    seeded, _ = gate.check_recorded_order(exports + ["unrecorded_export"], without_wpli)
    new = set(seeded) - set(baseline)
    assert _flagged(new) == {"wpli", "unrecorded_export"}, new

    stale, _ = gate.check_recorded_order([e for e in exports if e != "rdm"], record)
    assert "rdm" in _flagged(set(stale) - set(baseline))


#: Exports the order record does not yet place in any category, observed on this tree. The
#: record, not this test, is where they belong; once it places them this set must shrink,
#: and an export added without an order fails here immediately.
UNRECORDED_ON_THIS_TREE = {"SqueezedAttributeWarning", "nwb_read_io", "read_nwb", "vis"}


def test_the_live_tree():
    results = {name: violations for name, violations, _ in gate.run_checks(jnwb)}
    assert results["execution switch"] == []
    assert results["precision request"] == []
    assert _flagged(results["recorded order"]) == UNRECORDED_ON_THIS_TREE, results["recorded order"]
