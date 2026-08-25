# `notebooks/` — figure-suite notebooks

**Purpose:** notebook-driven figure generation, as opposed to `../scripts/`'s standalone
analysis/aggregation scripts.

**Owns:** current figure-suite notebooks at the top level; `historical/` for quarantined ones.

**Does not own:** current scientific state (`../context/PROJECT_STATE.md`) or one-off analysis
scripts (`../scripts/`).

**Footgun:** `historical/reproducibility_master_pipeline.py` is quarantined — it asserts a
retracted census figure (see `../context/09_conflicts_and_flagged_discrepancies.md` and
`../tests/test_no_retracted_census_in_live_code.py`, which enforces this at test time). Do not
run it as a current reproducibility check and do not un-quarantine it without resolving that
retraction first.
