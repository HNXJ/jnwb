# Open stack (jnwb, 2026-10-25)

Open rows: the section at the end (0.2.15, 2026-10-28). A row leaves by being repaired, shown false, or moved into the todo stack (`AGENTS.md` §11); `git log -- artifacts/open_stack.md` holds the rows of earlier dates.

Cleared 2026-10-25, the 40 rows of the audit of ac8736ff (`git show e00e8664:artifacts/open_stack.md`):

- Moved to the todo stack as 17-09 to 17-56, section "Audit of 2026-10-25", one defect per item (O-1 to O-5, O-7 to O-16, O-19 to O-26, O-32 to O-36, O-38 to O-41).
- Folded into existing items, whose text now carries them: O-27 (12-05, 09-07, 12-06, 07-05, 11-07, 12-11, 16-18, 15-22 rewritten), O-28 (the Accept clauses of 11-07, 11-09, 11-03, 12-07), O-29 (15-20 and 12-05), O-37 (17-01).
- Repaired with its item: O-30 (16-10, the I3 scan, landed 2026-10-25).
- Repaired: O-6 (both handoff notes moved outside the repository, hashes checked, ruled 2026-10-25); O-31 (S9's row names its holder's scope, ruled 2026-10-25; non-finite inputs are roadmap row 17-24).
- Moved to the roadmap: O-17 (roadmap 17-07).
- Shown false: the `waveform_index_dtype` refusal (the repair casts to uint8, so refusing values above 255 is correct); FM-16 (path misses inside dated rulings are records).

Opened and closed 2026-10-23: P-CI-1, CI red on `dev` at 18457f3a. Every test leg failed on `fig37_verify_written_nwb` (panel B counted pynwb's embedded schema datasets, whose number changes by release). Repaired in 2543f72f; the run on 93ab6a82 is green on every leg.

## Open at 0.2.15 (added 2026-10-28, read-only audit at 6640f4a3)

Each row was checked against its file on 2026-10-28; the keeper commits this section.

| Id | Open item | Evidence | Owner | Next step |
|---|---|---|---|---|
| P-215-03 | 0.2.15 tag not cut; omission not told | `jnwb/__init__.py:14` is 0.2.14; `CHANGELOG.md` has no 0.2.15 heading; no notice record. A message to omission is outward: needs Hamm's word | keeper, Hamm | Tag after the release merge; notice on Hamm's word |
| P-215-04 | Mistake-log lines missing: false VIOLATION; a commit chained after a guarded command | `memory/mistake_log.md` has no line for either; its newest dated entries are 2026-10-27 and 2026-10-28. The false VIOLATIONs came from dispatcher commits that moved HEAD during runs; the chained commit never ran | keeper | Add one `trigger -> repair` line for each event |
| P-215-05 | Scratch clones and scratch folders not cleared | Session scratchpad: 37 clones under `lanes/`, plus `_temp_pathspec`, `_temp_pathspec2`, `diag_c1`. `C:/workspace/_temp_lane_*`: 13 clones of 39 MB, outside the scratchpad, all clean and detached. 11 lane HEADs are on no ref; 10 match a dev commit by patch; lane e (b24abc9f) is superseded by dev 6c0fd09b. Lane d2 also holds an ignored `artifacts/_temp/`. `C:/workspace/_temp_oc` (no git) holds run receipts and `suite_a.log` | Hamm | Ruled 2026-10-31, delete after check. Checked 2026-10-31: 8 `_temp_lane_*` clones remain, all clean; 7 HEADs match a dev commit by patch id, `_temp_lane_d2` is an ancestor of dev; its ignored `artifacts/_temp/` holds 7 probe scripts (39 KB). Hamm deletes `C:/workspace/_temp_lane_*`, `C:/workspace/_temp_oc` (15 MB) and the scratchpad `lanes/` (bulk deletes are blocked for the agent) |
| P-215-06 | agy retry not scheduled | Ruling 2026-10-28 (work routing): agy returned empty; its use waits on a packet that needs no file reads. No todo row, no packet | keeper | Write a no-read packet; route through `delegate-cli` |
| P-215-07 | Jarness branches: content in dev, no merge commit | Ruling 2026-10-28 said merge `_temp_jarness-check` (0038e3ad) and `_temp_jnwb-tools` (a7c8c7f3). Their content is in dev as d18a518e and e659cbd2 (cherry-picks); neither branch tip is an ancestor of dev | keeper | Record the content-equivalent merge or re-rule; the four agent files already point at `scripts/` |
| P-215-10 | 11-09, 16-20, 17-24 unstarted | In `todo_stack.md`; 17-24 waits on waves 1 to 3 merged | jnwb-developer lanes | Waves 3 and 4 |
| P-215-14 | 0.2.15 release not cut | `__version__` 0.2.14; 15 change fragments in `artifacts/changelog.d/` not assembled; blocked by P-215-09 to 11 | keeper, Hamm | Release gate after the wave barrier |
| P-215-15 | Branch names and a stale worktree | The nine local branches were renamed `_temp_*` and pushed on 2026-10-31. `proposal/spike-qc-pt-skill` (e40a4923) and `skill/spectrolaminar-work-bastos` (4dfb6422) are on origin as `_temp_spike-qc-pt-skill` and `_temp_spectrolaminar-work-bastos`, SHAs checked; the old names are still on origin (`push_guard.py` denies deleting a non-temporary branch). Worktree `.claude/worktrees/site-overview-326890` is clean at 9b52c5e7 (= `_temp_site-overview` on origin); `git worktree remove` hit Permission denied | Hamm | Hamm deletes the two old origin names and the worktree folder, then `git worktree prune` |
| P-215-16 | 16-20 coherence graph open (lane H, wave 3) | No distance-normalised edge code or planted-field test in `jnwb/spectral/_coupling.py`, `jnwb/connectivity/_network.py`, `tests/test_connectivity_pitfalls.py`; the reviewer-at-high step has no receipt | jnwb-developer, lane H | Reviewer first, then the packet |
| P-215-20 | Stack pointers name roadmap ids that are done or in todo | `standing.md:144-148`, `fact_stack.md:68,82,86`, `open_stack.md:10-11` cite roadmap 17-03 to 17-08 and 17-24; `roadmap.md` has none of them. `standing.md:144` says psth keeps `(-1000, 2000)` until 0.2.15; false, psth requires `window_ms`. S13 holds `todo:12-21`, which lives in roadmap | keeper | Repoint each row to its current place; correct the B3 claim |
| P-215-28 | `artifacts/state.md` is over its 80-line cap | `artifacts_check.py` (measured, checked 2026-10-30): 123 lines against 80; the file is generated by `scripts/reconstruct_state.py` | keeper | Condense the generator's output; git holds the history |

Verified closed, not open: the v0.2.14 tag re-cut (`refs/tags/v0.2.14` peels to 58a2b92e, which is `main`); the four agent files point at `scripts/`.
