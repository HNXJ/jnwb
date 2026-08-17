# Handout 3 v1.1 — Cross-Position Identity-Reversal Design Amendment

**Status: SCIENTIFIC_SIGNOFF: APPROVED (2026-08-10). Milestone 2A only.**

Sol/Hamm approved this amendment on 2026-08-10. The approval authorizes the positive control,
R0/R1 linear baselines, grouped/exchangeable nulls, reversal scoring, and session/subject
diagnostics described below. Nonlinear flat, structured, ablation, architecture-search, and
regularization experiments remain closed.

This document amends the signed Handout 3 v1 estimand after the Milestone 1 design inspection
found that expected identity is deterministically recoverable from preceding identity,
omission position, sequence family, and cycle. The signed v1 document remains preserved and is
not edited in place.

## 1. Design finding carried forward

For every inspected outer train/test partition:

```text
P(Y_expected | Y_previous, omission_position, sequence_family, cycle) = 1
```

The original within-position estimand, “expected identity conditional on preceding identity,” is
not identified by this corpus. Statistical residualization is not an acceptable repair because it
cannot create independent variation that the experiment did not contain.

## 2. Revised estimand

The primary question becomes:

> Does the neural representation generalize across omission positions according to expected
> identity when expected and preceding identity make opposite predictions?

At p2/p3:

```text
Y_previous = Y_expected
```

At p4:

```text
A_previous -> B_expected
B_previous -> A_expected
```

The primary contrast is therefore:

```text
train: p2 + p3 omissions
test:  p4 omissions
```

The same held-out predictions are scored twice:

```text
A_expected  = accuracy against Y_expected
A_previous  = accuracy against Y_previous
G           = A_expected - A_previous
```

For complementary p4 labels, `A_previous = 1 - A_expected` and `G = 2*A_expected - 1`.
Positive `G` favors expected-identity generalization; negative `G` favors
preceding-identity/history generalization; `G` near zero supports neither account.

This is a cross-position generalization design, not pooled within-position decoding.

## 3. Prespecified contrasts

Primary:

1. `p2+p3 -> p4`, scored against both expected and previous identity.

Secondary, recorded only if eligibility supports them:

2. `p4 -> p2+p3`.
3. `p2 -> p4`.
4. `p3 -> p4`.
5. `p4 -> p2`.
6. `p4 -> p3`.

The primary contrast is the only one eligible to support the reversal-based expected-versus-
previous interpretation directly, because p4 is the test context where the labels reverse.

## 4. Group and eligibility contract

Before any model or tensor work, assign a common session-level temporal cycle to all eligible
p2/p3/p4 trials using the canonical `detect_trial_cycles` gap rule on their combined timestamps.
A train/test fold holds out one complete common cycle.

A session/contrast is eligible only when:

- readiness gates pass;
- every participating trial is correct, A/B-family, and has a non-null expected identity;
- at least three common cycles contain the required train/test material;
- each valid outer fold has at least two training cycles;
- both A and B occur in outer training;
- both A and B occur in outer testing;
- at least two valid outer folds exist;
- each valid outer fold has a predetermined inner partition;
- no fallback to random trial validation is permitted.

An invalid fold receives `INELIGIBLE_DESIGN` plus a reason. It is not repaired by changing the
split scheme after inspection.

Inner partitions are formed by holding out one training cycle from the outer-training set. A
session/contrast may be reported as design-supported only if at least two valid inner
partitions remain after the same class checks.

## 5. Scope boundary

The design-only scope above governed Milestone 1B. Following the 2026-08-10 Sol/Hamm sign-off,
Milestone 2A is authorized for the frozen primary corpus:

- presented-identity positive control;
- R0 rate/collapsed linear baseline;
- R1 temporally resolved flattened linear baseline;
- grouped/exchangeable permutation nulls;
- expected-versus-previous reversal scoring;
- session, subject, and leave-one-session-out diagnostics;
- complete machine-readable receipts.

Nonlinear flat M2, structured M3, structure-ablation M4, architecture searches, broad
hyperparameter searches, and Figure 04 regeneration remain outside this authorization.

## 6. Falsifier

The amendment is rejected for Milestone 2 if the primary contrast has fewer than two eligible
sessions or subjects, fewer than two valid outer folds in a material fraction of eligible
sessions, or if the reversal relation is not present exactly in the canonical ontology.
