"""Gate 17 (stack pointers): every Skill, Role and Blocked-by resolves."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
from scripts.gates.stacks_form import (
    TODO_STACK, _FIELD_LABEL, _ITEM_ID, _code_span_mask,
)
from scripts.stack_parse import stack_items as _stack_items


#: The placeholder forms a `Skill:` field may carry instead of a skill directory name. A closed
#: set and not a prefix rule: `per skil` must fail, and it does. A placeholder may take a trailing
#: qualifier after a comma -- 06-25 writes `per skill, nine packets` -- so the head segment is what
#: is matched, and the qualifier is prose the gate does not read.
SKILL_PLACEHOLDERS = frozenset({"none", "per skill", "per module", "per finding", "per chain"})

#: `Role:` values naming a person rather than an agent file. Same shape as the skill placeholders:
#: `human, with verifier receipts` is `human` plus a qualifier.
ROLE_PLACEHOLDERS = frozenset({"human", "human ruling", "none"})

#: The three fields gate 17 resolves. `Reads:` and `Writes:` name paths and are gate 15's.
_RESOLVED_FIELDS = ("Skill", "Role", "Blocked by")


def _field_value(body: str, label: str) -> Optional[Tuple[int, str]]:
    """The value of `label:` in an item body, as (offset of the label, value).

    Three things make this harder than a line regex, and each of them was measured on the live
    stack rather than anticipated:

    * **The value wraps.** Fields are hard-wrapped mid-declaration, so the value ends at the next
      field label or the paragraph break, never at the newline.
    * **A field label appears inside a code span.** One heading reads "Resolve every
      ``Skill:`` field against ``skills/``", and a scanner that reads it extracts the value
      ``` ` field against `skills/` ``` and reports a missing skill directory -- a false positive
      manufactured by the item that asked for the gate. `_code_span_mask` is what excludes it.
    * **The value ends at a sentence, not at the label alone.** `Skill: none. Blocked by: none.`
      bounds on the next label, but the last field in a paragraph has no next label.
    """
    mask = _code_span_mask(body)
    for match in re.finditer(re.escape(label) + r":", body):
        if mask[match.start()]:
            continue  # the label is quoted, not declared
        rest = body[match.end():]
        offsets = [len(rest)]
        following = _FIELD_LABEL.search(rest)
        if following:
            offsets.append(following.start())
        paragraph = rest.find("\n\n")
        if paragraph != -1:
            offsets.append(paragraph)
        value = rest[:min(offsets)]
        return match.start(), " ".join(value.split())
    return None


def _declared_name(value: str) -> str:
    """A field value reduced to the thing it names: sentence-terminated, unbackticked."""
    text = value.strip()
    # The sentence the field sits in ends the value; `jnwb-nwb-data. Blocked by: ...` already
    # bounded on the label, but `Blocked by: 06-06.` and a trailing `.` have not.
    text = re.split(r"\.(?:\s|$)", text, maxsplit=1)[0]
    return text.strip().strip("`*").strip().rstrip(".").strip()


def check_stack_pointers_resolve(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 17 (Stack Pointers Resolve): every `Skill:`, `Role:` and `Blocked by:` field names
    something that exists on this tree.

    Two fields declared ``Skill: jnwb-nwb-io``. No such skill has ever existed -- the tree
    holds `jnwb-nwb-data` -- and the name reached two dispatched packets, where nothing errored
    and a packet worked around it silently. The standing rule is that a file pointing at other
    files goes stale without erroring; this pointer never resolved at all, so it did not go
    stale, it was **born wrong**, and a staleness check would not have caught it either. Only
    resolution against the tree catches it, which is what this does.

    Later widened to the cross-references. Of the three directions that widening names, one is
    implemented here and two no longer exist:

    * ``Blocked by:`` -> a live item is **here**. Nothing resolved it before: a parenthesis
      "the blocker direction is checked" refers to a sweep somebody ran, not to a check in any
      script.
    * A problem row's ``Answered in`` -> a live item: `scripts/release_gate.py` STEP 0a requires
      the open stack to hold no row at release, so no such cell is left to resolve.
    * The todo stack's ``P-NN`` -> a problem row: the id labels a row that has left the problem
      stack, and it resolves through that file's git history rather than against the tree.

    **What this gate cannot see**, stated because narrowing a check is how blind spots are made:
    it resolves the *name* and not the *fit*. ``Skill: jnwb-spiking`` on an item about spectra
    resolves and passes. Nothing here reads whether the named skill is the right one, and nothing
    should -- that is a judgement, and a gate that guesses at it would be a proxy.
    """
    root = repo_root or REPO_ROOT
    violations: List[str] = []

    todo_path = root / TODO_STACK
    if not todo_path.is_file():
        return [f"STACK_POINTER: {TODO_STACK} is missing; the sweep is broken, not the tree"]
    text = todo_path.read_text(encoding="utf-8")
    items = _stack_items(text)
    if not items:
        return [f"STACK_POINTER: no item found in {TODO_STACK}; the sweep is broken, not the tree"]
    live = {ident for _, ident, _ in items}

    skills_dir = root / "skills"
    agents_dir = root / "artifacts" / "agents"
    # A sweep that finds no skill directory would pass every item vacuously.
    available_skills = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
    if not available_skills:
        violations.append(
            f"STACK_POINTER: no skills/*/SKILL.md found under {skills_dir}; every Skill: field "
            "would resolve vacuously, so the sweep is broken, not the tree"
        )
    available_roles = {p.stem for p in agents_dir.glob("*.md")}
    if not available_roles:
        violations.append(
            f"STACK_POINTER: no artifacts/agents/*.md found under {agents_dir}; every Role: "
            "field would resolve vacuously, so the sweep is broken, not the tree"
        )

    resolved = 0
    for lineno, ident, body in items:
        for label in _RESOLVED_FIELDS:
            found = _field_value(body, label)
            if found is None:
                violations.append(
                    f"STACK_POINTER: {TODO_STACK}:{lineno} item {ident} declares no '{label}:' "
                    "field; the scheduler reads it, so an absent field is not a silent default"
                )
                continue
            offset, raw = found
            line = lineno + body.count("\n", 0, offset)
            name = _declared_name(raw)

            if label == "Blocked by":
                # Prose blockers ("all repairs", "a Hamm ruling ...") name no item and resolve to
                # nothing. Only the ids are resolvable, and each one must be live.
                #
                # `name`, the first sentence, and NOT the whole label-bounded span. Measured: the
                # span version reported 12 violations on a pristine tree and every one was the
                # parser's. An item that has been unblocked records why on the line after the
                # field -- 06-06 declares `Blocked by: none.` and then "06-01 and 06-02 were both
                # ruled 2026-09-19 and deleted as complete" -- so a span running to the next
                # field label reads the history as the declaration and flags exactly the items
                # that are correctly maintained. **What the narrowing cannot see:** an id in a
                # second sentence of the field. That is deliberate -- after the first full stop
                # the field is narrating, not declaring -- and `test_a_dead_id_in_the_narration_
                # is_not_read_as_a_blocker` plants both shapes to hold the boundary where it is.
                for ref in _ITEM_ID.findall(name):
                    resolved += 1
                    if ref not in live:
                        violations.append(
                            f"STACK_POINTER: {TODO_STACK}:{line} item {ident} is 'Blocked by: "
                            f"{ref}', which is not an item in this stack. A block on a retired "
                            "item is a block that can never lift, and the scheduler reads this "
                            "field."
                        )
                continue

            head = name.split(",")[0].strip().lower()
            if label == "Skill":
                if head in SKILL_PLACEHOLDERS:
                    continue
                segments = [s.strip().strip("`") for s in name.split(",") if s.strip()]
                for segment in segments:
                    resolved += 1
                    if segment not in available_skills:
                        violations.append(
                            f"STACK_POINTER: {TODO_STACK}:{line} item {ident} declares "
                            f"'Skill: {segment}', and skills/{segment}/SKILL.md does not exist. "
                            f"Available: {sorted(available_skills)}. Declared placeholders: "
                            f"{sorted(SKILL_PLACEHOLDERS)}."
                        )
            else:  # Role
                if head in ROLE_PLACEHOLDERS:
                    continue
                resolved += 1
                if name not in available_roles:
                    violations.append(
                        f"STACK_POINTER: {TODO_STACK}:{line} item {ident} declares "
                        f"'Role: {name}', and artifacts/agents/{name}.md does not exist. "
                        f"Available: {sorted(available_roles)}. Declared placeholders: "
                        f"{sorted(ROLE_PLACEHOLDERS)}."
                    )

    # Every item could legally declare `none` for all three fields, and then this gate would pass
    # while resolving nothing. It would still be honest -- there would be nothing to resolve --
    # but it would be indistinguishable from a parser that extracts no values at all, which is
    # this repository's dominant defect shape. So the count is asserted, not assumed.
    if resolved == 0:
        violations.append(
            f"STACK_POINTER: {len(items)} items were read and not one named a skill, a role or a "
            "blocking item. Either the stack genuinely declares nothing, or the field parser is "
            "matching nothing; the gate cannot tell those apart, so it fails rather than pass "
            "vacuously."
        )
    return violations
