1. Cell-splitting places under `tree/scripts/`:
- `scripts/tableio/cells.py:16`, `CellSplitter.split`: `text.replace("\\|", U+E000)`, then `.split("|")`, then restore. It is in scope, and it is the only one.
- The pipe-related code below is not table-cell splitting:
  - `scripts/gates/stacks_closure.py:95` counts unescaped pipes in a row. It is row-shape logic and baseline code the tree leaves unchanged, so it is out of scope.
  - `scripts/obligation_diff.py:35` and `:43`, `SPLIT.split`, cuts prose clauses on sentence punctuation or `|`. It is not a table row, and it is baseline code the tree leaves unchanged, so it is out of scope.
  - `scripts/push_guard.py:31` splits shell command segments. It is out of scope.
  - `scripts/learning_gate.py:63`, `re.split(r";\s*", ...)`, splits a cell's content on `;`. That is not cell splitting.
  - `scripts/docs_form_gate.py:310`, `:626`, `:775` and `:874`, and `scripts/reconstruct_state.py:48`, are regexes that match a row's first cell or the separator row. They are out of scope.
  - `docs_form_gate.py`, `cited_works_removed`, is explicitly out of scope.
- I found no other `.split("|")`, `partition`, `chr(124)`, `\x7c` or character-scan splitter. `[1:-1]` appears only as row-shape logic.

2. The eight sites. Each reader's wrapper does only strip, outer-pipe removal or `[1:-1]`, then calls `CellSplitter.split` (`cells.py:16`).
- Site 1, `build_dashboard.py`: `_cells` at `:354-355` (`deferred_section`, `references_section`, `order_section` and `_study_cards` via `:390`, `:422`, `:627`, `:805`).
- Site 2, `build_fact_graph.py`: `_cells` at `:225-226`, read by `_all_tables` at `:240` and `:244`.
- Site 3, `build_fact_graph.py:400`, `reference_table_rows`: calls `CellSplitter.split` inline.
- Site 4, `learning_gate.py`: `_cells` at `:53-54`, used by `ledger_rows` (`:61`) and `_is_mapping_header` (`:141`).
- Site 5, `release_gate.py`: `_cells` at `:1290-1294`, used by `roadmap_rows` (`:1436`).
- Site 6, `release_gate.py`: `_table_cells` at `:1297-1302`, used by `table_data_rows` (`:1317`). `_is_separator` works on cells it is given.
- Site 7, `docs_form_gate.py:289`, `parse_vocabulary`: calls `CellSplitter.split` inline. The import and `sys.path` setup are at `:78-81`.
- Site 8, `reconstruct_state.py:229`, `open_defect_classes`: calls `CellSplitter.split` inline. The import is at `:42-46`.

3. Criteria.
- L1 is met. Only `cells.py:16` performs cell splitting. It is one class with one classmethod and no per-site branches or arguments.
- L2 is met. All eight readers get their cells from `CellSplitter.split`. The header and separator paths use the same wrappers, and no site splits the cells again on the pipe.
- L3 is met. None of the eight baseline splitters (the regex `_cells` and the `.split("|")` forms) remain. The `_cells` and `_table_cells` functions that remain are wrappers over `CellSplitter`. No defined-but-uncalled splitter exists.

4. Commands run beyond reading: Grep and `grep` searches over `tree/scripts` for split, partition, find, pipe literals and regexes. I read the diff, `cells.py` and `__init__.py`. I ran no reader and wrote no files, so `notes/` was not created. I confirmed the sentinel is the 3-byte character U+E000 (bytes `ee 80 80`), not an empty string.
- Not established: nothing material. I did not execute any code, because reading settled every site.
- The rubric did not decide two borderline cases as written. `obligation_diff.SPLIT` splits prose on `|` but is not a table-row split, and `stacks_closure.py:95` only counts pipes. I treated both as out of scope, because they are unchanged baseline code and not among the eight sites. If either were counted, the verdict would change.
- Model id: claude-sonnet-5-5.

VERDICT: PASS
