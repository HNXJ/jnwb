# Goal

Ruled 2026-09-19. The statement jnwb is measured against. Subject to `artifacts/direction.md`,
which it does not restate.

This exists because two pillars of an earlier goal statement named capabilities the package does
not have and does not intend to build. Repairing the repository against an unrevised goal cannot
produce a valid result, so the goal is corrected first, from package evidence plus a human
ruling. A desired presentation never produces a new package identity.

## 1. Entry topology

Researcher and AI agent are parallel first-class entry paths to jnwb operations. A researcher
does not conceptually pass through the AI layer.

                     /  researcher  \
    NWB data  ----->                  -----> jnwb operations -----> verification
                     \  AI skills   /

## 2. Scientific alignment

    code <-> documentation <-> tests

describes and verifies the scientific surface. Skills sit outside that relation and discover,
constrain, compose, execute and verify use of it. A skill names an operation; documentation
defines it.

## 3. Authorization

Authorization is not a jnwb capability claim. The relevant boundary is that scientific choices
remain explicit: an agent may execute operations, and may not decide scientific assumptions.

## 4. Synthetic data

jnwb never substitutes synthetic values for missing empirical data in an analysis path. Explicit
synthetic testing and calibration infrastructure remains valid and is not an analysis surface.

## 5. Dynamic

"Dynamic" means adaptation to unfamiliar NWB datasets, metadata, structures, and explicit caller
inputs. It does not mean conversion of arbitrary source data into NWB. Raw-data-to-NWB conversion
is not added in 0.2.6.

## Supported interpreters

Python 3.12, 3.13 and 3.14. Every claimed version is exercised in CI; `requires-python`,
classifiers, the CI matrix, the install documentation, the README and release material converge
on this set, and `scripts/harness_gate.py` gate 8 enforces the convergence.
