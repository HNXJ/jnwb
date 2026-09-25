# `except Exception` inventory — jnwb 0.1.7

Scan date: 2026-09-10 (post-metadata/jrsa narrowings). Each remaining broad catch is
classified; none are unclassified.

| Location | Class | Rationale |
|---|---|---|
| `_backend.py:55,65` | **narrowed** | CUDA probe: `ImportError`, `OSError`, `RuntimeError`, `AttributeError` |
| `addressing.py:145,173` | **narrowed** | Electrode row mapping: value/index/type errors only |
| `metadata.py:91,338` | **narrowed** | NWB batch read: `_NWB_READ_ERRORS` + `on_read_error` |
| `jrsa.py:109,912,1004,1462,1314` | **narrowed** | Repr/tensor conversion/RNG introspection/Granger AIC |
| `analyzers.py:453,715,738` | required boundary | Optional GPU (CuPy/torch) with CPU fallback |
| `compression.py:461` | required boundary | NWB round-trip verify: any read failure must be captured for src/dst parity |
| `connectivity.py:249` | required boundary | Optional GPU VAR fit with CPU fallback |
| `gpu_pca.py:77` | required boundary | Optional torch SVD with NumPy fallback |
| `tfr.py:219` | required boundary | Optional CuPy convolution with CPU fallback |
| `trajectory.py:163` | required boundary | Optional torch SVD with NumPy fallback |
| `spectral.py:250,520,587,678,701,792` | required boundary | Optional GPU welch/coherence paths with CPU fallback |
| `mcp_server/nwb_tools.py:64,134` | required boundary | MCP tool must return structured error, not raise |
| `mcp_server/event_tools.py:156` | required boundary | MCP tool structured error surface |
| `mcp_server/meta_tools.py:72` | required boundary | MCP tool structured error surface |
