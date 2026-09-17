# Planned work after 0.2.5

Not part of the frozen 0.2.5 stack. `artifacts/todo_stack.md` is executing to empty and
nothing here may be started before it is empty, the independent critic has run, and the
release is sealed. This file exists so that requests arriving mid-pass are not lost and
do not enlarge the object being stabilized.

## P1. RDM and geometry surface (request from the omission team, ruled 2026-09-17)

The request arrived as ten candidate APIs. It is accepted in substance and rejected in
that shape: ten independent entry points would overlap each other and overlap what
already ships. It is consolidated into four groups, to be taken strictly in order.

**Order.** `finish 0.2.5 hardening -> independent closure -> RDM expansion`.

### Step 0 (mandatory, before any implementation): audit what already ships

The package is not empty here. Verified at `9a7e4fd5` by calling `inspect.signature`:

| Symbol | Signature |
|---|---|
| `rdm` | `(X, metric='correlation', condensed=True, device='cpu') -> np.ndarray` |
| `rdm_similarity` | `(rdm1, rdm2, metric='spearman') -> Tuple[float, float]` |
| `jrsa` | 30+ keyword parameters, `jnwb/jrsa.py` (1786 lines) |
| `probe_geometry` | `(electrodes_table, *, probe_name=None, units='um', ...) -> ProbeGeometry` |

`jnwb/rsa.py` is 210 lines with two private helpers, `_condensed_distances` and
`_as_condensed_rdm`. So the request is partly a consolidation and correctness request,
not ten missing capabilities. Reuse or repair this mathematics; do not create a second
RDM subsystem beside it.

### P1.1 RDM core (highest priority; absorbs candidates 1, 2, 3, 4, 8)

`rdm`, `rdm_contrast`, `rdm_similarity`. Feature-RDM orientation, Euclidean / correlation
/ cosine metrics, validity checks, identity propagation, batching, CPU/GPU parity.

The first implementation slice is deliberately `rdm + rdm_contrast + rdm_similarity`
only, with explicit orientation, IDs, the three metrics, unequal-group correctness,
deterministic behaviour, batched execution, validity checks, and CPU/GPU parity. Nothing
below starts until that primitive is independently validated.

### P1.2 RDM reliability (absorbs candidates 6, 7)

Split-half reliability and noise ceiling, deterministic splitting, attenuation
diagnostics, trial-count matching, with explicit RNG and provenance.

### P1.3 General geometry

Cross-block `U x C` geometry and radial/angular decomposition. Admissible only if their
APIs can be stated without SPK/LFP or omission semantics. If they cannot, they stay
downstream.

### P1.4 Crossnobis (deferred)

Candidate 10 stays pending until an independently validated estimator or reference
implementation exists. Covariance estimation, folds, regularization and cross-validation
make it substantially higher-risk than P1.1-P1.3.

## P2. Correctness utilities

Accepted, with one qualification: a universal structured statistical result must not
force every estimator into fields that are mathematically undefined for it. `estimate`,
`ci`, `statistic`, `df`, `p` and `n` are optional, with explicit `None` / undefined
semantics.

BH-family construction remains downstream unless the caller hands jnwb an explicit
family. This preserves the existing requirement that the inferential unit and the
multiplicity family stay visible to the caller.

The coverage identity `N_expected = N_computed + N_excluded`, `N_unexplained = 0` is a
good generic correctness primitive, provided jnwb only checks and accountably represents
coverage and never decides the scientific exclusion rule.

**Candidate: a provenance identity that names the tree, not just the version.** A
consumer recording `jnwb.__version__` alone cannot tell an editable install of this tree
from site-packages, and those are exactly the two that disagree -- 0.2.4 here against
0.1.8 installed. `__version__` with `__file__` distinguishes them; `__version__` alone
does not. This is a property of how Python resolves the package rather than of any one
consumer, so if a caller has to remember to record both, most will record the version.
This is not hypothetical, and jnwb is on the wrong side of it. `jnwb.Provenance` is
already public (`jnwb/ontology.py`, in `jnwb.__all__`) and is documented as "Part of
every Result". Its fields are `software_version`, `backend`, `timestamp`,
`random_seed`, `git_commit`, `parameters`, `environment`. Two problems:

- There is no path field. `software_version` alone cannot separate an editable install of
  this tree from site-packages, which is the distinction that matters.
- `software_version` is a required argument supplied by the caller, not read from the
  package. A caller can therefore record a version that never ran, and the dataclass is
  frozen, so the wrong value is preserved faithfully.

`environment` could carry the path but nothing asks it to. Candidate repair: default
`software_version` from `jnwb.__version__` and record `jnwb.__file__` beside it, so the
identity is taken from the package that is actually imported. Scope it narrowly -- it
identifies the package that ran, and decides nothing about what an artifact means.

Note the overlap with 05-50, which removes three unused constructors from the same
module; sequence them so they do not collide.

**Why this is worth doing rather than documenting.** The hazard is not speculative: a
probe in this pass resolved site-packages 0.1.3 instead of the tree and reported it as
the tree's number, which is why every probe here now asserts `jnwb.__file__`. But this
package's probes compare against a known-good expectation, so a wrong-tree number reads
as a failure. A consumer computing a novel quantity has no such expectation, and a
wrong-tree number there is indistinguishable from a result. The party least able to
detect the error is the one furthest from the package, which is the argument for the
identity coming from the package rather than from the caller.

## P3. Consumer-reported items (omission, 2026-09-17)

Relayed by a consumer session working against **installed 0.1.8 in site-packages**, not
this tree. Re-resolve every one against HEAD before acting; two are already fixed here.

The consumer re-resolved and confirmed: at their tree `import jnwb.laminar` raises
`ModuleNotFoundError`, `'vflip' in jnwb.__all__` is `False`, and
`classify_layer_from_depth` takes `(peak_channel_id, electrodes_df) -> str` with no unit
parameters. Their reports are accurate of 0.1.8 and stale of this tree; both statements
are true at once.

**That gap is the more useful finding.** omission does not execute this tree -- every
number its manuscript rests on came from installed 0.1.8 -- so "landed upstream" and "not
available to the consumer" are simultaneously true, and neither tree can see it alone.
Consequences to carry into the post-release re-resolution:

- Whichever jnwb the consumer runs at that point determines which of their reports are
  still live. Re-resolving against HEAD answers a different question than they are
  asking.
- Whether they upgrade is not ours to decide and not housekeeping. Their policy binds:
  package version alone never invalidates an existing artifact, their bridge stays
  `generated_with_jnwb = 0.1.3`, and an upgrade moves `analyzed_with_jnwb` for anything
  re-run after it. They also have arms mid-corpus, so the environment must not move
  underneath them.
- The same gap can bite inside one command. A script run by path imports whichever jnwb
  wins on `sys.path`, and site-packages wins unless the tree is on `PYTHONPATH` or
  installed editable, so a probe that looks like it measures this tree can measure 0.1.8
  instead. Every probe in the 0.2.5 pass asserts `jnwb.__file__` starts with the tree
  root for that reason.

| Report | Status at `9a7e4fd5` |
|---|---|
| `classify_layer_from_depth` thresholds at 1000.0 um regardless of unit, so mm-scale z silently returns a constant label | **Does not reproduce.** The function takes `depth_unit` / `threshold` / `threshold_unit`, inspects `electrodes_df` metadata for `depth_unit` / `z_unit` / `unit`, and returns `'Unknown'` when units are unknown (`jnwb/addressing.py:210-240`) |
| `jnwb.laminar` not yet landed (their JNWB-008) | **Landed.** `jnwb.laminar` ships, and `vflip`, `VFlipResult`, `xflip`, `XFlipResult` are in `jnwb.__all__`. One stale claim remains: `jnwb/addressing.py:233` still says "``jnwb.laminar`` (forthcoming)" |
| `compare_groups` has no `test=` parameter and returns both `significant_parametric` and `significant_nonparametric` from one call | Not yet re-verified against HEAD |
| Three dead `result.pop(...)` loops guarding keys that can no longer appear (`statistics.py:796/811/826`) | Not yet re-verified against HEAD |
| `jrsa`'s internal permutation null has no grouping awareness, unlike `jnwb.permutation.permute_labels(..., groups=..., scheme='within_group')` | Not yet re-verified against HEAD |

Two constraints they asked to be preserved, which are theirs to hold and not ours to
change: a package version alone never invalidates an existing artifact, and historical
provenance is not rewritten.

One design constraint worth keeping: `jnwb.paths.REPO_ROOT` is the library's root, and
reading it as the caller's root once put 6.7 GB of cache inside `site-packages`. Any new
path constant must be impossible to misread as the caller's root by its *name*, not by a
docstring.
