r"""Structure of the table-row splitting under scripts/ for experiment task t2 (amendment 2).

Usage: python t2_structure.py <tree> <baseline tree>

Prints `P1 <PASS|FAIL|AMBIGUOUS> ...` (consolidation) and `P2 <PASS|FAIL|AMBIGUOUS> ...` (removal). Exit 0 when
it runs to the end, 2 on a usage error. Standard library only; reads source, runs nothing from either tree.

The check is bounded to the eight baseline split sites (SITES) and reads AST relationships, not source spelling.

Delimiter definition: the place a function body splits text on a pipe. Recognised forms, in a function's body:
  a. `<x>.split(P)` / `<x>.rsplit(P)` and `re.split(P, ...)` where P is a string constant holding `|`, or a name
     bound to one (in the function or at module level, imported names included);
  b. `<pattern>.split(...)` where <pattern> is `re.compile(<such a constant>)`, inline or bound to a name;
  c. a `==` / `!=` comparison with the constant `"|"` inside a `for` or `while` loop (a character scan).
Its identity is the module-level name when the pipe pattern is bound at module level (two functions sharing one
compiled pattern are one definition), otherwise the function that holds it. `strip("|")` is not a split.

Anchors: for a baseline splitter definition, the baseline functions of its module that call it; for a baseline
inline split, the function that holds it. Anchors are computed from the baseline tree. In the tree under test
each anchor's reachable definitions are those in its own body and in every function it reaches by a call the
AST resolves inside scripts/ (local functions, module-level `g = f` and `g = lambda ...: f(...)`,
`from m import f [as g]`, `import m [as n]` then `n.f`), to depth 8. Definitions in functions that already split on a pipe at the baseline outside the eight sites are
left out (UNRELATED, computed from the baseline).

P1 PASS       every anchor of every site reaches exactly one definition, the same one for all eight sites.
P1 FAIL       two anchors each reach a recognised definition and have none in common: those two readers do
              not share one implementation, wherever the splitters live.
P1 AMBIGUOUS  neither: an anchor is missing from the tree, an anchor reaches no recognised definition (a form
              outside a to c, or a call the AST cannot resolve), or every pair of anchors shares a definition
              while more than one is reached. AMBIGUOUS is not a rejection: the cell goes to independent
              adjudication.
P2 PASS       no baseline site function and no anchor holds a definition in its own body, the shared one of a
              passing P1 excepted.
P2 FAIL       two or more such definitions remain, or one remains while P1 passes on another.
P2 AMBIGUOUS  P1 does not pass and exactly one such definition remains (it may be the shared one).
"""

import ast
import pathlib
import sys

#: Baseline (ac995dde) split sites: (file, function that holds the split, kind). For `def` the function is the
#: splitter definition itself; for `inline` it is the reader function whose body holds the split.
DEF_SITES = (
    ("scripts/build_dashboard.py", "_cells"),
    ("scripts/build_fact_graph.py", "_cells"),
    ("scripts/learning_gate.py", "_cells"),
    ("scripts/release_gate.py", "_cells"),
    ("scripts/release_gate.py", "_table_cells"),
)
#: Inline sites by (file, baseline line); the enclosing function is read from the baseline tree.
INLINE_SITES = (
    ("scripts/build_fact_graph.py", 399),
    ("scripts/docs_form_gate.py", 285),
    ("scripts/reconstruct_state.py", 224),
)
DEPTH = 8


def is_pipe_text(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and "|" in node.value


def is_compile_of_pipe(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "compile"
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "re"
            and bool(node.args) and is_pipe_text(node.args[0]))


class Module:
    """One file under scripts/: its functions, its imports from scripts/, its module-level pipe names."""

    def __init__(self, tree_root, path):
        self.rel = path.relative_to(tree_root).as_posix()
        self.key = path.relative_to(tree_root / "scripts").with_suffix("").as_posix().replace("/", ".")
        self.ast = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        self.functions = {}       # name -> [FunctionDef]
        self.from_imports = {}    # local name -> (module key, attribute)
        self.module_aliases = {}  # local name -> module key
        self.pipe_names = set()   # module-level names bound to a pipe constant or a compiled pipe pattern
        self.aliases = {}         # module-level `a = b`
        for node in ast.walk(self.ast):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions.setdefault(node.name, []).append(node)
            elif isinstance(node, ast.ImportFrom):
                base = (node.module or "").lstrip(".")
                base = base[len("scripts."):] if base.startswith("scripts.") else ("" if base == "scripts" else base)
                for alias in node.names:
                    local = alias.asname or alias.name
                    self.from_imports[local] = (base, alias.name)
                    self.module_aliases.setdefault(local, f"{base}.{alias.name}" if base else alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name[len("scripts."):] if alias.name.startswith("scripts.") else alias.name
                    self.module_aliases[alias.asname or alias.name.split(".")[-1]] = name
        for node in self.ast.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if is_pipe_text(node.value) or is_compile_of_pipe(node.value):
                    self.pipe_names.add(name)
                elif isinstance(node.value, ast.Name):
                    self.aliases[name] = node.value.id
                elif isinstance(node.value, ast.Lambda):
                    node.value.name = name  # a module-level `name = lambda ...` delegates like a function
                    self.functions.setdefault(name, []).append(node.value)


class Tree:
    def __init__(self, root):
        self.root = root
        self.modules = {}
        for path in sorted((root / "scripts").rglob("*.py")):
            if "__pycache__" not in path.parts:
                module = Module(root, path)
                self.modules[module.key] = module
        self.by_rel = {m.rel: m for m in self.modules.values()}

    def pipe_name(self, module, name, seen=()):
        """(module key, name) when `name` in `module` is a module-level pipe name, following one import."""
        if name in module.pipe_names:
            return module.key, name
        target = module.from_imports.get(name)
        if target and target[0] in self.modules and (module.key, name) not in seen:
            return self.pipe_name(self.modules[target[0]], target[1], seen + ((module.key, name),))
        return None

    def definitions(self, module, fn):
        """Identities of the delimiter definitions in the body of `fn`."""
        own = (module.key, "fn", fn.name)
        local_pipe = set()
        for node in ast.walk(fn):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and (is_pipe_text(node.value) or is_compile_of_pipe(node.value))):
                local_pipe.add(node.targets[0].id)

        def ident(node):
            """Identity when `node` is a pipe constant, a compiled pipe pattern, or a name bound to one."""
            if is_pipe_text(node) or is_compile_of_pipe(node):
                return own
            if isinstance(node, ast.Name):
                if node.id in local_pipe:
                    return own
                found = self.pipe_name(module, node.id)
                return (found[0], "name", found[1]) if found else None
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id in module.module_aliases):
                other = self.modules.get(module.module_aliases[node.value.id])
                if other and node.attr in other.pipe_names:
                    return other.key, "name", node.attr
            return None

        found = set()
        loops = [n for n in ast.walk(fn) if isinstance(n, (ast.For, ast.While, ast.AsyncFor))]
        in_loop = {id(sub) for loop in loops for sub in ast.walk(loop)}
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("split", "rsplit"):
                receiver = node.func.value
                candidates = [ident(receiver)]
                args = list(node.args) + [kw.value for kw in node.keywords if kw.arg in ("sep", "pattern")]
                if args:
                    candidates.append(ident(args[0]))
                found.update(c for c in candidates if c)
            elif isinstance(node, ast.Compare) and id(node) in in_loop:
                sides = [node.left] + list(node.comparators)
                if (all(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)
                        and any(isinstance(s, ast.Constant) and s.value == "|" for s in sides)):
                    found.add(own)
        return found

    def callees(self, module, fn):
        """(module, FunctionDef) for every call in `fn` that resolves to a function under scripts/."""
        out = []
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                name = func.id
                for _ in range(DEPTH):  # module-level `a = b` chains
                    if name in module.functions or name not in module.aliases:
                        break
                    name = module.aliases[name]
                if name in module.functions:
                    out.extend((module, f) for f in module.functions[name])
                elif name in module.from_imports:
                    base, attr = module.from_imports[name]
                    other = self.modules.get(base)
                    if other and attr in other.functions:
                        out.extend((other, f) for f in other.functions[attr])
            elif isinstance(func, ast.Attribute):
                owner = func.value
                key = None
                if isinstance(owner, ast.Name):
                    key = module.module_aliases.get(owner.id)
                elif isinstance(owner, ast.Attribute):
                    key = owner.attr
                other = self.modules.get(key) if key else None
                if other and func.attr in other.functions:
                    out.extend((other, f) for f in other.functions[func.attr])
        return out

    def reach(self, module, fn):
        """Every (module, FunctionDef) reachable from `fn`, itself included."""
        seen, frontier, order = {(module.key, id(fn))}, [(module, fn)], [(module, fn)]
        for _ in range(DEPTH):
            nxt = []
            for mod, func in frontier:
                for other, callee in self.callees(mod, func):
                    if (other.key, id(callee)) not in seen:
                        seen.add((other.key, id(callee)))
                        nxt.append((other, callee))
                        order.append((other, callee))
            frontier = nxt
        return order


def enclosing(module, line):
    best = None
    for fns in module.functions.values():
        for fn in fns:
            if fn.lineno <= line <= fn.end_lineno and (best is None or fn.lineno > best.lineno):
                best = fn
    return best.name if best else None


def baseline_plan(base):
    """Sites as [(label, file, site function, [anchor names])] and the UNRELATED (module key, function) set."""
    sites = []
    for rel, name in DEF_SITES:
        module = base.by_rel[rel]
        anchors = sorted({fn.name for fns in module.functions.values() for fn in fns if fn.name != name
                          and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name
                                  for n in ast.walk(fn))})
        sites.append((f"{rel}:{name}", rel, name, anchors))
    for rel, line in INLINE_SITES:
        module = base.by_rel[rel]
        name = enclosing(module, line)
        sites.append((f"{rel}:{line}", rel, name, [name]))
    site_functions = {(base.by_rel[rel].key, fn) for _, rel, fn, _ in sites}
    unrelated = set()
    for module in base.modules.values():
        for fns in module.functions.values():
            for fn in fns:
                if (module.key, fn.name) not in site_functions and base.definitions(module, fn):
                    unrelated.add((module.key, fn.name))
    return sites, unrelated


def show(ident):
    return f"{ident[0]}.{ident[2]}" + ("" if ident[1] == "fn" else " (module name)")


def evaluate(tree, base):
    sites, unrelated = baseline_plan(base)
    reached_by, reached_all, ambiguous = {}, set(), []
    for label, rel, _, anchors in sites:
        module = tree.by_rel.get(rel)
        for anchor in anchors:
            fns = module.functions.get(anchor) if module else None
            if not fns:
                ambiguous.append(f"{label}: anchor {anchor} missing")
                continue
            reached = set()
            for fn in fns:
                for mod, func in tree.reach(module, fn):
                    if (mod.key, func.name) not in unrelated:
                        reached |= tree.definitions(mod, func)
            if not reached:
                ambiguous.append(f"{label}: anchor {anchor} reaches no recognised split")
            else:
                reached_by[f"{label} via {anchor}"] = reached
            reached_all |= reached
    shared = next(iter(reached_all)) if len(reached_all) == 1 and not ambiguous else None
    names = sorted(reached_by)
    apart = next(((a, b) for i, a in enumerate(names) for b in names[i + 1:]
                  if not reached_by[a] & reached_by[b]), None)
    if shared:
        p1 = "PASS", f"all eight sites reach one definition: {show(shared)}"
    elif apart:
        a, b = apart
        p1 = "FAIL", (f"no shared definition between [{a}] -> {sorted(show(i) for i in reached_by[a])} and "
                      f"[{b}] -> {sorted(show(i) for i in reached_by[b])}; "
                      f"{len(reached_all)} definitions reached in all")
    else:
        p1 = "AMBIGUOUS", (f"definitions reached {sorted(show(i) for i in reached_all) or 'none'}; "
                           f"unresolved {ambiguous or 'none'}")

    remaining = set()
    for label, rel, site_fn, anchors in sites:
        module = tree.by_rel.get(rel)
        for name in [site_fn] + list(anchors):
            for fn in (module.functions.get(name, []) if module else []):
                remaining |= {i for i in tree.definitions(module, fn) if i[1] == "fn" and i != shared}
    listed = sorted(show(i) for i in remaining)
    if not remaining:
        p2 = "PASS", "no baseline site function or anchor holds a split of its own"
    elif shared or len(remaining) > 1:
        p2 = "FAIL", f"splits kept in baseline site functions or anchors: {listed}"
    else:
        p2 = "AMBIGUOUS", f"one split remains and P1 did not pass: {listed}"
    return p1, p2, len(sites), sum(len(a) for *_, a in sites)


def main(argv):
    if len(argv) != 2 or not all((pathlib.Path(a) / "scripts").is_dir() for a in argv):
        print("usage: python t2_structure.py <tree> <baseline tree>", file=sys.stderr)
        return 2
    tree, base = (Tree(pathlib.Path(a).resolve()) for a in argv)
    p1, p2, n_sites, n_anchors = evaluate(tree, base)
    print(f"P1 {p1[0]} {p1[1]} [{n_sites} sites, {n_anchors} anchors]")
    print(f"P2 {p2[0]} {p2[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
