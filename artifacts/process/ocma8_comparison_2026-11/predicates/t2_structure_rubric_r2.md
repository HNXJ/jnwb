# T2 structural adjudication rubric, revision 2 (Hamm 2026-11-16, literal reading; frozen before validation 2)

Supersedes `t2_structure_rubric.md` (kept as written). Changed: the criteria are the literal task contract and
take precedence over every example; an implementation is counted where splitting is performed; a retained,
uncalled splitter fails; the scope is stated.

## Question

After the change, does `scripts/` hold exactly one implementation that splits a markdown table row into cells,
do all eight designated sites obtain their cells from it, and are the other splitter implementations gone? The
answer is `PASS`, `FAIL` or `UNRESOLVED`, with evidence. Judge what the code does and how it is built, never
spelling, names or file layout. Whether the cells come out right is scored elsewhere and is not your question:
a tree with wrong cells and one implementation passes; a tree with right cells and two fails.

## The eight designated sites (baseline ac995dde, `scripts/`)

| # | File | Baseline form | Readers that go through it |
|---|---|---|---|
| 1 | `build_dashboard.py` | `_cells` (regex split, slice `[1:-1]`) | `deferred_section`, `references_section`, `order_section`, `_study_cards` |
| 2 | `build_fact_graph.py` | `_cells` | `_all_tables`, which `read_facts`, `read_constants` and others read |
| 3 | `build_fact_graph.py` | inline split, line 399 | `reference_table_rows` |
| 4 | `learning_gate.py` | `_cells` | `ledger_rows`, `_is_mapping_header` (`mapping_tables`) |
| 5 | `release_gate.py` | `_cells` | `roadmap_rows` |
| 6 | `release_gate.py` | `_table_cells` | `table_data_rows` |
| 7 | `docs_form_gate.py` | inline split, line 285 | `parse_vocabulary` |
| 8 | `reconstruct_state.py` | inline split, line 224 | `open_defect_classes` |

Find each reader in the tree by what it reads, not by its baseline name: functions may be renamed, split or moved.

## Terms

- Cell splitting: deciding where one cell ends and the next begins in a table line (header, separator or data
  row), including the treatment of an escaped pipe. Any technique counts: `split`, a regex, `partition`,
  `find`, a character scan, `translate` then split, `csv`, a state machine.
- Splitter implementation: a body of code that itself performs cell splitting: a function, method, lambda,
  generator or inline expression. Count the places where splitting is performed, not the functions on a call
  path.
  - A constant (a compiled pattern, a delimiter string) is not an implementation. Each place that applies it
    to split a row is one.
  - A wrapper that calls the implementation and adds only row-shape logic is not an implementation.
  - One body may take several steps (replace then split, split then re-join, a private helper that only it
    calls): that is one implementation.
  - One function that holds alternative cell-splitting logic chosen by an argument, a table, the caller or the
    file (for example a flag that turns escape handling off for some sites) holds several implementations.
- Row-shape logic: what a reader or wrapper may do around the split: deciding whether a line is a row,
  removing blockquote markers or outer pipes, dropping the outer empty segments, trimming cells, counting or
  naming cells, recognising a separator row from cells it was given. Row-shape logic is not cell splitting.
  Splitting a cell's content on another character (a comma, a space) is not cell splitting either.

## Scope

- In scope: the eight baseline implementations and whatever replaces them, and any code the tree adds or
  changes under `scripts/` that performs cell splitting.
- Out of scope: `tests/`; baseline code other than the eight sites that the tree leaves unchanged (for example
  regexes that match a row's first cell); and `docs_form_gate.py`, `cited_works_removed`, whose single cut at
  the first spaced pipe is none of the eight sites: ignore it whether the tree leaves it or routes it.
- The one implementation must be under `scripts/` (any module or subpackage).

## Criteria (all three for PASS; they decide, the examples only illustrate)

- L1 One implementation. Exactly one splitter implementation exists in the in-scope code.
- L2 All sites use it. Every reader of the table obtains its cells from that implementation, directly or
  through wrappers that add only row-shape logic.
- L3 The others are gone. No other splitter implementation remains in the in-scope code: not one that a site
  uses, not one that is dispatched to, and not one left defined and uncalled. Code inside a comment or a
  string is not code.

## Decided cases (illustrations of L1 to L3)

| Case | Verdict | By |
|---|---|---|
| One shared splitter, all eight sites call it directly or through an alias, a `partial`, a `map`, a decorator or a delegating wrapper | PASS | L1 to L3 |
| Two entry functions (for the two outer-segment conventions) that both call one shared core, and neither splits | PASS | L1 |
| A class or subclasses that override only row-shape hooks around one split method | PASS | L1 |
| A table or registry whose entries are all the one function | PASS | L1 |
| The splitter added to an existing module under `scripts/` | PASS | L1 |
| Two functions that each apply a shared pattern themselves (`PATTERN.split` in both) | FAIL | L1: two implementations |
| A lambda or small function per module over one shared pattern | FAIL | L1 |
| Inline splits at the sites sharing one compiled pattern | FAIL | L1, L2 |
| Any site still splitting for itself, in any technique | FAIL | L2 |
| Copies of one splitter in several modules or in one module | FAIL | L1 |
| A shared entry point dispatching to separate splitters, or one function with per-site splitting branches | FAIL | L1 |
| A shared implementation that is called while the site's own splitting produces the cells used | FAIL | L2 |
| Subclasses or callables that override the split itself per site | FAIL | L1 |
| All eight sites on the shared splitter and a former splitter left defined, called by nothing | FAIL | L3 |
| The shared splitter for data rows and a site's own split kept for the header or the separator row | FAIL | L2 |
| A site that takes cells from the shared splitter and splits them or the row again on the pipe | FAIL | L2 |

## UNRESOLVED

Use it when, after reading the code and, where needed, running a reader on a row, you cannot establish where
splitting is performed for a site, or whether a second body performs cell splitting or only row-shape logic.
Say what you could not establish. UNRESOLVED is never a pass.

## Procedure

1. List every place under the tree's `scripts/` that performs cell splitting. Use the diff against the
   baseline and a search of the whole directory (pipe characters written as `"|"`, `chr(124)`, `\x7c`, or
   inside a pattern; `split`, `partition`, `find`, `finditer`, `translate`, character loops). Give each as
   `path:line` and say whether it is in scope.
2. For each of the eight sites find the reader and trace how it obtains its cells. Read the code; run it where
   reading does not settle it (cwd = the tree, stdin closed, no writes in the tree).
3. Apply L1, L2 and L3 in turn. Give the verdict, the criterion that decides it and the evidence.
4. You are given one tree. Do not look for other trees, earlier results or keys.

## Record

Verdict; deciding criterion; the list from step 1; for each of the eight sites where its cells are split, as
`path:line`; commands run; what was not established. The adjudicator knows neither the arm, nor the tree's
origin, nor any automated result for it, nor the other adjudicator's verdict.
