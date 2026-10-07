# `validate_nwb`: the NWB Inspector and DANDI layers, run

Run 2026-10-07 in a throwaway environment holding nwbinspector 0.7.2, dandi 0.81.0 and pynwb
3.1.3, with `jnwb` imported from the `m-validate` lane tree (since removed). The one later change
to `jnwb/nwb_validate.py`, `e3db3a49`, deletes a docstring sentence; `tests/test_nwb_validate.py`
is unchanged since `53b3dd73`.

## What it shows

| Claim | Receipt |
|---|---|
| A clean synthetic file (`_make_nwb` of `tests/test_nwb_validate.py`) passes all six layers | probe output, first summary: `ok=True complete=True dandi_ready=True`, six `pass` rows |
| `dandi_ready` is True when every layer runs | same line |
| The NWB Inspector layer passes with 3 best-practice warnings, none CRITICAL or ERROR | `nwbinspector  pass    errors=0 warnings=3`, and the three `BEST_PRACTICE_SUGGESTION` messages |
| The DANDI layer passes with `DANDI.NO_DANDISET_FOUND` ignored | `dandi         pass    errors=0 warnings=0 (dandi 0.81.0; ...)` |
| A run of only those two layers is not `dandi_ready` | second summary: `dandi_ready=False` |
| `tests/test_nwb_validate.py` passes with dandi installed, the two dandi tests included | `13 passed` and no skip; the two tests call `pytest.importorskip("dandi")`, so a skip would be counted |

## Not tested

The floors the `validate` extra declares, `nwbinspector>=0.6` and `dandi>=0.70`, were not
installed or run. Both layers are exercised with nwbinspector 0.7.2 and dandi 0.81.0 only.

## Probe output, verbatim

Script: `_temp_probe_validate.py` (builds the file with `_make_nwb`, calls
`jnwb.validate_nwb(p)` and `jnwb.validate_nwb(p, layers=["nwbinspector", "dandi"])`).

```text
jnwb from C:\workspace\jnwb-lanes\m-validate\jnwb\__init__.py
nwbinspector 0.7.2 dandi 0.81.0
s.nwb  ok=True complete=True dandi_ready=True
  read          pass    errors=0 warnings=0 (opened with jnwb.read_nwb)
  pynwb_schema  pass    errors=0 warnings=0 (namespaces cached in the file)
  pynwb_core    pass    errors=0 warnings=0 (core namespace of pynwb 3.1.3)
  integrity     pass    errors=0 warnings=0 (ragged indices of units, electrode regions)
  nwbinspector  pass    errors=0 warnings=3 (CRITICAL and ERROR fail; best-practice findings are warnings)
  dandi         pass    errors=0 warnings=0 (dandi 0.81.0; ignored ids: DANDI.NO_DANDISET_FOUND)
ok True complete True dandi_ready True
read pass []
pynwb_schema pass []
pynwb_core pass []
integrity pass []
nwbinspector pass ["BEST_PRACTICE_SUGGESTION check_description ElectricalSeries:raw: Description ('no description') is a placeholder.", 'BEST_PRACTICE_SUGGESTION check_experiment_description NWBFile:root: Experiment description is missing.', 'BEST_PRACTICE_SUGGESTION check_keywords NWBFile:root: Metadata /general/keywords is missing.']
dandi pass []
s.nwb  ok=True complete=True dandi_ready=False
  nwbinspector  pass    errors=0 warnings=3 (CRITICAL and ERROR fail; best-practice findings are warnings)
  dandi         pass    errors=0 warnings=0 (dandi 0.81.0; ignored ids: DANDI.NO_DANDISET_FOUND)
```

## Test output, verbatim

`tests/test_nwb_validate.py` run with pytest `-q` in the same environment (`_temp_vtests.out`):

```text
.............                                                            [100%]
============================== warnings summary ===============================
tests/test_nwb_validate.py: 11 warnings
  C:\Python314\Lib\site-packages\hdmf\utils.py:592: DeprecationWarning: The 'manufacturer' field is deprecated. Instead, use DeviceModel.manufacturer and link to that DeviceModel from this Device.
    return func(args[0], **pargs)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
13 passed, 11 warnings in 5.75s
```
