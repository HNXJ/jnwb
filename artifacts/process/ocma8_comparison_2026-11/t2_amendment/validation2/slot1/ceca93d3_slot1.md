1. Cell splitting under tree/scripts/:
- scripts/tablecells.py:10 `split_cells` (regex `(?<!\\)\|` split, trim). In scope. This is the shared implementation.
- scripts/reconstruct_state.py:224-230 inline `str.partition("|")` loop, in `open_defect_classes`. In scope (site 8). It splits on every pipe and ignores escaped pipes.
- scripts/docs_form_gate.py:326 `line.split(" | ", 1)` in `cited_works_removed`. Out of scope per the rubric.
- scripts/gates/stacks_closure.py:95 only strips escaped pipes and counts pipes. That is row-shape logic, not cell splitting.
- The other pipe-related regexes I grepped match a row's first cell or split prose, not cells. Out of scope.

2. Sites, reader and where cells are split:
1. build_dashboard.py: `_cells` (line 354) calls `split_cells` (tablecells.py:10) and then slices `[1:-1]`. Row-shape only. Readers are `deferred_section`, `references_section`, `order_section` and `_study_cards`.
2. build_fact_graph.py: `_cells` (line 225-226) calls `split_cells`, which splits at tablecells.py:10.
3. build_fact_graph.py:400 `reference_table_rows` calls `split_cells`, which splits at tablecells.py:10.
4. learning_gate.py: `_cells` (line 53-54) calls `split_cells`, which splits at tablecells.py:10.
5. release_gate.py: `_cells` (line 1294) calls `split_cells`, which splits at tablecells.py:10.
6. release_gate.py: `_table_cells` (line 1302) calls `split_cells`, which splits at tablecells.py:10.
7. docs_form_gate.py:288 `parse_vocabulary` calls `split_cells`, which splits at tablecells.py:10.
8. reconstruct_state.py:224-230 `open_defect_classes` still builds its own cells with the `partition` loop. It never imports or calls `split_cells`. The diff confirms it, and the import list in the diff has no `tablecells` for this file. This is the site's own split, so its cells do not come from the shared implementation.

3. Criteria:
- L1 not met. Two implementations exist in scope: `split_cells` (tablecells.py:10) and the `partition` loop (reconstruct_state.py:224-230). They are different bodies with different escape handling.
- L2 not met. Site 8 splits for itself. Rubric decided cases "Any site still splitting for itself, in any technique" and "Inline splits at the sites" give FAIL.
- L3 not met. A second splitter implementation remains in the in-scope code, and site 8 uses it. The other seven sites' old splitters are gone. Their `_cells` and `_table_cells` are now row-shape wrappers around `split_cells`.

4. Commands run beyond reading: grep over tree/scripts for split, partition, finditer and pipe patterns. I did not run a reader on a row, because reading settled every site. Nothing is unestablished. The rubric decided the case as written. Model id: claude-sonnet-5-5.

Deciding criterion: L1, L2 and L3 all fail on site 8.

VERDICT: FAIL
