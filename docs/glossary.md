# Glossary

Each pair below names two different things. Every page uses these terms in these senses.

| Term | Means | Not to be confused with |
|---|---|---|
| operation | one exported jnwb function or class: a tested computation with documented inputs, units and failure behaviour | a workflow |
| workflow | a sequence of operations a caller composes for one question; jnwb ships none, so a workflow lives in the caller's code | a pipeline, which jnwb is not |
| session | one NWB file | a recording |
| recording | one continuous data series within a session, such as an LFP `ElectricalSeries` | a session |
| contact | a physical recording site on a probe shaft | a channel |
| channel | one row of the data axis, which may map to one contact | a contact; its id need not equal its position |
| electrode | one row of the NWB electrodes table | the electrodes table |
| electrodes table | the NWB table describing every electrode, read as `electrodes_df` | an electrode |
| trial | one row of an interval table | an epoch |
| epoch | the window of data cut around one trial; `epoch_continuous` turns trials into epochs | a trial |

`units`, `electrodes`, `acquisition` and `trials` are NWB's own names and are used as NWB
defines them. The spelling rules every page follows are on [Documentation Form](documentation_form.md).
