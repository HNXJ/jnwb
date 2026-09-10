# CLAUDE.md — jnwb

Generic, dataset-agnostic NWB (Neurodata Without Borders) analysis library.

**Start with [`AGENTS.md`](AGENTS.md)** for the repository map, workflow loop (`W = P (R G)^N S`),
gates, skills, and change policy. This file holds scientific invariants only.

## Where truth lives

| Question | Source | Never |
|---|---|---|
| What is in the public API | `jnwb/__init__.py`'s `__all__` | a symbol list remembered from any document, including this one |
| What was actually computed | the receipt named beside the number | a summary of it |

## Tripwires

1. **No empirical value in any output that no script computed from data.** Hardcoded values
   are permitted only for visual/task constants or output explicitly marked synthetic.
2. **Take the logarithm last.** Average power, divide by baseline, `10·log10` once. Never
   average decibels — it biases each site by its own noisiness.
3. **`jnwb/` does not import from any project folder.** The dependency runs one way: projects
   depend on `jnwb`, never the reverse. `jnwb` must give identical scientific behaviour
   whether a downstream project package is installed or absent.
4. **Preserve module- and array-level invariants**: units, coordinate frames, timestamps,
   sample rates, 0- vs 1-indexing do not change silently across a `jnwb` function boundary.

## Working agreements

- Preserve originals; write revisions as new files.
- On `dev`, commit and push validated checkpoints per `AGENTS.md` §3.

## Skills

Load the skill before doing the work; do not reinvent its contents. See `AGENTS.md` §7.
`numerical-computing` · `biophysical-modeling`
