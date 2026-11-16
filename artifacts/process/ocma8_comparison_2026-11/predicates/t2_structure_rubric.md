# T2 structural adjudication rubric (Hamm 2026-11-16; written before any candidate is examined)

Question, per tree: after the change, do the eight baseline split sites use one effective shared parsing
implementation, with the redundant implementations removed? The answer is `PASS`, `FAIL` or `UNRESOLVED`, with
evidence. It is judged on what the code does and how it is built, never on spelling, names or file layout.
Behaviour (whether cells come out right) is scored elsewhere and is not part of this judgement.

## The eight sites (baseline ac995dde, `scripts/`)

| # | File | Baseline form | Readers that go through it |
|---|---|---|---|
| 1 | `build_dashboard.py` | `_cells` (regex split, slice `[1:-1]`) | `deferred_section`, `references_section`, `order_section`, `_study_cards` |
| 2 | `build_fact_graph.py` | `_cells` | `_all_tables`, which `read_facts` and `read_constants` read |
| 3 | `build_fact_graph.py` | inline split, line 399 | `reference_table_rows` |
| 4 | `learning_gate.py` | `_cells` | `ledger_rows`, `_is_mapping_header` (`mapping_tables`) |
| 5 | `release_gate.py` | `_cells` | `roadmap_rows` |
| 6 | `release_gate.py` | `_table_cells` | `table_data_rows` |
| 7 | `docs_form_gate.py` | inline split, line 285 | `parse_vocabulary` |
| 8 | `reconstruct_state.py` | inline split, line 224 | `open_defect_classes` |

Find each reader in the tree by what it reads, not by its baseline name: functions may be renamed, split or moved.

## Terms

- Delimiter logic: the code that decides where one cell ends and the next begins in a table row, including the
  treatment of an escaped pipe. Any technique counts: `split`, a regex, `partition`, `find`, a character scan,
  `translate` then split, `csv`, a state machine.
- Effective: the delimiter logic whose output the reader actually uses on the rows it reads. Code that is
  called and whose result is discarded, or used only on a path the reader's inputs do not reach, is not
  effective.
- Row-shape logic: what a reader does around the split and may keep for itself: deciding whether a line is a
  row, stripping blockquote markers or outer pipes, dropping the outer empty segments, trimming cells, counting
  or naming cells. Row-shape logic is not delimiter logic.

## Criteria (all three for PASS)

- S1 One implementation. Exactly one body of delimiter logic is effective for all eight sites. Parameters that
  select row-shape behaviour (keep or drop the outer segments, strip or not) are allowed inside it. Two public
  functions over one private splitting core are one implementation.
- S2 All sites use it. Every reader of the table above obtains its cells from that implementation, directly or
  through wrappers that add only row-shape logic.
- S3 Redundancy removed. No other delimiter logic for table rows remains effective, or remains as live code that
  a reader could call, in the six files or in the shared module. Wrappers kept under baseline names are fine
  when they delegate.

## FAIL anchors

- F1 Any site still splits for itself (an inline or local splitter), however it is written.
- F2 Several copies of the same splitter, in several modules or in one module, each used by different sites.
- F3 A shared entry point that dispatches, by an argument, a table, the caller or the file, to separate
  per-site delimiter logic. The shared name is a wrapper; the implementations are still several.
- F4 A shared implementation that is called while the site's own delimiter logic produces the cells used.
- F5 Sites that share only a constant (a pattern, a delimiter string) and each run their own split with it and
  their own handling around it that changes where cells begin and end.
- F6 A baseline splitter left in place and still reachable beside the shared one.

## PASS anchors

- One function, or one class or method, or one generator, in any module or subpackage, reached by every site
  directly, through an alias, a `partial`, a lambda, a `map`, or a thin wrapper.
- A splitter added to an existing module instead of a new one.
- Two entry functions (for the two outer-segment conventions) over one shared pattern or core, where the
  functions differ only in row-shape logic.
- Readers renamed or split in two, as long as each obtains its cells from the one implementation.

## UNRESOLVED

Use it when, after reading the code and, where needed, running the reader on a row, you cannot establish which
delimiter logic is effective at a site, or whether a second body of logic differs only in row shape. Say what
you could not establish. UNRESOLVED is never a pass.

## Procedure

1. For each of the eight sites find the reader and trace, in the tree, how it obtains its cells. Read the code;
   run it where reading does not settle it (cwd = the tree, stdin closed, no writes in the tree).
2. Note file and line of the effective delimiter logic for each site.
3. Apply S1 to S3 and the anchors. Give the verdict, the criterion or anchor that decides it, and the evidence
   as `path:line`.
4. Judge each tree on its own. Do not compare trees with each other, and do not infer a verdict from how many
   trees you have passed or failed.

## Record

Per tree: label, verdict, deciding criterion or anchor, the eight sites' effective logic as `path:line`,
commands run, what was not established. The adjudicator sees neither the arm, nor the tree's origin, nor any
automated result for it.
