# Benchmark design (declared, unrun)

Carried verbatim from `artifacts/planned_post_0.2.6.md` at `47235371`, the one part of that file
no item or landed change holds; the rest of it is accounted for in the commit that deleted it.
Ruled 2026-09-25: the benchmark stays as declared, and a paper agent's with-and-without-jnwb
comparison is reported downstream (`artifacts/rulings/2026-09-25.md`).

The hypothesis ruled 2026-09-17 (`artifacts/archive/0.2.5/planned_post_0.2.5.md`, P0): an agent
given jnwb's skills and tested operations outperforms the same agent given raw repository access,
on a predefined set of NWB analysis tasks. Pre-registered here. **None of it has run**, it is a
non-goal of 0.2.6 and it gates nothing: an experiment whose either outcome is admissible cannot
be a release criterion without giving it a result to reach.

| Element | Declaration |
|---|---|
| Task set | 30 tasks, frozen and hashed before the first run: 12 in-scope single-operation tasks (spiking, spectral, statistics, NWB inspection, three each), 8 in-scope compositions of two or more operations, 6 out-of-scope tasks whose correct outcome is a refusal (study-specific meaning, an undocumented condition code, a claim the data cannot support), 4 tasks whose correct outcome is a request for a missing input (sampling rate, baseline window, exchangeability scheme, reference). Data: DANDI 000253 excerpts and seeded synthetic NWB only |
| Arms | A: the agent with `skills/` and the installed package. B: the same agent with the repository checkout and no skill loaded. Same model, same prompt template, same tool set, same token and wall-clock budget per task |
| Repetitions | 5 independent runs per task per arm, fresh context each, seeds recorded; 300 scored runs in total |
| Scoring rubric | Each run scored 0/1 on each semantic dimension the task declares (shape, units, axes, estimator, aggregation, failure, randomness, identity, composition), against a reference computed by a committed script; the run score is the fraction of declared dimensions correct. Resemblance to a reference output is not scored |
| Refusal scoring | On an out-of-scope task a refusal naming the reason scores 1 and any answer scores 0. On a missing-input task a request for the named input scores 1, a silently assumed value 0. On an in-scope task an unwarranted refusal scores 0 |
| Inferential unit | The task: per-task mean over its 5 runs, compared between arms by a paired sign-flip permutation test over the 30 tasks (10 000 flips, fixed `rng`), two-sided, alpha 0.05, reported with the per-category breakdown and the effect as a paired mean difference with a bootstrap interval |
| Scorer | A script, not a reviewer; its dimension references are written and committed before the task set is hashed |
