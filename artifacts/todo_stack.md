# 0.2.6

Authorized 2026-09-19 as a fresh cycle. The 0.2.5 stack is not extended: its record is
`artifacts/todo_stack_0.2.5.md`, immutable, and nothing here is appended to it.

Items are deleted when done; finished work is not recorded here. The closure records in the
0.2.5 file say what each of that cycle's items measured.

0.2.5 raised per-surface correctness. The next failure class is system-level: jnwb can hold
correct code, tests, documentation and skills while its public identity, examples, diagrams,
packaging and presentation-facing claims disagree with each other or cannot be reached.
0.2.6 is a coherence, reachability and evidence release. It adds no scientific capability.

## Execution protocol

Imported evidence: the 2026-09-19 alignment review (31 findings confirmed under two-lens
adversarial verification, 12 upheld with one lens dissenting, 4 refuted, 36 low-severity and
unverified), `artifacts/planned_post_0.2.5.md`, the two residual limits recorded by 05-85, and
the carried `granger_causality(order=...)` candidate.

**Every imported finding enters as a hypothesis to reproduce, never as a defect to implement.**
A finding that does not reproduce is marked unsupported with its evidence and its item deleted.
Correct code is not modified to match a wrong audit. The review's own adversarial pass refuted
four findings that read as solid, so its confirmations get the same treatment.

Within a batch: reproduce, repair, add the discriminator, mutation-kill where practical,
continue. One batch-level regression and gate run, then commit and push, then the next batch.
Qualification runs in a clean environment built from the declared extras, or in CI. The
development `.venv` is not package evidence.

Batch 0 completes before any substantive edit elsewhere.

## Batch 0. Goal and authority

The goal statement is the artifact 0.2.6 is scored against, and two of its three pillars name
capabilities that do not exist and that this cycle decides not to build. Repairing the
repository against an unrevised goal cannot produce a valid result.

The direction of repair is fixed: **package evidence plus human ruling produces the corrected
goal.** A desired presentation never produces a new package identity. This constrains the
"dynamic" wording, the AI-native positioning and the topology figure in particular.

### 06-01 Rule the corrected goal statement

One page, human-ruled, derived from `artifacts/direction.md` and live package evidence.

- Entry topology: researcher and AI agent are parallel entry paths into one set of operations.
  AI is never a mandatory intermediate layer.
- Authority: code, documentation and tests constrain each other; skills route over that tested
  surface and hold no mutable API fact of their own.
- Authorization is not a jnwb capability. The real boundary is that an agent may execute
  operations and may not decide scientific assumptions.
- "Does not generate data" means no substitution of synthetic values for missing empirical
  observations in an analysis path. `jnwb.testing` is explicit test and calibration
  infrastructure and is not an analysis surface.
- "Dynamic" means adaptation to unfamiliar NWB structure, not raw-data-to-NWB conversion.

### 06-02 Reconcile the agent-vocabulary rule before writing any public architecture page

`AGENTS.md` restricts harness vocabulary to four places and excludes `docs/`; `docs/` already
carries it in four files, and no gate enforces the rule either way. A known contradiction
between a rule and its own subject is a stop condition. Rule it, then proceed. The architecture
page is blocked on this item.

### 06-03 Disposition every imported finding

A ledger over all 31 confirmed and 12 single-lens findings, each resolved to reproduced,
refuted, stale, already repaired, or deferred. **No finding may disappear for falling outside a
batch.** Every deferred entry records why it is out of scope for 0.2.6 and where it stays
discoverable. The 36 unverified low-severity findings are listed by identifier so the set is
recoverable, and are not individually dispositioned unless a batch reaches one.

### 06-04 Reconstruct the live basis

Branch, HEAD, tree state, package metadata, declared Python support, CI matrix, exports,
skills, published documentation, packaging and gates, each re-resolved rather than recalled.

### 06-05 Freeze the acceptance set and the non-goals

Before any substantive edit. The non-goals of this cycle are listed at the end of this file and
are part of the frozen record.

## Batch 1. Public truth and reachability

### 06-06 Publish the canonical architecture page

Extract the durable content of `artifacts/direction.md` into a maintained page under `docs/`:
identity, the two entry paths, the code/documentation/tests relation with skills acting on it,
the four routing cases, the boundary test. No ruling or process language in the public version.
The artifact remains the historical authority. Blocked on 06-02.

### 06-07 Gate architecture reachability

The page is reachable from the navigation; the agent documentation links it; no maintained
public asset draws the researcher-through-AI chain; the public identity never requires an agent
to be present; skills are not described as an implementation authority. Behaviour-shaped
assertions, not whole-prose snapshots.

### 06-08 Make diagrams render

`mkdocs.yml` declares `pymdownx.superfences` with no `custom_fences`, so the five mermaid
fences in `docs/` publish as source text. Configure rendering, build strict, and assert the
built output carries a mermaid container rather than a literal code block. Six of the planned
documentation assets are diagrams and are blocked on this.

### 06-09 Correct the `SKILLS_URL` entry on the public API page

`docs/api.md` types it as a function and shows the `str` constructor docstring. Repair the
generator's scalar-constant path, regenerate rather than hand-patch, and discriminate with a
second exported constant.

### 06-10 One truth for Python support

Reconcile `requires-python`, the classifiers, the CI matrix, `README.md`, `docs/install.md` and
the published release body. Two live defects to reproduce: the release notes' inherited
"3.10 through 3.14", and a 3.13 classifier the matrix never exercises. Determine the declared
policy first; absence from CI is not evidence of non-support. Then either test 3.13 or withdraw
the claim.

### 06-11 Gate the release body

The release body is the one version-bearing surface nothing reads, and a correct changelog does
not make it correct. Derive or check its mechanically knowable claims -- version, Python
support, install command, release status -- against package metadata rather than maintaining
another prose replica.

### 06-12 Repair the `relative_power` routing row

The row tells an agent the estimand is named in the result; the function returns a bare array.
Repair the skill claim, not the API: a richer return needs independent justification. Then test
the class, since the signature harness cannot see a claim about return contents.

## Batch 2. Scientific defects

### 06-13 `compress_fp32` dataset specificity

A public export recognises one corpus's layout by name. Apply the boundary test: generic,
dataset-independent, scientifically stable, explicitly parameterized, independently testable.
If reproduced, separate generic mechanics from dataset-specific selection, make selection an
explicit caller input, and add adversarial names that must not be matched silently.

### 06-14 `granger_causality(order=...)` validation

Re-authorize and reproduce rather than importing the carried candidate. If valid: establish the
allowed domain, reject invalid orders explicitly, cover it at primitive and property level, check
documentation and skill exposure, and mutation-kill the gap.

### 06-15 The `jrsa` correction fallback

With `statsmodels` unimportable, every method except `bonferroni` returns Benjamini-Hochberg
q-values while the recorded correction still echoes the request. Reachable only in an install
that violates a declared hard dependency, so this is a principle repair: raise, as the
unrecognised-method path directly above it already does. An estimator failure is not converted
into a plausible labelled result.

### 06-16 Sweep the same substitution class

The two repairs above share one shape: a fallback that produces a differently-computed but
plausible result under the original label. Sweep for it across the package rather than fixing
two instances.

### 06-17 Confirmed numerical and API findings not covered above

Taken from the 06-03 ledger, reproduced individually, highest consequence first.

## Batch 3. Coherence of code, documentation, tests and skills

05-85 recorded two limits: composition's aggregation order and identifier survival were not
swept, and no capability-by-capability matrix was built. A matrix over every public symbol and
every dimension is its own release and is not attempted here. This batch closes the named
limits over a declared subset and records the subset's boundary as part of the result.

### 06-18 Declare the high-risk subset

Name the producer-consumer chains before writing any test. Within the declared subset, unknown
is not a pass. The boundary of the subset is part of the acceptance record, not an omission from
it.

### 06-19 Aggregation order

Channel aggregation against ratio; averaging against log and dB; trial and session aggregation;
band integration; baseline normalisation; group weighting; non-finite filtering relative to
aggregation. Asymmetric inputs where order changes the answer.

### 06-20 Identifier survival

Channel, unit, probe, area, trial and session identity through selection, transform, filtering,
permutation and aggregation. Positional reassignment must not become semantic identity.

### 06-21 Axis composition

Extend 05-85's per-function axis work to chains, especially channel-major to time-major
boundaries. Deliberately unequal dimensions so a transpose cannot pass by coincidence.

### 06-22 Failure propagation

A missing, ambiguous or non-identifiable intermediate produces an explicit downstream failure,
never a zero, a non-finite value read as a result, or an empty valid-looking output.

### 06-23 Randomness propagation

The caller's generator reaches every stochastic child; no child reseeds; one seed reproduces a
whole workflow; observed and null estimators stay identical where the comparison requires it.

### 06-24 Skill routing against live behaviour

Every routing row in every skill: the callable exists, the signature matches, the return type
and keys match, units match, failure behaviour matches. Conditional return schemas are included
-- a skill must not name a key that exists only under an unstated branch.

### 06-25 Decline behaviour as executable evidence

Representative cases per applicable skill for all four outcomes: supported routes, missing input
is requested, a non-identifiable result is reported as a failure, an unsupported claim is
declined. No language model is required to test this layer.

### 06-26 Worked examples stop teaching synthesis

Classify every example input as real NWB, deterministic minimal array, stochastic synthetic, or
explicit calibration fixture, and default normal routing examples to the first two. The
objective is not removing generators from documentation; it is that a normal analysis
instruction never implies inventing data. Execute the example blocks, which nothing does today.

### 06-27 Semantic mutation classes over the declared subset

Unit scaling, axis swap, sign flip, conjugation, density against spectrum, mean against median
and sum, log before aggregate, permutation p-value substitution, generator ignored, support gate
removed, failure converted to a default, identity restoration removed, result key deleted,
signature drift. A class list, not a mutation score.

### 06-28 Mutation harness validity as a precondition

Per case: the pristine selector collects; the pristine selector passes; the mutation lands
exactly once; the source differs; the expected test is collected under mutation; the mutant
fails on the semantic property; the restore is byte-exact; the whole-run digest is clean. This
is the 05-85 false-kill lesson enforced before a verdict rather than discovered after one.

## Batch 4. Maintained evidence and demonstrations

### 06-29 Make generated figures maintained

Nothing runs `docs/generate_figures.py`, and re-running it reproduces none of its outputs
byte-identically. Map every artifact to its generator, regenerate in isolation, and gate on
unexplained drift with a tolerance the plotting stack can actually meet.

### 06-30 Produce the canonical diagrams

Dual entry; code, documentation and tests with skill routing over them; the four-outcome
decision; NWB to analysis; the package boundary. One maintained source each, original to jnwb.
Blocked on 06-08.

### 06-31 One real NWB end-to-end example

Select a small, redistributable or remotely accessible public dataset by capability fit, not by
name. Open, inspect, select, analyse, verify, visualise, reusing the operations the skills
route, with provenance sufficient to reproduce the result.

### 06-32 Separate empirical from synthetic

Visibly and structurally, in the documentation tree and in the figures.

### 06-33 Retain the benchmark design as explicitly unrun

`artifacts/planned_post_0.2.5.md` already rules the hypothesis and its pre-registration
constraints. Bring it to pre-registration quality and mark it unrun. It is not an acceptance
criterion for this release: an empirical comparison whose either outcome is scientifically
admissible cannot gate a release without giving the experiment a result to reach. The prior-art
positioning is already ruled in `artifacts/direction.md` and is enforced, not redesigned.

## Batch 5. Independent closure and release

### 06-34 Adversarial mutation pass

Seed known semantic defects and require the intended gate to catch each one. Every selector
collects and passes pristine before any verdict counts.

### 06-35 Clean-environment matrix

Across the declared Python and operating-system support, resolving the 3.13 question from 06-10.

### 06-36 Documentation qualification

Strict build; diagrams render as diagrams; generated assets current; links resolve; no stale
version claim; the canonical architecture page reachable from the navigation.

### 06-37 Distribution qualification

Source distribution and wheel: contents, metadata, imports, exports, `SKILLS_URL`,
representative workflows, documentation-facing constants, no checkout shadowing.

### 06-38 Fresh-install workflow

From the published candidate rather than the checkout: install, open an NWB file, analyse,
verify.

### 06-39 Independent critic

A reviewer who implemented none of the repairs, over the acceptance set, the unresolved
unknowns, the mutation evidence, the public claims and the release artifacts.

### 06-40 Release

dev green, pull request and main green, tag validates without publishing, GitHub Release,
production index, then verification from the index in a clean environment.

## Out of 0.2.6 scope

Frozen as part of the acceptance set. Each needs its own authorization.

- Raw-data-to-NWB conversion. Documentation may route a reader toward external conversion
  systems; implementing conversion is feature expansion.
- An authorization or permission subsystem.
- Benchmark execution. The design is retained and marked unrun.
- A capability-by-capability matrix over the whole public surface.
- Repository minimization: dead tests, hand-transcribed examples, root and documentation
  cleanup. It advances no goal claim and it risks the release.
- Dataset-specific package code, and new estimators that only improve a demonstration.
- The 36 unverified low-severity review findings, except where a batch above reaches one.

## Acceptance

    no known material defect under the 0.2.6 acceptance set
  + one canonical scientific model, published and reachable
  + every public claim reproduced against the implementation that answers it
  + skills route, decline, and are tested against live behaviour
  + cross-surface and compositional audit complete over the declared 0.2.6 high-risk set
  + documentation assets render and are regenerable
  + one real NWB end-to-end example with provenance
  + published artifact independently verified from the index

The fourth line is bounded deliberately and does not claim package-wide semantic completeness.
The form matches 0.2.5's closure: no known material defect under a stated acceptance set, not a
claim of exhaustive correctness. What changed is that the set is cross-surface and compositional
rather than per-surface.
