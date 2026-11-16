1. Cell-splitting places under tree/scripts/ (I searched the directory for split, partition, finditer, translate and pipe patterns, and read the diff):
- scripts/cell_reader.py:8, `re.split(r"(?<!\\)\|", text)`. In scope. This is the shared implementation.
- scripts/build_fact_graph.py:401, `cells = "|".join(cells).split("|")`. In scope. It re-splits the cells that `read_cells` returned, on every pipe, escaped or not.
- scripts/docs_form_gate.py, `cited_works_removed` (defined at line 312). Out of scope by the rubric. I did not inspect its body.
- No other implementation in scripts/ splits table rows. The other `.split` hits are on ".", whitespace or other non-pipe delimiters.

2. The eight sites. Each reader gets its cells from `read_cells` at cell_reader.py:8, except site 3, which splits again.
1. build_dashboard.py `_cells` (line ~355) calls `read_cells(line)[1:-1]`. Readers: deferred_section, references_section, order_section, _study_cards. The split is at cell_reader.py:8.
2. build_fact_graph.py `_cells` (line 226) calls `read_cells`. Reader: `_all_tables`. The split is at cell_reader.py:8.
3. build_fact_graph.py `reference_table_rows` (line 400) calls `read_cells`, then line 401 does `"|".join(cells).split("|")`. The cells it uses come from that second split on the pipe. Split at build_fact_graph.py:401 on top of cell_reader.py:8.
4. learning_gate.py `_cells` calls `read_cells`. Readers: ledger_rows, _is_mapping_header. The split is at cell_reader.py:8.
5. release_gate.py `_cells` (line ~1294) calls `read_cells`. Reader: roadmap_rows. The split is at cell_reader.py:8.
6. release_gate.py `_table_cells` (line ~1302) calls `read_cells`. Reader: table_data_rows. The split is at cell_reader.py:8.
7. docs_form_gate.py parse_vocabulary (line 288) calls `read_cells`. The split is at cell_reader.py:8.
8. reconstruct_state.py open_defect_classes (line ~231) calls `read_cells`. The split is at cell_reader.py:8.

3. Criteria.
- L1 not met. There are two in-scope places that split cells: cell_reader.py:8, and build_fact_graph.py:401, which splits on the pipe again.
- L2 not met. Site 3 takes its cells from its own second split on the pipe after the shared call. The decided case "A site that takes cells from the shared splitter and splits them or the row again on the pipe" covers this exactly.
- L3 not met. The second splitter at build_fact_graph.py:401 is still in the in-scope code and the site uses it. The former splitters at the other sites are gone: each `_cells` or `_table_cells` is now a wrapper that adds only row-shape logic.

4. I ran no commands beyond reading and searching, with the Read and Grep tools. Nothing was left unestablished; the L2 and L1 failures show in the code as written, so I did not run the reader. The rubric decided the case as written. Model id: claude-sonnet-5-5.

VERDICT: FAIL
