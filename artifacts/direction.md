# Direction

Adopted 2026-09-17 as the durable product direction, effective after the 0.2.5 release.
Ruling of record; supersedes any longer draft.

## Identity

JNWB is a Python toolbox for reliable analysis of Neurodata Without Borders datasets,
designed for direct use by researchers and reliable composition by AI agents.

Both are first-class entry paths. A researcher does not reach the operations through the
AI layer:

                     /  researcher  \
    NWB data  ----->                  -----> JNWB operations -----> verification
                     \  AI skills   /

The package separates into a core and a layer, which is what keeps the identity free of
its own tooling:

    JNWB core       = scientific operations + documentation + verification
    AI-native JNWB  = JNWB core + skills

The core is the package. It stays scientifically useful with no agent present. Skills add
routing over it and are never a reason to add a second copy of the scientific
interface.

## Authority

    code implements    docs explain    skills route    tests verify

Documentation, code and tests constrain each other. They are not a pipeline, and none of
the three is free to move without the other two:

    scientific intent -> documented API <-> code <-> tests

The skill sits outside that triangle and acts on it:

    skill -> discover, constrain, compose, execute, verify

A skill may not hold a mutable API fact that documentation and exports also hold. It
names the operation; documentation defines it.

## The AI-native layer

A skill routes to an operation or it declines. Four cases:

    supported task            -> compose and execute
    missing input             -> request it
    non-identifiable result   -> report the failure
    unsupported inference     -> decline

    skill decides how; the tested operation performs what

This extends the existing failure semantics rather than adding an AI-specific scientific
rule: estimator failure is never converted into a plausible finite result or label, and a
skill may not convert an unsupported question into a supported-looking answer. Declining
is a correct outcome, and a skill that cannot decline is incomplete.

## Boundary

JNWB owns generic, testable operations. Study-specific conditions, hypotheses and
interpretation stay downstream. An operation belongs here when all five hold:

    generic                  it is not about one dataset's structure
    dataset-independent      it names no study, session or condition
    scientifically stable    its definition does not move with a hypothesis
    explicitly parameterized scientific choices are caller inputs, not defaults in hiding
    independently testable   it can be verified without the study that motivated it

New code is written when this test finds a genuine missing generic capability, not when
composition of what exists would have answered the question.

## Surface

Maximum capability coverage, subject to minimum nonredundant surface. "Skill rich and
documentation rich" means coverage, not files or prose.

- One canonical explanation per scientific concept.
- One implementation per mathematical primitive.
- Skills reference operations; they do not restate the mathematics.
- Examples demonstrate composition; they do not duplicate the reference documentation.
- Presentation assets derive from maintained documentation figures.

Documentation and presentation share source assets, in one direction. Documentation is
the scientific source a presentation is derived from; it is never shaped to be
slide-like. Canonical diagrams, examples, capability maps, terminology and evidence are
maintained in the documentation, and slide compositions are derived from them.
Documentation optimised for presentation distorts the thing being presented.

This is what lets the package become richer and smaller at once.

## Acceptance

For each public capability, the four faces are

    C = (I implementation, D documentation, S skill routing, T tests/evidence)

Agreement is checked per semantic dimension, over the faces that make a claim about that
dimension:

    for every capability c and dimension d:
        |{ meaning(c, d, f) : f claims d }| <= 1

A demonstrated disagreement fails. A dimension the operation requires and no face
specifies fails. A dimension the operation does not have is N/A, not missing. A skill
silent on a dimension passes when routing does not require it.

The dimensions are shape, units, axes, estimator, aggregation, failure behaviour,
randomness, identity/provenance, and composition where an operation is reached through a
skill that sequences it with others. Composition carries its own claims: order of
operations, order of aggregation, whether identifiers survive, and which signal class is
substituted for which. A routing layer can get every individual operation right and still
compose them into a wrong result, without restating any mathematics.

Presence stays with the gates. Public-symbol presence, API generation and export
agreement, documentation coverage and onboarding alignment are decided deterministically;
the audit consumes those results rather than reproducing them.

The audit is a 0.2.5 close-out gate (`artifacts/todo_stack_0.2.5.md`, 05-85), run once after the
stack empties and the independent critic completes, before the release seal.

## Prior art

*Reimagining research papers as interactive and reliable AI agents* (Paper2Agent) converts
individual papers into agents exposing tools, resources and workflow prompts, validating
each executable tool before exposing it and excluding the ones that keep failing. Its
decomposition is the one above reached from the other direction: tools to code, resources
to documentation, prompts to skills.

JNWB sits in the complementary position -- one maintained, dataset-agnostic toolbox for
NWB neurodata rather than a per-paper conversion -- and takes verification further, since
these tests cover units, axes, randomness, null models, leakage and failure states rather
than reproduction of reference outputs alone.

The paper is CC BY-NC-ND. Its figures are not reproduced or adapted here, in JNWB
documentation, or in any JNWB presentation; the architecture figure is JNWB's own.
