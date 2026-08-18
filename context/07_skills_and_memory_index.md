# 07 — Skills and Memory Index

Generated 2026-08-17. Confirmed on disk via `ls .claude/skills/`: **7 skills exist** —
`omission-data`, `omission-signal`, `omission-spiking`, `omission-statistics`,
`omission-figures`, `manuscript`, `labyrinth`. **CLAUDE.md's skill list names 9**, including
`numerical-computing` and `biophysical-modeling`, which do **not exist on disk**. This is a
confirmed registry-staleness instance (CLAUDE.md's own "registries go stale silently" principle,
demonstrated by CLAUDE.md itself) — flagged in [09_conflicts_and_flagged_discrepancies.md](09_conflicts_and_flagged_discrepancies.md).

## Skill index

| Skill | Owns | Load when |
|---|---|---|
| **`omission-data`** | Path resolution API, corpus discovery, session loading, condition/quality-tier tables, dual-area-probe/identity footguns | Any task touching NWB paths, session loading, or corpus counts |
| **`omission-signal`** | TFR/LFP filtering, spectral estimation, baseline normalization, band table, connectivity pooling design | Any TFR, LFP, spectral, or connectivity task |
| **`omission-spiking`** | Unit analysis API, response classification (naming which of the several classifiers), drift metrics, laminar assignment, waveform | Any spike/unit-response task |
| **`omission-statistics`** | Estimand/model choice, inferential unit, multiplicity, intervals, permutation exchangeability, `jrsa` | Any statistical test, p-value, or interval being reported |
| **`omission-figures`** | Figure pipeline, style constants, panel assembly, visual verification, placeholder flagging, per-panel scope | Any figure build or edit under `context/figures/` |
| **`manuscript`** | Verb-to-design matching, register, claim discipline, prose style, DOCX production | Any manuscript-prose or DOCX-generation task |
| **`labyrinth`** | Evidence graph (`artifacts/.lab/`), node schema, evidentiary standing, checkpoints, graph health | Recording a finding, bug, or decision durably; checking graph health |

Each skill body opens with a `ROUTING_SENTINEL` (e.g. `omission-data:v1`) — an acceptance-test
marker unique to that skill's body, not its description, so quoting it back is positive evidence
the skill was actually retrieved rather than guessed.

## `omission-data` — summary

Path resolution: `oa.paths.describe()`/`REPO_ROOT`/`nwb_dir()`/`analysis_dir()`/`tfr_dir()`/
`meta_dir()`/`outputs_dir()`/`require()`. Corpus discovery via `scripts/discover_corpus.py
--check`. Session loading: `oa.read`, `oa.batch_read`, `session.info/summary/get_units/
get_electrodes/get_epochs/lfp_channel_areas/channel_unit_mapping`. Full condition-code table
(see doc01). Unit-quality-tier definitions. **Footguns**: unit identity is row position, not
`unit_id` column; dual-area probes resolve by channel position (never `.split(',')[0]`);
bytes-encoded h5py columns; direct h5py layout differs by subject; same-named join columns
aren't the same field (`quality` in two different tables disagrees on 1,942/6,650 shared units);
constant-column footgun (`layer=Superficial` for all 6,655 legacy units).

## `omission-signal` — summary and confirmed staleness

11 numbered sections ordered by damage-when-unnoticed: (1) log-last rule; (2) phase-
representation-decided-up-front, **references `jnwb.complex_tfr` — confirmed dead**, module
quarantined to `jnwb/_unused/complex_tfr.py`, not importable as written (doc02/doc04); (3)
filtering (zero-phase filtfilt vs causal, filter-before-decimate, edge effects); (4) spectral
estimation naming; (5) baseline normalization as a modeling choice; (6) settled band table
(matches `connectivity.CANONICAL_BANDS` — but see doc02's four-way band fragmentation, this
skill's table is only one of four live definitions); (7) V3a/V3d pooling; (8) TFR array
naming/shape; (9) LFP memory management; (10) connectivity "test within session first, pool
after" — **the PPC-retirement stance here is now stale**: the skill says PPC is retired in favor
of the sliding-correlation replacement, but the 2026-08-15 corrected-design PPC rebuild reversed
that (doc04) — provisional non-null result, explicit Hamm override of the skill default; (11)
trial-count sanity checks.

## `omission-spiking` — summary

API list (`UnitAnalyzer`, `raster_plot`, `psth_analysis`, `autocorrelogram`, `find_units`,
`classify_omission_response`, `phase_locking_index`). "The unit axis has no biological
topology" — never spatially smooth/convolve across unit rows. Response-classification section
names **two** classifiers (`jnwb.unit_classification` shuffle-test vs the archived
template-correlation script) — doc03 now documents **four**, including the modern native
classifier's own distinct O+/O++ design and S1's additive inclusion criterion; this skill
predates that full reconciliation and should be read alongside doc03, not instead of it.
Verification checks: one-vs-two-sided, denominator-before-enrichment, selection-criterion-
contains-conclusion (O++ being area-restricted by construction is the sharpest current example),
count-sessions-not-just-units.

## `omission-figures` — summary

Import style: `figstyle.py`/`svgassemble.py`/`figstats.py` — never restate a color/area/exemplar/
timing constant elsewhere. **Standing rule**: any figure or panel with placeholder/synthetic/
fallback content must render an unmissable red `PLACEHOLDER-DUMMY` title; one fabricated panel
flags the whole assembled figure. Reference implementation: `fig04_omission_identity_decoding.py`'s
`used_placeholder` flag. Population scope must be labelled per panel. **Rendering workaround on
this machine** (`cairosvg`/`reportlab.renderPM`/browser `file://` all fail): read the `.png`
companion every `figstyle.save()` call writes; for an SVG with no PNG companion, `svglib.svg2rlg`
→ `reportlab.renderPDF.drawToFile` → Read the PDF. **`jnwb.markdown_report` reference is
confirmed dead** — quarantined to `jnwb/_unused/markdown_report.py`, same staleness class as
`omission-signal`'s `complex_tfr` reference (doc02).

## `omission-statistics` — full detail in [06_statistics_and_inference.md](06_statistics_and_inference.md)

## `manuscript` — summary

Verb-to-design matching table; register separation (instruction voice vs paper voice); claim
discipline; measured style targets (median 16/mean 18/p90<32 words, hedge-word frequencies,
banned-words list); numbers-in-prose rules; methods-must-describe-what-actually-ran; structure
(Abstract→Intro→Results→Discussion→Methods→Appendix→References, abstract 6-move template,
declarative results subheadings); DOCX production rules (hard page breaks, `keep_with_next`,
never regex-substitute raw XML, `docxtpl` Jinja2); 16-item anti-patterns list; self-check
checklist.

## `labyrinth` — summary

**Owns**: the evidence graph under `artifacts/.lab/` — node schema, evidentiary standing, edge
vocabulary, checkpoints, graph health, export. Write a node when a turn produces something a
future session would be wrong without — not on a per-turn cadence (measured on this repo's own
graph: write-every-turn nodes carried receipts 97% of the time but were isolated at 21%, vs 41%/
12% for older nodes — claim quality rose while graph connectivity decayed). **Prefer an edge, a
status change, or an appended note over a new node.** `unconfirmed → provisional → confirmed`
requires independent confirmation (threshold 2) — never move to `confirmed` from reasoning alone.
Goals require a stated falsifier. **The user is a source, not an oracle** — what Hamm asserts
enters as a claim at `unconfirmed`, same bar as a paper; a contradiction with a confirmed node is
a `contradicts` edge stated plainly, never silently reconciled. Conservation: move rather than
delete (the `jnwb/_unused/` quarantine pattern is the reference implementation). **Amendment**:
changes to CLAUDE.md or memory always require explicit human approval; skill/memory files need
independent confirmation before the human gate — agents propose, never amend. Known open debt:
this repo's graph currently carries unresolved validator violations and dangling edges,
deliberately unresolved, not a blocker for ordinary work.

```bash
python scripts/validate_labyrinth_claim_status.py
python scripts/build_lab_obsidian_graph.py    # --format html | md | both
```

## Memory system (auto-memory, outside the repo)

Stored at `C:\Users\nejath\.claude\projects\C--workspace-omission\memory\`, indexed by
`MEMORY.md`. Current entries relevant to this project's work:

- **User role/domain** — Hamm, systems neuroscience, electrophysiology/NWB.
- **Machine and git setup** — single Windows box, SSH-only remotes, no Mac client.
- **Check hardware before heavy compute** — GPU is real here, check unprompted.
- **Memory is path-keyed and fragile** — a drive-letter change orphans the whole store (directly
  relevant to the `D:`→`C:` remap history documented in `jnwb/paths.py`, doc01/doc02).
- **How Hamm gives figure feedback** — dense multi-figure specs, check cross-figure consistency
  first.
- **External protocol proposals** — adopt amendments, reject parallel infrastructure.
- **Concurrent Cursor session** — repo shares an uncommitted tree with another live agent
  session; check before editing shared files. **Directly relevant right now** — doc05's git
  status shows heavy uncommitted work across shared figure infrastructure; this memory note is
  the reason to `git diff` before trusting or further editing any of it.

## `artifacts/.lab/` — evidence graph, current state (per skill's own "known open debt")

The graph carries unresolved validator violations and dangling edges as of the last check this
audit is aware of. Run `scripts/validate_labyrinth_claim_status.py` for a current reading before
citing any node's `confirmed` status as verified — per `labyrinth`'s own rule, a `confirmed`
label is only as good as its receipt, and status inflation (nodes marked confirmed without a
verification receipt) is a measured, not assumed, quantity.
