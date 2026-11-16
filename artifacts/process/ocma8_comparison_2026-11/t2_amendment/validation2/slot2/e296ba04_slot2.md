1. Places under `tree/scripts/` performing cell splitting (observed via `changes.diff` and grep):
- `stack_parse.py:222` (`iter_cells`, split executed `stack_parse.py:228-230` via `_UNESCAPED_PIPE.finditer`): IN SCOPE — the single implementation.
- Call sites applying it (not implementations; inline use plus only row-shape logic): `build_dashboard.py:386,418,623,801`; `build_fact_graph.py:236,240,396`; `docs_form_gate.py:289`; `learning_gate.py:57,137`; `reconstruct_state.py:229`; `release_gate.py:1306,1427`: all IN SCOPE uses.
- `docs_form_gate.py:327` (`cited_works_removed`, `line.split(" | ", 1)`): OUT OF SCOPE (rubric names it explicitly; tree leaves it unchanged).
- `gates/stacks_closure.py:95` (`_row_delimiters`, counts pipes): OUT OF SCOPE (unchanged baseline code; counting is not splitting in any case).
- `obligation_diff.py:35,43` (`SPLIT` regex with a `|` alternative, clause segmentation of prose): OUT OF SCOPE (unchanged; not table-row splitting).
- Row-matching regexes (`computational_contract_gate.py:653`, `docs_form_gate.py:310,626,775,874`, `release_gate.py:1468,1469,1481`, `gates/api_types.py:15`, `gates/docs.py:71`): OUT OF SCOPE (matching, not splitting; rubric says so). `learning_gate.py:60` (`re.split(r";\s*")`) splits a cell's content: not cell splitting by definition.

2. Eight sites — reader → where cells are split (all observed):
1. `build_dashboard.py` `deferred_section`/`references_section`/`order_section`/`_study_cards` → `iter_cells`, `stack_parse.py:228-230` (via lines 386/418/623/801; `strip`/`[1:-1]` is row-shape).
2. `build_fact_graph.py` `_all_tables` → `iter_cells` (lines 236/240).
3. `build_fact_graph.py` `reference_table_rows` → `iter_cells` (line 396).
4. `learning_gate.py` `ledger_rows`/`_is_mapping_header` → `iter_cells` (lines 57/137).
5. `release_gate.py` `roadmap_rows` → `iter_cells` (line 1427; `startswith("|")` guard is row-shape).
6. `release_gate.py` `table_data_rows` → `iter_cells` (line 1306; blockquote `lstrip(" \t>")` is row-shape per rubric).
7. `docs_form_gate.py` `parse_vocabulary` → `iter_cells` (line 289).
8. `reconstruct_state.py` `open_defect_classes` → `iter_cells` (line 229).

3. L1 met: exactly one in-scope splitter body exists (`iter_cells`); every baseline `_cells`/`_table_cells`/inline `split("|")` was deleted (no `def _cells`, no `split("|")` remain in `tree/scripts`). L2 met: all eight readers obtain cells from `iter_cells`, directly or with only strip/outer-pipe/None-guard wrappers. L3 met: no second splitter remains in changed code, called or uncalled.
4. Commands beyond reading: none (no shell tool in this environment; reading settled every site — each call site names `iter_cells` directly). Nothing material left unestablished. No rubric gap encountered; the only judgment call (pipe-counting is not splitting) follows the rubric's own definition. Model id: `muse-spark-1.3-contributor`. No files written (no write tool available; nothing in `tree/`/`baseline/` touched).
VERDICT: PASS