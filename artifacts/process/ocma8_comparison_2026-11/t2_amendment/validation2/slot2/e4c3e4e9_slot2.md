Cell-splitting places under `tree/scripts/` (`path:line`, observed by reading):

In scope (each applies the shared pattern itself — rubric counts each applier as one implementation):
- `scripts/build_dashboard.py:355` — `_cells` does `PIPE.split(line)[1:-1]`. In scope (site 1).
- `scripts/build_fact_graph.py:226` — `_cells` does `PIPE.split(...)`. In scope (sites 2, 3).
- `scripts/learning_gate.py:54` — `_cells` does `PIPE.split(...)`. In scope (site 4).
- `scripts/release_gate.py:1291` — merged `_cells` does `PIPE.split(...)`. In scope (sites 5, 6).
- `scripts/docs_form_gate.py:279` — new `_cells` does `PIPE.split(...)`. In scope (site 7).
- `scripts/reconstruct_state.py:225` — new `_cells` does `PIPE.split(...)`. In scope (site 8).
- `scripts/mdpattern.py:5` — `PIPE = re.compile(r"(?<!\\)\|")` is a constant, not an implementation (rubric).

Out of scope / not cell splitting: `docs_form_gate.py:330` (`line.split(" | ", 1)` in `cited_works_removed` — rubric explicitly excludes it); `computational_contract_gate.py:653` (`_first_cells`, first-cell regex — rubric's out-of-scope example, unchanged); `gates/stacks_closure.py:95` (`_row_delimiters` counts pipes, never segments a row; unchanged baseline); `measure_agents_md_duplication.py:78` (`re.split` on sentence boundaries, not a table row).

Eight sites — reader → where its cells are split (all observed):
1. `build_dashboard.py` `deferred_section`/`references_section`/`order_section`/`_study_cards` call `_cells` (:390, :422, :627, :805) → split at :355.
2. `build_fact_graph.py` `_all_tables` (:240, :244) → :226.
3. `reference_table_rows` (:400 calls `_cells`, inline split gone) → :226.
4. `learning_gate.py` `ledger_rows` (:61), `_is_mapping_header` (:141) → :54.
5. `release_gate.py` `roadmap_rows` (:1428, with `startswith` guard as row-shape) → :1291.
6. `table_data_rows` (:1309 loop strips blockquote markers then calls `_cells`; stripping is row-shape only) → :1291. Old `_table_cells` deleted.
7. `docs_form_gate.py` `parse_vocabulary` (:292 calls new `_cells`) → :279.
8. `reconstruct_state.py` `open_defect_classes` (:235 calls new `_cells`) → :225.

Criteria: L1 NOT MET — six distinct bodies each perform splitting (`PIPE.split` applied in six places); rubric: "each place that applies it to split a row is one," and the decided case "two functions that each apply a shared pattern themselves → FAIL L1" decides it. L2 NOT MET — with no single implementation, readers obtain cells from six different splitters, not "that implementation." L3 NOT MET — five extra splitter bodies remain beyond any one candidate.

Commands run beyond reading: none; reading settled every site (each `_cells` visibly splits, each reader visibly calls it), so no runner scripts were needed. Could not establish: nothing material. Rubric gap: none — the shared-pattern case is decided verbatim. Model id: `muse-spark-1.3-contributor`.

VERDICT: FAIL