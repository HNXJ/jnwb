# CLAUDE.md — Omission

Claude Code entrypoint for this repo.

**Canonical project doctrine:** `.agents/AGENTS.md`  
**Global working agreement:** `C:\Users\nejath\.gemini\config\AGENTS.md`

Do not duplicate long doctrine here. If you need omission-specific paths, footguns, or PRP
triggers, read `.agents/AGENTS.md` first. Legacy notes in `legacy/markdowns/CLAUDE.md` are
historical — prefer live `artifacts/data/nwb_catalog.json` and `artifacts/data/session_readiness.csv`.
Note that `session_readiness.csv` lists 21 NWB-ready sessions while the TFR analysis corpus is
17 sessions; the two inventories overlap but neither contains the other.


---

## Labyrinth Reflex — every user turn reads and writes the graph

**Consult `artifacts/.lab/` before you answer; leave a delta in it before you finish.** The
default posture on every turn, including one-line prompts — not a ceremony reserved for big
tasks. Do not ask permission to do it.

Read first (recalled context is a hypothesis, the graph is the record) → write last (every
turn ends with a claim, status change, edge, or `notes[]`/`issues[]` append, or an explicit
"nothing worth recording" said out loud) → prefer edges and status changes over new nodes
(node-count growth without confirmed-claim growth is failure) → treat the user as a source,
not an oracle (user assertions enter at `unconfirmed`, the same bar a paper gets; a conflict
with a confirmed node is a `contradicts` edge you state plainly) → no receipt, no claim,
graph writes included.

Canonical wording: the "Labyrinth Reflex" section of `C:\Users\nejath\.gemini\config\AGENTS.md`.

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
- The repo also has downstream-audience handouts (`outputs/archive/notebooks/data_handout.md`,
  `outputs/archive/notebooks/colab_handout.md`) that restate the data topology for external/Colab
  runtimes. These are convenience copies, not the source of truth — if they conflict
  with the authoritative handout below, the authoritative one wins and the drift is
  worth flagging to the user.
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
