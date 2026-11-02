# Open stack (jnwb, 2026-10-25)

Open rows: the section at the end (0.2.15, 2026-10-28). A row leaves by being repaired, shown false, or moved into the todo stack (`AGENTS.md` §11); `git log -- artifacts/open_stack.md` holds the rows of earlier dates.

Cleared 2026-10-25, the 40 rows of the audit of ac8736ff (`git show e00e8664:artifacts/open_stack.md`):

- Moved to the todo stack as 17-09 to 17-56, section "Audit of 2026-10-25", one defect per item (O-1 to O-5, O-7 to O-16, O-19 to O-26, O-32 to O-36, O-38 to O-41).
- Folded into existing items, whose text now carries them: O-27 (12-05, 09-07, 12-06, 07-05, 11-07, 12-11, 16-18, 15-22 rewritten), O-28 (the Accept clauses of 11-07, 11-09, 11-03, 12-07), O-29 (15-20 and 12-05), O-37 (17-01).
- Repaired with its item: O-30 (16-10, the I3 scan, landed 2026-10-25).
- Repaired: O-6 (both handoff notes moved outside the repository, hashes checked, ruled 2026-10-25); O-31 (S9's row names its holder's scope, ruled 2026-10-25; non-finite inputs became todo 17-24, done 2026-10-31).
- Moved to the roadmap: O-17 (roadmap 17-07).
- Shown false: the `waveform_index_dtype` refusal (the repair casts to uint8, so refusing values above 255 is correct); FM-16 (path misses inside dated rulings are records).

Opened and closed 2026-10-23: P-CI-1, CI red on `dev` at 18457f3a. Every test leg failed on `fig37_verify_written_nwb` (panel B counted pynwb's embedded schema datasets, whose number changes by release). Repaired in 2543f72f; the run on 93ab6a82 is green on every leg.

## Open at 0.2.15 (added 2026-10-28, read-only audit at 6640f4a3)

Each row was checked against its file on 2026-10-28; the keeper commits this section.

| Id | Open item | Evidence | Owner | Next step |
|---|---|---|---|---|

Verified closed, not open: the v0.2.14 tag re-cut (`refs/tags/v0.2.14` peels to 58a2b92e, which is `main`); the agent files point at `scripts/`.

Audit of 2026-11-02 (seven models at `7ca5b9a6`): no open row; its findings went to the todo stack as 17-83 to 17-105.

## Open at 0.2.16 (GitHub issues, 2026-11-02)

Each issue's own repro was run on `dev` at `9fa0833a` (jnwb 0.2.15 from the checkout). #34 reproduced fixed (dae675a9, v0.2.15) and was closed on GitHub.

| Id | Open item | Evidence | Owner | Next step |
|---|---|---|---|---|
| P-216-01 | hnxj/jnwb#35: `check_waveform_blocks` refuses amplitude and `waveform_mean` in different unit scales with no way to declare the scale | repro: `ValueError ... median ratio ... is 1e+06`; `waveform_mean.attrs["unit"]` unread | keeper, Hamm | a keyword-only scale argument is a public signature: Hamm's word, then a todo item |
| P-216-02 | hnxj/jnwb#36: `validate_nwb` reports the installed distribution's version and hides read-layer warnings | `nwb_validate.py:273` reads `metadata.version`; repro prints `1 [0]` (one read warning, layer counts 0) | keeper | todo item: `jnwb.__version__`, record read-layer warnings |
| P-216-03 | hnxj/jnwb#37: `events` and `inspect` cannot reach `TimeIntervals` in a processing module | repro: `inspect(...)["interval_tables"]` is `[]`; `events(table="processing/behavior/events")` raises `IntervalTableNotFoundError` | keeper | todo item: resolve slash paths, list them in `inspect` |
| P-216-04 | hnxj/jnwb#38: `electrode_inventory`'s `group` column holds the `ElectrodeGroup` repr with memory addresses | repro prints `probeA pynwb.ecephys.ElectrodeGroup at 0x...` | keeper | todo item: map containers to `.name` |
| P-216-05 | hnxj/jnwb#39: on a file with no `/units`, `unit_census_report` fails inside pandas and the integrity checks raise `KeyError` | repro: `ValueError Cannot describe a DataFrame without columns`, `KeyError "no table group 'units'"` twice | keeper, Hamm | `unit_census_report` is a bug; the checks' documented `KeyError` is Hamm's API call |
| P-216-07 | `granger_causality` (deprecated since v0.1.7) is the only Granger with a GPU path; `granger` has no `device=` | `_granger.py` `resolve_device(device, context="granger_causality", prefer="cupy")`; `inspect.signature(jnwb.granger)` has no `device` | Hamm | rule: give `granger` a `device=` path, or drop GPU Granger with `granger_causality` (ruling 2026-11-02, 17-93) |
| P-216-06 | hnxj/jnwb#40: proposal, a profile-driven `jnwb.lab` certification framework with lab profiles outside jnwb | the draft branch `lab-validate-bastoslab` is local only; no ruling or roadmap row names it | Hamm | Hamm rules scope (AGENTS.md §4.3: no corpus convention in jnwb) |
