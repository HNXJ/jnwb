# TODO stack

Open work on `jnwb`, most consequential first. Written 2026-09-10, immediately after
0.1.5 shipped to PyPI. Each entry names what is wrong, where, and what closing it means.

Nothing here blocks using 0.1.5. Items 1 and 2 are correctness-adjacent; the rest is
cleanup and follow-through.

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
tool that produced them fail to read without this.

**Two defects, independent of each other:**

**1a. The patch is process-wide.** Any other code in the same process — pyNWB directly, a
notebook, another library — reads *every* NWB file through jnwb's `construct`. Importing an
analysis library must not change how an unrelated file parses. Close by moving the repair
into jnwb's own read path, so a caller who never asks jnwb to open a file is unaffected.

**1b. Repair 2 fabricates data.** A missing `session_description` becomes the literal
`'NWB session'`, indistinguishable afterwards from a description the experimenter wrote.
This violates tripwire 1 in `CLAUDE.md`: no empirical value in any output that no script
computed from data. Close by writing `''` or failing loudly. Whichever is chosen, a reader
must be able to tell that the file carried no description.

Neither defect is new; both predate 0.1.5. A review flagged 1a as the highest-priority
post-release technical item and explicitly deferred it out of 0.1.4 and 0.1.5.

**Done means:** a process that imports jnwb and then reads an NWB file through pyNWB gets
unpatched HDMF behaviour, with a test asserting it; and no jnwb code path invents a
description.

## 2. Project references in `jnwb/` comments and docstrings

**Where:** 83 occurrences of `omission` across 17 modules. Densest:

| Module | Count |
|---|---|
| `jnwb/statistics.py` | 12 |
| `jnwb/__init__.py` | 12 |
| `jnwb/metadata.py` | 9 |
| `jnwb/spectral.py` | 7 |
| `jnwb/artifact_repair.py` | 7 |

Two kinds, needing opposite treatment:

- **Promotion provenance** — "promoted 2026-08-23 from `omission.jnwb_ext.spectral`". A
  historical record with no bearing on behaviour. `git log` holds it better than a comment
  that no longer resolves to anything.
- **Live claims about another repository** — `jnwb/spectral.py:40` asserts that
  `omission.jnwb_ext.connectivity.CANONICAL_BANDS` re-exports jnwb's constant. jnwb cannot
  verify that, and it goes stale the moment the other repository changes. A registry
  pointing at files jnwb cannot resolve.

Gate 12 passes all of these deliberately: it parses code strings and identifiers and skips
comments and docstrings. This is a readability and staleness problem, not a boundary
breach — the layering invariant holds.

A review deferred this out of 0.1.4 as a non-blocker.

**Done means:** no comment in `jnwb/` asserts anything about a project repository's
contents. Provenance either goes or is stated without naming a module path jnwb cannot
resolve.

## 3. Close the five GitHub issues

Replies are drafted, verified against 0.1.5, and split one file per issue:
`scratchpad/issues/{4,9,10,11,12}.md` (session scratchpad — copy them somewhere durable
before the session ends).

Blocked on credentials, not on work. `gh` reads its token from the Windows keyring, which
is scoped to the interactive desktop session; agent processes see an empty config entry and
get 401. Run from a shell where `gh auth status` shows the keyring token:

```powershell
foreach ($n in 4,9,10,11,12) { gh issue close $n -R HNXJ/jnwb -c (Get-Content "$d\$n.md" -Raw) }
```

## 4. File the omission-side issue from #4

Items 1, 2, 5 and 6 of the expert feedback register are questions about the omission
project's data and figures, not about jnwb. The jnwb-side reply says they belong in the
omission repository; nothing files them there yet. Items 3 and 4 were checked against
0.1.5 and are closed (3 became the HSIC fix).

## 5. The remaining four notebooks

`examples/notebooks/01_spectral_and_inference.ipynb` covers spectral analysis and
inference; WP3 planned five. `tests/test_notebooks.py` executes every notebook in the
directory, so a new one is picked up with no test change.

## 6. Environment: stale jnwb on Python 3.12

Not a repository defect — recorded because it hid a real one. Python 3.12's site-packages
holds jnwb 0.1.1, masked whenever the working directory is the repo. It surfaced only when
the notebook kernel ran from a temp directory and imported the old copy. Fix with
`py -3.12 -m pip install -U jnwb`.

The test is now hermetic regardless: it launches `sys.executable` with the repo root on
`PYTHONPATH` rather than trusting the global `python3` kernelspec, which runs whichever
`python` is first on `PATH`.
