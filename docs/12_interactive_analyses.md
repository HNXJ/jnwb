# Interactive Analyses

`jnwb` is a generic analysis library; the analyses built *with* it live in project folders and are
published separately as a static **analysis atlas**. This page is the link between the two
surfaces.

```
docs source            ->  Read the Docs   (this site: API, guides, verification)
canonical tables       ->  atlas builder   ->  GitHub Pages (interactive analysis UI)
```

The separation is deliberate. Read the Docs builds the package documentation and **does not**
recompute time-frequency transforms, read NWB files, run bootstraps, or render the interactive
figure corpus. The atlas is generated ahead of time from small, reviewed tables and deployed as
static HTML, so neither build depends on the other's data.

## Analysis 6A — onset timing during stimulus omission

The pilot atlas covers **Analysis 6A**: which changes first during stimulus omission, the local
field potential or spiking? It is built from macaque multi-area laminar electrophysiology and
exercises a wide slice of this library — {py:mod}`jnwb.onset_fitting` for the onset estimators,
the spectral machinery for the frequency-resolved LFP analysis, and the permutation and
exact-interval tools for inference.

:::{admonition} Status: reviewed analysis, not a finalized manuscript result
:class: caution

The atlas labels every claim with its standing. Its primary population-level result — that
temporal *resolvability* of the omission response is higher for beta/gamma than for theta/alpha
LFP, replicated across sessions — is a reviewed scientific finding, not a published one. Several
comparisons on the site are explicitly marked *descriptive* and must not be read as population
claims.
:::

### What the atlas contains

| Section | Content |
| --- | --- |
| Overview | The corpus census and the three session-level tests, with their three different outcomes |
| SPK timing | Census funnel and per-unit resolved omission latency with bootstrap intervals |
| SPK omission vs stimulus | ΔT = T<sub>om</sub> − T<sub>stim</sub>, unit-level and session-level |
| LFP frequency & resolvability | P(resolved \| frequency), LOW-vs-HIGH session pairing, censoring |
| DSP temporal support | What the transform can resolve, shown alongside what the data resolve |
| Session-level statistics | The three exact sign-flip permutation tests |
| Coverage & design limits | Subject × session × area coverage, making the confound visible |
| Methods | Estimators, inclusion rules, constants, and what is deliberately not done |
| Static figures | Vector SVG versions of Figures A–D |
| Provenance | Source commit, canonical tables with checksums, deployed file manifest |

### Reproducibility

Every number on the atlas is read at build time from a small canonical table, and every table is
derived from an analysis receipt — never retyped. The truth order is:

```
current receipted analysis  ->  canonical table  ->  generated figure / site
```

The site is the last link and carries no independent authority. If a rendered value disagrees with
its canonical table, the site is wrong and fails its own verification gate.

Subject and session identifiers on the atlas are deterministic anonymous labels. No spike times,
LFP traces, trial-level neural data, NWB paths, or machine-local paths are published.

### Where it is published

:::{admonition} Not yet deployed
:class: note

The atlas is built and verified locally but has **not** been published yet. When it is deployed it
will be served from GitHub Pages at:

`https://hnxj.github.io/jnwb/analyses/onset-6a/`

Until that deployment happens this page deliberately records the target address as text rather
than as a link, so the documentation never points readers at an address that does not resolve.
:::

## Building the atlas locally

The builders live alongside the analysis, not in this package:

```bash
python omission/atlas/build_public_tables.py   # receipts -> canonical public tables
python omission/atlas/build_atlas.py           # canonical tables -> static site
python omission/atlas/verify_site.py           # privacy, visibility, links, reconciliation
```

Then serve the generated tree and open it:

```bash
python -m http.server 8000 --directory omission/atlas/_site
```

`verify_site.py` is the gate that matters. It runs over the *generated* output rather than the
source, and it fails closed: an artifact that is not explicitly labelled `public` is never
deployed, a declared-public artifact missing from disk is an error rather than a silent omission,
and a private identifier appearing anywhere in the deployed bytes fails the build.
