# Findings ledger 0.2.6

Dispositions every identifier in `artifacts/alignment_review_0.2.5.md` against the live tree.
Written under `artifacts/todo_stack.md` item 06-03.

Basis re-resolved, not recalled (`observed`):

```text
$ git rev-parse --abbrev-ref HEAD ; git rev-parse HEAD ; git status --porcelain ; git rev-parse origin/dev
# run before this file existed; it is itself the only untracked entry now
dev
265eb01e09eb34128d178603c02572092e50a2b2
(no output)
265eb01e09eb34128d178603c02572092e50a2b2

$ python scripts/harness_gate.py            # tail
PASS: Python >=3.12 floor, classifiers ['3.12', '3.13', '3.14'], CI covering ['3.12', '3.13', '3.14'] all agree.
ALL HARNESS GATES PASSED.

$ probe (provenance-asserted) -> C:\workspace\jnwb\jnwb\__init__.py 0.2.5 ; len(__all__) = 156
```

The review ran against `dev` at `6741d23c`. Sixteen files changed between that commit and HEAD:

```text
$ git diff --stat 6741d23c..HEAD
 .github/workflows/workflow.yml, AGENTS.md, README.md, artifacts/agents/jnwb-developer.md,
 artifacts/alignment_review_0.2.5.md, artifacts/direction.md, artifacts/goal.md,
 artifacts/planned_post_0.2.5.md, artifacts/todo_stack.md, artifacts/todo_stack_0.2.5.md,
 docs/install.md, scripts/harness_gate.py, skills/jnwb-fact-action/SKILL.md,
 tests/test_gates_reject_the_trees_they_passed.py, tests/test_harness_adversarial_gates.py,
 tests/test_skills_validation.py
 16 files changed, 2312 insertions(+), 700 deletions(-)
```

Nothing under `jnwb/`, `mkdocs.yml`, `CONTRIBUTING.md`, `CHANGELOG.md`, or `docs/` other than
`install.md` moved. Every finding whose receipt lands on an untouched path was still re-resolved
against disk; the diff bounds where a repair could have happened, it does not substitute for a
check.

## Identifiers

Extracted mechanically, not hand-numbered: every `### ` heading under a `## ` section of the
review.

```text
== Confirmed: 31   == Upheld with dissent: 12   == Unverified tail: 36   == Refuted: 4
TOTAL: 83   UNIQUE: 83   DUPLICATES: []   NO_SLASH: []
```

83 identifiers, all unique, all of the form `<dimension>/<id>`. The counts match the review's own
header. `tests/test_findings_ledger.py` re-runs this extraction and asserts it against the index
below.

## How a disposition was chosen

| Disposition | Means |
|---|---|
| `reproduced` | The described state holds on this tree, re-resolved by command |
| `already repaired` | It was true and has since been fixed; the fix is named with its receipt |
| `stale` | It described something that was never true of the tree the review ran on |
| `refuted` | Its load-bearing claim is false against evidence -- the review's own dissent, or mine |
| `deferred` | The state holds and its repair is frozen out of 0.2.6 by a recorded ruling |

`deferred` is used only where `artifacts/todo_stack.md` section "Out of 0.2.6 scope" names the
subject. Deciding scope is not this packet's to do, so a finding that holds and that no ruling
covers is `reproduced` and `unclaimed`, which routes it to 06-17 rather than closing it here.

No finding resolved to `stale`. Two findings carry a numeric error inside a statement that
otherwise reproduces; those are recorded at the entry, not promoted to a disposition.

## Index

Every identifier, exactly once. This table is what `tests/test_findings_ledger.py` checks.

| Identifier | Disposition |
|---|---|
| `identity/core-model-contradicted-by-ruling-of-record` | already repaired |
| `identity/dataset-agnostic-contradicted-by-compression-module` | reproduced |
| `identity/mermaid-diagrams-do-not-render-on-the-site` | reproduced |
| `skills/relative-power-result-claim-false` | reproduced |
| `skills/no-authorization-concept-in-skills` | deferred |
| `doc-assets/mermaid-renders-as-source-text` | reproduced |
| `reliability/jrsa-holm-silently-becomes-bh` | reproduced |
| `public-claims/release-notes-declare-python-3-10` | already repaired |
| `public-claims/api-md-skills-url-typed-function` | reproduced |
| `identity/human-control-stated-as-caller-control-not-human-control` | reproduced |
| `dynamic-conversion/compress-fp32-is-nwb-to-nwb-only` | deferred |
| `dynamic-conversion/no-skill-routes-conversion` | deferred |
| `skills/two-skills-carry-no-stop-language` | reproduced |
| `skills/ontology-subsystem-unreachable-from-any-skill` | reproduced |
| `skills/no-nwb-conversion-anywhere` | deferred |
| `skills/workflow-blocks-never-executed-by-the-harness` | reproduced |
| `doc-assets/asset01-capability-map-split-and-unchecked` | reproduced |
| `doc-assets/asset02-code-docs-skills-diagram-absent` | reproduced |
| `doc-assets/asset03-semantics-distinction-diagram-absent` | reproduced |
| `doc-assets/asset04-test-hierarchy-diagram-absent` | reproduced |
| `ai-plumbing/agent-roles-exist-but-ship-nowhere` | reproduced |
| `ai-plumbing/generator-boundary-is-naming-not-enforcement` | reproduced |
| `ai-plumbing/no-nwb-conversion-asset` | deferred |
| `reliability/contributing-taxonomy-is-a-different-one` | reproduced |
| `reliability/hierarchy-exists-only-in-suite-shape` | reproduced |
| `public-claims/no-gate-reads-release-notes` | reproduced |
| `public-claims/readme-omits-agent-surface` | reproduced |
| `evaluation-and-roadmap/p0-is-a-hypothesis-and-constraints-not-a-design` | reproduced |
| `evaluation-and-roadmap/roadmap-and-direction-are-unindexed` | reproduced |
| `ai-plumbing/writes-nothing-guard-is-narrow` | reproduced |
| `public-claims/install-md-states-no-python-requirement` | already repaired |
| `identity/agents-vocabulary-rule-forbids-the-planned-doc-assets` | already repaired |
| `dynamic-conversion/no-public-nwb-write-export` | refuted |
| `dynamic-conversion/only-nwb-writer-is-a-synthetic-data-generator` | refuted |
| `evaluation-and-roadmap/out-of-scope-rejection-has-no-behaviour-to-score` | reproduced |
| `doc-assets/module-map-omits-nwb-entry-points` | reproduced |
| `ai-plumbing/readme-silent-on-mcp-and-skills` | reproduced |
| `ai-plumbing/authorization-has-no-mechanism` | deferred |
| `reliability/suite-size-and-collection-error` | reproduced |
| `public-claims/readme-table-omits-ontology-laminar-analyzers` | reproduced |
| `evaluation-and-roadmap/p0-forbids-the-paper2agent-transfer` | refuted |
| `evaluation-and-roadmap/nearest-roadmap-record-is-p0-p3-plus-three-bullets` | refuted |
| `dynamic-conversion/write-mode-reachable-through-undeclared-module-attribute` | reproduced |
| `public-claims/classifier-3-13-never-tested` | already repaired |
| `identity/does-not-generate-data-unstated-about-the-ai` | deferred |
| `identity/authorization-claim-has-no-matching-asset` | deferred |
| `identity/nwb-translation-capability-does-not-exist` | deferred |
| `identity/decline-semantics-live-only-in-a-pruned-artifact` | deferred |
| `identity/direction-md-is-the-identity-source-and-is-unpublished` | deferred |
| `identity/landing-page-asset-exists-but-not-the-overview-diagram` | deferred |
| `identity/docs-overstates-what-the-gates-enforce` | deferred |
| `skills/every-worked-example-synthesizes-its-input` | deferred |
| `skills/router-gpu-paragraph-partly-false` | deferred |
| `skills/skills-absent-from-architecture-diagram-and-readme` | deferred |
| `doc-assets/asset05-skill-to-tool-diagram-absent` | deferred |
| `doc-assets/asset06-failure-decision-diagram-absent` | deferred |
| `doc-assets/asset07-no-openscope-tutorial-or-figure` | deferred |
| `doc-assets/asset08-responsibility-diagram-unpublished` | deferred |
| `doc-assets/asset09-ai-benchmark-is-an-unstarted-hypothesis` | deferred |
| `doc-assets/asset10-landing-page-overview-diagram-absent` | deferred |
| `doc-assets/generate-figures-runs-nowhere` | deferred |
| `doc-assets/generate-figures-output-not-reproducible` | deferred |
| `doc-assets/direction-md-states-the-principle-the-repo-does-not-yet-meet` | deferred |
| `evaluation-and-roadmap/p2-provenance-candidate-already-shipped` | deferred |
| `evaluation-and-roadmap/paper2agent-absent-from-published-references` | deferred |
| `identity/dangling-spec-pointer-in-public-docstrings` | deferred |
| `identity/todo-stack-cites-a-direction-section-that-does-not-exist` | deferred |
| `identity/end-to-end-pipeline-page-title-vs-not-a-pipeline` | deferred |
| `dynamic-conversion/conversion-script-provenance-points-at-nothing` | deferred |
| `dynamic-conversion/ontology-docstring-names-a-method-that-does-not-exist` | deferred |
| `skills/stale-eight-in-validation-docstring` | deferred |
| `doc-assets/quickstart-svg-copy-is-stale-and-unchecked` | deferred |
| `ai-plumbing/skills-url-mislabelled-in-api-page` | deferred |
| `public-claims/changelog-0-1-0-python-range` | deferred |
| `evaluation-and-roadmap/todo-stack-points-at-a-heading-that-does-not-exist` | deferred |
| `evaluation-and-roadmap/closure-records-filed-under-findings-marked-unsupported` | deferred |
| `evaluation-and-roadmap/empty-marker-nested-under-section-12` | deferred |
| `evaluation-and-roadmap/close-out-gate-condition-not-satisfiable-as-written` | deferred |
| `evaluation-and-roadmap/p3-line-numbers-and-one-claim-have-drifted` | deferred |
| `identity/ai-identity-absent-from-published-surface` | refuted |
| `dynamic-conversion/no-test-writes-nwb-through-a-public-export` | refuted |
| `reliability/no-testing-and-reliability-guide` | refuted |
| `evaluation-and-roadmap/no-ai-interface-benchmark-asset-exists` | refuted |

Totals: 29 `reproduced`, 5 `already repaired`, 41 `deferred`, 8 `refuted`, 0 `stale`. 83.

Of the 29 `reproduced`, 13 are claimed by a stack item and 16 are unclaimed and go to 06-17.

## Confirmed findings (31)

### identity/core-model-contradicted-by-ruling-of-record

- Finding: the target's linear chain routes analysis to jnwb through the AI layer; the ruling of record states two parallel first-class entry paths.
- Disposition: already repaired.
- Evidence (`observed`): `artifacts/goal.md` did not exist at `6741d23c` (`git diff --stat` shows `artifacts/goal.md | 48 +`). It now exists, dated "Ruled 2026-09-19", and section 1 "Entry topology" carries the parallel-path diagram and the sentence "A researcher does not conceptually pass through the AI layer." The statement jnwb is measured against now states the repository's side of the contradiction. 06-01 is the item that did it.

### identity/dataset-agnostic-contradicted-by-compression-module

- Finding: `compress_fp32` is public and hardcodes one corpus's NWB layout.
- Disposition: reproduced. Claimed by 06-13.
- Evidence (`observed`): `grep -n 'SPIKE_TRAIN_PATH\|CONVOLVED_PATH\|_LFP_MUAE_RE\|this corpus' jnwb/compression.py` returns `:93 _LFP_MUAE_RE = re.compile(r"(probe_\d+_(?:lfp|muae))(?:/\1_data)?/data$")`, `:107 SPIKE_TRAIN_PATH = "processing/spike_train/spike_train_data/data"`, `:108 CONVOLVED_PATH = ...`, `:60 "in these files or this codebase"`, `:317 "a real structural variant of this corpus"`. `grep -n "'compress_fp32'" jnwb/__init__.py` returns `223`. `jnwb/compression.py` is untouched since the review basis.

### identity/mermaid-diagrams-do-not-render-on-the-site

- Finding: five mermaid fences in `docs/`, and mkdocs renders them as code blocks.
- Disposition: reproduced. Claimed by 06-08.
- Evidence (`observed`): a recursive grep for a mermaid fence over `docs/` returns `01_architecture_and_philosophy.md:15`, `03_representational_similarity_jrsa.md:11`, `05_artifact_detection_and_repair.md:17`, `08_directed_connectivity_and_information.md:11`, `09_decoding_and_visual_qc.md:11`. `grep -n 'custom_fences\|mermaid\|superfences' mkdocs.yml` returns one line, `47:  - pymdownx.superfences`, with no child keys and no mermaid entry.

### skills/relative-power-result-claim-false

- Finding: the routing row says `relative_power` names its estimand in the return value; it returns a bare array.
- Disposition: reproduced. Claimed by 06-12.
- Evidence (`observed`): `skills/jnwb-lfp-spectral/SKILL.md:35` still ends "the model is named in the result." Provenance-asserted probe: `relative_power type: ndarray | has .model: False`.

### skills/no-authorization-concept-in-skills

- Finding: no authorization or permission-gating concept exists anywhere in the skills surface.
- Disposition: deferred.
- Why out of 0.2.6 scope: `artifacts/todo_stack.md` section "Out of 0.2.6 scope" freezes "An authorization or permission subsystem", and `artifacts/goal.md` section 3 rules "Authorization is not a jnwb capability claim." Each frozen item "needs its own authorization" before it returns.
- Where it stays discoverable: `artifacts/alignment_review_0.2.5.md` section Confirmed, and this row.
- Evidence that the state holds (`observed`): `grep -rniE "authori[sz]|permission|consent|approval|human-in-the-loop" skills/` returns 3 hits, all in `skills/jnwb-fact-action/SKILL.md`, all about `artifacts/fact_stack.md`. Unchanged from the review's count.

### doc-assets/mermaid-renders-as-source-text

- Finding: the same five diagrams reach readers as syntax-highlighted source.
- Disposition: reproduced. Claimed by 06-08.
- Evidence (`observed`): as for `identity/mermaid-diagrams-do-not-render-on-the-site`. The two identifiers are one defect found by two surveys; 06-08 closes both, and both are kept so the identifier set stays complete.

### reliability/jrsa-holm-silently-becomes-bh

- Finding: with statsmodels unimportable, `jnwb.jrsa` returns BH q-values for `correction='holm'` while recording `'holm'`.
- Disposition: reproduced. Claimed by 06-15.
- Evidence (`observed`): `jnwb/jrsa.py` is untouched since `6741d23c`; the fallback marker "Fallback BH via unified statistics module" is present (probe). The path is reachable in this checkout's own environment: `.venv\Scripts\python.exe -c "import statsmodels"` gives `ModuleNotFoundError: No module named 'statsmodels'`.

### public-claims/release-notes-declare-python-3-10

- Finding: the published v0.2.5 release notes say "Python 3.10 through 3.14" against `requires-python = ">=3.12"`.
- Disposition: already repaired.
- Evidence (`observed`): `gh release view v0.2.5 --json body -q .body | grep -c "3\.10"` returns `0`. The body now ends "Install: `pip install jnwb==0.2.5`. Python 3.12 through 3.14." `gh release view v0.2.5 --json tagName,publishedAt` returns `{"publishedAt":"2026-09-19T16:31:06Z","tagName":"v0.2.5"}`. 06-10 records the correction as landed at commit `026b9a6f` and scopes itself to the durable prevention only.

### public-claims/api-md-skills-url-typed-function

- Finding: `docs/api.md` types `jnwb.SKILLS_URL` as `function` with the `str` constructor signature.
- Disposition: reproduced. Claimed by 06-09.
- Evidence (`observed`): `grep -n "SKILLS_URL" docs/api.md` returns `15:| jnwb.SKILLS_URL | function | *str(object='') -> str str(bytes_or_buffer[, encoding[, errors]]) -> str* |`. Probe: `SKILLS_URL type: str`.

### identity/human-control-stated-as-caller-control-not-human-control

- Finding: the substance of human control is documented as caller, project or downstream control; "human" appears nowhere in `docs/`.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): `grep -rni "human" README.md docs/ jnwb/ --include=*.md --include=*.py` returns one line, `jnwb/paths.py:272: what: Human-readable description`. `artifacts/goal.md` section 3 restates the boundary without the word ("an agent may execute operations, and may not decide scientific assumptions"), so the substance has an authority; the published wording gap is unchanged. 06-06 publishes the ruling's boundary content into `docs/` and may absorb this, but its text does not name it, so it is not recorded as claimed.

### dynamic-conversion/compress-fp32-is-nwb-to-nwb-only

- Finding: the only public export producing an NWB-shaped file is an NWB-to-NWB rewrite, so it cannot serve as a conversion path.
- Disposition: deferred.
- Why out of 0.2.6 scope: `artifacts/goal.md` section 5 rules "Raw-data-to-NWB conversion is not added in 0.2.6", and the todo stack freezes it under "Out of 0.2.6 scope".
- Where it stays discoverable: the review section Confirmed, and this row.
- Evidence that the state holds (`observed`): `jnwb/compression.py` untouched since the review basis; the two package NWB writers are `jnwb/testing/nwb_fixtures.py:408` and `jnwb/testing/synth.py:693` (`grep -rn 'NWBHDF5IO(.*"w"' jnwb/ --include=*.py`).

### dynamic-conversion/no-skill-routes-conversion

- Finding: no skill routes a conversion or ingestion task.
- Disposition: deferred, for the reason above.
- Where it stays discoverable: the review section Confirmed, and this row.
- Evidence that the state holds (`observed`): `grep -rniE "pynwb|convert|translat|non-NWB|ingest" skills/` returns 4 lines, none a conversion route: `jnwb-connectivity/SKILL.md:22` (lag units), `jnwb-figures/SKILL.md:21` and `:38` (text outlines), `jnwb-nwb-data/SKILL.md:92` (`compress_fp32` to fp32). Identical to the review's result.

### skills/two-skills-carry-no-stop-language

- Finding: `jnwb-population` and `jnwb-figures` carry no stop, decline or non-identifiability language.
- Disposition: reproduced. Claimed by 06-25.
- Evidence (`observed`): per-file counts of `\bstop\b|declin|refus|unavailable|non-identifiab|accepted=False|\braise|censored|missing` give `connectivity 1, fact-action 2, figures 0, lfp-spectral 5, nwb-data 6, population 0, spiking 1, statistics 1, jnwb 1`. Identical to the review.

### skills/ontology-subsystem-unreachable-from-any-skill

- Finding: the whole `jnwb.ontology` surface is named by no skill.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): `grep -rnE "ontology|Provenance|Lineage|Interpretation|EpochCollection|AlignedDataset" skills/` returns 0 matches. 06-24 checks the routing rows that exist; nothing in the stack claims coverage of an unrouted module.

### skills/no-nwb-conversion-anywhere

- Finding: no skill routes NWB writing or format conversion; the public API exports none.
- Disposition: deferred, for the raw-data-to-NWB reason above.
- Where it stays discoverable: the review section Confirmed, and this row.
- Evidence that the state holds (`observed`): the skills grep above; `len(jnwb.__all__)` is 156 and the only writer among them is `compress_fp32`, which rewrites an existing NWB file.

### skills/workflow-blocks-never-executed-by-the-harness

- Finding: no test executes any SKILL.md python block.
- Disposition: reproduced. Claimed by 06-26.
- Evidence (`observed`): `grep -rn "exec(" tests/ | grep -i skill | wc -l` returns `0`.

### doc-assets/asset01-capability-map-split-and-unchecked

- Finding: no single maintained capability map; three partial candidates with different maintenance status.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): `grep -n "Capabilities" README.md` returns `24`; `grep -n "Module Map" docs/01_architecture_and_philosophy.md` returns `104:## 4. Module Map & Architecture Summary`; `docs/api.md` is generated and gate-enforced (gate 9 passes in the run above). 06-30's diagram list names dual entry, the code/documentation/tests relation, the four-outcome decision, NWB to analysis and the package boundary -- not a capability map.

### doc-assets/asset02-code-docs-skills-diagram-absent

- Finding: no code-documentation-skills architecture diagram exists in `docs/`.
- Disposition: reproduced. Claimed by 06-30 ("code, documentation and tests with skill routing over them").
- Evidence (`observed`): the five mermaid fences above are the only diagrams in `docs/`, and `docs/01_architecture_and_philosophy.md` is untouched since the review basis. `grep -rn "direction\.md\|planned_post\|goal\.md" AGENTS.md CONTRIBUTING.md README.md docs/` returns 0, so the ASCII original is still unpublished.

### doc-assets/asset03-semantics-distinction-diagram-absent

- Finding: no scientific-semantics distinction diagram exists; the distinctions are prose plus one PNG panel.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): `docs/` unchanged apart from `install.md`; no diagram was added. Not in 06-30's named set.

### doc-assets/asset04-test-hierarchy-diagram-absent

- Finding: no reliability or test-hierarchy diagram exists anywhere.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): `docs/` unchanged apart from `install.md`; `CONTRIBUTING.md` untouched since the review basis. Not in 06-30's named set.

### ai-plumbing/agent-roles-exist-but-ship-nowhere

- Finding: the role structure is fully specified but lives only in `artifacts/` and `skills/`, is referenced from no page in `docs/`, and `artifacts/` is pruned from the sdist.
- Disposition: reproduced, with one count corrected. Unclaimed.
- Evidence (`observed`): `ls artifacts/agents/` returns six files (`actor.md authority.md critic.md docs-harness.md jnwb-developer.md verifier.md`), not the five the review recorded; `artifacts/agents/jnwb-developer.md` was added after the review basis and `AGENTS.md`'s role map was corrected to match. `grep -rniE "docs-harness|jnwb-developer|\bverifier\b" docs/` returns 0. `grep -n "prune" MANIFEST.in` returns `18:prune artifacts`.
- Note, not a disposition: the amended `AGENTS.md` rule (2026-09-19) keeps internal repository roles out of public documentation, so the repair this finding implies may be one the current rule forbids. That is a scope question for 06-17 and 06-05, not for this ledger.

### ai-plumbing/generator-boundary-is-naming-not-enforcement

- Finding: the "does not generate data" boundary is naming and documentation, not an output-level mechanism.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): both NWB writers are inside `jnwb/testing/` (`grep -rn 'NWBHDF5IO(.*"w"' jnwb/ --include=*.py` returns `jnwb/testing/nwb_fixtures.py:408` and `jnwb/testing/synth.py:693`); `jnwb/` and `docs/10_operation_specifications.md` are untouched since the review basis. `artifacts/goal.md` section 4 now rules the boundary explicitly ("jnwb never substitutes synthetic values for missing empirical data in an analysis path") but adds no mechanism.

### ai-plumbing/no-nwb-conversion-asset

- Finding: no MCP tool, routing row or public export converts a non-NWB dataset into NWB.
- Disposition: deferred, for the raw-data-to-NWB reason above.
- Where it stays discoverable: the review section Confirmed, and this row.
- Evidence that the state holds (`observed`): the skills and writer greps above; `jnwb/mcp_server/` untouched since the review basis.

### reliability/contributing-taxonomy-is-a-different-one

- Finding: the only durable account of testing expectations is a flat nine-item probe list, not a five-tier hierarchy.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): `CONTRIBUTING.md` is untouched since `6741d23c`, so its "Testing rule" list is unchanged. The five-tier structure the finding contradicts came from the superseded target, and `artifacts/goal.md` names no test hierarchy -- whether that dissolves the finding is a scope call for 06-17.

### reliability/hierarchy-exists-only-in-suite-shape

- Finding: nothing mechanical encodes a test hierarchy -- no custom markers, no tier naming, one flat CI invocation.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): `grep -n "markers" pyproject.toml` returns no output; `grep -rno "pytest\.mark\.[a-z_]*" tests/ | sort -u` returns `pytest.mark.parametrize` and `pytest.mark.skipif`, nothing else.

### public-claims/no-gate-reads-release-notes

- Finding: every surface stating Python support is gated except the GitHub Release body.
- Disposition: reproduced. Claimed by 06-11.
- Evidence (`observed`): `grep -rniE "release note|gh release|release body" scripts/ tests/ | wc -l` returns `0`. Gate 8 now covers pyproject, classifiers, the CI matrix and `.readthedocs.yaml`; the release body remains unread.

### public-claims/readme-omits-agent-surface

- Finding: README -- verbatim the PyPI description -- never mentions MCP or skills.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): `grep -niE "mcp|skill|agent" README.md` returns one line, `135:If you are an AI agent, read [AGENTS.md](...) first.` The only README change since the review basis is the Python-support sentence at `:41`.

### evaluation-and-roadmap/p0-is-a-hypothesis-and-constraints-not-a-design

- Finding: P0 states a hypothesis and pre-registration constraints and says the design work has not been done.
- Disposition: reproduced. Claimed by 06-33.
- Evidence (`observed`): `git diff 6741d23c..HEAD -- artifacts/planned_post_0.2.5.md` changes only the opening paragraph, which now adds "it is candidate input to a cycle that must reproduce each item, not a queue of accepted work." P0 itself is unchanged. 06-33 requires task set, scoring rubric, arms, repetitions, refusal scoring and inferential unit to be declared and marked unrun.

### evaluation-and-roadmap/roadmap-and-direction-are-unindexed

- Finding: `planned_post_0.2.5.md` has zero inbound references and `direction.md` two, one broken; neither appears in the orientation table, CONTRIBUTING, README or `docs/`.
- Disposition: reproduced. Unclaimed.
- Qualification: the substance reproduces; the reference counts the review states have drifted. The disposition field carries one of the five words and nothing else, so a qualifier lives here.
- Evidence (`observed`): `grep -rn "direction\.md\|planned_post\|goal\.md" AGENTS.md CONTRIBUTING.md README.md docs/` returns 0 matches, so the orientation half is unchanged; `AGENTS.md` section 0 lists `artifacts/agents/`, `todo_stack.md`, `fact_stack.md` and `benchmarks/` and no ruling document. The inbound-reference half has moved: `artifacts/goal.md:3`, `artifacts/planned_post_0.2.5.md:9` and several `artifacts/todo_stack.md` lines now cite `direction.md`, and `todo_stack.md:78` and `:604` cite `planned_post_0.2.5.md`, so "zero inbound references" is no longer true. The broken pointer the finding mentions was fixed: `artifacts/direction.md:120` now reads `artifacts/todo_stack_0.2.5.md`.

### ai-plumbing/writes-nothing-guard-is-narrow

- Finding: the mechanical guard behind "it writes nothing" is a source scan for the literal `write_text`.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): `grep -n "write_text" tests/test_mcp_server.py` returns `263:                "write_text", source,`, the only guard. `tests/test_mcp_server.py` and `jnwb/mcp_server/` are untouched since the review basis.

### public-claims/install-md-states-no-python-requirement

- Finding: `docs/install.md` states no minimum Python version.
- Disposition: already repaired.
- Evidence (`observed`): `git diff 6741d23c..HEAD -- docs/install.md` adds, after the `pip install` block, "Requires Python **3.12 or newer**. Tested in CI on 3.12, 3.13 and 3.14."

## Upheld with dissent (12)

### identity/agents-vocabulary-rule-forbids-the-planned-doc-assets

- Finding: `AGENTS.md` forbids naming agents anywhere in `docs/`, the place the planned AI-facing assets must live.
- Disposition: already repaired.
- Evidence (`observed`): `git diff 6741d23c..HEAD -- AGENTS.md` replaces the four-places rule with "Public documentation may describe AI agents, skills, routing, and agent-assisted use when these are public jnwb capabilities", drops `docs/` from the excluded list, and adds "Amended 2026-09-19. The previous rule named `docs/` among the places harness vocabulary may not appear, which contradicted an intentionally agent-usable package and was already broken by four published pages." 06-02 is the item that ruled it.

### dynamic-conversion/no-public-nwb-write-export

- Finding: of 156 public names, "not one of them constructs or writes an NWB file".
- Disposition: refuted.
- Evidence (`observed`): the review's own dissent names the counterexample, and it holds here. `grep -n "'compress_fp32'" jnwb/__init__.py` returns `223`, so it is one of the 156, and `jnwb/compression.py` writes a new NWB file to `dst`. The finding's method was a regex over export names for write verbs, which cannot see a writer whose name carries no verb. The narrower true statement -- that no export builds an NWB file from non-NWB input -- is carried by `skills/no-nwb-conversion-anywhere` and `ai-plumbing/no-nwb-conversion-asset`, both deferred above, so nothing is lost by refuting this one.

### dynamic-conversion/only-nwb-writer-is-a-synthetic-data-generator

- Finding: the only pynwb write path in the distributed package is a synthetic-recording generator, and it ships.
- Disposition: refuted.
- Evidence (`observed`): the literal pynwb-path claim reproduces -- `grep -rn 'NWBHDF5IO(.*"w"' jnwb/ --include=*.py` returns only `jnwb/testing/nwb_fixtures.py:408` and `jnwb/testing/synth.py:693`. The load-bearing inference does not: the dissent's counterexample `compress_fp32` is public, writes an NWB file, and generates nothing, and `artifacts/goal.md` section 4 now rules that "Explicit synthetic testing and calibration infrastructure remains valid and is not an analysis surface." The shipped-fixture fact is retained here so it stays discoverable.

### evaluation-and-roadmap/out-of-scope-rejection-has-no-behaviour-to-score

- Finding: no skill file contains a decline rule, so by the repository's own criterion every skill is incomplete on the dimension P0 proposes to score.
- Disposition: reproduced. Claimed by 06-25.
- Evidence (`observed`): `grep -rniE "\bdecline" skills/ | wc -l` returns `0`, unchanged. The dissent argues seven agent-facing rules already implement direction.md's cases without the word; 06-25 settles it the only way that decides between them, by requiring executable evidence per skill and recording a skill that does not need it.

### doc-assets/module-map-omits-nwb-entry-points

- Finding: the docs/01 module map has 21 rows and omits 8 modules owning 36 public exports.
- Disposition: reproduced, with the export count corrected to 35. Unclaimed.
- Evidence (`observed`): provenance-asserted probe returns `DOC01_MODULE_MAP_ROWS: 21`; modules owning public exports with no row are `continuous 1, io 1, laminar 8, nwb_events 9, nwb_inspect 10, nwb_io 1, rsa 2, tfr 3` -- 8 modules, 35 exports, plus 8 module-level constants that belong to no submodule. The review said 36 and its own dissent said 35; my count is 35, so the finding's number is wrong by one and its substance stands.

### ai-plumbing/readme-silent-on-mcp-and-skills

- Finding: README mentions neither the MCP server nor the skills; its capability table is ten library rows.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): `grep -niE "mcp|skill|agent" README.md` returns the single line `135`. Same subject as `public-claims/readme-omits-agent-surface`; both are kept so the identifier set stays complete, and one repair closes both.

### ai-plumbing/authorization-has-no-mechanism

- Finding: nothing enforces authorization; the only `authoriz` occurrence under `jnwb/` is a hardcoded `False` no code consumes.
- Disposition: deferred.
- Why out of 0.2.6 scope: `artifacts/todo_stack.md` section "Out of 0.2.6 scope" freezes "An authorization or permission subsystem"; `artifacts/goal.md` section 3 rules authorization out of the capability set.
- Where it stays discoverable: the review section "Upheld with dissent", and this row.
- Evidence that the state holds (`observed`): probe returns `training_authorized literal False present: True` in `jnwb/decoding.py`; `jnwb/` is untouched since the review basis.

### reliability/suite-size-and-collection-error

- Finding: 118 test files, 2841 collected, and collection does not complete cleanly in the repository's own `.venv` because statsmodels -- a declared hard dependency -- is absent.
- Disposition: reproduced, in the environment the finding named. Claimed by 06-35.
- Evidence (`observed`), both interpreters, because they disagree and the disagreement is the point:
  - `.venv\Scripts\python.exe -m pytest --collect-only -q` gives `2841 tests collected, 1 error in 9.59s`, `ERROR tests/test_estimator_values_are_pinned.py`, `Interrupted: 1 error during collection`; `.venv\Scripts\python.exe -c "import statsmodels"` gives `ModuleNotFoundError`.
  - `python -m pytest --collect-only -q` (C:\Python314, statsmodels 0.14.6) gives `2879 tests collected in 26.76s`, no error.
  - `ls tests/test_*.py | wc -l` gives `118`.
  This is an environment condition, not a package defect: the suite collects clean wherever the declared dependency is installed. 06-35 holds the clean-environment matrix and states "The development virtualenv is not package evidence."

### public-claims/readme-table-omits-ontology-laminar-analyzers

- Finding: eight modules have zero representation in the README capability table, three of them substantial.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): the README capability table is unchanged since the review basis, and the module-coverage probe above reproduces the omission. The dissent's qualifier also reproduces: `README.md:26` reads `| Area | Representative API |`, so the table declares itself representative. Whether a self-declared representative table may omit a module is the open question 06-17 inherits.

### evaluation-and-roadmap/p0-forbids-the-paper2agent-transfer

- Finding: presenting the skills layer as demonstrated rather than hypothesised would contradict a written ruling.
- Disposition: refuted.
- Evidence (`observed`): the receipts verify -- `artifacts/planned_post_0.2.5.md` P0 is still headed "(hypothesis, ruled 2026-09-17)" and `artifacts/direction.md` Prior art is unchanged except the `todo_stack_0.2.5.md` pointer. No repository asset makes the forbidden claim: the deck that would have made it is not a repository artifact, and the statement jnwb is now measured against, `artifacts/goal.md`, asserts no benchmark result. A ruling being obeyed is not a defect.

### evaluation-and-roadmap/nearest-roadmap-record-is-p0-p3-plus-three-bullets

- Finding: the repository's whole recorded roadmap is P0-P3 plus three bullets in the todo stack; "Nothing else is recorded as planned work."
- Disposition: refuted.
- Evidence (`observed`): the completeness claim was false when written -- the dissent names `artifacts/direction.md`, which `planned_post_0.2.5.md:9` itself makes authoritative over its contents -- and the inventory has since moved: `grep -n "^# Before 1.0" artifacts/todo_stack.md` returns no output, the three bullets are gone, and the stack is now a 0.2.6 cycle with its own "Reported and not admitted" and "Out of 0.2.6 scope" sections. Both halves of the statement fail.

### dynamic-conversion/write-mode-reachable-through-undeclared-module-attribute

- Finding: `jnwb.nwb_io` is reachable as a package attribute despite being module-internal, and `nwb_read_io` forwards a non-`"r"` mode straight to `NWBHDF5IO`.
- Disposition: reproduced. Unclaimed.
- Evidence (`observed`): provenance-asserted probe returns `hasattr(jnwb,'nwb_io'): True`, `nwb_read_io mode default in signature: True`, `nwb_read_io forwards non-r mode: True`. `jnwb/nwb_io.py` and `jnwb/__init__.py` are untouched since the review basis. The dissent argues the reachability does not matter because a documented public writer already exists; that is an argument about consequence, not about the state, and no stack item names the surface test's narrowness.

## One unverified finding a packet reached

06-03 leaves the unverified tail undispositioned "unless a batch reaches one". This packet was
directed at one of them.

### public-claims/classifier-3-13-never-tested

- Finding: the package claims Python 3.13 in its classifiers; CI never runs on 3.13.
- Disposition: already repaired, in the working tree only.
- Evidence (`observed`): `git diff 6741d23c..HEAD -- .github/workflows/workflow.yml` turns `python-version: [ "3.12", "3.14" ]` into `[ "3.12", "3.13", "3.14" ]`; `scripts/harness_gate.py` `PYTHON_CI_REQUIRED` becomes `("3.12", "3.13", "3.14")`; `python scripts/harness_gate.py` prints "classifiers ['3.12', '3.13', '3.14'], CI covering ['3.12', '3.13', '3.14'] all agree."
- What no repository change can repair (`observed`): the published v0.2.5 artifact still carries the 3.13 classifier that no CI leg of that release exercised. A shipped artifact is immutable, and editing the repository does not alter it. The gap closes for the next release, not for 0.2.5.
- Two corrections to the packet's own description of this finding (`derived`, from the review text): it is filed under "Unverified tail", not among the confirmed findings, and it is graded `low - risk`. The review does not call the gate broken. 06-03's body states the same conclusion the packet does -- that the gate permitted the gap by design and this was a policy question -- and that reading is correct: gate 8 checked containment against `PYTHON_CI_REQUIRED` and never related the classifier set to the matrix. 06-10 remains open for exactly that durable prevention and is not closed by the surface convergence.

## Unverified tail (35 remaining, deferred as a set)

Below the review's verification cap, carried without adversarial checking. `artifacts/todo_stack.md`
section "Out of 0.2.6 scope" freezes "The 36 unverified review findings, except where a batch above
reaches one", so each is `deferred` under that ruling rather than individually dispositioned here.
They stay discoverable at `artifacts/alignment_review_0.2.5.md` section "Unverified tail", and every
identifier is in the index above, so a later cycle can enumerate them without reading this prose.
The 36th, `public-claims/classifier-3-13-never-tested`, is dispositioned above.

```text
identity/does-not-generate-data-unstated-about-the-ai
identity/authorization-claim-has-no-matching-asset
identity/nwb-translation-capability-does-not-exist
identity/decline-semantics-live-only-in-a-pruned-artifact
identity/direction-md-is-the-identity-source-and-is-unpublished
identity/landing-page-asset-exists-but-not-the-overview-diagram
identity/docs-overstates-what-the-gates-enforce
skills/every-worked-example-synthesizes-its-input
skills/router-gpu-paragraph-partly-false
skills/skills-absent-from-architecture-diagram-and-readme
doc-assets/asset05-skill-to-tool-diagram-absent
doc-assets/asset06-failure-decision-diagram-absent
doc-assets/asset07-no-openscope-tutorial-or-figure
doc-assets/asset08-responsibility-diagram-unpublished
doc-assets/asset09-ai-benchmark-is-an-unstarted-hypothesis
doc-assets/asset10-landing-page-overview-diagram-absent
doc-assets/generate-figures-runs-nowhere
doc-assets/generate-figures-output-not-reproducible
doc-assets/direction-md-states-the-principle-the-repo-does-not-yet-meet
evaluation-and-roadmap/p2-provenance-candidate-already-shipped
evaluation-and-roadmap/paper2agent-absent-from-published-references
identity/dangling-spec-pointer-in-public-docstrings
identity/todo-stack-cites-a-direction-section-that-does-not-exist
identity/end-to-end-pipeline-page-title-vs-not-a-pipeline
dynamic-conversion/conversion-script-provenance-points-at-nothing
dynamic-conversion/ontology-docstring-names-a-method-that-does-not-exist
skills/stale-eight-in-validation-docstring
doc-assets/quickstart-svg-copy-is-stale-and-unchecked
ai-plumbing/skills-url-mislabelled-in-api-page
public-claims/changelog-0-1-0-python-range
evaluation-and-roadmap/todo-stack-points-at-a-heading-that-does-not-exist
evaluation-and-roadmap/closure-records-filed-under-findings-marked-unsupported
evaluation-and-roadmap/empty-marker-nested-under-section-12
evaluation-and-roadmap/close-out-gate-condition-not-satisfiable-as-written
evaluation-and-roadmap/p3-line-numbers-and-one-claim-have-drifted
```

Observations made while dispositioning other findings, recorded as observations and not as
dispositions, because 06-03 forbids individually dispositioning this set:

- `skills/stale-eight-in-validation-docstring` is repaired at HEAD. `git diff 6741d23c..HEAD -- tests/test_skills_validation.py` changes the docstring from "the 8 intended canonical skill directories" to "the 9".
- Three overlap with findings dispositioned above and would resolve the same way: `ai-plumbing/skills-url-mislabelled-in-api-page` (with `public-claims/api-md-skills-url-typed-function`, 06-09), `identity/nwb-translation-capability-does-not-exist` and `identity/authorization-claim-has-no-matching-asset` (with the frozen non-goals).

## Refuted by the review (4)

Carried through so the set of 83 stays complete and countable. The disposition is the review's own,
and each refutation is summarised from its recorded dissent; none was re-litigated here.

| Identifier | The review's refutation |
|---|---|
| `identity/ai-identity-absent-from-published-surface` | "The published surface never describes jnwb as AI-assisted" is contradicted by `docs/agents.md`, a nav-listed page titled "Analyzing with an Agent". The literal greps reproduced; the load-bearing clause did not. |
| `dynamic-conversion/no-test-writes-nwb-through-a-public-export` | The `compress_fp32` half verified verbatim, but both load-bearing sentences failed the dissent's checks. |
| `reliability/no-testing-and-reliability-guide` | The narrow checks verified; a load-bearing sentence and the inference from it are contradicted by the repository, and the nav block was miscited. |
| `evaluation-and-roadmap/no-ai-interface-benchmark-asset-exists` | Every cited path and line verified, but the receipt enumerates filenames under `artifacts/benchmarks/` only and therefore cannot support a repository-wide absence claim. |

## Unclaimed reproduced findings

Sixteen findings reproduce and no stack item names them. 06-17 dispatches one packet per entry,
highest consequence first.

```text
identity/human-control-stated-as-caller-control-not-human-control
skills/ontology-subsystem-unreachable-from-any-skill
doc-assets/asset01-capability-map-split-and-unchecked
doc-assets/asset03-semantics-distinction-diagram-absent
doc-assets/asset04-test-hierarchy-diagram-absent
ai-plumbing/agent-roles-exist-but-ship-nowhere
ai-plumbing/generator-boundary-is-naming-not-enforcement
reliability/contributing-taxonomy-is-a-different-one
reliability/hierarchy-exists-only-in-suite-shape
public-claims/readme-omits-agent-surface
evaluation-and-roadmap/roadmap-and-direction-are-unindexed
ai-plumbing/writes-nothing-guard-is-narrow
doc-assets/module-map-omits-nwb-entry-points
ai-plumbing/readme-silent-on-mcp-and-skills
public-claims/readme-table-omits-ontology-laminar-analyzers
dynamic-conversion/write-mode-reachable-through-undeclared-module-attribute
```

Three pairs among the 29 reproduced entries are one defect seen twice, and one repair closes each
pair: the two mermaid findings, the two README agent-surface findings, and the SKILLS_URL pair
whose second half sits in the unverified tail. Both identifiers are kept in every case.

## What this ledger does not decide

- Whether a reproduced finding is worth repairing. That is 06-05's frozen acceptance set and
  06-17's per-finding packets.
- Whether the amended `AGENTS.md` vocabulary rule forbids the repair implied by
  `ai-plumbing/agent-roles-exist-but-ship-nowhere`.
- Whether a README table that declares itself representative may omit a module.
