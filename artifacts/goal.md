# Goal

Ruled 2026-09-19 by Hamm (06-01); revised by Hamm 2026-09-22; version-specific lines updated on
his instruction 2026-09-24, when 0.2.7 opened. The statement jnwb is measured against, from 0.2.6
on. Subject to `artifacts/direction.md`, which it does not restate. Durable rules it relies on live
in `artifacts/fact_stack.md`; release acceptance is `AGENTS.md` §11. The 0.2.7 sequence is
`artifacts/planned_post_0.2.6.md`.

Each section states one goal and the check that holds it. A goal with no check is a preference,
and is recorded as work in `artifacts/todo_stack.md` until it has one.

## 1. Entry topology

Researcher and AI agent are parallel first-class entry paths to jnwb operations. A researcher
does not conceptually pass through the AI layer.

                     /  researcher  \
    NWB data  ----->                  -----> jnwb operations -----> verification
                     \  AI skills   /

Held by: `README.md` serves the researcher; `artifacts/agents.md`, linked from it, serves the
agent. Gate 13 holds README, tutorials, skill and docs to one NWB workflow.

## 2. Scientific alignment

    code <-> documentation <-> tests

describes and verifies the scientific surface. Skills sit outside that relation and discover,
constrain, compose, execute and verify use of it. A skill names an operation; documentation
defines it.

Held by: `tests/test_skills_validation.py` binds every routing row to the live signature and every
routed symbol to `jnwb.__all__`; `tests/test_skill_default_claims_match_signatures.py` binds every
default a skill states; gates 5 and 9 hold `docs/api.md` to `__all__`.

## 3. Control through explicit choices

jnwb has no authorization subsystem and adds none. Control is two things jnwb does have:
scientific choices are explicit caller inputs, and refusal boundaries are real. An agent may
execute operations; it may not decide scientific assumptions. Every skill ends a task in one of
the four outcomes of `artifacts/direction.md`, declining included.

Held by: the refusal tests of each module, and skill routing tests for all four outcomes
(06-25; kept in 0.2.6 by ruling R-2 of 2026-09-22).

## 4. No invented data or metadata

jnwb never substitutes synthetic values for missing empirical data in an analysis path. Explicit
synthetic testing and calibration infrastructure remains valid and is not an analysis surface.

A read never invents metadata a file does not contain. A caller may waive a specific required
field by naming it -- `read_nwb(path, allow_missing=("session_description",))` -- and waiving it
does not produce a plausible value. The default is refusal, and the default does not move. Where
an upstream constructor requires the field to exist, as pynwb does for `session_description`, the
waived field reads `""` and `jnwb_waived_requirements` records the waiver that actually happened
on that read, so a waived field and a genuinely empty one are distinguishable (ruled 2026-09-22,
06-67 option (d); implemented by 06-82).

Held by: `tests/test_nwb_read_tolerance_and_visibility.py`, which carries one test per row of the
missingness table in `docs/errors.md`.

## 5. Dynamic

"Dynamic" means adaptation to unfamiliar NWB datasets, metadata, structures, and explicit caller
inputs. Generic structural NWB operations -- validate, write, convert, repair a representation
whose intent is identifiable -- may enter the core under the boundary in
`artifacts/fact_stack.md`, each with API, documentation and tests before its skill. None was added
in 0.2.6; any in 0.2.7 enters through the capability-gated section of
`artifacts/planned_post_0.2.6.md`. Ambiguous scientific meaning is detected and never resolved by
jnwb.

Held by: the fact-stack boundary and Gate 6, which keeps study tokens out of `jnwb/`, `skills/`
and `docs/`.

## 6. Integration

Every public capability agrees across its four faces -- implementation, documentation, skill
routing and tests -- on every dimension it has (`artifacts/direction.md`, Acceptance). A change to
one face updates the others in the same commit. The code on `dev` is what CI qualifies: all
declared interpreters on Ubuntu and Windows, plus the suite against the built wheel.

Held by: the tests named in section 2, every harness gate, and CI on every push to `dev`. A
local pass is not a CI pass.

## 7. Open to contribution

A contributor, human or agent, finds one entry point per purpose and one rule per concern:

| Purpose | Entry point |
|---|---|
| Use jnwb | `README.md`; agents start at `artifacts/agents.md` |
| Change code, tests, docs or skills | `CONTRIBUTING.md`, including its Skill rule |
| Work inside this repository | `AGENTS.md` |

A skill is created only under the capability gate in `artifacts/fact_stack.md`. The standard a
contribution must meet is enforced by checks a contributor can run locally
(`python -m pytest tests/ -q`, `python scripts/harness_gate.py`), never by review alone.

Held by: `tests/test_skills_validation.py` (skill shape and routing), Gate 4 (repository root) and
`tests/test_docs_links.py`, which resolves every link on `artifacts/agents.md`.

## 8. Economy

Computational order is condition 2 of `AGENTS.md` §11; an order is recorded as an upper bound
justified by its published reference (ruled 2026-09-22, P-34). Tests are the fewest and
smallest that reach the coverage required, shared across the items that need them rather than
added per item; a new check extends an existing module or gate before it creates one. Suite wall
time and peak memory are costs: measured before each release and not grown without a recorded
reason.

Held by: `AGENTS.md` §11 condition 2 for computational order, and `scripts/release_gate.py` STEP 1,
which records suite wall time and the ten slowest tests. Peak memory has no check yet (07-02).

## Supported interpreters

Python 3.12, 3.13 and 3.14. Every claimed version is exercised in CI; `requires-python`,
classifiers, the CI matrix, the install documentation, the README and release material converge
on this set. Held by gate 8, which is widened to read `README.md` and `docs/install.md` (ruled
2026-09-22, P-68).
