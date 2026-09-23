# Install

## PyPI

```bash
pip install -U jnwb
```

Requires Python **3.12 or newer**. Tested in CI on 3.12, 3.13 and 3.14.

The current library release is dataset-agnostic. The public surface is documented in [Public API](api.md) and is the contents of `jnwb.__all__`.

A wheel carries the library, and the sdist adds `AGENTS.md` and `skills/`. Neither carries `examples/`, so the executable tutorials the [Quickstart](quickstart.md) and [Tutorials](tutorials/01_nwb_basics.md) tell you to run need the [source checkout](#source-checkout) below. [What an agent gets](agents.md) has the full table.

### Optional Acceleration Backends & Extras

`jnwb` is structured with modular extras so production workflows install only what they need:

```bash
pip install "jnwb[torch,gpu]"   # PyTorch, CuPy, and CUDA 12.x acceleration
pip install "jnwb[mcp]"         # Model Context Protocol server tooling
pip install "jnwb[vis]"         # Plotly figure engine jnwb.vis, with kaleido for SVG/PNG export
pip install "jnwb[docs]"        # MkDocs documentation builder
pip install "jnwb[test]"        # pytest and pytest-xdist, plus the build and notebook
                               # tooling the release gate and the tutorial tests need
pip install "jnwb[all]"         # Complete dependency bundle
```

`jnwb.vis` is the one export that needs an extra. Without `vis` installed, `import jnwb` and
every other export work, and accessing `jnwb.vis` raises `ImportError` naming
`pip install jnwb[vis]`. So does `from jnwb import *`, because `vis` is in `jnwb.__all__`.
[Plotly Figures](vis.md) shows a canvas end to end.

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
inside it. jnwb's own harness enforces the equivalent invariant on this repository,
and the published wheel ships only `jnwb/`.

For a stricter editable install that maps `jnwb` alone instead of the whole root:

```bash
pip install -e . --config-settings editable_mode=strict
```

## Deferred imports (0.1.6+)

`import jnwb` eagerly loads the core spectral, connectivity, and TFR surface. Symbols from
`statistics`, `metadata`, `decoding`, `ontology`, `analyzers`, `onset_fitting`, and `viz` resolve
on first access through `jnwb.__getattr__` without importing their submodules at package import
time. The `visual_qc` and `vis` submodules are likewise deferred. This keeps `scikit-learn`, `statsmodels`,
`matplotlib` and `joblib` out of the import while preserving the full public API in
`jnwb.__all__`, which the suite verifies symbol by symbol.

It does not make the import quick. `import jnwb` takes about 1.9 s, and about 1.8 s of that is
`scipy`, `pandas` and `pynwb`, which the eager surface needs: roughly 1.1 s for the first `scipy`
submodule imported, then 0.3 s each for `pandas` and `pynwb`, on top of 0.1 s for `numpy`. jnwb's
own module bodies are about 0.05 s of it. Deferring any single module does not change this --
`scipy` alone is imported at module scope by seven eagerly imported modules, so whichever one
runs first is charged the shared cost and the rest are free. Import the package once at process
start rather than per task.

## Verify

Run the verification snippet in your Python environment:

```python
import jnwb

print(f"jnwb version: {jnwb.__version__}")
print(f"Public surface: {len(jnwb.__all__)} symbols")
# jnwb.vis resolves only where the vis extra is installed.
from importlib.util import find_spec
optional = set() if find_spec("plotly") else {"vis"}
missing = [name for name in jnwb.__all__ if name not in optional and not hasattr(jnwb, name)]
assert not missing, f"Unresolved public exports: {missing}"
print("Verification passed successfully.")
```
