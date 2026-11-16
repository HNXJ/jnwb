Cell-splitting places under `tree/scripts/` (`path:line`; observed by grep/read/diff):
- `table_rows.py:10` (`PATTERN.split` in `split_stripped`) — in scope (added).
- `table_rows.py:15` (`PATTERN.split` in `split_inner`) — in scope (added).
- `release_gate.py:1294` (`return split_stripped(stripped)` in `_cells`) and `release_gate.py:1302` (same in `_table_cells`) — in scope but wrappers only (row-shape: `startswith("|")` guard, blockquote stripping, `None` for non-rows); not implementations.
- `docs_form_gate.py:326` (`line.split(" | ", 1)` in `cited_works_removed`) — out of scope (rubric names it explicitly).
- `learning_gate.py:60` (`re.split(r";\s*", cells[2])`) — not cell splitting (splits a cell's content on `;`); not a splitter.
- `gates/stacks_closure.py:95` (`.count("|")` after escaped-pipe removal) and `computational_contract_gate.py:653` (regex matching a row's first cell) — out of scope (unchanged baseline files, none of the eight sites; rubric exempts first-cell regexes). No `chr(124)`/`\x7c`/`csv`/char-loop splitters found anywhere.

Eight sites (readers found by behavior; all names unchanged):
1. `build_dashboard.py` (`deferred_section`, `references_section`, `order_section`, `_study_cards`, call sites :386,:418,:623,:801) → `split_inner` → split at `table_rows.py:15`.
2. `build_fact_graph.py` `_all_tables` (:236,:240) → split at `table_rows.py:10`.
3. `build_fact_graph.py` `reference_table_rows` (:396) → `table_rows.py:10`.
4. `learning_gate.py` `ledger_rows` (:57), `_is_mapping_header` (:137) → `table_rows.py:10`.
5. `release_gate.py` `roadmap_rows` (:1436 via `_cells`) → `table_rows.py:10`.
6. `release_gate.py` `table_data_rows` (:1317 via `_table_cells`) → `table_rows.py:10`.
7. `docs_form_gate.py` `parse_vocabulary` (:288) → `table_rows.py:10`.
8. `reconstruct_state.py` `open_defect_classes` (:231 per diff) → `table_rows.py:10`.

L1 (one implementation): NOT MET — `split_stripped` (`PATTERN.split(line.strip().strip("|"))`) and `split_inner` (`PATTERN.split(line)[1:-1]`) each apply the shared `PATTERN = re.compile(r"(?<!\\)\|")` themselves, the rubric's decided FAIL case verbatim.
L2 (all sites use it): NOT MET as written — sites 2–8 share one function but site 1's readers use the other; no single implementation serves all eight (no site splits for itself).
L3 (others gone): MET — baseline `_cells`/inline splits removed (diff), remaining `_cells`/`_table_cells` add only row-shape logic, and the only other pipe cut is the out-of-scope `cited_works_removed`.

Commands beyond reading: none (no shell tool exposed, so no reader runs; reading settles every site since each call site names its splitter). Nothing material left unestablished; the rubric decided this case exactly, so no gap. Model id: `muse-spark-1.3-contributor`.
VERDICT: FAIL