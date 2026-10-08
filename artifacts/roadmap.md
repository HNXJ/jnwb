# Roadmap

Work deferred past the cycles the todo stack holds, one row per item. An item moves into the
todo stack, with its full text, when its cycle opens; it is never in both files.

A row is `| id | theme | defect | waits | deferred-X.Y.Z |`: the item id, a short theme, the
defect in one line, the reason it waits (AGENTS.md section 11), and the cycle it is deferred to,
later than the declared version. `scripts/release_gate.py` STEP 0a refuses any row that breaks
this form, and `scripts/fact_gate.py` counts each row's id as a live item.

The full text of each item carried here from the todo stack is in
`artifacts/archive/0.2.10/todo_stack_0.2.10.md`, the stack as it stood when this file opened.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
