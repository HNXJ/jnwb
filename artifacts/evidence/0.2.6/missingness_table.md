# 06-71 — The missingness truth table

Evidence for a ruling. Nothing here is implemented; the empty-string behaviour ships as-is.

**Baseline** `577847f2aa7203f2d06e03b870de56fbe89e1d81`, tree clean, verified at run start.
**Measured copies** — both, and they disagree:

| copy | `jnwb.__file__` | `__version__` | `allow_missing` in `read_nwb` |
|---|---|---|---|
| worktree | `C:\workspace\jnwb\jnwb\__init__.py` | `0.2.5` | **True** |
| installed (shipped) | `C:\Python314\Lib\site-packages\jnwb\__init__.py` | `0.2.5` | **False** |

Both report `0.2.5`. The version string does not separate them; the signature does. Every "shipped
version" cell below means the installed copy, which has the refusal but **no waiver**.

Nothing under `C:\workspace\jnwb` was written. All candidate patches were applied in-process.

---

## The table

Six states, one row each. `sd` = `nwbfile.session_description`. "default" = `read_nwb(p)`;
"waived" = `read_nwb(p, allow_missing=("session_description",))`.

| # | on-disk state | current behaviour (run) | proposed behaviour (observable) | compatibility consequence for a caller on the shipped version | information lost by collapsing |
|---|---|---|---|---|---|
| 1 | **absent entirely**<br>`s1_absent.nwb`<br>`sha256 6fd10c1c…` | default → `MissingRequiredNWBFieldError: NWB file is missing required field 'session_description'`<br>waived → `OPENED`, `sd=''`, `type=str`, `bool=False`, `len=0`, `jnwb_waived_requirements=('session_description',)`<br>bare pynwb → `ConstructError`<br>public API (`inspect`/`events`/`event_onsets`/`unit_spike_times`/`acquisition_channel`) → `MissingRequiredNWBFieldError`, **no waiver reachable** | status quo (06-67 ruled the refusal; only the `''` fill is provisional) | **None for the refusal** — shipped 0.2.5 raises the same `MissingRequiredNWBFieldError`. **The waiver does not exist there**: `read_nwb(p, allow_missing=…)` → `TypeError: NWBHDF5IO.__init__: unrecognized argument: 'allow_missing'`. A caller writing forward-compatible code gets an error naming `NWBHDF5IO`, not jnwb. | **YES** — under a defensive waiver, **state 1 (absent entirely)** and **state 3 (empty string `""`)** become indistinguishable. See Row 3. |
| 2 | **explicit `None`**<br>three encodings built, none opens | No encoding reaches a Python `None`. All raise:<br>• NULL dataspace (`H5S_NULL`) → `TypeError: object of type 'NoneType' has no len()` (both modes)<br>• zero-length array `(0,)` → `ConstructError` ← `TypeError: NWBFile.__init__: incorrect type for 'session_description' (got 'Dataset', expected 'str')`<br>• null object reference → `ValueError: Invalid HDF5 object reference`<br>Identical on worktree, installed and bare pynwb. | none proposed — the state is unreachable through the reader, so there is no behaviour to change | **None.** All three raise identically on shipped 0.2.5 and on bare pynwb. This is pynwb/h5py behaviour, not jnwb's. | **YES** — **state 2 (explicit `None`, zero-length-array encoding)** and **state 4 (malformed, `(2,)` float array)** collapse: both bottom out at the same deepest cause, `TypeError: NWBFile.__init__: incorrect type for 'session_description' (got 'Dataset', expected 'str')`. A caller cannot tell an empty array from a float array from the exception. |
| 3 | **empty string `""`**<br>`s3_empty_string.nwb`<br>`sha256 57a88022…` | default → `OPENED`, `sd=''`, `type=str`, `bool=False`, `len=0`, `jnwb_waived_requirements=()`, **no warning**<br>waived → `OPENED`, `sd=''`, `jnwb_waived_requirements=('session_description',)`, **no warning**<br>bare pynwb → `OPENED`, `sd=''` | five candidates, measured — see **Row 3 detail** | **None.** Shipped 0.2.5 also opens it and returns `''`. Every candidate except `c3a` changes what a caller sees; `c3c` turns a file that opens today into a refusal. | **YES** — see Row 3 detail. Under the defensive waiver, **six** on-disk states return a byte-identical `''`. The pair the ruling turns on: **state 1 (absent entirely)** and **state 3 (genuinely empty `""`)**. |
| 4 | **malformed value**<br>`s4b_malformed_len1_strarray.nwb`<br>`sha256 e892f171…` | **Opens silently.** `(1,)` string array `['MALFORMED']` → `OPENED`, `sd='MALFORMED'`, `type=str`, `len=9`, **no warning**. Byte-identical result to a genuine scalar `'MALFORMED'` (`s4b_control_scalar_str.nwb`).<br>Other malformed encodings refuse: `int64 42` → `ConstructError` ← `got 'int64'`; `(2,)` str array → `ConstructError` ← `got 'StrDataset'`; `(2,)` float array → `ConstructError` ← `got 'Dataset'`.<br>`SqueezedAttributeWarning` **cannot fire** here: `session_description` is in `builder.datasets`, and the squeeze repair only walks `builder.attributes` (measured: `sd_in_builder.datasets=True`, `sd_in_builder.attributes=False`). Bare pynwb also returns `'MALFORMED'`, so the length-1 collapse is **pynwb's**, not jnwb's. | three candidates, measured — see **Row 4 detail** | **None for the status quo** — shipped 0.2.5 returns `'MALFORMED'` too. `c4b` would turn a file that opens on 0.2.5 into a refusal; `c4c` adds a warning a 0.2.5 caller never saw. | **YES** — **state 4 (malformed `(1,)` string array)** and **state 6 (present and valid, scalar string)** are indistinguishable from the returned object. Zero differing observables across `sd`, `type`, `bool`, `len`, `jnwb_waived_requirements`, `in fields`, and warnings. |
| 5 | **caller-waived**<br>same bytes as state 1<br>`sha256 6fd10c1c…` | `OPENED`, `sd=''`, `type=str`, `bool=False`, `len=0`, `jnwb_waived_requirements=('session_description',)`, no warning.<br>**`jnwb_waived_requirements` records the request, not the event**: a valid file read with the same waiver also reports `('session_description',)` (measured on `s6_present_valid.nwb`).<br>Reachable **only** through `jnwb.nwb_io.read_nwb` / `nwb_read_io`. Measured: `jnwb.read_nwb` → attribute absent; `jnwb.nwb_read_io` → attribute absent; neither in `jnwb.__all__`. No public entry point accepts `allow_missing`. | status quo. The `''` fill is what `goal.md` §4 marks provisional. | **The state is unreachable on the shipped version.** 0.2.5 has no `allow_missing` on `read_nwb`, no `jnwb_waived_requirements` attribute, and no way to open an incomplete file at all. Any change here is additive for a 0.2.5 caller, because there is nothing there to break. | **YES** — **state 5 (caller-waived)** and **state 3 (genuinely empty `""`)** are indistinguishable whenever the caller passes the waiver for the whole corpus rather than per file. Also collapsed in: **state 1 (absent)**, the two broken-link states, and the NUL-byte state — six in total. |
| 6 | **present and valid**<br>`s6_present_valid.nwb`<br>`sha256 cdc3b367…` | default → `OPENED`, `sd='Synthetic multi-table NWB for jnwb fixtures'`, `len=43`, `jnwb_waived_requirements=()`<br>waived → same value, but `jnwb_waived_requirements=('session_description',)` on a file that waived nothing | status quo | **None.** Identical on shipped 0.2.5 (minus the `jnwb_waived_requirements` attribute, which does not exist there). | **YES** — **state 6 (present and valid)** and **state 4 (malformed `(1,)` string array)** are indistinguishable; the `(1,)` array is silently flattened to the scalar. Separately, under a defensive waiver a valid file is flagged `jnwb_waived_requirements=('session_description',)`, which makes the flag useless for telling **state 6** from **state 5**. |

---

## Row 3 detail — the five candidates

All run. `1` = absent on disk, `3` = genuinely empty on disk, `6` = valid on disk.

| candidate | `1` waived | `3` default | `3` waived | `6` waived | can a reader tell **1** from **3**? by what observable? |
|---|---|---|---|---|---|
| **c3a status quo** | `sd=''`, waived=`('session_description',)` | `sd=''`, waived=`()` | `sd=''`, waived=`('session_description',)` | `sd='Synthetic…'`, waived=`('session_description',)` | **NO** under a defensive waiver — every observable is equal. **YES** only if the caller waives *per file, after a default read already raised*, in which case `jnwb_waived_requirements` differs `('session_description',)` vs `()`. That is circular: it distinguishes them only for a caller who already knew. |
| **c3b1 text sentinel** | `sd='\x00jnwb:waived:session_description'` | `sd=''` | `sd=''` | `sd='Synthetic…'` | **YES** — `sd` itself. Cost: `sd` is no longer falsy for a waived file (`bool=True`), and the sentinel is a synthesized value on an object whose contract says nothing is synthesized. |
| **c3b2 str subclass** | `sd=''`, `type=WaivedRequirement` | `sd=''`, `type=str` | `sd=''`, `type=str` | `sd='Synthetic…'`, `type=str` | **YES** — `type(sd)`. `sd == ''` and `bool(sd) is False` still hold, so no value comparison changes. Invisible to `repr`, to logging, and to anything that round-trips through `str()`. |
| **c3c refuse empty** | `sd=''`, waived=`('session_description',)` | **`RAISED MissingRequiredNWBFieldError`** | **`RAISED MissingRequiredNWBFieldError`** | `sd='Synthetic…'` | **YES** — state 3 no longer opens at all. Cost: a file that opens on shipped 0.2.5 stops opening, and the waiver cannot rescue it. The only candidate that breaks a currently-working read. |
| **c3d event flag** | `sd=''`, waived=**`('session_description',)`** | `sd=''`, waived=`()` | `sd=''`, waived=**`()`** | `sd='Synthetic…'`, waived=**`()`** | **YES** — `jnwb_waived_requirements`, made to record what was *actually* waived rather than what was *requested*. No value changes, no read starts or stops failing. The flag also stops lying on valid files. |

## Row 4 detail — the three candidates

`4b` = `(1,)` string array on disk; `4ctl` = genuine scalar `'MALFORMED'` on disk. The two files
differ in bytes (`sha256 e892f171…` vs the control's, and on-disk shape `(1,)` vs `()`).

| candidate | `4b` default | `4ctl` default | can a reader tell **4** from **6**? by what observable? |
|---|---|---|---|
| **c4a status quo** | `OPENED`, `sd='MALFORMED'`, no warning | `OPENED`, `sd='MALFORMED'`, no warning | **NO** — zero differing observables. |
| **c4b refuse non-scalar** | **`RAISED MissingRequiredNWBFieldError`** | `OPENED`, `sd='MALFORMED'` | **YES** — the read raises. Cost: a file that opens on shipped 0.2.5 *and on bare pynwb* stops opening under jnwb only. |
| **c4c warn non-scalar** | `OPENED`, `sd='MALFORMED'`, **`SqueezedAttributeWarning`** | `OPENED`, `sd='MALFORMED'`, no warning | **YES**, but only at read time. The warning is not on the returned object, so anything reading the object later — or reading it with warnings suppressed — still cannot tell. |

---

## Three states found during this run that were not in the brief

Each collapses into row 3's bucket and is byte-verified.

| state | bytes | default read | waived read |
|---|---|---|---|
| dangling `SoftLink` → `/no_such_target`<br>`sha256 439d8773…` | `b'session_description'` ×2, `b'no_such_target'` ×1; link class `SoftLink`, does not resolve | `MissingRequiredNWBFieldError` — **identical to absent** | `OPENED`, `sd=''`, waived=`('session_description',)`, `BrokenLinkWarning` |
| broken `ExternalLink` → missing file<br>`sha256 89cd3fbf…` | `b'no_such_file.h5'` ×1; link class `ExternalLink`, does not resolve | `MissingRequiredNWBFieldError` — **identical to absent** | `OPENED`, `sd=''`, waived=`('session_description',)`, `BrokenLinkWarning` |
| `S2` dataset holding one NUL byte<br>`sha256 26377654…` | raw data bytes `0000` read at offset 974696 with plain binary IO | `OPENED`, `sd=''` — **identical to genuinely empty** | `OPENED`, `sd=''`, waived=`('session_description',)`, no warning |

Under a defensive waiver **six** states return an identical `''` with an identical waiver flag:
absent, genuinely-empty-vlen, genuinely-empty-fixed-`S1`, NUL-byte-`S2`, dangling soft link,
broken external link. The only discriminator across all six is a transient `BrokenLinkWarning`
raised by h5py for the two link states — not an observable on the returned object.

A soft link pointing at a **valid** description is refused: default → `MissingRequiredNWBFieldError`,
waived → `ValueError: 'session_description' already exists in root.links, cannot set in datasets.`
The value is present and correct on disk and reachable through the link. The same applies to an
empty group named `session_description`.

---

## Two items the brief left open

**(A) Further encodings of explicit `None`.** Nine attempted. Not constructible: `h[sd] = None`
and `create_dataset(data=None)` (both `TypeError: One of data, shape or dtype must be specified`),
and `np.array(None, dtype=object)` as a vlen string (`TypeError: Can't implicitly convert
non-string objects to strings`). Constructible and all refused: NULL dataspace (vlen and fixed
`S1`), zero-length array (vlen and fixed `S1`), null object reference, float64 NaN.
The literal ASCII string `'None'` opens and returns `sd='None'`, `bool=True` — distinguishable,
not a collapse. **No on-disk encoding of explicit `None` produces a Python `None` on the returned
object.** State 2 is constructible on disk but unreachable through the reader.

**(B) Can the public API open a waived file?** No.

```
jnwb.inspect              RAISED MissingRequiredNWBFieldError
jnwb.events               RAISED MissingRequiredNWBFieldError
jnwb.event_onsets         RAISED MissingRequiredNWBFieldError
jnwb.unit_spike_times     RAISED MissingRequiredNWBFieldError
jnwb.acquisition_channel  RAISED MissingRequiredNWBFieldError

jnwb.read_nwb                      attr=False  in __all__=False
jnwb.nwb_read_io                   attr=False  in __all__=False
jnwb.hdmf_build_repair_context     attr=False  in __all__=False
jnwb.MissingRequiredNWBFieldError  attr=True   in __all__=True
```

No public entry point accepts `allow_missing`, and `_with_nwb` calls `nwb_read_io` without it.
The error is exported; the opt-in that clears it is not. The only route is
`import jnwb.nwb_io`, a module whose own docstring calls itself module-internal.

A two-step workaround exists: `read_nwb(p, allow_missing=…)` then hand the object to the public
API. `jnwb.inspect(nwbfile)` → `OPENED`, and `jnwb_waived_requirements` survives the handoff.
`jnwb.events` / `event_onsets` raise `AmbiguousIntervalTableError` (a fixture property, unrelated
to missingness) and `jnwb.unit_spike_times` raises `RuntimeError: Unable to synchronously get
dataspace` because the file handle is closed by then.

---

## How each state was built and confirmed in bytes

Built with h5py on a copy of `jnwb.testing.nwb_fixtures.write_synth_nwb` output. Confirmed before
any read, by two routes that do not ask h5py for the value:

1. **Raw data bytes.** The dataset's contiguous offset and storage size come from the low-level
   id (`dset.id.get_offset()` / `get_storage_size()`); the bytes themselves are read with
   `open(path,'rb').seek(offset).read(n)`.
   - state 6 valid → `2b000000c8f90e00000000002c000000` — vlen length prefix `0x2b` = 43 = `len('Synthetic multi-table NWB for jnwb fixtures')`
   - state 3 empty vlen → `00000000f8c611000000000001000000` — length prefix `0`
   - state 3 empty fixed `S1` → `00`
   - state 4 `(1,)` array → `09000000f8c611000000000001000000` — prefix `9` = `len('MALFORMED')`
   - state 4 int64 42 → `2a00000000000000`
   - NUL-byte `S2` → `0000`
2. **Object-header bytes**, for the states with no contiguous data offset. The object-header
   address comes from `h5py.h5o.get_info(...).addr`; the header is read with plain binary IO and
   the dataspace message decoded by hand:

   | state | header first 48 bytes (hex) | decoded dataspace |
   |---|---|---|
   | NULL dataspace | `010005000100000000010000000000000100080000000000020000020000000003001800010000001901010010000000` | msg v2, class byte `2` = `H5S_NULL` |
   | zero-length array | `010005000100000000010000000000000100180000000000010101000000000000000000000000000000000000000000` | msg v1, rank 1 = `H5S_SIMPLE` |
   | empty string `""` | `010005000100000000010000000000000100080000000000010000000000000003001800010000001901010010000000` | msg v1, rank 0 = `H5S_SCALAR` |

   The empty-string and present-valid headers are byte-identical over these 48 bytes — same scalar
   vlen-string layout — and differ only in the data bytes above. That is the truth table's premise
   in bytes: on disk the two states differ by 43 characters of payload and nothing else.
3. **Whole-file byte scan.** `b'session_description'` occurs 2× in every state where the dataset
   or link exists and 1× in state 1, where it was deleted.
4. **SHA-256** of every fixture, recorded in `states.json` and re-checked at read time.

Files: `build_states.py` / `states.json` · `probe_current.py` / `current_worktree.json` /
`current_installed.json` · `pairwise.py` / `pairwise.json` · `candidates.py` / `cand_*.json` ·
`final_probes.py` / `final_probes.json` · `collapse_probe.py` / `collapse_probe.json` ·
`error_detail.py` / `error_detail.json` · `fixtures/`.
