# `artifacts/` — catalogs and the evidence graph

**Purpose:** machine-generated, machine-readable state — not narrative. This is what
`../context/PROJECT_STATE.md`'s prose should always trace back to.

**Owns:** `data/` (corpus catalogs: `nwb_catalog.json`, `session_readiness.csv`,
`corpus_manifest.json` — prefer these over any session/unit count written in prose anywhere else
in the repo); `.lab/` (the `labyrinth` evidence graph — read before starting work that depends on
a claim's standing, write after that standing changes); `developer/` (local scratch, partially
git-tracked per `.gitignore`); `reports*/` (generated verification reports).

**Does not own:** scientific narrative (`../context/PROJECT_STATE.md`) or generated figure/table
outputs (`../outputs/`).

**How to apply:** when a number in this repo needs verifying, this directory (or the receipt it
names) is the source — not a summary of it, and not a document that itself summarizes it.
