# Direction

Adopted 2026-09-17 as the durable product direction, effective after the 0.2.5 release.
Ruling of record; supersedes any longer draft.

## Identity

JNWB is a reliable scientific toolbox for analysis of NWB neurodata, designed for direct
use by researchers and constrained use by AI agents.

AI-native usability is a design property, not part of the identity. The package stays
scientifically useful with no agent present, and "AI-native" is never a reason to add a
second copy of the scientific interface.

    JNWB = generic NWB operations
         + explicit scientific semantics
         + AI-usable routing
         + verification

## Authority

    code implements    docs explain    skills route    tests verify

Construction order, which is also the order of authority:

    scientific intent -> documented operation -> code -> tests/evidence

The skill is a routing layer, not a semantic authority:

    question -> skill -> documented operation -> execution -> verification

A skill may not hold a mutable API fact that documentation and exports also hold. It
names the operation; documentation defines it.

## Boundary

JNWB owns generic, testable operations. Study-specific conditions, hypotheses and
interpretation stay downstream. An operation belongs here when it can be specified and
verified without naming a study.

## Surface

Maximum capability coverage, subject to minimum nonredundant surface. "Skill rich and
documentation rich" means coverage, not files or prose.

- One canonical explanation per scientific concept.
- One implementation per mathematical primitive.
- Skills reference operations; they do not restate the mathematics.
- Examples demonstrate composition; they do not duplicate the reference documentation.
- Presentation assets derive from maintained documentation figures.

Documentation and presentation share source assets. Public documentation stays dry and
technically useful; diagrams and examples are reused in slides from there.

This is what lets the package become richer and smaller at once.

## Acceptance

For each public capability, the four faces are

    C = (I implementation, D documentation, S skill routing, T tests/evidence)

and they must agree on: name, inputs, shapes, units, axes, estimator, outputs, failure
behaviour, randomness, and the verification that applies.

A capability with no skill routing passes when it needs none. A capability whose four
faces contradict each other fails.

The triangle audit is a 0.2.5 close-out gate (`artifacts/todo_stack.md`, 05-85). It runs
once after the stack empties and the independent critic completes, before the release
seal.
