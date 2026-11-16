1. Places under `tree/scripts/` performing cell splitting (observed by reading diff + grep):
- `scripts/md_table.py:10` (`split_row`, `_UNESCAPED_PIPE.split` at line 15) — in scope (the replacement).
- `scripts/docs_form_gate.py:327` (`line.split(" | ", 1)` in `cited_works_removed`) — out of scope (rubric §Scope explicitly ignores it).
- No other body splits a table line on pipes: old `_cells`/`_table_cells`/inline `.split("|")`/`re.split` forms are deleted (diff observed; grep for `def _cells|def _table_cells` finds none; `strip("|")` hits only wrap `split_row`). Other `split`/`partition`/`finditer` hits split on `.`, `;`, `::`, `:`, whitespace etc., i.e. not table-cell splitting (observed), and unchanged non-site code is out of scope anyway.

2. Eight sites — reader → split location (all observed in tree):
1. `build_dashboard.py` `deferred_section:623`, `references_section:386`, `order_section:418`, `_study_cards:801` → cells from `split_row` at each line.
2. `build_fact_graph.py` `_all_tables:236,240` (read by `read_facts`/`read_constants`) → `split_row`.
3. `build_fact_graph.py` `reference_table_rows:396` → `split_row`.
4. `learning_gate.py` `ledger_rows:57`, `_is_mapping_header:137` → `split_row`.
5. `release_gate.py` `roadmap_rows:1427` → `split_row`.
6. `release_gate.py` `table_data_rows:1306` → `split_row`.
7. `docs_form_gate.py` `parse_vocabulary:289` → `split_row`.
8. `reconstruct_state.py` `open_defect_classes:229` → `split_row`.
Each call site adds only row-shape logic (`strip`, `strip("|")`, `[1:-1]`, `startswith("|")`/blockquote-strip guards, separator/header checks) — not implementations per Terms.

3. Criteria:
- L1 met: exactly one in-scope splitting body exists, `md_table.py:10 split_row`; no per-site/flag branches, no second applier of the pattern.
- L2 met: all eight readers obtain cells directly from `split_row` through wrappers adding only row-shape logic.
- L3 met: no former splitter remains defined or called; no uncalled splitter left (grep + diff show deletions complete).
4. Commands: none beyond reading (no shell/file-write tool available); created no files. Nothing unresolved — every site's split point was located by reading. Rubric decided the case as written; no gap. Single shared splitter with per-convention wrappers is the decided PASS case.
Model id: `muse-spark-1.3-contributor` (provider `opencode-go`, name `Muse Spark 1.3 Contributor`).

VERDICT: PASS
