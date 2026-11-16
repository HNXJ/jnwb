# Validation 2: control specifications and expected verdicts (fixed 2026-11-16, before any tree is adjudicated)

Each tree is built from the T2 baseline (jnwb ac995dde) by a builder agent from the specification below, not
copied from an earlier control. The expected verdict is the literal reading of the task contract
(`predicates/t2_structure_rubric_r2.md`). Behaviour is not the question; every tree must import and pass
`accept/t2_preserved_test.py` unless its row says otherwise. Each tree uses its own module name and its own
splitting technique so that no two share wiring.

Expected PASS

| Tree | Specification | Technique of the one splitter |
|---|---|---|
| n1 | New module; one function; all eight sites call it directly; the five baseline functions deleted, their callers rewritten | regex with a lookbehind |
| n2 | New module; two public entry functions (outer pipes stripped; inner segments `[1:-1]`) that both call one private core function; neither entry function splits | character scan in the core |
| n3 | The splitter is a classmethod of a class in a new subpackage `scripts/<pkg>/`; the five baseline function names are kept as wrappers that delegate to it and add only row-shape logic; the three inline sites call it | replace an escaped pipe by a sentinel, split, restore |
| n4 | The splitter is a generator added to the existing `scripts/stack_parse.py`; sites reach it through `list(...)`, a `functools.partial` or a `map` | `re.finditer` generator |
| n5 | As n1, and `docs_form_gate.py` `cited_works_removed` (line 323) is also rewritten to use the shared splitter | regex split, then strip |

Expected FAIL

| Tree | Specification | Decided by |
|---|---|---|
| m1 | New module with two functions that each apply one module-level compiled pattern themselves (`PATTERN.split` in both), differing in outer-pipe handling; all eight sites call one of the two | L1 (the v1 class) |
| m2 | As n1, but one baseline splitter function (`release_gate._table_cells`, body unchanged) stays defined and nothing calls it | L3 |
| m3 | New module exporting only a compiled pattern; each of the six files defines a one-line lambda or function applying it; sites call their module's lambda | L1 |
| m4 | New module; one function with a keyword flag that turns escape handling off (plain `split("|")` branch); five sites pass the flag on, three pass it off | L1 (alternative splitting logic in one function) |
| m5 | As n1 for data rows, but `release_gate.table_data_rows` decides the separator row with its own `line.strip().strip("|").split("|")` | L2 |
| m6 | New module; seven sites call the shared function; `reconstruct_state.open_defect_classes` finds its cells with a `partition("|")` loop and no `split` | L2 |
| m7 | New module; all eight sites call the shared function, and `build_fact_graph.reference_table_rows` then joins the cells and splits again on the pipe to obtain the cells it uses | L2 |

Five expected PASS, seven expected FAIL. The earlier controls v1 (now the class of m1) and any tree with a
retained uncalled splitter change class under the literal reading; their recorded 23-tree verdicts are not
rewritten.
