# T2 structural adjudication: deployed protocol (Hamm 2026-11-16; frozen before validation 2)

Applies to every arm-produced T2 tree and, unchanged, to validation 2. Hidden from workers with the predicates.

## 1. Isolation of the tree (`build_adjudication_tree.py`)

For one tree and each of the two adjudicators the orchestrator builds a separate directory
`D:/repos/_adj/<label>/`, `<label>` = 8 random hex characters (`secrets`), different for the two adjudicators:
- `tree/`: a `git clone --shared` of the T2 baseline with the tree's `scripts/` copied over it, without
  `__pycache__`. Nothing else of the tree is copied (no `tests/`, no git history, no worktree path, no author).
- `baseline/`: a clone of the baseline.
- `RUBRIC.md`: `t2_structure_rubric_r2.md`.
The key (label, source tree, adjudicator slot, time) is appended to a file outside `D:/repos/_adj/`, in the
ledger directory. The contents of `scripts/` are the evidence and are not altered: what a tree's code reveals
about its origin is not hidden and is a stated limit.

## 2. Adjudicators

- Two per tree, each a fresh session that receives one directory and judges one tree. No adjudicator judges
  two trees in one session, sees another tree, the other adjudicator's directory or verdict, the arm, the
  cell, an automated result (D1, D2, P3, P4, C1 to C5, acceptance) or this record.
- Slot 1: a Claude `reviewer` agent. Slot 2: a second model family, opencode Muse (`delegate-cli`, review
  tier, read mode). A slot-2 run that fails, returns no verdict line or does not parse is retried once; after
  that a fresh Claude `reviewer` replaces it and the tree is marked "no cross-family". The count of such trees
  is reported.
- The packet is `t2_adjudication_packet.md`, the same text for both slots and every tree, with only the
  directory filled in. The report ends with one line `VERDICT: PASS`, `VERDICT: FAIL` or `VERDICT: UNRESOLVED`.
- Evidence an adjudicator may use: its directory; code it runs there (scripts written in its `notes/`
  directory, cwd = `tree/`, stdin closed). Nothing else.

## 3. Verdict

Both `PASS`: structure PASS. Both `FAIL`: structure FAIL. Anything else (disagreement, or either
`UNRESOLVED`): `AMBIGUOUS`. The lead checks that the procedure was followed, approves the ledger entry and
cannot break a tie or override. The ledger keeps both reports as returned, both labels, the tree SHA, the model
of each slot, and the automated observations as printed. The rubric and this protocol are not edited after an
arm output is seen.

## 4. AMBIGUOUS in the results

`AMBIGUOUS` is its own outcome: never a pass, a fail or an exclusion. For T2 the report gives:
- the count of AMBIGUOUS trees over all T2 trees assigned (denominator stated);
- the definitive-success rate: trees with `V = 1` established (structure PASS and every other requirement of
  `PREREG.md` met) over all assigned trees;
- for each cell whose structure is AMBIGUOUS and whose other requirements are met: `V` as the interval [0, 1],
  `E = V / C` as the interval [0, 1 / C], and every sum and difference that includes the cell as an interval
  with both ends shown. A cell that fails another requirement has `V = 0` whatever its structure.

## 5. Validation 2 (before freeze) and its stopping criteria

Trees: the twelve of `t2_amendment/validation2_controls.md`, built by agents other than the adjudicators from
written specifications, expected verdicts fixed there before any adjudication. Each goes through sections 1 to
3 exactly: 24 adjudications. The 23-tree validation stays as recorded.

Reported: the confusion matrix of the two-adjudicator verdict against the expected verdict (PASS, FAIL,
AMBIGUOUS by expected PASS, FAIL); per slot, the confusion matrix against the expected verdict including
UNRESOLVED; agreement between the slots and Cohen's kappa where defined; AMBIGUOUS count over 12; trees marked
"no cross-family".

STOP T2 (remove it from the executable pilot) when any holds:
1. a tree expected FAIL receives the verdict PASS;
2. a tree expected PASS receives the verdict FAIL;
3. more than 2 of 12 trees are AMBIGUOUS;
4. an adjudicator report shows the rubric does not decide a case (material ambiguity);
5. a material defect of the instrument appears whose repair needs a wider scope than the authorised one.
One or two AMBIGUOUS trees pass the gate and are reported with their cause. A tree found, before adjudication,
not to implement its specification is rebuilt or dropped with the reason recorded; after adjudication no tree
is rebuilt, relabelled or dropped.
