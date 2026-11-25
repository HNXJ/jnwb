# 17-099 equivalence evidence

Owner decision on 17-099 (2026-11-25): review-based semantic equivalence is accepted, with the lexical checks
kept as smoke tests and not as proof of equivalence. Acceptance needs an independent non-writer review of the
exact candidate SHA, an explicit comparison of duplicate cases, precedence and observable behaviour, positive,
negative and adversarial regression tests, and recorded residual limits. This file records the comparison.
The candidate SHA and the review verdict are in `artifacts/process/release_checklist.md`.

## 1. Four outcomes

Canonical home: fact row K3 (`artifacts/fact_stack.md`): "a task ends in one of four outcomes: compose and
execute, request missing information, report non-identifiability or failure, decline unsupported inference".
Holder: `tests/test_skill_decline_behaviour.py::test_every_skill_outcome_is_tested_or_excused`.

Precedence: K3 names the rule. The code names the API values: `jnwb.ontology.Preflight.OUTCOMES` is
`("supported", "request", "failure", "decline")`, which map one to one to K3's four names. The mapping lives in
`tests/test_four_outcomes_one_claim.py::MAPPING`.

| Location | Text (quoted) | Compared with K3 |
|---|---|---|
| `.github/CONTRIBUTING.md:294` | "ends in one of four outcomes: compose and execute, request missing information, report non-identifiability or failure, or decline an unsupported inference" | equivalent; "an" is a grammatical variant |
| `artifacts/agents.md:27` | "ends every task in one of four outcomes: compose and execute, request missing information, report non-identifiability or failure, or decline an unsupported inference" | equivalent |
| `docs/architecture.md:46` | "Every task a skill receives ends in one of four outcomes:" and a diagram with Decline, Request the input, Report the failure, Compose and execute the operations, Return the verified result | equivalent; the diagram labels are the four outcomes, and "Return the verified result" is the compose-and-execute leg |
| `docs/api.md:277` | `jnwb.preflight` "return one of the four outcomes" | equivalent to the code values in `Preflight.OUTCOMES` |
| `jnwb/ontology.py:374-380` | "One of four outcomes": `"supported"` compose and execute; `"request"` missing input; `"failure"` not identifiable; `"decline"` no operation supports the inference | equivalent (docstring of the code value) |

Observable behaviour: `Preflight.OUTCOMES` has exactly the four values; the docs' count and names agree with it
(`test_the_code_names_the_four_outcomes_the_docs_name`). The routing behaviour behind K3 is tested by its holder.

## 2. Python matrix

Canonical: goal row 12 (`artifacts/goal.md`): Python 3.12, 3.13, 3.14 and 3.15, with 3.15 excluded on Windows
until h5py ships cp315 wheels. Enforced by `scripts/gates/versions.py` (`PYTHON_FLOOR = "3.12"`,
`PYTHON_CI_REQUIRED = ("3.12", "3.13", "3.14", "3.15")`) and by the CI matrix in
`.github/workflows/workflow.yml` (`exclude: windows-latest / 3.15`; an `include` adds Windows 3.14 for the figures
leg, which does not change the claim).

The prose restatements: three pages, not the four that 17-099 once named. `README.md:43`, `docs/install.md:9`
and `docs/index.md:23` each state the floor "3.12 or newer", the tested set "3.12, 3.13, 3.14 and 3.15" and
"on Windows for all but the last".

Gate coverage (observed, `scripts/gates/versions.py` block 4): gate 8 reads `README.md` and `docs/install.md`
only. No gate reads `docs/index.md`. Before this change a drifted index sentence passed every gate.

| Surface | Read by | Result at this SHA |
|---|---|---|
| README.md | gate 8 and `test_every_page_states_the_declared_floor_and_tested_set` | agrees |
| docs/install.md | gate 8 and the page test | agrees |
| docs/index.md | the page test only (new) | agrees |
| `artifacts/goal.md` row 12 | read by the stack reviewer, not by a test | agrees with the constants |

## 3. Tests added (all pass at this SHA)

`tests/test_four_outcomes_one_claim.py` (6 tests): the code values equal the mapping; K3 is one row naming all four;
each restatement carries its phrases (positive, the real files); a dropped outcome is reported (negative); a count
of three is reported (negative); a permission to decline is reported (adversarial); a reworded restatement with the
same four outcomes passes (adversarial positive).

`tests/test_python_matrix_pages_agree.py` (6 tests): every page states the declared floor and the tested set and
the Windows clause (positive); gate 8 agrees with the pages it reads (positive); a page that drops 3.15 is reported
(negative); a drifted floor is reported (negative); a Windows claim that includes 3.15 is reported (adversarial); a
second drifted "Tested in CI on" sentence is reported (adversarial; gate 8 reads every sentence too).

`tests/test_spikes_lfp_restatements.py` (8 tests, 17-099 spikes part, see `915cd91a`..`88a6eeec`).

## 4. Residual limitations

- All three checks are lexical. A contradiction phrased outside their word lists passes them. Equivalence
  of wording is judged by the independent review at the candidate SHA, as the owner's decision requires.
- Spikes and LFP: a sentence that states the rule without a pooling word is not read (for example "combine" or
  "merge"); a sentence split by `;` carries its contradiction without a pooling word; "namespaced or not" from S16
  is dropped by three restatements, which keeps the prohibition unconditional and so does not contradict S16.
- Four outcomes: the `docs/architecture.md` diagram is read by label, not by its arrows; the labels are compared
  by exact text.
- Python matrix: the Windows clause is checked as a sentence, not against the workflow's `exclude` block; the
  workflow is the enforcer, and the goal row states the exclusion.
- The Python-matrix tests read the three pages with one sentence pattern each. A page reworded to another
  sentence shape will be reported as not stating the matrix, which fails loudly rather than passing.
- No change to any gate. Gate 8 still reads two pages; the index page is covered by its test only.
