# jnwb for AI agents

jnwb is a Python toolbox for analysing Neurodata Without Borders (NWB) electrophysiology data:
composable, tested operations over NWB files, arrays and metadata. Researchers call it directly;
agents reach the same operations through skills. The skills set the standard an agent's work
with jnwb has to meet, and this page says where to start.

## Where to start

| You want to | Read |
|---|---|
| Analyse data with jnwb | [`skills/jnwb/SKILL.md`](../skills/jnwb/SKILL.md), the router. It sends each task to the domain skill that covers it |
| Look up an operation | [`docs/api.md`](../docs/api.md) lists every public symbol; [`docs/common_mistakes.md`](../docs/common_mistakes.md) lists the failures jnwb guards against |
| Build a skill or an agent on jnwb | The "Skill rule" section of [`CONTRIBUTING.md`](../CONTRIBUTING.md): when a skill is created, what it contains, and what checks it |
| Adapt a role definition | [`artifacts/agents/`](agents/): portable roles, each independent of any analysis domain |
| Change jnwb itself | [`AGENTS.md`](../AGENTS.md) for the repository's working rules, then [`CONTRIBUTING.md`](../CONTRIBUTING.md) |

An installed copy does not include `skills/`; `jnwb.SKILLS_URL` gives the address of the skills
for the installed version.

## The standard

Each skill narrows jnwb to what its operations support. An agent working through the skills:

- calls the public operation instead of re-implementing it, so results carry the tested behaviour;
- keeps units, axes, sample rates and index bases explicit across every call;
- passes an explicit `rng` wherever randomness is consumed;
- ends every task in one of four outcomes: compose and execute, request missing information,
  report non-identifiability or failure, or decline an unsupported inference.

The scientific safeguards (signal classes, logarithm last, causal filtering, directionality and
delay claims) are in section 4 of [`skills/jnwb/SKILL.md`](../skills/jnwb/SKILL.md). Each domain
skill adds the invariants for its own operations.
