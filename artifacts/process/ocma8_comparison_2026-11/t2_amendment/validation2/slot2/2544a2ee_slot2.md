## 1. Places under `tree/scripts/` performing cell splitting

- `tree/scripts/md_split.py:11` — `UNESCAPED_PIPE.split(line)` (escape-aware branch). **In scope** (the replacement splitter).
- `tree/scripts/md_split.py:12` — `line.split("|")` (plain branch, `escapes=False`). **In scope**.
- `tree/scripts/docs_form_gate.py:326` — `line.split(" | ", 1)` in `cited_works_removed`. **Out of scope** (the rubric's stated exclusion).
- Examined and not splitters: `tree/scripts/gates/stacks_closure.py:95` (`_ESCAPED_PIPE.sub("", line).count("|")`) only counts pipes — "counting cells" is row-shape logic per the rubric, and it is unchanged baseline code (baseline lines 94–95 identical). All other `split`/`partition` hits split on `.`, `/`, `;`, whitespace, `\n`, etc., never a table row on a pipe. Grep confirms no remaining `split("|")`, `re.split` on `\|`, `chr(124)`, or character-loop pipe scan anywhere else in `tree/scripts/`.

## 2. The eight sites (found by reader behavior; all route to `split_row`)

| # | Reader (tree location) | Cells split at |
|---|---|---|
| 1 | `build_dashboard.py:390,422,627,805` (`references_section`, `order_section`, `deferred_section`, `_study_cards`) via `_cells` (`:354-355`, `split_row(line)[1:-1]`) | `md_split.py:11` |
| 2 | `build_fact_graph.py:229` `_all_tables` via `_cells` (`:225-226`); read by `read_facts`, `read_constants` et al. | `md_split.py:11` |
| 3 | `build_fact_graph.py:400` `reference_table_rows` calls `split_row` directly | `md_split.py:11` |
| 4 | `learning_gate.py:61,141` (`ledger_rows`, `_is_mapping_header` for `mapping_tables`) via `_cells` (`:53-54`) | `md_split.py:11` |
| 5 | `release_gate.py:1436` `roadmap_rows` via `_cells` (`:1290-1294`, `escapes=False`) | `md_split.py:12` |
| 6 | `release_gate.py:1317` `table_data_rows` via `_table_cells` (`:1297-1302`, default escapes) | `md_split.py:11` |
| 7 | `docs_form_gate.py:288` `parse_vocabulary`, `escapes=False` | `md_split.py:12` |
| 8 | `reconstruct_state.py:231` `open_defect_classes`, `escapes=False` | `md_split.py:12` |

## 3. Criteria

- **L1 One implementation: NOT met.** `split_row` holds two alternative cell-splitting bodies chosen by its `escapes` argument (`:11` regex split vs `:12` plain split), which the Terms count as several implementations — the rubric's own example is "a flag that turns escape handling off for some sites," exactly what sites 5/7/8 (`escapes=False`) vs 1/2/3/4/6 (default `True`) do.
- **L2 All sites use it: met.** Every reader above obtains its cells from `split_row` directly or through `_cells`/`_table_cells` wrappers that add only row-shape logic (outer-pipe strip, `[1:-1]` slice, `None` for non-rows, separator recognition).
- **L3 The others are gone: met.** The diff shows all eight baseline splitters replaced, and grep finds no other in-scope pipe-splitting body left defined, called or uncalled (`:326` is explicitly out of scope).

## 4. Method, gaps, identity

- Commands run beyond reading: none — no shell or write tool is exposed in this session, so no reader run and no `notes/` file was created; reading (diff + full grep + targeted reads) settled every call path, and both `escapes` branches are observably dispatched to at the call sites above.
- What I could not establish: nothing material; no site needed a runtime read to trace.
- Rubric gap: none as written — the flag-with-per-site-branches case is decided explicitly and matches this tree.
- Model id: `muse-spark-1.3-contributor` (per the dispatch header of this session).

VERDICT: FAIL