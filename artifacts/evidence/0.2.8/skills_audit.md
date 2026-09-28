# Skills and roles against the review checks: audit

Read-only critic audit, 2026-09-28, at `ac08e973`. The subject is how jnwb's nine skills and six
agent roles meet the code-and-math, figure and prose checks that Hamm's personal review skills
carry. What follows is the plan's evidence. Hamm's rulings on it are in
`artifacts/rulings/2026-09-28.md`.

Baseline: 207 passed and 1 skipped across the 10 skill, figure-form and docs-form test modules.
`harness_gate.py` had 21 PASS. `docs_form_gate.py` had 5 of 5 PASS.
`measure_agents_md_duplication.py` found 224 claim sentences: 0 duplicated and 3 echoed.

## Where each rule can go

Two constraints decide where every rule can go.

- `artifacts/direction.md` Surface and `CONTRIBUTING.md` bar skills from restating mathematics or
  implementation internals. Code and notation checks therefore go to a review surface, not to
  domain skills.
- The role files are vendor-neutral, and the personal skills exist on one machine only. The checks
  are copied into the repository in its own words, and no repository file names a personal skill.

| Source | Transfers | Stays out, and why |
|---|---|---|
| Prose checks | Keeping expression and proposition apart; a freeze list (code, paths, identifiers, numbers, units, citations and defined terms stay byte-exact); a semantic lock before an edit and an audit after it; the drift order (certainty, scope, causation, time, quantities, operators, modality, attribution); a slop lexicon as a docs-form rule; the delete-test; fact and number recompute; reference support as a review item | Voice profile, style script, register and sign-off, which are personal; the verdict format, which would be a second return contract; the em-dash and bold ban (ruled: no rule) |
| Code and math checks | Named constants with unit and source; log-domain numerics; float64 unless justified; tolerances justified, never loosened; stats reporting (test, sidedness, n, correction, interval); dimensions, limiting cases and sign conventions; equation-to-code correspondence | "Stop after three failed repairs", which contradicts `AGENTS.md` §12; gradients and ODEs, which no operation uses; LaTeX, TikZ and JS |
| Figure checks | A figure is verified only from its render at final size; text-overlap and outside-figure probes; units on every axis and colorbar; colorblind-safe perceptual colormaps with diverging maps centred on zero; minimum font size; true minus sign | Personal tooling and slide rubrics; renderers not known to be available on CI |

## Gaps

| Where | Gap | Edit |
|---|---|---|
| `jnwb-figures` | No render-and-inspect step; "visual QC" reads as figure checking but routes `jnwb.visual_qc` unit plots; the `raster_psth` row is also in `jnwb-spiking` | Add a verification line; rename the trigger to Matplotlib and unit-quality plots; keep one row, in spiking |
| `jnwb-landmark-viz` | The layout sentence and a checks bullet both ask for no overlap and give no method; "300/600 DPI PNG" is false, because one PNG is written at `png_dpi`, default 300 (`jnwb/vis/canvas.py:318`) | Merge the two into one inspect-the-PNG check; correct the DPI sentence |
| `jnwb-statistics` | No reporting line | A reported p names test, sidedness, n and correction; an effect names its interval |
| `jnwb-nwb-data` | Names 2 of the 3 MCP tools | Add `prepare_signal_reference` |
| `jnwb` router | No route for checking a figure; refusals not linked | Route through 07-11; link `docs/errors.md` and tutorial 00 |
| `artifacts/agents/authority.md` | Keeps its own loading order, without direction, goal, state or problem | Point to `AGENTS.md` §3 |
| Role files | Five each list a private subset of packet fields; `BASELINE COMMIT` appears in none | Say "the §5 packet", then the role's own additions |
| `critic.md`, `verifier.md`, `docs-harness.md`, fact-action V | No per-artifact checks; docs-harness says "seven domain skills" and "100%" | Point each to the review skill; delete the count and both "100%" |
| `.claude/agents/` | No verifier dispatch file | Add `jnwb-verifier.md` as a thin router |

## Friction, measured

| # | Friction | Count |
|---|---|---|
| 1 | Modules no skill references | 8 of 48: `bilinear`, `gpu_pca`, `nam`, `mcp_server`, `mcp_server.server`, `testing`, `testing.nwb_fixtures`, `testing.synth` |
| 2 | Exports no skill names | 26 of 162 (matches `artifacts/evidence/0.2.7/package_inventory.md`) |
| 3 | Docs pages no skill links | 20 of 33. 14 have a domain home; 6 are justified exclusions |
| 4 | Examples and notebooks no skill names | 12 of 12 |
| 5 | Stale claims the tests do not cover | 4: the MCP tool count, the DPI sentence, `docs/agents.md` giving unit QC to spiking, "seven domain skills" |
| 6 | Ambiguous triggers | 4: figures and landmark-viz overlap; `raster_psth` in two skills; "visual QC"; unit QC claimed twice |
| 7 | Safeguards in both `AGENTS.md` §4 and the router | 7 of 8 |
| 8 | Broken links | 0 |
| 9 | Line endings | 8 of 9 `SKILL.md` and 8 of 9 yaml files are CRLF, landmark-viz is LF; fact-action is CRLF |
| 10 | Slop lexicon hits | 0 in skills, docs and roles |
| 11 | Hardcoded skill counts | 2 |
| 12 | Accept lines naming a missing table | 07-10 and 07-11 name an `AGENTS.md` §7 row; §7 holds no table |
| 13 | Skill table with two homes | The router §2 and `docs/agents.md`, which already disagree |
| 14 | Wrong unit in a public default | `plot_csd` labels its colorbar "CSD (mV/mm²)". `current_source_density_1d` returns A/m³ and `voltage_curvature_1d` returns V/m², so the default is wrong for both |

## Acceptance for 0.2.8

These can be tests or gates:

- Every public module, export, docs page, example and notebook is named by the skill of its domain,
  or sits on an exclusion list whose reason a test checks.
- Every row binds to `inspect.signature`, `jnwb.vis` included.
- Every skill example executes.
- Each trigger phrase has one owning skill.
- The `docs/agents.md` table equals the skill directories and the router, and states no count.
- No broken links, and one line ending across `skills/`.
- No role file holds its own loading order or packet-field list, and every role in the loop has a
  dispatch file.
- Every generated docs figure passes the overlap, outside-figure and legend checks in both themes.
- The slop lexicon is zero in `docs/` and `skills/`.
- The review skill exists and every pointer to it resolves.

These are review only: a per-release eye-check of rendered figures; proposition preservation across
docs and skill edits, judged independently; each cited source supporting what jnwb attributes to it.

## Review checks (draft for the review skill)

| Artifact changed | Checks |
|---|---|
| Computation or test | Units and dimensions of every term; sign and orientation against the skill row; limiting cases (N=1, zero, one bin); float32 justified; tolerances justified, never loosened; each new test fails on its defect; constants named with unit and source |
| Figure | Rendered at final size in both page themes, every panel inspected; no clipped or overlapping text, no legend over data; every axis and colorbar gives quantity and unit matching the producing operation; colorblind-safe perceptual colormaps, diverging maps centred on zero; values trace to computed results; findings labelled observed or inferred |
| Docs or skill prose | Semantic lock before, audit after; frozen elements byte-exact; drift checked in order: certainty, scope, causation, quantities, operators and modality, attribution and tense; a word goes only when deleting it loses no proposition, boundary or load-bearing hedge |
| Citation | DOI shape and docstring agreement (test); registration and support with a locator (review); never add an unresolved reference |
