# jnwb and jaxfne: docs figures and dashboard compared

Read against `E:/repos/jaxfne` at 4ca608f9 (`dashboard/`, `docs/assets/interactive/`, `jaxfne/vis/plotly/`). Each difference that needed a choice went to Hamm; the ruling column names the row.

| Aspect | jaxfne | jnwb before | Ruling |
|---|---|---|---|
| Verdict set | reproduced, conditional, mixed, in progress, not started, failed | reproduces, partial, does_not | 2026-10-24 "Verdict vocabulary" |
| Publish trigger | each `dev` push after checks | `main` only | 2026-10-24 "Dashboard publish trigger" |
| Colours and chips | its own | its own | 2026-10-24 "Dashboard style" |
| Layout | hash-routed tabs, a page per validation | one page of sections | 2026-10-24 "Dashboard layout" |
| Stage track | shown | none | 2026-10-24 "Stage track" |
| Deferred work | roadmap rows shown | not shown | 2026-10-24 "Roadmap on the dashboard"; 2026-10-26 "Dashboard validation rows" |
| Verdict split | paper, library, methods | one per replication | 2026-10-26 "Dashboard verdict split" (17-57 on the roadmap) |
| Interactive figures | hand-built Plotly per figure | stills only | 2026-10-24 "Interactive figure home", "Interactive scope", "Interactive theme"; 2026-10-26 "Interactive figures" |
| Figure header | none | none | 2026-10-24 "Figure header" |
