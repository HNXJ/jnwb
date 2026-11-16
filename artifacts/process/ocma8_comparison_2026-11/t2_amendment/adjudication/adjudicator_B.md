| label | verdict | deciding criterion or anchor | effective delimiter logic | evidence |
|---|---|---|---|---|
| k01 | PASS | PASS anchor (one function, all sites) | scripts/md_cells.py:13-24 (split_cells, char scan) | All 8 sites call split_cells directly or via _row_cells/_table_row_cells wrappers; no baseline splitter left. |
| k02 | PASS | PASS anchor | scripts/md_cells.py:14-16 (regex split) | Same call sites as k01, all through split_cells; baseline splitters removed. |
| k03 | PASS | PASS anchor (map/thin wrapper) | scripts/md_cells.py:14-16 | Release wrappers call next(map(split_cells,[x])); other sites call split_cells; one implementation. |
| k04 | PASS | PASS anchor (subpackage, one core) | scripts/tables/cells.py:7-19 (_SEP, _split_body via row_cells) | All 8 sites call _tc.row_cells; dashboard/fact_graph readers renamed only. |
| k05 | FAIL | F1/F2 | build_dashboard.py:354, build_fact_graph.py:225,399, learning_gate.py:53, release_gate.py:1293,1301, docs_form_gate.py:285, reconstruct_state.py:224 | Tree has no md_cells; every site still has its own re.split(r"(?<!\)\|") copy. |
| k06 | FAIL | F3 (also S3: second body of logic live) | scripts/md_cells.py:6-9 (_s1 sentinel), md_cells.py:25-27 (regex fallback) | split_cells dispatches by site= tag through a per-tag _IMPLS table; a second regex splitter stays reachable as the site=None path. |
| k07 | PASS | PASS anchor | scripts/md_cells.py:4-8 (sentinel replace + split) | All 8 sites reach split_cells directly or via thin _cells wrappers (build_fact_graph.py:225, learning_gate.py:53); no inline split remains. |
| k08 | PASS | PASS anchor (two entry functions over one shared pattern) | scripts/table_cells.py:6-15 (_PIPE; padded_cells, inner_cells) | Dashboard uses inner_cells ([1:-1] shape), the other 7 sites use padded_cells; both split by the same _PIPE regex and differ only in row shape. |
| k09 | FAIL | F1/F6 | baseline code unchanged (build_dashboard.py:354, build_fact_graph.py:225,399, learning_gate.py:53, release_gate.py:1293,1301, docs_form_gate.py:285, reconstruct_state.py:224) | git status shows no change; all baseline splitters in place. |
| k10 | FAIL | F1 | md_cells.py:6 used by dashboard/learning/release; inline split remains at build_fact_graph.py:398, docs_form_gate.py:285, reconstruct_state.py:224 | Sites 3, 7, 8 still split inline with .split("|"). |
| k11 | FAIL | F2 | scripts/md_cells.py:11-52 (split_cells_1..split_cells_6) | Six byte-identical splitter copies, each imported (aliased) by a different module. |
| k12 | FAIL | F2 | build_dashboard.py:87-89, build_fact_graph.py:191-193, learning_gate.py:37-39, release_gate.py:68-70, docs_form_gate.py:85-87, reconstruct_state.py:49-51 | A translate/split copy is defined in each of six modules (plus an unused md_cells.py); each site uses its local copy. |
| k13 | PASS | PASS anchor (generator over finditer) | scripts/md_cells.py:5-17 (iter_cells, split_cells) | Same call-site diff as k01; all sites reach split_cells. |
| k14 | FAIL | F5 | build_fact_graph.py:236,240,396, learning_gate.py:57, release_gate.py:1294,1302, docs_form_gate.py:288, reconstruct_state.py:227 (each PIPE.split(...)) | Sites share only the PIPE pattern constant; each runs its own split(line.strip().strip("|")) inline. |
| k15 | PASS | PASS anchor (splitter added to an existing module) | scripts/stack_parse.py:~220-236 (table_cells, char scan) | All sites call _STRIP/_SLICE = table_cells(line[, True]); stack_parse had no other row splitter; baseline splitters removed. |
| k16 | PASS | PASS anchor | scripts/md_cells.py:14-16 | Same as k01 except site 3 filters empty cells after split_cells (row-shape only). |
| k17 | PASS | PASS anchor (class staticmethod, alias) | scripts/md_cells.py:11-15 (Row.cells) | Each module aliases split_cells = Row.cells; all sites use it. |
| k18 | PASS | PASS anchor | scripts/md_table.py:7-11 (cells) | All sites via _c/_STRIP/_SLICE and wrappers; dead _study_rows stub (calls an undefined name) is never called and holds no delimiter logic. |
| k19 | FAIL | F2 | build_dashboard.py, build_fact_graph.py, docs_form_gate.py, learning_gate.py, reconstruct_state.py, release_gate.py (each defines its own split_cells with re.split) | Identical splitter copy defined in each of six modules; no shared module. |
| k20 | PASS | PASS anchor (object/method) | scripts/mdtable/rows.py:5-11 (RowSplitter.cells, ROWS) | All sites call ROWS.cells; baseline splitters removed. |
| k21 | PASS | PASS anchor (partial) | scripts/md_cells.py:11-17 (split_cells, partial split_cells_outer) | Dashboard uses the partial, the rest split_cells; one body. |
| k22 | FAIL | F2 | _part_split defined in build_dashboard.py, build_fact_graph.py, docs_form_gate.py, learning_gate.py, reconstruct_state.py, release_gate.py (partition loop) | Identical partition-based splitter copied into each of six modules; no shared module. |
| k23 | PASS | PASS anchor | scripts/md_cells.py:6-7 (cells, [1:-1] regex split) | All 8 sites import cells (aliased _cells/_table_cells); baseline splitters and release_gate wrappers deleted. Row-shape/behaviour changes (no outer-strip, no non-row None) were not judged. |

Commands beyond reading: git status --porcelain and git diff HEAD per tree, md5sums of diffs and md_cells.py to find identical trees, grep for residual split sites and for shadowing defs/aliases, diff of each tree's diff against k01's. No Python was run, no trees modified.

Least sure:
- k08: two entry functions each calling _PIPE.split; judged PASS by the "two entry functions over one shared pattern, differing in row shape" anchor, not F5, since the splitting lives in the shared module. Reads as F5-adjacent.
- k06: all per-site impls share one body, and the fallback is a regex (not just a dispatch to different logic); FAIL on F3 and S3 (a second live splitter) rather than F2.
- k23: structure passes; behaviour of dropped row-shape logic in release_gate and fact_graph not examined.
- No tree was run; import validity (sys.path placement) was read, not executed.

Model: claude-sonnet-5-5
