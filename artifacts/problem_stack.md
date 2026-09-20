# Problem stack

Opened 2026-09-19. Every problem detected from this date until the release that empties it.
Companion to `artifacts/todo_stack.md`: the todo stack holds work that was planned, this holds
defects, contradictions and unknowns that were found. A problem may become a todo item; it is
not deleted when it does, it is dispositioned to the item that answers it.

## The rule

A release requires this file to hold no `open` problem. Four dispositions close one:

| Disposition | Meaning |
|---|---|
| `open` | Not yet answered. **Blocks the release.** |
| `repaired` | Fixed, with the commit and the check that would catch its return. |
| `accepted` | Real, not repairable, and the reason is recorded. A published artifact cannot be un-published. |
| `not-a-defect` | Investigated and the premise is false. The evidence that killed it is recorded. |

`accepted` is the dangerous one. It closes a problem without fixing it, so it carries a reason
that would survive someone hostile reading it, and it is never used for something merely
inconvenient to repair.

Emptiness is a fixpoint, ruled 2026-09-19: the release opens when one full pass over the
documentation, the code and both stacks discovers no new problem. Problems found during that
pass re-open it. A pass that finds nothing is the terminating condition, not a date.

## Open

| ID | Problem | Found by | Answered in |
|---|---|---|---|
| P-01 | `scripts/docs_build.py` writes `site/` inside the repository, so no read-only packet can establish that the strict docs build passes. Build status is unknown, not passing. | 06-04 | 06-36 |
| P-02 | 16 review findings reproduce on the live tree and no stack item claims them. | 06-03 | 06-17 |
| P-03 | Three findings need a human ruling on scope before they can be dispositioned: whether the amended agent-vocabulary rule permits the repair that `ai-plumbing/agent-roles-exist-but-ship-nowhere` implies; whether a table declaring itself "Representative API" may omit a module; whether a superseded five-tier test taxonomy still makes `reliability/contributing-taxonomy-is-a-different-one` a defect. | 06-03 | Human ruling, then 06-17 |
| P-04 | `dist/` holds 0.1.1, 0.1.3 and 0.2.4 and no 0.2.5 build, so the distribution-cleanliness test inspects three superseded releases and never the one that shipped. | 06-04 | 06-37 |
| P-05 | Nothing fails if the CI matrix and `PYTHON_CI_REQUIRED` are shrunk together: every existing assertion is a containment, so the untested-classifier gap can return with the suite green and gate 8 printing "all agree". | 06-04 | 06-10 |
| P-06 | `.venv\Scripts\python.exe` collects 2841 tests with 1 error (statsmodels absent); `C:\Python314` collects 2879 with none. Two interpreters disagree on what the suite is. | 06-03 | 06-35 |
| P-16 | This development machine runs pandas 3.0.5 while hdmf 4.3.1 declares `pandas<3`. 20 of 21 active declared requirements are satisfied; that one is violated. CI installs fresh and resolves pandas 2.x, so every green suite run here is in a configuration hdmf declares unsupported, and CI and this machine test different dependency sets. | 06-42 | Open — changes what "the suite is green" means. Plausible common cause of P-06 |
| P-17 | A downstream consumer's 9 of 22 NWB files fail through `jnwb.nwb_io.read_nwb`, refused at `jnwb/nwb_io.py:71` with `MissingRequiredNWBFieldError` because `session_description` is absent on disk. Bare pynwb refuses the same files. `artifacts/goal.md` §4 is adjacent but does not mandate the refusal: it forbids synthetic values "for missing empirical data in an analysis path", and this is metadata outside one. | Peer report, confirmed at `nwb_io.py:66-71` | Open — needs a human ruling before any item is written |
| P-18 | The length-1 attribute squeeze at `jnwb/nwb_io.py:59-64` is silent: no warning, no flag, nothing on the returned object. A caller cannot tell a value was repaired, so a receipt written from a repaired file cannot record that the file needed repair. Measured reachable -- a file with `session_description` and a length-1 device `description` fails through bare pynwb and opens through `read_nwb` with the value a `str` -- and measured unreachable on the consumer's shape, where the refusal at line 71 fires first and HDMF never constructs the Device. | 06-41, and the consumer independently | Open — new observable behaviour on a public read path; a ruling |
| P-23 | `jnwb/nwb_io.py:3` opens "Module-internal: not part of `jnwb.__all__`." The module is not exported, but the one exception class it defines, `MissingRequiredNWBFieldError`, is: `jnwb/__init__.py:234` lists it, `docs/api.md:178` and `docs/errors.md:148` document it, and `tests/test_api_consistency.py:104` asserts it public. A reader hitting the raise at line 71 is told by the file's own first paragraph that nothing here is catchable by name. | 06-41 reproducer | Open — a sentence, repairable under any ruling |
| P-19 | `docs/10_operation_specifications.md:91` describes `label_layers` as returning `Dict[int, str]` "mapping channel index". It is keyed on `probe_geometry.channel_ids`, which are `str` under `synth_laminar_motif`, and they are identifiers rather than indices. Both the type and the word are wrong. | 06-43 | Open — unclaimed; fits Batch 5 |
| P-20 | The unit-to-layer composition works through existing exports and no document or skill shows it. The capability exists and is unreachable by reading. | 06-43 | Open — unclaimed; a documentation item, not an API one |
| P-21 | `metadata.get_all_units_metadata` emits a `layer` column that silently reads `Unknown`, and `addressing.enrich_units_dataframe` writes a column literally named `layer` carrying the geometric taxonomy, not the electrophysiological one. Two exports produce a column of that name whose values are not the labels a reader would expect. | 06-43 | Open — the substitution class of 06-16 |
| P-22 | No export derives `peak_channel_id` from an NWB units table; `jnwb/addressing.py:340` assumes the column exists. | 06-43 | Open — does not block the composition, whose caller supplies it |
| P-14 | `skills/jnwb-fact-action/SKILL.md` declares a Mandatory Authority Loading Order of `AGENTS.md`, `fact_stack`, `todo_stack`, domain skill, evidence. `AGENTS.md` §3 now loads eight, adding `goal.md`, `state.md` and `problem_stack.md`. Packets follow the skill, so they will not load three of the five `X` slots. | This session, creating it | Open — skill files are doctrine-adjacent and need Hamm's ruling, not a unilateral edit |
| P-15 | `AGENTS.md` is 360+ lines against a contract requiring it to be a thin router that never duplicates project truth. The duplication has not been measured, so the size is not yet evidence of a defect. | This session | Open — needs the measurement before any trim |
| P-08 | Two findings that otherwise reproduce carry wrong counts: `doc-assets/module-map-omits-nwb-entry-points` says 36 omitted exports where a probe counts 35, and `ai-plumbing/agent-roles-exist-but-ship-nowhere` says five roles where six exist. | 06-03 | 06-17 |
| P-09 | A shadowing `jnwb` package and a `jnwb.release-backup` sit in `C:\Python314\Lib\site-packages\`. Byte-identical to the checkout today, so nothing is wrong now, and any probe that omits the path insert silently measures the wrong tree. | 06-04 | Open; needs a decision, not a test |
| P-10 | `.gitignore` excludes the 6.7 GB derived cache under `artifacts/developer/.cache/` by extension (`*.pkl`), not by path. A cache file written with any other suffix lands untracked and visible to a careless `git add -A`. | This session | Open |
| P-11 | `git fetch` aborts on this clone: the v0.1.x tag objects are missing, so `git rev-list -n1 v0.2.5` fails and tags must be resolved through `git ls-remote` or `gh`. | Carried, re-observed by 06-04 | Open |
| P-12 | The suite is collection-order fragile: an ad-hoc pytest subset can fail three `test_backend` tests and segfault. Pre-existing and unrelated to any current change. | Carried | Open |
| P-13 | The Write tool refused a `.md` deliverable inside a packet's own declared `Writes` scope, treating it as a report file. The packet reached its acceptance through a generator script instead. A tool constraint made an authorized write indirect. | 06-03 | Open; harness, not repository |

## Closed

| ID | Problem | Disposition | Evidence |
|---|---|---|---|
| P-C1 | A read-only packet's basis was invalidated because this session kept editing the tree while it ran. | `repaired` | Sequencing changed: nothing writes the tree while a packet reads it. Re-run of 06-04 on `026b9a6f` confirmed the tree stable at both ends. |
| P-C2 | `AGENTS.md` named five agent roles where six exist on disk. | `repaired` | `026b9a6f`; `tests/test_harness_adversarial_gates.py` asserts the role set and now also the `ROLE:` enum. |
| P-C3 | `AGENTS.md` and `scripts/harness_gate.py` stated a floor-and-head CI policy that the constant beside them had already replaced. | `repaired` | `265eb01e`. |
| P-C4 | `docs/install.md` made no Python claim while `artifacts/goal.md` asserted the install documentation converges on the supported set. | `repaired` | `026b9a6f`; the page now carries the same sentence as `README.md:41`. |
| P-C5 | `tests/test_skills_validation.py` docstring claimed eight canonical skills against a set of nine. | `repaired` | `026b9a6f`. |
| P-07 | `artifacts/todo_stack.md` item 06-03 said the review graded `public-claims/classifier-3-13-never-tested` as a broken gate; the review files it in the unverified tail at `low`. | `repaired` | The sentence lived inside 06-03, which is complete and therefore deleted (`9a11ffcf`). The ledger dispositions that identifier against the live tree instead. |
| P-C7 | The `state` slot of `X` had no artifact, so the same basis was reconstructed twice in one day into agent transcripts the next packet could not read. | `repaired` | `scripts/reconstruct_state.py` generates `artifacts/state.md`; `--check` reports staleness in 0.3s; `tests/test_state_reconstruction.py` drives both. |
| P-C6 | The published v0.2.5 artifact carries a 3.13 classifier no CI leg exercised. | `accepted` | Unrepairable by definition: a shipped artifact cannot be retested retroactively, and rewriting immutable historical material to look correct was ruled out on 2026-09-19. The release body's "Python 3.12 through 3.14" is true of declared support and was false of tested support when it shipped. Only a subsequent release changes the fact. |
