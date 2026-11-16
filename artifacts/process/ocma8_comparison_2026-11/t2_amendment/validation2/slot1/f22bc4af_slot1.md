1. Places under tree/scripts/ that split a table row into cells:
- `scripts/table_rows.py:10`, `split_stripped`, applies `PATTERN.split(line.strip().strip("|"))`. In scope.
- `scripts/table_rows.py:15`, `split_inner`, applies `PATTERN.split(line)[1:-1]`. In scope.
- `scripts/docs_form_gate.py:326`, `cited_works_removed`, `line.split(" | ", 1)`. Out of scope per the rubric.
- `scripts/gates/stacks_closure.py:95` only counts pipes after removing escaped ones. That is row-shape logic, not splitting.
- A grep for other pipe splits (`"|"`, `[|]`, `chr(124)`, `\x7c`, `translate`, `partition`, `csv`, `finditer`) found no other cell splitting.
- No baseline splitter body remains. The old `_cells` and `_table_cells` bodies are gone or are now thin wrappers.

2. The eight sites, reader and where its cells are split:
1. `build_dashboard.py` (`references_section` 386, `order_section` 418, `deferred_section` 623, `_study_cards` 801) calls `split_inner`, which splits at `table_rows.py:15`.
2. `build_fact_graph.py` `_all_tables` (236, 240) calls `split_stripped`, which splits at `table_rows.py:10`.
3. `build_fact_graph.py` `reference_table_rows` (396) calls `split_stripped`, which splits at `table_rows.py:10`.
4. `learning_gate.py` `ledger_rows` (57) and `_is_mapping_header` (137) call `split_stripped`, which splits at `table_rows.py:10`.
5. `release_gate.py` `_cells` (1294) is a wrapper that checks for a leading pipe and then calls `split_stripped`. It splits at `table_rows.py:10`.
6. `release_gate.py` `_table_cells` (1302) strips the blockquote marker and then calls `split_stripped`. It splits at `table_rows.py:10`.
7. `docs_form_gate.py` `parse_vocabulary` (288) calls `split_stripped`, which splits at `table_rows.py:10`.
8. `reconstruct_state.py` `open_defect_classes` (231) calls `split_stripped`, which splits at `table_rows.py:10`.

3. Criteria:
- L1 not met. `table_rows.py` holds two separate bodies that each call `PATTERN.split` themselves: `split_stripped` at line 10 and `split_inner` at line 15. They differ in how they handle the outer segments, but neither calls a shared core. A shared constant is not an implementation, and each place that applies it counts. This matches the decided case "Two functions that each apply a shared pattern themselves", which is FAIL under L1.
- L2 met. All eight sites get their cells from `table_rows.py`, directly or through wrappers that add only row-shape logic.
- L3 met. No former splitter is left defined, called or dispatched to. The only remaining splitter outside `table_rows.py` is the out-of-scope `cited_works_removed`.

4. Commands run beyond reading: Grep searches only. I ran no reader on a row, because reading settled every site. I could not establish nothing that matters here. The rubric decided the case as written, since the decided case on two functions applying a shared pattern fits the tree exactly. Model id: claude-sonnet-5-5.

VERDICT: FAIL
