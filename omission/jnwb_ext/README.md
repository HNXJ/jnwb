# `jnwb_ext/` — omission-specific extensions of the `jnwb` API

**Purpose:** every module here is this experiment's own code — paradigm-specific classification,
condition mappings, report generation — built *on* the frozen `jnwb/` library, never inside it.

**Owns:** `OmissionSession` (session.py), unit classification (S+/S-/O+/O++), spectral/spiking
analysis at the omission-condition level, decoding, connectivity, report generation, viz.

**Does not own:** anything dataset-agnostic — that belongs in `jnwb/` (repo root), which is
frozen and read-only (see root `CLAUDE.md`). If a function here feels generic enough to belong
in `jnwb/`, that's a promotion decision for Hamm, not a unilateral move.

**Canonical entry points:** `session.py` (`OmissionSession` — nearly everything hangs off this),
`factories.py` (bridges to the generic `jnwb.ontology` objects). See the module map in
[`../README.md`](../README.md) for the full table.

**Dependencies:** imports from `jnwb/` (one-way — `jnwb/` never imports back, see root
`CLAUDE.md` tripwire 3). Consumed by `../scripts/`, `../tests/`, `../context/figures/`.

**Receipts/current authority:** behavioral changes here are scientific-code changes, not harness
changes — verify against `../tests/` and record in `../artifacts/.lab/` per the working
agreements in `../CLAUDE.md`.
