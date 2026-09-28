# Figure eye-check, 0.2.7

The recorded eye-check that P-241 (07-01) asks for, covering every figure variant regenerated
for P-240 (07-01) and the critic's follow-ups (F1, F3). Each PNG was flattened onto the page
background its variant is shown on: white (`#ffffff`) for `NAME.png`, and the slate background
(`#1b1b1b`) that `tests/test_figure_form.py` uses for `NAME.dark.png`. The flattened copy was
then viewed.

Generator: `docs/generate_figures.py`, Matplotlib 3.10, on the lane branch after the merge of
dev `5e610000`. A second full run of the generator was byte-identical on all 20 PNGs.

| Variant | sha256 | Seen on its page background |
|---|---|---|
| `fig01_addressing_laminar.png` | `791c2eefec194e8e4178f6e22ce8a0006e98c873f3ab0b95eb01709ce2112441` | White: panel B has no legend box; the red "Boundary (1000 µm)" label sits beside the dashed line in row 1, where the bars stop short of it |
| `fig01_addressing_laminar.dark.png` | `d1d8771b5a6247f7bb14d93726b95a5306c17d5c32962112a79b1fc8ab8f8516` | Slate: same placement; the red label and the light axis text are legible |
| `fig03_onset_fitting.png` | `aa9c905d6eff11fb216de74916ebeec0d8cc9c1d6998ea0fc673ec5a8e45a3f2` | White: the four-row legend is in the lower right, below the risen trace, and clear of the points and both vertical lines |
| `fig03_onset_fitting.dark.png` | `0431d1194646d0ef1e5bfb60eb617519f8df4754807819ffd8615e76ef6b0614` | Slate: same placement, legible. The green ground-truth line is faint on slate but passes the contrast test |
| `fig04_psd_spectral_tilt.png` | `7b1d5b5919264853d0e31c91647c90d79a1c003bd5bd0840d9a65a375da22426` | Byte-identical to the committed copy at `1142ad0e`; the `slope` key changes no pixel |
| `fig04_psd_spectral_tilt.dark.png` | `7293aac7cac45692f0739aa6d95049c648450993871142154ebbfcc3aa43d6ed` | Slate: the legend "Power-law fit: slope=-1.90 (R²=0.52)" is in the lower left and clear of both curves; byte-identical to `1142ad0e` |
| `fig05_complex_tfr_coi.png` | `7406f1e359f91de96f4eef023526fb7c99d564b43332d91c9033325edc5eedb4` | White: panel B's boxed legend sits at top centre, between the two arms of the cone. Its key is the violet dashed line the contour is drawn in, and it does not touch the contour |
| `fig05_complex_tfr_coi.dark.png` | `b717c39e9d49c7fd69bd5d86639814a04fe38eb1d53bc8e7a06f011c1de9f48e` | Slate: same placement; the white text in its dark box reads over the mesh |
| `fig07_population_decoding.png` | `65ffd23e949d611dba7bbb3106a57ca30aa8c958e64dce87f8c96fda2f5eb625` | White: both legends are in the free band above 100% and above 1.0; no text over bars 4-5 or the F1 bar |
| `fig07_population_decoding.dark.png` | `cef44ced6834d552ea8e3e9f2b4d68536958044a42705aa28ef9de1f6791484b` | Slate: same placement; the legend text and the bar outlines are legible |
| `fig10_artifact_repair.png` | `48a8da4720d658fee5a875673dab066dbf2eec3714536b5347a5b5aa39a0e0b5` | White: both legends sit above the traces. The gold "Samples replaced" band covers 180-239 ms, the samples the repair changed, and stops at the trace maximum. The gray envelope is visible |
| `fig10_artifact_repair.dark.png` | `b5096856f5d516b913d7a50e7d7698a42d6bf584a982c59e6256d3209447238f` | Slate: same placement; the gray envelope, the violet repair and the legend text are legible |

The mechanical counterpart is `test_no_legend_covers_the_data` in `tests/test_figure_form.py`. It
reports an intersection between any legend and any line, contour, patch, fill, point cloud or text
in all 20 variants. The one exempt element is a background mesh.
