# Packet: the single independent freeze review of the T2 instrument (read-only on the record)

You are an independent reviewer. You wrote none of this. Your job is to find how the T2 measurement, as it
now stands, can give a wrong answer. Agreement is not the goal; a missed defect is the failure, and so is an
invented one.

## Context

A pilot compares two ways of organising coding agents (arm A, arm B) on four tasks. Task T2: in the repo jnwb
at baseline ac995dde, eight sites under `scripts/` split markdown table rows on `|` (five functions, three
inline); the task is to consolidate them into one cell splitter that honours an escaped pipe `\|` inside a
cell, with all other behaviour kept. The measurement of an arm's output tree was amended three times and
reviewed four times (REVISE, REVISE, STOP, REVISE). After review 4 the owner (Hamm) authorised one final,
bounded repair cycle. This review is its terminal gate.

Owner's rules for this gate (his words where in quotation marks):
- "The next review is a terminal decision gate, not permission for another iterative round."
- STOP T2 if a known-invalid structural implementation is accepted, a known-valid one is rejected, material
  rubric ambiguity remains unresolved, the deployed adjudication cannot reliably distinguish valid from
  invalid trees, or another material defect requires expanding the repair scope.
- "A new material REVISE at that review ends T2 development for this pilot."
- "No retrospective modification of prior controls, verdicts, or acceptance results."
- "Preserve AMBIGUOUS as a distinct outcome. Report definitive-success rate over all assigned trees and an
  uncertainty interval that treats ambiguous outcomes as unresolved, not excluded. Do not silently classify
  them as failures."
- Structural ruling (literal): "The task contract requires exactly one cell-splitter implementation in
  scripts/, with all eight designated sites using it and redundant splitter implementations removed." "Count
  implementations that perform cell splitting, not merely functions involved in the call path." "A wrapper
  that delegates to the single implementation is not itself another splitter." "Behavioral correctness
  remains independently scored. Structural PASS cannot compensate for behavioral FAIL."

  | Case | Ruled |
  |---|---|
  | one shared splitter, all eight sites | PASS |
  | two entry functions calling one shared core, neither independently splits | PASS |
  | two functions independently calling one compiled pattern's `split` | FAIL |
  | eight inline splits sharing one compiled pattern | FAIL |
  | shared wrapper dispatching to separate splitters | FAIL |
  | uncalled legacy splitter retained | FAIL |
  | a ninth split outside the designated eight | outside adjudication scope |

- The generator's acceptance, "without post hoc exclusions": 28 behaviour-correct trees at zero scored
  mismatches at every seed; 29 wrong trees at least one at every seed; `w_ws` exploratory, excluded from
  scoring. "The missing inner-whitespace cases in three readers are a coverage limitation, not automatically a
  failure."

Because the gate is terminal, mark every finding MATERIAL or NOT MATERIAL and say why.
MATERIAL: an instrument file (rubric revision 2, adjudication protocol, adjudication packet, isolation script,
generator, `predicates_t2.py`, acceptance files) would have to change, or a validation would have to be rerun,
before a T2 result could be trusted; or one of the owner's STOP conditions holds.
NOT MATERIAL: a correction to the record's wording, or a limit that is already stated, or should be stated,
without changing any instrument file or result.
Do not soften a finding to avoid ending T2, and do not raise one to seem thorough. A wrong convention that
scores 0 is evidence; say for each whether an agent attempting the task could plausibly produce it.

## Read (record, branch `_temp_ocma8_pilot` at the commit named in your dispatch message; edit nothing under it)

Record root R = `D:/repos/_work/jnwb_pilot_rec/artifacts/process/ocma8_comparison_2026-11/`
1. `R/t2_amendment/AMENDMENT.md`: the status paragraph and table at the top; from "Review 4 of amendment 3"
   to the end. Earlier sections are history.
2. `R/PACKETS.md`: the block TASK-t2 (the task contract) and the paragraphs "AMBIGUOUS predicate results" and
   "T2 structure". `R/FREEZE.md`: the T2 paragraph.
3. Structure: `R/predicates/t2_structure_rubric_r2.md` (the rubric in force), `t2_structure_rubric.md` (the
   first rubric, history), `t2_adjudication_protocol.md`, `t2_adjudication_packet.md`,
   `build_adjudication_tree.py`.
4. Validation 2: `R/t2_amendment/validation2_controls.md` and `R/t2_amendment/validation2/` (`key.jsonl.txt`,
   `slot1/`, `slot2/`, `smoke/`, `score_validation2.py`, `score.txt`, `trees/*.patch`).
5. Behaviour: `R/predicates/t2_differential.py` (generator revision 3), `R/predicates/predicates_t2.py`,
   `R/t2_amendment/packet_generator_r3.md`, `matrix7_run.py`, `matrix7.txt`, `matrix7_runs.jsonl.txt`,
   `matrix7_reconcile.py/.txt`, `coverage_r3.py/.txt`, `reader_check_r3.py/.txt`, `reader_check_r3/`,
   `predicates_r3_controls.txt`, `contract_scan.py/.txt`.
6. `R/review/t2_amendment_reviewer4.md` (the previous review and its findings F1 to F10).

Trees (read, copy, never edit): baseline `D:/repos/_work/exp_prereq/t2/base`; corrected reference
`D:/repos/_work/exp_t2beh/pos2`; validation 2's trees `D:/repos/_work/exp_t2val2/{n1..n5,m1..m7}`; their
isolated copies as the adjudicators saw them `D:/repos/_adj/`; other controls under
`D:/repos/_work/exp_t2ctl/`, `exp_t2cov/`, `exp_prereq/t2/`, and in
`D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/` under `rev_t2c/trees/` and
`rev4/trees/`.

## Questions (answer each; evidence as `path:line`, or a command and its output)

Q1. Rubric revision 2. Does it decide every row of the owner's table as ruled, by its criteria L1 to L3 and
    its scope rule, with no contradiction between criteria and examples? Test it against at least eight
    architectures that are not among the twelve validation trees (for example: per-site flags changing how
    one body splits; a lambda per module over one shared pattern; a state machine with `str.split` kept for
    the separator row only; a class with per-site subclasses overriding the split; re-export through
    `__init__`; a decorator; a splitter kept only in `tests/`; unchanged baseline code that holds a pipe
    regex but is none of the eight sites). For each: decided or not, by which criterion, the decision right
    under the literal ruling or not, and whether two careful readers would plausibly disagree. Four slot-1
    reports noted the scope rule decides unchanged baseline pipe code by its general wording, not by its
    listed example (AMENDMENT.md, validation 2): is that material ambiguity?
Q2. Protocol, packet and isolation script. Are arm-tree isolation, adjudicator independence, evidence access
    and AMBIGUOUS handling specified completely enough to run without a further decision? Does the
    efficiency scoring follow the owner's rule quoted above? Can the arm, the builder or another tree leak
    into an isolated directory (inspect two under `D:/repos/_adj/`)? Is slot 2's read-only, no-shell limit a
    stated limit or a defect of the instrument?
Q3. Validation 2. Was the deployed procedure followed as written? Recompute `score.txt` from `key.jsonl.txt`
    and the 24 reports. Read at least eight reports (four per slot, hard cases first: m1, m2, m4, n2, n3):
    does each verdict follow from the rubric and the tree, or from a cue? Do at least five trees implement
    their specification (`validation2_controls.md` against the patch or the tree)? Were the expected
    verdicts and stopping criteria committed before the adjudications (`git -C D:/repos/_work/jnwb_pilot_rec
    log --format="%h %ci %s" -12`)? Was the pre-adjudication edit of m5 inside the protocol? Does 12 of 12
    on these trees support "the deployed adjudication distinguishes valid from invalid structures", given
    the limits listed? Is any stopping criterion (protocol, section 5) triggered?
Q4. Generator revision 3. (a) Are review 4's F1, F2, F8 and F9 repaired? (b) Is any scored input one whose
    correct output is contested, so that a valid implementation could be rejected? (c) Does the oracle
    wrongly forgive anything? (d) Propose at least five wrong splitting conventions not among the 29 wrong
    trees, build at least three as trees in your scratch directory, run each at seeds 2026111600 and 7, and
    report scored mismatches. (e) Is the per-reader coverage as `coverage_r3.txt` states, and do the stated
    limits (three readers without inner whitespace; `w_hdr2` rejected through `routing.targets` alone;
    whitespace padding unscored) leave a wrong answer likely?
Q5. Matrix 7. Recompute the per-tree result from `matrix7_runs.jsonl.txt` yourself for at least twelve trees
    and compare with `matrix7.txt`, `matrix7_reconcile.txt` and the table in AMENDMENT.md. Is each tree's
    class (behaviour-correct, wrong) justified independently of the generator, or does the classification
    presuppose the result? Was any run excluded or any expectation changed after the run?
Q6. `predicates_t2.py`. Does P3 pass only with 17 readers, more than 0 inputs, 0 mismatches in both scored
    modes and no WARN? Does the summary line `PRIMARY automated k/2 CONSTRAINTS j/5 STRUCTURE adjudicated`
    keep structure out of the automated score, and does `predicates_r3_controls.txt` show the expected lines
    for the corrected reference, the baseline, a wrong tree (`w_hdr2`) and an unconsolidated tree with
    correct behaviour (`u_const2`)? Do not run this script.
Q7. Record honesty. Were any earlier controls, verdicts or acceptance results changed in this cycle
    (`git -C D:/repos/_work/jnwb_pilot_rec diff --stat 1be511ae HEAD -- artifacts/process/ocma8_comparison_2026-11`)?
    Does any file overstate: call the adjudicators blind, present amended T2 as measured under the original
    preregistration, pool the 23-tree and 12-tree validations, omit a failure, or quote a number the stored
    files do not show? Check at least twelve quoted numbers against their source files.
Q8. Anything else that makes the T2 measurement give a wrong answer on a tree an arm could produce.

## How to run things

- Differential on one tree (about 1 to 2 minutes), one at a time, at most 14 runs in total:
  `python D:/repos/_work/exp_t2diff/t2_differential_r3.py <tree> D:/repos/_work/exp_prereq/t2/base --seed <S>`
  (byte-identical to `R/predicates/t2_differential.py`, sha256 efa05ca3e514b050...; confirm with `sha256sum`,
  run the copy, not the record). Frozen seed 2026111600.
- Scratch directory, the only place you write:
  `D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev5/` (create it). Build a
  tree with `cp -r D:/repos/_work/exp_t2beh/pos2 <scratch>/<name>` and edit only your copy.
- Never: `python -c`, `python -` or heredoc code (write a script file and run it by path); `sed -i`; any git
  write anywhere; any edit outside your scratch directory; pytest on whole trees; `predicates_t2.py`;
  spawning agents; running a project script with `--help`.
- Budget: about 80 tool calls.

## Report

Write the report to
`D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev5/freeze_review.md`, at
most 3,000 words, and return the same text. Form:

1. VERDICT: ACCEPT (freeze as it stands; NOT MATERIAL corrections may be listed), REVISE (at least one
   MATERIAL finding that a change could repair; under the owner's rule this ends T2 development for this
   pilot), or STOP (a STOP condition holds; name it).
2. Findings table: id, MATERIAL or NOT MATERIAL, question, finding, evidence, what would have to change.
3. Q1 table: architecture, decided (yes/no), criterion, decision right (yes/no), disagreement risk
   (low/medium/high).
4. Q4 table: wrong convention, built (yes/no), scored mismatches per seed, plausible arm output (yes/no, why).
5. Numbers checked (Q5, Q7): quoted value, source file, match (yes/no).
6. What you did not check.

Mark each claim observed (you ran it or read the line) or inferred.
