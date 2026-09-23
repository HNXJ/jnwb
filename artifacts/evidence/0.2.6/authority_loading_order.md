# Authority loading-order comparison — evidence for ruling 06-61 (P-14)

Assembled by a critic. **No candidate is selected here.** The ruling is Hamm's.

Baseline: `HEAD d7023484daf8a82cb52236250370fe8719c69276`, `git status --short` empty.
Every value below was re-resolved against disk at that HEAD; none is quoted from recall.

---

## 1. The disagreement (P-14), quoted from both sources

### `skills/jnwb-fact-action/SKILL.md`, lines 13–19

```
13  ## 2. Mandatory Authority Loading Order
14  Before inspecting or altering code, an agent MUST load authorities in strict sequence:
15  1. `AGENTS.md` (repository invariants, operational rules, workflow grammar)
16  2. `artifacts/fact_stack.md` (human-authorized durable facts)
17  3. `artifacts/todo_stack.md` (unresolved executable work)
18  4. Relevant domain skill (e.g. `jnwb-nwb-data`, `jnwb-lfp-spectral`, `jnwb-statistics`)
19  5. Current repository evidence (re-read targets, execute probes, inspect live tree)
```

### `AGENTS.md`, lines 124–131 (§3 Loop, Prepare)

```
124  - **Prepare** — load, in order: (1) `AGENTS.md` (this file), (2) `artifacts/goal.md`,
125    (3) `artifacts/fact_stack.md`, (4) `artifacts/state.md`, regenerating it first if
126    `scripts/reconstruct_state.py --check` fails, (5) `artifacts/problem_stack.md`,
127    (6) `artifacts/todo_stack.md`, (7) relevant skills (§7), (8) current repository evidence
128    (re-read targets, run probes, collect receipts). Order the remaining work; define
129    acceptance. A fact is not proof that mutable repository state currently satisfies it. If
130    evidence contradicts a fact, surface the conflict to Hamm — do not silently rewrite the
131    fact or the evidence.
```

**The two lists are not the same order stated twice.** The skill names 5 sources; §3 names 8.
Three of the five `X` slots — `goal`, `state`, `problem` — have no source at all in the skill's
list. The stop condition of this packet ("the candidates turn out to be the same order stated
twice") does **not** fire, and P-14 is **not** a not-a-defect.

Set difference, sources named by §3 and absent from the skill:

| Source | Slot it is the only source for | Present in skill §2 |
|---|---|---|
| `artifacts/goal.md` | `goal` | No |
| `artifacts/state.md` (+ `--check` gate) | `state` | No |
| `artifacts/problem_stack.md` | `problem` | No |

A third disagreement is not a set difference but an ordering one: §3 loads `goal` **before**
`fact`, so a fact that contradicts the ruled goal is caught at load time. The skill loads `fact`
second with nothing above it but the router.

---

## 2. The slots, and who owns them

From `AGENTS.md` §2, lines 82–88 (the table that defines the five slots and their edit rights):

| Slot | File | Agents may edit? |
|---|---|---|
| goal | `artifacts/goal.md` | No — Hamm rules it |
| state | `artifacts/state.md` | Generated only — `python scripts/reconstruct_state.py` |
| fact | `artifacts/fact_stack.md` | No — challenge with evidence; surface conflicts to Hamm |
| problem | `artifacts/problem_stack.md` | Yes — add on discovery; close by repair/accept/falsify |
| todo | `artifacts/todo_stack.md` | Yes — delete finished; add unresolved |

### Which slot each source is AUTHORITATIVE for

Applies to every candidate; the candidates differ in which of these sources they reach, not in
who owns what.

| Source | goal | state | fact | problem | todo | Authoritative for |
|---|---|---|---|---|---|---|
| `AGENTS.md` | leaks (§11 acceptance) | — | leaks (§4 invariants, §5 vocabulary) | — | — | **none of the five.** It is the router: it defines the slot schema and the loop. Its §4/§5/§11 content in slots it does not own is exactly P-15. |
| `artifacts/goal.md` | **writes** | — | — | — | — | **goal** |
| `artifacts/fact_stack.md` | — | — | **writes** | — | — | **fact** |
| `artifacts/state.md` | — | **writes** | — | — | reports counts | **state** — and only when `reconstruct_state.py --check` passes; a stale copy is authoritative for nothing |
| `artifacts/problem_stack.md` | — | — | — | **writes** | — | **problem** |
| `artifacts/todo_stack.md` | leaks (per-item `Accept:`) | — | — | — | **writes** | **todo** |
| Domain skill (`skills/jnwb-*`) | — | — | leaks (routing rows hardcode signatures) | — | — | **none of the five.** Procedure and capability, not `X`. |
| Current repository evidence | — | **writes** | falsifies applicability | may create | — | **state** at the top of §1's within-evidence order (`receipt on disk > live repository state > machine-readable state files > prose`). It can falsify whether a fact still applies; it cannot rewrite the fact (§2 line 117). |

---

## 3. The candidates

Four. A and B are the two orders that exist on disk today. C and D are the two coherent
alternatives a ruling could reach instead of simply picking A or B.

`—` = the candidate never loads a source for that slot.

### Candidate A — the skill's order as written (`SKILL.md` §2, status quo of the skill)

Order: `AGENTS.md` → `fact_stack.md` → `todo_stack.md` → domain skill → evidence

| # | Source | goal | state | fact | problem | todo |
|---|---|---|---|---|---|---|
| 1 | `AGENTS.md` | leak (§11) | — | leak (§4, §5) | — | — |
| 2 | `artifacts/fact_stack.md` | — | — | **fact** | — | — |
| 3 | `artifacts/todo_stack.md` | leak (`Accept:`) | — | — | — | **todo** |
| 4 | domain skill | — | — | leak (rows) | — | — |
| 5 | current repository evidence | — | **state** (ad hoc) | falsifies | — | — |
| | **slots reached** | **NO** | partial, ungated | yes | **NO** | yes |

**Conflict-resolution rule.** The skill states two rules and no general one:
`SKILL.md` line 25 — evidence contradicting a fact → stop and surface to Hamm;
line 29 — conflicting conclusions between roles → empirical receipts and discriminating tests,
never voting. It states no rule for two sources writing the same slot, because within its list no
two sources write the same slot. `AGENTS.md` §1 lines 70–72 supply the general rule by inheritance
(the skill loads `AGENTS.md` first), but only for conflicts the agent can see.

**Contradiction with the stated orderings.** Consistent with `Hamm > task > AGENTS.md > universal
> defaults` in what it ranks, but it cannot apply that ordering to `goal.md`, which is the
highest-authority artifact in the tree (`AGENTS.md` §2: "No — Hamm rules it"). An order that never
loads Hamm's ruling cannot rank it. It also omits the `--check` gate, so where it reads `state.md`
opportunistically it puts a stale machine-readable file where §1 puts live repository state.

---

### Candidate B — `AGENTS.md` §3 Prepare as written (status quo of the router)

Order: `AGENTS.md` → `goal.md` → `fact_stack.md` → `state.md` (regenerate if `--check` fails) →
`problem_stack.md` → `todo_stack.md` → skills → evidence

| # | Source | goal | state | fact | problem | todo |
|---|---|---|---|---|---|---|
| 1 | `AGENTS.md` | leak (§11) | — | leak (§4, §5) | — | — |
| 2 | `artifacts/goal.md` | **goal** | — | — | — | — |
| 3 | `artifacts/fact_stack.md` | — | — | **fact** | — | — |
| 4 | `artifacts/state.md` (+`--check`) | — | **state** | — | — | reports counts |
| 5 | `artifacts/problem_stack.md` | — | — | — | **problem** | — |
| 6 | `artifacts/todo_stack.md` | leak (`Accept:`) | — | — | — | **todo** |
| 7 | relevant skills (§7) | — | — | leak (rows) | — | — |
| 8 | current repository evidence | — | **overrides** | falsifies | may create | — |
| | **slots reached** | yes | yes, gated | yes | yes | yes |

**Conflict-resolution rule.** `AGENTS.md` §1 lines 70–72, verbatim: "the receipt on disk, then
live repository state, then machine-readable state files, then prose. Unresolved conflict on a
material point stops the work and surfaces both sides." Plus §3 lines 129–131: evidence
contradicting a fact surfaces to Hamm rather than rewriting either side. Plus §2 line 117: current
evidence can falsify whether a fact applies; it does not authorize rewriting it.

Where two sources write the same slot the rule is therefore *source class*, not load position:
evidence (8) beats `state.md` (4) beats prose (1, 2, 3, 5, 6) — except that `goal.md` and
`fact_stack.md` are human-ruled prose whose contradiction by evidence is a **stop**, not an
override.

**Contradiction with the stated orderings.** None found. Loading `goal.md` at position 2 and
`--check`-gating position 4 is what makes `Hamm > … > AGENTS.md` and `receipt > live > state file
> prose` both applicable.

---

### Candidate C — the skill carries no list and points at `AGENTS.md` §3

Order: identical to B by construction. The skill's §2 becomes one line: *load the authorities in
`AGENTS.md` §3 Prepare, in that order*, with no second enumeration.

Mapping: **identical to Candidate B's table.** Conflict rule: identical to B.

What distinguishes C from B is not the order but the number of places the order is written.
Today there are two, and they have already drifted — which is P-14. C makes drift structurally
impossible rather than test-detectable, and satisfies the operating contract's "A is a thin
router … Never duplicate project truth", which is the same contract P-15 is filed against.

Cost, stated plainly: a packet that loads only the skill no longer sees the order inline and must
follow one pointer. The pointer is to the one file §0 line 4 already calls "the only
repository-level instruction file", so the hop is to a file the skill's own step 1 already loads.

**Contradiction with the stated orderings.** None found.

---

### Candidate D — evidence-first (`AGENTS.md` §1's precedence read as a *load* order)

Order: evidence → `state.md` → `AGENTS.md` → `goal.md` → `fact_stack.md` → `problem_stack.md` →
`todo_stack.md` → domain skill

| # | Source | goal | state | fact | problem | todo |
|---|---|---|---|---|---|---|
| 1 | current repository evidence | — | **state** | — | may create | — |
| 2 | `artifacts/state.md` (ungated) | — | overwrites (1) | — | — | reports counts |
| 3 | `AGENTS.md` | leak (§11) | — | leak (§4, §5) | — | — |
| 4 | `artifacts/goal.md` | **goal** | — | — | — | — |
| 5 | `artifacts/fact_stack.md` | — | — | **fact** | — | — |
| 6 | `artifacts/problem_stack.md` | — | — | — | **problem** | — |
| 7 | `artifacts/todo_stack.md` | leak (`Accept:`) | — | — | — | **todo** |
| 8 | domain skill | — | — | leak (rows) | — | — |
| | **slots reached** | yes | yes, **ungated** | yes | yes | yes |

**Conflict-resolution rule.** Last writer in load order wins. That is what reading a precedence
list as a load order means, and it is the flaw: position 2 overwrites position 1 with a file that
ranks *below* it in §1.

**Contradiction with the stated orderings — shown, not asserted.** §1 ranks live repository state
above machine-readable state files. D loads live evidence first and the state file second, so
under last-writer-wins the lower-ranked source wins. It also runs probes at position 1, before
`AGENTS.md` at position 3 — before the file that says which evidence counts, which stops bind, and
that a shared worktree makes a clean `git status` "independently true and jointly meaningless"
(§8 lines 250–252). It is included because it is the obvious misreading of §1 and the ruling
should exclude it on the record.

Observation: §1's list is a **conflict-resolution precedence**, not a load order. Nothing in
`AGENTS.md` proposes D. It is a candidate only in the sense that it is the reading a packet could
arrive at from §1 alone.

---

## 4. Adversarial example — real files, real content, demonstrated

### The example

Two files in this tree, at `HEAD d7023484`, clean:

| File | Line | Content on disk |
|---|---|---|
| `artifacts/state.md` | 27 | `| Uncommitted paths | 6 |` |
| `artifacts/state.md` | 24 | `| HEAD | `e2698280275398891172d904730c1eb4e5c80509` |` |
| `artifacts/state.md` | 64 | `| `artifacts/todo_stack.md` | 56 items |` |
| `.git` (live) | — | `git status --porcelain=v1` → **0 lines** |
| `artifacts/todo_stack.md` (live) | — | 59 items matching `^### \d\d-\d\d ` |

`artifacts/state.md` is gitignored (`.gitignore:137`) and generated. It was generated at commit
`e2698280`, and HEAD has since moved to `d7023484`, so it is **stale right now**:

```
$ python scripts/reconstruct_state.py --check
ERROR: artifacts/state.md was generated at e26982802753 and HEAD is now d7023484daf8.
Run: python scripts/reconstruct_state.py
(exit 1)
```

### The stop it collides with

`AGENTS.md` §8, lines 255–257: "If exclusive ownership cannot be established, STOP before editing.
If you find uncommitted changes you did not make, follow the single-writer recovery protocol".

### The divergence, run

`scratchpad/loading_order/demonstrate.py` reconstructs the `state` slot from exactly the sources
each candidate names, in that candidate's order, and applies §8:

| Candidate | `state.md` handling | `Uncommitted paths` it ends up with | Verdict on §8 |
|---|---|---|---|
| **A** | never loaded; read opportunistically if at all, never `--check`ed | **6** | **STOP** — six unowned changes |
| **B** | loaded, `--check` gated → check fails → regenerate | **0** | **PROCEED** — clean tree, sole writer |
| **C** | loaded, `--check` gated → check fails → regenerate | **0** | **PROCEED** — clean tree, sole writer |
| **D** | loaded, not `--check` gated → stale file accepted, overwriting the live probe | **6** | **STOP** — six unowned changes |

Same tree, same HEAD, same second. A and D halt the work on a phantom concurrent writer; B and C
proceed. **The outcome differs under at least two candidates**, which is this packet's acceptance
condition, and it differs on a *stop condition*, not on a cosmetic value.

The mechanism is precise: it is not that A lacks `state.md`, it is that A lacks the `--check`
**gate**. D loads the file and still fails, because the gate and not the file is what makes the
state slot trustworthy. A ruling that adds `artifacts/state.md` to the skill's list without
carrying over "regenerating it first if `scripts/reconstruct_state.py --check` fails" buys nothing
— it converts A into D.

### Second example, on a different slot (goal vs fact)

Also real, also on disk, and it separates A from B/C/D rather than {A,D} from {B,C}:

| Source | Line | Says |
|---|---|---|
| `artifacts/fact_stack.md` | 58 | "CI tests the declared floor and newest supported version." |
| `artifacts/goal.md` | 68 | "Python 3.12, 3.13 and 3.14. Every claimed version is exercised in CI" |
| `AGENTS.md` | 200–202 | "CI tests every declared version. Amended 2026-09-19: this said 'the floor and the newest declared version', which is the policy that let 0.2.5 ship a 3.13 classifier no CI leg exercised." |
| `.github/workflows/workflow.yml` | 46 | `python-version: [ "3.12", "3.13", "3.14" ]` — three legs |

The `fact` slot still carries the exact policy `AGENTS.md` §6 says was amended away, and that
`goal.md` — the slot Hamm rules — contradicts.

| Candidate | Outcome |
|---|---|
| **A** | `goal.md` never loaded. The superseded policy is the only thing in the `fact` slot and is carried forward unflagged. An agent trimming CI to "floor and newest" would be following the fact slot correctly. |
| **B, C, D** | `goal.md` and `fact_stack.md` both in hand → Hamm-ruled goal contradicts the fact → **surface the conflict to Hamm** (§3 lines 129–131). |

This is a live, unrecorded contradiction in the `fact` slot, found only because `goal.md` was
loaded. It is evidence for P-14's severity and is **not** in the problem stack; see §6.

---

## 5. Stale-pointer resolution (required: resolve every named entry against disk)

Every path named in the skill's loading list, in `AGENTS.md` §3 Prepare, in §7, and in the §0 map,
resolved at `HEAD d7023484`:

| Named in | Path | On disk |
|---|---|---|
| `SKILL.md` §2 items 1–4 | `AGENTS.md`, `artifacts/fact_stack.md`, `artifacts/todo_stack.md`, `skills/jnwb-nwb-data`, `skills/jnwb-lfp-spectral`, `skills/jnwb-statistics` | all **EXIST** |
| `SKILL.md` §6 | `scripts/harness_gate.py`, `tests/test_skills_validation.py` | both **EXIST** |
| `AGENTS.md` §3 | `artifacts/goal.md`, `artifacts/state.md`, `artifacts/problem_stack.md`, `scripts/reconstruct_state.py` | all **EXIST** |
| `AGENTS.md` §7 | 9 skills | all 9 **EXIST**, names match |
| `AGENTS.md` §0 | 21 further paths | all **EXIST** |
| `AGENTS.md` §2 line 99 | `docs/fact_stack.md`, `docs/todo_stack.md` | **MISSING** — conditional ("when the repository has no `artifacts/`"); the condition is false here, so not stale |
| `artifacts/agents/` | 6 role files vs the §0 list and the skill's `ROLE:` enum | all **EXIST**, three-way match |

**No stale pointer in either loading list.** P-14 is a content disagreement, not a broken
reference.

---

## 6. Two findings the ruling should have in front of it

### 6a. A test currently pins the skill's side of the disagreement

`tests/test_harness_adversarial_gates.py`, `test_mandatory_authority_loading_order_specified`
(lines 641–652) hardcodes the five-item list:

```python
expected_order = [
    "AGENTS.md",
    "artifacts/fact_stack.md",
    "artifacts/todo_stack.md",
    "domain skill",
    "evidence",
]
for item in expected_order:
    assert item in skill_text
```

It asserts *containment*, not agreement, and it lists one side — which is precisely what 06-61's
acceptance forbids ("asserts the agreement by parsing both, not by listing either"). It is
satisfied by the current divergent state and would remain green under Candidates B and D (they are
supersets of the five strings) but **fails under Candidate C**, where the skill no longer
enumerates `artifacts/fact_stack.md` or `artifacts/todo_stack.md` inline. Choosing C requires
rewriting this test in the same change; choosing B does not force it but leaves the acceptance
condition unmet.

### 6b. An unrecorded contradiction in the `fact` slot

`artifacts/fact_stack.md` line 58 states the interpreter-CI policy that `AGENTS.md` §6 lines
200–202 record as amended away and that `artifacts/goal.md` line 68 contradicts.

It is **not** recorded in `artifacts/problem_stack.md`. The nearest row, `P-C6` (line 82), is
`accepted` and is about the *shipped v0.2.5 artifact* carrying an untested 3.13 classifier; no row
records that the `fact` slot still asserts the policy that caused it. Per `AGENTS.md` §2 line 86
the `fact` slot is not agent-editable, so this is Hamm's to rule. It is a direct instance of the
damage Candidate A's omission causes rather than a separate topic: the contradiction is invisible
to any packet that follows the skill's order.

### 6c. Scope note

Todo item 06-70 declares `Writes: artifacts/evidence/0.2.6/authority_loading_order.md`. This packet's ALLOWED
SCOPE forbids every write inside `C:\workspace\jnwb`. This table was therefore written to the
scratchpad only, and `artifacts/evidence/0.2.6/authority_loading_order.md` does **not** exist. Promoting it is a
separate authorized action.

---

## 7. Summary for the ruling

| | A (skill today) | B (§3 today) | C (skill points at §3) | D (evidence-first) |
|---|---|---|---|---|
| goal slot reached | **no** | yes | yes | yes |
| state slot reached | no (ungated if at all) | yes, gated | yes, gated | yes, **ungated** |
| fact slot reached | yes | yes | yes | yes |
| problem slot reached | **no** | yes | yes | yes |
| todo slot reached | yes | yes | yes | yes |
| general conflict rule | inherited, unusable on unloaded slots | §1 explicit | §1 explicit | last-writer-wins |
| contradicts `Hamm > … > AGENTS.md` | yes — cannot rank a ruling it never loads | no | no | no |
| contradicts `receipt > live > state file > prose` | yes — no `--check` gate | no | no | yes — state file overwrites live probe |
| order written in N places | 2 (drifted) | 2 (drifted) | **1** | 2 |
| Example 1 verdict | STOP (phantom) | PROCEED | PROCEED | STOP (phantom) |
| Example 2 verdict | carries superseded fact | surface to Hamm | surface to Hamm | surface to Hamm |
| existing test | green | green | **fails, must be rewritten** | green |

Reproduce everything above:

```
python scratchpad/loading_order/demonstrate.py     # candidate divergence
python scripts/reconstruct_state.py --check        # exit 1, the stale-state receipt
git rev-parse HEAD && git status --short           # d7023484, clean
```
