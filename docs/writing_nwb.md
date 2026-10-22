# Verifying a Written NWB File

`jnwb.verify_nwb` re-reads one written NWB file and reports what it found. It is the
check every jnwb writer runs, public so a caller can re-run it.

```python
import jnwb

rep = jnwb.verify_nwb("out.nwb")
rep = jnwb.verify_nwb("out.nwb", against="src.nwb", report=writer_report)
```

Always, `verify_nwb` parses the file through pynwb, runs schema validation, and resolves
every link and object reference. With `against` and the writer's `report` it compares
content, not storage: each dataset the report's applied records do not name is
byte-identical over `n_check` rows (200000 by default), `file_create_date` is ignored,
object references are dereferenced and their targets compared, and scalars are read
whole. Any difference in a dataset the report does not name is reported as unexplained.
An applied record named `cast` declares its paths as dtype casts of the source.
`against` without `report` raises `ValueError`, since without the declared changes every
difference would be unexplained.

A failed check is `ok=False` in the returned `MutationReport`; writers turn it into an
error and leave the file for inspection.
