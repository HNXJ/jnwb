# 0.2.0



# 0.2.1


# 0.2.2


# 0.2.3


# 0.2.4

- 0.2.4-01: Empty the executable todo stack (zero unresolved package tasks unless explicit human decision blocks release).
- 0.2.4-02: Documentation minimization pass: Audit and eliminate duplicated explanations, stale version statements, excessive prose, internal codes, unsupported claims, drifting screenshots, and non-executing examples; verify small, accessible docs without internal engineering manual overhead.
- 0.2.4-03: Executable tutorial verification against installed wheel: Run all 8 tutorials (01 basics through 08 end-to-end) in a clean environment against the installed wheel without repo-relative imports; verify synthetic expected truth is known by construction and labeled synthetic.
- 0.2.4-04: Independent numerical audit of every high-risk primitive and composition for sign, scale, units, axes, complex preservation, aggregation order, failure, boundary, and determinism.
- 0.2.4-05: Randomness and inference audit verifying caller control of RNG, no global RNG mutation, no salted hash seeds, verified permutation exchangeability, and CV isolation.
- 0.2.4-06: NWB/addressing audit with synthetic fixtures covering missing tables/columns, alternate layouts, identifiers, malformed labels, units, geometry, ambiguity, and lazy access (no missing metadata becomes valid-looking science).
- 0.2.4-07: API audit verifying implementation == exports == signatures == typing == docstrings == reference docs == examples == skills with zero leaked deprecated symbols.
- 0.2.4-08: Boundary audit scanning code, tests, docs, examples, skills, agents, defaults, and artifacts for zero downstream semantic leakage.
- 0.2.4-09: Skills and agents adversarial acceptance testing against stale APIs, ambiguous units, downstream requests, invalid assumptions, and evidence conflicts.
- 0.2.4-10: Dependency matrix audit verifying base install and declared optional dependency combinations, plus import-time optional dependency behavior.
- 0.2.4-11: Supported Python and OS matrix audit derived from live metadata/CI; every required remote CI job must PASS.
- 0.2.4-12: Strict documentation build audit with all examples/API references resolved, zero stale names, zero contradictory definitions, zero unsupported claims.
- 0.2.4-13: Distribution audit building sdist and wheel from clean checkout, inspecting manifests, installing into clean environments, verifying site-packages resolution, and running representative numerical workflows against installed wheel.
- 0.2.4-14: Reproducibility audit from fresh checkout -> install -> tests -> docs -> calibration -> representative workflows with zero undocumented local state.
- 0.2.4-15: CPU/CUDA/parallelism independent verification: Confirm performance decisions and numerical parity across CPU and GPU backends on clean test systems.
- 0.2.4-16: Independent final critic pass attempting to falsify numerical correctness, boundary, API consistency, docs, skills, agents, packaging, CI, and release state.
- 0.2.4-17: Release seal verifying acceptance predicate Q_release = Q_science & Q_API & Q_performance & Q_CPU/GPU & Q_NWB & Q_docs & Q_tutorials & Q_skills/agents & Q_distribution, changelog/version bump, clean tree, commit, push dev, remote CI PASS, merge/release per policy, tag, build, install, smoke-test, and reconcile.

# Before 1.0

- Replace example-based estimator coverage with analytic/property-based tests.
- PSTH SEM policy for `N=1` trials (zero vs NaN) if statistical contract tightened.
- Processing-module discovery generalization beyond LFP if corpus requires it.

# Unversioned

- File omission-side expert-feedback items in the omission repository.
