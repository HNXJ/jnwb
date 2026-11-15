# Addendum, after the freeze

Written 2026-11-15T16:39:26Z, while arm B's critic and reviewer ran and arm A was final. Nothing here changes a packet or the flow.

## Post hoc measures (Hamm 2026-11-15, requested after the freeze; not preregistered)

| Measure | Definition |
|---|---|
| Review yield | distinct actionable defects found per reviewed task, per arm; a finding the tree refutes does not count |
| Repair overhead | tokens, agent seconds and review cycles attributable to findings (fix rounds and re-reviews) |
| Closure reliability | findings independently verified as resolved / findings raised |

They refine the preregistered "in-formation review yield" row. Reported as post hoc.

## Packet defect found during the run (unequal condition)

COMMON tells every agent to run the acceptance command once at the end; B-helper, B-worker-1, B-worker-2 and
B-checker have no need of it, and two of those blocks say not to run it. Observed: B-worker-1 did not run it and
reported the conflict; B-worker-2 and B-checker ran it. Those two surplus runs are arm B's (arm A's agents ran it 4 times, arm B's 5). The packets were not changed.

## Independent review of this record (2026-11-15)

Verdict REVISE: no numeric mismatch; comparability text and two bullets overreached. Its findings are applied in
`RESULTS.md` ("Deviations and unequal conditions", "What the sample shows"); the report is
`agent_reports/record_reviewer.md`. The revised text was not reviewed again.

## Design decision recorded (Hamm 2026-11-15)

Finding-disposition rule for Jarness accepted with amendments; implementation deferred until this pilot closes;
no Jarness edit authorized yet. Classification follows impact and authority, not repair effort. Every finding has
exactly one accountable resolution path, including findings against the dispatcher. The pilot's numbers on the
three measures above go beside the proposal.
