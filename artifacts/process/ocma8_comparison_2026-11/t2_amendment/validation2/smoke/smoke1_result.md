Adjudication attempted; blocked on the rubric itself. Report (words counted under 600):

1. Places under `tree/scripts/` that perform cell splitting (all observed by grep/read; scope marking requires the rubric, which I could not read — every scope below is UNKNOWN):
- `scripts/md_cells.py:13` — `re.split(r"(?<!\\)\|", body)` inside `split_cells()`; the single shared splitter (strips outer pipes unless `keep_outer`, strips each cell).
- `scripts/build_dashboard.py:355` — `_row_cells()` via `split_cells(line, keep_outer=True)[1:-1]`.
- `scripts/build_fact_graph.py:236` — `_all_tables()` header via `split_cells(line)`.
- `scripts/build_fact_graph.py:240` — `_all_tables()` body rows via `split_cells(lines[i])`.
- `scripts/build_fact_graph.py:396` — `reference_table_rows()` via `split_cells(line)`.
- `scripts/docs_form_gate.py:288` — `parse_vocabulary()` via `split_cells(line)`.
- `scripts/learning_gate.py:57` — `ledger_rows()` via `split_cells(line)`.
- `scripts/learning_gate.py:137` — `_is_mapping_header()` via `split_cells(line)` (membership test only).
- `scripts/reconstruct_state.py:227` — `open_defect_classes()` via `split_cells(line)`.
- `scripts/release_gate.py:1294` — `_row_cells()` via `split_cells(stripped)`.
- `scripts/release_gate.py:1302` — `_table_row_cells()` via `split_cells(body)` (blockquote markers stripped first).
- `scripts/docs_form_gate.py:326` — `cited_works_removed()` via `line.split(" | ", 1)`, first-cell split only; the one row-splitting site not routed through `split_cells`.
- Literal greps for `split("|")` / `split('|')` under `tree/scripts/` found no remaining naive pipe splits (observed).

2. The eight designated sites (reader + split location): COULD NOT ESTABLISH. The rubric defines the sites; it was unreadable (see §4). The candidate reader→split mapping above is observed code, not an adjudication, and I do not know which eight the rubric designates.

3. L1: not established — rubric unread, no criterion text to apply. L2: not established — same reason. L3: not established — same reason; one sentence each as instructed, evidence being the missing rubric.

4. Commands run beyond reading: NONE — this session exposes no shell tool (only glob/grep/read/skill/webfetch/websearch), so `git status`, `git diff`, and any reader-on-a-row script were impossible; no script was written since it could not be executed, and `notes/` lies outside the accessible root so nothing was written there either. Could not establish: the rubric's question, terms, eight sites, scope boundaries, L1–L3, the baseline-vs-tree diff, and all runtime behavior. Rubric passages that did not decide the case as written: the entire rubric — `D:/repos/_adj_smoke/7f03d871/RUBRIC.md` read was denied (`Permission denied: external_directory`; work root confined to `tree/`), and `baseline/` is likewise unreachable. Exact model id: `muse-spark-1.3-contributor`.

VERDICT: UNRESOLVED
