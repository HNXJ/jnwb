# 0.2.5

Audited read-only at `3f432306` (0.2.4, released and served by PyPI) across code, tests,
docs, skills, packaging, CI and backends. Each item carries the observation that produced it.
Items are deleted when done; finished work is not recorded here.

What the green state did not prove: the suite runs against the checkout and never against the
installed wheel (`pythonpath = ["."]`); `docs/api.md` is generated from `__all__` and then
checked against it; gate 5 is satisfied by its own generator; and a declared hard dependency
can be absent while 1465 tests pass, because two modules convert the `ImportError` into NaN.

## Execution protocol (authorized 2026-09-16)

The stack is frozen. It is executed to empty in dependency batches, not as 84 approval cycles:
A `05-01..25` scientific correctness, B `26..42` API and NWB, C `43..52` performance and
backend, D `53..60` tests, E `61..66` docs, F `67..72` skills and agents, G `73..78` packaging,
H `79..82` harness, I `83..84` independent critic and release.

Within a batch: reproduce, repair, add the discriminator, continue. Critical and high findings
are reproduced first. **A finding that does not reproduce is marked unsupported with its
evidence and its item deleted -- correct code is not modified to match a wrong audit.** One
batch-level regression and gate run, then commit and push, then the next batch.

The numbering controls coverage, not ordering: when a defect being repaired is mechanically
preventable, the smallest relevant repair from `05-79..82` is applied in that batch rather than
deferred to H, so later work benefits from the gate.

Qualification runs in a clean environment built from the declared extras, or in CI. The
development `.venv` described at the end of this file is not package evidence.

## 9. Documentation

### 09 note: the persona is a neuroscientist who knows `pynwb` and nothing else, going install -> inspect their own file -> select data explicitly -> analyze -> interpret, without reading contributor material.

## 10. Skills and agents

**Acceptance condition for every item in this section** (ruled 2026-09-17, stated in
`artifacts/direction.md` under "Skill behaviour"): a skill routes to an operation or it
declines -- supported analysis executes, missing information is requested, a
non-identifiable result is reported as a failure, an unsupported claim is not inferred.
Where an item already edits a skill, the edited skill must satisfy this and representative
routing behaviour must be tested. Skills are release surfaces: verify against live exports
and docs, not against the skill's own text.

### 05-71 One skill overclaims a safeguard the router and `AGENTS.md` both state correctly
- **Problem** `skills/jnwb-lfp-spectral/SKILL.md:23` calls `imaginary_coherency` "volume-conduction-robust", while the router section 4.8 and `AGENTS.md` section 5 both say these measures "reduce sensitivity specifically to zero-phase-lag coupling; they do not establish immunity". Its neighbouring `wpli` row uses the correct phrasing.
- **Evidence** Same file, adjacent lines.
- **Change** Match the `wpli` row. Also add the narrowband PSI exclusion: the connectivity skill's own verification instruction ("verify PSI returns positive slope for driver") fails on narrowband — a 20 Hz sinusoid with 10 ms delay over a 19-21 Hz band gives `net=0.0000, sd=0.0, n_freq_bins=3, z=1.07e8`, while the same delay over 15-30 Hz gives 0.9161. And add the group-delay caveat to `jnwb-spiking`: it mandates `causal_exp_smooth` for latency without stating that the filter shifts onset by about 0.7*tau (measured: tau=25 gives +10 ms, tau=50 gives +30 ms), which `common_mistakes.md` section 8 documents and no skill repeats.
- **Preserves** The safeguards, which are otherwise the tree's best asset.
- **Discriminator** No skill states a stronger claim than the router.
- **Accept** Cross-checked against `AGENTS.md` section 5 and `docs/common_mistakes.md`.

### 05-72 The MCP server has a fourth tool that writes code, is undocumented, and never loads
- **Problem** `docs/agents.md:24` says "Three tools, all of them ingest"; `mcp.list_tools()` returns four.
- **Evidence** `['inspect_nwb', 'prepare_signal_reference', 'get_event_codes_and_timings', 'add_tool']`. `add_tool(code)` writes Python source into the installed package directory, gated only by `ALLOW_DYNAMIC_TOOLS=1`, and appends to `custom_tools.py` — which `jnwb/mcp_server/__init__.py` does not import, so its "Please restart the MCP server to load the new tool" message is false at any restart. `docs/10:18` gives a third number by pointing at `jnwb.mcp_server.__all__`, which has five entries.
- **Change** Decide whether `add_tool` ships. If it does: document it and its env gate, and wire `custom_tools` into `__init__.py` so the message is true. If not: drop it from `__init__.py`. Point every count at the live registry rather than restating it.
- **Preserves** The three ingest tools.
- **Discriminator** The documented tool list equals `mcp.list_tools()`.
- **Accept** A test compares the documented table against the live registry. Ruled 2026-09-16: resolve from evidence, not by asking. Inspect `add_tool` for mutation scope, input validation, security boundary and overlap with the other three tools. Keep it, wire `custom_tools` in and document four tools only if it is a distinct, safe, generic operation genuinely intended for external agents; otherwise remove it from the exposed MCP surface and document three. Public exposure requires intent, and the live implementation -- not the stale docs -- is the authority on what it does.

## 11. Packaging

### 05-73 A build from `dev` today produces a different distribution calling itself 0.2.4
- **Problem** The version is not bumped after a release, and nothing compares the declared version against what the index already serves.
- **Evidence** HEAD is 5 commits past `v0.2.4` with `__version__ = '0.2.4'` and 20 non-empty lines under `## [Unreleased]` naming three shipped fixes. Local wheel against the PyPI wheel: `> jnwb/mcp_server/__main__.py`. Local sdist carries `AGENTS.md` and `skills/` (261,291 B) where PyPI's does not (238,292 B). `test_release_date_matches_the_changelog_entry_for_this_version` passes, because it compares the version to its own changelog entry and never to the index.
- **Change** Add a release-gate step: fail when `jnwb.__version__` already appears in the PyPI index and `CHANGELOG.md` has a non-empty `## [Unreleased]`.
- **Preserves** The existing version-sync gate 7.
- **Discriminator** The current tree fails the new check.
- **Accept** Two distributions can never share a version string.

### 05-74 Seven of ten dependency floors cannot be installed on any supported interpreter
- **Problem** Floors copied from an older support window and never re-derived after the 3.12 floor landed.
- **Evidence** PyPI metadata: `numpy==1.22.0` tags `['cp310','cp38','cp39','pp38','sdist']`; `scipy==1.8.0` declares `requires_python '>=3.8,<3.11'`, which contradicts `requires-python = ">=3.12"` outright; `pandas==1.4.0`, `h5py==3.6.0`, `matplotlib==3.5.0`, `scikit-learn==1.0.0`, `statsmodels==0.13.0` ship no cp312 or pure-python wheel. Separately `jnwb.statistics` and `jnwb.connectivity` call `scipy.stats.false_discovery_control`, added in SciPy 1.11, three minor versions above the declared floor — masked only because scipy <1.11 cannot install on 3.12.
- **Change** Raise each floor to the oldest release with a cp312 artifact, or delete the floors and state that the package takes whatever pip resolves on 3.12.
- **Preserves** Current resolutions, which are all far above the floors.
- **Discriminator** Every declared floor is installable on the declared interpreter.
- **Accept** `pip install 'numpy==<floor>'` succeeds on 3.12 for each dependency.

### 05-75 The forbidden-path check cannot see `tests/` or `scripts/` in the wheel
- **Problem** `forbidden = [..., '/tests/', '/scripts/']` substring-matched against archive entries whose delimiters differ by format.
- **Evidence** `'/tests/' in 'tests/__init__.py'` is False. Wheel entries have no leading component, so the check works only for the sdist, whose entries are `jnwb-0.2.4/tests/...`.
- **Change** Match on path components for the wheel; keep the substring form for the sdist; `workflow.yml:89`, `release_gate.py:178`.
- **Preserves** The sdist check.
- **Discriminator** A wheel containing a top-level `tests` package fails.
- **Accept** Verified by constructing such a wheel in a scratch directory.

### 05-76 CI never runs the suite against the installed distribution
- **Problem** `pytest -v tests/` runs from the checkout root and `pythonpath = ["."]` puts the checkout ahead of site-packages, so the four-cell matrix tests the source tree that also happens to have the package installed. Only the single-cell build job touches the wheel.
- **Evidence** `workflow.yml:49`, `pyproject.toml:107`. Several test docstrings reason about wheel behaviour while importing the checkout.
- **Change** One matrix leg, or one extra step, that installs the built wheel and runs pytest from a directory outside the checkout with `pythonpath` overridden.
- **Preserves** The existing legs, which need `pythonpath` for the `scripts.*` gate tests.
- **Discriminator** A defect present only in the packaged artifact fails CI.
- **Accept** The claim "tested against the installed wheel" becomes true for the suite, not only for the tutorials.

### 05-77 The skills distribution decision
- **Problem** `MANIFEST.in`'s comment describes an outcome its mechanism does not produce.
- **Evidence** `graft skills` places the tree at the sdist root, outside any package; `packages.find` is `include = ["jnwb*"]`, so `pip install jnwb-0.2.4.tar.gz` installs `jnwb/` and discards `skills/` and `AGENTS.md`. Only someone who untars by hand receives them — and the sdist carries no `docs/`, `tests/` or `scripts/`, so 11 of 12 skill documentation links dangle inside it and the skills' own verification steps cannot run there. `grep -rn "skills" jnwb/ --include=*.py` returns zero hits: nothing in the runtime reads them.
- **Change** Recommendation from the packaging audit, for a ruling: keep `skills/` in the sdist as source, correct the `MANIFEST.in` comment to say what it does, and do not put the tree in the wheel — the consumer is a harness configured by path, not the Python runtime, and `site-packages` is the worst place to put something that must be pointed at. Close the discovery gap instead with a machine-readable pointer (a `jnwb.SKILLS_URL` constant naming the GitHub tree). The `importlib.resources` and console-entry-point routes both require the tree inside the wheel, which is the second tree gate 2 forbids.
- **Preserves** Exactly one canonical skill tree.
- **Discriminator** A `pip install` user can find the skills without guessing.
- **Accept** Ruled 2026-09-16, as recommended: one canonical tree in the repository; ship `skills/` in the sdist where appropriate; do **not** create a duplicate `jnwb/.../skills` tree to force them into the wheel. Wheel runtime resources carry skills only if a runtime loader needs them, and none does -- `grep -rn "skills" jnwb/ --include=*.py` returns nothing. Packaging symmetry is not an objective. Correct the `MANIFEST.in` comment to describe what its mechanism actually does, and close the discovery gap with a machine-readable pointer. This closes the open half of the carried-forward 05-02.

### 05-78 Declared test tooling that is never invoked, and a second source of truth for the docs pins
- **Problem** Unused declarations and duplicated configuration.
- **Evidence** `pytest-cov` and `pytest-xdist` are declared, and the `test` extra pulls `pytest-cov-7.1.0`, `coverage-7.16.1`, `pytest-xdist-3.8.0` and `execnet-2.1.2` onto all four CI cells; there is no `addopts`, no `--cov` and no `-n` anywhere in the repository. `.readthedocs.yaml` installs both `docs/requirements.txt` and `.[docs]`; the two lists are byte-identical today and nothing compares them, while `fail_on_warning: true` means a drift is a failed publish. Also: `scripts/build_unified_review.py` and `scripts/reconcile_review_probes.py` have zero references anywhere (625 lines), and `harness_gate.py:205` holds a root-allowlist exemption for `jnwb-unified-rev.md`, the output of the first of them.
- **Change** Drop both pytest plugins or make the declaration true with an `addopts`; delete `docs/requirements.txt` and its `.readthedocs.yaml` entry; retire both dead scripts and the allowlist entry.
- **Preserves** Every live script: `docs_build`, `generate_api_md`, `harness_gate`, `release_gate`, `calibrate_vflip`, `mkdocs_version_hook`, `benchmark_import`.
- **Discriminator** Every declared dependency and every script has a caller.
- **Accept** All six extras resolve (verified: `mcp` 24, `torch` 9, `gpu` 6, `test` 78, `docs` 25, `all` 107 packages, all exit 0, `all` an exact union). Note `jnwb[gpu]` installs cleanly with no CUDA and yields no GPU, because plain `jax`/`jaxlib` from PyPI is CPU-only: it should be `jax[cuda12]`.

## 12. Harness and gates

### 05-79 Nine of thirteen gates can pass on a broken tree
- **Problem** Presence and substring checks standing in for behaviour.
- **Evidence, each reproduced** Gate 11: a root directory containing `.py` files and no `__init__.py` is importable as a PEP 420 namespace package and is not flagged, so JNWB-002 reproduces green; `test_non_package_directory_is_not_flagged` locks the hole in. Gate 13: a README stating the three symbols are REMOVED, all nine tutorials raising `SystemExit`, and a commented-out mkdocs nav line all pass. Gate 5: satisfied by `docs/api.md`, which is generated from `__all__` — it cannot fail while gate 9 passes, and substring matching means short names match inside longer ones. Gate 7: a `pyproject.toml` whose `attr` binding sits inside a comment, plus `version = "0.0.1"`, passes. Gate 8: every block is guarded by `if <file>.exists():` with no `else`, so an empty directory passes the Python-policy gate; and `PYTHON_CI_REQUIRED` omits 3.13 while the gate prints "all agree" for a classifier set that includes it. Gate 3: the drive-letter allowlist does not include `E:/`, which is in use on this machine. Gate 2: checks one hardcoded path, so a duplicate tree at `jnwb/skills/` or `docs/skills/` passes. Gate 4: the allowlist carries four entries that do not exist. Gates 5, 10 and `test_docs_links` all use non-recursive `glob("*.md")` and therefore miss the same nine live files under `docs/tutorials/` — reproduced by planting `jnwb==0.0.9` there.
- **Change** Gate 11 -> `find_spec`. Gate 13 -> parse the mkdocs YAML and `compile()` each tutorial, or demote it. Gate 5 -> retire, subsumed by gate 9, and replace with the check 05-41 needs: every `__all__` symbol mentioned outside the generated reference. Gate 7 -> parse with `tomllib`. Gate 8 -> add `else: violations.append(...)` three times, and either test 3.13 or change the PASS string. Gate 3 -> match `^[A-Za-z]:[\\/]`. Gate 2 -> glob `**/SKILL.md` and assert every hit is under `skills/`. Gate 4 -> prune the four stale entries. Three `glob` -> `rglob`.
- **Preserves** Gates 1, 6, 9 and 12, which are behavioural and well-documented.
- **Discriminator** Each repaired gate fails the adversarial tree that currently passes it.
- **Accept** `tests/test_harness_adversarial_gates.py` gains one constructed-input probe per repaired gate. Its `TestGateNumberingIntegrity` machinery is the right model. Also wire the four checks that ship but never run: `check_protected_paths` (all three paths missing), `validate_receipt_provenance`, `check_logarithm_last_rule`, `check_modality_isolation`.

### 05-80 Nothing enforces the todo-stack rule or resolves `AGENTS.md`'s own pointers
- **Problem** `AGENTS.md` section 2 states the stack holds only work not yet done; no gate or test checks it, which is why the stack accumulated a completed-work table, and no check resolves the file's own references, which is why section 4.3 points at a deleted item.
- **Evidence** `grep -rn "todo_stack" scripts/ tests/` returns one hit, a path string. The stale pointer is confirmed by `grep -in "non-blocking" artifacts/todo_stack.md` returning nothing.
- **Change** A test that resolves every path, test name and section reference in `AGENTS.md` and both stacks, and asserts the stack carries no "CLOSED"/"DONE" markers.
- **Preserves** Both stacks' formats.
- **Discriminator** Reintroducing a dangling pointer fails the suite.
- **Accept** The registry-staleness class that produced this item is mechanically prevented.

### 05-81 `scripts/harness_gate.py` and `scripts/mkdocs_version_hook.py` describe themselves wrongly
- **Problem** Module docstrings drifted from the code.
- **Evidence** `harness_gate.py`'s docstring lists gates 1-12; the runner prints 13. `mkdocs_version_hook.py:12` says "the package pins >=3.12,<3.13", while `pyproject.toml:17` is `>=3.12` and `harness_gate.py:493` fails the build on any `<` in that spec — so the comment cites the exact upper pin the harness exists to forbid. `connectivity.py:16` claims "Residual variance uses explicit N - p divisors" while `_residual_variance` ignores its `n_params` argument and returns RSS/N. `artifact_detection.py:93` documents returns as `(flag, corr_summary, amp_per_trial)` while the code returns z-scores (measured: `third[7] = 332.40` against a true `max|amp|` of 54.21). `tfr_accumulator.py:1` promises float64/complex128 accumulation; the persisted dtypes are float32/complex64.
- **Change** Correct each docstring; drop the dead `n_params`.
- **Preserves** Behaviour.
- **Discriminator** `test_docstring_matches_the_globs_it_claims`, which already exists for gate 6, is generalised.
- **Accept** No module docstring contradicts its code.

### 05-82 CI hygiene
- **Problem** Three small gaps on a publish-capable pipeline.
- **Evidence** No workflow-level `concurrency:` or `permissions:`, so rapid pushes run overlapping publish-capable pipelines. `pypa/gh-action-pypi-publish@release/v1` is a mutable branch ref on the two jobs holding `id-token: write`. `workflow_dispatch.inputs.target` defaults to `testpypi`, so any manual dispatch publishes unless the operator picks `none`. Confirmed clean: no `continue-on-error`, no `|| true`, no `set +e` anywhere; `if-no-files-found: error` is set; the production PyPI trigger is correctly narrow.
- **Change** Add `concurrency` and a `permissions: {contents: read}` floor; pin the publish action to a commit SHA with a version comment; flip the dispatch default to `none`.
- **Preserves** The publication ordering in `artifacts/fact_stack.md`.
- **Discriminator** A second push cancels the first; a manual dispatch publishes nothing by default.
- **Accept** `tests/test_workflow_release_policy.py` extended to cover the dispatch default.

## 13. Close-out

### 05-83 Independent adversarial pass over the repaired tree
- **Problem** The repairs above touch every subsystem and several change what other items calibrate.
- **Change** One independent pass attempting to falsify: numerical correctness, failure semantics, API consistency, docs, skills, packaging, CI and gate efficacy — reproducing each finding before repairing it, as the 0.2.4 pass did.
- **Preserves** Nothing by assumption.
- **Discriminator** Findings are reproduced before repair and pinned by a test that fails the previous code.
- **Accept** Every major finding either repaired with a failing-before test or recorded as triaged with its measurement.
- **Mandatory targets** These are not discretionary. Each is a known unknown carried into the pass, and each must be resolved or restated with a measurement rather than dropped:
  1. **Mutation restoration has stronger detection than its cause explains.** Write-restore harnesses have repeatedly shown detection that the stated mechanism does not account for. Unresolved since the 0.2.4 pass.
  2. **Python 3.14 Torch import is collection-order fragile.** An ad-hoc pytest subset can fail three `test_backend` tests and segfault. Reproduced at a sealed commit; pre-existing, not caused by any 0.2.5 repair.
  3. **Section 1-2 estimator mutation completeness is unknown.** 05-54's Accept read "no estimator in sections 1-2 survives its own mutation", which is broader than the nine candidates its evidence named. Those nine are closed at `da3fb343`. Whether every other estimator in those sections has a discriminating test has not been measured.
  4. **`_welch_csd_gpu`'s conjugation orientation is unverified.** The CPU path is derived from scipy's documented `conj(X) * Y` and tested at `tests/test_estimator_discrimination.py`. The CUDA path computes its own cross spectrum. A sign inversion there makes GPU and CPU disagree on `icoh_mean` while both look plausible, and no test reaches it: the fallback test establishes control flow only, and nothing in the suite executes on GPU.
  5. **`TFRAnalyzer.extract_band` is asserted by shape only.** Its three
     `TestTFRAnalyzerBandExtraction` tests and the five-band subtest check `result.shape`
     and `result.dtype`, never a value. Two mutations survive the whole file as a result:
     dropping the band's upper bound so every frequency above `f_min` is included, and
     replacing the frequency-axis `mean` with a `sum`. Both change every returned number
     while preserving shape. Measured at both the old 9.537 GiB fixture and the current
     one, so this is a pre-existing gap the fixture shrink neither caused nor closed.
  6. **Tracked files may still be rewritten through a text round-trip.**
     *Mechanism:* `read_text` normalizes every line ending to `\n` and `write_text` emits
     the running platform's `os.linesep`, so the pair reproduces a file's bytes only when
     its endings already match that platform, and rewrites them otherwise -- in either
     direction. `read_text` also conceals the difference from any check written the same
     way, so a test of this cannot use it.
     *Measured:* `jnwb/mcp_server/custom_tools.py` is CRLF (read as bytes), and on this
     Windows machine the round-trip reproduced its 101 bytes exactly. That instance was
     removed in 05-57.
     *Derived, not run:* `.github/workflows/workflow.yml:29` runs the matrix on
     `ubuntu-latest` as well, where the same code path converts that file to LF instead, so
     the restore preserved bytes on one half of the matrix and modified a tracked file on
     the other. Whether any other tracked file is rewritten this way, by a test or a
     script, has not been swept.
  7. **One 05-54 mutant is killed only incidentally.** Collapsing both shuffle p-values to `1/(n+1)` dies against `test_api_consistency.py::TestAlternativeAndAlpha::test_case_and_whitespace_are_folded_not_ignored`, a case-folding test, through its `assert plain[1] != two[1]` guard. The "nothing catches this" claim is false, so nothing was repaired; but a folding inequality is not evidence of p-value correctness, and that coverage disappears if the guard is relaxed.
  8. **Three `tests/test_rsa.py` tests are redundant only for the classes that were
     probed.** 05-59 refuted the proposed deletion of that file: it uniquely carries five
     failure classes, and the suite without it kills none of them -- `rdm` accepting a
     sub-2D input, and all four `rdm_similarity` rejection paths, including an unknown
     metric name silently computing Spearman. Of the remaining tests,
     `test_rdm_shapes_and_invariants`, `test_rdm_similarity_comparison` and
     `test_rdm_metrics` were redundant against every mutant aimed at them, but assertions
     in each (zero diagonal, condensed/square round-trip) were reached by no mutant, so
     their redundancy is measured only where it was measured. `test_rdm_metrics` also
     survives a mutation that makes `_condensed_distances` ignore its `metric` argument
     entirely -- the oracle catches it, so the suite is covered, but the test named for
     metrics does not detect that metrics are ignored.
  9. **`tests/test_docs_smoke.py` may be a second copy of the documentation.** Its ten
     tests hand-transcribe the documented workflows instead of reading the pages, so all
     ten passed while six documented calls raised `TypeError` -- the pattern 05-55
     removed from `tests/test_readme_smoke.py`. 05-61 added parse and execute checks that
     read the pages directly. Whether the transcribed file still carries failure classes
     those do not has not been measured, so it was neither deleted nor trusted.

### 05-85 Code / docs / skills / tests triangle audit
- **Problem** The four faces of a capability can disagree without any of them failing on its own. Nothing currently checks them against each other.
- **Runs** After 05-83 and before 05-84. Added to the frozen stack 2026-09-17 by the ruling recorded in `artifacts/direction.md`; numbered after the last frozen item because the frozen numbers are a record.
- **Scope** Semantic agreement, not duplicate presence. Public-symbol presence, API generation and export agreement, documentation coverage and onboarding alignment stay with the deterministic gates that already decide them (5, 9, 13 and the skill-vs-exports rule). 05-85 consumes those results and does not re-derive them.
- **Change** For each important capability, compare the faces that make a claim about each of: shape, units, axes, estimator, aggregation, failure behaviour, randomness, identity/provenance, and composition where the capability is reached through a skill that sequences it with others. Composition carries its own claims — order of operations, order of aggregation, whether identifiers survive, and which signal class is substituted for which — because a routing layer can get every individual operation right and still compose them into a wrong result without restating any mathematics.
- **Preserves** The rule that a skill may not hold a mutable API fact that documentation and exports also hold.
- **Discriminator** A seeded contradiction on a semantic dimension is found; a seeded presence-only defect is left to the gate that owns it.
- **Accept** For every capability `c` and dimension `d`, the faces that claim `d` carry at most one meaning between them. A demonstrated disagreement fails. A dimension the operation requires and no face specifies fails. A dimension the operation does not have is N/A, not missing. A skill silent on `d` passes when routing does not require it.

### 05-84 Release seal
- **Problem** 0.2.5 is not releasable until the above is closed.
- **Change** Bump version, release date and status; write the CHANGELOG; clean tree; push `dev`; remote CI green on the full matrix; merge per the ordering in `artifacts/fact_stack.md`; tag; release; verify from the published artifact rather than a local build.
- **Preserves** Release publication ordering: validate on `main`, tag, GitHub Release, production PyPI.
- **Discriminator** A fresh venv installs from PyPI and reproduces the version, status, release date and full symbol set.
- **Accept** Verified from PyPI, not from a local wheel or cache.

# Findings marked unsupported

## 05-70 counted 84 of 151 -- corrected 2026-09-18

The shape of the finding reproduced; the numbers did not. `jnwb.__all__` exports 155
symbols, not 151, and 81 were mentioned by no skill, not 84. Every symbol the item names
individually was genuinely unrouted, so the change stands as written.

The item's Accept asks for the unmentioned set to be reviewed and justified. It was, and
the review changed the standard: mention is not routing. A symbol named in a sentence is
not callable from that sentence, so the coverage test requires a routing row for every
public callable and accepts a bare mention only for constants and types. Under that
stricter reading the tree ends at 111 symbols carrying a row and 44 excluded by category;
a count of mentions would have reported 126 and 29 for the same tree.

The `jnwb-laminar` skill was not created; the item's second option was taken. The depth
estimators consume the PSDs and correlation matrices `jnwb-lfp-spectral` already produces,
a separate skill would have to restate that half to be usable, and the skill tree is
doctrine. The router gains the laminar trigger either way.
## 05-67 found three more rows than it listed -- extended 2026-09-18

All six rows reproduce as described. The strengthened check from 05-68 found three the
audit did not list, each of a kind the old check could not see: `granger` naming the
deprecated keyword-only `seed` instead of `rng`; `fit_exponential_onset` naming the
keyword-only aliases `t0_bounds`/`tau_bounds` in the positional slots of `t0_bounds_ms`
and `tau_bounds_ms`; and `aggregate_to_db` giving a default to a keyword-only argument
that deliberately has none while stating the wrong default for `aggregate_over`. One of
the three, `save_figure_suite`'s `formats`, sat inside a tuple default and so was in the
7 rows the old regex skipped entirely. Nine rows corrected, not six.

One detail of the audit's `paired_fire_prob_test` evidence is sharper than stated: the
row as written raises `TypeError` for the missing `n_shuffles`, so a reader copying it
verbatim gets an error. The silent sign flip is what happens next, when the reader adds
the missing argument and keeps the order.

## 05-65 claims about `coi_mask` and tutorial units -- partly refuted 2026-09-18

Two of the item's six claims do not hold as stated.

`docs/04` does not hand over `coi_mask` as a bare field name: the page carries a section
headed "What `coi_mask` excludes, and why the average comes after it", explaining the
`mode="same"` zero fill, the kernel-width exclusion and the bias from averaging before
masking. That was repaired earlier in 0.2.5. The CSD half of the same claim reproduces and
was fixed.

"`docs/tutorials/03, 04, 05, 06, 08` contain no unit token at all" is true of the five
`.md` files and false of the pages. Each includes its script with `--8<--`, and the
included scripts carry Hz, ms, um and seconds for 03, 04, 06 and 08. `05_statistics.py`
genuinely had none, and its quantities are the ones a unit changes; it was repaired.

The audit's implied mechanism for `docs/09` is also wrong. It reads as though the example
should pass `groups`; `nested_cv_linear_svm(X, labels, n_splits, rng)` has no such
parameter. The defect is real in the other direction -- the page promises protection the
function does not provide -- so the page now says where the protection actually is.

## 05-64 cut docs/01 sections 1-3 -- not followed 2026-09-18

The item prescribed cutting `docs/01` sections 1-3 and keeping only section 2C, on the
evidence that those sections "name an internal scaffolding marker and a test file". Both
leaks reproduce, and both are single clauses: `tests/test_jnwb_frozen_boundary.py` inside
the boundary invariant, and `PLACEHOLDER-DUMMY` inside the synthetic-data rule. The
sections around them are signal class independence, estimand disambiguation, the causal
verb hierarchy, the unit of inference, valid nulls and the observed/derived/inferred/
assumed/unknown vocabulary -- user-facing science, and the only statement of most of it.
Cutting them would delete every user-facing fact in three sections to remove two clauses,
against the item's own Preserves clause. The two clauses were removed instead.

The audit's other 05-64 claims reproduce with drift in the counts: 117 and 2,781 words
(2,764 claimed), 29 nav entries with 28 unique (28 and 27 claimed), 24,155 words over 28
pages (22,181 claimed). `docs/11` section 9.2 is not the only documentation of all seven
symbols it names -- `aperiodic_fit` is also in `docs/04`, and `zflip`, `probe_geometry`
and `stream_npz_array` in `docs/02` -- but it is the only statement of their result
fields and failure semantics, which is what the repair preserved.

## 05-59 whole-file deletion of `tests/test_rsa.py` -- refuted 2026-09-18

The item asked for the file to be deleted, on the evidence that every failure class it
carries is covered by `test_rsa_oracle.py` and that it caught nothing under a `pdist**2`
mutation. The `pdist**2` observation reproduces. The conclusion does not.

Deletion was decided per failure class rather than per file: fifteen mutations of
`jnwb/rsa.py` and `jnwb/jrsa.py` were run against `tests/test_rsa.py` and the oracle
separately, and anything only the former caught was rerun against the whole suite with
that file ignored. Five classes are uniquely carried by it, and the suite without it
kills none of them:

| Mutation | Only carrier | Caught elsewhere |
|---|---|---|
| `rdm` accepts input with fewer than 2 dimensions | `test_rdm_input_validation` | nothing |
| `rdm_similarity` accepts mismatched lengths | `test_rdm_similarity_validation` | nothing |
| `rdm_similarity` accepts a non-square 2D RDM | `test_rdm_similarity_validation` | nothing |
| `rdm_similarity` accepts non-finite RDMs | `test_rdm_similarity_validation` | nothing |
| an unknown metric silently computes Spearman | `test_rdm_similarity_validation` | nothing |

Four of those sit in `test_rdm_similarity_validation`, which the item's evidence never
mentions and which the first nine mutants never reached. Absence of kills against
mutations aimed at other failure classes is not evidence of redundancy, and treating it
as such would have deleted the only guard on every `rdm_similarity` rejection path.

The stated justification fails independently. J1, reintroducing the 05-06 defect where
the parametric p pre-empts the permutation null, is not caught by the oracle either, so
"every failure class is covered by `test_rsa_oracle.py`" is false as written. It is
caught elsewhere -- by `test_jrsa_correctness.py::TestPermutationPWins`, which asserts
that invariant by name rather than incidentally -- but `test_jrsa_delegation_parity`
also carries statistic-delegation parity and the `permutations=0` fallback, neither of
which any mutant reached.

Both merges in the item's Change are refused on inspection rather than measurement. The
nine `TestPublicImport` classes are not duplicates of each other; each hardcodes its own
module's export names, and parametrizing them over `EXPORT_MODULES` would check that
registry against itself -- the circularity 05-55 removed from `test_rsa_oracle.py`.
`TestHarnessResetContracts` is not nine substring assertions of one thing but six
distinct doctrine contracts across different files; merging them trades six named
failures for one anonymous failure on the gates that guard doctrine.

Claim 6 reproduces in magnitude and not in attribution, and the edit it prompted was
reverted: `parallel_map` dispatches `min(len(items), workers * chunks_per_worker)`
chunks (`_parallel.py:103`), 2 for 2 items whatever `n_jobs` says, so `n_jobs=32` never
started 32 interpreters. Measured back to back under the same load, 32 against 4 is
7.47 s against 6.66 s.
## 05-55 claims 4, 5 and 9 -- graded 2026-09-17

Seven of the item's nine claims reproduced and were repaired at this commit. Three did
not hold as written, and the corrections are recorded here because they outlive the item.

**Claim 4 is stale.** `test_gpu_pca_cpu_and_cuda_agree_within_float32` no longer exists.
05-43 renamed and repaired it at `c72d9c2a` to
`test_gpu_pca_cpu_and_cuda_return_the_same_numbers`, which compares `proj`, `comp` and
`var` rather than the sign-invariant variance ratio. No change was made for this claim.

**Claim 9 does not reproduce, and the change it proposed is harmful.** The item asks for
`pytest.importorskip("statsmodels")` in the two `test_release_recovery_gates` tests that
patch it. `statsmodels>=0.13.0` is a required install dependency at `pyproject.toml:50`,
not an optional extra, so a `ModuleNotFoundError` there is a broken installation and
should fail loudly. `importorskip` would convert that into a silent skip. No test in the
suite guards `statsmodels`, and the convention is right. No change was made.

**Claim 5 reproduces as a mechanism but not as a loss of coverage.** `rdm_similarity`
(`jnwb/rsa.py:197`) is a dispatcher whose `pearson` arm is `stats.pearsonr(v1, v2)`, and
the test compared it against `pearsonr(a, b)` -- the same function on the same inputs, so
the assertion was an identity. That much is confirmed by reading the dispatcher. The
implied consequence is not: under a mutant replacing the `pearson` arm with an uncentred
cosine, *both* the replacement definitional oracle and a replica of the old circular
assertion failed. A wrong implementation diverges from the SciPy value it is compared
against, so the old test did catch implementation defects. The repair was still made --
it removes the test's dependence on SciPy's correctness and on the implementation
continuing to delegate -- but it closed no measured gap, and the item's framing overstated
what the circularity cost.

## 05-52 Five modules carry unrelated responsibilities -- deleted 2026-09-17

Evidence regenerated against `5f229231`. The item's numbers predate 05-26, 05-49, 05-50
and 05-51, all of which edited these files. Structure measured as the intra-module
dependency graph over top-level symbols: a component is a disjoint cluster, and a
component is interleaved when another cluster's symbols fall inside its line span.

| module | claimed | actual lines | components | splits at a line? |
|---|---|---|---|---|
| `laminar` | 1831, three estimators, split at 862 and 1476 | 1882 | 2 | 862 yes; 1476 now lands inside a comment mid-function |
| `connectivity` | 2144, IT at 56-164 and 1728-2010, VAR at 167-1720 | 2304 | 2 plus 1 isolated | no -- 14 symbols interleave one span, 3 the other |
| `spectral` | 1913, 208 lines of re-referencing and CSD | 2124 | 7 | CSD yes (2028-2123, 94 lines); re-referencing no (3 symbols scattered over 201-1829, 112 lines) |
| `jrsa` | 1740, device subsystem duplicating `_backend.py` | 1778 | 2 | already closed by 05-26: `jrsa.py:22` imports `CPU, CUDA, resolve_device` from `._backend` |
| `statistics` | 1633, five pure forwarders | 1764 | 8 | forwarder direction resolved in 05-51 |
| `analyzers` | 779, three namespaces with no shared state | 805 | 3, zero edges | yes |

Three reasons the change is not made.

`laminar` does not hold three independent estimators. `xflip` and `zflip` share
`_surrogate_phase_randomize`, the only edge joining them. A three-way split either
duplicates that helper, reintroducing what 05-51 removed, or adds a fourth module the
item does not name.

Four of six modules interleave, so "split along the named line boundaries" is not
available. The change is a reorder plus a split, a diff in which every line moves and a
semantic change is invisible to review -- during a pass whose purpose is to stop the
object moving.

The split buys nothing measurable. `Preserves: every import path and __all__` means
re-export, and `jnwb/__init__.py` imports `laminar`, `spectral` and `connectivity`
eagerly at lines 76, 132 and 156. Per-module self import time is 1.5-5.9 ms of 2347.8 ms
total (`artifacts/benchmarks/import_breakdown.json`, 0.2.4); the remainder is scipy and
sklearn, charged to whichever module imports them first and needed by both halves either
way. API, import cost and symbol set are identical before and after, while
`_api_surface.py` gains entries -- surface added, none removed.

`analyzers.py` reproduces exactly: three classes, three components, no edges between
them. It is left alone for the third reason, which applies to it as much as to the rest.

# Before 1.0

- Replace example-based estimator coverage with analytic or property-based tests.
- Processing-module discovery generalization beyond LFP if a corpus requires it.

# Unversioned

- File omission-side expert-feedback items in the omission repository.

# Environment note, not repository work

The development virtualenv at `.venv` has `omission` editable-installed
(`__editable__.omission-0.1.0.pth`) and jnwb not installed (`pip show jnwb` -> not found), and
is missing `statsmodels`, a declared hard dependency, plus `mkdocs` and `nbclient`. Every local
receipt is therefore taken in an environment the boundary gates would reject, and 7 of the
1472 local test failures trace to it while CI is green. This is machine configuration, not a
repository change.
