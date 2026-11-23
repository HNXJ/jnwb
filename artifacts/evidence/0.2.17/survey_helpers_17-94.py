import ast
import sys
from pathlib import Path

root = Path(sys.argv[1])
targets = [
    "jnwb/laminar/_xflip.py",
    "jnwb/laminar/_zflip.py",
    "jnwb/laminar/_vflip.py",
    "jnwb/jrsa/__init__.py",
    "jnwb/connectivity/_psi.py",
]
import re


def loose(k):
    # drop string constants and local-name identities: catches same structure with other messages/names
    k = re.sub(r"Constant\(value='[^']*'\)", "Constant(S)", k)
    k = re.sub(r'Constant\(value="[^"]*"\)', "Constant(S)", k)
    return re.sub(r"id='[^']*'", "id=N", k)


def norm(fn):
    body = fn.body
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    args = [a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
    mapping = {a: f"a{i}" for i, a in enumerate(args)}

    class R(ast.NodeTransformer):
        def visit_Name(self, n):
            if n.id in mapping:
                n.id = mapping[n.id]
            return n

        def visit_arg(self, n):
            if n.arg in mapping:
                n.arg = mapping[n.arg]
            n.annotation = None
            return n

    m = ast.Module(body=[R().visit(ast.parse(ast.unparse(b))) for b in body], type_ignores=[])
    return ast.dump(m)


def calls(fn):
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            out.add(f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "?"))
    return out


alldefs = []
for p in sorted((root / "jnwb").rglob("*.py")):
    tree = ast.parse(p.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            alldefs.append((p.relative_to(root).as_posix(), n))
info = [(p, m, norm(m), calls(m)) for p, m in alldefs]
lkeys = [loose(k) for _, _, k, _ in info]
print("defs scanned:", len(info), flush=True)

for t in targets:
    tree = ast.parse((root / t).read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name.startswith("_"):
            key = norm(n)
            c = calls(n)
            exact = [f"{p}:{m.lineno}:{m.name}" for p, m, k, _ in info if not (p == t and m.lineno == n.lineno) and k == key]
            lk = loose(key)
            print_loose = [f"{p}:{m.lineno}:{m.name}" for (p, m, _, _), l2 in zip(info, lkeys) if not (p == t and m.lineno == n.lineno) and l2 == lk]
            same_name =[f"{p}:{m.lineno}" for p, m, _, _ in info if not (p == t and m.lineno == n.lineno) and m.name == n.name]
            # similarity: overlap in called names, same arity
            sim = []
            for p, m, _, cm in info:
                if p == t and m.lineno == n.lineno:
                    continue
                if c and cm and len(c & cm) / len(c | cm) >= 0.6 and len(m.args.args) == len(n.args.args) and len(m.body) <= 3 * len(n.body) + 3:
                    sim.append(f"{p}:{m.lineno}:{m.name}")
            print(f"{t}:{n.lineno}:{n.name} nlines={n.end_lineno - n.lineno + 1}")
            print("   exact:", exact)
            print("   loose:", print_loose)
            print("   same-name:", same_name)
            print("   similar:", sim[:8])
