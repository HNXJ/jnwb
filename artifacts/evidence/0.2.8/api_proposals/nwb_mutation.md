# Proposal: a public NWB mutation API

The minimal base of 07-21: an operation set with signatures and refusals, for Hamm to rule
before any code. Written 2026-09-29 against `57094a1a`. Nothing here is implemented.

## Where it starts

| Observed at `57094a1a` | Source |
|---|---|
| The only public writer is `compress_fp32(src, dst=None, *, drop_convolved, verify, n_check, overwrite, select)`: a float32 cast plus chunking and compression, source never modified, `select=` required, output re-read by `verify_roundtrip` | `jnwb/compression.py` |
| `read_nwb` and `nwb_read_io` repair malformed files in memory only, while a jnwb read is active: squeezed length-1 attributes, units `colnames` missing their data columns, `VectorIndex` type and target on `waveform_mean_index` and `spike_amplitudes_index`, `waveform_mean_index` cast to int64. A missing `session_description` is refused unless the caller waives it | `jnwb/nwb_io.py` `_repair_builder` |
| `nwb_read_io` refuses every mode but `"r"` | ruled 2026-09-23 |
| No export validates, writes, converts, upgrades or verifies an NWB file | `jnwb.__all__` |
| pynwb 3.1.3 and hdmf 4.3.1 are installed; `pynwb.validate` exists; NWB Inspector is not installed | this machine |

## Bounds every operation inherits

These are the rows of `artifacts/fact_stack.md` the set must hold, not new rules.

| Fact | What it forces on every signature below |
|---|---|
| D2, `mutation categories` | each operation carries exactly one of the eight categories; the table below uses all eight, one each |
| D4 | a repair runs only where the intended representation is identifiable; each repair is named and has its own identifiability test |
| D5 | ambiguity is detected and reported through an exception or a report entry, never resolved |
| D6, D7, D8 | no argument has a default that supplies condition meaning, anatomy, a unit or trial semantics; such a value is a required caller input or the operation refuses |
| D9 | no operation picks among plausible mappings: two candidates raise |
| B1 | nothing imports from a project; no corpus vocabulary in any default |
| goal 4 | a required field is never filled with a plausible value; the existing `MissingRequiredNWBFieldError` and `allow_missing` waiver are the one mechanism |
| K4 | the report extends `Provenance` and `Lineage` instead of defining a receipt of its own |

Common to every writer:

- `src` is never modified. `dst` is required and keyword-only; `dst == src` (after resolving)
  raises. An existing `dst` raises unless `overwrite=True`.
- `verify=True` is the default and re-reads `dst` through `verify_nwb`; a failed check raises
  `NWBVerificationError` and leaves `dst` for inspection, as `compress_fp32` does.
- Every call returns a `MutationReport`.

```python
@dataclass(frozen=True)
class MutationReport:
    category: str                 # one value of the fact stack's `mutation categories`
    src: Optional[str]            # None for write_nwb and convert_to_nwb
    dst: Optional[str]            # None for validate_nwb and verify_nwb
    src_sha256: Optional[str]
    dst_sha256: Optional[str]
    applied: Tuple[str, ...]      # named operations, in order
    checks: Tuple[Check, ...]     # (name, ok, detail); verify_nwb's output
    issues: Tuple[Issue, ...]     # (severity, location, message); validate_nwb's output
    waived: Tuple[str, ...]       # required fields the caller waived, as read_nwb records them
    provenance: Provenance        # jnwb version and path observed, pynwb/hdmf/schema versions in `environment`
    lineage: Lineage              # source_type="NWBFile", source_id=src_sha256, operation=category
    ok: bool
```

Exceptions, all under one new base `NWBMutationError`: `NWBVerificationError`,
`AmbiguousMappingError`, `UnidentifiableRepairError`, `UndeclaredUnitError`; the existing
`MissingRequiredNWBFieldError`, `AmbiguousLayoutError`, `AmbiguousAcquisitionError` and
`AmbiguousIntervalTableError` are raised where they already apply.

## The operation set

| # | Category | Operation |
|---|---|---|
| M1 | validate | `validate_nwb` |
| M2 | write or create | `write_nwb` |
| M3 | copy or transform | `transform_nwb` (and `compress_fp32`, tagged, unchanged) |
| M4 | convert to NWB | `convert_to_nwb` |
| M5 | structural repair | `repair_nwb` |
| M6 | normalize declared units or layouts | `normalize_nwb` |
| M7 | upgrade representation | `upgrade_nwb` |
| M8 | verify written output | `verify_nwb` |

The packet named six (validate, write, transform, convert, structural repair, verified output);
the fact stack's constant has eight, so M6 and M7 are proposed as well and may be ruled out
separately.

### M1 `validate_nwb`

```python
jnwb.validate_nwb(path, *, checks=("schema",), allow_missing=None) -> MutationReport
```

Reads only. `checks="schema"` runs `pynwb.validate`; `"readable"` opens the file through
`read_nwb` and reports each in-memory repair jnwb applied as an issue naming the `repair_nwb`
repair that would make it persistent (the read path records only squeezed attributes and waivers
today, so the other three repairs would have to record themselves); `"inspector"` runs NWB Inspector if installed.

| Refuses | How |
|---|---|
| an unknown check name | `ValueError` |
| `"inspector"` without NWB Inspector | `ImportError` naming the extra; never a silent skip |
| nothing else | a finding is an `issues` entry, never a repair |

### M2 `write_nwb`

```python
jnwb.write_nwb(nwbfile: pynwb.NWBFile, *, dst, overwrite=False, verify=True) -> MutationReport
```

Writes an `NWBFile` the caller built. jnwb adds no content: the caller's pynwb objects carry
every value, unit and region.

| Refuses | How |
|---|---|
| a file that fails schema validation before writing | `NWBMutationError` with the issues; nothing written |
| a `session_description` or other required field left empty by the caller | `MissingRequiredNWBFieldError` |
| `dst` exists, `overwrite=False` | `FileExistsError` |

### M3 `transform_nwb`

```python
jnwb.transform_nwb(src, *, dst, keep=None, drop=None, cast=None, compression=None,
                   overwrite=False, verify=True) -> MutationReport
```

A copy with declared changes: `keep` or `drop` (not both) as dataset or group paths; `cast` as
`{path: dtype}`; `compression` as `{"filter": "gzip", "level": 1, "shuffle": True}` or `None` for
the source's own. `compress_fp32` stays as it is and is recorded as this category.

| Refuses | How |
|---|---|
| a path that opens nothing, or a group in `cast` | raises before writing, as `compress_fp32` does for `select=` |
| dropping a dataset another object references or links to, unless the referrer is dropped too | `NWBMutationError` naming the referrer |
| a cast to a narrower or non-floating dtype of an integer, boolean or index dataset | `TypeError` |
| a change to values other than a declared `cast` | not offered: there is no argument for it |

### M4 `convert_to_nwb`

```python
jnwb.convert_to_nwb(spec: ConversionSpec, *, dst, overwrite=False, verify=True) -> MutationReport

@dataclass(frozen=True)
class ConversionSpec:
    session_description: str                  # required, no default
    session_start_time: datetime              # required, timezone-aware
    identifier: str                           # required
    series: Sequence[SeriesSpec]              # required, at least one

@dataclass(frozen=True)
class SeriesSpec:
    name: str
    data: ArrayLike
    neurodata_type: str                       # "ElectricalSeries", "TimeSeries", ...
    unit: str                                 # required: never inferred
    time_axis: int                            # required: layout is declared, never guessed
    rate_hz: Optional[float] = None           # exactly one of rate_hz, timestamps_s
    timestamps_s: Optional[ArrayLike] = None
    starting_time_s: float = 0.0
    electrodes: Optional[ElectrodeSpec] = None  # required for ElectricalSeries
```

Converts in-memory arrays with a caller-declared mapping. Vendor recording formats are out of
scope (Q-M2).

| Refuses | How |
|---|---|
| a missing unit, rate or timestamps, or both rate and timestamps | `UndeclaredUnitError` or `ValueError` |
| an `ElectricalSeries` without electrode rows, or with a `location` the caller did not write | `ValueError`; jnwb writes no anatomical label of its own |
| a `time_axis` whose length matches neither timestamps nor the rate and duration given | `AmbiguousLayoutError` |
| any interval or trial table | not offered: event and condition semantics are the caller's pynwb objects through `write_nwb` |

### M5 `repair_nwb`

```python
jnwb.repair_nwb(src, *, dst, repairs, overwrite=False, verify=True) -> MutationReport
```

Makes jnwb's in-memory read repairs persistent. `repairs` is required, as `select=` is for
`compress_fp32`: a list of names from `jnwb.REPAIRS`, the four the read path applies today.

| Repair | Proposed identifiability precondition | What the read path checks today |
|---|---|---|
| `squeeze_scalar_attributes` | the schema declares the attribute a scalar | only that it is not `colnames` |
| `units_colnames` | the data column exists in the units group and is absent from `colnames` | the same |
| `vector_index_types` | the index dataset's name is its target's name plus `_index`, and the target exists | the target's existence, for `target` only |
| `waveform_index_dtype` | the stored index values are integral | nothing: it casts |

Two of the four preconditions are stricter than the read path, so a persistent repair can refuse
a file that `read_nwb` reads; that is D4 applied to a write.

| Refuses | How |
|---|---|
| a repair name not in `REPAIRS` | `ValueError` |
| a named repair whose precondition does not hold in this file | `UnidentifiableRepairError`; nothing written |
| a missing `session_description` | `MissingRequiredNWBFieldError`: not a structural repair, the value is unknown |
| a container-type contradiction (`ContainerTypeContradictionWarning`) | reported, never rewritten: the stored type and the declared one are two plausible intents |

### M6 `normalize_nwb`

```python
jnwb.normalize_nwb(src, *, dst, series, to_unit=None, to_layout=None,
                   overwrite=False, verify=True) -> MutationReport
```

Rewrites one named series into a declared unit or layout, from what the file itself declares.
`to_unit` rescales only between units of one dimension with an exact factor (`"V"` to `"uV"`),
folding `conversion` and `offset` into the data. `to_layout="time_by_channel"` reorients a 2-D
series only when `inspect` reports its layout decided by the electrode region.

| Refuses | How |
|---|---|
| a series whose stored unit string is absent or not in the unit table | `UndeclaredUnitError`: a unit is never guessed |
| units of different dimension | `ValueError` |
| `layout` reported `"ambiguous"` | `AmbiguousLayoutError` |
| a series name that matches more than one series | `AmbiguousAcquisitionError` |

### M7 `upgrade_nwb`

```python
jnwb.upgrade_nwb(src, *, dst, overwrite=False, verify=True) -> MutationReport
```

Re-exports the file at the installed pynwb's schema version through `NWBHDF5IO.export`, after
applying no repair: repair is M5's, named.

| Refuses | How |
|---|---|
| an extension namespace the file uses and the environment lacks | `NWBMutationError` naming it |
| a type the target schema removed or renamed without a one-to-one mapping | `AmbiguousMappingError` |
| a file already at the installed schema version | returns `ok=True` with nothing written, and says so in `checks` |

### M8 `verify_nwb`

```python
jnwb.verify_nwb(dst, *, against=None, report=None, n_check=200_000) -> MutationReport
```

The check every writer runs, public so a caller can re-run it. Always: the file parses through
pynwb and passes schema validation, and every link and object reference resolves. With `against`
(the source): each dataset the report's `applied` does not name is byte-identical over `n_check`
rows, and each declared cast equals the cast of the source, as `verify_roundtrip` checks today.

| Refuses | How |
|---|---|
| `against` given without `report` | `ValueError`: without the declared changes every difference would be unexplained |
| a failed check | `ok=False` in the report; the writers turn it into `NWBVerificationError` |

## What is left out, and why

| Left out | Reason |
|---|---|
| in-place modification | the source is never modified; every operation writes a new file |
| any default that names a condition, area, layer, unit or trial | D6 to D8 |
| deriving a rate from timestamps | refused today on read; the rate needs an independent clock |
| a skill | goal 5: API, documentation and tests land before any skill |

## Open for Hamm

| # | Question | Options, graded |
|---|---|---|
| Q-M1 | The set | (a) M1, M2, M3, M5 and M8 first, M4, M6 and M7 after, 70; (b) all eight at once, 45; (c) M1 and M8 only, 40 |
| Q-M2 | Vendor recording formats in `convert_to_nwb` | (a) out: in-memory arrays with a declared spec only, and NeuroConv for vendor formats, 80; (b) in, 20 |
| Q-M3 | NWB Inspector | (a) an optional extra behind `checks="inspector"`, 70; (b) a required dependency, 25; (c) not used, 40 |
| Q-M4 | Names | (a) `<verb>_nwb` as above, beside `read_nwb`, 75; (b) a namespace `jnwb.nwb.<verb>`, 45 |
| Q-M5 | `compress_fp32` | (a) kept as is and tagged `copy or transform`, 80; (b) reimplemented on `transform_nwb` later, as a separate item, 50 |
