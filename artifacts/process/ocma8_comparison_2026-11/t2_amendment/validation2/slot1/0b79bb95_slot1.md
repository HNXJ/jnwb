1. Cell splitting under `tree/scripts/`:
- `scripts/md_table.py:15` (`_UNESCAPED_PIPE.split(line)` in `split_row`): in scope. It is the only splitter the tree has.
- `scripts/docs_form_gate.py:327` (`cited_works_removed`, `line.split(" | ", 1)`): out of scope by the rubric.
- `scripts/gates/api_types.py:15` (`API_MD_ROW`, a regex that captures the cells of an `api.md` row): baseline code, unchanged, not one of the eight sites. Out of scope. It is the one borderline case (see item 4).
- `scripts/gates/stacks_closure.py:95` (`_ESCAPED_PIPE.sub("", line).count("|")`): counts cells, so it is row-shape logic. Out of scope.
- `scripts/obligation_diff.py:35` (`SPLIT`): splits prose clauses on a pipe, not table cells. Out of scope.
- Several regexes that match a row's first cell: out of scope.
- No `split("|")`, `partition("|")`, `chr(124)`, `\x7c` or character-scan splitter appears anywhere else. I searched all of `scripts/`, including `scripts/gates/`.

2. The eight sites. Every one obtains its cells from `split_row` (`md_table.py:15`), with only row-shape logic around the call (`strip`, `strip("|")`, `[1:-1]`, blockquote removal).
- 1. `build_dashboard.py`: `references_section` (386), `order_section` (418), `deferred_section` (623) and `_study_cards` (801) each call `split_row(line)[1:-1]`. The old `_cells` is deleted.
- 2. `build_fact_graph.py:236` (header) and `:240` (rows) in `_all_tables`. The old `_cells` is deleted.
- 3. `build_fact_graph.py:396`, `reference_table_rows`.
- 4. `learning_gate.py:57` (`ledger_rows`) and `:137` (`_is_mapping_header`). The old `_cells` is deleted.
- 5. `release_gate.py:1427`, `roadmap_rows`. The old `_cells` is deleted.
- 6. `release_gate.py:1306`, `table_data_rows`, with blockquote stripping done inline. The old `_table_cells` is deleted. `_is_separator` only takes cells it is given.
- 7. `docs_form_gate.py:289`, `parse_vocabulary`.
- 8. `reconstruct_state.py:229`, `open_defect_classes`.

3. Criteria
- L1 met. There is exactly one splitter body, `md_table.py:15`. The pattern is a constant applied only there.
- L2 met. All eight readers get their cells from `split_row`, including headers and separators. No site splits a row or its cells again on the pipe.
- L3 met. All four old `_cells` functions (`build_dashboard.py`, `build_fact_graph.py`, `learning_gate.py`, `release_gate.py`) and `_table_cells` are removed. The three inline splits are replaced. Nothing is left defined and uncalled.

4. Commands run beyond reading: none, only Read and Grep. I ran no reader on a row, because reading settled every site.
- Not established: nothing material.
- Rubric gap: `gates/api_types.py:15` is a regex that captures the cells of a table row. The scope rule lists "regexes that match a row's first cell" as an example of unchanged baseline code. That example does not state whether a multi-cell capturing regex is also excluded. I read the general rule (unchanged baseline outside the eight sites is out of scope) as covering it. If a later adjudicator counts it in scope, L1 would fail.
- Model id: claude-sonnet-5-5.

VERDICT: PASS
