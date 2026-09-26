# Documentation form

The contract every jnwb documentation page is measured against. It exists because a verbosity or
formatting judgment made page by page is a preference, and pages each edited to their own
preference are worse than pages left alone.

Every rule below is checkable by reading one page against it and getting the same answer twice.
A rule that needed taste was removed rather than softened, and the removals are recorded at the
end so nobody re-proposes them.

## What this contract governs

Four kinds of page, with different rules, because a tutorial and an API page fail differently.

| Kind | Pages | Authored where |
|---|---|---|
| Authored | `index`, `install`, `quickstart`, `agents`, `errors`, `common_mistakes`, `references`, `architecture`, `glossary`, `vis`, and `01`–`10` (20 pages) | the Markdown page itself |
| Generated | `api.md` | `scripts/generate_api_md.py` |
| Included | the 10 `tutorials/*.md` | `examples/tutorials/*.py`, pulled in by a snippet include |
| Contract | this page | the Markdown page itself; F1 and F5 bind it like any other, and it has no length ceiling |

The four rows cover all 32 pages in the nav, this one included.

**Generated and included pages are governed through their source, never by editing the page.**
An edit to one of those eleven pages is discarded by the next build, silently. A change that
trims, retitles or reformats documentation edits the authored pages; if a generated or included
page violates a rule, the fix goes to the generator or the script it includes.

## Form

| # | Rule | How it is checked |
|---|---|---|
| F1 | Headings stop at `###`. | count headings of four or more `#` outside fenced code — must be zero |
| F2 | Three or more comparable facts of the same kind go in a table. | a detector for one shape, below; review for every other shape |
| F3 | An enumeration that makes no ordering claim is a list, not a paragraph. | review |
| F4 | A paragraph carries reasoning. A paragraph that only enumerates violates F2 or F3. | review |
| F5 | One surface form per concept, taken from the vocabulary list. | machine-checked against the [vocabulary list](#vocabulary) below |
| F6 | Every figure is referenced by the prose next to it, and no page carries a figure that repeats what its adjacent table already says. | review |
| F7 | No page states a fact that a gate or a test does not enforce and no command in the page demonstrates. | review |

F1 had two violations, at `04_spectral_analysis_and_tfr.md:103` and
`06_spikes_psth_and_onset_dynamics.md:74` — both a function name used as a heading, both now
`###`. The count is zero and is machine-checked, so it stays zero without being watched.

`scripts/docs_form_gate.py` runs F1, F5, the navigation rules N1, N2, N3 and N5, figure rule
G2, and the F2 detector, and prints one PASS or FAIL line for each. The rows whose column reads
review are checked by a reader: F3, F4, F6, F7, N4 and G3.

The F2 detector reports a paragraph in which three or more inline-code names each open a clause
with the same kind of verb, such as three functions each followed by "returns". It reads
paragraphs only and counts only code-span subjects, so F2 stays a review item for facts with
plain-English subjects, for a list of facts, and for facts spread across paragraphs.

F2's hard case was `common_mistakes.md`: the largest authored page after the generated API
reference, and until 2026-09-20 it carried zero tables across 2308 words. Three of its
sections held three or more comparable facts apiece — the directed metrics and what each
cannot rule out, the three causal-filter group delays, and the three representations of an
estimate that does not exist — and all three are tables now. F2 survived the page without
needing taste, which is what it was put on the hard case to find out.

## Vocabulary

F5's list. One concept per row: the surface forms to use, and the ones that are superseded.
English inflects, so a row accepts several forms of the same word — what it forbids is the
other spelling of it.

Every term below is backticked, and that is load-bearing rather than decorative. The check
reads prose with code spans stripped, so backticking lets this page name a superseded form
without reporting itself as a page that uses one.

| Concept | Use | Not |
|---|---|---|
| A recording defect, and its repair | `artifact`, `artifacts` | `artefact`, `artefacts` |
| Scaling to a common range | `normalize`, `normalizes`, `normalized`, `normalizing`, `normalization` | `normalise`, `normalises`, `normalised`, `normalising`, `normalisation` |
| Examining data | `analyze`, `analyzing`, `analyzed` | `analyse`, `analysing`, `analysed` |
| Adjacency in space or time | `neighboring`, `neighbor`, `neighbors` | `neighbouring`, `neighbour`, `neighbours` |
| Respecting a stated setting | `honor`, `honors`, `honored` | `honour`, `honours`, `honoured` |
| Bringing a value into memory | `materialize`, `materializes`, `materializing`, `materialized` | `materialise`, `materialises`, `materialising`, `materialised` |
| A rendered color | `color`, `colors` | `colour`, `colours` |
| Metric distance | `meters`, `micrometers` | `metres`, `micrometres` |
| Observable conduct | `behavioral` | `behavioural` |
| Fitting a model | `modeling`, `modeled` | `modelling`, `modelled` |
| Alignment on a midpoint | `centered`, `centering` | `centred`, `centring` |
| Propagation across space | `traveling` | `travelling` |
| A call made on the evidence | `judgment` | `judgement` |
| Terms of permitted use | `license`, `licenses` | `licence`, `licences` |
| A cortical layer | `layer`, `layers` | `lamina`, `laminae` |
| Spikes per second | `firing rate`, `firing rates` | `spike rate`, `spike rates` |
| The time-frequency object | `TFR`, `time-frequency representation`, `time-frequency representations` | `time-frequency decomposition` |
| An exported function | `operation`, `operations` | `primitive`, `primitives` |

**What is deliberately not on this list.** Three kinds of near-synonym were measured across
the corpus and left alone, because collapsing them would destroy a distinction rather than
enforce a convention.

| Left alone | Why |
|---|---|
| `channel`, `contact`, `electrode` | Three different things: the data axis, the physical thing on the probe shaft, and the NWB table row. A page that says `contact` where it means `channel` is wrong, but no rename fixes that |
| `trial`, `epoch` | A trial is a row of an interval table; an epoch is the window cut around one. `epoch_continuous` turns the first into the second |
| `unit`, `units`, `electrodes`, `acquisition`, `trials` | NWB's own nomenclature, fixed upstream. Adopted, not renamed |

The pairs that name two things -- operation and workflow, session and recording, contact and
channel, electrode and electrodes table -- are defined once on the [Glossary](glossary.md).
Terms measured and found to be one concept under two spellings are on the first table. Terms
measured and found to be two concepts — `shank` against `probe`, `region` against `area`,
`site` against `channel` — are not, because every occurrence of each was the right word.

## Length

A ceiling is a review trigger, not a gate. Shorter is not the acceptance condition; shorter while
lossless is. A page over its ceiling justifies the excess in one sentence or is cut.

| Kind | Ceiling | Why this number |
|---|---|---|
| Landing (`index.md`) | 400 words | it routes a reader; it does not teach one |
| Task (`install`, `quickstart`, `errors`, `common_mistakes`, `agents`) | 900 words | `install` at 835, `quickstart` at 819 and `agents` at 871 sit under it |
| Concept (`01`–`09`, `architecture`, `vis`) | 1200 words | nine of the eleven sit under it |
| Reference (`api.md`, `references.md`, `10_operation_specifications.md`, `glossary`) | none | length is a function of the API's size, and trimming it removes facts |
| Included (`tutorials/*`) | none | the page is a wrapper; the script it includes is the content |
| Contract (this page) | none | it is a reference for the other rows |

Measured 2026-09-25 with `wc -w`. Four pages sit over their ceiling, and each owes the one
sentence the rule asks for:

| Page | Words | Why the excess stands |
|---|---|---|
| `common_mistakes` | 2425 | eleven failure modes, each with a wrong form, a correct form and the reason; cutting one removes a failure mode rather than words |
| `02_paths_addressing_metadata` | 1609 | four unrelated subsystems — paths, streaming, addressing, metadata — on one page. The excess is a split, not a trim, and a split is not this rule's business |
| `04_spectral_analysis_and_tfr` | 1873 | same shape: PSD, decibel formation, coherence and Morlet TFR share a page |
| `errors` | 1679 | twelve error classes, each with its verbatim message, and the table of what a read returns for each on-disk state of `session_description`. The messages are pinned to the source, so they are not paraphrasable |

## Navigation

| # | Rule | How it is checked |
|---|---|---|
| N1 | Group depth is two. | parse `mkdocs.yml` |
| N2 | No group holds a single page. | parse `mkdocs.yml` |
| N3 | Every page is reachable in two clicks. | follows from N1 given every page is in a group; a top-level page outside a group fails |
| N4 | A top-level group is named for the question a reader arrives with, not for the material it contains. | review |
| N5 | Every nav target resolves to a file on disk. | parse `mkdocs.yml` against the tree |

All five hold today: six groups, depth two, 32 targets, all resolving, none holding one page.

N4 was the open one until the nav was reordered by arrival rather than by the order the pages
were written. "Getting started" carried the public API reference, the bibliography and this
page, none of which anyone arriving to get started is looking for, and "Architecture &
Foundations" carried two method pages. The groups now answer a question apiece:

| Group | The reader arriving at it |
|---|---|
| Getting started | install it and get one result out |
| Tutorials | walk me through a whole analysis |
| Doing an analysis | how do I do this particular thing |
| Troubleshooting | it raised, or the number looks wrong |
| Reference | what exactly does this function take |
| Design & conventions | why is it shaped this way |

## Figures

The site has two palette schemes, `slate` and `default`, each with a toggle, keyed on
`prefers-color-scheme`. It had one until 2026-09-19, which is why the rules below can be checked
at all: a figure that hardcoded a light background was previously unfalsifiable, because there was
no light ground to compare it against.

| # | Rule | How it is checked |
|---|---|---|
| G1 | No figure encodes its own background color. | every corner pixel of every figure is transparent, machine-checked |
| G2 | A figure is legible under both palette schemes. | each figure has a light and a dark variant, shown with `#only-light` and `#only-dark`; a fixed color outside a generator's per-theme table reads on both backgrounds, machine-checked |
| G3 | No figure is adapted from Paper2Agent. Its license forbids derivative figures. | review; the constraint is recorded in `artifacts/direction.md` |
| G4 | No documentation figure requires a library the `docs` extra does not declare. | build the docs in a clean environment |

**Format is not a rule.** Nine pages carry raster PNGs and they stay.
An inline-SVG requirement was proposed and removed: it would have forbidden what those pages do,
which is the signal that a rule is wrong rather than the pages. New figures that carry structure
are inline SVG because it scales and stays searchable, and that is a reason, not a rule.

G4 exists because plotly and kaleido are installed on the development machine and declared only
in the optional `vis` extra, not in `docs`. A page that rendered through them would build here and
fail in a docs-only environment, and nothing would say why. Ruled 2026-09-19: documentation
figures render without them.

## Rules that were proposed and removed

Kept here so they are not re-proposed as improvements.

| Proposed | Why it was removed |
|---|---|
| A global word ceiling across all pages | fails the reference pages for being long, which is what a reference is |
| "Prefer active voice" | not checkable twice with the same answer |
| "Every page opens with a summary paragraph" | would add words to the four pages already over their ceiling |
| "Figures are inline SVG, never raster" | forbids what nine pages do today, which is the signal that the rule is wrong rather than the pages |
