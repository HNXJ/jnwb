# 17-099 equivalence evidence

Owner decision on 17-099 (2026-11-25): review-based semantic equivalence is accepted, with the lexical checks
kept as smoke tests and not as proof of equivalence. Acceptance needs an independent non-writer review of the
exact candidate SHA, an explicit comparison of duplicate cases, precedence and observable behaviour, positive,
negative and adversarial regression tests, and recorded residual limits. This file records the comparison,
the tests, the residual limits (section 4) and the review record (section 5).

Status (2026-11-25): **ACCEPTED**, by owner decision, under review-based equivalence. Section 4 is the recorded
residual list and is explicitly non-exhaustive: the lexical checks are smoke tests, and the residual classes they
pass are named there. The 11,145 passing tests support regression coverage, not exhaustive semantic equivalence.
Acceptance applies to 17-099 only, not to release 0.2.17. The accepted check is review-based equivalence; the
original todo Check ("each fact has one home and the others link to it") was not the one ruled. The link-target
question recorded in the release checklist's update log (2026-11-25, `12c9fa43`) is not ruled by this decision.

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
| `docs/architecture.md:46` | "Every task a skill receives ends in one of four outcomes:" and a diagram with Decline, Request the input, Report the failure, Compose and execute the operations, Return the verified result | equivalent; the labels are the four outcomes, and "Return the verified result" is the compose-and-execute leg |
| `docs/api.md:277` | `jnwb.preflight` "return one of the four outcomes" | equivalent to the code values in `Preflight.OUTCOMES` |
| `jnwb/ontology.py:374-380` | "One of four outcomes": `"supported"` compose and execute; `"request"` missing input; `"failure"` not identifiable; `"decline"` no operation supports the inference | equivalent by reading; no test reads it (section 4) |
| `docs/unit_quality_example.md:4` | names the four outcomes | equivalent by reading; no checker reads it |

Observable behaviour: `Preflight.OUTCOMES` has exactly the four values; the docs' count and names agree with it
(`test_the_code_names_the_four_outcomes_the_docs_name`). The routing behaviour behind K3 is tested by its holder.

## 2. Python matrix

Canonical: goal row 12 (`artifacts/goal.md`): Python 3.12, 3.13, 3.14 and 3.15, with 3.15 excluded on Windows
until h5py ships cp315 wheels. Enforced by `scripts/gates/versions.py` (`PYTHON_FLOOR = "3.12"`,
`PYTHON_CI_REQUIRED = ("3.12", "3.13", "3.14", "3.15")`) and by the CI matrix in
`.github/workflows/workflow.yml` (`exclude: windows-latest / 3.15`; an `include` annotates the existing Windows 3.14 cell with `figures`
leg, which does not change the claim).

The prose restatements: three pages, not the four that 17-099 once named. `README.md:43`, `docs/install.md:9`
and `docs/index.md:23` each state the floor "3.12 or newer", the tested set "3.12, 3.13, 3.14 and 3.15" and
"on Windows for all but the last".

Gate coverage (observed, `scripts/gates/versions.py` block 4, line 272): gate 8 reads `README.md` and
`docs/install.md` only. No gate reads `docs/index.md`. Before this change a drifted index sentence passed every gate
(by grep of the gate sources; no drifted tree was run through every gate).

| Surface | Read by | Result at the candidate SHA |
|---|---|---|
| README.md | gate 8 and `test_every_page_states_the_declared_floor_and_tested_set` | agrees |
| docs/install.md | gate 8 and the page test | agrees |
| docs/index.md | the page test only (new) | agrees |
| `.github/CONTRIBUTING.md:12-13` | no test or gate | agrees by reading: "Python 3.12 or newer"; every declared version on Ubuntu and every one but 3.15 on Windows ("seven legs") |
| `artifacts/goal.md` row 12 | read by the stack reviewer, not by a test | agrees with the constants |

## 2a. Spikes and LFP

Canonical: fact row S16 (`artifacts/fact_stack.md`): spikes and LFP are never pooled, namespaced or not (ruled
2026-09-29; `AGENTS.md` section 5).

| Location | Text | Compared with S16 |
|---|---|---|
| `AGENTS.md:74` | the S16 wording | equivalent (verbatim, by reading) |
| `.github/CONTRIBUTING.md:378` | "Never pool spikes and LFP." | equivalent; drops "namespaced or not", so the prohibition stays unconditional |
| `skills/jnwb/SKILL.md:58` | "Never pool across them." | equivalent |
| `docs/architecture.md:132` | the spikes and LFP half | equivalent; the modality clause "Signals of distinct modalities are never pooled" is wider than S16 (section 4) |
| `jnwb/_units.py:136,185`, `jnwb/_declarations.py:7`, `jnwb/spectral/_coupling.py:955`, `jnwb/connectivity/_network.py:150` | "never pooled" in docstrings and comments | equivalent by reading; no checker reads them |

## 3. Tests (all pass at the candidate SHA)

`tests/test_four_outcomes_one_claim.py` (13 tests): the code values equal the mapping; K3 is one row naming all four;
each restatement carries its phrases (positive, the real files); a dropped outcome is reported (negative); a count of
three is reported (negative); a count of three beside the real sentence is reported (negative); a permission to decline
is reported (adversarial); five sentences that keep the four phrases and weaken the decline outcome are reported
("Declining is optional.", "need not decline", "does not decline", "should not decline", "not required to decline")
(adversarial); a reworded restatement with the same four outcomes passes (adversarial positive); "Skills never decline." is reported (adversarial, added after the 6ee80610 review); "must not decline", "will not decline", "is not allowed to decline" and "don't decline" are reported (adversarial, added after the 4ef9c443 review); "five possible outcomes" and "five distinct outcomes" are reported and "four possible outcomes" is not (adversarial and its negative, added after the 4ef9c443 review).

`tests/test_python_matrix_pages_agree.py` (12 tests): every page states the declared floor and the tested set and the
Windows clause (positive); gate 8 agrees with the pages it reads (positive); a page that drops 3.15 is reported
(negative); a drifted floor is reported (negative); a Windows clause that drops the exclusion is reported
(adversarial); a second drifted "Tested in CI on" sentence is reported (adversarial); six probes on `docs/index.md`
are reported: a Windows testing sentence, a 3.15 claim on Windows, a flipped Windows clause, a second floor, a negated
clause, a clause that calls the exclusion outdated (adversarial); a second floor sentence is reported (adversarial);
a version outside the declared set named as "Python 3.16" is reported (adversarial); a second floor written "Requires Python 3.12 only." is reported and "Python>=3.10 works." is reported (adversarial, added after the 6ee80610 review); a Windows testing claim in the same sentence as the canonical clause ("Requires Python 3.12 or newer, and Windows 3.15 is tested too; CI tests ...") is reported (adversarial, added after the dbfefc57 review, red first).

`tests/test_spikes_lfp_restatements.py` (8 tests; the 17-099 spikes part, commits `915cd91a` to `88a6eeec`).

## 4. Residual limitations

The checks are lexical. Each one reads words, not meaning. The equivalence of each restatement is judged by reading
at the candidate SHA (section 5). The residual classes below pass the checks; the review found them, and they are
not tests.

- Decline weakeners that avoid the listed verbs: "The decline outcome is a choice.", "Declining is not compulsory.",
  "Where the caller prefers, a skill answers instead of declining.", "Decline is not the usual outcome.", "A skill
  that cannot decline is complete.", "Skills decline ... only on request.", "Skills decline only when the user asks them to.", "Declining is a last resort.", "Unsupported inferences are answered with a best guess." The verb list now has "never", "must not", "will not", "not allowed to", "don't", "doesn't", "won't", "shouldn't" and "mustn't", so those sentences are reported; the forms above pass, and so does "cannot" (below).
- Counts that pass: an ordinal ("A fifth outcome is to guess.", "A sixth outcome is to guess."), a range ("Every task ends in three or four outcomes."), and an addition ("Every task ends in four outcomes plus a fallback."). A count reads a number word from one to ten, or a digit, with up to two modifier words before "outcomes"; a count word followed by "of", "or", "and" or "plus" is not read, so the real "one of four outcomes" is not a count. The digit form "4 outcomes" and "4 possible outcomes" are reported as a different count, a false positive that is harmless.
- Modal "cannot", and an inversion: "A skill cannot decline unsupported inference." passes. Adding "cannot" to the verb list would flag `.github/CONTRIBUTING.md:296` ("A skill that cannot decline is incomplete."), which states the rule correctly, so the modal stays unlisted. "A skill that declines is incomplete." passes: a sentence that makes declining the fault is not read.
- An edit to an existing sentence outside the required phrases (found by the 6ee80610 review): "Declining is a correct outcome." changed to "a wrong outcome." and "never turned" changed to "sometimes turned" in `docs/architecture.md`; "four outcomes" extended to "four outcomes or None" in `docs/api.md`. The checks read the phrases and counts, not the sentence around them.
- A floor qualified after the floor: "Requires Python 3.12 only." is now reported (a second floor sentence). A version claim after the floor, "3.12 or newer, and 3.11 with patches" on `docs/index.md`, passes, because the version check reads only "Python X.Y".
- A Windows claim with no testing word: "Windows users need 3.14 or older." passes. The Windows check needs a testing word beside Windows.
- A qualifier on a prohibition: "Never pool across them in the same trial." (`skills/jnwb/SKILL.md`) reads as a prohibition; "in the same trial" is not in the exception list.
- Diagram order (non-blocking): the architecture diagram puts failure after execution, while `preflight` decides failure before execution from a caller declaration. The text says "in the order drawn above". No check reads the order.
- Modality clause (owner decision): `docs/architecture.md:132` says "Signals of distinct modalities are never pooled". It is wider than S16, which names spikes and LFP, and no fact row holds the wider claim. It is not a contradiction. The owner decides whether S16 widens or the sentence narrows.
- Count and edge: the required phrases are matched anywhere in a file. A contradicting sentence beside the real one
  passes, unless it carries a count of outcomes other than four. The diagram's arrows are not read; a flipped edge
  (`S -->|yes| DC[Decline]`) passes (probe 12). The labels are case-insensitive regexes read anywhere in the file, not exact text: "Return the verified result" is not
  one of the required labels, so changing it to "Return the guess" passes (review probe 75, dbfefc57 round).
- Python version claims that do not contradict the set by a version number: a version inside the set stated as
  unsupported or as Windows-only ("Python 3.15 is unsupported.", "Python 3.15 on Windows is supported.", "The 3.15
  build runs on Windows nightly.") passes (probes 17, 19, 26).
- Python version claims without the word "Python": "Tested on 3.12 to 3.15." and "(3.9 also works)" pass (probes 23,
  25). A new support claim with another platform, "Supports 3.12 through 3.15 on Linux and macOS.", is not read (probe
  20).
- Spikes and LFP: a sentence that states the rule without a pooling word is not read ("Combine spikes and LFP in one
  array.", "Merge them for plotting."; probes 27, 28); a sentence that makes pooling a caller's choice ("Pooling is a
  choice for the caller.", probe 30) passes; a sentence split by `;` carries its contradiction without a pooling word;
  "namespaced or not" from S16 is dropped by three restatements, which keeps the prohibition unconditional.
- Version claim with a range word and no number: "Python versions older than 3.12 may work." passes (checked in the 4ef9c443 round). The version check reads "Python" followed by a number, so a range word escapes it.
- Restatements that no checker reads: `jnwb/ontology.py:374-380` (docstring), `skills/jnwb/SKILL.md:36` (routing prose on the outcomes), and `.github/CONTRIBUTING.md:12-13` (the Python floor and "seven legs"). Their equivalence rests on the review alone.
- Count qualifier before the number: "at least four outcomes" and "more than four outcomes" pass. The count reads the number and the words after it, not a qualifier before it.
- Other count nouns: "three outcome classes", "three result categories" and "4 end states" pass. The count reads the noun "outcomes" only.
- Number words outside one to ten: "eleven", "zero", "several" and "a dozen" outcomes pass.
- A second floor in other words: "Needs Python 3.13 or later." passes. The floor check reads "Requires Python" and "or newer" only.
- Version spellings the version regex misses: lowercase "python 3.9", "python3.9", "Python 3" with no minor, and "PyPy 3.10" pass. The regex reads a capital "Python", optional spaces or a comparison operator, then a minor version (review observations, ce738cd2 round).
- A spikes and LFP premise contradicted with no pooling word: "Spikes and LFP are the same observable." passes. Changing "distinct physical observables" to "the same physical observable" in `skills/jnwb/SKILL.md` also passes. The spikes check reads pooling words, not the premise (review observation, ce738cd2 round).
- False positives, harmless: "should not be pooled", "shouldn't be pooled", "never get pooled", "Don't pool spikes and LFP." and "Never fully pool spikes and LFP." are reported by the spikes/LFP check. Rewordings of `.github/CONTRIBUTING.md:296` that state the rule correctly, such as "can't decline", "does not decline", "never declines" and "Declining is not optional", are reported by the decline check, and "One test checks outcomes." is reported by the count check (review observations, 4ef9c443 and ce738cd2 rounds). "local field potentials" spelled out is reported by the spikes check, and so is a pooling sentence that carries "across", "both" or "them" with unrelated content, such as "pool across trials" (review observation, dbfefc57 round).
- Required text that is not rendered: the same phrases inside an HTML comment (`<!-- -->`), struck through (`~~`), or in a mermaid fence changed to plain text pass, because the checks read raw text (review probes 78, 80 to 82 and 84, dbfefc57 round).
- Count after the noun, split by punctuation, singular or hyphenated: "The number of outcomes is five.", "a five-outcome scheme", "the four, or sometimes five, outcomes" and "four outcomes or five" pass. The count reads a number word or digit before "outcomes" (dbfefc57 round).
- A pronoun borrows every signal word in its block: "Never pool spikes and EEG. Never pool them. LFP is separate." passes when the three sentences share one block, because "them" takes the block's words. Split by a blank line, the same sentences are reported (dbfefc57 round; confirmed in the 0b1bd026 review).
- Permission verb beyond the decline window: "A skill may, when the caller explicitly asks it to, decline an unsupported inference." passes, because the decline check reads only 30 characters between the verb and "decline" (0b1bd026 review, kind d).
- A rule called false or revoked with words outside the contrast list, in a sentence with a pooling word: "It is false that spikes and LFP are never pooled." and "Never pool spikes and LFP, as the rule is outdated." pass (0b1bd026 review, kind d).
- Windows spelling variants: "Also tested on windows." and "Also tested on Win11." pass, because the Windows check matches only the capitalised word "Windows" (0b1bd026 review, kind d).
- Gate coverage: gate 8 reads two pages; the index page is covered by its test only. No gate was changed.
- The page tests require the canonical sentence in full, so a page reworded to another true sentence fails loudly.
  That is intended, and a person must re-approve the sentence.

## 5. Review record

| Candidate | Review | Verdict | Outcome |
|---|---|---|---|
| `05c88a78` | fresh reviewer, 2026-11-25 | REVISE | eight weakening and Windows probes passed; fixed at `b380fb15` (decline verbs widened; the page check requires the canonical sentence in full; tests added) |
| `b380fb15` | not completed | none | the suite and the review were stopped after a wrong provenance line in 17-144 was found; corrected at `fff7a1b3` |
| `fff7a1b3` | fresh reviewer, 2026-11-25 | REVISE | 18 misses among 29 scored probes (probe 9 void, probe 20 no verdict; 10 correct): 3 fixed by the count, floor-count and version-set checks (probes 7, 16, 21), 15 are the residual classes in section 4. Also: the checklist rows 58 and 74 were stale; the candidate SHA was not recorded here; a duplicate sentence in the 17-144 provenance |
| `6ee80610` | fresh reviewer, 2026-11-25 | REVISE | Equivalence by reading holds for every restatement; 26 tests passed. Blocking: the 17-144 provenance rows (Recycle Bin said absent, System Volume said readable) and the unrecorded residuals in section 4 (owner condition d). Fixed at the next candidate. 30 probes: 10 correct, 1 false positive, 19 misses. Three cheap misses (never decline, a floor written "only", "Python>=3.10") are now reported, with red tests first; the rest are section 4 residuals |
| `4ef9c443` | fresh reviewer, 2026-11-25 | REVISE | No blockers. Equivalence by reading holds for every restatement, with none contradicting its record. Major: section 4 was incomplete (owner condition d); the classes it named are recorded above at the next candidate. 67 probes: one void, 66 scored; every miss outside the new classes falls in a class section 4 already records. The 17-144 counts were not reproduced (17-144 evidence, section 5). |
| `ce738cd2` | fresh reviewer, 2026-11-25 | REVISE | No blockers. Major M1: section 4 incomplete (owner condition d). Seven classes passed the checks and were not recorded: contraction negatives, a qualifier before the number, other count nouns, number words outside one to ten, a second floor in other words, version spellings, and a spikes and LFP premise with no pooling word. Minors: restatements outside sections 1 and 2 (now in section 1 and section 2a), extra false positives, and the 17-144 `-path` count. 96 probes: 31 reported, 65 pass (not reproduced by the dbfefc57 review, whose input did not include those probes). Red and green confirmed for the two new tests. The contraction class is fixed at the next candidate; the rest are recorded in section 4 |
| `dbfefc57` | fresh reviewer, 2026-11-25 | REVISE | No blockers; every restatement matches its record, and no real sentence fails. Major F1: section 4 misstated the label check ("exact text"); corrected above. Minor F2: a Windows testing claim in the same sentence as the canonical clause passed; a clear contradiction, fixed at the next candidate, red first. Minors F3 to F6 (unrendered text, count forms, pronouns, false positives) are recorded in section 4. 88 probes: every other passing probe is an instance of a class section 4 already names. |
| `0b1bd026` | final reviewer, 2026-11-25 | ACCEPT | No defects of kind (a) to (c). The Windows-clause fix was checked red and green; the real pages pass; the record checks pass, with one precision point (the pronoun bullet, now corrected). The three kind (d) classes the review found are recorded in section 4 by the record commit that follows (artifacts only; that commit is not separately reviewed). |
| owner decision | recorded after the owner's answer | pending | accept review-based equivalence for 17-099, with section 4 as the recorded, non-exhaustive residual list, or keep 17-099 blocked |
