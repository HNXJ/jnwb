# Final handout for the next agent

**Project:** Omission / `jnwb` manuscript and figure production  
**User:** Hamm  
**Date:** 2026-07-27  
**Working directory:** `D:/workspace/omission`

## Current state

The manuscript is in a strong editorial state. The central thesis is locked:

> Visual omission recruits sparse higher-order spiking while broadly perturbing low-frequency cortical state.

The current working manuscript is:

`context/omission-2026-manuscript-master-scientific-revision.docx`

The original master remains preserved at:

`context/omission-2026-manuscript-master.docx`

Do not overwrite the original unless Hamm explicitly requests it.

## Verified figure state

The manuscript contains eight inline figures in strict order:

`Figure 1 -> Figure 2 -> Figure 3 -> Figure 4 -> Figure 5 -> Figure 6 -> Figure 7 -> Figure 8`

All eight primary figures have editable SVG counterparts and PNG exports under:

`context/draft-assets/figure_01_*.{png,svg}` through `figure_08_*.{png,svg}`

The pair manifest is:

`context/figure_asset_manifest_2026-07-27.json`

Important recent corrections:

- Figure 3 internal title corrected from “Figure 2” to “Figure 3.”
- Figure 3 title shortened to “Representative raster and firing-rate profiles.” Exact-pulse matching and causal exponential smoothing remain in the caption.
- Figure 8 alpha drift corrected across PNG, SVG, caption, and embedded DOCX image: **5,816/8,736 = 66.58%**, not 5,635/8,736 = 64.50%.
- Figure 8 visible frequency labels standardized to alpha **8-14 Hz** and theta **4-8 Hz**.
- Figure 6 remains tied to empirical precomputed TFR arrays; do not replace it with synthetic data.

## Protected invariants

Do not change these without explicit instruction from Hamm:

- Existing condition colors: standard gray, omission red, random control teal.
- Epoch shading order and colors: yellow -> purple -> green -> blue.
- Figure insertion order.
- Figure 6 empirical TFR source data in `D:/workspace/data/tfr_arrays/`.
- Primary census: 8,597 units; O+ = 421/8,597 = 4.90%.
- LFP census: 8,736 channels; beta modulation = 6,771/8,736 = 77.51%.
- GLMM headline result: OR = 3.08, 95% CI [2.51, 3.78], z = 10.726, p = 7.25e-27.
- Ten analysis regions versus eleven labeled recording targets.
- Canonical bands: theta 4-8 Hz, alpha 8-14 Hz, beta 14-30 Hz, low gamma 30-50 Hz, high gamma 50-80 Hz.

## Scientific/editorial decisions already made

- Captions are descriptive and avoid causal overclaiming.
- Figure 5 describes association, not causal determination.
- Discussion uses “consistent with” and explicitly states that area-wise correlations do not establish causal direction.
- Results headings are declarative scientific statements.
- Figure 1 is clarified as a recording-topology/QC subset, not the primary 8,597-unit census.
- Figure 3 is explicitly described as representative exemplars, not population averages.
- Placeholder citations `[Ref21, Ref26]` were replaced in the revised manuscript.
- The malformed Introduction sentence was fixed to: “Because SPK, MUAe, and LFP were recorded simultaneously...”

## Remaining work, in priority order

1. Run a final Word/LibreOffice render of the revised DOCX and visually inspect every page.
2. If desired, perform a source-level design pass on Figures 2, 5, 6, and 7:
   - Figure 2: enlarge or rebalance the right trace/PSTH panel.
   - Figure 5: tighten horizontal plotting margins.
   - Figure 6: integrate the four empirical panels into a more unified composition.
   - Figure 7: reduce excess vertical whitespace.
3. Do not use `scripts/build_clean_publication_figures.py` to regenerate Figure 6; that legacy script contains synthetic placeholder construction. Any Figure 6 redesign must load the empirical arrays and preserve their provenance.
4. Verify Figure 8 alpha percentages and the multiplicity treatment of the three bandwise correlations from the underlying analysis receipt.
5. Add GLMM convergence diagnostics to the supplement or repository receipt if available.
6. Before submission, replace the future data-deposition language with final Zenodo/OSF accessions.
7. Perform a final bibliography audit: DOI formatting, journal titles, italics, and reference numbering.

## Verification commands

Use the bundled Python runtime when available:

```powershell
$py = 'C:\Users\nejath\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

# Verify figure-caption order and key drift strings
& $py -c "import docx,re; d=docx.Document(r'D:\workspace\omission\context\omission-2026-manuscript-master-scientific-revision.docx'); print([re.match(r'Figure (\\d+)',p.text).group(1) for p in d.paragraphs if re.match(r'Figure \\d+',p.text)])"

# Verify alpha arithmetic
& $py -c "vals=[714,605,624,676,507,338,522,343,727,760]; print(sum(vals),sum(vals)/8736*100)"

# Audit embedded image placement
& $py 'C:\Users\nejath\.codex\plugins\cache\openai-primary-runtime\documents\26.727.11326\skills\documents\scripts\images_audit.py' 'D:\workspace\omission\context\omission-2026-manuscript-master-scientific-revision.docx'
```

Expected order output is `['1','2','3','4','5','6','7','8']`; expected alpha arithmetic is `5816 66.575...`.

## Rendering limitation

The packaged DOCX renderer previously failed because the required office conversion executable was unavailable. Do not claim final PDF/layout approval until a functioning Word or LibreOffice render has been run and inspected. Direct inspection of the corrected Figure 3 and Figure 8 PNGs has passed.

## Labyrinth state

Latest relevant checkpoint:

`artifacts/.lab/scientific_figure_svg_labyrinth_review_20260727.json`

The Labyrinth audit found 99 schema-v3 JSON nodes, 180 legacy/missing-schema JSON files, and a zero-byte `artifacts/.lab/labyrinth.db`. Do not mass-migrate or initialize the ledger without a deterministic migration/validation receipt; preserve historical state under the Conservation rule.

The scientific review and figure audit is:

`context/SCIENTIFIC_REVIEW_AND_FIGURE_AUDIT_2026-07-27.md`

## Operating rules for the next agent

- Address the user as **Hamm**.
- Read `.agents/AGENTS.md`, global `C:/Users/nejath/.gemini/config/AGENTS.md`, `CLAUDE.md`, and the relevant `.lab` nodes before acting.
- Record a Labyrinth delta before finishing the turn.
- Separate observed facts from inference.
- No receipt, no claim.
- Preserve existing user changes and do not commit/push unless Hamm asks.
- Prefer reversible outputs and keep the original master manuscript intact.
