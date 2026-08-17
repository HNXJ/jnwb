# Figure 4 — leakage-safe omission-identity decoding

Status: `truth_safe_unverified` until the complete-corpus receipt and visual review are available.

The empirical path is:

```text
session_readiness.csv
  -> scripts/compute_omission_identity_leakage_safe.py
  -> cycle-safe cells, folds, held-out predictions, and permutation null
  -> fig04_safe_renderer.py
  -> fig04.svg / fig04.png / svg/fig04_stats.* / svg/fig04_provenance_receipt.json
```

The renderer refuses missing or incomplete leakage-safe artifacts and contains no synthetic
scientific fallback values. Panel A is a task schematic; Panels B–E2 are computed from
persisted artifacts.

## Estimator and leakage control

- Signal: SPK/SUA only; this figure makes no LFP decoding claim.
- Trials: correct P1-aligned trials, with `stimulus_number == 2` as the alignment anchor.
- Slots: p2, p3, and p4 from the canonical omission-identity condition map.
- Features: per-unit spike counts in the omitted-slot window relative to P1.
- Leakage unit: repeated temporal cycle detected from combined A/B/R trial timestamps.
- Cross-validation: leave one complete temporal cycle out.
- Training: class-balanced within each training fold.
- Null: labels permuted within cycle, with folds and cycle-level class counts preserved.
- Seed, permutation count, exclusions, and estimator parameters are recorded in the receipts.
- Unit identity uses `session.get_units(area).index` row positions, not local Kilosort IDs.

The earlier random-CV `_v2` estimate (`0.601284`) remains diagnostic provenance only. It is not
consumed by the renderer and cannot support a frontal decoding claim. The existing
cycle-deconfounded estimate (`0.494627`) is historical evidence; the new complete-corpus
receipt is required before promoting any null or positive result.

## Commands

Smoke test:

```powershell
python scripts/compute_omission_identity_leakage_safe.py `
  --nwb-dir D:/nwb/omission `
  --output-dir outputs/classification/fig04_smoke `
  --limit 1 --permutations 5
```

Complete eligible corpus:

```powershell
python scripts/compute_omission_identity_leakage_safe.py `
  --nwb-dir D:/nwb/omission `
  --output-dir outputs/classification `
  --permutations 1000
python context/figures/fig04_omission_identity_decoding/fig04_omission_identity_decoding.py
```

The complete run must finish before the renderer is used. Its receipt records eligible and
excluded sessions, fold assignments, class balance, estimator parameters, null construction,
Git SHA, platform, and output hashes.

## Acceptance

Figure 4 is not publication-ready until:

1. the complete eligible corpus receipt exists;
2. all panels regenerate after deleting result artifacts and rerunning the documented pipeline;
3. no empirical panel depends on a literal or fallback scientific value;
4. the permutation null uses the same cycle grouping as the CV;
5. the figure provenance receipt maps each panel to its input and estimator;
6. the user visually reviews the regenerated figure;
7. a Labyrinth claim records the final null-compatible or positive result.
