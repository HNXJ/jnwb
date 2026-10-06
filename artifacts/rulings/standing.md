# Standing rulings

The rulings of the dated files in this folder that still bind, one row each, as of `7cb72f4b`.
The dated files stay as written and carry each ruling's reasons and the work it created; this
table carries only the rule, when it was ruled and what holds it now. Later rows of a dated file
replace earlier ones on the same subject, and only the standing form is here.

Left out: rulings whose work was a single act now done (reverts, freezes, cleanups, the closure
of 0.2.6 and 0.2.7, the release of each), rulings on the scope of a closed cycle, and rulings a
later row replaces. Held by names the test, gate, code or file that keeps the rule true, or the
live item that will; a ruling held by nothing else says "the ruling".

| Subject | Rule | Ruled | Held by |
|---|---|---|---|
| Autonomy and decisions | Grade each option 0 to 100 and act by grade; two defensible options with a material trade-off come to Hamm | 2026-09-25 | `AGENTS.md` §12 |
| Problem stack | Empty for a release; a problem leaves repaired, shown false, or moved into the todo stack as `required-` or `deferred-` | 2026-09-23 | `AGENTS.md` §11, `tests/test_release_requires_an_empty_problem_stack.py` |
| Concurrent agents | One integrator writes `dev`; workers execute claimed packets in their own clones; the project-state files are the only shared truth | 2026-09-25 | `artifacts/cooperation.md` |
| Standard tasks | None runs on a schedule; each runs on request; the four on-demand tasks are T8 to T11, read-only, from a clone at a named SHA | 2026-09-25, 2026-09-29 | `artifacts/cooperation.md` |
| The agents' chat | `F:/cowork/jnwb-bus/jchat/jchat.py`, bound to 127.0.0.1, is the one chat center; a client that cannot reach it uses the room files | 2026-09-29 | the ruling (`2026-09-29.md`, "The agents' chat hub") |
| Corpus access | Read the raw NWB on `D:` read-only; write only to `E:` or the scratchpad; no corpus identifier in `jnwb/`, `docs/`, `skills/` or `tests/` | 2026-09-22 | the ruling; gate 6 for the identifiers (`scripts/harness_gate.py`) |
| Branches | Only `main`, `dev` and `gh-pages` stay on the remote; merged work is deleted | 2026-09-23 | the ruling |
| The todo stack's order | The integrator re-sequences lanes, waves and blockers for throughput; no item's meaning, Accept or Stop changes | 2026-09-29 | the ruling |
| Planned cycles | 0.2.8 to 0.2.12, one theme and one acceptance line each, lanes that share no file, at most three writers at once | 2026-09-29 | `artifacts/todo_stack.md` |
| Deferred marks | Every item after the current cycle carries `deferred-<next>`; the version heading carries the schedule; each cycle opening relabels its section | 2026-09-29 | `scripts/release_gate.py` |
| Carry-map rows | A row resolves when it names the commit that finished its work | 2026-09-29 | `artifacts/evidence/0.2.8/plan/carry_map.md` |
| Rulings layout | This table holds the rulings that still bind; the dated files stay as written | 2026-09-29 | this file |
| Repository minimization | Authorized for 0.2.8 to 0.2.12; each deletion is still reviewed | 2026-09-29 | the ruling |
| Module splits | An oversized module becomes a package at the same import path; `__init__` re-exports every name; public classes keep `__module__` at the old path | 2026-09-29 | 10-02, 10-05, 10-07 |
| Line endings | LF everywhere through `.gitattributes` in one commit at the end of 0.2.12; until then each file keeps its own convention and gate 16 refuses a mixed file | 2026-09-29 | gate 16 (`scripts/harness_gate.py`); 12-06 |
| Process tests | The audited prune and merge list stands; it runs after the gates split, each pruned case shown held by a stronger test first | 2026-09-29 | 12-05 |
| Sweep site fingerprint | The stated gap is kept; keying on the handler body is not built | 2026-09-29 | the ruling |
| `AGENTS.md` | A router of rules and routes at about 2250 words; reasons go to `artifacts/rulings/history.md` | 2026-09-29 | `AGENTS.md`, `scripts/measure_agents_md_duplication.py` |
| Echo ratchet | The count of `AGENTS.md` claims echoed elsewhere stays at its measured value, lowered on every rewrite and never raised | 2026-09-29 | `tests/test_agents_md_stays_a_router.py` (`BASELINE_ECHOED`) |
| `AGENTS.md` §4.7 | Stays a rule; fact S7 keeps only its checkable half | 2026-09-29 | `AGENTS.md` §4 |
| `AGENTS.md` §7 skills | Points to the one skill table in `docs/agents.md` and names the repository-only skills | 2026-09-26 | `AGENTS.md` §7 |
| Host skills | A jnwb skill governs jnwb operations; an overlapping host skill adds only checks it leaves open | 2026-09-28 | `AGENTS.md` §7 |
| Review checks | Live in the repository-only skill `artifacts/skills/jnwb-review`; the verifier dispatch file is a local copy under the git-ignored `.claude/agents/` | 2026-09-28, 2026-09-29 | `artifacts/skills/jnwb-review/SKILL.md` |
| Process skill | `jnwb-fact-action` does not ship; it lives at `artifacts/skills/jnwb-fact-action/SKILL.md`, and gate 2 accepts a skill there only when no shipped skill has its name | 2026-09-25 | gate 2 (`scripts/harness_gate.py`) |
| Archive contents | `AGENTS.md` and `jnwb-fact-action` are forbidden components of a built archive | 2026-09-25 | `scripts/release_gate.py` |
| Role definitions | The files in `artifacts/agents/` stay out of the wheel; `artifacts/agents.md` names only public capabilities and does not link them, which replaces the 2026-09-22 link (`3d7ac490`) | 2026-09-22, 2026-09-25 | gate 14 (`scripts/harness_gate.py`) |
| Gate 14 reach | `artifacts/agents.md` is scanned like `README.md` | 2026-09-25 | gate 14 (`scripts/harness_gate.py`) |
| Spikes and LFP | Never pooled, namespaced or not | 2026-09-29 | `AGENTS.md` §5; 08-07 for `CONTRIBUTING.md` and the docs |
| Log last | Fact S2 governs every decibel output: average raw power, divide by baseline, take `10*log10` once; a mean-of-dB estimand is a separately named function; `CONTRIBUTING.md` invariant 4 is rewritten to match | 2026-09-29 | fact S2 (`artifacts/fact_stack.md`); the ruling names 08-07 for the rewrite, which carries no bullet for it at `7cb72f4b` |
| Fact stack form | Typed predicate rows (ID, Domain, Predicate, Held by, Ruled), one atomic claim each, in six tables | 2026-09-29 | `artifacts/fact_stack.md` |
| Fact graph | Generated as `artifacts/fact_graph.json` by `scripts/build_fact_graph.py`, never committed; `scripts/fact_gate.py` reports each fact HELD, VIOLATED or UNHELD, and VIOLATED fails | 2026-09-29 | `scripts/fact_gate.py`, `tests/test_fact_gate.py` |
| Fact constants and holders | The lexicons, categories, claim classes, forbidden vocabularies and k are owned in the fact stack; an item that lands a fact's holder replaces its `todo:` cell in the same merge, with a verifier's sign-off | 2026-09-29 | `artifacts/fact_stack.md` |
| Capability order | Implemented, identity-verified where an execution switch exists, documented, tested, routed; a state holds only with every earlier one; performance evidence is not a state | 2026-09-29 | `artifacts/fact_stack.md` |
| Fact schedule | 0.2.8 the tables and gate; 0.2.9 Science and Skills; 0.2.10 Identity and B3; 0.2.11 Design; 0.2.12 Release and B2, with no fact UNHELD by the end of 0.2.12 | 2026-09-29 | 09-04, 10-10, 11-03, 12-07 |
| Identity tests | The fact stack owns the list of test modules whose reference establishes the identity-verified state | 2026-09-29 | `artifacts/fact_stack.md` (`identity tests`) |
| Invariant checks | Figures call a public operation and draw no bare-literal reference line; the dB-averaging lexicon; randomness implies an `rng` parameter and no global seed; the computational-contract gate; a retype scan over docs generators, examples and skills, backed by review (S1, S2, S5, S6, S7) | 2026-09-29 | 09-04 |
| Study vocabulary | Gate 6 widens to all of `jnwb/`, `docs/`, `skills/` and `tests/` | 2026-09-29 | 12-07 |
| Scientific choices | A parameter that sets a scientific choice is keyword-only and required, or defaulted with a cited reason | 2026-09-29 | 10-10 |
| No pipeline | A public callable delegates to at most one public analysis operation, or names every sequenced choice as a parameter | 2026-09-29 | 11-03 |
| Mutation and execution scope | Closed-world allowlists: eight categories for NWB side effects, seven for caching | 2026-09-29 | 11-03 |
| Estimand identity | A function's signal class, estimator, estimand, unit and frame are never silently substituted; numeric operations declare them | 2026-09-29 | 10-10 |
| Claim classes | Each estimand declares magnitude, lag asymmetry, delay or inference; text about it uses no higher class; the immunity vocabulary is refused | 2026-09-29 | 09-04 |
| Skills partition | The shipped domain skills partition the routed operations, each owning at least three; routing targets are public objects; four outcomes | 2026-09-29 | 09-04 |
| Skill template | Trigger, Routing, Invariants & Safeguards, Minimal Workflow, Verification, Documentation; the router adds Execution | 2026-09-25 | `CONTRIBUTING.md` |
| Router reach | A routed call is one in a bullet's head, before the colon after it; the router's own routing example is a deterministic array | 2026-09-29 | `tests/test_skill_router_reach.py` |
| Safeguards | Stated once, in the router skill; `docs/agents.md` links there | 2026-09-29 | `skills/jnwb/SKILL.md` |
| Checkout-only files | Kept out of the shipped router; contributor checks live in `CONTRIBUTING.md` | 2026-09-25 | `tests/test_skills_are_findable_from_an_installed_copy.py` |
| Downstream paper agent | Lives downstream, pinned to a release; jnwb gains only what every NWB consumer can use | 2026-09-25 | 07-05 |
| Omission's laminar curation | Arrives as a pull request of composable public parts with cited parameter defaults and no project vocabulary, reviewed against the library rules | 2026-09-24 | 07-05 (P-335) |
| Benchmark | Stays as declared and unrun; a paper agent's comparison is reported downstream | 2026-09-25 | `artifacts/evidence/0.2.8/stack/benchmark_design.md` |
| Method references | The Bastos survey lands in phases R1 to R6: method papers on the references page, the pitfalls stated once, one synthetic test per pitfall, skills pointing to their sources, estimator proposals each ruled before code, and reference edges in the fact graph | 2026-09-29 | 09-05, 09-06, 10-11, 10-12, 11-04, 12-08 |
| Documentation precedence | "No fact present before is absent after" wins; F7 applies to new facts only | 2026-09-29 | 09-02 |
| Representative API | The `README.md` "Representative API" table may omit modules while `docs/api.md` lists every export | 2026-09-22 | gate 9 (`scripts/harness_gate.py`) for `docs/api.md` |
| README links | `README.md` does not link `artifacts/todo_stack.md` | 2026-09-23 | gate 14 (`scripts/harness_gate.py`), `tests/test_harness_adversarial_gates.py` |
| One glossary | Each pair of terms (operation and workflow, session and recording, contact and channel, electrode and electrodes table) is defined once | 2026-09-22 | `docs/glossary.md` |
| Documentation form page | `docs/documentation_form.md` stays under `docs/`, out of the build and the navigation | 2026-09-26 | `mkdocs.yml` |
| Prose style gate | Only the slop lexicon is gated; em dashes and bold are not | 2026-09-28 | `scripts/docs_form_gate.py` |
| Claim wording | A suite test keyed by enclosing fragment and reason, beside gate 14 | 2026-09-27 | `tests/test_claim_wording.py` |
| API page cells | Signatures render as code spans | 2026-09-27 | `scripts/generate_api_md.py` |
| Figure legends | A legend that covers data fails release condition 1 | 2026-09-27 | `tests/test_figure_form.py` |
| fig04 fit | fig04 draws `jnwb.aperiodic_fit` over 15-90 Hz of the `compute_psd` spectrum it plots | 2026-09-29 | `docs/generate_figures.py` |
| Computational order | Upper bounds justified by the algorithm and its published reference; timed exponents are a separate benchmark with at least three input scales | 2026-09-22 | `CONTRIBUTING.md` |
| Test taxonomy | One: the probe classes of the "Testing rule" in `CONTRIBUTING.md` | 2026-09-22 | `CONTRIBUTING.md` |
| Additive API changes | Each gets a `CHANGELOG.md` Added entry and needs no deprecation path | 2026-09-22 | the ruling; 08-05 for the fragment form |
| CHANGELOG | One fragment file per change, assembled at release | 2026-09-27 | 08-05 |
| Gate 8 | Holds `README.md` and `docs/install.md` to the interpreter set | 2026-09-22 | gate 8 (`scripts/harness_gate.py`) |
| Gate 21 | Runs the computational-contract checks the suite runs | 2026-09-26 | `scripts/computational_contract_gate.py` |
| Version literals | The live-version scan reads every string literal and skips versions after a comparison operator | 2026-09-26 | `tests/test_prose_version_claims_are_live.py` |
| Package version | Bumped at the release step, with the CHANGELOG heading and the import profile; `dev` keeps the last release version until then | 2026-09-27 | `CONTRIBUTING.md` |
| Release gate receipt | STEP 0a accepts the fixpoint receipt when only the receipt and the todo stack changed since its commit, refuses an item relabelled from `required-` after it, counts a deleted held item as done only when the receipt names it, and accepts `release-step-<cycle>` items | 2026-09-23, 2026-09-28 | `scripts/release_gate.py`, `tests/test_release_requires_an_empty_problem_stack.py` |
| Unparseable todo headings | An item-depth heading with no id and no release field is reported by the readiness step; `##` structure is exempt | 2026-09-28 | `scripts/release_gate.py` |
| Peak memory | The release gate measures peak RSS without writing; the committed record is refreshed before the closure pass | 2026-09-27, 2026-09-28 | `scripts/measure_peak_memory.py`, `scripts/release_gate.py` |
| Publication order | The tag push publishes to TestPyPI, a verify job checks it with the build job's smoke script, and PyPI requires that job | 2026-09-22, 2026-09-25, 2026-09-28 | `.github/workflows/workflow.yml`, `tests/test_workflow_release_policy.py` |
| CI on a passed commit | The tag-push matrix is skipped when a dev-push run of the same SHA passed; main and pull-request runs still run; the release event skips the matrix and build, and publish uses the artifacts the tag run verified | 2026-09-29 | 08-07 (RP-4) |
| After PyPI | A CI job installs the release from PyPI, matches the wheel's sha256 to the tag run's artifact, runs `pip check` and the installed smoke test | 2026-09-29 | 12-07 |
| `dev` deletion rule | No admin bypass; automatic deletion of merged heads stays | 2026-09-25 | 08-07 (RP-1) |
| Dependency floors | The lowest versions at which the suite passes, held by a CI leg installed at the floors with no `continue-on-error` | 2026-09-27 | `.github/workflows/workflow.yml`, `tests/test_dependency_floors_are_installable.py` |
| Suite parallelism | xdist is required, with `--dist=loadgroup`; browser-backed tests share one `xdist_group`, and Plotly export tests one session browser per worker | 2026-09-26, 2026-09-27, 2026-09-28 | `pyproject.toml`, `CONTRIBUTING.md` |
| State file | `scripts/reconstruct_state.py` removes the old file before it runs the gates | 2026-09-25 | `scripts/reconstruct_state.py:215` |
| NWB reads | `nwb_read_io` accepts only `mode='r'`; manual labels are written through `pynwb` directly, and jnwb only reads them | 2026-09-23, 2026-09-24 | `jnwb/nwb_io.py` |
| Waived requirements | `jnwb_waived_requirements` records what was waived on this read, not what was requested | 2026-09-22 | `jnwb/nwb_io.py`, `docs/errors.md` |
| `starting_time` | `inspect` reports each series' `starting_time`; `acquisition_channel` warns when it is non-zero | 2026-09-23 | `jnwb/nwb_inspect.py` |
| NWB mutation API | The core five: validate, write, transform, structural repair, verified output; options (a) of Q-M2 to Q-M5 | 2026-09-29 | 07-21 |
| Execution surface | Per-call device and worker arguments, with the resolved execution recorded on the result | 2026-09-29 | 07-22 |
| Mutation and execution APIs | Proposals and identity evidence in 0.2.8; implementation in 0.2.11 after the shape is ruled | 2026-09-29 | 07-21, 07-22 |
| Public API changes | Export `ContainerTypeContradictionWarning`; a unit-scale message distinct from the type message; no new no-constant-rate exception; `assign_quality_tier` unchanged; no new routing rows for the analyzer classes or the unrouted exports | 2026-09-29 | 11-05, 11-01 |
| `compress_fp32` | `select=` is required; it refuses integer and boolean datasets as it refuses groups | 2026-09-22, 2026-09-23 | `jnwb/compression.py`, `tests/test_compression.py` |
| `verify_roundtrip` | A cast destination is float32 with the source's shape, besides equal values | 2026-09-25 | `jnwb/compression.py`, `tests/test_compression.py` |
| `depth_class` | The geometric column is `depth_class`; a layer-only frame given to the census warns that `layer` is not read | 2026-09-23, 2026-09-25 | `jnwb/metadata.py`, `tests/test_metadata.py` |
| `is_stable` | pandas `boolean` dtype, `<NA>` for a unit with no usable `quality`; `filter_quality=True` excludes it | 2026-09-23 | `jnwb/addressing.py`, `tests/test_addressing.py` |
| `jnwb.vis` | An optional extra; `import jnwb` works without `plotly` | 2026-09-22 | `tests/test_optional_vis_extra.py` |
| Laminar plot units | A required `depth_unit=`, never inferred; "Cortical Depth (mm)" for millimetres | 2026-09-25 | `jnwb/vis/laminar.py`, `tests/test_vis.py` |
| Vis units and ranges | `plot_csd` takes the unit of its matrix as a required keyword and has no default title; `plot_sorted_heatmap` a required `value_unit`; `plot_hierarchy_regression` a required axis label; `plot_spectrolaminar_map` refuses values outside [0, 1] | 2026-09-28 | `jnwb/vis/laminar.py`, `tests/test_vis.py` |
| Decibels | `aggregate_to_db(how="mean_of_ratios")` on trial-averaged input raises (a view raises; a real copy carries no mark); `TFRAccumulator.add_trial(..., baseline=)` takes each trial's baseline and `mean_of_ratios()` returns the linear mean | 2026-09-22, 2026-09-23, 2026-09-25 | `jnwb/tfr_accumulator.py`, `tests/test_composition_aggregation_order.py` |
| Baseline shape | A per-frequency baseline is refused unless its `ndim` is 0 or the data's, suggesting `baseline[:, None]`; a 1-D baseline to `relative_power` for N-D power warns, then raises | 2026-09-25, 2026-09-27 | `jnwb/spectral.py`; 10-03 for the second step |
| Zero baselines | A zero that cannot reach a ratio is ignored; one that can raises, in `aggregate_to_db` and `add_trial` | 2026-09-26 | `jnwb/spectral.py`, `tests/test_spectral.py` |
| `band_power`, `relative_power` | Computed on the CPU; `device='cuda'` or `'metal'` warns through the one resolver | 2026-09-23 | `tests/test_execution_switch.py` |
| `spectral_tilt` | The value is under `slope`; `exponent` stays one release behind a `DeprecationWarning`, then goes | 2026-09-27 | `jnwb/spectral.py`; 10-03 for the removal |
| Coupling sign | `imaginary_coherency` takes the cross-spectrum as `<X Y*>`, so a positive value means x leads, as for `phase_slope_index` | 2026-09-23 | `jnwb/connectivity.py`, `tests/test_estimator_discrimination.py` |
| Constant channels | `wpli` and `imaginary_coherency` return NaN when either channel is constant | 2026-09-24 | `jnwb/spectral.py` |
| Directed surrogates | Circular shift below 7 trials, recorded as `params['surrogate_scheme']` | 2026-09-25 | `jnwb/connectivity.py`, `tests/test_connectivity.py` |
| `transfer_entropy` | `estimator='symbolic'` is refused; the surrogate comparison uses plug-in values and Miller-Madow applies only to the reported estimate | 2026-09-25, 2026-09-28 | `jnwb/connectivity.py`, `tests/test_connectivity.py` |
| `phase_slope_index` p | With `jackknife=True` the lead p comes from the jackknife t test and the surrogate p is `p_coupling_surrogate`; with `jackknife=False` the lead p fields are None; below `8*eps*n_seg*n_pairs` z and p are undefined | 2026-09-28 | `jnwb/connectivity.py`, `tests/test_connectivity.py` |
| Permutation ties | One helper counts a draw within `100*eps*abs(observed)` as at least as extreme; Granger directions tie at 100 eps of max(1, abs(statistic)), PSI widths scale with the bin-pair count | 2026-09-28 | `jnwb/statistics/`, `jnwb/connectivity.py` |
| `network_topology` | Complex input is refused with `TypeError`; `network_connectivity` takes the magnitude first | 2026-09-26 | `jnwb/connectivity.py` |
| Directed defaults | `phase_slope_index` defaults to at least about 20 segments; `directed_network` gains a conditional mode | 2026-09-29 | 10-06 |
| `jrsa` nulls | `null=` is `'circular_shift'` (default), `'block'` or `'iid'`; row metrics raise without a named null only when a permutation null is formed; `bootstrap=` for paired metrics is refused unless `null='iid'` | 2026-09-25, 2026-09-26 | `jnwb/jrsa.py`, `tests/test_jrsa_correctness.py` |
| `jrsa` p | `p` and `q` are 0-d arrays; with no permutations a one-sided `alternative` comes from the parametric test | 2026-09-22, 2026-09-23 | `tests/test_jrsa_correctness.py` |
| `jrsa` lag | Along axis 0 for the six observation-axis metrics, truncated to the overlap with the sample count recorded | 2026-09-25 | `jnwb/jrsa.py`, `tests/test_jrsa_correctness.py` |
| `jrsa` axes | `sliding=True` is refused; a row-metric reduction removes the observation axis; a `window` on the removed axis raises; `result.axes` keeps the input's numbering; an `adim` the resampling ignores is refused only when a null, bootstrap or lag acts on it; series metrics refuse more than one row | 2026-09-23, 2026-09-26, 2026-09-27, 2026-09-28 | `jnwb/jrsa.py`, `tests/test_jrsa_correctness.py` |
| `jrsa` window default | Stated at the default `adim`; windowing the observation axis by default lands with the module split | 2026-09-28, 2026-09-29 | 10-06 (IB-58) |
| Randomness | `rng=None` gives scikit-learn one int drawn from fresh entropy; `build_permutation_plan` takes a `Generator` or `None` and returns the base seed; `nested_cv_linear_svm` reports `seed`, `None` on early status | 2026-09-26 | `jnwb/_rng.py`, `tests/test_rng_control.py` |
| Grouped decoding | `nested_cv_linear_svm(groups=)` uses `StratifiedGroupKFold` over seeded relabelled group ids, groups the inner search too, returns `"insufficient_groups_for_cv"` below two groups and raises on a one-class outer training fold | 2026-09-25 | `jnwb/decoding.py`, `tests/test_decoding.py` |
| Exploratory comparisons | `exploratory_compare` and `exploratory_multi` report `correction: "none"`; `correlate` and `exploratory_correlate` take `method=` | 2026-09-22 | `jnwb/statistics/`, `tests/test_statistics.py` |
| Missing estimates | A comparison with no estimate reports `df` as float NaN; an empty test family gives NaN `fraction_significant_uncorrected` | 2026-09-23, 2026-09-27 | `jnwb/statistics/`, `jnwb/analyzers.py` |
| `cluster_permutation_test` | Cluster sums by one stable sort, bitwise identical to the mask sums | 2026-09-27 | `jnwb/statistics/` |
| `raster_psth` | A window that is not a whole multiple of `bin_ms` raises, naming the nearest valid windows; offsets are clipped to the outer bin edges | 2026-09-23, 2026-09-26 | `jnwb/viz.py`, `jnwb/_bins.py`, `tests/test_analyzers_coverage.py` |
| Response significance | The conditional binomial test of response against baseline counts, gated by `alpha` beside the z gate; `pvalue` is reported when the z-score is undefined | 2026-09-26, 2026-09-27 | `jnwb/spiking.py`, `tests/test_spiking.py` |
| Unit quality | `quality_metrics` sorts spike times; its ISI rule is the single-unit check; `autocorrelogram`'s refractory verdict is NaN behind a `FutureWarning` | 2026-09-23, 2026-09-28 | `jnwb/analyzers.py`, `tests/test_analyzers_coverage.py`; 10-08 for the removal |
| Trajectories | `explained_variance_ratio` and `explained_variance_per_component` carry the new values; `explained_variance` switches to the per-component meaning; one private helper holds the variance rule | 2026-09-26, 2026-09-27 | `jnwb/trajectory.py`; 10-08 for the switch |
| Addressing | A channel id missing from the first identifier column returns the not-found result | 2026-09-27 | `jnwb/addressing.py` |
| Preflight | `jnwb.preflight(question)` returns one of the four outcomes with the reason and missing inputs as data; a minimal core (`signals`, `signal_units`, `contrast`, `inference_unit`) is required, else `request`; decline is caller-declared; a blank or `None` unit means not stated, a non-string raises | 2026-09-25, 2026-09-26 | `jnwb/ontology.py` |
| `zflip` orientation | A required `orientation=` of `'superficial_to_deep'` or `'deep_to_superficial'` | 2026-09-24 | `jnwb/laminar.py` |
| `zflip` identifiability | A pair is identifiable only when its wPLI reaches `min_wpli` and beats its own phase-randomised null at uncorrected `alpha`, with every pair required; no surrogates, a contact under 0.01 in-band share, or a flat or round-off-linear contact makes pairs unidentifiable; segments are detrended; a delay gradient within 8 eps is zero | 2026-09-28 | `jnwb/laminar.py`, `tests/test_zflip.py`; 10-04 for the flat-contact nulls |
| Depth declaration | The caller declares `depth_axis` and `shallow_end`; `vflip` and `label_layers` anchor there and record `depth_anchor`; a contradicting fit, a differing declaration or `orientation="deep_to_superficial"` beside one raises; `crossover_depth_um` stays in the rank-times-pitch frame beside an absolute-z field | 2026-09-25, 2026-09-27 | `jnwb/laminar.py`, `tests/test_laminar_index_space_and_boundary.py` |
| Depth criteria | A declared `depth_axis` is monotone along the rows and a staggered column is refused; `classify_layer_from_depth` takes a declared shallow end | 2026-09-29 | 10-04, 11-02 |
| `vflip` | Keeps its name; the docstring and the laminar page state how it differs from the published vFLIP; a `contact_spacing` that disagrees with `nominal_pitch` raises | 2026-09-26, 2026-09-29 | `jnwb/laminar.py`; 10-04 for the page |
| `xflip` | The partition objective is the per-block sum of within-block similarity squared over its pair count; under `n_blocks=None` the count is the smallest surrogate p with the selection repeated on each surrogate, ties by contrast in surrogate SDs then the smaller count, and count 2 with nothing accepted when there are no surrogates; the null rate is calibrated to a stated bound at or below alpha | 2026-09-26, 2026-09-27, 2026-09-28 | `jnwb/laminar.py`, `tests/test_xflip.py`, `tests/test_xflip_calibration.py` |
