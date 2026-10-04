# Reading NWB Data

How jnwb reads an NWB file, finds data roots without absolute paths, and reads a slice of a large
array. What a session holds is `jnwb.inspect`: it lists a file's acquisitions, electrodes, units
and interval tables, and [Your Own NWB File](tutorials/00_your_own_file.md) runs it on a file you
did not write. Anatomical addressing and unit metadata are on
[Addressing & Metadata](02_paths_addressing_metadata.md).

---

## 1. NWB, PyNWB and HDMF

NWB is a data standard for neurophysiology: an HDF5 layout plus a schema for acquisitions,
electrodes, units, trials and intervals (Teeters et al., 2015; Rübel et al., 2022). jnwb reads
NWB files through PyNWB, the reference Python API, which uses HDMF for the schema and HDF5 input
and output.

jnwb-owned NWB reads (`jnwb.nwb_io.read_nwb` and `nwb_read_io`) repair malformed unit and
index builders through HDMF for that read only; `BuildManager.construct` is not altered at
import, and a missing required `session_description` raises `MissingRequiredNWBFieldError`
rather than synthesizing a value. Citations and links are in
[References](references.md#data-format).

---

## 2. Path Management & Drive Remap Isolation (`jnwb/paths.py`)

`jnwb.paths` resolves data roots for batch jobs from environment variables, so no absolute path
is written into code. It does not look inside a `.nwb` file: per-file discovery (acquisitions,
interval tables, event codes) is `jnwb.inspect` and the
[addressing tutorial](tutorials/02_addressing_and_metadata.md).

### Key API Functions

```python
import jnwb

# Print the status of all registered data roots and their resolution state
jnwb.paths.describe()

# Where the INSTALLED jnwb package lives. This is jnwb's own root, never yours --
# anchor to your own file (Path(__file__).resolve().parent.parent) for your project.
jnwb_package_root = jnwb.paths.PACKAGE_ROOT

# Outputs and artifacts resolve against the process working directory, so they
# follow the consuming project rather than the install location.
outputs = jnwb.paths.outputs_dir()
artifacts = jnwb.paths.artifacts_dir()

# Resolve an external data root (raises FileNotFoundError naming the env var to set)
nwb_dir = jnwb.paths.nwb_dir()
```

### Environment Variable Mapping

| Path Key | Environment Variable | Default Fallback | Purpose |
|----------|----------------------|------------------|---------|
| `nwb_dir` | `JNWB_NWB_DIR` | `None` (must be set) | Directory containing primary `.nwb` session files |
| `analysis_dir` | `JNWB_ANALYSIS_DIR` | `None` (must be set) | Analysis root volume |
| `outputs` | `JNWB_OUTPUTS_DIR` | `<cwd>/outputs` | Processed tables, analysis summaries |
| `artifacts` | `JNWB_ARTIFACTS_DIR` | `<cwd>/artifacts` | Evidence logs, metadata sidecars |

Each variable still reads a legacy `OMISSION_*` alias of the same suffix, with a
`DeprecationWarning`.

---

## 3. Memory-Bounded Array Streaming (`jnwb.io`, `stream_npz_array`)

`np.load` decompresses a whole `.npz` array into RAM. `jnwb.stream_npz_array` reads a slice of it, from `ZIP_DEFLATED` and `ZIP_STORED` archives alike. Peak memory is strictly proportional to the requested output slice plus bounded streaming/selection overhead. A stored entry is seeked past what the slice skips, except on CPython 3.12.0, where `ZipExtFile.seek` loses count of the bytes left in a stored entry and the skipped bytes are read instead. A compressed entry is read forward up to the slice's last element on every interpreter, so its time grows with the slice's position:

```python
import jnwb
from pathlib import Path

npz_path = Path("session_data.npz")

# Stream only the desired channels and time slice without allocating the full array
# e.g., channels 10:20 across time steps 1000:5000:
sliced_data = jnwb.stream_npz_array(
    npz_path,
    key="lfp_matrix",
    slice_tuple=(slice(10, 20), slice(1000, 5000)),
)

# Preserves exact dtype, shape, and C / Fortran memory order
print(sliced_data.shape, sliced_data.dtype)
```

Also accessible as `jnwb.io.stream_npz_array`.
