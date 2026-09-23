# How much of AGENTS.md has a second home

Measured 2026-09-19 at `HEAD d7023484`. Evidence for P-15.

P-15 said `AGENTS.md` is 360+ lines against a contract requiring a thin router that never
duplicates project truth, and that **the duplication had not been measured, so the size was not
yet evidence of a defect.** This is that measurement. It refutes the framing: the file is long,
and length is not where the defect is.

## Method

Size is a proxy. Duplication is the invariant, so duplication is what gets measured.

`AGENTS.md` is cut into claim-bearing sentences (8 words or more, fenced code excluded — a shared
code block is a quotation, not a duplicated claim). Every other authority is cut the same way.
Each `AGENTS.md` sentence is scored against every sentence elsewhere by Jaccard similarity over
4-grams of words, which survives rewording in a way a literal diff does not. A pair scoring 0.34
or above is counted as one claim with two homes.

Script: `scripts/measure_agents_md_duplication.py`. Re-run it; do not quote these numbers from
this file once `AGENTS.md` changes.

## Result

| Quantity | Value |
|---|---|
| Lines in `AGENTS.md` | 446 |
| Claim-bearing sentences | 187 |
| Sentences compared against | 1969, across 24 other authorities |
| **Duplicated** (Jaccard ≥ 0.34) | **0 — 0.0%** |
| Echoed (0.18 ≤ Jaccard < 0.34) | 6 — 3.2% |

Where it sits:

| Section | Sentences | Duplicated | Echoed |
|---|---|---|---|
| §2 Project state | 18 | 2 | 1 |
| §0 Where things are | 21 | 2 | 0 |
| §11 Release acceptance | 9 | 1 | 3 |
| §6 Tools | 7 | 1 | 1 |
| §8 Changes | 5 | 1 | 0 |
| §11 Evidence standards | 6 | 1 | 0 |
| Preamble | 44 | 0 | 3 |
| §12 Autonomy | 9 | 0 | 0 |
| every other section | 61 | 0 | 2 |

## The eight

Each is one claim that will disagree with itself the first time one copy is edited.

| Score | In `AGENTS.md` | Also in | Disposition |
|---|---|---|---|
| 1.00 | §11 — "the release opens when one full pass over the documentation, the code and both stacks discovers no new problem" | `artifacts/problem_stack.md` | Verbatim copy. Settles by deleting the non-owner |
| 0.58 | §6 — supported interpreters declared in `pyproject.toml`, enforced by gate 8 | `artifacts/fact_stack.md` | `fact` owns it; §6 points |
| 0.56 | §8 — "smallest change that reaches the acceptance you defined" | `CONTRIBUTING.md` | Contributor-facing and agent-facing; decide one owner |
| 0.50 | §2 — evidence can falsify whether a fact applies, not authorize rewriting it | `artifacts/fact_stack.md` | `fact` owns it |
| 0.44 | §0 — what `release_gate.py` does | `CONTRIBUTING.md` | The map may name it; the description belongs in one place |
| 0.41 | §11 — conformance to an official reference is sufficient evidence | `artifacts/todo_stack.md` | `AGENTS.md` owns it; the stack points |
| 0.36 | §0 — CI tests 3.12, 3.13, 3.14 | `artifacts/goal.md` | `goal` owns the supported set |
| 0.34 | §2 — why `reconstruct_state.py` exists | `artifacts/problem_stack.md` (P-C7) | The problem row owns the history |

## What this means for P-15

The premise does not hold. 4.4% duplication is not a thin-router violation by size, and trimming
`AGENTS.md` toward a line count would be optimizing a proxy — the same error P-37 records. The
defect is eight specific claims, each individually resolvable by naming an owner and making the
other file point at it. 06-72 does that.

Two observations the raw number hides:

**§12 Autonomy contributes zero duplicates** despite being the newest and one of the longest
sections. Length and duplication are independent here, which is the point.

**Six of the eight duplicates sit in §0 and §2** — the two sections whose job is to route. A
router that restates what it routes to is the failure mode P-15 was reaching for, and it is
visible at this resolution and not at the resolution of a line count.
