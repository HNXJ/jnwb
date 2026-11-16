1. Places under `tree/scripts/` that split cells, all in scope. Each one applies `PIPE.split` itself.
- `scripts/build_dashboard.py:355`
- `scripts/build_fact_graph.py:226`
- `scripts/docs_form_gate.py:279` (a new `_cells`)
- `scripts/learning_gate.py:54`
- `scripts/reconstruct_state.py:225` (a new `_cells`)
- `scripts/release_gate.py:1291`

The shared constant is `scripts/mdpattern.py:5`, `PIPE = re.compile(r"(?<!\\)\|")`. It is a pattern, not an implementation.

Not counted:
- `scripts/docs_form_gate.py:330` (`cited_works_removed`, `split(" | ", 1)`) is out of scope by rule.
- `scripts/gates/stacks_closure.py:95` only counts pipes, so it does no cell splitting.
- No other cell splitting turned up in a search of `scripts/`.

2. The eight sites. Each reader gets its cells from a module-local `_cells` that applies `PIPE.split` itself.
1. `build_dashboard.py`: `_cells`, split at `build_dashboard.py:355`.
2. `build_fact_graph.py`: `_cells` through `_all_tables`, split at `build_fact_graph.py:226`.
3. `build_fact_graph.py`, `reference_table_rows`: now calls `_cells` at about line 400, so the split is at `build_fact_graph.py:226`.
4. `learning_gate.py`: `_cells`, split at `learning_gate.py:54`.
5. `release_gate.py`, `roadmap_rows`: `_cells` at `release_gate.py:1291`.
6. `release_gate.py`, `table_data_rows`: its former `_table_cells` is gone. It now calls the same `_cells`, split at `release_gate.py:1291`.
7. `docs_form_gate.py`, `parse_vocabulary`: the new `_cells`, split at `docs_form_gate.py:279`.
8. `reconstruct_state.py`, `open_defect_classes`: the new `_cells`, split at `reconstruct_state.py:225`.

3. Criteria.
- L1 not met. There are six bodies in six modules that each apply `PIPE.split` themselves. The rubric's decided cases list "Two functions that each apply a shared pattern themselves" and "A lambda or small function per module over one shared pattern" as FAIL.
- L2 not met. Sites 1, 2, 3, 4, 5, 6, 7 and 8 reach a splitter, but each one reaches its own module's copy, not one shared implementation. This is the "inline splits at the sites sharing one compiled pattern" pattern.
- L3 not met. Five splitter implementations remain beyond any single chosen one, for example `build_dashboard.py:355` and `learning_gate.py:54`.

4. Commands run beyond reading: `cat` on `mdpattern.py` and several `grep` searches of `tree/scripts`. I wrote no probe scripts, because the code settles every site by reading. I wrote nothing inside `notes/`.

Not established: nothing material for this verdict. The split locations are unambiguous.

The rubric decided every case as written. One judgement call: I treated `PIPE.split(...)` as cell splitting, because its Terms section says each place that applies a pattern to split a row is one implementation.

Model id: claude-sonnet-5-5.

VERDICT: FAIL
