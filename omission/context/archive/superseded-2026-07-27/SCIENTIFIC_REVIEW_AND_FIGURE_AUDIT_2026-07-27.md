# Scientific review and figure audit

## Overall assessment

The manuscript has a clear central observation: omission-linked single-unit spiking is sparse and weighted toward higher-order cortex, whereas low-frequency LFP modulation is widespread. The figure sequence supports that narrative well: experimental topology (Figures 1-2), response exemplars and census (Figures 3-4), model-based enrichment (Figure 5), field-level dynamics (Figures 6-7), and cross-modal synthesis (Figure 8).

The primary weaknesses were consistency and inferential calibration rather than missing figures. The manuscript mixed ten analysis regions with eleven recording targets, used incompatible alpha/theta definitions in different sections, overstated what observational association and a forest plot establish, and contained a visible internal Figure 3 label error.

## Problems found and action taken

| Issue | Evidence | Revision |
|---|---|---|
| Region-count drift | Text alternated between 10 and 11 areas; Tables 1-2 and the population plots contain 10 analysis regions, while Figure 1 shows 11 labeled recording targets. | Text now distinguishes 11 recording targets from the 10-region analysis census. |
| Band-definition drift | Alpha/theta were reported as 8-12 vs 8-14 Hz and 3-8 vs 4-8 Hz. | Captions and methods-facing text now use theta 4-8, alpha 8-14, beta 14-30, low gamma 30-50, high gamma 50-80 Hz. |
| Figure 3 internal numbering error | The image title read “Figure 2” although it is embedded as Figure 3. | Corrected only that title; traces, panels, shading, and colors were retained. |
| Figure 6 window mismatch | Caption stated -1000 to +1000 ms, while the plotted axis extends to about +4000 ms and the manuscript describes a -1000 to +4000 ms analysis window. | Caption now reports -1000 to +4000 ms and the baseline explicitly. |
| Overclaim in Figure 5 caption | “Primary determinant” is causal/overstrong for an observational mixed-effects association. | Recast as an association supported by the model; causal language removed. |
| Placeholder citations | Discussion contained `[Ref21, Ref26]`. | Replaced with human-readable Bastos et al. (2015) and Miller et al. (2018) citations already present in the reference list. |
| Figure 8 caption drift | Alpha/theta definitions differed from the analysis table and the caption mixed “same census” with an n=10 analysis. | Caption now uses the ten-region analysis and consistent bands. |
| Caption interpretation | Several captions contained conclusion-like language (“establishes,” “demonstrating”). | Captions now describe what is plotted and reserve interpretation for Results/Discussion. |

## Figure-by-figure opinion

1. **Figure 1:** Strong overview, but it is a recording-topology/QC figure rather than the primary 8,597-unit census. The revised caption makes that distinction explicit.
2. **Figure 2:** The paradigm is understandable and the protected epoch shading is useful. The revised caption clarifies the trial proportions and timing without changing the figure.
3. **Figure 3:** Scientifically useful exemplar grid, but dense. The internal title-number error was corrected and the caption now states that these are representative exemplars, not population averages. The underlying raster/PSTH content was not removed.
4. **Figure 4:** The most important census figure. It now explicitly identifies panels a-c and the ten-region gradient, which reduces ambiguity about the composition plot and error bars.
5. **Figure 5:** Appropriate model summary and visually legible. Its interpretation should remain associational; the revised caption makes that limitation explicit.
6. **Figure 6:** Valuable empirical TFR anchor. It should remain tied to the precomputed arrays. The main correction was caption alignment with the actual time window and band definitions.
7. **Figure 7:** Good hierarchy-wide population summary. Its legend/condition notation was too implementation-specific in the caption; the revision uses readable condition names while preserving the protected colors.
8. **Figure 8:** Strong synthesis figure, but it is the most statistically vulnerable because it compresses several bands and cross-modal correlations into one panel. The revised caption makes the analysis-region count and band definitions explicit and avoids implying causal coupling.

## Remaining scientific checks before submission

These require the underlying analysis outputs, not editorial judgment alone:

- Verify that the Figure 8 alpha grand percentage and its per-area values are generated with the same 8-14 Hz definition used in Table 2.
- Confirm whether the reported area-wise correlation uses ten or eleven points and whether the p-values are corrected for the three bandwise correlations.
- Report the exact random-effects structure and convergence diagnostics for the GLMM/LMM in a supplement or analysis repository receipt.
- Replace the future “will be deposited” data-availability statement with a DOI/accession before submission.
- Check the manuscript’s reference numbering and DOI metadata against the final bibliography export.

## Follow-up review integration

The supplied GPT-5.5 review independently converges on the same remaining priorities: fix the malformed simultaneous-recording sentence, improve Figure 2 balance, tighten Figure 5 whitespace, integrate Figure 6 more strongly, and complete a final typography/reference proof. The malformed sentence has now been corrected in the revised DOCX.

I did not regenerate Figure 6 from `scripts/build_clean_publication_figures.py`: that legacy script contains synthetic placeholder construction and would violate the empirical-TFR guardrail. Any Figure 6 aesthetic redesign must be made in the empirical-array plotting path and re-audited against `D:/workspace/data/tfr_arrays/`.

## Deliverables

- Revised manuscript: `context/omission-2026-manuscript-master-scientific-revision.docx`
- Figure 3 corrected asset: `context/figure_03_spiking_exemplars_revised.png`
- Editable figure sources: `context/draft-assets/figure_01_*.svg` through `figure_08_*.svg` (all eight primary figures); pair hashes and dimensions are recorded in `context/figure_asset_manifest_2026-07-27.json`.
- Labyrinth review checkpoint: `artifacts/.lab/scientific_figure_svg_labyrinth_review_20260727.json`
- Original manuscript preserved unchanged: `context/omission-2026-manuscript-master.docx`

The latest review prompted one additional low-risk change: Figure 3 now uses the concise reader-facing title “Representative raster and firing-rate profiles.” Exact-pulse matching and causal exponential smoothing remain documented in the caption, so method information was relocated rather than discarded. The 12-panel hierarchy and Figure 2/6/7 redesign recommendations remain open source-level design work.

The final cross-layer audit found and corrected a real Figure 8 drift: Table 2 sums to 5,816 alpha-modulated channels (66.58%), not 5,635 (64.50%). Figure 8’s visible alpha/theta definitions were also corrected to alpha 8-14 Hz and theta 4-8 Hz in the PNG, SVG, caption, and embedded DOCX image.

## Verification limitation

The bundled DOCX renderer could not start because the required office conversion executable is unavailable in this environment. Structural verification passed (8 inline figures; captions ordered Figure 1 through Figure 8; Figure 3 embedded image hash matches the corrected asset), and the corrected Figure 3 PNG was visually inspected directly. A final Word/PDF render should be run before replacing the master PDF/package.
