# Next actions — proposed, not approved

These are candidate Review → Progress cycles ranked by the P0-P3 findings in `PRGS_PREPARE.md`
§8. **Nothing here is authorized.** Each entry names the finding, why it's worth a cycle now
rather than later, and what a Review pass would need to check before any Progress work starts.

## Highest value, P0

### 1. `jnwb/report.py`'s unlabeled synthetic-data sections

**Why now:** direct violation of a numbered CLAUDE.md tripwire (#2), in a file that also
contains a correctly-labeled real-computation section in the same run — so the fix pattern
already exists in-file, it just needs to be applied to the other four sections. Low
ambiguity, clear acceptance criterion (red `PLACEHOLDER-DUMMY` title present, or the synthetic
sections removed entirely).
**Review should first check:** is `generate_report`/`jnwb/report.py` still an active deliverable
path, or superseded by the `context/figures/` pipeline (per CLAUDE.md, "Results go under
context/figures/")? If superseded, the correct Progress action may be deletion/quarantine
rather than relabeling — this is a real branch point a Review pass should resolve before
picking an approach.

### 2. `context/EVIDENCE_ARCHITECTURE.md` adoption gap

**Why now:** the project's own evidence-standing contract says it isn't binding until a file
that doesn't exist starts passing. Every claim made under "L0-L4" framing since this file was
introduced inherits this ambiguity.
**Review should first check:** was `ACCEPTANCE_TESTS.md` ever drafted and lost, or never
started? Search `artifacts/.lab/` for a node referencing it (not done this pass). If never
started, Progress work is drafting it against the five listed conditions; if lost, recovering
or re-deriving it may be faster than a rewrite.

## Important, P1

### 3. Unify or explicitly reconcile the two unit-identity conventions

**Why:** silent-collision risk (per the row-position-vs-column footgun already documented three
times in-source) is exactly the kind of bug that produces a wrong-but-plausible number, which
this project's own doctrine treats as worse than a loud failure.
**Review should first check:** whether `omission_identity.py`'s `unit_id`-column usage is
actually safe in every call site (i.e., always called post area-filter) — this audit did not
verify that; it may turn out there is no live bug, only an inconsistent-looking pattern that
happens to be safe. Don't assume a fix is needed before checking.

### 4. Reconcile `CANONICAL_BANDS` vs `BANDS_7`

**Why:** two sources disagreeing on the same quantity is a named CLAUDE.md stop condition.
**Review should first check:** whether `BANDS_7` genuinely never reaches a statistical
computation (its docstring claims visualization-only) — if confirmed, the fix may be a comment
clarifying the two are deliberately different tools for different purposes, not a merge.

### 5. `jrsa.py` fabricated-null-on-failure + unseeded GPU RNG

**Why:** two separate, independently severe issues in one file — the fabricated `(r=0,p=1.0)`
result on internal failure could already be silently present in a real analysis output; the
unseeded CuPy path breaks a reproducibility contract the rest of the module establishes.
**Review should first check:** grep `scripts/` for callers of `jrsa()` with `backend="cuda"` or
GPU-array inputs to establish whether the unseeded-RNG path has actually been exercised on a
real analysis, vs. being latent/never-hit code.

### 6. Decide the fate of the ontology/factories/20-function "public API"

**Why:** two full API surfaces with zero confirmed consumers is real maintenance weight, and the
"v1.0.0 FROZEN" label makes it look load-bearing to anyone who hasn't checked usage.
**Review should first check:** the 20-function usage claim in this audit is moderate-, not
full-, confidence (generic names weren't individually disambiguated) — re-verify before treating
either surface as confirmed-dead. This is a decision with real removal cost if wrong; don't act
on the current evidence alone.

### 7. Test coverage for `omission_identity.py` and `ontology.py`

**Why:** the file with the two currently-quarantined, self-flagged `invalid_for_inference`
functions has no dedicated test file — exactly the code most likely to need a regression guard
before someone re-enables it.

## Improvement, P2 / Cleanup, P3

Lower urgency; batch these into a single housekeeping cycle rather than separate reviews:
stale `test_skill_tree_consolidation.py` assertions; `analyzers.py` changelog/behavior mismatch;
two stale skill-doc import paths; `jnwb/_unused/` git-incomplete move (this one specifically
should be finished — stage the deletions — before any other jnwb commit, to avoid the
duplicate-resurrection risk named in `JNWB_ARCHITECTURE.md` §0); `legacy/` directory disposition
(archive further / document as explicitly out-of-scope / remove from tracking — a scope decision,
not made here); dead parameters; the `_acg_pearson` alias name.

## Explicitly not recommended as urgent

The pervasive "empty selection → zero/NaN/empty return instead of raise" pattern across
`session.py`, `spectral.py`, `metadata.py`, `functions.py` (P1-adjacent in severity but listed
separately here) is **not** a single fixable bug — it is a package-wide design convention, used
consistently, and in several places explicitly chosen over raising (e.g. `plot_tfr`'s honest
`status='missing_tfr'` counterexample shows the authors know how to fail loudly when they choose
to). A Review pass here should scope narrowly — pick the highest-traffic functions
(`session.get_epochs`, `spectral.band_power`) and decide function-by-function whether silent-empty
is the right contract, rather than treating this as one repo-wide refactor.
