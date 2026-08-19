# Handout for the next agent — omission-a 7-figure pipeline

**Read `context/docs/CONTEXT.md` first** (authoritative project context — paradigm, corpus,
data topology, analysis contracts). This handout is scoped narrowly to the figure-build work
done across the last several sessions in `context/figures/`, not the whole project.

**This is a shared, multi-agent workspace.** You will see files change, new `artifacts/.lab/*.json`
nodes appear, and scripts you didn't write — that is routine, not an anomaly. Verify claims
(including ones in this handout) against the filesystem before relying on them; don't assume
you caused every change you see, and don't assume every change someone else made is safe to
build on without a quick check.

## Figure status

| Fig | Status | Notes |
|---|---|---|
| 1 | **Locked** | `context/figures/fig01_finalized.svg/.png` |
| 2 | **Locked** | `context/figures/fig02_finalized.svg/.png` — 4x4 raster grid (S+/S-/O+/O++), black dots, per-column PSTH row with all 4 R-family conditions overlaid + epoch shading, O++ column manually overridden to unit 51/FEF/sub-C31o_ses-230823 (documented in the script, not a reclassification) |
| 3 | **Locked** | `context/figures/fig03_finalized.svg/.png` — presence-by-area (MST+FST merged, "stable" redefined via `outputs/classification/unit_trial_presence.csv`), composition8-by-area (Null→Other display label), RXRR template trace split S-family/O-family |
| 4 | **In progress, not yet locked** | See below |
| 5 | **Not touched this session** | Whatever is on disk is its last standalone build; not reviewed |
| 6 | **Not touched this session** | Prior corrections (15/15 sessions, 3-way layers, 0/240 significant) still stand per `context/figures/fig06_band_power_coupling/README.md` |
| 7 | **Not touched this session** | Same corpus corrections as fig06, 0/60 significant |

## Figure 4 — current state and what's left

`context/figures/fig04_v1_pfc_condition_tfr/fig04_v1_pfc_condition_tfr.py`. Main output:
`fig04.svg` / `fig04.png` in that directory (last regenerated 2026-08-02, clean).

**Done this session:**
- Expanded from a V1/PFC-only build to the full 4-area plan (V1, V3a/d, TEO, PFC) — the
  2-area version was a scope gap against `CLAUDE.md`'s stated plan, not a deliberate choice.
- Per-spectrogram colour scale changed from one shared 99th-percentile |dB| limit to each of
  the 16 panels autoscaled to itself (`colour_scale_db_per_panel` in the receipt).
- Frequency-axis smoothing is now **proportional/constant-Q**: `sigma_hz = max(freq * 0.12, 2.0)`
  via `freq_proportional_smooth_matrix()` — higher frequencies get proportionally wider
  smoothing, matching how compressed they are on the log-frequency display. NOT a fixed bin
  count (that was the first pass; the user asked for it to scale with frequency).
- Time-axis smoothing is **segmented per epoch** (fx/p1/d1/p2/d2/p3 boundaries from
  `EPOCH_ONSETS_MS`) via `smooth_time_segmented()` — a transient at a real event onset cannot
  leak across that boundary the way one continuous whole-trial kernel would. Applies to both
  the spectrogram maps and the band traces.
- **fig04.png added** (copies the assembled panel's own matplotlib-rendered PNG).

**Root-caused and fixed a severe bug:** the script hung for 15+ hours (twice) before this was
found. Cause: spectrogram shading was set to `"gouraud"` for visual smoothness, and gouraud's
per-vertex SVG output measured **11x slower to save than `"nearest"`** (26.6s vs 2.4s for one
panel, isolated test) — across 8 spectrograms plus concurrent CPU load from other agent
sessions on this shared machine, that became pathological. Fixed: reverted to
`shading="nearest"` (the Gaussian data-smoothing already provides the visual softening; gouraud
interpolation on top was redundant and is what actually broke). Full script now runs in well
under a minute. **If you add any new smoothing/interpolation to this script, test SVG savefig
time on one panel in isolation before running the full thing** — this exact mistake is cheap to
avoid and expensive to debug live.

**Still open — pick this up:**
1. `fig04_finalized.png` has **not** been rendered yet. The user asked for it via headless
   Chrome (the `mcp__Claude_Browser__*` tools) with a solid white background, matching the
   convention used for figs 1-3's `_finalized.png` files — though note: nobody in this
   session's traceable work actually knows how figs 1-3's finalized PNGs were produced (no
   metadata trail, `PIL().info` is empty on all three). Don't assume a specific prior method;
   just produce a clean white-background PNG via the browser tool as asked.
2. Once `fig04_finalized.png` exists, copy it (and `fig04.svg`) out to
   `context/figures/fig04_finalized.svg/.png`, matching figs 1-3's pattern, and lock it —
   only after the user confirms the panel content itself (colour scales, smoothing, layout)
   is done, the same way figs 2/3 went through several rounds before being locked.
3. A `review_pass_*` / `seal_checkpoint_*` node in `artifacts/.lab/` should be written once
   fig04 is actually locked, following the pattern of
   `artifacts/.lab/seal_checkpoint_20260801_fig02_fig03_repo_reorg.json` (which explicitly
   excluded fig04 — it wasn't done yet at that point either).

## Process/environment gotchas learned this session

- **This machine runs slow and is shared.** A script that finishes in ~1 minute under light
  load has taken 15+ hours under contention from concurrent agent sessions. Long silent
  background runs are not automatically "hung" — check memory trend (`tasklist`/`wmic`) before
  killing; a steadily growing RSS usually means real progress, not a stall. But also don't wait
  indefinitely: if something that normally takes minutes is still at it after an hour with no
  output, isolate the slow step (see the SVG/gouraud lesson above) rather than just re-killing
  and re-running the whole thing repeatedly.
- **Python's stdout is block-buffered when redirected to a file** (`python script.py > log.txt`).
  Empty log content does not mean nothing is happening — it may just not have flushed yet.
  Use `python -u` for live output if you need to watch progress in a redirected log.
- **When killing stuck background processes, verify the kill actually took** (`tasklist`) before
  relaunching — duplicate zombie copies of the same script competing for memory was a real,
  repeated cause of slowdown this session, separate from the gouraud bug.
- **A transient `OSError: [Errno 22] Invalid argument` on a file write** (hit once on
  `fig04.svg`) resolved by deleting the stale file and rewriting fresh — likely a lock from
  concurrent access in this shared workspace, not a code bug.

## Repo layout note (also from this session)

`context/` and `outputs/` root directories were reorganized to hold only folders (no more
loose files at the top level):
- `context/docs/` — `CONTEXT.md`, `PUBLICATION_STYLE_CRITERIA.md` (moved from `context/` root)
- `context/drafts/` — `omission-a-draft-v1.md`, `v2.md`, `v3.md` (v3 is current, per its own
  header — check `context/drafts/omission-a-draft-v3.md`'s top comment before assuming, since
  drafts have moved fast this session)
- `outputs/archive/root_misc_2026-08-01/` — orphaned loose files that used to sit in `outputs/`
  root (dead packaging cruft, superseded CSVs, stray logs)
- `outputs/legacy_root_figures/` — `figure1_killer_omission_summary.png/.svg`, still referenced
  by `scripts/generate_context_figures.py` (itself a stale-looking legacy 8-figure pipeline
  script, not part of the current fig01-07 build — don't treat it as authoritative)

All live cross-references to the moved files (`CLAUDE.md`, `.agents/skills/match-my-writing-
style/SKILL.md`, the draft files' own self-references) were updated in the same pass — verified
by grep before and after, not assumed.

## Skill/graph housekeeping (background, probably not your immediate concern)

- `.claude/skills/` and `.agents/skills/` both hold the same 13 canonical skills — verified
  identical by directory diff. `.claude/skills/` is where Claude Code's project-skill loader
  actually reads from (per `artifacts/.lab/harness_skill_registry_repair_20260731_correction.json`).
- `.gemini/config/skills/progress-review-plan` was still not tombstoned as of this session,
  despite a claim (from a "Gemini" persona message) that it had been — checked directly, found
  false. If you're picking up cross-CLI skill parity work, verify current state again rather
  than trusting that claim or this note.
- `artifacts/.lab/labyrinth_patch_20260725_v16_doctrine.json`'s "92 derived_from / 6 claim_links
  / 83% isolated" graph-edge figures did not reproduce against a direct recount this session
  (actual: 178 `derives_from` edges, no relation literally named `claim_links`, 13.5% zero-
  outdegree nodes) — see `artifacts/.lab/claude_code_health_audit_20260801.json` for the full
  audit. Re-verify before citing either set of numbers.
