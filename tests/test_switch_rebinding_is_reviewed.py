"""The two shapes the computational contract gate cannot see are each a reviewed inventory.

`scripts/computational_contract_gate.py` tracks a switch argument flow-insensitively: an argument
rebound inside a branch still counts as reaching its mechanism, and under ``by_request`` one
``dtype=`` sink on one path passes while another path could ignore the request. Each live
instance of either shape is listed here with the reason it is correct; a new one fails until it
is read and added.
"""
from __future__ import annotations

import ast
from pathlib import Path

import jnwb
from jnwb._precision import BY_REQUEST, PRECISION_POLICY

PACKAGE = Path(jnwb.__file__).resolve().parent
SWITCH_PARAMETERS = {"device", "backend", "n_jobs", "dtype"}

#: (file, function, parameter) -> why the rebinding inside a branch is correct.
REVIEWED_BRANCH_REBINDINGS = {
    ("spectral/_coupling.py", "imaginary_coherency", "device"):
        "Rebinds the resolve_device answer to 'cpu' after warn_device_fallback, when the GPU "
        "run raised; the CPU branch below then computes.",
    ("spectral/_coupling.py", "wpli", "device"):
        "The same announced fallback as imaginary_coherency.",
    ("spectral/_psd.py", "harmonic_analysis", "device"):
        "The same announced fallback, inside the except that calls warn_device_fallback.",
}

#: Export -> the paths that each honour the requested dtype.
REVIEWED_BY_REQUEST = {
    "jnwb.tfr.complex_tfr":
        "Every device path writes the requested dtype: _convolve_gpu and _convolve_jax allocate "
        "and cast to it, and the CPU path allocates z_out with it and casts each convolution.",
}


def _branch_rebindings(tree: ast.AST) -> set[tuple[str, str]]:
    """(function, parameter) for each switch parameter rebound inside a branch, loop, with or try."""
    found = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = {a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs}
        mine = params & SWITCH_PARAMETERS
        for stmt in fn.body:
            if not isinstance(stmt, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                continue
            for node in ast.walk(stmt):
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    found |= {(fn.name, t.id) for t in targets
                              if isinstance(t, ast.Name) and t.id in mine}
    return found


def test_every_switch_argument_rebound_in_a_branch_is_reviewed():
    files = sorted(PACKAGE.rglob("*.py"))
    assert len(files) > 20, "the scan must read the package"
    found = {(p.relative_to(PACKAGE).as_posix(), fn, param)
             for p in files
             for fn, param in _branch_rebindings(ast.parse(p.read_text(encoding="utf-8")))}
    assert found == set(REVIEWED_BRANCH_REBINDINGS), (
        "new: " + repr(sorted(found - set(REVIEWED_BRANCH_REBINDINGS)))
        + "; gone: " + repr(sorted(set(REVIEWED_BRANCH_REBINDINGS) - found)))


def test_every_by_request_export_is_reviewed_path_by_path():
    stated = {name for name, policy in PRECISION_POLICY.items() if policy == BY_REQUEST}
    assert stated, "the policy must state at least one by_request export"
    assert stated == set(REVIEWED_BY_REQUEST), stated


def test_the_scan_finds_a_rebinding_the_gate_passes_and_skips_a_top_level_one():
    src = ("def f(x, device='cpu'):\n    if x:\n        device = 'cpu'\n"
           "    return resolve_device(device)\n\n"
           "def g(x, device='cpu'):\n    device = str(device)\n    return resolve_device(device)\n")
    assert _branch_rebindings(ast.parse(src)) == {("f", "device")}
