1. Cell splitting under tree/scripts/:
- scripts/pipe_cells.py:12 `split_row` runs `re.split(_UNESCAPED_PIPE, line)`. It is the only body that splits. In scope.
- scripts/pipe_cells.py:17 `split_cells` strips each segment of `split_row`. Row-shape logic, no splitting of its own. In scope.
- scripts/docs_form_gate.py:329 (`cited_works_removed`) calls `split_row`, then picks a cut by index. Out of scope per the rubric, and it splits nothing itself.
- scripts/gates/api_types.py:15 is a regex with `([^|]*)\|(.*)\|` groups. Unchanged baseline, not one of the eight sites. Out of scope.
- scripts/computational_contract_gate.py:653 is a first-cell regex. Unchanged baseline. Out of scope.
- scripts/gates/stacks_closure.py:95 counts pipes after removing escaped ones. It does not split. Out of scope.
- scripts/docs_form_gate.py:721 and :887 only test for a leading `|`. They do not split. Out of scope.
- The other grep hits split on `.` or sentence boundaries, or build rows with f-strings. They are not table-row splitting.
- A grep for `_cells` and `_table_cells` found no old splitter definitions left. The baseline `_cells` and `_table_cells` bodies and the inline `.split("|")` expressions are all removed (changes.diff).

2. The eight sites. Every one gets its cells from pipe_cells.py:12 through `split_cells`.
1. build_dashboard.py reads through `split_cells(line)[1:-1]` at lines 386 (`references_section`), 418 (`order_section`), 623 (`deferred_section`) and 801 (`_study_cards`). The slice is row-shape logic.
2. build_fact_graph.py:236 (header) and :240 (rows) in `_all_tables`. Both use `split_cells(x.strip().strip("|"))`.
3. build_fact_graph.py:396 in `reference_table_rows`.
4. learning_gate.py:57 (`ledger_rows`) and :137 (`_is_mapping_header`, used by `mapping_tables`).
5. release_gate.py:1426 in `roadmap_rows`.
6. release_gate.py:1306 in `table_data_rows`. The `>` blockquote removal and outer-pipe strip happen before the call, so they are row-shape logic. `_is_separator` works on cells it is given.
7. docs_form_gate.py:289 in `parse_vocabulary`.
8. reconstruct_state.py:229 in `open_defect_classes`.
No site splits or re-joins on the pipe after the call. Headers and separator rows go through the same function.

3. Criteria:
- L1 met. Exactly one body splits cells (pipe_cells.py:12). `split_cells` only strips.
- L2 met. All eight sites call `split_cells` and add only row-shape logic (outer-pipe strip, slice, blockquote strip, startswith test). No site splits again.
- L3 met. No other splitter remains defined, called or dispatched to. The old `_cells` and `_table_cells` functions and the inline splits are deleted. The remaining pipe-related code is out of scope or does not split.

4. Commands run beyond reading: Grep searches over tree/scripts for `split`, `partition`, `finditer`, `find`, `translate`, `chr(124)`, `\x7c`, pipe regexes and `_cells`. I did not run any reader, because reading settled every site. I wrote nothing, so notes/ was not created.
- Not established: nothing that affects the verdict. I did not check whether the cells come out the same as the baseline, since the rubric excludes that question.
- Rubric gap: gates/api_types.py:15 is a baseline regex that carves a row into groups by pipes. The rubric calls unchanged baseline code outside the eight sites out of scope (its example is first-cell regexes), so I treated it as out of scope. If it counted, L3 would fail. This is a judgement under the written scope, not a decided case.
- Model id: claude-sonnet-5-5.

VERDICT: PASS
