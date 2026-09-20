# Goal

Ruled 2026-09-19 by Hamm (06-01), five decisions, each authoritative for 0.2.6. The statement
jnwb is measured against. Subject to `artifacts/direction.md`, which it does not restate.

Every later item that cites a goal claim cites this file. Two things this ruling forbids adding
merely to satisfy the superseded goal: raw-data-to-NWB conversion, and an authorization
subsystem.

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

"Requires authorizations" is removed as a package capability claim. The actual control mechanism
is two things jnwb does have: scientific choices are explicit, and refusal boundaries are real.
An agent may execute operations; it may not decide scientific assumptions. No authorization
subsystem is added to satisfy the superseded goal.

## 4. Synthetic data

jnwb never substitutes synthetic values for missing empirical data in an analysis path. Explicit
synthetic testing and calibration infrastructure remains valid and is not an analysis surface.

Widened 2026-09-19. The rule above covers empirical data in an analysis path, and was read as
also governing required *metadata* on the read path. It did not, and the gap mattered: a consumer
corpus refused for a missing `session_description` was refused on an implementation detail rather
than on a frozen rule. The rule now extends to required metadata, with one bounded exception.

A read never invents metadata a file does not contain. A caller may waive a specific required
field by naming it -- `read_nwb(path, allow_missing=("session_description",))` -- and waiving it
must not produce a plausible value. The default is refusal, and the default does not move.

**Provisional, pending 06-67.** What a waived field holds where an upstream constructor requires
it to exist at all -- as pynwb does for `session_description` -- is *not* ruled. The shipped
implementation supplies the empty string and records `jnwb_waived_requirements` on the returned
object, and that empty string is **not** unmistakable for a real description: a genuinely empty
on-disk description is value-identical to a waived one. 06-67 rules the missingness truth table;
until it does, this paragraph states current behaviour, not a decision.

## 5. Dynamic

"Dynamic" means adaptation to unfamiliar NWB datasets, metadata, structures, and explicit caller
inputs. It does not mean conversion of arbitrary source data into NWB. Raw-data-to-NWB conversion
is not added in 0.2.6.

## Supported interpreters

Python 3.12, 3.13 and 3.14. Every claimed version is exercised in CI; `requires-python`,
classifiers, the CI matrix, the install documentation, the README and release material converge
on this set, and `scripts/harness_gate.py` gate 8 enforces the convergence.
