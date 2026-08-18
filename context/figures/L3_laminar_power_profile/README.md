# L3 — laminar power profile (depth x frequency heatmap + sup/deep contrast index)

Reads `canonical_pooling_method` from [L0](../L0_pooling_reconciliation/L0_stats.json). Reuses
**precomputed TFR arrays** (`oa.paths.tfr_dir()`, `{session}-{probe}-{area}-{condition}.npz`,
discovered this run — 970 files already on disk, full per-channel depth resolution, no need to
recompute from raw LFP) and `outputs/layers/channel_layers_all.csv`'s labelled sup/deep channel
calls (channel_idx uses the same local-probe-index convention as the TFR files' `channels` array
— directly joinable).

**Top row**: depth x frequency dB heatmap, one representative (most layer-labelled-channels)
session per area, real per-channel resolution (not pooled — this IS the depth axis), stim
condition, log-last within each channel.

**Bottom**: superficial − deep contrast index per band per area, stim (solid) vs omission
(hatched), session-bootstrap 95% CI (same construction as L2 — only sessions with ≥1 labelled
sup AND ≥1 labelled deep channel are used; V2 has only 1 such session, giving a degenerate
zero-width CI, shown honestly rather than hidden).

**Log-last applied at three nested levels** here (channel-within-group pooling, band-frequency
pooling, then the final baseline division/log) — see module docstring for why skipping any one
of these would reintroduce the exact log-averaging bias `omission-signal` S1 warns about.

**Qualitative result**: heatmaps show a real, depth-localized broadband power increase in
V1/V2/MT/MST (concentrated in specific channel bands, not uniform across depth — i.e. genuinely
laminar, not just an area-wide effect), and a broadband decrease across most channels in FEF —
consistent with L1/L2's finding there. The bar chart shows **wide, mostly zero-crossing CIs** for
most band/area/condition cells — this run does **not** establish the canonical
superficial-gamma/deep-beta FF/FB signature the spec references as a confirmed corpus finding;
it reports the contrast index and its uncertainty honestly. A few cells have both a sizeable
point estimate and a CI that excludes zero (e.g. FEF beta/omission, FEF high_gamma/stim) — worth
a closer per-cell look before any general FF/FB claim, not before.

**Known inefficiency, not yet fixed**: `group_band_db()` is called once per band, each call
reloading the same session's `.npz` from disk — 5x redundant I/O per session/condition. Real run
took 31m46s. Fix (cache the loaded `power`/`channels` arrays per session/condition, compute all
5 bands from the one in-memory load) is a straightforward follow-up, not done in this pass since
the output is already correct, just slower to reproduce than necessary.

Run `python L3_laminar_power_profile.py --test` first — synthetic profile with a known
superficial-gamma / deep-beta signature baked in; the contrast index must recover the correct
sign for both. Also caught and fixed a real numpy bug during test authoring: chained
boolean-fancy indexing (`arr[a][b][c] *= x`) silently mutates a copy, not the original array —
see the test's own comment.

Outputs: `L3.svg` / `L3.png` / `L3.pdf`, `L3_stats.json`, `L3_manifest.json`.
