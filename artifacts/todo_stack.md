# TODO stack

Remaining work only. Finished RG items from the final independent audit are deleted here;
evidence lives in `artifacts/independent_audit_0.1.7_final.md`, `CHANGELOG.md`, and git.

# 0.1.7 (post–final audit RG — commit pending Hamm review)

- Commit and push validated RG diff from final audit repairs.
- Re-run `python scripts/release_gate.py` on committed SHA before 0.1.7 version bump.

# 0.1.7 (justified debt / optional)

- jRSA `align='dtw'` → raise when `dtw-python` missing instead of silent downsample fallback.
- Neutralize subject-ID / promotion provenance strings in `compression.py`, `onset_fitting.py`,
  `spectral.py` docstrings (Gate 6 optional follow-up).
- Extend `jnwb-lfp-spectral` skill routing for `band_power`, `aggregate_to_db`, core filters.
- Wire `release_gate.py` into CI or document as mandatory human gate only (policy choice).

# Before 1.0

- Replace example-based estimator coverage with analytic/property-based tests.

# Unversioned

- File omission-side expert-feedback items in the omission repository.
- Four more notebooks under `examples/notebooks/`.
