# CLAUDE.md — Omission

Claude Code entrypoint for this repo.

**Canonical project doctrine:** `.agents/AGENTS.md`  
**Global doctrine (Claude sessions):** `~/.claude/CLAUDE.md` — authoritative, auto-loaded.  
**Cursor/Gemini working agreement:** `C:\Users\nejath\.gemini\config\AGENTS.md` — binding for
those harnesses, **not** a Claude authority. The two diverged (0.02 similarity) and contradict
each other on the v15 four-engine model; `~/.claude/CLAUDE.md` is the tie-breaker here.

Do not duplicate long doctrine here. If you need omission-specific paths, footguns, or PRP
triggers, read `.agents/AGENTS.md` first. Legacy notes in `legacy/markdowns/CLAUDE.md` are
historical — prefer live `artifacts/data/nwb_catalog.json` and `artifacts/data/session_readiness.csv`.

**Corpus size updated 2026-08-11: 22 sessions, not 21.** `sub-V198o_ses-230629_rec` (previously
on disk but absent from both inventories, flagged in
`artifacts/.lab/data-volume-layout-and-tfr-spec-transfer-20260808.json`) was deliberately added
to the corpus by explicit user decision — `scripts/build_nwb_catalog.py` and
`scripts/build_session_readiness.py` were re-run and now both list 22. `omission_grand_units.csv`
(the fig03/classification source table) reflects this: 9,056 units, 22 sessions, as of the
`scripts/classify_omission_units_grand.py` run that added `omission_class_v2` the same day. Any
older number quoting "21 sessions" or "8,592 units" predates this and should be re-verified
against the live tables before being restated. The stale "17-session TFR corpus" figure below
also predates the 2026-08-08 drive migration — verify against `session_readiness.csv`'s
`tfr_ok`/`suite_tfr_ready` columns rather than quoting either number.


---

## Labyrinth Reflex — every user turn reads and writes the graph

**Consult `artifacts/.lab/` before you answer; leave a delta in it before you finish.** The
default posture on every turn, including one-line prompts. Do not ask permission to do it.

**Full rules: the "Labyrinth Reflex" section of `~/.claude/CLAUDE.md`, which is already loaded
in this and every other session — read it there, not here.**

Condensed 2026-08-08. This section previously restated the reflex in full, making three copies
of one rule set: `~/.claude/CLAUDE.md` (always loaded), this file (always loaded), and
`C:\Users\nejath\.gemini\config\AGENTS.md`. Two always-loaded near-copies at 0.18 textual
similarity is the exact "two documents disagree, and you must diff them to know which won"
hazard the doctrine warns about. The user-scope file is the live text; this is a pointer.

---

## Draft series

Manuscripts on this corpus are named `omission-a`, `omission-b`, `omission-c`, … Each letter is
a distinct paper, not a revision of the previous one.

- **omission-a** — sparse omission-linked single-unit spiking together with low-frequency LFP
  change. Keep the number of distinct inferential frameworks minimal and prefer exact binomial
  CIs for proportions.

  **The original framing is superseded and must not be restated without re-deriving it.** It
  read: *sparse, higher-order-leaning spiking* plus *widespread low-frequency modulation across
  the hierarchy*, with V3 as the exception. As of 2026-07-28:
  - The low-frequency change is large within each animal, about twice the gamma change, but
    has **no direction shared across animals**. One animal falls in every band below 50 Hz
    (q < 0.005), another rises in all five (q < 0.02), and the pooled estimate over 23 sessions
    is null in theta, alpha and beta. The difference survives holding area constant, in seven of
    eight testable area-by-band comparisons.
  - Adjusted for animal, alpha and beta are elevated in FEF, PFC, MT and **V3a/d** relative to
    V1; V3a/d beta replicated at +1.11 dB on both the 17- and 23-session corpora.
  - The higher-order spiking claim depends on which classification pass is used and has not
    been settled. See `context/inventory/CLASSIFICATION.md`.

  Figure plan: 1 method/paradigm/showcase · 2 rasters · 3 unit counts by group, area and type ·
  4 omission TFR for V1, V3a/d, TEO, PFC · 5 band-power coupling network · 6 spike–LFP ·
  7 O+/S+/S− band-power relationship with laminar statistics. GLMM deferred to a later paper.

## Omission footguns and critical sources

Relocated 2026-07-28 from `~/.claude/CLAUDE.md`, which loads in every project on this
machine — these rules are specific to this repo and belong here.

Current focus: single-unit spiking, waveforms, unit metadata, and NWB event-aligned extraction.

Key doctrine:
- Use correct trials only by default.
- `nwb.intervals["omission_glo_passive"]` is event-level, not trial-level.
- Use `stimulus_number` for p1-p4 selection: p1=2, p2=3, p3=4, p4=5.
- Do not confuse BHV odd event codes with NWB sequential event codes; `stimulus_number` is the stable crosswalk.
- Preserve SPK/SUA, MUAe, and LFP separation.
- Preserve session, area, layer, probe, and unit namespaces.
- For single-unit/waveform work, use `outputs/publication_figures/data_tables/grand_database_6040_units.csv`,
  `outputs/publication_visual_review/area_layer_tfr/layer_masks.json`, and NWB `units`/`processing`
  as the core sources.
- Treat waveform duration units and layer-mask unit namespaces as verification hazards before making biological claims.
<!-- Removed 2026-08-08: this bullet described downstream-audience handouts at
     `outputs/archive/notebooks/{data,colab}_handout.md`. Neither file exists anywhere in the
     repo (checked by `find . -name "*handout*"`, which returns only
     `context/archive/info/09_figure3_handout_2026-07-13.md` and a .lab node). The rule it
     stated -- convenience copies lose to the authoritative handout, and drift gets flagged --
     still holds for any such copy that reappears; it just had no live referent. -->
- Figure/table provenance can mix scopes (e.g. the legacy `pie_charts_summary.svg`
  mixed "all 6,040 units" panels with "stable-only" panels without labeling the
  difference; see the revised version and its provenance note for the explicit-criteria
  fix). Verify the denominator/scope per panel before citing counts.

Critical handouts:
- **`context/docs/CONTEXT.md` — read this first.** Authoritative merged project context as of
  2026-07-28: paradigm, corpus, data topology, area/channel/layer model, analysis contracts,
  statistical doctrine, current findings with receipts, and a **retraction list of numbers that
  were previously circulated as "protected invariants" but are hardcoded literals no script
  computes**. It supersedes the three 2026-07-27 handouts, which are preserved unedited under
  `context/archive/superseded-2026-07-27/`.
- `legacy/context/07_authoritative_data_topology_single_units.md`
  (data topology, NWB event model, condition groups — pre-dates the three-subject corpus)
- `legacy/context/08_pie_charts_summary_provenance.md`
  (figure provenance and legacy-vs-revised criteria for summary pie charts)

<!-- Path corrections 2026-07-28: the two handouts above were listed under `context/info/`, which
     does not exist — they live under `legacy/context/`. The unit database, layer masks, and the
     two notebook handouts were also listed at paths that no longer resolve, and have been
     repointed above. All six were verified on disk. Registries that point at files go stale
     silently; re-resolve these before trusting them. -->

## Placeholder/dummy figures must be red-flagged in the render itself

**Standing rule, set 2026-08-06.** Any figure (main or supplement) that contains placeholder,
synthetic, or fallback content instead of a real computed result must render an unmissable red
title reading **"PLACEHOLDER-DUMMY"** directly on the figure — in addition to, not instead of,
its normal title. This applies per-panel or per-figure depending on scope: if any panel in an
assembled figure uses non-real data, the whole assembled figure gets the flag, since a figure
with even one fabricated panel cannot be presented as trustworthy without one.

This is a concrete enforcement mechanism for the existing "no silent synthetic science" rule
(global `CLAUDE.md`): the failure mode it closes is a script with a real-data code path AND a
synthetic-fallback code path (`if csv.exists(): ... else: <hardcoded numbers>`), where the
fallback silently produces a plausible-looking figure with no visual indication anything is
wrong. `context/figures/fig04_omission_identity_decoding/fig04_omission_identity_decoding.py`
is the reference implementation: a `used_placeholder` flag set `True` by every fallback branch
(including panels with NO real-data path at all — a plain `if` isn't enough, some panels there
are unconditionally hardcoded), checked once before `savefig()` to add the red title via
`fig.text(...)`. Copy this pattern into any other script that has a synthetic-fallback path.

## Numerical stack — four array backends, one dispatch pattern

This repo is not numpy-only. Measured 2026-08-08 across `jnwb/` and `scripts/`:
**numpy** (86 import sites) · **torch** (`analyzers`, `gpu_pca`, `nam`, `trajectory`, `jrsa`) ·
**cupy** (`analyzers`, `connectivity`, `spectral`, `jrsa`) · **jax/jnp** (`jrsa` only).
CUDA is live here (torch 2.12.0+cu126, `torch.cuda.is_available() → True`).

**New GPU code follows `jnwb/jrsa.py`'s dispatch — `_get_backend` / `_autodetect_backend` /
`_to_backend` / `_get_xp`, with a `backend="auto"` parameter — and never a bare `import cupy`
at module top level.** That is the house pattern; `jnwb/spectral.py` predates it and has a
`cupy` path with no CPU fallback, so it is not the one to copy.

**Every GPU path needs a working CPU path**, because GPU availability is not a property of the
repo. `jnwb/gpu_pca.py` shows the minimal correct shape: try the accelerated path, fall back,
and report which one ran.

Backends are optional extras (`pip install -e ".[gpu]"` / `".[torch]"`), so import them inside
the function that uses them, never at module scope — a top-level `import cupy` makes the whole
module unimportable on a CPU-only machine.

Details, including seeding across all four backends and the float32 precision trap:
`.claude/skills/numerical-computing/SKILL.md`.

## Band definitions — settled, do not re-drift

theta 4–8, alpha 8–14, beta 14–30, low gamma 30–50, high gamma 50–80 Hz.

This set is the resolution of a documented drift: earlier material used alpha 8–12 and theta 3–8
(or 2–7), and the 2026-07-27 figure audit fixed captions and methods onto the set above. Every
fitted coefficient in `outputs/lfp_band_census_v2/` uses it. A figure legend showing alpha 8–12 /
theta 2–7 / gamma-low 32–80 / gamma-high 80+ is pre-correction, not the house standard. Changing
the set means refitting everything downstream.

## Verification checks that caught real errors on this corpus

Each of these found a defect that had survived earlier review. Run them before trusting a
result, not after a reviewer asks.

**Average in the right order, and take the logarithm last.** A decibel change can be formed
several ways and they are not equivalent. Averaging decibels subtracts a quantity proportional
to the variance of the log, so a noisier session or animal is pushed downward relative to a
quieter one at identical mean power. Measured here the bias runs from −0.17 dB to −1.98 dB
across animals and was large enough to reverse an animal's sign. Averaging ratios biases the
other way. Average power over trials, divide by the baseline, then take `10·log10` once.
Receipt: `artifacts/.lab/db_averaging_bias_finding_20260728.json`.

**Check whether a test is one- or two-sided before reporting an absence.** The unit classifier
here is one-sided: 3,457 of 6,655 units have a negative omission effect and not one reaches
p = 0.05. No suppressed unit could ever be found, so "no O− units" was a property of the test.

**Apply the denominator before claiming enrichment.** Raw counts follow recording effort. PFC
had the most omission units and the most units screened, 1,342 against V1's 628; normalised it
sat below V1. A frontal gradient that is significant at one FDR threshold can vanish at a
stricter one when the area carrying it drops out.

**Check whether a selection criterion contains the conclusion.** The O++ set was 100 percent
frontal because its definition required FEF or PFC membership. Removing only that requirement,
28.9 percent of qualifying units were frontal, below the parent pool's own 32.9 percent.

**Check whether a column is constant before interpreting it.** All 6,655 screened units carry
`layer = Superficial`. Any laminar statement drawn from that field describes a default.

**Count the sessions behind a result, not just the units.** At q ≤ 0.01 all 45 surviving units
came from 2 of 15 sessions, and all 81 units of another cut from a single session. With session
as the unit of inference that supports nothing.

**Coverage being high enough is not the same as coverage being balanced.** vFLIP labels 58
percent of channels, above any reasonable floor, but the rate differs by animal
(Kruskal-Wallis H = 12.80, P = 0.0017) and about threefold by area. Since animal is the
dominant term for band power, a pooled laminar coefficient would carry an animal difference
inside it. Balance, not level, is the criterion.

**Verify a design is disconnected before declaring effects unidentifiable.** "No area was
recorded in all three animals" was true, but every area had at least two and V4 had three, so
the area-by-animal graph is connected and additive effects are jointly identifiable. Resolve
the graph rather than inferring from the marginal counts.

**Reconcile every count against its source table.** Four passes on this corpus report four
different O+ counts (386, 19, 7, and a retracted 421). Before quoting one, confirm which
script produced it and under which criteria.

**A field with the same name in two tables is not the same field until checked.**
`grand_stable_firing_rates.csv` carries its own `quality` column, separate from the one in
`omission_grand_units.csv`, and the two disagree on 1,942 of 6,650 shared units (29%).
`outputs/layers/unit_layers.csv` agrees with the grand table's `quality` on every one of those —
the stable-rates table's copy looks stale relative to a later re-sort. Found while building the
fig03 presence panel (2026-07-29); resolved by trusting the grand table's field for SUA/MUA and
using the stable-rates table only for its own primary output, `stable_trials_keep_fraction`.
Before joining any two tables on a same-named column, diff it on the overlap first.
