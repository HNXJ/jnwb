# Delegation test handoff (0.1.7)

Removed from `jnwb/tests/` — these assert that `omission.jnwb_ext.*` re-exports `jnwb`
objects. That contract is **omission-owned**; the jnwb suite must pass with `omission/`
absent (CI has only jnwb).

| Removed test (jnwb) | omission target module | jnwb symbols checked |
|---|---|---|
| `test_connectivity.py::test_omission_reexports_same_objects` | `omission` top-level | `granger`, `phase_slope_index`, `transfer_entropy` |
| `test_spectral.py::TestCanonicalBands::test_connectivity_reexports_same_object` | `omission.jnwb_ext.connectivity` | `CANONICAL_BANDS` |
| `test_spiking.py::test_omission_reexports_same_objects` | `omission` top-level | spiking exports |
| `test_metadata.py::test_omission_unit_inclusion_delegates_to_jnwb` | `omission.jnwb_ext.unit_inclusion` | `filter_by_criteria` path via inclusion |
| `test_metadata.py::test_omission_functions_delegates_to_jnwb` | `omission.jnwb_ext.functions` | metadata helpers |
| `test_metadata.py::test_omission_diagnostics_delegates_to_jnwb` | `omission.jnwb_ext.diagnostics` | `audit_units`, `audit_electrodes` |
| `test_statistics.py` (4 delegation tests) | `unit_inclusion`, `unit_classification`, `omission_identity`, `functions` | statistics primitives |
| `test_decoding.py` (2 delegation tests) | `decoding`, `structured_identity` | decoding / fold helpers |
| `test_viz.py::test_omission_viz_delegates_to_jnwb` | `omission.jnwb_ext.viz` | viz helpers |
| `test_permutation.py::test_omission_structured_identity_delegates` | `omission.jnwb_ext.structured_identity` | `build_permutation_plan` |

Suggested omission-side home: `omission/tests/test_jnwb_delegation.py` (single module mirroring
the removed tests). Filing tracked under unversioned stack item (expert feedback register).
