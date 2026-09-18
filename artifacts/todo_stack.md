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

## 11. Packaging

## 12. Harness and gates

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

## 05-82 everything reproduced, one change made narrower than asked -- recorded 2026-09-18

All three gaps were present exactly as described, including the item's four confirmations:
no `continue-on-error`, no `|| true`, no `set +e`, `if-no-files-found: error` set, and the
production PyPI trigger correctly narrow.

One change is narrower than the item's wording. The Discriminator reads "a second push
cancels the first", and `cancel-in-progress` is deliberately not unconditional: it is false
for `refs/tags/*` and for `release` events. Those are the refs that actually upload, and a
run cancelled between `build` and `publish-pypi` would leave a GitHub Release published
with nothing on PyPI -- the ordering `artifacts/fact_stack.md` fixes, broken by the thing
meant to protect it. For every other ref, which is every push to `main` and `dev` and every
pull request, the second push cancels the first as the item asks.

The pin resolves a moving target, so it is recorded here: on 2026-09-18,
`pypa/gh-action-pypi-publish` `release/v1`, tag `v1.14.2` and commit
`dc37677b2e1c63e2034f94d8a5b11f265b73ba33` were the same object, resolved through the
GitHub API rather than read from a badge. The pin is that commit; the branch will move and
the pin will not, which is the point.

## 05-81 the tfr_accumulator claim does not reproduce as stated -- recorded 2026-09-18

Four of the five docstrings reproduced exactly as described and are corrected. The fifth
does not. The item reads "`tfr_accumulator.py:1` promises float64/complex128 accumulation;
the persisted dtypes are float32/complex64". Both halves are true and they are not in
conflict: the module docstring and the class docstring describe *accumulation*, and
accumulation is float64/complex128 -- `__init__` allocates `np.float64` for `mean` and `M2`
and `np.complex128` for `sum_z` and `sum_unit_z`. The downcast happens in `write`, which
the docstring never described in either direction.

So there was no false claim to correct, but there was a real omission of the same kind:
nothing said that a summary round-tripped through HDF5 carries single-precision sufficient
statistics, which is what the module's central property -- `merge(A, B) == summarize(A u B)`
to floating-point tolerance -- holds to after a reload. That is now stated, with the reason
the downcast is deliberate.

The Accept condition, "no module docstring contradicts its code", is not achievable as a
single mechanical check and is not claimed. What is mechanized is each of the five claims
against the thing it is a claim about, plus one general sweep -- `Returns (...)` arity
across every module in `jnwb/`, eight functions today. Prose about what a function means
cannot be checked; counts, names, dtypes and numbers can, and those are what these are.

## 05-80 the evidence is superseded, and half the change would be wrong -- recorded 2026-09-18

The item's two evidence lines no longer hold. `grep -rn "todo_stack" scripts/ tests/`
returns four test modules, not one path string. `AGENTS.md` has no section 4.3 -- it runs
`## 0.` to `## 10.` with a single subsection, under 8 -- and the dead pointer the item
names is already asserted absent by
`test_agents_md_does_not_point_at_a_todo_item_that_is_not_there`, which also resolves any
other item `AGENTS.md` names against the live stack.
`test_every_repository_path_agents_md_cites_exists` already resolves every
directory-prefixed path the document cites, with a floor on how much it matched.

What did reproduce is narrower and is repaired: nothing resolved the document's own `§N`
cross-references, nothing resolved a file named without a directory (the sweep's regex
requires one of seven directory names in front, so `pyproject.toml` and `CHANGELOG.md`
were invisible to it), nothing resolved anything in `artifacts/fact_stack.md`, and
nothing held the todo stack to the section 2 rule.

Not done, and deliberately: the item asks that every path in both stacks resolve. For the
todo stack that check would be wrong. The stack is a record of findings as well as a plan,
and a record correctly names what the finding caused to be deleted -- measured, eight of
its cited paths and one test name are of exactly that kind, including
`docs/requirements.txt`, which the note one item above names because 05-78 removed it, and
`test_gpu_pca_cpu_and_cuda_agree_within_float32`, which the stack itself describes as no
longer existing. A resolving sweep over that file would force the evidence to be deleted
to stay green. The fact stack carries no such record and is swept in full.

## 05-79 four sub-claims did not reproduce -- recorded 2026-09-18

Nine gates were repaired and the item's central claim held everywhere it was tested:
each adversarial tree was built and watched to pass before anything changed. Four
sub-claims did not survive being checked.

Gate 4's allowlist was said to carry four entries that do not exist. Three do not
(`_audit_dist`, `_audit_dist2`, `_audit_dist_build`) and are pruned. The fourth absence
is deliberate and says so where it lives, and the new test requires exactly that: an
allowlisted file that is absent must carry its reason in the source or be pruned.

Gate 5 was to be retired as subsumed by gate 9, on the grounds that it takes credit from
the generated `docs/api.md` and matches substrings. Both were already repaired by 05-41:
the gate skips `GENERATED_REFERENCE` and matches with `\b...\b`, and its docstring
records the twelve symbols that repair surfaced. Only the non-recursive glob remained, so
the gate was widened rather than retired -- retiring a check whose two stated defects are
already gone would remove live coverage.

Gate 8's PASS line was said to print "all agree" over a classifier set including 3.13
while `PYTHON_CI_REQUIRED` omits it. The line names the two sets separately --
`classifiers ['3.12', '3.13', '3.14'], CI covering ['3.12', '3.14'] all agree` -- so it
asserts agreement between what is declared and what is tested, not that 3.13 is tested.
It is unchanged. Whether CI should test 3.13 is a matrix decision, not a defect here.

Of the four checks said to ship but never run, three do run:
`validate_receipt_provenance`, `check_logarithm_last_rule` and `check_modality_isolation`
are each imported and exercised by `tests/test_harness_adversarial_gates.py`. Only
`check_protected_paths` was dead, and its `PROTECTED_PATHS` named another repository's
`omission/...` directories, so it is removed rather than wired: wiring it would have
meant inventing paths for it to protect.

One process note. The discriminator harness left the D13 mutant (`rglob` -> `glob`) live
in `tests/test_docs_links.py` despite asserting a digest match after the restore, and the
full suite caught it. A pre/post digest comparison across the whole run, outside the
per-case try/finally, is now what the run is trusted on; the second run came back
byte-identical on all three mutated files.

## 05-78 one half superseded by work done since the audit -- recorded 2026-09-18

The item says neither `pytest-cov` nor `pytest-xdist` has a caller: no `addopts`, no
`--cov`, no `-n` anywhere. That was true at the audit and is now half true.
`pytest-xdist` acquired a caller in this execution -- the installed-wheel leg added for
05-76 runs `pytest ... -n auto` -- so it is declared and used, and stays. `pytest-cov`
still had none and is removed rather than given an `addopts`: adding coverage to every
run is a new gate with a threshold to argue about, and the item's own alternative was
to drop it.

Everything else reproduced. `docs/requirements.txt` and the `[docs]` extra were
byte-identical, `.readthedocs.yaml` installed both, and `fail_on_warning: true` makes a
drift a failed publish; the file and its entry are gone. The two scripts measured 464
and 161 lines, 625 together as stated, with no reference anywhere outside themselves,
and the root allowlist still carried `jnwb-unified-rev.md`.

The Accept records that all six extras resolve and notes that `jnwb[gpu]` installs
cleanly with no CUDA because plain `jax`/`jaxlib` from PyPI is CPU-only, and that it
should be `jax[cuda12]`. Not acted on: `jax[cuda12]` publishes no Windows wheel, so it
would turn a working install into a failing one on this platform. That is a packaging
decision with a user-visible consequence, not a defect to repair in passing, and it is
left for the release seal to rule on.
## 05-77 every figure in the item reproduced -- recorded 2026-09-18

Checked rather than accepted. Installing the built 0.2.4 sdist into a clean 3.12
environment yields `jnwb/` and `jnwb-0.2.4.dist-info/` and nothing else: no `SKILL.md`
and no `AGENTS.md` anywhere in the environment. The sdist itself carries all nine
skills and `AGENTS.md` at its root. Of the skills' 12 repository-relative links, 11
point into `docs/`, which the sdist prunes, so they resolve only in a checkout --
exactly the count the item gives. `grep -rn "skills" jnwb/ --include=*.py` returns
nothing.

Executed as ruled: one canonical tree, `skills/` still grafted into the sdist, no copy
under `jnwb/`, the `MANIFEST.in` comment rewritten to describe its mechanism, and
`jnwb.SKILLS_URL` added as the machine-readable pointer. The pointer names the tag for
the installed version rather than a branch, so an agent that has only the package finds
the routing rows written against the API it is holding; both forms were checked live
and return 200.

Not done, and deliberately outside the ruling: the 11 dangling links were left as
relative paths. Rewriting them to the published documentation site would make them
resolve inside the tarball, but it would also change seven skill files, which are
doctrine-adjacent, for a gap the ruling chose to close with a pointer instead. Flagged
here rather than actioned.
## 05-76 reproduced, and the claim was worse than stated -- recorded 2026-09-18

The mechanism reproduced exactly. With the wheel installed into a clean 3.12
environment, `pytest tests/` run from the repository root imports
`C:/workspace/jnwb/jnwb`, not the installed copy; `test_import_provenance.py` says so
when `JNWB_EXPECTED_PACKAGE_ROOT` names the environment.

Two corrections to the item. `pythonpath = ["."]` is not the only mechanism:
`tests/__init__.py` makes `tests` a package, so pytest's prepend import mode inserts the
repository root as well. Clearing `pythonpath` alone changes nothing; the leg also needs
`--import-mode=importlib`. And the item says only the build job touches the wheel -- the
tutorial step had stopped touching it too, because the checkout guard added with the
import-provenance repair finds the sibling package under `$GITHUB_WORKSPACE` and
prepends the source tree. That step's name has been false since that commit.

Running the suite against an installed copy was not merely absent; it was impossible.
Sixteen tests failed for three reasons, each a defect in its own right: five test
modules prepended the repository root to `sys.path` and re-shadowed the package under
test, two opened `skills/...` relative to the working directory, and one located
`CHANGELOG.md` through `jnwb.__file__`. All three are repaired, and the scanners that
keep them out are in `tests/test_the_suite_can_qualify_an_installed_copy.py`.

The Discriminator asks that a defect present only in the packaged artifact fail CI. It
now can: the leg runs the whole suite against the wheel. Against the built 0.2.4 wheel
the result is 2499 passed, 48 skipped -- 46 more skips than the checkout run, all of
them GPU-gated tests, because the clean environment has no CuPy. That is the same
condition a CI runner is in, so the leg is no weaker there than the matrix legs are.
## 05-75 reproduced exactly; the repair is wider than the item -- recorded 2026-09-18

The mechanism reproduced as stated. A wheel-shaped zip carrying `tests/__init__.py`,
`tests/test_secret.py` and `scripts/release_gate.py` was accepted by the old loop; the
sdist-shaped tarball with the same content was rejected on `/tests/`.

The item proposes component matching for the wheel and keeping the substring form for
the sdist. That was not done: one rule, applied to both, is the smaller thing to get
right, and the sdist layout passes it. Three things the item does not name were repaired
in the same commit because leaving them would have left the check unsound:

- The gate never rejected `site/` or `_build/`, which `MANIFEST.in` prunes. The two
  lists had drifted, which is the same defect class as the one being repaired, so the
  prune targets are now derived from `MANIFEST.in` in the suite.
- `.lab` matched the directory that exists, `.lab_bundle_build`, only as a substring.
  Switching to component matching would have silently dropped it; both names are listed.
- CI carried a byte-identical copy of the same defective list. Repairing only the local
  gate would have left the published pipeline shipping the same wheel. The workflow step
  now calls the gate's matcher, and the suite runs that step's Python out of the YAML.

Component matching narrows one case deliberately: `artifacts` used to reject a module
named `lfp_artifacts.py`. That is a false positive, not protection, and it is now
accepted. `omission` and `_unused` stay substring rules -- they are markers, not
directories.

The Accept asks for a wheel containing a top-level `tests` package to fail. It does,
constructed in the scratch directory and again from within the suite. The real built
wheel (54 entries) and sdist (103 entries) are clean under the repaired rule, so the
change adds no false positive to the artifacts this package actually produces.
## 05-74 nine floors, not seven -- corrected 2026-09-18

The finding reproduced and grew. The item names seven defective floors; nine are.
`torch>=1.12.0` and `pyyaml>=6.0` have exactly the defect the item describes and were
not listed: neither release ships a cp312 or pure-python wheel (torch 1.12.0 stops at
cp310, pyyaml 6.0 at cp311). Both moved in the same commit, because raising seven of
nine would have left the gate red on the two that remained.

The item's title also reads "of ten"; `pyproject.toml` declares 23 `>=` floors across
the core list and the `torch`, `test` and `docs` extras. The other fourteen are clean:
each resolves to a release with a usable wheel. The gate checks all 23, not the ten.

Of the nine, one is the requires_python contradiction the item names (`scipy==1.8.0`
declares `'>=3.8,<3.11'`); the other eight ship no usable wheel. The scipy floor had a
second, independent reason to move that the item records: `false_discovery_control`
arrived in 1.11. `tests/` derives that requirement from the call sites rather than
asserting 1.11 as a constant, so it disappears if the calls do.

The Accept asks for `pip install 'numpy==<floor>'` to succeed on 3.12 for each
dependency. It was met by reading the index metadata for each floor rather than by
running 23 installs: the question is whether an installable artifact exists for cp312,
which the wheel tags and `requires_python` answer directly. Installing them would also
have required a throwaway environment per dependency and would have tested this
machine's resolver as much as the declaration.
## 05-73 divergence measured larger, commit count unverifiable here -- recorded 2026-09-18

The finding reproduced and grew. `jnwb.__version__` is 0.2.4, the index serves 0.2.4, and
`## [Unreleased]` holds 1009 non-empty lines, not the 20 the audit measured.

One figure could not be checked from this clone: "HEAD is 5 commits past `v0.2.4`". The
tag objects are missing locally, so `git describe` and `git rev-list v0.2.4..HEAD` both
abort. That is a defect of this checkout, not of the repository, and it does not affect
the finding -- the version collision is established from the index and the changelog
without needing a commit count.

The check lives in `scripts/release_gate.py`, not `scripts/harness_gate.py`: it needs the
network, and a per-commit gate that reaches the internet fails for reasons that have
nothing to do with the tree. The suite drives every branch through the pure function and
stubs the transport, so it gives the same answer offline.
## 05-72 third count already gone, and the ruling is removal -- recorded 2026-09-18

Two of the three counts reproduced: `docs/agents.md` says three tools at lines 12 and 24,
`mcp.list_tools()` returned four, and `jnwb.mcp_server.__all__` had five entries. The
third pointer, `docs/10:18`, no longer exists -- 05-64 deleted that page and replaced it
with `docs/10_operation_specifications.md`, which says nothing about the MCP server.

The item left the keep-or-drop decision to the implementation. It was dropped, on three
grounds, each checked rather than assumed: nothing imports `custom_tools`, so the
registration never took effect and the restart message was false; validation was
`ast.parse` plus the presence of a function definition, with the write target inside the
install; and no surface documented it. The removal went past the item's "drop it from
`__init__.py`" to deleting `meta_tools.py` and `custom_tools.py`, because an unreferenced
module whose whole content is a code-writing primitive is the same defect one import away.
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
