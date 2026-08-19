# CLAUDE.md — jnwb

Generic, dataset-agnostic NWB (Neurodata Without Borders) analysis library. Project-specific
doctrine (paradigms, corpus specifics, manuscript rules) lives under each project folder's own
`CLAUDE.md` — e.g. [`omission/CLAUDE.md`](omission/CLAUDE.md) for the `omission` example
project — and adds to, never overrides, what's here.

## Freeze policy (2026-08-19)

`omission` is now `jnwb`'s major dataset, test corpus, and main reason for the library's
existence — not a peer project. Given that, **`jnwb/` is frozen and read-only from here
forward.** Do not edit, add to, or refactor anything under `jnwb/` except in the rare case Hamm
explicitly authorizes it for that specific change. Every other omission-track task (new
analyses, figures, scripts, evidence) works *through* the frozen API, never by extending it.
If a task seems to need a new `jnwb` function or a change to an existing one, stop and say so
rather than writing it — that is exactly the case requiring authorization first.

All omission-related work — scripts, figures, evidence, tests, docs — stays inside `omission/`.
That folder is expected to eventually move to `.gitignore` (kept locally, backed up outside git)
and be absorbed into `jnwb`'s examples/docs in reduced form; treat it as project-local, not as
part of the library's own tracked surface, even before that gitignore change actually lands.

**The freeze is enforced, not just stated**: `tests/test_jnwb_frozen_boundary.py` asserts
`jnwb/` has zero omission/ imports beyond the two authorized exceptions above, that those two
stay lazy (function-body-local, not module-level), that `import jnwb` succeeds even with
omission/ blocked from `sys.path` entirely, and that every `jnwb.__all__` name actually
resolves. A change that breaks the freeze fails this test before it fails a human review.

## Repo-wide freeze (2026-08-19 → 2026-09-28)

For 40 days from 2026-08-19, **no commits or pushes land on this repo at all** — this is on top
of, and broader than, the `jnwb/` freeze above, which already forbade editing `jnwb/`. During
this window `omission/`'s normally-tracked surface (scripts, figures, `context/`, tests, docs)
is paused the same way: don't commit new or changed files there either, even routine ones.

All actual work during the freeze happens as local files inside `omission/outputs/` (already
gitignored, already local-only — see `.gitignore:19`). Nothing written there needs review or
authorization to create/edit; it's scratch space by design.

**Anything discovered during the freeze that *would* be worth applying to the tracked repo** —
a fix, a new analysis, a `jnwb` change that needs Hamm's authorization, a doc correction — gets
written up as a markdown file under `omission/outputs/fixlist/`, one file per item
(`fix-<short-slug>.md`), instead of being applied now. Each entry should say what the change is,
why it matters, and exactly what files it would touch, so it can be actioned quickly once the
freeze lifts — write it as a ticket for future-you, not a diff.

At the end of the freeze (2026-09-28), `omission/outputs/fixlist/` becomes the punch list for
the next major change pass: work through it, apply what's still relevant, and only then resume
normal commit/push activity.

## Where truth lives

| Question | Source | Never |
|---|---|---|
| What is in the public API | `jnwb/__init__.py`'s `__all__` | a symbol list remembered from any document, including this one |
| What was actually computed | the receipt named beside the number | a summary of it |

## Tripwires

1. **No empirical value in any output that no script computed from data.** Hardcoded values
   are permitted only for visual/task constants or output explicitly marked synthetic.
2. **Take the logarithm last.** Average power, divide by baseline, `10·log10` once. Never
   average decibels — it biases each site by its own noisiness.
3. **`jnwb/` does not import from any project folder** (e.g. `omission/`). The dependency runs
   one way: projects depend on `jnwb`, never the reverse. A handful of narrow, documented
   exceptions exist today (lazy, call-time-only imports for optional cross-project delegation,
   e.g. in `addressing.py` and `jrsa.py`) — do not add more without discussing the layering
   first.
4. **Preserve module- and array-level invariants**: units, coordinate frames, timestamps,
   sample rates, 0- vs 1-indexing do not change silently across a `jnwb` function boundary.

## Working agreements

- Preserve originals; write revisions as new files.
- Do not commit or push unless asked.

## Skills

Load the skill before doing the work; do not reinvent its contents. See a project folder's own
`CLAUDE.md` for its task-scoped skills (e.g. `omission/CLAUDE.md`).
`numerical-computing` · `biophysical-modeling`
