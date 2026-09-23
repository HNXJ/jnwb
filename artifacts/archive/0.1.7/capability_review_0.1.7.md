# Capability hypothesis review (0.1.7)

Review-only closure for the three stack items admitted into 0.1.7. No new public
exports. Repository: `dev` at time of review.

---

## 1. `vflip2`

### Evidence searched

| Source | Result |
|---|---|
| Working tree `rg -i vflip` | **1 hit:** `artifacts/todo_stack.md` only |
| `git ls-tree -r HEAD \| rg vflip` | empty |
| Git history | `ae906a4` added `codes/functions/vflip2_mapping.py`; deleted `801544b` in production reorg; never in active `jnwb/` |
| Historical tests | `ae906a4:tests/test_vflip2_mapping.py` (mask coercion, zig-zag bad-channel detection) |
| Historical consumer | `e66981f:scripts/build_channel_layer_mapping.py` → putative layer CSVs |

**Naming:** vFLIP2 = *Vectorized / Frequency-based Laminar Identity Profile* v2. **Not** a vertical
array flip of LFP channels.

### Reconstructed contract (from `ae906a4:codes/functions/vflip2_mapping.py`)

**Input**

| Field | Shape / type | Units / meaning |
|---|---|---|
| `data` | `(n_channels, n_freqs)` float | PSD or power vs frequency (Welch output) |
| `intdist` | scalar | Inter-contact distance (mm); default 0.05 |
| `freqbinsize` | scalar | Hz per frequency bin |
| `fsample` | scalar | Sampling rate (Hz) |
| `valid_channel_mask`, `bad_channel_mask` | `(n_channels,)` bool | Manual QC masks |
| `area_labels` | `(n_channels,)` str | Anatomical segment per contact |
| `orientation` | str | Expected sup/deep orientation (`superficial`, `deep`, `both`) |
| `omega_cut` | scalar | Minimum fit quality to accept segment |
| `auto_bad_channels` | bool | Enable PSD zig-zag neighbor outlier detection |

**Operation (per contiguous segment)**

1. Normalize PSD; optionally flag zig-zag spectral outliers vs ±2 channel neighbors.
2. Mask finite rows, area labels not in `na_area_labels` (`white_matter`, `out_of_brain`, …).
3. Split probe into area-aware candidate segments (`min_segment_channels` ≥ ~8).
4. Search low/high frequency band edges on a fixed spectral-profile grid; find channels
   maximizing low-band vs high-band power (`lowfreqmaxchannel`, `highfreqmaxchannel`).
5. Estimate **crossover channel** (alpha/beta ↔ gamma transition along probe axis); optional
   adaptive refinement within `crossover_search_radius`.
6. Score fit with **omega**; reject segment if below `omega_cut`.
7. Assign laminar labels `sup` / `mid` / `deep` / `na` via `get_laminar_label_vector()`.

**Output (`FlipResults` + label vector)**

| Field | Meaning |
|---|---|
| `crossoverchannel` | Continuous crossover index along probe |
| `lowfreqmaxchannel`, `highfreqmaxchannel` | Band-dominance peak channels |
| `omega`, `goodnessvalue` | Fit acceptance metrics |
| `orientation` | Resolved superficial-vs-deep flip |
| `segment_startchannel`, `segment_endchannel`, `segment_area` | Fitted segment bounds |
| Label vector length `n_channels_total` (default 128) | Per-contact laminar class |

**Failure behavior**

- `ValueError` if mask/area filtering leaves zero valid channels.
- `ValueError` if no contiguous segment is long enough for fitting.
- Channels outside accepted segments or below `omega_cut` → `'na'`.
- Historical omission corpus: ~54% channel coverage; many segments non-converging.

### Active jnwb primitives (related, not equivalent)

| Primitive | Relationship |
|---|---|
| `compute_psd` / `compute_multitaper_psd` | **Upstream input** — produces `(channels, freqs)` only |
| `classify_layer_from_depth` | **Alternative layer claim** — metadata `z` depth threshold (µm), not spectral crossover |
| `voltage_curvature_1d` / `current_source_density_1d` | **Different laminar geometry** — spatial 2nd derivative, not spectral crossover |
| `bipolar_reference` / `laplacian_reference` | Spatial preprocessing only |
| `channel_correlation_matrix` + `bad_channels_from_correlation` | **Different bad-channel geometry** — temporal correlation, not PSD neighbor zig-zag |

**Why not composition today:** crossover search, omega acceptance, area segmentation, and
`sup/mid/deep` labeling are entangled in one ~800-line class. No single jnwb function exposes
crossover or omega; reproducing vFLIP2 requires porting the full algorithm, not wiring existing
exports.

### Decision: **project-specific (downstream-owned)**

- Never promoted to `jnwb/`; lived in pre-split `codes/` and omission-side scripts.
- Bundles **area vocabulary**, segment policy, `na_area_labels`, and method-specific hyperparameters
  (`omega_cut`, spectral-profile grid) — analysis-pipeline concerns, not a minimal array primitive.
- Generic metadata alternative already exists: `classify_layer_from_depth`.
- **Do not** restore the name `vflip2` on the public API. Historical reference:
  `git show ae906a4:codes/functions/vflip2_mapping.py`.

---

## 2. LFP channel QC

### Inventory (measurement vs policy)

| Candidate metric | Classification | jnwb surface |
|---|---|---|
| Detached / uncorrelated contact | **already available** | `channel_correlation_matrix` → `bad_channels_from_correlation` |
| Trial movement / chewing artifact | **already available** | `bad_trials_single_channel` → `consensus_bad_trials` |
| Cross-channel synchrony impulse (within trial) | **already available** | `repair_lfp_trials` detection geometry (repair is separate policy) |
| TFR single-trial power spike | **already available** | `detect_band_outliers` / `repair_band_artifacts` |
| Zero-variance / flat line | **composable** | `np.std(trace)==0` on `(channels, time)` |
| Clipping / amplitude outlier | **composable** | robust z on `max(abs(trace))` — same statistic as `bad_trials_single_channel` amp leg |
| Line noise / harmonic contamination | **composable** | `harmonic_analysis` or `notch_filter` + band power ratios |
| 1/f / broadband noise level | **already available** | `spectral_tilt`, `compute_psd` |
| PSD zig-zag neighbor outlier (vFLIP2 QC) | **composable** | neighbor median deviation on `log10(psd)` rows — ~15 lines on `compute_psd` output; documented in git `ae906a4` `_detect_zigzag_bad_channels` |
| Laminar spatial structure QC | **already available** | `voltage_curvature_1d`, `current_source_density_1d` |
| Impedance thresholding | **study policy** | Read from NWB electrodes table if present; jnwb does not invent thresholds |
| Unit SNR gate | **study policy** | `get_snr_analysis`, `assign_quality_tier` — unit table, not LFP channel metric |
| Session-wide exclusion % caps | **study policy** | Downstream decision on `frac_flagged` / consensus fractions |

### Gap matrix summary

No row classified **missing generic primitive** after inventory. Existing detection covers
correlation-based bad channels, trial consensus, synchrony, and TFR outliers. Residual metrics
are either **composable** from `compute_psd` + numpy or **study policy** (thresholds, exclusion
rules).

### Decision: **already covered + composable — no new exports**

Measurement remains separate from exclusion/repair policy (`artifact_detection` vs
`artifact_repair`). Do not add a generic `channel_qc()` sack.

---

## 3. Channel locality / relation / clustering

### Layer separation check

| Layer | jnwb provides | External compose |
|---|---|---|
| **Physical locality** | `map_peak_channel_to_area`, `classify_layer_from_depth`, `bipolar_reference`, `laplacian_reference`, `voltage_curvature_1d`, CSD | `scipy.spatial.distance.pdist` on NWB `x/y/z` electrode coordinates |
| **Functional relation** | `cross_area_coherence`, `imaginary_coherency`, `granger`, `phase_slope_index`, `transfer_entropy`, MI estimators | — |
| **Cluster assignment** | — (intentionally) | `sklearn.cluster`, `scipy.cluster.hierarchy` on explicit feature/distance matrices |
| **Biological network** | `network_topology`, `directed_network` on **time-series** signals | Graph interpretation is downstream |

`jnwb.jrsa` uses `scipy.spatial.distance` for representational geometry — pattern is: jnwb
computes scientific features/relations; clustering algorithm choice stays outside.

### Missing building blocks?

- **Electrode distance matrix from coordinates:** composable with scipy on NWB metadata; no
  jnwb-specific coordinate frame logic required beyond what `electrode_inventory` already extracts.
- **Combined spatial+functional distance:** would silently merge layers → **do not implement**.
- **Clustering wrapper:** would hide algorithm choice (k, linkage, metric) → **do not implement**.

### Decision: **close without implementation**

Existing connectivity + addressing + scipy/sklearn compose sufficiently. Clustering algorithm
choice is scientifically consequential and belongs in project code once jnwb has produced
explicit relation matrices or coordinate distances.

---

## Validation receipt

```
python scripts/harness_gate.py     → 12/12 PASS (run at review time)
python -m pytest tests/ -q         → 641 passed, 1 skipped (prior checkpoint 9399c14)
rg 'importorskip\("omission' tests/ → empty
```

No code changes required for these three hypotheses.
