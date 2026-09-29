# 0.2.8

Opened 2026-09-29, after 0.2.7 was published. Items are deleted when done, never ticked; git,
`CHANGELOG.md` and the receipts hold history. The previous cycle's record is
`artifacts/archive/0.2.7/todo_stack_0.2.7.md`, with its closure receipt beside it;
`artifacts/evidence/0.2.8/plan/carry_map.md` says where every open item and bullet of it went.

Theme: the state files are compact, every documentation figure is correct, and the skills meet the
review checks with no friction.

Acceptance: `AGENTS.md` §11; every figure passes the checks of 08-02 in both themes; the skills
audit's acceptance list (`artifacts/evidence/0.2.8/skills_audit.md`) holds.

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet, in the contract of `artifacts/skills/jnwb-fact-action` §5; role `jnwb-developer` unless named | a batched packet redefines the hard item |
| A lane is one worktree and one writer; at most three lanes run at once; a lane's items run in the order listed | lanes never share a file, so they merge without conflict |
| A packet reproduces each bullet on its own tree first; a bullet that does not reproduce is deleted | non-reproduction is a result |
| The actor is never the verifier | every repair is re-run by someone else |
| The integrator owns the stacks, `CHANGELOG.md` and `docs/api.md` | packets report the disposition and the changelog text |
| Wave barrier: `python scripts/harness_gate.py` (count PASS lines), `python -m pytest tests/ -q`, commit, push, CI green on `dev` | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then `Do`, `Accept`, `Stop` as
needed. A bullet reads `ID: defect. Check: what closes it.` Bullets in a deferred cycle end with
`Waits:` and the reason it cannot make release evidence falsely pass.

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| A state and apparatus | 08-01, 08-05, 08-06, 08-07, 08-08 | `artifacts/` stack, rulings and evidence files, `AGENTS.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, release scripts, CI workflow |
| B figures | 08-02, 08-03, 08-04 | `docs/generate_figures.py`, figure assets, figure tests, the quickstart, the topic pages that show a figure except `docs/09` |
| C skills and roles | 07-30, 07-18, 07-13 | `skills/`, `artifacts/skills/`, `artifacts/agents/`, `docs/agents.md`, `docs/09`, `docs/common_mistakes.md`, `mkdocs.yml`, `jnwb/vis/canvas.py`, the docs-form gate |

### 08-01 The stack and state files in compact form

Release: required-0.2.8.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/todo_stack.md`, `artifacts/problem_stack.md`, `artifacts/planned_post_0.2.6.md`, `artifacts/archive/0.2.7/**`, `artifacts/rulings/*.md`, `artifacts/evidence/0.2.8/stack/**`, `artifacts/evidence/0.2.8/roadmap_proposal.md`.
Do: archive the 0.2.7 stack byte for byte to `artifacts/archive/0.2.7/`; land this draft as
`artifacts/todo_stack.md` in the file's current CRLF endings; carry the live residue of
`artifacts/planned_post_0.2.6.md` (the benchmark design) to `artifacts/evidence/0.2.8/stack/` and
delete that file; add `artifacts/rulings/standing.md`, one table of the rulings that still bind (`decisions.md`
D6, integrator 70); add P-36's lesson as
one sentence where order work is read.
- P-36: reading computational order off loop structure was wrong on six specs. Check: one sentence in the order section of `CONTRIBUTING.md`, reported to 08-06, which owns that file.
Accept: `python scripts/release_gate.py`'s stack readers and gates 15 and 17 pass on the landed
stack; every row of `carry_map.md` resolves to a live bullet or a stated drop.
Stop: a carried check would be lost by the compaction.

### 08-02 Mechanical figure checks, written to fail on today's figures

Release: required-0.2.8.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `tests/test_figure_form.py`, `tests/test_generated_figures_are_maintained.py`, `tests/test_synthetic_figures_are_labelled.py`.
Source: section 6 of the figure QC report (`artifacts/evidence/0.2.8/figure_qc.md`). Each check is built by a fixture of its own case and is red on the baseline
figure the report names.
- QC-1 theme contrast: each `THEMES[theme]` value against that theme's page background, at least 3 for data marks and 4.5 for text. Check: fig03 and fig08 `faint` fail.
- QC-2 rendered contrast: composite each PNG on its page background and bound the share of ink below 1.5, with a declared mesh exemption. Check: fig03 and fig08 fail; fig05's dark mesh floor is flagged for a decision.
- QC-3 text placement: every text and annotation bbox against lines, patches and other texts in its axes, and inside the canvas, the quickstart generator included. Check: fig08 and the quickstart permutation panel fail.
- QC-4 shared x: axes that share x have equal pixel x-extent. Check: fig05 fails.
- QC-5 axis units: every visible axis has a label, and a physical quantity carries a parenthesised unit. Check: fig04 and fig08 fail.
- QC-6 declared unit: a panel that plots a result declaring `unit` labels its axis with that unit. Check: the 0.2.7 fig09 label, planted, fails.
- QC-7 displayed size: minimum font times dpi/72 times displayed width over natural width is at least 9 px at the topic-page and gallery widths. Check: the quickstart captions fail.
- QC-8 one style source: every generator takes font family, size tiers and width from one module, checked by AST. Check: the serif quickstart and the 7.0/7.2/7.5 pt spread fail.
- QC-9 colormaps: `cmap=` values come from a perceptual set or a declared diverging map. Check: a planted `jet` fails.
- QC-10 computed values: every figure function calls a public `jnwb.` symbol, and no reference line sits at a bare literal unless listed as a theoretical constant. Check: fig08, fig01 `1000.0` and fig07 `0.5` fail.
- QC-11 captions: a `jnwb.<name>` in a panel title appears in the caption and in `jnwb.__all__`, and the synthetic-caption test reads `<img>` tags. Check: the gallery's fig03 "PSTH" caption fails.
- QC-12 fit on its grid: a fit drawn over a spectrum is evaluated on the drawn grid, with a bounded median log residual. Check: the 0.2.7 fig04 fit, planted, fails (+0.263 decades).
- P-241: the contrast check exempts `THEMES` and parses only 6-digit hex and four names. Check: QC-1 and QC-2 replace the exemption, and a named colour such as `navy` is parsed.
- P-276: the self-test does not pin the changed-pixel slack (1e-5). Check: raising it to 2e-4 fails a test.
- P-307: every venv and CI leg skips all 20 figure comparisons on a Matplotlib minor mismatch. Check: a pinned Matplotlib in one CI leg, or a comparison tolerant of the minor version, so one leg compares.
- Figure checks: the legend test compares texts only with its own axes' legend, tests scatter by centre, skips images, and misses the quickstart. Check: QC-3 covers each case with a fixture.
- Legend check reach: a `QuadMesh`, `ax.images`, a single-point scatter, marker extent, twin axes, `fig.legend` and annotation arrows are unseen. Check: each is a fixture case.
Accept: each check fails on the baseline figure its bullet names and passes on a clean fixture.
Stop: a check needs a renderer CI does not have.

### 08-03 Figure content defects

Release: required-0.2.8.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: 08-02.
Writes: `docs/generate_figures.py`, `docs/figure_style.py`, `docs/assets/figures/*.png`, `docs/index.md`, `docs/02_paths_addressing_metadata.md`, `docs/04_spectral_analysis_and_tfr.md`, `docs/05_artifact_detection_and_repair.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/07_statistical_inference_and_nulls.md`, `docs/08_directed_connectivity_and_information.md`.
Source: section 4 of the figure QC report. The three blocker rows (fig01 a, fig04 a, fig09 a)
landed in 0.2.7. `docs/09` belongs to
07-30; a fig07 sentence change on that page is reported there.
- fig01: gold and violet carry no key; the boundary is the retyped literal `1000.0`; V1 and V2 are adjacent blue-violets; V3 text is 2.45:1 on dark; panel A's right half is empty. Check: a two-entry key, `threshold=` passed and drawn from one variable, a distinguishable categorical triple, a tightened xlim.
- fig02: the shaded band is unlabelled SEM computed by hand; no onset marker in the raster; "Δ=15ms" and "tau=25ms" lack a space. Check: "±1 SEM" from `raster_psth`'s `sem_rate_hz`, `axvline(0)` in panel A, spaced units.
- fig03: raw points 1.32:1 on white; "Binned Rate (raw counts)" labels simulated Hz; the truth label omits tau 30 ms; the gallery caption says PSTH. Check: at least 3:1 in each theme, "Simulated noisy rate", `tau=30 ms` in the label, the caption corrected.
- fig04: the PSD axis has no unit. Check: "(a.u.²/Hz)".
- fig05: the colorbar narrows panel B so the time axes misalign; the COI outline does not say which side is excluded; magma's floor is 1.22:1 on dark. Check: equal colorbar slots or `constrained_layout`; the masked region hatched and named in the legend; the floor decided under QC-2.
- fig06: a 0.04 dB Jensen gap drawn as bars from 0 on a 0-5 axis; the axis label is redundant. Check: per-unit ratios with realistic spread, or differences from ratio-of-means with the dB values printed.
- fig07: the chance line is the literal 0.5 across AUC and F1; the mean line shares the bars' colour; the panel titles are misaligned. Check: chance scoped to AUC or F1 chance from the label prior; a contrasting mean line; one title height.
- fig08: the annotation is crossed by the observed line; the x axis has no unit and says "fire rate"; the null and p are retyped numpy; "Monte Carlo" and "Exact" in one label; the null fill is 1.32:1. Check: `jnwb.exact_sign_flip(diffs, alternative="greater", rng=...)`, the annotation left of the line, "one-sided Monte Carlo p", "Mean paired difference (Hz)".
- fig09: the net PSI band is unmarked while out-of-band points are drawn; no markers on seven points; `psi_freqs` recomputed. Check: the summed band shaded, markers, `psi.spectrum["psi_freqs"]`.
- fig10: "LFP (µV / a.u.)" reads as a ratio; the raw trace is called an envelope; the two channels are indistinguishable; 40 % of each axis is empty legend band. Check: "LFP (a.u.)", "Raw (contaminated)", one channel or an offset, a compact legend.
- Cross-figure style: sizes vary 7.0/7.2/7.5 pt, figsize 6.5 to 7.4 in, and gallery (311 px) and mobile (343 px) text is illegible and unlinked. Check: `docs/figure_style.py` sets family, size tiers and width; gallery images link to full size.
Accept: 08-02 passes; the QC probes re-run clean (fig04 median offset near 0, no text-line hits,
equal shared-x extents); `python scripts/docs_build.py` is strict-clean; each regenerated pair is
eye-checked in both themes at displayed size.
Stop: a fix would need a jnwb call whose output differs from the page's own text.

### 08-04 The quickstart figure

Release: required-0.2.8.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: 08-03.
Writes: `examples/quickstart_jnwb.py`, `examples/figures/*`, `docs/assets/jnwb_quickstart*.png`, `docs/quickstart.md`.
- Quickstart QC row: the refusal texts sit over the histogram and are crossed by the observed line; 6.4 pt captions show at about 5.6 px; serif font and a palette unlike fig01-fig10; band labels print "-0.0". Check: the refusal text above the bars or in the caption, captions sized by QC-7 or moved to the page, `docs/figure_style.py` shared, `+0.0` formatting.
- P-76: every quickstart run dirties two tracked files through SVG dates and random ids. Check: `rcParams["svg.hashsalt"]` and `metadata={"Date": None}`, and two runs byte-identical.
Accept: 08-02 passes on the quickstart; two consecutive runs leave `git status` clean.
Stop: none beyond the standing ones.

### 08-05 CHANGELOG fragments

Release: required-0.2.8.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `CHANGELOG.md`, `changelog.d/**`, `scripts/assemble_changelog.py`, `tests/test_changelog_fragments.py`.
- CHANGELOG fragments: one file per change under `changelog.d/`, assembled into `CHANGELOG.md` at release by a script with a test. Check: two parallel fragments merge without conflict, and the assembled text equals the hand-written form for one past release.
Accept: the test passes; the release gate's CHANGELOG checks still read the assembled file.
Stop: the assembly would change a released section's text.

### 08-06 `AGENTS.md` rules and routes only

Release: required-0.2.8.
AUTONOMY: none for the landing; the draft is `max`.
Role: jnwb-developer. Skill: none. Blocked by: 08-01.
Writes: `AGENTS.md`, `CONTRIBUTING.md`, `artifacts/rulings/history.md`, `artifacts/cooperation.md`, `tests/test_agents_md_recipes.py`, `tests/test_agents_md_stays_a_router.py`.
- A draft of about 1500 words (4403 at `fe14858d`): rules and routes only, reasons and incidents moved to `artifacts/rulings/history.md`. Check: Hamm approves the draft before it lands.
- The P-36 sentence reported by 08-01, and RP-1's release-step sentence (the `dev` deletion rule has no bypass; merged feature heads are still deleted).
Accept: `tests/test_agents_md_*.py` pass; every rule of the old file maps to a rule, a route or a
`history.md` paragraph in a table the packet returns.
Stop: a rule would change meaning.

### 08-07 A faster release cycle

Release: required-0.2.8.
Role: jnwb-developer. Skill: none. Blocked by: 08-05.
Writes: `scripts/release_gate.py`, `scripts/calibrate_xflip.py`, `.github/workflows/workflow.yml`, `tests/test_release_body_gate.py`, `tests/test_release_recovery_gates.py`, `tests/test_workflow_release_policy.py`, `tests/test_representative_workflow.py`, `tests/test_state_reconstruction.py`, `CONTRIBUTING.md`, `tests/test_docs_nwb_workflow.py`.
- RP-3: the release gate stops at its first failure after a 12 to 30 minute suite. Check: state freshness, the extracted smoke script and the release body run before the suite.
- RP-4: the full matrix ran four times on one commit at release. Check: skip a run whose tree already passed, and measure the saving.
- Load-sensitive workflow test: `test_full_workflow_runs_with_omission_blocked` timed out at 60 s under load. Check: a timeout scaled to the machine, or a cheaper subprocess.
- Load-sensitive state generation: `test_generation_is_deterministic_apart_from_its_timestamp` recorded the harness gate FAILED once under load. Check: the cause named and removed.
- Install line: `CONTRIBUTING.md` line 21 installs `.[test,docs]`, but `tests/test_docs_call_shapes.py` fails at collection without plotly (the `vis` extra); found by cowork on 2026-09-29. Check: the documented install runs the suite to collection.
- Absent-extra handling: `test_mkdocs_strict_build` fails without the `docs` extra while `test_diagrams_render` skips; found by cowork on 2026-09-29. Check: one rule for an absent extra, applied to both.
- xflip calibration wall time: 297 s to 503 s across lanes with identical rates. Check: dev and head back to back on one machine.
Accept: one release-gate run on a tree with a stale state file fails within a minute.
Stop: reordering would let a later step pass on an unverified artifact.

### 08-08 Proposals for the mutation and execution APIs

Release: required-0.2.8.
AUTONOMY: none for the choice; the proposal is `max`.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `artifacts/evidence/0.2.8/api_proposals/**`.
The minimal bases of 07-21 and 07-22, which `artifacts/goal.md` §5 names as 0.2.8 work; the
implementations follow the ruling in 0.2.11.
- 07-21 base: a proposed operation set (validate, write, transform, convert, structural repair, verified output) with signatures and refusals. Check: Hamm rules the set.
- 07-22 base: identity across CPU, parallel CPU and CUDA for every operation the execution API would cover, measured. Check: a table per operation, with the tolerance each function states.
Accept: both files exist and name every signature and every measured tolerance.
Stop: a proposal would infer condition meaning, anatomy or units.

### 07-30 Skills and roles carry the review checks

Release: required-0.2.8.
Role: jnwb-developer. Skill: per skill. Blocked by: none.
Writes: `artifacts/skills/**`, `artifacts/agents/*.md`, `skills/*/SKILL.md`, `skills/*/agents/*.yaml`, `docs/agents.md`, `docs/documentation_form.md`, `docs/09_decoding_and_visual_qc.md`, `docs/common_mistakes.md`, `mkdocs.yml`, `jnwb/vis/canvas.py`, `scripts/docs_form_gate.py`, `tests/test_docs_form_gate.py`, `tests/test_skills_validation.py`, `tests/test_skill_router_reach.py`.
Asked by Hamm on 2026-09-28. Evidence: `artifacts/evidence/0.2.8/skills_audit.md`; rulings
`artifacts/rulings/2026-09-28.md`. Its first review lane passed: the `skills/` line endings, the
trigger and table repair, and the verification lines are done. The figure-test step moved to 08-02
and the `AGENTS.md` §7 line to 08-06, so the lanes share no file. `.claude/` is git-ignored, so the
verifier dispatch file is a local step and not a tracked write. Ruled by the integrator (85): the
MCP tool count stays in `docs/agents.md`, because a test holds it to the live registry.
- `artifacts/skills/` line endings levelled, with Gate 16 held per tree (`decisions.md` D3).
- Landmark-viz checks: the layout sentence and its checks bullet become one inspect-the-PNG check, with a render-at-final-size line.
- One skill table: the router's table and `docs/agents.md` agree, held by a test. Check: the lfp-spectral, spiking and nwb-data rows, which differ today, are reconciled.
- Unit-quality wording: "Visual QC" becomes "unit-quality plots" in `docs/09_decoding_and_visual_qc.md`, its nav label and `docs/common_mistakes.md`, with any fig07 sentence 08-03 reports.
- Router-reach parser: `_routed_operations` reads every backticked call in a bullet; the parser fixture in `tests/test_skill_router_reach.py` is renamed; the skill-count regex refuses "Nine shipped skills". Check: a planted count and a two-call bullet each caught.
- `jnwb/vis/canvas.py:16`: the docstring says "300/600 DPI" where one PNG is written at `png_dpi`. Check: the docstring names `png_dpi`.
- Docs form F8: the slop lexicon, zero in `docs/` and `skills/`, with a planted case caught.
- 07-10 and 07-11 accept on the `docs/agents.md` row; public text names checks, never roles.
Accept: each trigger phrase has one owning skill; no role file holds a loading order or packet
list; every pointer to the review skill resolves; the F8 check passes; an independent critic finds
none of the frictions the audit lists.
Stop: a skill edit would restate mathematics `artifacts/direction.md` keeps out of skills, or put
personal voice or process vocabulary in `skills/` or `docs/`.

### 07-18 Skill examples run in the suite

Release: required-0.2.8.
Role: jnwb-developer. Skill: per skill. Blocked by: 07-30.
Writes: `skills/*/SKILL.md`, `tests/test_skill_examples_execute.py`.
Seven of nine example blocks executed at `dcb75f12`; six skills build inputs from a random
generator.
Accept: every example block executes in the suite and declares its input class (real NWB,
deterministic array, stochastic synthetic, calibration fixture); the test checks the declaration;
a routing example uses one of the first two.
Stop: an example needs data the repository does not carry.

### 07-13 Skills say each thing once

Release: required-0.2.8.
Role: jnwb-developer. Skill: per skill. Blocked by: 07-18.
Writes: `skills/*/SKILL.md`, `tests/test_skills_validation.py`.
Three normalised lines of 40 or more characters are shared by two skills at `dcb75f12`, and 7 of
the 8 safeguards sit in both `AGENTS.md` §4 and the router. The test lands before 07-10 and 07-11,
so the new skills are born under it.
Accept: a test fails when a normalised invariant line appears in two skills, `docs/` links
excluded; a restated `docs/` definition becomes the link; the summed length of the skills does not
grow.
Stop: removing a restatement leaves a routing row without a dimension its operation requires.

### 08-09 The fact stack as typed tables, with the ontology gate

Release: required-0.2.8.
AUTONOMY: none for the landing of `artifacts/fact_stack.md`; the draft is `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/fact_stack.md`, `scripts/build_ontology.py`, `scripts/ontology_gate.py`, `tests/test_ontology_gate.py`, `.gitignore`.
Ruled 2026-09-29 (quiz Q1 to Q19, `artifacts/rulings/2026-09-29.md`).
- The fact stack as six tables of typed predicate rows with their constant tables, drafted from today's facts and `AGENTS.md` §4 with no change of meaning. Check: Hamm approves the draft; a map from every old clause to a row is returned.
Accept: the gate runs in the harness with 0 VIOLATED; each UNHELD fact names the item that holds it.
Stop: a fact's meaning would change in the rewrite.

# 0.2.9

Theme: the skill set is complete and routes every export, and the documentation menu follows how a
reader arrives.

Acceptance: `AGENTS.md` §11; every export, module, docs page, example and notebook is routed or
excluded with a checked reason; the nav matches the arrival table of `restructure_plan.md` (c).

Every item here carries `deferred-0.2.9`, the one deferred value `scripts/release_gate.py` accepts
while 0.2.8 is released; the version heading carries the schedule (`decisions.md` D2).

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| C skills | 07-10, 07-11, 07-12, 07-08, 07-09 | `skills/`, skill tests, composition tests, `docs/agents.md` |
| D docs | 09-01, 09-02, 09-03 | `mkdocs.yml`, every other `docs/*.md`, docs tests, `scripts/docs_form_gate.py`, `scripts/docs_build.py` |

### 07-10 `jnwb-paradigm`: experiment structure, timing and condition semantics

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `skills/jnwb-paradigm/SKILL.md`, `skills/jnwb-paradigm/agents/openai.yaml`, `skills/jnwb/SKILL.md`, `skills/jnwb-nwb-data/SKILL.md`, `tests/test_skills_validation.py`, `tests/test_skill_decline_behaviour.py`, `tests/test_skill_router_reach.py`, `docs/agents.md`.
Routes `events`, `EventTable`, `resolve_interval_table`, `EpochCollection`, `epoch_continuous`,
`detect_trial_cycles`. Condition meaning comes from explicit metadata first and structural
inference last; an undocumented code is reported, never named.
Accept: the `CONTRIBUTING.md` template and all four outcomes, with an undocumented condition code as
the decline case; each row it takes leaves `jnwb-nwb-data`; its router and `docs/agents.md` rows
exist; gates 2 and 6 pass.
Stop: the capability gate of the fact stack is not met; a condition vocabulary would enter the skill.
Waits: new skill; no shipped behaviour changes.

### 07-11 `jnwb-qc`: independent scientific and output QC

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: 07-10.
Writes: `skills/jnwb-qc/SKILL.md`, `skills/jnwb-qc/agents/openai.yaml`, `skills/jnwb/SKILL.md`, `skills/jnwb-figures/SKILL.md`, `skills/jnwb-nwb-data/SKILL.md`, `tests/test_skills_validation.py`, `tests/test_skill_decline_behaviour.py`, `tests/test_skill_router_reach.py`, `docs/agents.md`.
`visual_qc`, `audit_units`, `audit_electrodes`, `Result`, `Provenance` and `Lineage` each get one
routing row, here only, so the skill that draws a figure is not the one that judges it.
Accept: the template and all four outcomes; its router and `docs/agents.md` rows; gate 2 passes.
Stop: the capability gate of the fact stack is not met.
Waits: new skill; no shipped behaviour changes.

### 07-12 Every export routed or excluded with a checked reason

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: per skill. Blocked by: 07-11.
Writes: `skills/*/SKILL.md`, `tests/test_skill_symbol_coverage.py`, `tests/test_skills_validation.py`.
Measured at `ac08e973`: 26 of 162 exports and 8 of 48 modules named by no skill
(`artifacts/evidence/0.2.7/package_inventory.md`).
- IB-61: the coverage test excludes `PopulationAnalyzer`, `TFRAnalyzer` and `UnitAnalyzer` as facades, but they compute on their own, and the router's GPU table names two methods with no row. Check: routing rows, or de-export by ruling (`decisions.md` D8), then a reason the test verifies.
- IB-63: `jnwb-landmark-viz` routes by module, so no signature check covers its rows. Check: per-function rows checked against `inspect.signature` when plotly is installed.
- P-267: no skill routes `jnwb.ontology`, and the exclusion comment points to a workflow no skill has. Check: rows in 07-11's skill, or a checked exclusion.
- P-279: the tuple check counts elements only, so a swapped return order survives it. Check: element names or types compared.
- Exports and modules outside the routing: the inventory's 26 exports and 43 modules with names outside `__all__`. Check: Hamm rules each group (`decisions.md` D8).
Accept: the excluded set is smaller than at `dcb75f12` and each remaining reason is checked.
Stop: a row would restate a definition that belongs in `docs/`.
Waits: routing completeness; a stale row raises loudly and no value is wrong.

### 07-08 The router composes the minimal skill set a task needs

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb. Blocked by: 07-12.
Writes: `skills/jnwb/SKILL.md`, `skills/jnwb/agents/openai.yaml`, `tests/test_skill_router_reach.py`.
Router section 2 maps each task phrase to one skill, so a multi-skill task reaches the first match.
Accept: a table of tasks and required skill sets passes, with plotting supplied arrays reaching
figures and QC, and a band comparison between conditions reaching paradigm, NWB data, spectral,
statistics, figures and QC.
Stop: a task needs a skill outside the fact stack's planned set.
Waits: router feature; no shipped behaviour changes.

### 07-09 Composition tests over the chains the router sequences

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: per chain. Blocked by: 07-08.
Writes: `tests/test_composition_*.py`.
No test composes two skills' operations in router order where each call is right and the order,
an identifier or a substituted signal class is wrong. Minimal base: the band-comparison task as one
chain.
Accept: each chain runs on unequal dimensions, fails on the wrong composition and passes on the
right one; a chain correct today records its killing mutation in its docstring.
Stop: a chain is wrong today and its repair needs a path outside `Writes`.
Waits: new tests of new composition.

### 09-01 The menu by how a reader arrives

Release: deferred-0.2.9.
Role: docs-harness. Skill: none. Blocked by: none.
Writes: `mkdocs.yml`, `docs/index.md`, `docs/architecture.md`, `docs/01_architecture_and_philosophy.md`, `docs/02_paths_addressing_metadata.md`, `docs/04_spectral_analysis_and_tfr.md`, `docs/reading_nwb.md`, `docs/coherence_and_tfr.md`, `docs/documentation_form.md`, `docs/tutorials/*.md`, `tests/test_docs_user_navigation.py`, `tests/test_documentation_form.py`, `tests/test_docs_links.py`.
Plan: `restructure_plan.md` (c). Topic filenames stay, so skill links hold.
- Nav regrouped into Start, Analyse, Tutorials, Use with an agent, Fix a problem, Look up, Design.
- `01_architecture_and_philosophy.md` merged into `architecture.md` with nothing lost; the module map kept.
- `02` split: paths and streaming move to `reading_nwb.md`; addressing and metadata stay.
- `04` split: coherence and TFR move to `coherence_and_tfr.md`; PSD and decibels stay.
- P-269: the magnitude, direction, delay and inference distinctions as one table in `architecture.md`.
- P-277: the reachability test misses an agent named in an edge label, "Assistant", "LLM" and "requires an LLM agent", and fails a legitimate `subgraph`. Check: each is a fixture.
- P-278: the routing diagram asks "inference supported?" before "inputs present?", and the dependency diagram omits six libraries. Check: the order that `artifacts/direction.md` implies, and the full list.
Accept: N1 to N5 pass; every page under its ceiling or tabled; no page's facts lost, by a
before-and-after claim table.
Stop: a merge would drop a fact another page does not hold.
Waits: presentation; no shipped behaviour changes.

### 09-02 Documentation statements

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: per finding. Blocked by: 09-01.
Writes: `README.md`, `docs/common_mistakes.md`, `docs/02_paths_addressing_metadata.md`, `docs/reading_nwb.md`, `docs/03_representational_similarity_jrsa.md`, `docs/08_directed_connectivity_and_information.md`, `docs/install.md`, `docs/quickstart.md`, `examples/tutorials/09_open_data.py`, `tests/test_open_data_example.py`, `tests/test_docs_operation_statements.py`, `tests/test_docs_interpretation_statements.py`.
- P-20: no page shows the unit-to-layer composition. Check: one worked composition on the addressing page.
- P-280: minor text (open-data "within a millisecond" is 6-9 ms; `plot_decoding_timecourse`'s promised ribbon; `rdm_similarity` Step 5 and the wPLI threshold only in docstrings; `correlate`'s `test=`; the quickstart's "single trial"; `population_trajectory`'s short context name). Check: each corrected where a reader sees it.
- P-317: the page says a stored entry is seeked past; on 3.12.0 it is read forward. Check: the page states the 3.12.0 exception.
- P-349 docs half: the `starting_time` alignment patterns in README and common mistakes raise `TypeError` for a series stored with timestamps. Check: a pattern that works for both, run by a test.
- P-341: the docs/03 direction table, the docs/03 loop that replaces `sliding=True` and the docs/08 transfer-entropy source window have no test. Check: a test each, with the `t-u-l` mutant killed.
- P-199: nothing pins the three-segment tick-rate check of the open-data example. Check: a test kills the window-only mutant.
- P-259: rule F7 conflicts with "no fact present before is absent after". Check: the precedence Hamm rules (`decisions.md` D9) written into `docs/documentation_form.md`.
Accept: each bullet's check passes.
Stop: a statement fix changes a documented value.
Waits: wording; no value or contract changes.

### 09-03 One copy of each documentation check

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: none. Blocked by: 09-02.
Writes: `scripts/docs_form_gate.py`, `scripts/docs_build.py`, `tests/test_documentation_form.py`, `tests/test_docs_form_gate.py`, `tests/test_figure_form.py`, `tests/test_docs_user_navigation.py`, `tests/test_docs_call_shapes.py`, `tests/test_docs_smoke.py`.
- P-282: F1, F5, N1, N2, N5 and G2 are asserted twice, and the gate imports private helpers from two test modules. Check: one copy in the gate, the tests call it, and the old F1 `#####` gap is covered once.
- P-288: the gate leaves `docs/tutorials/*.md` outside F1, F5 and F2 and misses an indented `####`. Check: both read.
- Nav check edges: a commented wheel flag passes; `exclude_docs` compared literally; an external nav URL ending `.md` reads dead. Check: comments dropped, gitignore matching, URLs skipped.
- P-01: `scripts/docs_build.py` writes `site/` into the tree, and the suite creates `site/` mid-run. Check: the build writes to a temporary directory and the suite leaves no `site/`.
- IB-56: the quickstart smoke fixture seeds its own generator, so its arrays differ from the page's. Check: the fixture executes the page's setup lines.
- P-84: the call-shape check's code half is landed; P-167's record correction and the type oracle remain. Check: merged with P-167.
- P-167: P-79b, P-79c and P-82 are wrong-type calls that bind cleanly. Check: a type oracle for documented call shapes (06-110) fails each.
Accept: the gate and tests share one implementation per rule; the suite leaves the tree clean.
Stop: merging would drop a case one copy catches.
Waits: both copies must pass today, so nothing passes falsely.

### 09-04 Science and Skills facts held

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: none. Blocked by: 08-09.
Writes: `scripts/ontology_gate.py`, `tests/test_ontology_gate.py`.
- S8 claim classes and the text check over docs, skills, figure labels and docstrings. Check: the 0.2.7 fig09 unit, planted, is VIOLATED.
- S1, S2, S5 and S7 scans as ruled in Q13. Check: each catches its planted case.
- K1 partition with k = 3 exclusive operations per shipped domain skill; the planned-skill list moves here as plan. Check: a two-operation planted skill is VIOLATED.
Accept: the Science and Skills tables report no UNHELD fact.
Stop: a scan would need a scientific criterion not ruled in Q12 or Q13.

# 0.2.10

Theme: oversized modules become small packages behind the same public API, and the scientific
edges in them are closed.

Acceptance: `AGENTS.md` §11; `jnwb.__all__` and every public signature identical to 0.2.9;
gate 19 entries re-pointed with unchanged hashes; each estimator change carries a calibration
record in `artifacts/evidence/0.2.10/`.

Every item here carries `deferred-0.2.9` until 0.2.9 is tagged (`decisions.md` D2).

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| A preparation | 10-01 | the shared tests that hard-code module paths, `scripts/mutation_harness.py` |
| F spectral and laminar | 10-02, 10-03, 10-04 | `jnwb/spectral*`, `jnwb/tfr*`, `jnwb/laminar*`, their tests, the calibration scripts, `docs/laminar.md` |
| G connectivity and similarity | 10-05, 10-06 | `jnwb/connectivity*`, `jnwb/jrsa*`, `jnwb/rsa.py`, their tests |
| H statistics, spiking, decoding, display | 10-07, 10-08, 10-09 | `jnwb/statistics*`, `jnwb/spiking.py`, `jnwb/onset_fitting.py`, `jnwb/analyzers.py`, `jnwb/trajectory.py`, `jnwb/gpu_pca.py`, `jnwb/bilinear.py`, `jnwb/nam.py`, `jnwb/artifact_repair.py`, `jnwb/_spread.py`, `jnwb/_bins.py`, `jnwb/_dictlike.py`, `jnwb/viz.py`, `jnwb/vis/**`, `jnwb/visual_qc.py`, `jnwb/testing/**` |

10-01 runs alone first; F, G and H then run at once.

### 10-01 Tests find module files by import, not by path

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `tests/test_semantic_mutation_classes.py`, `tests/test_claim_wording.py`, `tests/test_estimator_values_are_pinned.py`, `tests/test_module_docstrings_match_their_code.py`, `tests/test_mutation_harness_validity.py`, `scripts/mutation_harness.py`.
Measured at `fe14858d`: these files name `jnwb/spectral.py`, `jnwb/connectivity.py`,
`jnwb/laminar.py`, `jnwb/statistics.py` or `jnwb/jrsa.py` as paths, so every split would edit them
and the three split lanes would share files.
- Path derivation: each target is `inspect.getsourcefile(<public object>)`. Check: moving a function to a new file changes none of these files.
- P-305: `tests/test_semantic_mutation_classes.py` fails on any uncommitted byte change to its targets, so a mutation oracle must deselect it, and CUDA agreement tests kill device mutants only on a GPU. Check: the recipe states both in the harness docstring.
Accept: the full suite passes and a scratch move of one function needs no edit here.
Stop: a path is a machine-required literal of a fixture.
Waits: no shipped behaviour changes.

### 10-02 `spectral` and `laminar` as packages

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: 10-01.
Writes: `jnwb/spectral.py`, `jnwb/spectral/**`, `jnwb/laminar.py`, `jnwb/laminar/**`, `tests/test_spectral.py`, `tests/test_laminar.py`, `tests/test_xflip.py`.
Split per `restructure_plan.md` (a). Pure moves; the package `__init__` re-exports every name the
old module bound, and public classes keep their old `__module__` (`decisions.md` D5).
Accept: `jnwb.__all__`, signatures and `jnwb.spectral.<name>` / `jnwb.laminar.<name>` lookups
identical; the full suite and gate 19 pass.
Stop: a move changes a number.
Waits: layout only.

### 10-03 Spectral edges

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: 10-02.
Writes: `jnwb/spectral/**`, `jnwb/tfr.py`, `jnwb/tfr_accumulator.py`, `tests/test_spectral.py`, `tests/test_tfr*.py`, `tests/test_gpu*.py`, `skills/jnwb-lfp-spectral/SKILL.md`, `docs/04_spectral_analysis_and_tfr.md`, `docs/coherence_and_tfr.md`.
- P-203: `relative_power(model="log_ratio")` retypes `10*log10`. Check: it calls `to_db`. Waits: same formula.
- P-230: `aperiodic_fit` fits without removing peaks (graded keep, 2026-09-25). Check: an opt-in `remove_peaks=`, default unchanged. Waits: documented.
- P-340: `compute_psd` and `compute_multitaper_psd` return 1e-33 residue for a constant trace. Check: exact zero or the residue documented. Waits: no positivity guard to mislead.
- P-349 device half: CPU and CUDA `wpli` differ for a channel one ulp from constant. Check: parity below working precision declared undefined. Waits: one-ulp edge.
- P-331 coherence half: the coherence residual-variance guard sees detrend residue. Check: a stated tolerance. Waits: degenerate input.
- P-171: the density test's name promises what `test_band_power_is_the_mean_psd_over_the_band` catches. Check: rename. Waits: name only.
- IB-60: the coherence GPU-fallback test compares only p and spectrum. Check: the shift list equals the CPU run's. Waits: the numbers invariant 6 protects are equal.
- P-257: `ComplexTFR(device=...)` accepts any string. Check: a checked device. Waits: only a hand-built `ComplexTFR`.
- P-347: `TFRAccumulator.mean` returns a copy. Check: the docstring and a test. Waits: stated; no user.
- P-287: the trial-mean view check reads one level deep. Check: nested lists and memoryviews refused or copied under the ruled limit. Waits: copies under the ruled limit.
- Deprecations to complete: `spectral_tilt`'s `exponent` key is removed, and `relative_power` raises `ValueError` for a lower-dimension baseline. Check: both land with a CHANGELOG entry. Waits: ruled to land one release after the warning.
- Generator seeds and `jrsa` axes, spectral part: `cross_area_coherence` records no seed for a `Generator`. Check: a child seed recorded.
Accept: each check passes and the suite is green.
Stop: a change moves a documented value without a ruling.

### 10-04 Laminar edges and a laminar page

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: 10-03.
Writes: `jnwb/laminar/**`, `scripts/calibrate_vflip.py`, `scripts/calibrate_xflip.py`, `tests/test_laminar.py`, `tests/test_xflip.py`, `tests/test_zflip*.py`, `docs/laminar.md`, `mkdocs.yml`.
- P-228: `vflip` shares its name with a different published procedure. Check: the choice of `decisions.md` D7. Waits: rename is a public API ruling.
- P-229: the vflip receipt hashes docstrings. Check: hash code without docstrings. Waits: fails closed.
- P-285: the xflip receipt hashes comments. Check: the same hash rule. Waits: fails closed.
- P-351: `vflip` reports `log(max(1e-12, metric))`, so no support reads as -27.63. Check: -inf or NaN with the reason. Waits: rejected at the 3.75 gate.
- P-353 vflip half: a caller threshold at or below -27.63 accepts a zero-support fit. Check: closed by P-351. Waits: the default is 3.75.
- Depth declaration guard: `vflip` accepts a non-monotone `depth_axis`. Check: a criterion Hamm rules (`decisions.md` D10), the staggered shaft as the test. Waits: what counts as a depth axis is a scientific choice.
- Zflip long ramps: one flat contact makes every pair unidentifiable; the zero-gradient guard is unreachable; the fewer-than-3-bins docs check runs at `n_surrogates=0`; long cumsum ramps exceed the ramp width. Check: untouched pairs draw their own nulls (IB-99's 0.2.8 note), the guard removed or tested, the docs check run with surrogates, a ramp rule that keeps the offset signal. Waits: at defaults the `min_wpli` gate and the pair test refuse first.
- Tie-width test reach, vflip part: `scripts/calibrate_vflip.py` hashes a single module. Check: the receipt walks every module the estimator reaches.
- Generator seeds and `jrsa` axes, laminar part: `xflip` and `zflip` record no seed for a `Generator`. Check: a child seed recorded.
- 06-97 residue: no topic page documents the laminar operations. Check: `docs/laminar.md` with one call site each for `vflip`, `xflip`, `zflip` and `label_layers`, on the nav.
Accept: each check passes; calibration records regenerated.
Stop: a criterion is a scientific choice with no ruling.

### 10-05 `connectivity` and `jrsa` as packages

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: 10-01.
Writes: `jnwb/connectivity.py`, `jnwb/connectivity/**`, `jnwb/jrsa.py`, `jnwb/jrsa/**`, `tests/test_connectivity.py`, `tests/test_jrsa*.py`.
Split per `restructure_plan.md` (a); `bin_spikes` and `as_trials` stay importable from
`jnwb.connectivity`. Pure moves.
Accept: as 10-02.
Stop: a move changes a number.
Waits: layout only.

### 10-06 Directed and similarity estimator edges

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: 10-05.
Writes: `jnwb/connectivity/**`, `jnwb/jrsa/**`, `jnwb/rsa.py`, `tests/test_connectivity.py`, `tests/test_jrsa*.py`, `tests/test_rsa.py`, `tests/test_substitution_class_sweep.py`, `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-population/SKILL.md`, `docs/03_representational_similarity_jrsa.md`, `docs/08_directed_connectivity_and_information.md`.
- P-227: the PSI jackknife leaves out a segment, not an epoch; liberal under zero-lag mixing (0.0655). Check: an epoch-level jackknife. Waits: stated with IB-97; conservative under independence.
- P-264: with undefined bands PSI sums `net` over defined bands only. Check: the docstring says so, or undefined bands make `net` NaN. Waits: flagged by `ok_for_interpretation`.
- P-196: no test pins `psi_freqs` or `psi_per_freq[0]`. Check: both pinned. Waits: output correct.
- PSI segment count and conditional networks: the default `nperseg` leaves 7 segments; `directed_network` has no conditional mode. Check: a default of about 20 segments and a conditional mode, each ruled first (`decisions.md` D10). Waits: p valid, a warning fires.
- IB-45: an int `rng` gives every pair the same surrogate stream. Check: one scheme for both, recorded per pair. Waits: each pair's p stays valid.
- Directed estimator edges: `bias_corrected_*` values sit off zero under mixing; `directed_network(method="psi", jackknife=False)` returns an all-NaN `q_matrix` silently; the TE large-n excess has no pinned mechanism. Check: the docstring, a warning, a record by n. Waits: no p depends on them.
- Tie-width test reach, directed part: the substitution probes accept any error type with no `match`; the PSI width test pins a lower bound only; TE's net width keeps the plain sum. Check: each probe matches its selector's message. Waits: all ten probes raise their own refusal today.
- P-331 jrsa and Granger half: `jrsa` standardises detrend residue, and the Granger residual guard sees it. Check: stated tolerances. Waits: degenerate input.
- P-256 information half: two MI functions name `spike_mutual_information` in their errors. Check: each names itself. Waits: message quality.
- P-332 similarity part: `cka` and `rv` give 1e-33 on a constant pattern; `_phase_slope` says normal-approximation p where the code uses t; `jrsa(align='bogus')` accepted at equal lengths. Check: exact values, the docstring, a refusal. Waits: degenerate or wording.
- IB-44: a calibrated block bootstrap for the `jrsa` paired metrics replaces the refusal (ruled 2026-09-25). Check: 95 % interval coverage near 0.95 on AR(1) pairs at phi 0.9. Waits: the refusal is correct.
- IB-48: `jrsa` accepts `device='cuda'` but never reaches the CuPy branch. Check: route it or drop the branch. Waits: records cpu truthfully.
- IB-58: the `jrsa` row-metric `window` at the default `adim` (integrator's 0.2.8 note, graded 70). Check: windowing the observation axis by default, with a CHANGELOG entry. Waits: stated in the docstring and page.
- `jrsa` resampling fallback: `_resample_axis` downsamples when SciPy is missing while `align` echoes the request. Check: the branch removed. Waits: SciPy is declared.
- Generator seeds and `jrsa` axes, similarity part: the `adim` refusal's dropped-axis branch has no test. Check: a test.
- P-281: `test_cuda_matches_cpu` for `jrsa` compares CPU with CPU. Check: renamed or removed. Waits: no GPU path.
Accept: each check passes; calibration records in `artifacts/evidence/0.2.10/`.
Stop: a default change without a ruling.

### 10-07 `statistics` as a package

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: 10-01.
Writes: `jnwb/statistics.py`, `jnwb/statistics/**`, `tests/test_statistics.py`, `artifacts/frozen_validated.json`.
Split per `restructure_plan.md` (a); `StatisticalAnalysis` moves whole. Gate 19's two
`jnwb/statistics.py` entries are re-pointed with unchanged hashes.
Accept: as 10-02, and gate 19 passes with no hash changed.
Stop: a move changes a function body gate 19 hashes.
Waits: layout only.

### 10-08 Statistics, spiking and decoding edges

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: per finding. Blocked by: 10-07.
Writes: `jnwb/statistics/**`, `jnwb/permutation.py`, `jnwb/spiking.py`, `jnwb/onset_fitting.py`, `jnwb/analyzers.py`, `jnwb/trajectory.py`, `jnwb/gpu_pca.py`, `jnwb/bilinear.py`, `jnwb/nam.py`, `jnwb/artifact_repair.py`, `jnwb/_spread.py`, `jnwb/_bins.py`, `jnwb/_dictlike.py`, `jnwb/testing/**`, `tests/test_statistics.py`, `tests/test_permutation.py`, `tests/test_spiking*.py`, `tests/test_analyzers*.py`, `tests/test_trajectory*.py`, `tests/test_bilinear*.py`, `tests/test_rng*.py`, `skills/jnwb-statistics/SKILL.md`, `skills/jnwb-spiking/SKILL.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/07_statistical_inference_and_nulls.md`.
- P-265: one value per group gives NaN ANOVA beside `eta_squared` 1.0. Check: NaN or a stated reason. Waits: no p or flag passes.
- P-297: the `compare_multiple_groups` docstring omits NaN `eta_squared` for an empty group. Check: stated. Waits: loud NaN.
- P-321: `confirmatory_compare` returns `correction: "none"` beside BH q values. Check: the key names what it describes. Waits: q named separately.
- P-329: an arithmetic paired difference gives t near 6e15 rather than inf. Check: stated. Waits: outside the exact-equality rule.
- P-346: the sign-flip tie tolerance over-counts at 1e11 dynamic range, and no test pins its size. Check: a test pins 8 eps. Waits: conservative.
- P-350: `permutation_test` reports significant at the floor with NaN difference beyond 1.8e308. Check: NaN on non-finite centred values. Waits: no physical input.
- P-333: no test catches `is_constant(ignore_nan=True)` regressing. Check: a NaN case in a row with spread. Waits: verified correct.
- P-334: `_spread.zscore` on inf returns `[-inf, -inf, nan]`. Check: NaN. Waits: non-finite input only.
- P-246: `paired_fire_prob_test(rng=<int>)` raises `AttributeError`. Check: a checked `TypeError`. Waits: loud.
- P-255: `causal_exp_smooth(tau_ms=0)` returns NaN with a warning. Check: a refusal. Waits: loud NaN.
- P-256 permutation half: `build_permutation_plan(labels, None)` raises a bare `TypeError`. Check: it names `groups`. Waits: message quality.
- P-231: the Rayleigh comment quotes the second-order formula. Check: aligned. Waits: code correct.
- P-315: `_whole_bin_count` prints "Use , or ..." for a reversed window, and its tolerance near 3e7 bins was not rechecked. Check: the message and a test. Waits: loud on unrealistic input.
- P-320: the whole-bin refusal prints refused and suggested windows alike at large times. Check: enough digits. Waits: error path only.
- P-319: the refractory-key test accepts any number of warnings. Check: exactly one. Waits: one in 60 of 60.
- P-292: after `cupy.linalg`, `compute_population_trajectory(device='cuda')` warns the wrong cause. Check: the message names the DLL conflict. Waits: `device_used` correct.
- P-323: `compute_population_trajectory` omits `device_used` for an empty area. Check: always present. Waits: nothing computed.
- P-343: float32 PCA with a near-degenerate top pair differs across devices. Check: parity below working precision declared undefined. Waits: below working precision.
- P-332 remainder: flat input in `fit_exponential_onset`, `population_trajectory` and `rdm`; the `UnitAnalyzer` multi-class error; project-history text in `nam.py` and `bilinear.py`. Check: named refusals, text removed. Waits: loud or wording.
- Response-significance wording: the bursting limit holds for 4 ms bursts and falls to 19 % at 50 ms, unstated in four homes; `RenamedKeyDict.setdefault` inserts a shadow key; `docs/04` carries release-transitional clauses. Check: the limit stated once and linked, `setdefault` fixed, the clauses cut. Waits: direction right everywhere.
- RNG surface: the dataset builders annotate `seed: int`, and the stochastic-parameter walk finds only `rng` or `seed`. Check: annotations and a walk by `resolve_rng` use. Waits: annotation only.
- IA-19: two-class `bilinear` `predict_proba` is overconfident (0.856 predicted, 0.582 observed). Check: one model for two classes and a calibration test. Waits: experimental and outside `__all__`.
- IA-23: `bootstrap_ci` loops in Python (11x slower at n 200). Check: vectorised with a version note, since the random stream changes (graded keep 2026-09-25). Waits: same order.
- IA-28: `bilinear` tests check a length only. Check: value-pinning tests with IA-19. Waits: goes with IA-19.
- IA-29: `nam` cites missing scripts and calls `torch.manual_seed`; `REWARD_WINDOW_MS` is unused; `artifact_repair` cites two missing scripts; `layer_masks_path` hardcodes project folders. Check: a local `torch.Generator`, the leftovers removed. Waits: non-exported modules.
- P-296: dangling references in `jnwb/` (`nwb_tfr_storage_spec.md`, `artifacts/benchmarks/...`) and development-history comments. Check: none left, merged with IA-29. Waits: no behavioural effect.
- P-216 statistics part: the unscoped-delay paraphrase branch is unpinned. Check: a killing test. Waits: behaves correctly.
Accept: each check passes; values that move carry a CHANGELOG entry.
Stop: a fix changes shipped values without a ruling.

### 10-09 Display edges

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: 10-08.
Writes: `jnwb/viz.py`, `jnwb/vis/**`, `jnwb/visual_qc.py`, `tests/test_vis*.py`, `tests/test_visual_qc.py`, `tests/test_viz*.py`, `skills/jnwb-landmark-viz/SKILL.md`, `skills/jnwb-figures/SKILL.md`.
- P-244: `apply_tight_auto_axis` floors y at 0, so signed data is drawn outside the axes. Check: a floor only for non-negative data. Waits: display only, stated.
- P-313: the stability panel coerces with `astype(bool)`, so a text flag plots every unit Stable. Check: a refusal of non-boolean flags. Waits: display only.
- P-275: the no-default-landmark test misses a `UnaryOp` default and a body fallback. Check: both fixtures. Waits: the code has neither.
- Vis label edges: a full label in `plot_csd`'s `colorbar_title` doubles the unit; a whitespace title; the depth hover has no unit. Check: a title naming a unit refused, the hover names `depth_unit`. Waits: visibly contradictory, never silent.
- Vis range edges: the hierarchy hover's "%" removal is unpinned; `plot_spectrolaminar_map` draws infinities as gaps; an empty `rel_power` fails in numpy. Check: a killing assertion, infinities refused, a named error. Waits: shipped hover correct.
- P-254: `Canvas.save_and_seal` loses its export on a loaded Windows machine when choreographer's shutdown budget expires; a serial run can hang at exit after a failed close; no test shows an export error reaching the caller. Check: one kaleido session per call, a serial run exits after a failed close, the swallowed-error mutant killed, later calls fail fast. Waits: loud, and release runs use xdist, where the hang does not occur.
- P-332 display part: `plot_sorted_heatmap(category_labels)` is ignored. Check: used or refused. Waits: display.
- P-216 display part: the gradients crossover default and the `jnwb.vis` vocabulary beyond a grep are unpinned. Check: killing tests. Waits: behaves correctly.
Accept: each check passes.
Stop: none beyond the standing ones.

### 10-10 Identity and scientific-choice facts held

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: none. Blocked by: 08-09.
Writes: `scripts/ontology_gate.py`, `tests/test_ontology_gate.py`, `jnwb/_declarations.py`.
- I1 declared signature types for every numeric public operation, and type-checked composition edges. Check: a spikes-to-LFP-only edge, planted, is VIOLATED.
- B3 lexicon and exceptions table. Check: a planted defaulted `window=` with no cited reason is VIOLATED.
Accept: the Identity table and B3 report no UNHELD fact.
Stop: a declaration would change a public signature without a ruling.

# 0.2.11

Theme: NWB reading and writing are complete: every container `inspect` lists is readable, and the
mutation and execution APIs ship in the shape Hamm rules.

Acceptance: `AGENTS.md` §11; 07-21 and 07-22 ship only in the ruled shape; each landed writer has a
re-read test and an ambiguity refusal.

Every item here carries `deferred-0.2.9` until the cycle before it is tagged (`decisions.md` D2).

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| I reading | 11-01 | `jnwb/nwb_inspect.py`, `jnwb/nwb_io.py`, `jnwb/nwb_events.py`, `jnwb/io.py`, `jnwb/mcp_server/**`, their tests |
| J files and tables | 11-02, 07-05 | `jnwb/compression.py`, `jnwb/metadata.py`, `jnwb/addressing.py`, `jnwb/ontology.py`, `jnwb/paths.py`, their tests |
| K new APIs | 07-21, 07-22 | new modules only, their tests and pages |

### 11-01 Every container `inspect` lists is readable

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/nwb_inspect.py`, `jnwb/nwb_io.py`, `jnwb/nwb_events.py`, `jnwb/io.py`, `jnwb/mcp_server/**`, `tests/test_nwb_inspect.py`, `tests/test_nwb_read_tolerance_and_visibility.py`, `tests/test_nwb_events.py`, `tests/test_mcp_server.py`, `tests/test_io*.py`, `docs/errors.md`, `skills/jnwb-nwb-data/SKILL.md`.
- P-294: `acquisition_channel` does not resolve behavior containers under `processing/`. Check: `processing/behavior/EyeTracking` reads. Waits: loud.
- P-314: `BehavioralEvents` cannot be read by any name; `BehavioralEpochs` and ophys unprobed. Check: one table covers every container `inspect` reports. Waits: loud; same root as P-294.
- P-303: `inspect` of an in-memory file and the file walk unwrap different container sets. Check: one unwrap rule. Waits: known types agree.
- P-299: `inspect` reports `packaging` `direct` for wrapped containers with nested `data_path`. Check: the right label. Waits: vocabulary only.
- P-190: a series with `timestamps` and no constant `rate` raises `AcquisitionNotFoundError`. Check: the exception class of `decisions.md` D8. Waits: message true; a new class is API.
- P-204: `ContainerTypeContradictionWarning` blames the type when only the `uV` unit is wrong (78 of 96 corpus warnings). Check: a unit-scale message distinct from a type message (D8). Waits: errs toward caution.
- P-221: that warning is not exported. Check: exported or not by D8. Waits: changes no value.
- P-220: an empty `session_description` group raises `ValueError` under the waiver. Check: a missingness-table row and a named error. Waits: fails loudly.
- P-336: no test pins the `channel_conversion` length refusal. Check: a killing test. Waits: behaves correctly.
- P-337: the unit warning names only `conversion=`, and the `starting_time` warning points at `nwb_inspect.py`. Check: both conversions named, `stacklevel` at the caller. Waits: messages true.
- P-216 reading part: the `/acquisition` bare-name ambiguity refusal is unpinned. Check: a killing test. Waits: behaves correctly.
- MCP signal reference edges: the reader check does not pin the channel axis; a `channel_conversion` outside the schema is reported but ignored; an infinite rate is accepted; the sweep row omits the reference tool's handler. Check: each a test or a refusal. Waits: loud or outside the schema.
- P-289: the MCP writes-nothing test snapshots two directories, and the no-`jnwb.testing` check misses `importlib`. Check: a whole-tree snapshot and a runtime check. Waits: no current path does either.
- P-291: `stream_npz_array` accepts `Ellipsis` on 0-d where its docstring says `TypeError`. Check: the docstring. Waits: value right.
Accept: each check passes.
Stop: reading a container would need to infer its meaning.

### 11-02 Compression, unit tables and addressing edges

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/compression.py`, `jnwb/metadata.py`, `jnwb/addressing.py`, `tests/test_compression.py`, `tests/test_metadata.py`, `tests/test_addressing.py`, `docs/02_paths_addressing_metadata.md`.
- P-283: `_timestamps_fate` does arithmetic with `None` when `rate` is absent. Check: a named refusal. Waits: loud.
- P-298: a hard-linked timestamps array is neither collapsed nor refused. Check: links resolved by object id. Waits: receipt consistent.
- P-324: `compress_fp32(select=)` on a SoftLink writes an independent copy. Check: stated or refused. Waits: pinned.
- P-338: a second link can open a cast irregular timestamps array. Check: refused or recorded per link. Waits: opt-in, recorded.
- P-344: wall time rises 2.4x from 800 to 1600 series. Check: a measurement against HDF5 per-op cost. Waits: linear op count.
- P-348: relative soft-link resolution, the soft-linked `select=` message and CUDA constant-channel NaN are unpinned. Check: tests. Waits: observed correct.
- P-192: `enrich_units_dataframe` without `peak_channel_id` fills Unknown silently. Check: a warning and the prerequisite on the page (06-90). Waits: Unknown, not wrong.
- P-242: `unit_census_report` drops absent grouping columns silently. Check: a warning. Waits: documented filter.
- P-245: `assign_quality_tier` maps an unknown code to `'unstable'`. Check: D8's choice. Waits: conservative.
- P-312: `compare_old_new_criteria` mishandles nullable `is_stable`. Check: nullable handled. Waits: not exported.
- P-322: `get_all_units_metadata(filter_quality=True)` without `quality` raises where the CHANGELOG says a warning. Check: the warning. Waits: loud.
- `classify_layer_from_depth` reads electrode z as depth with no declared shallow end. Check: D10's ruling. Waits: stated; a ruling.
- P-216 addressing part: `VISp6a/b` splits into a spurious area. Check: a test and a fix. Waits: no corpus here carries it.
Accept: each check passes.
Stop: a fix would name an area vocabulary.

### 07-05 A downstream paper agent can consume jnwb

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: per skill. Blocked by: 11-02.
Writes: `jnwb/ontology.py`, `jnwb/paths.py`, `tests/test_preflight*.py`, `tests/test_paths.py`, `tests/test_paths_identity.py`, `skills/jnwb/SKILL.md`, `CONTRIBUTING.md`.
Ruled 2026-09-25: the paper agent lives downstream; jnwb gains only what it cannot do without.
- a. A script scores decline accuracy from `jnwb.preflight` alone: outcome, reason and missing inputs as data.
- b. A result names its input's sha256 and object path, through `Provenance` or `Lineage` if they can carry it; IA-27's tests for `resolve_nwb_path`, `sha256_file` and `require` land here.
- c. `CONTRIBUTING.md` states the intake: a downstream miss classified as a jnwb defect enters the problem stack as a generic row with a synthetic discriminator.
- P-335: review the omission project's laminar curation pull request (ruled 2026-09-24) against the Boundary: composable parts, cited parameter defaults, micrometres, no project vocabulary.
Accept: a test per outcome in (a); a round trip in (b) by path and hash; gate 6 passes.
Stop: a study, paradigm or DANDI id in `jnwb/`, `skills/` or `docs/`.
Waits: new downstream capability.

### 07-21 A public NWB mutation API

Release: deferred-0.2.9.
AUTONOMY: none until Hamm rules the set from 08-08.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: 08-08.
Writes: `jnwb/nwb_write.py`, `tests/test_nwb_write.py`, `docs/writing_nwb.md`.
Accept: each landed operation re-reads its output and refuses an ambiguous mapping; API,
documentation and tests land before or with any skill.
Stop: anything that infers condition meaning, anatomy or units.
Waits: public API; Hamm rules the shape.

### 07-22 A public execution and cache API

Release: deferred-0.2.9.
AUTONOMY: none until Hamm rules the surface from 08-08.
Role: jnwb-developer. Skill: jnwb. Blocked by: 07-21.
Writes: `jnwb/execution.py`, `tests/test_execution_api.py`, `docs/execution.md`.
Order, per the fact stack: numerical identity (08-08), then the public abstraction, then
performance evidence, then routing.
Accept: a cache key includes input hash, parameters and version, with an invalidation test; no
control changes a number.
Stop: a control would change a number.
Waits: public API; Hamm rules the surface.

### 11-03 Design facts held

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: none. Blocked by: 08-09.
Writes: `scripts/ontology_gate.py`, `tests/test_ontology_gate.py`.
- D1 delegation edges for every public callable and each Analyzer method. Check: a planted two-step convenience is VIOLATED.
- D2 and D3 category tags on every operation with NWB or cache side effects, landing with 07-21 and 07-22. Check: an untagged planted writer is VIOLATED.
Accept: the Design table reports no UNHELD fact.
Stop: a category outside the ruled allowlists would be needed.

# 0.2.12

Theme: the release apparatus is smaller and faster, and the repository carries no process
identifiers outside the stacks.

Acceptance: `AGENTS.md` §11; `scripts/` and the process tests are shorter than at `fe14858d` with
every gate still reported; no item or problem id outside `artifacts/` except machine-required
literals.

Every item here carries `deferred-0.2.9` until the cycle before it is tagged (`decisions.md` D2).

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| L release and CI | 12-02, 12-03 | `scripts/release_gate.py`, `scripts/smoke_installed.py`, `scripts/measure_peak_memory.py`, the workflow, `CONTRIBUTING.md`, release tests |
| M gates | 12-01, 12-04 | `scripts/harness_gate.py` and its split, `scripts/stack_edit.py`, `scripts/mutation_harness.py`, `scripts/computational_contract_gate.py`, gate tests |
| N test hygiene | 12-05 | the process tests on the prune list |
| Z alone | 12-06 | every comment in `scripts/` and `tests/`; runs when no other lane is open |

### 12-01 One stack parser and gates in their own modules

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/harness_gate.py`, `scripts/gates/**`, `scripts/stack_parse.py`, `scripts/stack_edit.py`, `tests/test_harness_adversarial_gates.py`, `tests/test_every_gate_runs.py`, `tests/test_stack_metadata_contradictions.py`, `tests/test_stack_edit.py`, `tests/test_gate*.py`, `tests/test_gates_reject_the_trees_they_passed.py`.
Plan: `restructure_plan.md` (a), scripts row.
- P-232: gates 15 and 17 read only `###` items while STEP 0a reads any depth. Check: one parser in `scripts/stack_parse.py`, used by both. Waits: the gates can only under-read.
- P-274: STEP 0a leaves four HTML heading forms unparsed. Check: the shared parser reads them. Waits: no HTML headings.
- Stack editor edges: `os.replace` raised WinError 5 once under load; no chained-edit test; a fence line can be removed; heading depth capped at six where the gate takes any; non-breaking-space indents; the check-then-replace race and missing fsync. Check: a retry, the chain test, a fence check, one heading rule. Waits: one call per edit reaches none of these.
- P-218: gate 2 excuses a counterfeit at a stale worktree registration. Check: the admin `gitdir` points back. Waits: needs a counterfeit.
- P-219: gate 2's PASS message is narrower than its check. Check: the message. Waits: no verdict changes.
- P-235: the stated-gate-count test misses `skills/`, `docs/`, number words and ranges. Check: all read. Waits: the live count is correct.
- P-295: gate 14's id pattern passes `items/06-55`, `P-1000`, `p-29` and fails `09-23`. Check: the pattern. Waits: live tree clean.
- P-311: gate 14 does not read `README.md` or follow `--8<--` includes. Check: both. Waits: clean at `3f533574`.
- P-301: no test pins the removal of an external project's name from `jnwb/vis/sidecar.py`. Check: gate 6's token list. Waits: clean.
- P-342: gate 19 hashes a name's first definition only and accepts a wrongly-named killing test. Check: last binding hashed, test ids resolved. Waits: no name bound twice.
- P-198: `run_full_preflight` de-duplication is unpinned. Check: a killing test. Waits: a duplicate cannot hide a failure.
- P-304: gate 9's api sync is untested against a same-length drift, the contract gate against a doubly-categorised export, and `win_ms=` literals against `bin_ms`. Check: a fixture each. Waits: no evidence passes falsely.
- P-216 gate part: a second interpreter sentence (gate 8 reads the first) and `sys.modules.clear()` in the collection-order detector are unpinned. Check: killing tests. Waits: behave correctly.
Accept: `python scripts/harness_gate.py` reports every gate PASS; the gate tests pass; the harness
is shorter.
Stop: a split changes a gate's verdict on any fixture.

### 12-02 The release gate reads the shared parser

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: none. Blocked by: 12-01.
Writes: `scripts/release_gate.py`, `tests/test_release_requires_an_empty_problem_stack.py`, `tests/test_release_body_gate.py`, `tests/test_release_recovery_gates.py`, `tests/test_release_version_is_unpublished.py`, `tests/test_generation_closure_is_declared.py`.
- P-300: the STEP 0a message truncates item titles. Check: whole titles. Waits: wording only.
- P-302: a problem-shaped row outside `## Open` is not counted. Check: counted. Waits: Open is fully checked.
- P-330: renaming a required id to a deferred one after the receipt reads as one done and one added. Check: no new ids after the receipt. Waits: needs a deliberate rename.
- Readiness blind spots: a `##` section listing work outside any item; `--assume-unchanged` and `--skip-worktree` files; a job-level `continue-on-error` on TestPyPI. Check: each refused. Waits: none present.
- RP-2: STEP 0e refused on an in-progress pull-request run while the push run for the commit passed. Check: a concluded green run for the exact commit suffices, tested. Waits: fails closed.
Accept: STEP 0a imports `scripts/stack_parse.py`; its tests pass.
Stop: the shared parser reads an item STEP 0a did not, or the reverse, on the live stack.

### 12-03 CI and release workflow

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: none. Blocked by: 12-02.
Writes: `.github/workflows/workflow.yml`, `scripts/smoke_installed.py`, `scripts/measure_peak_memory.py`, `CONTRIBUTING.md`, `tests/test_workflow_release_policy.py`, `tests/test_ci_conclusion_gate.py`, `tests/test_import_provenance.py`, `tests/test_distribution_manifest_inspection.py`, `tests/test_dependency_floors_are_installable.py`, `tests/test_the_suite_can_qualify_an_installed_copy.py`, `tests/test_test_imports_survive_the_wheel_leg.py`.
- RP-7: a threshold on peak memory beside wall time in the suite step. Check: set from the recorded measurements. Waits: needs the 0.2.7 measurements first.
- CI guard hardening: exit-masking forms in the pytest steps, `set +e` in Resolve, a re-upgrade after the constrained install, only `env.FLOOR_PYTHON` checked, two copies of the browser retry. Check: each refused by a test. Waits: each needs a deliberate workflow edit.
- Peak-memory reset evidence: a clear_refs write counts as a reset unobserved; the unwritable case is undocumented; the `ru_maxrss` fallback is unlabelled. Check: a re-read, a row, a label. Waits: every row is labelled correctly.
- Floor coverage: 3.12.0 runs only on the Ubuntu floors leg. Check: newest dependencies on 3.12.0, and Windows 3.12.0. Waits: the known defect class reaches the Ubuntu leg.
- One smoke definition: CI's smoke script and the release gate's installed-package script check different things. Check: one definition both run. Waits: each exercised where it runs.
- P-352: the release gate's smoke script runs only at step 7. Check: the suite runs it against the tree. Waits: fails closed.
- P-353 smoke half: the smoke step keeps `PYTHONPATH` where the tutorial step strips it. Check: stripped. Waits: asserts a `site-packages` import.
- Release workflow edges: the smoke pass branch, export and extra checks are untested to failure; a yanked TestPyPI file passes the hash comparison; the verify job's one-wheel count is not asserted. Check: tests. Waits: each fails loudly in CI.
- P-309: the distribution tests read only `<repo>/dist` and do not reject `examples` or `data` components. Check: an external build path and the rejection. Waits: the byte comparison held.
- P-328: Actions pinned to tags. Check: commit SHAs, then the requirement on. Waits: GitHub-owned and allow-listed.
- P-191: a contributor install without `vis` fails the `__all__` sweeps. Check: those tests skip names of absent extras. Waits: false failures only.
- P-197: the provenance scanners miss ten spellings and accept five prepend forms. Check: each a fixture, or the installed-wheel leg named as the check. Waits: the wheel leg catches a checkout-pinned test.
- Prepend scanner reach: slice assignment, rebinding, aliasing and non-zero indices are missed; the path-order assertion runs only when ordered after. Check: each flagged; the assertion at session end. Waits: no such form exists.
- RP-1: `CONTRIBUTING.md`'s release steps say the `dev` deletion rule has no bypass, if 08-06 did not already.
Accept: each check passes; one CI run on `dev` is green.
Stop: a hardening would refuse the current workflow.

### 12-04 Mutation and contract gate reach

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: none. Blocked by: 12-01.
Writes: `scripts/mutation_harness.py`, `scripts/computational_contract_gate.py`, `tests/test_mutation_harness_validity.py`, `tests/test_computational_contract_gate.py`, `tests/test_substitution_class_sweep.py`.
- P-238: `collect_selector` drops node ids containing a space. Check: such ids selectable. Waits: fails closed.
- P-266: the contract gate tracks aliases without order and accepts one correct path among several. Check: order-aware aliasing. Waits: switch tests hold live behaviour.
- Sweep site fingerprint: a handler edited in place keeps its site key. Check: `decisions.md` D11's choice. Waits: no current row is wrong.
Accept: each check passes.
Stop: none beyond the standing ones.

### 12-05 Process tests pruned and merged

Release: deferred-0.2.9.
AUTONOMY: none for the list; Hamm rules it.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/evidence/0.2.12/process_tests/**`, `tests/test_docs_runnable_prerequisites.py`, `tests/test_standing_rules_name_no_cycle.py`, `tests/test_uncovered_exports.py`, `scripts/reconstruct_state.py`, `tests/test_state_reconstruction.py`.
The exact files come from the ruled list; this set is the 0.2.7 audit's candidates and is resolved
against `artifacts/evidence/0.2.7/process_test_audit.md` before dispatch.
- Process tests to prune or merge: 4 files to prune, 4 to merge, and four weaker checks a stronger test covers. Check: Hamm rules the list (`decisions.md` D12).
- P-290: the ruled test taxonomy (`CONTRIBUTING.md:154`) is enforced by nothing. Check: each kept process test named under one category in the prune record; a taxonomy change goes to 12-03, which owns `CONTRIBUTING.md`.
- Apparatus bound: `artifacts/goal.md` §10 has no check. Check: `scripts/reconstruct_state.py` records the line counts of `scripts/` and the process tests, so growth is visible per release; a refusal is 12-02's to add if Hamm asks.
Accept: the pruned files' cases are held by the stronger tests named in the audit.
Stop: a pruned test is the only one that kills some mutant.

### 12-06 No process identifiers outside the stacks

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: none. Blocked by: 12-02, 12-03, 12-04, 12-05.
Writes: `scripts/*.py`, `tests/**/*.py`, `.github/workflows/workflow.yml`, `CONTRIBUTING.md`.
- P-284: 134 identifiers in 7 `scripts/` files and 641 in 98 test files cite item and problem ids (P-209 and IB-71 merged here). Check: each removed or rewritten as a plain reason, then gate 14 extended to both folders with an allowlist for machine-required literals.
- P-102: line endings levelled across the tree if `decisions.md` D3 rules it, as the last commit of the cycle, since it touches every file. Check: gate 16 passes and one byte-mode edit per convention applies.
Accept: gate 14 passes on `scripts/` and `tests/`; the suite passes.
Stop: an id is a literal a parser fixture needs.
Waits: neither directory ships.

### 12-07 Release and study-vocabulary facts held; no fact UNHELD

Release: deferred-0.2.9.
Role: jnwb-developer. Skill: none. Blocked by: 08-09.
Writes: `.github/workflows/workflow.yml`, `scripts/harness_gate.py`, `scripts/ontology_gate.py`, `tests/test_ontology_gate.py`, `tests/test_harness_gate_study_tokens.py`.
- R2: a verify-pypi job after publish-pypi (fresh install from PyPI, sha256 equal to the tag run's artifact, `pip check`, the installed smoke test). Check: a planted hash mismatch fails the job's check function.
- B2: Gate 6 scans all of `jnwb/`, `docs/`, `skills/` and `tests/`; each hit repaired or shown generic. Check: a planted study token in `tests/` fails.
Accept: `scripts/ontology_gate.py` prints UNHELD 0 and VIOLATED 0.
Stop: a workflow change would alter the ruled publication order.

## Out of scope for 0.2.8 to 0.2.12

Each needs its own authorization.

- Raw-data-to-NWB conversion.
- An authorization or permission subsystem.
- Benchmark execution; the design is kept, unrun, in `artifacts/evidence/0.2.8/stack/`.
- A capability-by-capability matrix over the whole public surface (P-268).
- Dataset-specific package code, and new estimators that only improve a demonstration.
- The 36 unverified review findings, except where an item reaches one.
