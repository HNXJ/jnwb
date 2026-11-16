Splitting inventory (tree/scripts): in-scope splitter: `scripts/rowcells.py:12` (`_scan`, def at :6; `if char == "|" ...` with backslash-escape check, :6-19) — IN SCOPE. `row_cells` (:22-24, `_scan(line.strip("|"))`) and `inner_cells` (:27-29, `_scan(line)[1:-1]`) only add row-shape (outer-pipe removal/segment drop) — wrappers, not implementations. No other in-scope splitter: no `def _cells`/`def _table_cells` remains; no inline `.split("|")`/`re.split(...\|...)` remains (verified by search). Out of scope: `docs_form_gate.py:327` (`line.split(" | ", 1)` in `cited_works_removed` — rubric explicitly excludes it); `computational_contract_gate.py:649-655` (`_first_cells` first-cell regex), `gates/api_types.py:15`, `gates/docs.py:71` (row/first-cell matching regexes), `obligation_diff.py:35` clause splitter — all unchanged baseline code outside the eight sites; `learning_gate.py:60-61` (`";"`/`":"` splits of cell contents — splitting a cell's content, not cells).

Eight sites (reader → cells split at):
1. `build_dashboard.py`: `deferred_section` (:623), `references_section` (:386), `order_section` (:418), `_study_cards` (:801) — all `inner_cells(line)`; split at `rowcells.py:12`.
2. `build_fact_graph.py` `_all_tables` (:236, :240) — `row_cells(...)`; split at `rowcells.py:12`.
3. `build_fact_graph.py` `reference_table_rows` (:396) — `row_cells(line)`; split at `rowcells.py:12`.
4. `learning_gate.py` `ledger_rows` (:57), `_is_mapping_header` (:137, via `mapping_tables`) — `row_cells(line.strip())`; split at `rowcells.py:12`.
5. `release_gate.py` `roadmap_rows` (:1427) — `row_cells(stripped)` guarded by `startswith("|")`; split at `rowcells.py:12`.
6. `release_gate.py` `table_data_rows` (:1306) — `row_cells(body)` after blockquote-marker strip; split at `rowcells.py:12`.
7. `docs_form_gate.py` `parse_vocabulary` (:289) — `row_cells(line)`; split at `rowcells.py:12`.
8. `reconstruct_state.py` `open_defect_classes` (:229) — `row_cells(line.strip())`; split at `rowcells.py:12`.
Each call site adds only `[c.strip() for c in ...]` / startswith guards — row-shape per rubric.

L1 met: exactly one in-scope splitter (`_scan`); two entry functions over one core is PASS per decided cases. L2 met: every reader above obtains cells from that core, directly or via row-shape-only wrappers. L3 met: all eight baseline splitters removed by the diff; no second splitter defined or dispatched to.

Commands: none beyond reading/grep (no shell tool available). Nothing unresolved: reading plus the diff settled every site; no run needed. No rubric gap encountered; first-cell regexes are decided by the scope exclusion. Model id: `muse-spark-1.3-contributor`.
VERDICT: PASS