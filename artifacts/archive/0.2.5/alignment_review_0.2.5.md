# Alignment review of 0.2.5

Read-only review taken 2026-09-19 against `dev` at `6741d23c`, 0.2.5 released and verified from
the index. Nothing in the repository was modified to produce it.

Target of the review: the stated project goal -- a dataset-agnostic toolbox for reliable
AI-assisted analysis of NWB datasets, with skills that adapt to unfamiliar datasets, an AI that
requires authorization and does not generate data, and an eighteen-slide presentation plan whose
diagrams are meant to become maintained documentation assets.

Method: eight parallel surveys (identity, dynamic/conversion, skills, documentation assets, AI
plumbing, reliability, public claims, evaluation and roadmap). Every finding was then put to two
adversarial verifiers with different lenses -- one checking that the receipt says what the
finding claims, one checking whether the rest of the repository already answers it. 102 agents,
96 completed; six verifiers did not finish, so four confirmed findings rest on one lens and are
marked.

Counts: 83 findings -- 31 confirmed, 12 upheld with one lens dissenting, 4 refuted, 36
low-severity and unverified.

**These are hypotheses, not defects.** The adversarial pass refuted four findings that read as
solid; the confirmations get the same treatment. `artifacts/todo_stack.md` item 06-03 dispositions
every entry below. Identifiers here are stable and are what that ledger cites.

## Confirmed

Both verifier lenses upheld these.

### identity/core-model-contradicted-by-ruling-of-record

*high · contradiction · bears on: (f) core model NWB data -> AI skills -> JNWB tools -> analysis -> verification*

The target's core model is a linear chain in which analysis reaches JNWB tools through AI skills. The repository's own ruling of record states the opposite topology: two parallel first-class entry paths, with an explicit denial that the researcher path runs through the AI layer.

Receipt: artifacts/direction.md:8-18 — "JNWB is a Python toolbox for reliable analysis of Neurodata Without Borders datasets, / designed for direct use by researchers and reliable composition by AI agents." / "Both are first-class entry paths. A researcher does not reach the operations through the / AI layer:" followed by the diagram " / researcher \ / NWB data -----> -----> JNWB operations -----> verification / \ AI skills /". Also artifacts/direction.md:24-26: "The core is the package. It stays scientifically useful with no agent present."

### identity/dataset-agnostic-contradicted-by-compression-module

*high · contradiction · bears on: (a) dataset-agnostic toolbox; the "Dataset-agnostic" headline the deck reuses from README*

`compress_fp32` is a public exported symbol whose implementation hardcodes one corpus's NWB layout and whose module docstring reasons about "these files" and "this corpus". It fails the repository's own boundary test ("generic — it is not about one dataset's structure").

Receipt: jnwb/compression.py:107-108 — `SPIKE_TRAIN_PATH = "processing/spike_train/spike_train_data/data"` and `CONVOLVED_PATH = "processing/convolved_spike_train/convolved_spike_train_data/data"`; jnwb/compression.py:93 — `_LFP_MUAE_RE = re.compile(r"(probe_\d+_(?:lfp|muae))(?:/\1_data)?/data$")`; jnwb/compression.py:472 — `ts_paths = ["acquisition/probe_0_lfp", "processing/spike_train/spike_train_data"]`; jnwb/compression.py:59-60 — "no kernel parameters are recorded anywhere / in these files or this codebase"; jnwb/compression.py:550-551 — "IRREVERSIBLE DATA LOSS on this corpus". Public: probe run against C:\workspace\jnwb (provenance asserted, jnwb.__file__ = C:\workspace\jnwb\jnwb\__init__.py, …

### identity/mermaid-diagrams-do-not-render-on-the-site

*high · contradiction · bears on: durable assets 2, 3, 4, 5, 6, 10 (every planned diagram) and the principle that diagrams become maintained documentation assets*

All five diagrams currently in docs/ are mermaid fences, and mkdocs is not configured to render mermaid. The built site ships them to readers as raw `graph TD` source text inside a code block.

Receipt: Five fences: docs/01_architecture_and_philosophy.md:15, docs/03_representational_similarity_jrsa.md:11, docs/05_artifact_detection_and_repair.md:17, docs/08_directed_connectivity_and_information.md:11, docs/09_decoding_and_visual_qc.md:11 (all ```mermaid). Config: `grep -n "custom_fences|mermaid" mkdocs.yml` exits 1 (no match); mkdocs.yml declares `- pymdownx.superfences` with no custom_fences block. Built output: `grep -o '.\{0,180\}graph TD.\{0,120\}' site/01_architecture_and_philosophy/index.html` returns `<div class="highlight"><pre><span></span><code>graph TD`, and `grep -c "mermaid" site/01_architecture_and_philosophy/index.html` returns 0. Local site build timestamp: site/index.html,…

### skills/relative-power-result-claim-false

*high · contradiction · bears on: Slide 11 ("tested tool performs what") and the core model's verification step; the claim that skills are checked against live exports*

skills/jnwb-lfp-spectral/SKILL.md:35 tells an agent that `relative_power` names its estimand in the return value. It does not: the function returns a bare numpy.ndarray with no model field and no metadata of any kind. An agent following the row would look for something that does not exist.

Receipt: skills/jnwb-lfp-spectral/SKILL.md:35: "- `jnwb.relative_power(power, baseline, *, model=\"mean_of_ratios\", axis=None, device=\"cpu\")`: Power against baseline under an explicit estimand. `\"mean_of_ratios\"` and `\"ratio_of_means\"` are different quantities, not two routes to one; the model is named in the result." Probe scratchpad/probe_relative_power.py -> signature: (power, baseline, *, model: str = 'mean_of_ratios', axis=None, device: str = 'cpu') -> numpy.ndarray {'model': 'mean_of_ratios'} -> ndarray shape= (5, 10) | has .model: False {'model': 'ratio_of_means', 'axis': 0} -> ndarray shape= (10,) | has .model: False The companion `aggregate_to_db` also returns a bare ndarray (probe_a…

Single verifier lens only; the second did not complete.

### skills/no-authorization-concept-in-skills

*high · gap · bears on: Target claim: "the AI requires authorization, is limited to provided data"*

There is no authorization or permission-gating concept anywhere in the skills surface. A case-insensitive grep for authoriz/authoris/permission/consent/approval/human-in-the-loop over skills/ returns hits in only one file, jnwb-fact-action, and both are about a repository document (artifacts/fact_stack.md), not about data access, tool invocation or analysis. The eight other skills contain none. Meanwhile all 9 agents/openai.yaml manifests set `allow_implicit_invocation: true`.

Receipt: Grep `(?i)authori[sz]|permission|consent|approval|human-in-the-loop` over C:\workspace\jnwb\skills -> the only authorization hits are: skills\jnwb-fact-action\SKILL.md:16: "2. `artifacts/fact_stack.md` (human-authorized durable facts)" skills\jnwb-fact-action\SKILL.md:25: "`fact_stack.md` is strictly human-authorized. Agents may read, test, and challenge facts using evidence, but MUST NOT autonomously add, edit, or delete facts." skills\jnwb-fact-action\SKILL.md:49: "- No drive-by edits, cosmetic refactoring, or unauthorized API expansions." All nine manifests, e.g. skills/jnwb/agents/openai.yaml:5-6: "policy:" / " allow_implicit_invocation: true". Package-wide: Grep `(?i)authoriz|authoris|…

### doc-assets/mermaid-renders-as-source-text

*high · contradiction · bears on: Durable assets 2, 5, 6, 10 (every diagram asset) and the published documentation site*

The five mermaid diagrams in the published docs render as syntax-highlighted code blocks, not diagrams: mkdocs.yml declares pymdownx.superfences with no mermaid custom_fences and loads no mermaid JavaScript.

Receipt: mkdocs.yml:47 ' - pymdownx.superfences' (no child keys) and mkdocs.yml:33-34 'extra_javascript:' / ' - https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js' (the only script). Mermaid blocks: docs/01_architecture_and_philosophy.md:15 '```mermaid', docs/03_representational_similarity_jrsa.md:11, docs/05_artifact_detection_and_repair.md:17, docs/08_directed_connectivity_and_information.md:11, docs/09_decoding_and_visual_qc.md:11. Corroboration from the generated site (built today, site/01_architecture_and_philosophy/index.html mtime 'Sep 19 11:52'): `grep -c mermaid` returns 0, and the rendered markup is '<div class="highlight"><pre><span></span><code>graph TD\n NWB[NWB 2.0+ Files / HD…

### reliability/jrsa-holm-silently-becomes-bh

*high · contradiction · bears on: Slide 10's claim that the suite enforces 'rejection rather than plausible assignment when an estimator is unsupported'*

When statsmodels is not importable, jnwb.jrsa returns Benjamini-Hochberg q-values for correction='holm' (and for 'fdr_by' and 'holm-sidak') while still recording parameters['correction'] == 'holm'. The run is corrected one way and documented another. No test detects this; the test that guards corrections asserts only the recorded label.

Receipt: Code: jnwb/jrsa.py:1039-1045 ` except ImportError:` / ` if m_lower == "bonferroni":` / ` q = np.minimum(p_flat * len(p_flat), 1.0)` / ` else:` / ` # Fallback BH via unified statistics module` / ` from jnwb.statistics import StatisticalAnalysis` / ` q = StatisticalAnalysis.fdr_correct(p_flat, method="bh")`. Probe (scratchpad/probe_holm.py, run as `PYTHONPATH="C:\workspace\jnwb" .venv/Scripts/python.exe .../probe_holm.py`), actual output: ``` jnwb.__file__ = C:\workspace\jnwb\jnwb\__init__.py jnwb.__version__ = 0.2.5 statsmodels: ABSENT -> No module named 'statsmodels' p = [0.001 0.008 0.02 0.04 0.3 ] q(holm) = [0.005 0.02 0.033333 0.05 0.3 ] q(fdr_bh) = [0.005 0.02 0.033333 0.05 0.3 ] holm =…

### public-claims/release-notes-declare-python-3-10

*high · contradiction · bears on: Public claim: Python version support (GitHub Release notes for v0.2.5 vs pyproject.toml requires-python and published PyPI metadata)*

The published GitHub Release notes for v0.2.5 tell readers the release supports "Python 3.10 through 3.14." The package as actually published declares `requires-python = ">=3.12"`. Python 3.10 and 3.11 are excluded.

Receipt: Command: `gh release view v0.2.5 --json body,tagName,publishedAt` (tagName v0.2.5, publishedAt 2026-09-19T16:31:06Z). Body ends: "Install: `pip install jnwb==0.2.5`. Python 3.10 through 3.14. No API removals beyond those\nlisted under Removed and Deprecated in the changelog." || C:\workspace\jnwb\pyproject.toml:17 `requires-python = ">=3.12"` || Command: `curl -s https://pypi.org/pypi/jnwb/0.2.5/json` -> `version: 0.2.5`, `requires_python: '>=3.12'`, `classifiers: ['Programming Language :: Python :: 3', '... :: 3.12', '... :: 3.13', '... :: 3.14']`.

### public-claims/api-md-skills-url-typed-function

*high · contradiction · bears on: Public claim: docs/api.md is the authoritative Public API page ("every symbol in jnwb.__all__"), linked from README and from docs/agents.md as what an agent should read*

The published Public API page lists `jnwb.SKILLS_URL` with type `function` and the built-in `str` constructor signature as its description. `jnwb.SKILLS_URL` is a `str` instance, not a callable.

Receipt: C:\workspace\jnwb\docs\api.md:15 `| jnwb.SKILLS_URL | function | *str(object='') -> str str(bytes_or_buffer[, encoding[, errors]]) -> str* |` || Executed probe (provenance asserted): `PROVENANCE OK: C:\workspace\jnwb\jnwb\__init__.py 0.2.5` then `SKILLS_URL = 'https://github.com/HNXJ/jnwb/tree/v0.2.5/skills' type: str` || C:\workspace\jnwb\jnwb\__init__.py:27 `SKILLS_URL = f'https://github.com/HNXJ/jnwb/tree/v{__version__}/skills'` || Live on the published site: `curl -s -L https://jnwb.readthedocs.io/en/latest/api/` returns `jnwb.SKILLS_URL function str(object='') -> str str(bytes_or_buffer[, encoding[, errors]]) -> str` || Root cause, C:\workspace\jnwb\scripts\generate_api_md.py:126-133 `…

### identity/human-control-stated-as-caller-control-not-human-control

*medium · gap · bears on: (b) scientific choices and interpretation remain explicit and human-controlled*

The substance of (b) is documented, but as "caller" / "project code" / "downstream" control, never as human control. The word "human" appears nowhere in docs/. The human-vs-AI distinction the deck needs is asserted in no file.

Receipt: `grep -rn "human" README.md docs/*.md jnwb/*.py -i` returns exactly one line: jnwb/paths.py:272 "what: Human-readable description, e.g. ``\"NWB session directory\"``." What is stated instead: README.md:18 "Task structure, condition codes, and experimental hypotheses stay in project code"; artifacts/fact_stack.md:46-51 "## Scientific choices stay downstream" ... "Project-specific scientific choices — which comparisons to run, which areas or conditions / define a cohort, what constitutes a response — remain in the consuming project's / repository. jnwb supplies primitives; it does not encode one study's design."; docs/07_statistical_inference_and_nulls.md:14 "- **Caller Control**: Callers can…

### dynamic-conversion/compress-fp32-is-nwb-to-nwb-only

*medium · gap · bears on: Goal claim: conversion into NWB; and the capability-map durable asset*

`compress_fp32` is the only public export that produces an NWB-shaped file on disk, and it is an NWB-to-NWB (HDF5-to-HDF5) rewrite. It requires an HDF5 source and fails immediately on a non-HDF5 input, so it cannot serve as a conversion path from non-NWB data.

Receipt: Command: `<venv>/python.exe <scratchpad>/probe_dim2.py`. Output: ``` compress_fp32 SIGNATURE: (src: 'str | Path', dst: 'str | Path | None' = None, *, drop_convolved: bool = False, verify: bool = True, n_check: int = 200000, overwrite: bool = False) -> dict compress_fp32 MODULE: jnwb.compression compress_fp32 ON NON-HDF5: OSError: Unable to synchronously open file (file signature not found) ``` C:\workspace\jnwb\jnwb\compression.py:1 `"""fp32 + chunk + compress an NWB file, losslessly except a documented float32 cast.` The docs scope this correctly: C:\workspace\jnwb\docs\04_spectral_analysis_and_tfr.md:322 "**`compress_fp32` (`jnwb.compression`)**: On-disk NWB conversion — rewrites electric…

### dynamic-conversion/no-skill-routes-conversion

*medium · gap · bears on: Goal claim: "jnwb has skills for adapting and adopting new datasets and or translate datasets into nwb files"; and the skill-to-tool execution diagram*

None of the nine skills routes a conversion or ingestion task. The router's task matrix has eight rows and no conversion row; the data skill's routing matrix lists only read/inspect/QC primitives plus `compress_fp32`.

Receipt: Directory listing of C:\workspace\jnwb\skills shows nine skills (jnwb, jnwb-connectivity, jnwb-fact-action, jnwb-figures, jnwb-lfp-spectral, jnwb-nwb-data, jnwb-population, jnwb-spiking, jnwb-statistics). Grep for `convert|conversion|write|pynwb|ingest|translat|non-NWB|create NWB` (case-insensitive) over C:\workspace\jnwb\skills returned only: skills\jnwb-figures\SKILL.md:21 and :39 (figure export), skills\jnwb-lfp-spectral\SKILL.md:34 (dB conversion), skills\jnwb-nwb-data\SKILL.md:28 (`calibrated by `conversion` and `offset``), and skills\jnwb-nwb-data\SKILL.md:92 "**NWB compression contract:** `compress_fp32` converts on-disk electrical series to fp32". Router matrix: C:\workspace\jnwb\sk…

### skills/two-skills-carry-no-stop-language

*medium · gap · bears on: Slide 12: "reliable failure is a feature"*

Seven of nine skills carry explicit stop/decline/non-identifiability language; two carry none. jnwb-population and jnwb-figures contain zero occurrences of stop, decline, refuse, unavailable, non-identifiable, accepted=False, raise, censored, or missing. Their invariants are prescriptive ("must", "Never", "Always") -- they tell an agent what to do, never when to stop or report that a question is unanswerable.

Receipt: Per-file count of lines matching `\bstop\b|declin|refus|unavailable|non-identifiab|accepted=False|\braise|censored|report unavailable|not identifiable|surface the conflict|missing`: 1 jnwb-connectivity/SKILL.md 2 jnwb-fact-action/SKILL.md 0 jnwb-figures/SKILL.md 5 jnwb-lfp-spectral/SKILL.md 6 jnwb-nwb-data/SKILL.md 0 jnwb-population/SKILL.md 1 jnwb-spiking/SKILL.md 1 jnwb-statistics/SKILL.md 1 jnwb/SKILL.md Strongest existing language, skills/jnwb-lfp-spectral/SKILL.md:50: "0. **Depth estimates report non-identifiability rather than a number.** `vflip`, `xflip` and `zflip` all return `accepted=False` when the data does not support the motif, and `label_layers` then labels every channel `'na…

Single verifier lens only; the second did not complete.

### skills/ontology-subsystem-unreachable-from-any-skill

*medium · gap · bears on: Core model "NWB data -> AI skills -> JNWB tools -> analysis -> verification"; durable asset #3 (scientific-semantics distinction diagram)*

The entire jnwb.ontology vocabulary -- Question, Query, Dataset, AlignedDataset, Alignment, EpochCollection, Result, Interpretation, Lineage, Provenance, Figure, 11 public types whose docstrings describe the scientific-semantics layer -- is named by no skill at all. It is excluded from routing by design, with the stated reason that an agent "reaches these by constructing what a workflow asks for", but no skill contains such a workflow.

Receipt: Probe scratchpad/probe_unrouted_detail.py -> Question module=jnwb.ontology :: Scientific hypothesis: what are we asking? Query module=jnwb.ontology :: Data selection rules: what subset of data? Dataset module=jnwb.ontology :: Aggregated query result: immutable collection of data. Result module=jnwb.ontology :: Analysis output: statistics, provenance, lineage. Interpretation module=jnwb.ontology :: Meaning and claims: what does the result mean? Lineage module=jnwb.ontology :: Artifact dependencies: where did this come from? Provenance module=jnwb.ontology :: Execution context and metadata. Figure module=jnwb.ontology :: Visualization: rendering of Result + Interpretation. Exclusion rationale…

Single verifier lens only; the second did not complete.

### skills/no-nwb-conversion-anywhere

*medium · gap · bears on: Target claim: "Dynamic: skills adapt to new datasets, including translating non-NWB datasets into NWB files via pynwb"*

No skill routes any NWB-writing or format-conversion operation, and the public API exports none. The word pynwb does not appear in any SKILL.md. The only conversion in the skills surface is `compress_fp32`, which converts an existing NWB file's dtype in place.

Receipt: `grep -rn -i "pynwb\|convert\|translat\|non-NWB\|ingest" skills/` returns 4 lines, none of them a conversion route: jnwb-connectivity/SKILL.md:22 ("cannot be converted to a sample shift"), jnwb-figures/SKILL.md:21 and :38 ("Never convert text to outlines"), and jnwb-nwb-data/SKILL.md:92 ("`compress_fp32` converts on-disk electrical series to fp32"). Probe scratchpad/probe_conversion.py, filtering the live `jnwb.__all__` (156 names) by `(?i)nwb|convert|write|create|build|to_|from_|import|export|ingest`, returns 14 names -- 3 NWB exception classes and 11 unrelated (aggregate_to_db, apply_tight_auto_axis, bad_channels_from_correlation, build_inner_validation_partitions, build_permutation_plan,…

Single verifier lens only; the second did not complete.

### skills/workflow-blocks-never-executed-by-the-harness

*medium · risk · bears on: "configured != executed != verified"; the skills harness's own coverage*

No test in the repository executes any SKILL.md python block. The signature harness parses only backticked rows inside section 2, so the ```python Minimal Workflow blocks in section 4 -- the code an agent is most likely to copy -- are entirely unchecked. I executed all 8 of them; 7 ran clean and the 8th failed only for a missing data file.

Receipt: `grep -rn "exec(" tests/ | grep -i skill` -> "(none)". The one test that reads a SKILL.md near a python fence, tests/test_docs_nwb_workflow.py:63-70, extracts the fence from README, not from SKILL: "blocks = re.findall(fence, README.read_text(encoding=\"utf-8\"), re.S)". The parser's scope, tests/test_skills_validation.py:99-103: "section = _routing_matrix_section(skill_text)" ... "for match in re.finditer(r\"`jnwb\\.((?:\\w+\\.)*\\w+)\\(\", section):". Probe scratchpad/probe_run_workflows.py (each block run in its own subprocess with provenance asserted): jnwb OK | jnwb-connectivity OK | jnwb-fact-action NO python block | jnwb-figures OK | jnwb-lfp-spectral OK | jnwb-nwb-data FAIL rc=1 (Fi…

Single verifier lens only; the second did not complete.

### doc-assets/asset01-capability-map-split-and-unchecked

*medium · gap · bears on: Durable asset 1: JNWB capability map*

No single maintained capability map exists. Three partial candidates exist with different maintenance status: docs/api.md (generated, gate-enforced), README.md's Capabilities table (one-directionally test-checked), and docs/01 section 4 'Module Map & Architecture Summary' (nothing checks it).

Receipt: docs/api.md:3 'All 156 core functions, classes, and constants exported in the top-level jnwb namespace.' and :5 'Generated from `jnwb.__all__`, `inspect.signature`, and runtime docstrings. Do not edit by hand -- run `python scripts/generate_api_md.py --write`.' | scripts/harness_gate.py:263 '"""Gate 9 (API Set Equality): assert documented API == set(jnwb.__all__), both directions.' | tests/test_generated_files_are_byte_stable.py:28 '"docs/api.md",' | README.md:24 '## Capabilities' | tests/test_readme_smoke.py:110-115 'def test_readme_capability_table_symbols_exist():' ... 'assert hasattr(jnwb, symbol), f"README capability table references missing jnwb.{symbol}"' | docs/01_architecture_and_p…

### doc-assets/asset02-code-docs-skills-diagram-absent

*medium · gap · bears on: Durable asset 2: code-documentation-skills architecture diagram*

No code-documentation-skills architecture diagram exists in docs/. The nearest content is ASCII text in artifacts/direction.md, which is not published: mkdocs docs_dir is docs/ and artifacts/ appears in no nav entry.

Receipt: artifacts/direction.md:30 ' code implements docs explain skills route tests verify' and :35 ' scientific intent -> documented API <-> code <-> tests' and :39 ' skill -> discover, constrain, compose, execute, verify' | mkdocs.yml:8 'docs_dir: docs' and mkdocs.yml:53-87 (the whole nav) lists no artifacts/ page | docs/01_architecture_and_philosophy.md:16-31 (the only architecture mermaid) contains no 'skill' node; `grep -rn skill -i docs/*.md docs/tutorials/*.md` returns hits only in docs/agents.md, docs/api.md:15, docs/index.md:54 and docs/install.md:11.

### doc-assets/asset03-semantics-distinction-diagram-absent

*medium · gap · bears on: Durable asset 3: scientific-semantics distinction diagram (spikes != MUAe, power != dB)*

No scientific-semantics distinction diagram exists. The distinctions are stated in prose in three maintained places and shown in one PNG panel, but there is no diagram asset.

Receipt: docs/common_mistakes.md:9 '## 1. Averaging Decibels Instead of Power (Jensen's Inequality)' | docs/01_architecture_and_philosophy.md:60 '* **Physical Classes**: Spikes (SUA/MUA), Multi-unit activity envelopes (MUAe), Local Field Potentials (LFP), and behavioral covariates ... represent distinct physical observables.' | CONTRIBUTING.md:197 '1. **Signal Class Independence**: SUA/SPK, MUA, and LFP represent physically distinct observables.' | skills/jnwb/SKILL.md:29-30 | the nearest visual is docs/assets/figures/fig06_aggregate_to_db.png, drawn by docs/generate_figures.py:302 'labels = ["Mean of Ratios\n(equal weight)", "Ratio of Means\n(power weighted)", "Mean of Decibels\n[WRONG Jensen Error…

### doc-assets/asset04-test-hierarchy-diagram-absent

*medium · gap · bears on: Durable asset 4: reliability / test hierarchy diagram*

No reliability or test-hierarchy diagram exists anywhere in the repository. The hierarchy exists only as a prose bullet list in CONTRIBUTING.md and as gate functions in scripts/harness_gate.py.

Receipt: `grep -i 'hierarchy'` over the repo (excluding site/) returns exactly three non-code hits: CONTRIBUTING.md:159 '### Repository Hierarchy' (a directory tree, not tests), skills/jnwb/SKILL.md:30 'Estimand & Causal Hierarchy', artifacts/capability_review_0.1.7.md:137 'scipy.cluster.hierarchy'. The test taxonomy lives at CONTRIBUTING.md:130 'Every module must be protected by deterministic test coverage in `tests/`. Tests must include diagnostic probes covering:' followed by nine bullets (Identity, Sign, Scale, Shape, Boundary, State Isolation, Composition, Numerical Stability, Regression Tests) at CONTRIBUTING.md:132-140. Gates are functions in scripts/harness_gate.py (e.g. :48 'Gate 1 (Frozen …

### ai-plumbing/agent-roles-exist-but-ship-nowhere

*medium · gap · bears on: Durable asset "human-AI-JNWB responsibility diagram"; the deck's human/AI roles slide*

A five-role structure (authority, critic, actor, verifier, docs-harness) is fully specified with purposes, read-only constraints and a delegation packet contract, but it lives only in artifacts/ and skills/, is referenced from no page in docs/, and artifacts/ is pruned from the sdist.

Receipt: Files present: `ls C:\workspace\jnwb\artifacts\agents\` -> `actor.md authority.md critic.md docs-harness.md verifier.md`. Role definitions e.g. C:\workspace\jnwb\artifacts\agents\actor.md:20-22 `- **Cannot Be Sole Verifier**:\n $$\\text{actor} \\ne \\text{sole verifier}$$`; authority.md:19 `- **Read-Only**: No file modifications, no git commits, no execution of mutating commands.`; critic.md:19 `- **Read-Only**: Generates diagnostic probes, inspection scripts, and reports. Never applies production fixes or modifies repository files.` Delegation contract: C:\workspace\jnwb\skills\jnwb-fact-action\SKILL.md:66 `ROLE: authority | critic | actor | verifier | docs-harness`. Every reference to the…

### ai-plumbing/generator-boundary-is-naming-not-enforcement

*medium · risk · bears on: Target claim "does not generate data"; the plan's request for a precise boundary*

The boundary is a naming and documentation convention, not an output-level mechanism. jnwb.testing is importable by any agent, a docs page in the site navigation advertises it as a signal generator, and the only two NWB writers in the package are both inside jnwb/testing/. No gate scans outputs for synthetic values.

Receipt: Advertised in a nav page: C:\workspace\jnwb\docs\10_operation_specifications.md:92 `| \`testing.synth\` | \`jnwb.testing.synth\` | ... | Generates synthetic signals (laminar crossover motifs, AR noise, pink/white noise, shared common response). |` (page is in mkdocs.yml:80 `- Operation Specifications: 10_operation_specifications.md`). NWB writers: `grep -rn "NWBHDF5IO(.*\"w\"" jnwb/ --include=*.py` -> `jnwb/testing/nwb_fixtures.py:408: with NWBHDF5IO(str(path), "w") as io:` and `jnwb/testing/synth.py:693: with pynwb.NWBHDF5IO(str(p), "w") as io:`. The stated boundary: C:\workspace\jnwb\docs\01_architecture_and_philosophy.md:87 `* Outputs must never contain synthetic or placeholder values. S…

### ai-plumbing/no-nwb-conversion-asset

*medium · gap · bears on: Target claim "Dynamic: skills adapt ... including translating non-NWB datasets into NWB files via pynwb"*

No MCP tool, no skill routing row, and no public export converts a non-NWB dataset into NWB. The only code in the package that writes an NWB file is the synthetic test-fixture builder.

Receipt: MCP surface is ingest-only (three tools listed above; docs/agents.md:24 `Three tools, all of them ingest: the server reads NWB files and returns what it found.`). Skills: `grep -rn -i "convert\|to_nwb\|non-nwb\|NWBFile(" skills/*/SKILL.md` -> only unrelated hits (`skills/jnwb-figures/SKILL.md:21` about text outlines, `skills/jnwb-nwb-data/SKILL.md:92` about `compress_fp32` converting an existing series to fp32, `skills/jnwb-connectivity/SKILL.md:22` about lag units). Writers: `grep -rn "NWBHDF5IO(.*\"w\"" jnwb/ --include=*.py` -> `jnwb/testing/nwb_fixtures.py:408` and `jnwb/testing/synth.py:693` only.

### reliability/contributing-taxonomy-is-a-different-one

*medium · contradiction · bears on: Slide 10's five-tier structure: primitive -> property -> composition -> regression -> adversarial calibration*

The only durable written account of jnwb's testing expectations is CONTRIBUTING.md's 'Testing rule', and it is a flat nine-item list of probe classes, not a five-tier hierarchy. Two of the five tier names appear in it; 'primitive', 'property' and 'adversarial calibration' do not appear as tiers anywhere in the repository.

Receipt: CONTRIBUTING.md:128 `## Testing rule`; :130 "Every module must be protected by deterministic test coverage in `tests/`. Tests must include diagnostic probes covering:"; the list at :132-:140 is **Identity**, **Sign**, **Scale**, **Shape**, **Boundary**, **State Isolation**, **Composition**, **Numerical Stability**, **Regression Tests**. The word "primitive" appears in CONTRIBUTING.md only at :107 `1. **Small Composable Primitives**: Functions perform one well-defined operation.` — a code rule, not a test tier. "Adversarial" appears only inside the regression item at :140 "Every corrected bug or edge case must be accompanied by an adversarial regression test." Grep of AGENTS.md for `primitiv…

### reliability/hierarchy-exists-only-in-suite-shape

*medium · gap · bears on: Slide 10's claim that the suite has a tier structure, and durable asset #4*

Nothing mechanical encodes the hierarchy. There are no custom pytest markers, no naming convention on files or classes that names a tier, and CI runs the suite as one flat invocation. The tiers are recoverable only by reading test bodies.

Receipt: Markers: grep for `pytest\.mark\.\w+` across tests/test_*.py returns only `pytest.mark.parametrize` and `pytest.mark.skipif` — no third marker name in any of the ~210 occurrences. pyproject.toml:105-107 is the entire pytest config — `[tool.pytest.ini_options]` / `pythonpath = ["."]` / `testpaths = ["tests"]` — with no `markers = ` key. Class names: grep for `^class Test(Primitive|Property|Composition|Regression|Adversarial|Calibrat)` across tests/test_*.py returns "No matches found". Filenames: the leading token after `test_` is topical or narrative (`docs` x7, `no` x4, `jrsa` x4, `xflip` x3, `skill` x3, ...), never a tier name. CI: .github/workflows/workflow.yml:65 ` pytest -v tests/` is t…

### public-claims/no-gate-reads-release-notes

*medium · gap · bears on: Goal claim: public statements are reliable; the repository's own harness gates every other surface that states Python support*

Every surface that states Python support is checked by a gate except the GitHub Release body, which is hand-written per CONTRIBUTING.md and read by nothing.

Receipt: C:\workspace\jnwb\tests\test_readme_smoke.py:136-140 `declared_min = re.search(r'requires-python\s*=\s*">=([\d.]+)"', pyproject)` ... `assert re.search(rf"Requires Python \*\*{re.escape(minimum)} or newer\*\*", text)`; ran `python -m pytest tests/test_readme_smoke.py -q` -> `6 passed in 3.39s`. || C:\workspace\jnwb\scripts\harness_gate.py:180-182 `PYTHON_FLOOR = "3.12"` / `PYTHON_SUPPORTED = ("3.12", "3.13", "3.14")` / `PYTHON_CI_REQUIRED = ("3.12", "3.14")`, enforced against pyproject, the CI matrix and .readthedocs.yaml (harness_gate.py:506-516 docstring: "1. `requires-python` declares PYTHON_FLOOR ... 3. The CI matrix contains every version in PYTHON_CI_REQUIRED ... 4. `.readthedocs.yaml…

### public-claims/readme-omits-agent-surface

*medium · gap · bears on: Goal claim: "JNWB: Dynamic AI-Assisted Skills and Analysis of NWB"; core model "NWB data -> AI skills -> JNWB tools -> analysis -> verification"*

The README — which is verbatim the PyPI project description — never mentions MCP or skills. Its only agent-facing sentence is one line in the Contributing section pointing at a GitHub file that does not ship in the wheel.

Receipt: Executed probe over README.md: `README mentions 'MCP': False | 'skill': False | 'agent': True | 'AI': True`. || The sole match, README.md:135 `If you are an AI agent, read [AGENTS.md](https://github.com/HNXJ/jnwb/blob/main/AGENTS.md) first.` || C:\workspace\jnwb\docs\agents.md:13-14 records that neither ships in the wheel: `| Skills | **no** | The routing and scientific safeguards |` / `| `AGENTS.md` | **no** (in the sdist) | Repository map, working rules, recipes |` || The agent surface exists and is documented elsewhere: docs/agents.md:33-37 lists three MCP tools, and an executed probe confirms them live — `mcp_server public names: ['event_tools','get_event_codes_and_timings','inspect_nwb…

### evaluation-and-roadmap/p0-is-a-hypothesis-and-constraints-not-a-design

*medium · gap · bears on: Slide 15's ten scoring axes; Durable Asset #9*

The nearest thing to an AI-interface benchmark design is artifacts/planned_post_0.2.5.md P0, which states a hypothesis and pre-registration constraints and explicitly says the design work has not been done. Of Slide 15's ten scoring axes, four are recorded (scientific correctness, out-of-scope rejection, and -- via the nine semantic dimensions -- parameter semantics and provenance in part); six are not recorded anywhere: tool selection, reproducibility, runtime, token cost, prompt-paraphrase robustness, dependency drift.

Receipt: artifacts/planned_post_0.2.5.md:12-29. Line 12: "## P0. Does the routing layer help? (hypothesis, ruled 2026-09-17)". Lines 14-16: "H: an agent given JNWB's skills and tested operations outperforms the same agent given raw repository access, on a predefined set of NWB analysis tasks." Line 19: "The work is to state the task set and measure it." Lines 21-26: "the task set is fixed and frozen before measurement; both arms get the same model and the same budget; out-of-scope tasks are included, where the correct outcome is a refusal and an answer scores zero; correctness is judged on the semantic dimensions of 05-85 -- shape, units, axes, estimator, aggregation, failure, randomness, identity, …

### evaluation-and-roadmap/roadmap-and-direction-are-unindexed

*medium · gap · bears on: Slide 17's near-term development direction; the claim that the plan's assets become maintained repository material*

artifacts/planned_post_0.2.5.md has zero inbound references from anywhere in the repository, and artifacts/direction.md has exactly two, one of which is broken. Neither appears in AGENTS.md's orientation table, CONTRIBUTING.md, README.md or docs/. An agent or reader following the repository's own map never learns the direction ruling or the roadmap exists.

Receipt: Grep for `direction\.md|planned_post` over the repository (excluding site/, _build/, .venv/, dist/, jnwb.egg-info/, .git/) returns exactly two lines: artifacts\todo_stack.md:38 "`artifacts/direction.md` under \"Skill behaviour\"): a skill routes to an operation or it" and artifacts\planned_post_0.2.5.md:8 "Everything here is subject to `artifacts/direction.md`, which sets what the package is". AGENTS.md:20-38 is the orientation table; it lists `artifacts/todo_stack.md` (line 28), `artifacts/fact_stack.md` (29), `artifacts/benchmarks/` (30) and `artifacts/agents/` (27), and neither direction.md nor planned_post_0.2.5.md.

### ai-plumbing/writes-nothing-guard-is-narrow

*low · risk · bears on: docs/agents.md public claim that the MCP server writes nothing*

The "it writes nothing" claim is true by reading the code today, but the only mechanical guard is a source scan for the literal string write_text in mcp_server/*.py, which would not catch open(path, "w"), an h5py write mode, or any other writer.

Receipt: Claim: C:\workspace\jnwb\docs\agents.md:24 `Three tools, all of them ingest: the server reads NWB files and returns what it found. It writes nothing, and it has no tool that registers another tool.` Code read: jnwb/mcp_server/nwb_tools.py:53 `with h5py.File(str(path), 'r') as f:`; jnwb/mcp_server/event_tools.py:83 `with nwb_read_io(str(path), load_namespaces=True) as io:` and jnwb/nwb_io.py:144 `def nwb_read_io(path: Any, mode: str = "r", **kwargs: Any) -> Iterator[NWBHDF5IO]:` (mode defaults to read). Guard: C:\workspace\jnwb\tests\test_mcp_server.py:261-265 `for module in sorted(package_dir.glob("*.py")):\n source = module.read_text(encoding="utf-8")\n self.assertNotIn(\n "write_text", so…

### public-claims/install-md-states-no-python-requirement

*low · gap · bears on: Public claim: Python version support, consistency across the three installation surfaces*

docs/install.md — the page docs/index.md advertises as "setup and verification" — states no minimum Python version anywhere. README.md and docs/index.md both state it.

Receipt: Command: `grep -n -i "python" docs/install.md` -> only `docs/install.md:91:Run the verification snippet in your Python environment:` and `docs/install.md:93:```python` — no version statement in 101 lines. || README.md:41 `Requires Python **3.12 or newer**. Tested in CI on 3.12 and 3.14.` || docs/index.md:25 `Requires Python 3.12 or newer; CI tests 3.12 and 3.14. See [Installation](install.md).` || docs/index.md:50 `- [Installation](install.md) — setup and verification`.

## Upheld with dissent

One lens upheld and one refuted. The dissent is quoted; read it before acting.

### identity/agents-vocabulary-rule-forbids-the-planned-doc-assets

*high · contradiction · bears on: (c)/(d)/(e) AI-assisted identity, and durable assets 2, 5, 8 (architecture, skill-to-tool execution, human-AI-JNWB responsibility diagrams)*

AGENTS.md forbids naming agents anywhere in docs/ — the exact place the plan says the AI-facing diagrams must live as maintained documentation. The rule is already violated by the published site in three places, and no gate or test enforces it.

Receipt: AGENTS.md:9-15 — "**Leave no process-authorship narrative in the library surface.** Harness vocabulary / (agents, assistants, orchestration tooling) is named only in four places: `skills/`, this / file, one line in `README.md`, and `CONTRIBUTING.md`. Not in `jnwb/`, `tests/`, `scripts/`, / `docs/`, `CHANGELOG.md`, or code comments/docstrings — except **machine-required literals** ... A reader of the library should see a library." Violations on the published site: docs/agents.md:1 "# Analyzing with an Agent" (whole page, in mkdocs.yml:66 nav as "Analyzing with an Agent: agents.md"), docs/index.md:54 "- [Analyzing with an agent](agents.md) — what ships, the MCP server, and the skills", docs/i…

Dissent: The receipt is accurate (I re-verified AGENTS.md:9-15, docs/index.md:54, docs/install.md:11, and the absence of any gate), but the conclusion does not survive. The surveyor concludes the collision "must be resolved before any of assets 2, 5 or 8 is produced" because otherwise the assets "cannot land in docs/". The repository already answered that: docs/agents.md was created by a deliberate human commit (c5e5bcc4, 2026-09-16, "docs: close the loop from 'I have an NWB file' to 'an agent can analy…

### dynamic-conversion/no-public-nwb-write-export

*high · gap · bears on: Goal claim: skills "translate datasets into nwb files via pynwb if they are not" (NWB conversion capability)*

The package exposes 156 public names and not one of them constructs or writes an NWB file. The only export whose name contains a write verb is `save_figure_suite`, which writes matplotlib figures.

Receipt: Command: `C:\workspace\jnwb\.venv\Scripts\python.exe <scratchpad>/probe_dim2.py` (probe asserts provenance first). Output: ``` PROVENANCE OK: C:\workspace\jnwb\jnwb\__init__.py VERSION: 0.2.5 N_ALL: 156 EXPORTS_MATCHING_WRITE_WORDS: ['save_figure_suite'] jnwb.nwb_read_io: AttributeError -> module 'jnwb' has no attribute 'nwb_read_io' jnwb.read_nwb: AttributeError -> module 'jnwb' has no attribute 'read_nwb' jnwb.NWBFile in __all__: False jnwb.NWBHDF5IO in __all__: False ``` Corroborating source: C:\workspace\jnwb\jnwb\__init__.py:193 `__all__ = [` ... :391 `]` — the list contains no NWBFile/NWBHDF5IO/write/convert symbol. C:\workspace\jnwb\pyproject.toml:41-52 `dependencies = [...]` lists `…

Dissent: The statement's load-bearing clause — "not one of them constructs or writes an NWB file" — is false, and the receipt does not support it. The surveyor's method was a regex over export NAMES for write verbs, which cannot detect a writer whose name contains no verb. `jnwb.compress_fp32` IS one of the 156 (`C:\workspace\jnwb\jnwb\__init__.py:223` ` 'compress_fp32',`) and it writes a new NWB file: `C:\workspace\jnwb\jnwb\compression.py:257` ` with h5py.File(src_path, "r") as s, h5py.File(dst_path, …

### dynamic-conversion/only-nwb-writer-is-a-synthetic-data-generator

*high · contradiction · bears on: Goal claims: "translate datasets into nwb files via pynwb" AND "the AI ... is limited to provided data, and DOES NOT GENERATE DATA"*

The only pynwb write path inside the distributed package is a synthetic-recording generator under `jnwb/testing/`, declared module-internal, which fabricates LFP, units and interval tables from an RNG and writes them to an NWB file. It ships in the distribution.

Receipt: C:\workspace\jnwb\jnwb\testing\nwb_fixtures.py:406-409: ``` path.parent.mkdir(parents=True, exist_ok=True) with NWBHDF5IO(str(path), "w") as io: io.write(nwb) return receipt ``` C:\workspace\jnwb\jnwb\testing\nwb_fixtures.py:342-347 `nwb = NWBFile(` ... `session_description="Synthetic multi-table NWB for jnwb fixtures",` / `_add_electrodes(nwb, opts.n_channels)`. C:\workspace\jnwb\jnwb\testing\synth.py:693-694: ``` with pynwb.NWBHDF5IO(str(p), "w") as io: io.write(nwb) ``` Disposition: C:\workspace\jnwb\jnwb\_api_surface.py:59-61 `"testing": "module-internal",` / `"testing.nwb_fixtures": "module-internal",` / `"testing.synth": "module-internal",`. Shipped: command `python -c "import tarfile…

Dissent: The receipt is accurate but the conclusion does not survive, on three independent grounds. (1) THE CENTRAL INFERENCE IS FALSE AS STATED. The surveyor infers "the package's sole NWB writer generates synthetic data rather than converting real non-NWB data." The package has a PUBLIC NWB writer that consumes a real NWB file, generates nothing, and is nowhere synthetic: `C:\workspace\jnwb\jnwb\compression.py:535` `def compress_fp32(`, docstring at :544 "Compress one NWB file: float32 LFP/MUAE, chunk…

### evaluation-and-roadmap/out-of-scope-rejection-has-no-behaviour-to-score

*high · contradiction · bears on: Slide 15's "out-of-scope rejection" scoring axis; the goal claim that the AI "is limited to provided data, and DOES NOT GENERATE DATA"*

P0 requires that out-of-scope tasks score zero for an answer and require a refusal, and direction.md declares that a skill which cannot decline is incomplete. No skill file contains a decline rule. By its own criterion the repository's nine skills are all incomplete on the dimension Slide 15 proposes to score.

Receipt: artifacts/direction.md:46-58: "A skill routes to an operation or it declines. Four cases:" / "supported task -> compose and execute / missing input -> request it / non-identifiable result -> report the failure / unsupported inference -> decline" and line 58 "Declining is a correct outcome, and a skill that cannot decline is incomplete." Grep for `decline` (case-insensitive) over C:\workspace\jnwb\skills returns "No matches found". A wider grep for `declin|refus|unsupported|out-of-scope|stop and|do not answer|cannot answer` over skills/ returns three hits, none of them a decline rule: skills\jnwb-nwb-data\SKILL.md:48 "A name that exists in both `/acquisition` and a processing module is refus…

Dissent: The receipt is accurate but the conclusion does not survive. Three independent checks break it. (1) The literal grep is right and the inference from it is wrong. I re-ran it: Grep `\bdecline\b` (case-insensitive) over C:\workspace\jnwb\skills returns "No matches found". But the surveyor searched for the word and then classified everything it did find as "library refusal". That classification is wrong for at least seven agent-facing rules I read in full, which are exactly direction.md's cases 3 …

### doc-assets/module-map-omits-nwb-entry-points

*medium · stale-record · bears on: Durable asset 1: JNWB capability map; core model 'NWB data -> AI skills -> JNWB tools'*

The docs/01 'Module Map & Architecture Summary' table has 21 module rows and omits 8 modules that own 36 public exports, including the NWB entry points `inspect`, `events`, `event_onsets`, `complex_tfr`, and the whole laminar surface.

Receipt: Probe C:\Users\nejath\AppData\Local\Temp\claude\C--workspace-jnwb\9fe5eb2c-f88f-482a-9c42-d31985bcb551\scratchpad\probe_modulemap2.py (asserts jnwb provenance) output: 'provenance OK: C:\workspace\jnwb\jnwb\__init__.py 0.2.5' / 'public exports: 156 | modules owning them: 29' / 'MODULES THAT OWN PUBLIC EXPORTS BUT HAVE NO ROW IN THE docs/01 MODULE MAP:' / ' continuous 1 exports: [epoch_continuous]' / ' io 2' / ' laminar 8 exports: [VFlipResult, XFlipResult, ZFlipResult, label_layers, vflip, vflip_from_lfp, xflip, zflip]' / ' nwb_events 9 exports: [AmbiguousIntervalTableError, ColumnNotFoundError, EventTable, IntervalTableNotFoundError, InvalidOnsetValueError, NWBEventError, event_onsets, eve…

Dissent: The raw count reproduces, but the conclusion and its bearing do not survive the rest of the repo. WHAT I CONFIRMED (own probe, provenance-asserted): `C:\Users\nejath\AppData\Local\Temp\claude\C--workspace-jnwb\9fe5eb2c-f88f-482a-9c42-d31985bcb551\scratchpad\verify_modulemap.py` -> "provenance OK: C:\workspace\jnwb\jnwb\__init__.py 0.2.5" / "len(__all__): 156" / "doc table rows: 21" / missing modules "continuous 1, io 1, laminar 8, nwb_events 9, nwb_inspect 10, nwb_io 1, rsa 2, tfr 3" = 35 named…

### ai-plumbing/readme-silent-on-mcp-and-skills

*medium · gap · bears on: "AI-assisted" positioning; durable asset "capability map" and "overview diagram for the landing page"*

README.md never mentions the MCP server or the skills. Its Capabilities table has ten rows, all of them library function areas, and no agent/MCP/skills row. The only agent-facing line in the whole README is a pointer to AGENTS.md.

Receipt: Command: `grep -n -i -c "mcp" README.md` -> `0` (exit 1). `grep -n -i "mcp\|skill" README.md` -> no output. `grep -n "MCP|mcp|agent|Agent|skill|Skill" README.md` (Grep tool) -> single hit: `README.md:135: If you are an AI agent, read [AGENTS.md](https://github.com/HNXJ/jnwb/blob/main/AGENTS.md) first.` Capability table at README.md:25-38 rows: NWB discovery & events, NWB metadata & addressing, Spiking, LFP & spectral, Filtering, Statistics, Population & decoding, Connectivity, Quality control, Visualization.

Dissent: The receipt reproduces exactly (README.md:24-37 is a ten-row library-only Capabilities table; `grep -n -i -E "mcp|skill|agent" README.md` returns a single hit, README.md:135 "If you are an AI agent, read [AGENTS.md]..."). But the conclusion is answered twice elsewhere in the repo. (1) The single agent line in README is a written, deliberate decision, not an omission. AGENTS.md:9-11: "**Leave no process-authorship narrative in the library surface.** Harness vocabulary (agents, assistants, orches…

### ai-plumbing/authorization-has-no-mechanism

*medium · risk · bears on: Target claim "the AI requires authorization"*

Nothing in the package enforces authorization. The only occurrence of the word anywhere in jnwb/*.py is a hardcoded False inside a returned metadata dict that no code consumes; the only other authorization language is policy prose in the skills and AGENTS.md.

Receipt: Command: `grep -rn -i "authoriz" jnwb/ --include=*.py` -> single line `jnwb/decoding.py:407: "training_authorized": False,` (inside the `contract` dict returned by `build_representation_ladder`, jnwb/decoding.py:353). Consumers: `grep -rn "training_authorized" --include=*.py --include=*.md .` -> only `./jnwb/decoding.py:407` and `./tests/test_decoding.py:174: assert result["contract"]["training_authorized"] is False`. `build_representation_ladder` is public: probe `python -c "import jnwb; print('build_representation_ladder' in jnwb.__all__)"` -> `True`. Skills side: `grep -rn -i "authoriz" skills/` -> `skills/jnwb-fact-action/SKILL.md:16`, `:25` (`\`fact_stack.md\` is strictly human-authori…

Dissent: The receipt reproduces exactly, but the conclusion drawn from it does not survive the rest of the repository. I re-ran the greps: `jnwb/decoding.py:407: "training_authorized": False,` is indeed the only "authoriz" match under jnwb/, and the only consumers are that line and `tests/test_decoding.py:174: assert result["contract"]["training_authorized"] is False`. A provenance-asserted probe (PYTHONPATH pinned to the checkout; `provenance OK: C:\workspace\jnwb\jnwb\__init__.py`, `version: 0.2.5`) c…

### reliability/suite-size-and-collection-error

*medium · risk · bears on: Any slide or asset stating the size or green status of the suite*

The suite is 118 test_*.py files and 2841 collected tests. Collection is cheap (6-13 s) but does not complete cleanly in the repository's own .venv: one module fails to import because statsmodels, a declared hard dependency, is absent, and pytest aborts collection unless --continue-on-collection-errors is passed.

Receipt: Files: `ls tests/test_*.py | wc -l` -> `118` (plus tests/__init__.py; tests/ has no subdirectories per `find tests -type d -not -name __pycache__` -> `tests`). There is no conftest.py at the repo root or in tests/. Collection: `.venv/Scripts/python.exe -m pytest --collect-only -q` -> `2841 tests collected, 1 error in 12.55s`, preceded by `ERROR tests/test_estimator_values_are_pinned.py` / `!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!` and `tests\test_estimator_values_are_pinned.py:23: in <module>` / ` import statsmodels.formula.api as smf` / `E ModuleNotFoundError: No module named 'statsmodels'`. With `--continue-on-collection-errors`: `2841 tests collecte…

Dissent: The receipts reproduce, but the conclusion does not survive the rest of the repo, and one of the finding's own numbers is wrong. (1) ALREADY ANSWERED, TWICE, NAMING THE SAME PACKAGE. `artifacts/todo_stack.md:665` is a top-level section headed `# Environment note, not repository work`, whose body at :667-672 reads "The development virtualenv at `.venv` has `omission` editable-installed ... and / is missing `statsmodels`, a declared hard dependency, plus `mkdocs` and `nbclient`. Every local / rec…

### public-claims/readme-table-omits-ontology-laminar-analyzers

*medium · gap · bears on: Goal claim: "Scientific choices and interpretation remain explicit and human-controlled"; and the dimension question "any major capability area exported but absent from the table"*

Eight modules have zero representation in the README capability table. Three are substantial: `jnwb.ontology` (11 exports, including Provenance, Lineage, Interpretation, Question, Dataset, Result), `jnwb.laminar` (8 exports: vflip, xflip, zflip, vflip_from_lfp, label_layers and three result classes), `jnwb.analyzers` (PopulationAnalyzer, TFRAnalyzer, UnitAnalyzer).

Receipt: Executed probe (provenance asserted, jnwb 0.2.5 from C:\workspace\jnwb), grouping `jnwb.__all__` by `__module__` against the 39 backticked names parsed from README.md's `## Capabilities` section: `jnwb.ontology 11 / 0 <-- ZERO COVERAGE ['AlignedDataset','Alignment','Dataset','EpochCollection','Figure','Interpretation','Lineage','Provenance','Query','Question','Result']`; `jnwb.laminar 8 / 0 <-- ZERO COVERAGE ['VFlipResult','XFlipResult','ZFlipResult','label_layers','vflip','vflip_from_lfp','xflip','zflip']`; `jnwb.analyzers 3 / 0 <-- ZERO COVERAGE ['PopulationAnalyzer','TFRAnalyzer','UnitAnalyzer']`; also zero: jnwb.rsa (2), jnwb.io (2), jnwb.tfr_accumulator (2), jnwb.compression (1), jnwb.…

Dissent: The conclusion does not survive the rest of the repository. (1) The qualifier is in the finding's own receipt location and was not engaged: README.md:26 reads "| Area | Representative API |" — the table declares itself representative, and README.md:126 routes the reader to the complete surface ("Guides, the public API (every symbol in `jnwb.__all__`), and common mistakes are on [Read the Docs]"). Absence from a table that never claims exhaustiveness is not a gap. (2) Two of the three "substanti…

### evaluation-and-roadmap/p0-forbids-the-paper2agent-transfer

*medium · risk · bears on: Paper2Agent cited as motivation; the deck's core model "NWB data -> AI skills -> JNWB tools -> analysis -> verification"*

The repository's own ruling forbids inferring that jnwb's routing layer helps from Paper2Agent's reported gap. A slide that presents the skills layer as demonstrated rather than hypothesised contradicts a written ruling of record.

Receipt: artifacts/planned_post_0.2.5.md:17-19: "Paper2Agent reports a gap in that direction. That is evidence about its implementation and its benchmark, and it does not transfer here by analogy. The work is to state the task set and measure it." artifacts/direction.md:131-134: "JNWB sits in the complementary position -- one maintained, dataset-agnostic toolbox for NWB neurodata rather than a per-paper conversion -- and takes verification further". artifacts/direction.md:3-4: "Adopted 2026-09-17 as the durable product direction... Ruling of record; supersedes any longer draft."

Dissent: Both quoted receipts verify verbatim, but the conclusion is self-answering: the "contradiction" is already resolved by a deliberate, committed, dated documented decision — the very document the surveyor cites. Five checks, all against the repo, none supporting a live defect. (1) The surveyor quoted planned_post_0.2.5.md:17-19 but missed the stronger line directly above it — line 12 is the section heading itself: "## P0. Does the routing layer help? (hypothesis, ruled 2026-09-17)". The repositor…

### evaluation-and-roadmap/nearest-roadmap-record-is-p0-p3-plus-three-bullets

*medium · gap · bears on: Slide 17, "near-term development direction"*

The repository's whole recorded roadmap is: artifacts/planned_post_0.2.5.md P0 (benchmark hypothesis), P1.1-P1.4 (RDM core, RDM reliability, general geometry, crossnobis deferred), P2 (correctness utilities, incl. a provenance candidate already shipped), P3 (five consumer-reported items, two resolved); plus three bullets in todo_stack.md. Nothing else is recorded as planned work.

Receipt: artifacts/planned_post_0.2.5.md headings: line 12 "## P0. Does the routing layer help? (hypothesis, ruled 2026-09-17)"; 31 "## P1. RDM and geometry surface (request from the omission team, ruled 2026-09-17)"; 37 "**Order.** `finish 0.2.5 hardening -> independent closure -> RDM expansion`."; 55 "### P1.1 RDM core"; 66 "### P1.2 RDM reliability"; 70 "### P1.3 General geometry"; 76 "### P1.4 Crossnobis (deferred)"; 82 "## P2. Correctness utilities"; 131 "## P3. Consumer-reported items (omission, 2026-09-17)". artifacts/todo_stack.md:656-663: "# Before 1.0" / "- Replace example-based estimator coverage with analytic or property-based tests." / "- Processing-module discovery generalization beyon…

Dissent: The inventory in the receipt reproduces exactly, but the conclusion built on it does not survive. (a) The completeness claim "Nothing else is recorded as planned work" omits artifacts/direction.md, the adopted forward-direction record (line 3: "Adopted 2026-09-17 as the durable product direction, effective after the 0.2.5 release."; line 4: "Ruling of record; supersedes any longer draft."), which planned_post_0.2.5.md:8 itself makes authoritative over its whole contents ("Everything here is sub…

### dynamic-conversion/write-mode-reachable-through-undeclared-module-attribute

*low · risk · bears on: "Exactly which file modes are reachable through the public API"; and the human-AI-JNWB responsibility diagram*

`jnwb.nwb_io` is reachable as an attribute of the top-level package despite being declared module-internal, and `nwb_read_io` forwards any non-`"r"` mode straight to `NWBHDF5IO`. A write mode is therefore reachable from an `import jnwb` session; I executed it and produced a 180 KB NWB file. The surface test asserts only that `nwb_io` is absent from `__all__` and `EXPORT_MODULES`, not that the attribute is absent.

Receipt: C:\workspace\jnwb\jnwb\nwb_io.py:3 "Module-internal: not part of ``jnwb.__all__``." C:\workspace\jnwb\jnwb\nwb_io.py:144-149: ``` def nwb_read_io(path: Any, mode: str = "r", **kwargs: Any) -> Iterator[NWBHDF5IO]: """Open an NWB file; apply builder repairs on read paths only.""" if mode != "r": with NWBHDF5IO(path, mode, **kwargs) as io: yield io return ``` The attribute exists because C:\workspace\jnwb\jnwb\__init__.py:54 `from .nwb_io import MissingRequiredNWBFieldError` binds the submodule as a side effect. Command: `<venv>/python.exe <scratchpad>/probe_dim2b.py`. Output: ``` _api_surface disposition of nwb_io: module-internal hasattr(jnwb, 'nwb_io'): True jnwb.nwb_io.nwb_read_io: <functi…

Dissent: The receipts are accurate but the conclusion does not survive the rest of the repository, on four independent counts. (1) THE CAPABILITY IS ALREADY PUBLIC AND DOCUMENTED, so `jnwb.nwb_io` is not the reachability path that matters. `compress_fp32` is in `__all__` (C:\workspace\jnwb\jnwb\__init__.py:224 `'compress_fp32',`), eagerly imported at C:\workspace\jnwb\jnwb\__init__.py:53 `from .compression import compress_fp32`, listed in the generated API page (C:\workspace\jnwb\docs\api.md:60 `| jnwb.…

## Unverified tail

Below the verification cap, carried forward without adversarial checking. Listed so the set stays recoverable; no receipt is reproduced, because an unverified receipt invites being trusted.

### identity/does-not-generate-data-unstated-about-the-ai

*medium · gap · bears on: (c) AI-assisted ... DOES NOT GENERATE DATA*

No file states that the AI does not generate data. The nearest durable statements are library invariants about outputs, not constraints on an agent. A genuine supporting asset does exist — the MCP surface is read-only and verified so — but it is narrower than the claim.

Single verifier lens only; the second did not complete.

### identity/authorization-claim-has-no-matching-asset

*medium · gap · bears on: (d) the AI requires authorization*

Every occurrence of "authoriz" in the repository is one of three unrelated things, none of which is an authorization requirement for AI-assisted analysis or data access.

Single verifier lens only; the second did not complete.

### identity/nwb-translation-capability-does-not-exist

*medium · gap · bears on: (e) "Dynamic": translating non-NWB datasets into NWB files via pynwb*

The package has no non-NWB-to-NWB conversion capability, in code or in any skill. The only NWB-writing public symbol converts an existing NWB file to fp32.

Single verifier lens only; the second did not complete.

### identity/decline-semantics-live-only-in-a-pruned-artifact

*medium · gap · bears on: durable asset 6 (failure/rejection decision diagram) and the target's AI-declines-rather-than-guesses posture*

The four-case routing rule including "declining is a correct outcome" is stated only in artifacts/direction.md, which ships to nobody. No skill file states a decline rule. The library-side half of the asset does exist and is good.

Single verifier lens only; the second did not complete.

### identity/direction-md-is-the-identity-source-and-is-unpublished

*medium · risk · bears on: every identity claim the deck makes; the plan's "Documentation reuse" column*

artifacts/direction.md is the "Ruling of record" and carries the identity, authority model, boundary test, acceptance model and the prior-art licence constraint. It is pruned from the sdist, absent from the docs nav, and linked from no user-facing page.

Single verifier lens only; the second did not complete.

### identity/landing-page-asset-exists-but-not-the-overview-diagram

*medium · gap · bears on: Slide 1 "Documentation reuse" and durable asset 10 (overview diagram for the landing page)*

The landing-page prose asset the deck wants to reuse does exist, in two places. The overview diagram does not — docs/index.md carries a logo and six result figures and no diagram at all.

Single verifier lens only; the second did not complete.

### identity/docs-overstates-what-the-gates-enforce

*medium · contradiction · bears on: (a) dataset-agnostic, and any slide claiming the boundary is mechanically enforced*

docs/01 tells the reader the boundary invariant is mechanically enforced by automated regression gates. The gate that covers the condition-code half checks a fixed list of one study's tokens, and its own docstring says it proves nothing more. The agent-facing file states the limit correctly; the user-facing one does not.

Single verifier lens only; the second did not complete.

### skills/every-worked-example-synthesizes-its-input

*medium · risk · bears on: Target claim: the AI "is limited to provided data, and DOES NOT GENERATE DATA"*

Seven of the eight executable Minimal Workflow blocks construct their inputs with np.random.default_rng rather than reading data. Only jnwb-nwb-data's block opens a file. Exactly one skill states any constraint on synthetic data, and it is scoped to figures.

Single verifier lens only; the second did not complete.

### skills/router-gpu-paragraph-partly-false

*medium · contradiction · bears on: skills/jnwb/SKILL.md section 3, an agent-facing statement in the top-level router*

The router tells an agent that a GPU-capable call warns and falls back only when no CUDA device is present, and that "the result records which device produced it". On this machine, with one CUDA device present, `vflip(device='cuda')` still warned -- for a different reason the router does not mention -- and neither VFlipResult nor relative_power's return records any device.

Single verifier lens only; the second did not complete.

### skills/skills-absent-from-architecture-diagram-and-readme

*medium · gap · bears on: Durable assets #2 (code-docs-skills architecture diagram) and #5 (skill-to-tool execution diagram); core model "NWB data -> AI skills -> JNWB tools"*

The repository's only architecture diagram has no skills node, and the word "skill" does not appear in it at all. README.md mentions skills zero times. The skills layer is documented only in docs/agents.md, in prose and a table, with no diagram.

Single verifier lens only; the second did not complete.

### doc-assets/asset05-skill-to-tool-diagram-absent

*medium · gap · bears on: Durable asset 5: skill-to-tool execution diagram*

No skill-to-tool execution diagram exists. docs/agents.md carries the equivalent as prose tables, and its MCP tool table is genuinely maintained against the live server registry.

Single verifier lens only; the second did not complete.

### doc-assets/asset06-failure-decision-diagram-absent

*medium · gap · bears on: Durable asset 6: failure / rejection decision diagram*

No failure/rejection decision diagram exists in docs/. docs/errors.md is a maintained prose page about refusals, and the four-case decision the plan describes exists only as ASCII in the unpublished artifacts/direction.md.

Single verifier lens only; the second did not complete.

### doc-assets/asset07-no-openscope-tutorial-or-figure

*medium · gap · bears on: Durable asset 7: canonical OpenScope end-to-end tutorial and figure*

The string 'OpenScope' does not appear anywhere in the repository. An end-to-end tutorial exists and is CI-executed, but it runs on a synthetic in-process NWB fixture and writes no figure.

Single verifier lens only; the second did not complete.

### doc-assets/asset08-responsibility-diagram-unpublished

*medium · gap · bears on: Durable asset 8: human-AI-JNWB responsibility diagram*

No human-AI-JNWB responsibility diagram exists in docs/. The exact content the plan describes is ASCII art in artifacts/direction.md, which is not part of the documentation site.

Single verifier lens only; the second did not complete.

### doc-assets/asset09-ai-benchmark-is-an-unstarted-hypothesis

*medium · gap · bears on: Durable asset 9: AI-interface benchmark design*

No AI-interface benchmark design exists. artifacts/benchmarks/ holds only import-time, GPU-parity and vflip/xflip numeric calibration receipts, and the repository's own record states the benchmark's task set has not been written.

Single verifier lens only; the second did not complete.

### doc-assets/asset10-landing-page-overview-diagram-absent

*medium · gap · bears on: Durable asset 10: overview diagram for the documentation landing page*

docs/index.md carries a logo and a six-cell grid of result figures. It has no overview diagram.

Single verifier lens only; the second did not complete.

### doc-assets/generate-figures-runs-nowhere

*medium · risk · bears on: The plan's principle that deck assets become MAINTAINED documentation assets*

Nothing in the repository runs docs/generate_figures.py: not CI, not the harness gate, not the release gate, not Read the Docs, and no test. The ten figures are PRESENT, not MAINTAINED.

Single verifier lens only; the second did not complete.

### doc-assets/generate-figures-output-not-reproducible

*medium · risk · bears on: Durable assets 3 and 7 and the 'build once, reuse everywhere' principle*

Running docs/generate_figures.py today produces all ten figures without error, at identical pixel dimensions, but not one is byte-identical to the committed file; 6.3-8.6 percent of pixels differ in each. matplotlib is unpinned, so the repository cannot distinguish renderer drift from content drift.

Single verifier lens only; the second did not complete.

### doc-assets/direction-md-states-the-principle-the-repo-does-not-yet-meet

*medium · contradiction · bears on: The plan's stated principle that diagrams/examples become maintained documentation assets*

artifacts/direction.md declares that canonical diagrams and capability maps are maintained in the documentation and that presentation assets derive from them. Today the documentation holds no maintained diagram at all, and the diagrams it does hold do not render.

Single verifier lens only; the second did not complete.

### evaluation-and-roadmap/p2-provenance-candidate-already-shipped

*medium · stale-record · bears on: Slide 17 / the roadmap record; Slide 15's "provenance" scoring axis*

artifacts/planned_post_0.2.5.md P2 records as an open candidate a defect that 0.2.5 already repaired. Its stated defect "There is no path field" is false at HEAD: Provenance now carries jnwb_version and jnwb_path, read from the executing package and not passable by the caller.

Single verifier lens only; the second did not complete.

### evaluation-and-roadmap/paper2agent-absent-from-published-references

*medium · gap · bears on: External prior art citation (Paper2Agent, Miao et al. 2026, Nature)*

The repository mentions Paper2Agent in exactly two places, both inside artifacts/, which is pruned from the sdist and not in the docs site nav. It carries no authors, no year and no DOI anywhere. docs/references.md -- the published citation registry -- has no entry for it and no prior-art section to hold one.

Single verifier lens only; the second did not complete.

### identity/dangling-spec-pointer-in-public-docstrings

*low · stale-record · bears on: provenance of the compression and TFR-accumulator capabilities on a capability map (asset 1)*

Three public docstrings cite a specification file that does not exist anywhere in the repository.

Single verifier lens only; the second did not complete.

### identity/todo-stack-cites-a-direction-section-that-does-not-exist

*low · stale-record · bears on: the acceptance condition governing all skill work, which the deck's AI-layer slides rest on*

The todo stack attributes the skill-behaviour acceptance condition to a section of direction.md that has no such heading.

Single verifier lens only; the second did not complete.

### identity/end-to-end-pipeline-page-title-vs-not-a-pipeline

*low · risk · bears on: (a) "toolbox, not a pipeline" as a slide headline*

The published site has a navigation entry and page title reading "End-to-End Pipeline" while the README headline says jnwb is not a pipeline. The page body says composition, so the substance agrees and only the title does not.

Single verifier lens only; the second did not complete.

### dynamic-conversion/conversion-script-provenance-points-at-nothing

*low · stale-record · bears on: Durable-asset principle (maintained assets, not stale ones); provenance of any file produced by the one public writer*

`compress_fp32` stamps every output file with `conversion_script = "scripts/convert_nwb_compressed.py"`, and writes the same path into a per-dataset `stored_dtype_note`. That script does not exist anywhere in the repository.

Single verifier lens only; the second did not complete.

### dynamic-conversion/ontology-docstring-names-a-method-that-does-not-exist

*low · stale-record · bears on: Goal claim: "adapting and adopting new datasets" via the ontology's Dataset abstraction*

`Dataset`'s docstring tells the reader it is "Created from: Query.execute(sessions)". `Query` has no `execute` method, and no `execute` is defined anywhere in the module.

Single verifier lens only; the second did not complete.

### skills/stale-eight-in-validation-docstring

*low · stale-record · bears on: Task question: how many skills exist, exactly*

tests/test_skills_validation.py:50 states the repository has eight canonical skills. The set two lines above it has nine entries, and nine directories exist on disk. The assertion is correct; only its docstring is stale.

Single verifier lens only; the second did not complete.

### doc-assets/quickstart-svg-copy-is-stale-and-unchecked

*low · stale-record · bears on: Durable asset 7 and the maintained-copy principle generally*

The published quickstart SVG differs from the one the quickstart script writes. The test that exists for this pair compares only the PNG, so the SVG drifted by two weeks unnoticed.

Single verifier lens only; the second did not complete.

### ai-plumbing/skills-url-mislabelled-in-api-page

*low · stale-record · bears on: The "Dynamic skills" claim's one machine-readable pointer*

The generated public API page lists jnwb.SKILLS_URL as type "function" and shows the str constructor's docstring instead of a description. SKILLS_URL is a module-level string constant.

Single verifier lens only; the second did not complete.

### public-claims/classifier-3-13-never-tested

*low · risk · bears on: Public claim: the PyPI classifier list, which is a support claim readers and resolvers act on*

The package claims Python 3.13 support in its classifiers, on PyPI today. CI never runs on 3.13.

Single verifier lens only; the second did not complete.

### public-claims/changelog-0-1-0-python-range

*low · stale-record · bears on: Public claim: Python version support in the CHANGELOG, and the likely source of the wrong v0.2.5 release note*

CHANGELOG.md's 0.1.0 entry records "Python 3.10 through 3.14" — the same phrase that appears in the v0.2.5 release body — while the CHANGELOG's own later entry records that 0.1.1 declared `>=3.12, <3.13`.

Single verifier lens only; the second did not complete.

### evaluation-and-roadmap/todo-stack-points-at-a-heading-that-does-not-exist

*low · stale-record · bears on: The record; direction.md as authority for skill behaviour*

artifacts/todo_stack.md:38 cites artifacts/direction.md "under 'Skill behaviour'". direction.md has no such heading. The gate that exists to catch stale pointers passes anyway, because it only resolves numeric section references.

Single verifier lens only; the second did not complete.

### evaluation-and-roadmap/closure-records-filed-under-findings-marked-unsupported

*low · stale-record · bears on: The record; whether closure records can be read correctly*

Every closure record in todo_stack.md sits under the heading "# Findings marked unsupported", including records that reproduced, were repaired, or were accepted. The stack's own protocol defines "unsupported" as the opposite.

Single verifier lens only; the second did not complete.

### evaluation-and-roadmap/empty-marker-nested-under-section-12

*low · stale-record · bears on: Whether the 0.2.5 stack reads as closed*

The marker declaring the stack empty sits under "## 12. Harness and gates", while sections 9, 10 and 11 carry headings and notes with no items and no marker. Read structurally, only section 12 is declared empty.

Single verifier lens only; the second did not complete.

### evaluation-and-roadmap/close-out-gate-condition-not-satisfiable-as-written

*low · contradiction · bears on: direction.md's definition of the 0.2.5 close-out audit gate*

direction.md requires the close-out audit to run after the stack empties and before the release seal. The release item is itself in the stack, so the two conditions cannot both hold. The record shows the audit ran with the release item still open.

Single verifier lens only; the second did not complete.

### evaluation-and-roadmap/p3-line-numbers-and-one-claim-have-drifted

*low · stale-record · bears on: The roadmap record's P3 consumer-reported items*

Two P3 entries have drifted against HEAD: the "one stale claim remains" note is no longer true, and the cited statistics.py line numbers moved by ~320 lines.

Single verifier lens only; the second did not complete.

## Refuted

These did not survive verification and are recorded so they are not rediscovered. Each is followed by the reason it failed.

### identity/ai-identity-absent-from-published-surface

*high · gap · bears on: deck title "JNWB: Dynamic AI-Assisted Skills and Analysis of Neurodata Without Borders" and Slide 1*

The published surface never describes jnwb as AI-assisted. The token "AI" appears exactly once in README.md and zero times in docs/. Every AI-identity claim in the repository lives in artifacts/direction.md, which is pruned from the sdist and absent from the docs site.

Receipt: `grep -rn "\bAI\b|AI-assisted|AI-native" README.md docs/*.md docs/tutorials/*.md` returns one line: README.md:135 "If you are an AI agent, read [AGENTS.md](...) first." The same grep over AGENTS.md CONTRIBUTING.md artifacts/direction.md artifacts/fact_stack.md returns seven lines, all in artifacts/direction.md (lines 9, 12, 16, 22, 44, 55, 125). Not published: MANIFEST.in:18 "prune artifacts"; mkdocs.yml nav (lines 57-92) lists no direction.md. Today's self-description is README.md:14 "Dataset-agnostic Python library for Neurodata Without Borders (NWB 2.0+) electrophysiology: addressing, spikes, LFP, spectral analysis, statistics, population methods, decoding, connectivity, laminar CSD, fil…

Dissent: The receipt's literal greps all reproduce exactly (README.md:135 and :14 verbatim, one AI token in README, zero in docs markdown, MANIFEST.in:18 "prune artifacts", direction.md lines 9/12/16/22/44/55/125, no direction.md in mkdocs nav). But the receipt does not support the two load-bearing clauses of the statement. (1) "The published surface never describes jnwb as AI-assisted" is contradicted by docs/agents.md, a nav-listed page (mkdocs.yml:60) titled "Analyzing with an Agent" that states "`jn…

### dynamic-conversion/no-test-writes-nwb-through-a-public-export

*medium · gap · bears on: Goal claim: conversion capability; and the reliability/test-hierarchy durable asset*

No test in tests/ writes an NWB file through a public jnwb export. Every NWB write in the test suite calls pynwb directly. The single test suite that exercises `compress_fp32` asserts only h5py-level properties and never reads the output back with pynwb.

Receipt: Grep for `NWBHDF5IO|io.write|NWBFile(|add_acquisition|add_unit|create_processing_module|compress_fp32` over C:\workspace\jnwb\tests: every write hit is a direct pynwb call, e.g. tests\test_acquisition_layout.py:52-53 `with pynwb.NWBHDF5IO(str(path), "w") as io:` / `io.write(nwb)`; tests\test_docs_nwb_workflow.py:60-61; tests\test_hdmf_nwb_read_boundary.py:234-235; tests\test_inspect_one_schema.py:79-80; tests\test_metadata.py:285-286; tests\test_laminar.py:1162-1163; tests\test_mcp_server.py:68-69. Grep for `compress_fp32|verify_roundtrip` over tests/ returned exactly one file: `tests\test_compression.py`. C:\workspace\jnwb\tests\test_compression.py:62-73 asserts via h5py only: ``` stats = …

Dissent: The receipt's compress_fp32 half checks out verbatim (I confirmed C:\workspace\jnwb\tests\test_compression.py:37 `def test_compress_fp32_synthetic_hdf5_conversion(tmp_path):`, :47 `with h5py.File(src, "w") as f:`, :62 `stats = jnwb.compress_fp32(src, dst, verify=False, overwrite=True)`, :64 `assert dst.exists()`, :69 `with h5py.File(dst, "r") as f_dst, h5py.File(src, "r") as f_src:`, and that `grep pynwb tests/test_compression.py` returns nothing, exit 1). But both load-bearing sentences of the…

### reliability/no-testing-and-reliability-guide

*medium · gap · bears on: The deck's 'Documentation reuse: testing and reliability guide' for Slide 10, and durable asset #4 (reliability/test hierarchy diagram)*

No testing or reliability guide exists anywhere in the repository. There is no such page in docs/, no entry in the mkdocs navigation, and no Markdown file in the repo containing the phrase.

Receipt: `ls docs/*.md` returns exactly 18 files, none about testing: `01_architecture_and_philosophy.md 02_paths_addressing_metadata.md 03_representational_similarity_jrsa.md 04_spectral_analysis_and_tfr.md 05_artifact_detection_and_repair.md 06_spikes_psth_and_onset_dynamics.md 07_statistical_inference_and_nulls.md 08_directed_connectivity_and_information.md 09_decoding_and_visual_qc.md 10_operation_specifications.md agents.md api.md common_mistakes.md errors.md index.md install.md quickstart.md references.md`. Grep for `testing and reliability|reliability guide|test hierarchy|hierarchy of test` (case-insensitive) over `*.md` across C:\workspace\jnwb: "No matches found". The mkdocs.yml `nav:` bloc…

Dissent: The receipt's narrow checks verify, but a load-bearing sentence of the statement and its inference are contradicted by the repository. (1) VERIFIED: `Get-ChildItem C:\workspace\jnwb\docs\*.md` returns exactly the 18 names quoted; the four-phrase case-insensitive Grep over `*.md` returns "No matches found"; `docs/install.md:21` matches the quoted text byte-for-byte (PowerShell equality test returned MATCH:True); `docs/tutorials/` adds 9 more files, none about testing. (2) MISCITED: the `nav:` bl…

### evaluation-and-roadmap/no-ai-interface-benchmark-asset-exists

*medium · gap · bears on: Durable Documentation Asset #9, "AI-interface benchmark design"; Slide 15's proposed AI+jnwb vs AI+raw-repo benchmark*

All ten files under artifacts/benchmarks/ are performance or estimator-calibration receipts. None involves an AI agent, a task set, two arms, a model, prompts or a scoring rubric. No benchmark design for the AI interface exists anywhere in the repository.

Receipt: `git ls-files | grep -Ei 'eval|bench|arena|rubric|taskset|task_set|agent'` returns, under artifacts/benchmarks/, exactly: baseline_performance.json, complexity_inventory.md, cuda_parity_0.2.4.md, gpu_launch_overhead_0.2.5.md, import_breakdown.json, import_profile.txt, vflip_calibration_0.2.4.md, vflip_calibration_0.2.4_raw.json, xflip_calibration_0.2.5.md, xflip_calibration_0.2.5_raw.json -- and no evaluation harness, task set or rubric file. All ten were read/inspected. Their self-declared scope: complexity_inventory.md:3 "Formal Big-O time and peak memory bounds for core primitives in `jnwb`"; cuda_parity_0.2.4.md:4 "the release needs a receipt of CUDA **executing**, not of CUDA tests pas…

Dissent: Every cited path:line in the receipt checks out verbatim -- complexity_inventory.md:3, cuda_parity_0.2.4.md:4, gpu_launch_overhead_0.2.5.md:31, import_profile.txt:1, baseline_performance.json:113, vflip_calibration_0.2.4.md:1, xflip_calibration_0.2.5.md:1 and AGENTS.md:30 all say what the finding says they say, the directory contains exactly those ten files, and the two JSON key lists reproduce exactly. But the receipt only enumerates FILENAMES and reads artifacts/benchmarks/; it therefore cann…
