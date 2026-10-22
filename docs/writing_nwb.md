# Verifying a Written NWB File

`jnwb.verify_nwb` re-reads one written NWB file and reports what it found. It is the
check every jnwb writer runs, public so a caller can re-run it.

```python
import jnwb

rep = jnwb.verify_nwb("out.nwb")
rep = jnwb.verify_nwb("out.nwb", against="src.nwb", report=writer_report)
```

![Standalone checks of a written copy, and the comparison of its recast copy against the source](assets/figures/fig37_verify_written_nwb.png#only-light)
![Standalone checks of a written copy, and the comparison of its recast copy against the source](assets/figures/fig37_verify_written_nwb.dark.png#only-dark)

Synthetic: a written copy of a synthetic session re-read by `jnwb.verify_nwb`: the four standalone checks on the copy (A), and the comparison of the recast copy against its source, with the byte-identical datasets beside the one declared `cast` (B).

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

## Writing a caller-built file

`jnwb.write_nwb` writes a caller-built `NWBFile` to `dst` and reports the write. Its
signature is `write_nwb(nwbfile, *, dst, overwrite=False, verify=True)`, and it returns
a `MutationReport`.

| Refusal | Error | What is left behind |
|---|---|---|
| `nwbfile` is not a `NWBFile` | `TypeError` | nothing written |
| a required field left empty | `MissingRequiredNWBFieldError` | nothing written |
| `dst` exists and `overwrite=False` | `FileExistsError` | nothing written |
| the object fails schema validation before writing | `NWBMutationError` | nothing written |
| a post-write check fails with `verify=True` | `NWBVerificationError` | the file is left in place |

The other error classes, `AmbiguousMappingError`, `UnidentifiableRepairError` and
`UndeclaredUnitError`, subclass `NWBMutationError`. They are reserved for mutation operations
that are not yet in jnwb; `write_nwb` does not raise them.
