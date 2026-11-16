r"""Terminal-cell edge of the t2 differential: is a final cell ending in an escaped pipe observed, and is it right?

Usage: python terminal_cell_check.py <differential script> <tree> [<tree> ...]

For every reader of the differential harness, one valid document whose data row's LAST cell is `<value>\|`, in
three closings: `spaced` (`| a | v\| |`), `open` (no trailing delimiter: `| a | v\|`), `tight` (`| a | v\||`).
Oracle, written here and independent of any tree: an escaped pipe is ordinary text, so the last cell is the
value followed by a pipe, the backslash kept or dropped. A reader OBSERVES the last cell when its result on the
same row without the escape holds the value as a whole string (a parsed cell; a reader that returns the raw
line does not count). Only then is the row judged: OK when a string of the result equals `<value>\|` or
`<value>|`, WRONG otherwise.

Scope (Hamm 2026-11-16, provisional): `spaced` is inside the scored T2 contract. `open` and `tight` are
exploratory: outside the bounded contract, neither invalid syntax nor correct behaviour. Their WRONG lines on
the baseline, the corrected reference and v1 to v3 are known oracle failures (`.strip("|")` removes the escaped
pipe's bar), recorded here and unscored.
Prints one line per tree, reader and closing that is observed, then per tree
`TERMINAL tree=<name> scored observed=<n> ok=<n> wrong=<n> | exploratory observed=<n> ok=<n> wrong=<n>`.
"""
import importlib.util
import json
import pathlib
import sys

MARK = "zq9term"
CLOSINGS = {"spaced": " |", "open": "", "tight": "|"}
SCORED = ("spaced",)


def load(path):
    spec = importlib.util.spec_from_file_location("t2_differential", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(d):
    inputs = []
    for name, _entry, prefix, header_cells, pools in d.READERS:
        cells = [pool[0] for pool in pools]
        head = prefix + d.render(header_cells, "|", "|", False) + "\n" + d.canonical_sep(len(header_cells)) + "\n"
        body = "|" + "|".join(f" {c} " for c in cells[:-1]) + "| " + MARK
        for closing, tail in CLOSINGS.items():
            for kind, escape in (("plain", ""), ("escaped", d.BSL + "|")):
                inputs.append({"id": f"{name}|{closing}|{kind}", "reader": name,
                               "doc": head + body + escape + tail + "\n"})
    return inputs


def strings(value):
    """Every string in a JSON value, keys included."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings(item)


def main(argv):
    if len(argv) < 2:
        print("usage: python terminal_cell_check.py <differential script> <tree> [<tree> ...]", file=sys.stderr)
        return 2
    d = load(argv[0])
    inputs = build(d)
    path = pathlib.Path("D:/pytest_temp/t2diff_terminal_inputs.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inputs), encoding="utf-8")
    good = {MARK + d.BSL + "|", MARK + "|"}
    for tree in argv[1:]:
        tree = pathlib.Path(tree).resolve()
        results = d.run_child(tree, path, "doc")["results"]
        tally = {"scored": [0, 0, 0], "exploratory": [0, 0, 0]}
        for name, *_ in d.READERS:
            for closing in CLOSINGS:
                plain = {s.strip() for s in strings(results[f"{name}|{closing}|plain"])}
                escaped = results[f"{name}|{closing}|escaped"]
                if MARK not in plain:
                    continue  # the reader does not return this cell as a parsed cell
                found = [s.strip() for s in strings(escaped) if MARK in s]
                right = any(s in good for s in found)
                scope = "scored" if closing in SCORED else "exploratory"
                tally[scope][0] += 1
                tally[scope][1 if right else 2] += 1
                shown = found[0] if found else json.dumps(escaped)[:60]
                print(f"{tree.name} {name} {closing} [{scope}] {'OK' if right else 'WRONG'} cell={shown!r}")
        print(f"TERMINAL tree={tree.name} " + " | ".join(
            f"{scope} observed={n} ok={ok} wrong={wrong}" for scope, (n, ok, wrong) in tally.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
