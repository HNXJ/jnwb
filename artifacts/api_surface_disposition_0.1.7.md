# API surface disposition — jnwb 0.1.7

Authority: `jnwb.__all__` (111 symbols). Registry: `jnwb/_api_surface.py`.

## Focus modules

| Module | Disposition | Rationale |
|---|---|---|
| `nwb_io` | module-internal | HDMF read-boundary repairs; used by `metadata`, `compression`, MCP tools. Not in `__all__`. |
| `gpu_pca` | module-internal | SVD helper tested directly; public trajectory API is `compute_population_trajectory`. Not in `__all__`. |
| `bilinear` | optional-experimental | Rank-K bilinear decoder; import `jnwb.bilinear`. Torch/sklearn optional. Not promoted. |
| `nam` | optional-experimental | Per-unit NAM decoder; torch required. Not promoted. |
| `mcp_server` | optional-experimental | MCP tool host; symbols not in top-level `__all__`. |

## Infrastructure (module-internal)

`_backend`, `_parallel`, `_lazy_exports`, `_api_surface` — not public.

## Public modules

All other active `jnwb/*.py` modules export symbols via `__all__` / `_lazy_exports.EXPORT_MODULES` / eager imports in `__init__.py`.

## Asymmetries resolved

- `trajectory.py` removed unused `gpu_pca` import (`compute_population_trajectory` uses inline SVD).
- `docs/03_representational_similarity_jrsa.md` no longer claims `jrsa` calls `gpu_pca`.
