## 1. Places under `tree/scripts/` performing cell splitting

- `md_cells.py:13` — `re.split(r"(?<!\\)\|", body)` inside `split_cells` — **in scope** (the single shared implementation; new file `scripts/md_cells.py` is the only untracked file).
- `build_dashboard.py:355` (`_row_cells`), `release_gate.py:1294` (`_row_cells`), `release_gate.py:1302` (`_table_row_cells`) — **in scope, not implementations**: each only calls `split_cells` and adds row-shape logic (outer-segment slice `[1:-1]`, `startswith("|")`/`None` guard, blockquote-marker strip).
- Former splitters are gone (observed in `changes.diff` deletions, no remaining `split("|")`/`strip("|").split` on pipes anywhere in `tree/scripts/`): baseline `_cells` bodies in `build_dashboard.py`, `build_fact_graph.py`, `learning_gate.py`, `release_gate.py` (both) and the three inline splits — all removed or replaced by a `split_cells` call.
- Out of scope / not cell splitting: `docs_form_gate.py:326` (`line.split(" | ", 1)` in `cited_works_removed` — rubric explicitly excludes it); `computational_contract_gate.py:653` (regex matching a row's first cell — unchanged baseline, rubric excludes); `gates/stacks_closure.py:95` (counts unescaped pipes, yields no cells — unchanged baseline); `learning_gate.py:60` (`re.split(r";\s*")` splits a cell's content — rubric excludes); `measure_agents_md_duplication.py:78`, `gates/stacks_pointers.py:66` (split prose, not table rows; unchanged).

## 2. The eight sites — reader and where its cells are split

1. `build_dashboard.py`: `references_section:390`, `order_section:422`, `deferred_section:627`, `_study_cards:805` → via `_row_cells` → `md_cells.py:13`.
2. `build_fact_graph.py`: `_all_tables:236,240` → `md_cells.py:13` directly.
3. `build_fact_graph.py`: `reference_table_rows:396` → `md_cells.py:13` directly.
4. `learning_gate.py`: `ledger_rows:57`, `_is_mapping_header:137` → `md_cells.py:13` directly.
5. `release_gate.py`: `roadmap_rows:1436` → via `_row_cells` → `md_cells.py:13`.
6. `release_gate.py`: `table_data_rows:1317` → via `_table_row_cells` → `md_cells.py:13`.
7. `docs_form_gate.py`: `parse_vocabulary:288` → `md_cells.py:13` directly.
8. `reconstruct_state.py`: `open_defect_classes:227` → `md_cells.py:13` directly.

## 3. Criteria

- L1 met: exactly one in-scope body performs cell splitting (`md_cells.py:10-13`); the `keep_outer` flag only selects outer-pipe removal (row-shape logic), escape handling is identical in both branches, so it is one implementation, not per-site branches.
- L2 met: every reader above takes its cells from `split_cells`, directly or through wrappers adding only row-shape logic; no site re-splits on the pipe.
- L3 met: no second splitter remains in in-scope code — old bodies deleted, none left defined-and-uncalled, none dispatched to.

## 4. Method and gaps

- Commands run beyond reading: none — this environment exposes no shell tool, so no reader was executed; reading settles it because every call site is a one-line substitution passing the row straight through. Nothing material is unestablished.
- One rubric borderline, decided by scope rather than text: `stacks_closure.py:95` counts (not produces) cells, and the rubric does not say whether counting is "splitting" — moot, since it is unchanged baseline code and therefore out of scope either way.
- Model id: `muse-spark-1.3-contributor`.

VERDICT: PASS