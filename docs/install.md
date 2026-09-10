# Install

## PyPI

```bash
pip install -U jnwb
```

The current library release is dataset-agnostic. The public surface is documented in [Public API](api.md) and is the contents of `jnwb.__all__`.

### Optional Acceleration Backends & Extras

`jnwb` is structured with modular extras so production workflows install only what they need:

```bash
pip install "jnwb[torch,gpu]"   # PyTorch, CuPy, and CUDA 12.x acceleration
pip install "jnwb[mcp]"         # Model Context Protocol server tooling
pip install "jnwb[docs]"        # MkDocs documentation builder
pip install "jnwb[test]"        # pytest, pytest-cov, pytest-xdist test suites
pip install "jnwb[all]"         # Complete dependency bundle
```

### GPU and parallel execution

Functions with a `device=` argument (see [Public API](api.md)) accept `'cpu'`, the default, or
`'cuda'`. `'cuda'` runs on an NVIDIA GPU through [CuPy](https://docs.cupy.dev/en/stable/),
installed by the `gpu` extra (CUDA 12.x). The device is resolved once per call: if CuPy or a
GPU is missing, or the GPU run raises, the whole call runs on CPU and a `RuntimeWarning` names
the function. Results record which device produced them: `device_used` in
`cross_area_coherence`, `.device` on the `ComplexTFR` from `complex_tfr`.

Functions with an `n_jobs=` argument run independent work items in worker processes through
[joblib](https://joblib.readthedocs.io/en/stable/). The default is 1 (serial) and -1 uses every
core. Work items are seeded before they are dispatched, so `n_jobs` changes speed and never a
result. Starting workers has a cost, so raise it for calls that take seconds.

## Source Checkout

Clone and install an editable development environment:

```bash
git clone https://github.com/HNXJ/jnwb.git
cd jnwb
pip install -e ".[all]"
```

### Do not clone other projects inside this checkout

An editable install writes a `.pth` file containing the **repository root**, not just
`jnwb/`. Every top-level package sitting beside `jnwb/` therefore becomes importable
from any working directory, ahead of a package of the same name elsewhere on your path.

A project cloned inside the jnwb checkout will shadow itself. The failure is silent:
`import yourproject` returns a well-formed module, from the wrong copy, and no error is
raised. `.gitignore` hides the directory from `git status`, which removes the last
signal you would get. This has happened in practice — two copies of one project
disagreed on a label, and most importing files took the stale one.

Keep your analysis project in its own directory, beside the jnwb checkout rather than
inside it. jnwb's own harness enforces the equivalent invariant on this repository
(`scripts/harness_gate.py`, Gate 11), and the published wheel ships only `jnwb/`.

For a stricter editable install that maps `jnwb` alone instead of the whole root:

```bash
pip install -e . --config-settings editable_mode=strict
```

## Verify

Run the verification snippet in your Python environment:

```python
import jnwb

print(f"jnwb version: {jnwb.__version__}")
print(f"Public surface: {len(jnwb.__all__)} symbols")
missing = [name for name in jnwb.__all__ if not hasattr(jnwb, name)]
assert not missing, f"Unresolved public exports: {missing}"
print("Verification passed successfully.")
```
