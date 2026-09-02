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

:::{admonition} Status: exploratory analysis — not publication-final
:class: caution

The atlas labels every claim with its standing. Analysis 6A currently carries **one**
session-level positive inferential result: a larger fraction of high-frequency LFP responses
(beta, low gamma, high gamma) are temporally resolved than low-frequency responses (theta,
alpha), and that replicates across sessions. Everything
else is descriptive or not significant at the session level — in particular the omission-minus-
stimulus latency shift is a unit-level tendency that the available number of sessions cannot
establish. Nothing on the site is a finalized manuscript result.
:::

### What the atlas contains

| Section | Content |
| --- | --- |
| Overview | The corpus census and the three session-level tests, with their three different outcomes |
| SPK timing | Census funnel and per-unit resolved omission latency with bootstrap intervals |
| SPK omission vs stimulus | ΔT = T<sub>om</sub> − T<sub>stim</sub>, unit-level and session-level |
| LFP frequency & resolution | Fraction temporally resolved by frequency, low-vs-high session pairing, censoring |
| Transform temporal resolution | What the transform can resolve, shown alongside what the data resolve |
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

The atlas is published on GitHub Pages:

**[Analysis 6A — onset timing during stimulus omission](https://hnxj.github.io/jnwb/analyses/onset-6a/)**

The atlas index, which will list further analyses as they migrate to this pattern, is at
<https://hnxj.github.io/jnwb/>.

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
