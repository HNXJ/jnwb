- `jnwb.inspect` reports each column's stored NWB `description` under a new `description` key
  in every column record of `interval_tables`, `electrodes` and `units`, from a path and from an
  in-memory `NWBFile` alike. A description stored empty reads `""`; a column that stores none,
  such as `id`, reads `None`. No existing key changes.
