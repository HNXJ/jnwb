### Result records

- `jnwb.Result(question, statistics, provenance, lineage)`: An immutable analysis output that
  carries its question, provenance and lineage; it cannot be built without all four.
  `to_dict()` returns a plain nested `dict` and converts no value, so `json.dumps` of NumPy
  statistics needs a hook such as `lambda o: o.tolist()`.
- `jnwb.Provenance(software_version, backend, timestamp, random_seed, git_commit, parameters, environment)`:
  What ran. `jnwb_version` and `jnwb_path` are read from the executing package and cannot be
  passed; `software_version` is the caller's claim, and `version_claim_matches_execution` says
  whether the two agree.
- `jnwb.Lineage(source_type, source_id, parents, operation)`: Where an output came from: its
  source, the identifiers of its parents and the operation that made it.
