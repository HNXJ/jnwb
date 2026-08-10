---
name: nwb-analysis-forms
description: |
  Comprehensive NWB analysis forms and pipelines in the omission project.
  Includes single-unit rasters, multi-channel LFP power/TFR bands, layer-wise spectrolaminar motifs,
  directional spectral Granger networks, population trajectory PCA (SVD), and SVM population decoding.
---

# NWB Analysis Forms & Pipelines

## 1. Single-Unit Raster Suite
Generates aligned spike rasters, PSTH, and ACG for a neuron.
```python
import jnwb as oa
session = oa.read(oa.paths.nwb_dir() / "sub-C31o_ses-230630_rec.nwb")
res = session.raster_suite(unit_id=2.0, condition=None, phase=2)
# Saves figures using Madelane Golden dark theme
res["figure"].savefig("outputs/task_01_raster.png", bbox_inches='tight')
```

## 2. 2D Log-Frequency TFR Spectrograms
Computes and plots baseline-normalized power spectrograms across theta, alpha, beta, and gamma bands.
```python
# Plots TFR power for a specific brain area and condition
session.plot_tfr(area="PFC", condition="AAXB", phase=3)
```

## 3. Layer-Wise Spectrolaminar Motifs
Identifies superficial and deep layer spectral power dynamics across visual hierarchies.
```python
# Computes layer-wise power (superficial vs deep)
session.spectrolaminar_motif(area="V4", condition="AAAB")
```

## 4. Bivariate Spectral Granger Causality
Computes directional lead-lag Granger causality between two continuous signals
(e.g. two LFP traces or two firing-rate time series) — takes raw arrays, not a
session/area pair. Returns residual diagnostics (Ljung-Box + ADF-like flag);
do not interpret GC as biological directionality when diagnostics warn.
```python
from jnwb.connectivity import granger_causality
# signal1, signal2 are 1D np.ndarray time series (same session/trial, two areas or two units)
gc_results = granger_causality(signal1, signal2, order="auto", device="cpu", criterion="aic")
# gc_results['F_2_to_1'], gc_results['F_1_to_2'], plus residual diagnostics
```

## 5. Population Trajectory PCA (GPU-Accelerated)
Performs PCA trajectory analysis of population activity using PyTorch SVD.
Requires an `epochs_df` (a DataFrame of trial onsets, e.g. from
`session.get_epochs(...)`) — GPU path uses PyTorch and needs
`torch.cuda.is_available()`; falls back to CPU otherwise.
```python
from jnwb.trajectory import compute_population_trajectory
epochs_df = session.get_epochs(condition="AAAB", phase=2, correct_only=True)
traj_results = compute_population_trajectory(
    session, area="PFC", epochs_df=epochs_df,
    time_window_ms=(-1000.0, 2000.0), bin_size_ms=20.0, n_components=3,
)
# traj_results['trajectory'], ['explained_variance'], ['unit_ids'], ['bin_centers']

# For PCA on an arbitrary matrix (not a trajectory), use the standalone helper:
from jnwb.gpu_pca import gpu_pca
# matrix is 2D (n_samples, n_features); returns a 3-tuple
projections, components, explained_variance_ratio = gpu_pca(matrix, n_components=3)
```

## 6. SVM Population Decoding
Trains linear SVM classifiers (nested CV) to predict stimulus identity or
omission presence from population activity. Returns `accuracy`, `f1`, `auc`,
and `majority_baseline_accuracy` (compare `accuracy` against the baseline to
check the classifier beats chance/class-imbalance, not just tracks it).
```python
from jnwb.decoding import decode_stimulus_identity, decode_omission_presence
# Two conditions, e.g. AAAB vs BBBA
dec_results = decode_stimulus_identity(session, area="PFC", condition_pairs=("AAAB", "BBBA"))
# Or specifically standard-vs-omission (thin wrapper around decode_stimulus_identity)
om_results = decode_omission_presence(session, area="PFC", standard_condition="AAAB", omission_condition="AAXB")
```

## 7. Omitted-identity decoding (`jnwb.omission_identity`)

Decodes *which* stimulus was omitted (not merely that one was). **Start with
`scripts/compute_omission_identity_leakage_safe.py`** (SPK/SUA, leave-one-temporal-cycle-out CV,
in-fold class balancing, within-cycle-exchangeable permutation null) — it is the current,
validated pipeline (2026-08-10, `artifacts/.lab/agent-harness-audit-20260810.json`) and the
source of the project's actual headline result (flattened omission-identity decoding is
chance-compatible under grouped CV; presented-stimulus identity is the positive control).
`jnwb.omission_identity.decode_identity_cycle_deconfound` (leave-one-cycle-out, per-cycle
mean-centered) is the other validated path, used by
`scripts/compute_omission_identity_cycle_deconfound_v3.py`.

```python
from jnwb.omission_identity import (
    OMISSION_IDENTITY_CONDITIONS,
    decode_identity_cycle_deconfound,   # VALID: leave-one-cycle-out, per-cycle mean-centered
    detect_trial_cycles,                # real cluster boundaries from start_time gaps
)
```

**`decode_omission_identity_slot` and `decode_omission_identity_full` are
`scientific_status = "invalid_for_inference"`** (marked in their own docstrings) — both use
ungrouped/random CV (`StratifiedKFold(shuffle=True)` or a bare integer `cv=`) that lets
same-cycle trials leak across train/test on this corpus's repeated-cycle structure. Their only
live callers, `scripts/compute_omission_identity_encoding.py` and `_v2.py`, are quarantined
under `scripts/historical/confounded/` for the same reason (12 decoding scripts total —
`tests/test_quarantine_enforcement.py` blocks any live import). Do not import or call either
function for a current result.

**Label construction: use `jnwb.trial_ontology`, not ad hoc condition-string parsing.**
`jnwb.trial_ontology.parse_condition(code)` / `build_trial_ontology(session, ...)` derive
`sequence_family`, `omission_position`, `preceding_identity`, `expected_identity`, and
`presented_identity` from the 12 canonical condition codes in one place (unit-tested against all
12, including both p4 A/B directions). Parsing `"AXAB"`-style strings by hand in a new script is
exactly how the 2026-08-06 p4 A/B label swap happened (see
`jnwb/omission_identity.py:37-44` — every p4 number computed before that fix was unreliable) —
don't repeat it.

```python
from jnwb.trial_ontology import build_trial_ontology, parse_condition, CONDITION_ONTOLOGY
onto = parse_condition("AAAX")  # {'sequence_family': 'A', 'omission_position': 'p4',
                                 #  'expected_identity': 'B', 'preceding_identity': 'A', ...}
table = build_trial_ontology(session, slot_keys=("p2", "p3", "p4"))
```

**Three footguns, all documented in the module/primitive source:**

1. **Window choice can leak a real stimulus.** In every omission slot the *preceding*
   presentation physically differs between the A and B conditions. Any window containing it
   decodes a presented stimulus, not an omitted one. Only the `px` window contains no differing
   physical stimulus. See `artifacts/.lab/p-d-px-d-window-stimulus-leak-20260807.json`.
2. **Split scheme changes the answer.** Random-CV and chronological/leave-one-cycle-out splits
   disagree systematically on this corpus — the random split runs high. Report which was used.
   `detect_trial_cycles` exists because `task_block_number` reuses labels across repeats and
   *looks* contiguous when it is not.
3. **The permutation null must respect the same grouping as the CV fold scheme.** Use
   `jnwb.permutation.permute_labels(y, groups=cycles, scheme="within_group", rng=...)` for any
   null on cycle-grouped data — never a bare `rng.permutation(y)`. This is not theoretical:
   `decode_identity_cycle_deconfound`'s null shipped exactly this bug (grouped LOCO folds
   compared against an ungrouped global-permutation null) until fixed 2026-08-10; see
   `tests/test_permutation_lint.py`, which fails if a bare call reappears in this module.

## 8. Structured 2D decoders — bilinear and NAM

Alternatives to flattening an (N × T) trial into a vector before PCA, which destroys laminar
topology and temporal continuity.

```python
from jnwb.bilinear import BilinearLogisticRegression
# W = sum_k u_k v_k^T -- separable spatial (u) and temporal (v) filters
clf = BilinearLogisticRegression(rank=2, C=1.0, random_state=0)
clf.fit(X, y)          # X: (n_trials, N, T)
clf.n_parameters()     # rank*(N+T) vs the flattened N*T
```

Objective is biconvex, not jointly convex — the solution depends on the seeded init of `V` and
converges to a local optimum. Fix `random_state` and say so.

```python
from jnwb.nam import LaminarNAM, train_nam, unit_importance, predict
model = LaminarNAM(num_units=N, time_samples=T, n_classes=3)
train_nam(model, X_tr, y_tr, X_val, y_val, device)
imp = unit_importance(model, X, device)   # per-unit attribution
```

Per-unit attribution is the point of the NAM — it is what makes unit pruning testable. Select
any prune level on a validation split, never on test.

## Minimal Pipeline Execution Recipes

### 1. Running GPU-Accelerated Population Trajectory (PCA)
```python
import jnwb as oa
from jnwb.trajectory import compute_population_trajectory

# Load session and get visual epochs
session = oa.read(oa.paths.nwb_dir() / "sub-C31o_ses-230823_rec.nwb")
epochs_df = session.get_epochs(condition="RRRR", phase=2, correct_only=True)

# Run PCA trajectory (automatically leverages GPU/CUDA if PyTorch detects it)
traj = compute_population_trajectory(
    session,
    area="FEF",
    epochs_df=epochs_df,
    time_window_ms=(-500.0, 1500.0),
    bin_size_ms=10.0,
    n_components=3
)

print("Trajectory shape (times x components):", traj["trajectory"].shape)
print("Explained variance:", traj["explained_variance"])
```

### 2. SVM Population Decoding Pipeline (Nested CV)
```python
import jnwb as oa
from jnwb.decoding import decode_omission_presence

session = oa.read(oa.paths.nwb_dir() / "sub-C31o_ses-230823_rec.nwb")

# Train linear SVM model to classify standard vs. omission presence
results = decode_omission_presence(
    session,
    area="FEF",
    standard_condition="AAAB",
    omission_condition="AAXB"
)

print("Classification Accuracy:", results["accuracy"])
print("Majority Baseline Accuracy:", results["majority_baseline_accuracy"])
print("F1 Score:", results["f1"])
```
