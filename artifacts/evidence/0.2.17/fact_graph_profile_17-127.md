# Fact graph build: one shared parse per source (todo 17-127)

Baseline fc0d61daba1d0c3dc9504b13acf4d321827020ce; change 7069242de5e16d936536a5b9972171cb716809b7
(`scripts/fact_graph/_sources.py`; `build()` runs every scan inside `shared_sources()`).
Host: Windows workstation, other agents' work running; load is `(Get-CimInstance Win32_Processor).LoadPercentage`,
sampled before and after each run.

## cProfile, one build each

`cProfile` around `build_fact_graph.main(["--out", <scratch>])`; counts read from `pstats` for
`ast.py:parse` and `ast.py:walk`. `ast.walk` is a generator: cProfile counts each resume as a call.

| Tree | Load before/after | Wall under profile | `ast.parse` calls | `ast.parse` cum. | `ast.walk` resumes | `ast.walk` cum. |
|---|---|---|---|---|---|---|
| baseline | 7% / 7% | 82.8 s | 6266 | 8.66 s | 7962916 | 37.65 s |
| change | 4% / 14% | 50.4 s | 1269 | 2.82 s | 2138038 | 11.82 s |

Parses by text (`ast.parse` patched to count each source text): baseline 6266 calls over 1261
distinct texts, 1177 texts parsed more than once, at most 44 times; change 1269 calls over 1261
distinct texts, 2 texts repeated (library calls outside the scans: `inspect`, matplotlib `rcsetup`).
Function sources are parsed once per function (`function_tree`), separately from their file.

## Wall time, unprofiled

`python scripts/build_fact_graph.py --out <scratch>`, runs interleaved. "baseline" is a clone at
the baseline with the new test file copied in, so its graph differs from the change's only by
the change's own files.

| Run | Baseline | Load | Change | Load |
|---|---|---|---|---|
| 1 | 32.2 s | 4% / 11% | 23.2 s | 26% / 5% |
| 2 | 28.2 s | 15% / 21% | 17.9 s | 8% / 8% |
| 3 | 28.7 s | 11% / 1% | 16.4 s | 6% / 1% |

The three change runs are under 60 s at 1-26% load, measured by the author.

## Graph identity

`diff` of each baseline graph against the change graph of the same run: the `head` line and one
added entry, `scripts/fact_graph/_sources.py` in the `python` entity (the new tracked file).
No relation, finding or examined count differs. Built before the new file was tracked, the
change's graph was byte-identical to the baseline's (`cmp`). Two builds of one tree are
byte-identical (`cmp`, runs 1 and 3 of each tree).

## Parse-once test

`tests/test_fact_gate.py::test_the_live_build_parses_each_python_file_once` counts `ast.parse`
per tracked file text during the module's live build and requires every `jnwb/` file parsed and
none parsed twice. Change: 1 passed. Baseline clone with the test copied in: 1 failed, 434 files
parsed more than once (`examples/quickstart_jnwb.py`: 3).
