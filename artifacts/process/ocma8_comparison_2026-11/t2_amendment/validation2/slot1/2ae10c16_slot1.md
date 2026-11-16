1. Places under `tree/scripts/` that split cells:
- `scripts/cellsplit.py:8`, `split_cells`, in scope. This is the shared splitter.
- `scripts/release_gate.py:1295`, `_table_cells`, in scope. It is a retained baseline splitter (`body.strip("|").split("|")`), and nothing calls it. A grep for `_table_cells` in `scripts/` finds only its definition at line 1290.
- A grep of `scripts/` for pipe splits found no other place. I did not run the readers.

2. The eight sites, with the reader and where its cells are split:
1. `build_dashboard.py`: `references_section` (386), `order_section` (418), `deferred_section` (623) and `_study_cards` (801). All call `split_cells(line)[1:-1]`, which splits at `cellsplit.py:8`.
2. `build_fact_graph.py`: `_all_tables` (236, 240). It calls `split_cells(... .strip("|"))`, which splits at `cellsplit.py:8`.
3. `build_fact_graph.py`: `reference_table_rows` (396). It calls `split_cells(line.strip("|"))`, which splits at `cellsplit.py:8`.
4. `learning_gate.py`: `ledger_rows` (57) and `_is_mapping_header` (137). Both call `split_cells`, which splits at `cellsplit.py:8`.
5. `release_gate.py`: `roadmap_rows` (1432). It calls `split_cells`, which splits at `cellsplit.py:8`.
6. `release_gate.py`: `table_data_rows` (1311-1313). The loop now holds the row-shape logic inline and calls `split_cells`, so it splits at `cellsplit.py:8`. The old `_table_cells` is no longer called.
7. `docs_form_gate.py`: `parse_vocabulary` (288). It calls `split_cells`, which splits at `cellsplit.py:8`.
8. `reconstruct_state.py`: `open_defect_classes` (231). It calls `split_cells`, which splits at `cellsplit.py:8`.

3. Criteria:
- L1: not met. Two splitter implementations stand in scope, `split_cells` (`cellsplit.py:8`) and `_table_cells` (`release_gate.py:1295`).
- L2: met. All eight readers get their cells from `split_cells`, and the wrappers around it add only row-shape logic (`strip("|")`, `[1:-1]`, blockquote removal). No site splits for itself and none splits a row again.
- L3: not met. `_table_cells` is a former splitter, left defined and called by nothing. The rubric's decided case "All eight sites on the shared splitter and a former splitter left defined, called by nothing" is FAIL by L3.

4. Commands run: only `grep` and `git status` for reading. I ran no readers and wrote no files. I created no `notes/` directory because I had nothing to write.
- Not established: I did not run the readers. Reading settled every site.
- Rubric gaps: none. The decided case above covers this tree as written.
- Model id: claude-sonnet-5-5.

VERDICT: FAIL
