1. Cell splitting under `tree/scripts/`:
- `scripts/stack_parse.py:222-230` is the only place that decides where a cell ends. `iter_cells` applies `_UNESCAPED_PIPE.finditer` (`stack_parse.py:45`). In scope.
- Out of scope, and not cell splitting by the rubric:
  - `scripts/docs_form_gate.py:327`: `line.split(" | ", 1)`, a single cut at the first spaced pipe. This is `cited_works_removed`, which the rubric tells me to ignore.
  - `scripts/computational_contract_gate.py:653`: a regex that matches a row's first cell. Unchanged baseline code.
  - `scripts/gates/stacks_closure.py:95`: counts delimiters with `.count("|")`. Unchanged.
  - `scripts/docs_form_gate.py:287`, `:716` and `scripts/build_fact_graph.py:394`: `|---` and "line is a separator or row" tests. These are row-shape logic.
  - `scripts/learning_gate.py:60`: splits cell content on `;`, not on the pipe.
- A grep of all `scripts/**` found no other pipe-splitting form: `split`, `partition`, `finditer`, `csv`, `chr(124)`, `\x7c`, `translate`. `_cells` and `_table_cells` no longer exist anywhere.

2. The eight sites. All call `iter_cells`, then add only row-shape logic: `strip`, outer-pipe removal, `[1:-1]`.
- Site 1, `build_dashboard.py`:
  - Readers: `references_section`, `order_section`, `deferred_section`, `_study_cards`.
  - Splits at `:386`, `:418`, `:623` and `:801` (`iter_cells` on the whole line, then `[1:-1]`). Import at `:82`.
- Site 2, `build_fact_graph.py`:
  - Reader: `_all_tables`.
  - Splits at `:236` (header) and `:240` (body rows).
- Site 3, `build_fact_graph.py`:
  - Reader: `reference_table_rows`.
  - Splits at `:396`.
- Site 4, `learning_gate.py`:
  - Readers: `ledger_rows` and `_is_mapping_header`.
  - Splits at `:57` and `:137`.
- Site 5, `release_gate.py`:
  - Reader: `roadmap_rows`.
  - Splits at `:1427`.
- Site 6, `release_gate.py`:
  - Reader: `table_data_rows`.
  - Splits at `:1306`, which strips blockquote markers first; that is row-shape logic.
- Site 7, `docs_form_gate.py`:
  - Reader: `parse_vocabulary`.
  - Splits at `:289`.
- Site 8, `reconstruct_state.py`:
  - Reader: `open_defect_classes`.
  - Splits at `:229`.

3. Criteria.
- L1 met. Exactly one body splits cells: `iter_cells`, one pattern applied once.
- L2 met. All eight readers get their cells from `iter_cells`. The headers (`build_fact_graph.py:236`, `learning_gate.py:137`) and the data rows use it too, and nothing re-splits on the pipe afterwards.
- L3 met. All eight former splitters (`_cells` in four modules, `_table_cells`, three inline splits) are deleted. No defined-but-uncalled splitter remains. The out-of-scope items in section 1 are not splitters under the rubric.

4. Commands run beyond reading: only Grep and Glob searches. I did not run a reader on a row. Nothing was left unestablished, because the code paths were all direct. The rubric decided every case as written. I note, without relying on it, that the `[1:-1]` slice in the site 1 readers differs from the outer-strip-pipe form used elsewhere; the rubric treats both as row-shape logic. Model id: claude-sonnet-5-5.

VERDICT: PASS
