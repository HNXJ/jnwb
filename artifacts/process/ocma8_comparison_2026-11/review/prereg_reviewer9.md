# prereg reviewer9 (claude-sonnet-5-5), verbatim

## Report 1

VERDICT: REVISE

A. Blocks the freeze (one item)

A1. Internal contradiction in the definition of V.
- Line 16 says a confirmed defect needs "a source other than the baseline".
- Line 52 says the sources "in the baseline, inside the task's target and left unrepaired" and "caused by the TASK block's own text" "count in both" V and the inventory.
- The first of those two sources is a baseline source. Read literally, line 16 excludes it. A task whose arm left a target defect unrepaired could then score V=1, which is the opposite of line 52.
- A script computing V cannot satisfy both lines, and V is the numerator of the primary estimand.
- Fix: replace "with a source other than the baseline" at line 16 with "whose source is not 'in the baseline and outside the task's target' (line 52)". This is one phrase.

B. Plausible but unproven risks

B1. The cross-family evaluation reaches the verdicts only through a Sonnet adjudicator (lines 45-53, 68-70).
- The adjudicator builds the tables and marks rows real or false. The Muse evaluator only supplies candidates, and "no cross-family" tasks drop to two Sonnet evaluators.
- Invariant 4 asks for cross-family independent evaluation. The file states the limit and gives a V restricted to rows holding a cross-family candidate, so I did not call this A.
- Evidence that would settle it: the count of tasks marked "no cross-family" and the agreement between V and the restricted V.
- Disposition: accept as a stated limitation, and require both V figures to be reported side by side.

B2. Blinding residue (lines 142-145, 72-73).
- Role words are left in the trees and only logged as a possible leak.
- Candidate counts per arm can hint at the formation.
- A judge may infer the arm from repeated role identifiers or from the candidate count.
- Evidence that would settle it: an evaluator or adjudicator guess-the-arm check after the run.
- Disposition: accept as a limitation, and add the guess-the-arm probe to the report.

B3. Orchestrator tokens (lines 164-169).
- The orchestrator cost is a window over a growing session context. The alternation order is fixed, so T1 and T3 run A first and T2 and T4 run B first.
- Evidence that would settle it: the agents-only analysis, which is already reported.
- Disposition: accept.

C. Optional

C1. Line 166 leaves the orchestrator's model id to be written at the freeze. Prerequisite 6 already gates this.
C2. The adjudicator's table is checked by script for completeness, but not for consistency between the "real on final" column and the "introduced by the arm" source. Add a script rule for it.

Other invariants I checked (1, 2, 5-11): no violation found. The four changed passages are consistent with the rest of the file. The replacement-run cost is inside C, and the missing-data rule gives a descriptive table naming the arm and the reason.

Examined: the full PREREG.md at 7d5b4694, the diff since a900f664, and prices_2026-11-15.md. The prices in line 158-161 match the saved table. I ran only read-only commands (the git diff, a file read and a cat), and executed no tests.

