# Documentation form

The contract every jnwb documentation page is measured against. It exists because a verbosity or
formatting judgement made page by page is a preference, and twenty-seven pages edited to
twenty-seven preferences is worse than leaving them alone.

Every rule below is checkable by reading one page against it and getting the same answer twice.
A rule that needed taste was removed rather than softened, and the removals are recorded at the
end so nobody re-proposes them.

## What this contract governs

Three kinds of page, with different rules, because a tutorial and an API page fail differently.

| Kind | Pages | Authored where |
|---|---|---|
| Authored | `index`, `install`, `quickstart`, `errors`, `common_mistakes`, `agents`, `references`, and `01`–`10` | the Markdown page itself |
| Generated | `api.md` | `scripts/generate_api_md.py` |
| Included | the 9 `tutorials/*.md` | `examples/tutorials/*.py`, pulled in by a snippet include |

**Generated and included pages are governed through their source, never by editing the page.**
Ten of twenty-seven pages are in those two rows. An edit to one of them is discarded by the next
build, silently. Any packet that trims, retitles or reformats documentation takes the seventeen
authored pages and leaves the other ten alone; if a generated page violates a rule, the fix goes
to the generator or the script it includes.

## Form

| # | Rule | How it is checked |
|---|---|---|
| F1 | Headings stop at `###`. | count `^#### ` — must be zero |
| F2 | Three or more comparable facts of the same kind go in a table. | review, with a seeded-violation check under 06-53 |
| F3 | An enumeration that makes no ordering claim is a list, not a paragraph. | review |
| F4 | A paragraph carries reasoning. A paragraph that only enumerates violates F2 or F3. | review |
| F5 | One surface form per concept, taken from the vocabulary list. | machine-checked, under 06-49 |
| F6 | Every figure is referenced by the prose next to it, and no page carries a figure that repeats what its adjacent table already says. | review |
| F7 | No page states a fact that a gate or a test does not enforce and no command in the page demonstrates. | review |

F1 has two violations today, at `04_spectral_analysis_and_tfr.md:103` and
`06_spikes_psth_and_onset_dynamics.md:74`. Both are a function name used as a heading, and both
become `###` or a table row.

F2's hard case is `common_mistakes.md`: 2308 words, zero tables, and the largest authored page
after the generated API reference. It is the first page 06-51 should take, and the one most
likely to show whether F2 can be applied without taste.

## Length

A ceiling is a review trigger, not a gate. Shorter is not the acceptance condition; shorter while
lossless is. A page over its ceiling justifies the excess in one sentence or is cut.

| Kind | Ceiling | Why this number |
|---|---|---|
| Landing (`index.md`) | 400 words | it routes a reader; it does not teach one |
| Task (`install`, `quickstart`, `errors`, `common_mistakes`, `agents`) | 900 words | `install` at 707 and `quickstart` at 743 already sit under it; `errors` at 1129 and `common_mistakes` at 2308 do not |
| Concept (`01`–`10`) | 1200 words | eight of the ten already sit under it |
| Reference (`api.md`, `references.md`, `10_operation_specifications.md`) | none | length is a function of the API's size, and trimming it removes facts |
| Included (`tutorials/*`) | none | the page is a wrapper; the script it includes is the content |

## Navigation

| # | Rule | How it is checked |
|---|---|---|
| N1 | Group depth is two. | parse `mkdocs.yml` |
| N2 | No group holds a single page. | parse `mkdocs.yml` |
| N3 | Every page is reachable in two clicks. | follows from N1 given every page is in a group |
| N4 | A top-level group is named for the question a reader arrives with, not for the material it contains. | review |
| N5 | Every nav target resolves to a file on disk. | parse `mkdocs.yml` against the tree |

N1, N2, N3 and N5 hold today: four groups, depth two, 27 targets, all resolving. N4 is the open
one, and it is 06-50's whole content. Today's nav orders pages by the order they were written:
"Getting started" carries the public API reference and the bibliography, which nobody arriving to
get started is looking for, and "Architecture & Foundations" carries two method pages.

## Figures

The site has two palette schemes, `slate` and `default`, each with a toggle, keyed on
`prefers-color-scheme`. It had one until 2026-09-19, which is why the rules below can be checked
at all: a figure that hardcoded a light background was previously unfalsifiable, because there was
no light ground to compare it against.

| # | Rule | How it is checked |
|---|---|---|
| G1 | No figure encodes its own background colour. | grep each figure source for a background fill |
| G2 | A figure is legible under both palette schemes. | render under each and compare |
| G3 | No figure is adapted from Paper2Agent. Its licence forbids derivative figures. | review; the constraint is recorded in `artifacts/direction.md` |
| G4 | No documentation figure requires a library the `docs` extra does not declare. | build the docs in a clean environment |

**Format is not a rule.** Seven pages carry raster PNGs from `docs/assets/figures/` and they stay.
An inline-SVG requirement was proposed and removed: it would have forbidden what seven pages do,
which is the signal that a rule is wrong rather than the pages. New figures that carry structure
are inline SVG because it scales and stays searchable, and that is a reason, not a rule.

G4 exists because plotly 6.6.0 and kaleido 1.2.0 are installed on the development machine and
declared in no extra. A page that rendered through them would build here and fail in CI, and
nothing would say why. Ruled 2026-09-19: they are not added, so figures render without them.

## Rules that were proposed and removed

Kept here so they are not re-proposed as improvements.

| Proposed | Why it was removed |
|---|---|
| A global word ceiling across all pages | fails the reference pages for being long, which is what a reference is |
| "Prefer active voice" | not checkable twice with the same answer |
| "Every page opens with a summary paragraph" | would add words to the four pages already shortest than their ceiling |
| "Figures are inline SVG, never raster" | forbids what seven pages do today, which 06-48's stop condition names as a signal the rule is wrong rather than the pages |
