# R2: §11 item 1 documentation review (gate A3 review clause)

Tree: `D:/tmp/jnwb_int/r2_review` at `a346708414ae9c317973f4bafacd20441aaaa003`. Read-only; scripts in `D:/tmp/jnwb_int/r2_scripts/`.

## Result

**A3 review clause: PASS (yes).** No finding breaks a criterion clause plainly. Ten non-blocking rows are listed below (4 minor, 4 nit, 2 recorded or ruled items). Scope: `README.md`, 40 nav pages (39 in nav plus the index; `docs/01_*` redirect excluded as ruled), `docs/assets` (70 figure files).

## Checks run

| Check | Command | Result |
|---|---|---|
| Strict build | `python scripts/docs_build.py` | rc 0, "Documentation built", 0 WARNING lines |
| Form gate | `python scripts/docs_form_gate.py` | "ALL DOCUMENTATION FORM CHECKS PASSED. 12 of 12 checks executed." |
| Docs-form tests | `pytest tests/test_docs_form_gate.py` / `test_docs_user_navigation.py` / `test_documentation_form.py` | 61 passed / 11 passed / 45 passed |
| Figure-form test | `pytest tests/test_figure_form.py` | 1509 passed, 33 xfailed (strict, listed in `AWAITING`) |
| Figure variants | embedded `assets/figures/*.png` vs disk (`comm`) | 70 on disk, 70 embedded, 0 orphans, 0 missing; every embed on 28 pages has one `#only-light` and one `#only-dark` line (counts equal per page) |
| Near-duplicates | `r2_scripts/dup.py` (word 5-gram Jaccard over paragraphs of at least 12 words, 40 pages) | 136 pairs at or above 0.5; 133 are the tutorial template (below), 3 are real |
| Term counts | `r2_scripts/terms.py` (code spans and fences stripped) | see Terms |
| Style scan | `r2_scripts/style.py` (negation, hedge, "doctrine/governance") | 0 "doctrine"/"governance"; negation lines per page 0-21 (references.md 21 is cited titles), hedges 0-3 outside references.md |

## Findings

| # | file:line | Class | Evidence | Blocks? |
|---|---|---|---|---|
| 1 | `docs/quickstart.md:57`, `docs/unit_quality_example.md:13`, `docs/tutorials/00_your_own_file.md` to `10_wavemap.md` (11 pages; e.g. `03_spiking.md:11`) | repetition | The sentence "`examples/` ships in neither the wheel nor the sdist, so this line needs a clone ..." appears word for word on 13 pages (exact sentence match, `dup.py`). Also the 11-page header "The page below is included from the tutorial script; edit the script, not this block." The tutorial pages are a deliberate template, each read standalone. | No. Minor: "each thing said once" read strictly fails; the template reading holds. Fix if wanted: one admonition snippet via `pymdownx.snippets`. |
| 2 | `README.md:43` = `docs/install.md:9`; `docs/index.md:23` | repetition | The Python-version sentence is identical in README and install; index.md says it a third way ("CI tests 3.12, ... "). Three phrasings of one fact. | No. Minor. index.md keeps the pointer to install.md; drop the CI list there. |
| 3 | `README.md` (intro) vs `docs/index.md:9` | repetition | Opening description paragraphs, Jaccard 0.58. README is also the PyPI page, so the copy is expected. | No. Nit. |
| 4 | `docs/reading_nwb.md` figure caption vs `docs/tutorials/01_nwb_basics.md` figure caption | repetition | Captions of the interval-table figure, Jaccard 0.52 ("... of the synthetic session on a time axis" / "... of a synthetic session on a time axis"). Same figure content shown twice. | No. Nit. |
| 5 | H1 of `02_*`, `03_*`, `04_*`, `05_*`, `06_*`, `07_*`, `08_*`, `09_*`, `10_*` ("02. Addressing, Metadata & Ontology") vs the unnumbered H1 of 20 other pages; nav labels drop the numbers | form | 9 pages carry a legacy chapter number in the H1; 20 do not. Nav order runs 02, 06, 04, 05, 07, 08, 09, 03, so the numbers contradict the menu order. Nav label and H1 differ on the same pages ("Spectra & Decibels" vs "04. Power Spectra & Decibels"; "Reading NWB" vs "Reading NWB Data"). Case differs: "Repairing NWB files" (`repairing_nwb.md:1`) vs nav "Repairing NWB Files". `documentation_form.md` F10 numbers H2s of concept pages and says nothing of H1. | No. Minor: "consistently formed" is weakened, no clause plainly broken. Fix: strip numbers from the nine H1s and align nav labels to H1s. |
| 6 | `mkdocs.yml` nav, group "Analyze" | menu order | A reader arrives with a file, then needs: read, inspect, repair damage, analyse. "Artifact Detection & Repair" sits 8th, after Laminar Depth and before Statistics; "Repairing NWB Files" is in "Fix a problem" at the end. The "Tutorials" group, which `docs/index.md:19` tells a newcomer to start with ("Start with the Tutorials"), is the 3rd group after 15 "Analyze" pages; its first page (NWB Basics) is not in "Start". Start itself runs index, install, quickstart, own file, recipes: correct. Look up runs api, specs, references, glossary: correct. | No. Minor: arrival order holds for Start, Fix, Look up; Analyze and Tutorials are ordered by topic rather than arrival. |
| 7 | `docs/vis.md:48`, `:57` | figure | One unsuffixed PNG with a white background; no dark variant. Page says "so on a dark page it shows as a white panel". Ruled: `artifacts/rulings/2026-10-04.md:24-25` (documented light-only; `theme=` waits for Hamm); gated by `LIGHT_ONLY_PAGES` in `scripts/docs_form_gate.py:97`. | No. Ruled exception; the "theme-matched" clause has this one documented gap. Reported so A3 names it. |
| 8 | `tests/test_figure_form.py:778-790` (33 strict xfails) | figure | Every embed fails the mobile-width text-size check (smallest text 5.3 px at 343 px). Recorded in the test with the reason. Not a light/dark matter. | No. Not in the §11 clause text; open for the figure style. |
| 9 | `docs/architecture.md:119,122,170`; `docs/common_mistakes.md:330,336,410`; `docs/errors.md:155`; `docs/08_directed_connectivity_and_information.md:166` | writing (§9) | "X is not Y" forms: "it is not about one dataset's structure", "a default in hiding", "A null finding is an observation, not an error", "The trajectory is not at the origin; there is no trajectory", "The average over no channels is not zero", "`codes` is a jnwb default, not an NWB requirement", "A TE of 0.05 bits is not 0.05 nats and not a percentage". Most carry a content distinction (unit, estimand). Lines 119/122/170 and `common_mistakes.md:330,336` restate rather than inform. | No. Nit (§9 asks for cuts; no page is dominated by it). |
| 10 | `docs/10_operation_specifications.md:118-135` | form | Table cells hold run-on sentences of 40+ words (for example `curate_and_label`, `fuse_laminar_anchors`, `xflip`), partly a restatement of `docs/api.md` signatures. | No. Nit; the table is reference material and the form tests (F12) pass. |

Checked and clean: "doctrine"/"governance" 0 hits.

## Terms (counts over README and docs, prose only; `terms.py`)

The glossary fixes: session/recording, contact/channel/electrode/electrodes table, trial/epoch. Usage matches the glossary in the sampled lines (channel 95, contact 68, electrode 51, trial 92, epoch 19). Candidate pairs:

| Pair | Counts | Verdict |
|---|---|---|
| dB / decibel | "decibel" 24, "dB" 5 | Different roles (unit symbol in formulas vs noun); not an inconsistency |
| PSD / power spectral density / power spectrum | 17 / 6 / 1 | Abbreviation after first use; the single "power spectrum" (`docs/api.md`) is a synonym used once. Nit. |
| cluster permutation / cluster-based | 3 / 4 | "cluster permutation" (`README.md:156`, `tutorials/05_statistics.md:17`) vs "cluster-based" (`07_*`, `api.md`). One concept, two names. Nit. |
| analyze / analyse | 2 / 1 | `docs/architecture.md` uses "analyses" as a noun; verbs are "analyze". No conflict found. |
| neuron / unit / cell | 4 / 178 / 3 | "neuron" appears in `common_mistakes.md:420,424` and `unit_quality_example.md:5` as "single-neuron claim" (the claim the library declines), a deliberate distinction. "cell" is "per-cell count" (`coherence_and_tfr.md:159`, array cell) and "cell type" (`10_wavemap.md:42`). No finding. |
| sampling rate / sample rate / fs | 6 / 0 / 1 | Consistent |
| color / colour | 2 / 0 | Consistent American |

## Not checked

- Rendered pages visually (light and dark): not opened in a browser. Figure variant presence and the form tests were checked; legibility of each PNG in both themes was not reviewed by eye, except `docs/assets/jnwb_vis_sorted_heatmap.png`.
- Interactive figure iframes: the figures site (`hnxj.github.io/jnwb/figures/`) is remote; the message-to-iframe theme sync in `_figure_theme.js` was read, not run.
- Verbosity: the style scan covered all pages; line-by-line reading covered `architecture.md` (first 60 lines), `02_paths_addressing_metadata.md` (first 40), `errors.md`, `common_mistakes.md`, `10_operation_specifications.md`, `08_*` and `00_your_own_file.md` by the scan's matched lines and headings, and not every paragraph of `api.md`, `references.md`, `common_mistakes.md` or `errors.md` end to end (13,000+ words in those four).
- Mermaid diagrams (`architecture.md`): theme follows Material's own palette; not rendered here.
- Whether the numbered H1 (finding 5) is an owner choice: no ruling found in a quick `documentation_form.md` read; not searched in `artifacts/rulings/`.
