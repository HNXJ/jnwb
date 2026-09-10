# TODO stack

Open work on `jnwb`, in the order a 2026-09-10 deep review of the published 0.1.5 sdist
recommended. That review scored 91/100 and found nothing requiring withdrawal of 0.1.5:
the remaining deficits are architectural maturity, not correctness. Items 1-6 are its
recommended path from 91 toward 100.

Each entry names what is wrong, where, and what closing it means. Nothing here blocks
using 0.1.5.

New analysis methods are explicitly **not** a priority until 1-4 are substantially closed.
Completeness for jnwb means small sufficient primitives, explicit semantics, strong
composition, and no hidden study choices — not breadth of method.

---

## 1. Scope the HDMF patch to jnwb's own readers — target 0.1.6

**Where:** `jnwb/__init__.py:25-96`

`import jnwb` replaces `hdmf.build.manager.BuildManager.construct` on the class, for the
whole interpreter. It repairs four builder anomalies on read:

1. scalar string attributes stored as 1-element arrays → decoded to `str`
2. a missing top-level `session_description` → inserted
3. `units.colnames` listing index columns → `spike_times_index` swapped for `spike_times`
4. `waveform_mean_index` / `spike_amplitudes_index` missing `VectorIndex` type or `target`,
   and float index data → retyped, re-pointed, cast to `int64`

Repairs 1, 3 and 4 recover information already in the file. Files written by the upstream
tool that produced them fail to read without this. **Do not simply delete the patch** —
it exists to recover real malformed builders. Preserve the capability, narrow the state
mutation.

**Two defects, independent of each other:**

**1a. The patch is process-wide.** Any other code in the same process — pyNWB directly, a
notebook, another library — reads *every* NWB file through jnwb's `construct`. The review
enumerates the consequences: behaviour depends on import order; unrelated HDMF users
inherit jnwb's semantics; correctness depends on HDMF internals that upstream may change;
and `BuildManager.construct` no longer means what a debugger says it means. The repair also
runs for callers who never needed malformed-file recovery.

**1b. Repair 2 fabricates data.** A missing `session_description` becomes the literal
`'NWB session'`, indistinguishable afterwards from a description the experimenter wrote.
This violates tripwire 1 in `CLAUDE.md`: no empirical value in any output that no script
computed from data. Close by writing `''` or failing loudly. Either way a reader must be
able to tell the file carried no description.

Neither defect is new; both predate 0.1.5.

**Order of work:** establish the exact malformed-file cases that require each repair
first, then move the repair to jnwb's NWB-read boundary. A case with no reproducer is a
candidate for removal rather than migration.

**Done means:** a process that imports jnwb and then reads an NWB file through pyNWB gets
unpatched HDMF behaviour, with a test asserting it; and no jnwb code path invents a
description.

## 2. Cut import time — target 0.1.6

**Measured 2026-09-10** by `python -X importtime -c "import jnwb"` on the working tree:

| Module | Cumulative | Share |
|---|---:|---:|
| `jnwb` (total) | 24.88 s | 100% |
| ` jnwb.analyzers` | 23.71 s | 95% |
| `  scipy.signal._support_alternative_backends` | 23.29 s | 94% |
| `   scipy.stats` (via `scipy.signal._peak_finding`) | 12.86 s | 52% |
| `   scipy.signal._signaltools` (via `_spline_filters`) | 8.17 s | 33% |
| ` hdmf.build.manager` | 0.66 s | 3% |
| ` jnwb.decoding` | 0.26 s | 1% |

`scripts/benchmark_import.py --write` reports 50445 ms cold and 9115 ms warm; the
`-X importtime` run above was slower still. The spread across runs is large, so treat the
benchmark as the acceptance measure and compare like with like.

The distribution is the finding, not the absolute number: **jnwb's own modules cost
almost nothing.** One eager import chain — `jnwb.analyzers` pulling `scipy.signal`, which
pulls `scipy.stats` — is essentially the entire cost. `pynwb` alone imports in 0.3 s.

A warm import this slow damages interactive analysis, CLI and MCP startup, worker process
spawning, notebook iteration, and small scripts. Every `parallel_map` worker pays it.

**Done means:** `import jnwb` does minimal work and each capability imports what it needs
when called, verified by the benchmark against the 9115 ms baseline. Not micro-optimisation
— the target is the eager chain.

## 3. Project provenance in generic source

**Where:** 83 occurrences of `omission` across 17 modules. Densest:

| Module | Count |
|---|---:|
| `jnwb/statistics.py` | 12 |
| `jnwb/__init__.py` | 12 |
| `jnwb/metadata.py` | 9 |
| `jnwb/spectral.py` | 7 |
| `jnwb/artifact_repair.py` | 7 |

Three kinds, needing different treatment:

- **Promotion provenance** — "promoted 2026-08-23 from `omission.jnwb_ext.spectral`".
  Historical record with no bearing on behaviour. `git log`, the changelog, or one
  architecture note holds it better than a comment naming a module jnwb cannot resolve.
- **Live claims about another repository** — `jnwb/spectral.py:40` asserts that
  `omission.jnwb_ext.connectivity.CANONICAL_BANDS` re-exports jnwb's constant. jnwb cannot
  verify this, and it goes stale the moment that repository changes.
- **Intrusive residue** — the review's word. `jnwb/artifact_repair.py` discusses defaults
  "tuned on the omission corpus", historical artifact receipts and downstream figure paths;
  `jnwb/statistics.py:888` uses `"FR during omission > FR during stimulus in FEF O+ units"`
  as its worked example; `jnwb/trajectory.py:65` and `jnwb/decoding.py:12` explain
  themselves in terms of `OmissionSession`'s API.

Generic source should answer what an operation computes, under what assumptions, and how
it fails. Where a downstream corpus is genuinely the reason a default has its value, say
so without requiring the reader to know that corpus.

The numerical implementation is not project-specific, so this is not a release defect —
two reviews have now declined to treat it as one. It is what keeps the package from 100.

**Gate 12 cannot catch this, by design.** It parses executable syntax and skips comments
and docstrings, which is right for a hard CI gate — historical prose would otherwise make
it fail noisily. So `Gate 12 PASS` and `package is project-neutral` are different claims,
and the first must not be reported as the second. Measure the residue with a separate
**non-blocking** source-neutrality audit; leave the deterministic runtime gate alone.

**Done means:** no comment in `jnwb/` asserts anything about a project repository's
contents, and no docstring needs knowledge of a downstream project to be understood.
Semantics-preserving: no numerical behaviour changes.

## 4. Audit the broad exception handlers

**Where:** 31 `except Exception` sites in `jnwb/`. Densest: `spectral.py` 7, `jrsa.py` 5,
`analyzers.py` 3, then `metadata.py`, `mcp_server/nwb_tools.py`, `addressing.py` and
`_backend.py` at 2 each.

Broad catches are correct at optional-backend, controlled-fallback and external-file
parsing boundaries. They are dangerous when they convert a programming error or a
numerical defect into a plausible-looking fallback result — which is exactly how the
`cross_area_coherence` defect survived as long as it did.

Classify each site as **required boundary**, **narrowable**, or **dangerous**. Every
fallback must either preserve estimator identity or report that it could not.

## 5. A strict path for metadata filtering

**Where:** `jnwb/metadata.py`, `filter_by_criteria`

An unknown criterion is ignored, so `{"aera": "V1"}` returns the table unfiltered — a
misspelled selection silently yields a *larger* dataset. For scientific analysis the
failure should be asymmetric the other way.

The behaviour is documented and pinned intentional by
`tests/test_metadata.py:118 test_unknown_column_is_ignored_not_an_error`, so preserving it
through 0.1.5 was correct. It is API debt, not a bug.

Add `unknown="raise"` alongside the current `"ignore"`, keep `"ignore"` as the default for
compatibility, and consider flipping the default only at a declared breaking release.

## 6. Audit the public surface before 1.0

`jnwb.__all__` exports 111 symbols. Each one costs compatibility burden, documentation,
namespace complexity, import work, and long-term support.

Test each against: is this a primitive a user should reasonably call directly, or an
implementation component exported because it was convenient? Do not shrink the number for
its own sake.

## 7. Strengthen tests where coverage is example-based

The suite is broad and adversarial — `tests/test_harness_adversarial_gates.py` tests the
gates themselves, which is the right response to an earlier false PASS. The remaining gap
is estimators covered by examples rather than by analytic, property-based or composition
tests.

## 8. File the omission-side issue from #4

Items 1, 2, 5 and 6 of the expert feedback register are questions about the omission
project's data and figures, not about jnwb. The jnwb-side reply says they belong in the
omission repository; nothing files them there yet. Items 3 and 4 were checked against
0.1.5 and are closed (3 became the HSIC fix).

## 9. The remaining four notebooks

`examples/notebooks/01_spectral_and_inference.ipynb` covers spectral analysis and
inference; WP3 planned five. `tests/test_notebooks.py` executes every notebook in the
directory, so a new one is picked up with no test change.

---

## Closed

- Issues 1-12, and release pages for v0.1.3-v0.1.5 — 2026-09-10.
- Stale jnwb 0.1.1 on Python 3.12 — upgraded to 0.1.5 and verified from outside the repo
  2026-09-10. It had been masked whenever the working directory was the repo, and surfaced
  only when a notebook kernel ran from a temp directory. `tests/test_notebooks.py` is now
  hermetic regardless: it launches `sys.executable` with the repo root on `PYTHONPATH`
  rather than trusting the global `python3` kernelspec.
