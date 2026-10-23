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

The other error classes, `AmbiguousMappingError` and `UndeclaredUnitError`,
subclass `NWBMutationError`. They are reserved for mutation operations
not yet in jnwb; `write_nwb` and `transform_nwb` do not raise them.
`UnidentifiableRepairError`, raised by `repair_nwb` below, subclasses it too.

## Copying a file with declared changes

`jnwb.transform_nwb` copies a file with declared changes and reports the copy.
Signature: `transform_nwb(src, *, dst, keep=None, drop=None, cast=None, compression=None, overwrite=False, verify=True)`; it returns a `MutationReport`.

```python
rep = jnwb.transform_nwb("src.nwb", dst="out.nwb", drop=["units"],
                          cast={"acquisition/raw/data": "float32"})
rep = jnwb.transform_nwb("src.nwb", dst="zip.nwb",
                          cast={"acquisition/raw/data": "float32"},
                          compression={"filter": "gzip", "level": 1, "shuffle": True})
```

`keep` or `drop` (not both) names dataset or group paths; `cast` maps dataset paths
to floating-point dtypes, widening integer or boolean sources only; `compression` is `{"filter": "gzip", "level": 1, "shuffle": True}`
applied to the rewritten datasets, or `None` for the source's own storage. No argument
changes values other than a declared `cast`. The source is never modified.

| Refusal | Error | What is left behind |
|---|---|---|
| a path that opens nothing | `KeyError` | nothing written |
| a group in `cast` | `TypeError` | nothing written |
| `keep` and `drop` together, or a cast on a dropped path | `ValueError` | nothing written |
| an unknown compression filter, key or level | `ValueError` | nothing written |
| `dst` resolving to `src` | `ValueError` | nothing written |
| a cast naming an `*_index` dataset, a cast of an integer or boolean dataset to a narrower or non-floating dtype, or a cast of a float dataset to a non-floating dtype | `TypeError` | nothing written |
| dropping a dataset another kept object references or links to | `NWBMutationError` naming the referrer | nothing written |
| the copy failing schema validation | `NWBMutationError` | nothing written |
| `dst` exists and `overwrite` is False | `FileExistsError` | nothing written |
| a post-write check failing with `verify=True` | `NWBVerificationError` | the file is left in place |

## Making read repairs persistent

`jnwb.repair_nwb` makes the read path's in-memory repairs persistent and reports the
repair. Signature: `repair_nwb(src, *, dst, repairs, overwrite=False, verify=True)`; it
returns a `MutationReport`. `repairs` names from `jnwb.REPAIRS`, the four repairs
the read path applies today.

```python
rep = jnwb.repair_nwb("src.nwb", dst="fixed.nwb", repairs=["units_colnames"])
```

| Repair | Identifiability precondition |
|---|---|
| `squeeze_scalar_attributes` | the schema declares the attribute a scalar |
| `units_colnames` | the data column exists in the units group and is absent from `colnames` |
| `vector_index_types` | the index is `waveform_mean_index` or `spike_amplitudes_index`, its name is its target's name plus `_index`, and the target exists |
| `waveform_index_dtype` | `waveform_mean_index` holds integral values from 0 to 255 |

Two preconditions are stricter than the read: `vector_index_types` needs the target the
name derives to exist, where the read only fixes the target link; `waveform_index_dtype`
needs integral values, where the read casts without asking. A persistent repair can
therefore refuse a file the read accepts.

| Refusal | Error | What is left behind |
|---|---|---|
| a name not in `REPAIRS` | `ValueError` | nothing written |
| a named repair whose precondition does not hold, or that would change nothing | `UnidentifiableRepairError` | nothing written |
| a missing `session_description` | `MissingRequiredNWBFieldError` | nothing written |
| `dst` exists and `overwrite` is False | `FileExistsError` | nothing written |
| a post-write check failing with `verify=True` | `NWBVerificationError` | the file is left in place |

A container-type contradiction is reported in the report's `issues`, never rewritten.
