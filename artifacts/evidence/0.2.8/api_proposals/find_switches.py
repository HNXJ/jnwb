"""List every public export whose signature takes an execution switch."""
import inspect
import pathlib
import sys

WT = pathlib.Path(r"C:/workspace/jnwb/.claude/worktrees/lane-c-08-06")
sys.path.insert(0, str(WT))
import jnwb  # noqa: E402

assert pathlib.Path(jnwb.__file__).resolve().is_relative_to(WT), jnwb.__file__
SWITCHES = ("device", "backend", "n_jobs", "precision", "dtype", "use_gpu", "gpu")
print("jnwb", jnwb.__version__, "from", jnwb.__file__)
rows = []
for name in sorted(jnwb.__all__):
    obj = getattr(jnwb, name)
    targets = [(name, obj)]
    if inspect.isclass(obj):
        targets = [(f"{name}.__init__", obj.__init__)] + [
            (f"{name}.{m}", f) for m, f in inspect.getmembers(obj, inspect.isfunction)
            if not m.startswith("_")]
    for label, fn in targets:
        if not callable(fn):
            continue
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        hit = {p: sig.parameters[p].default for p in sig.parameters if p in SWITCHES}
        if hit:
            rows.append((label, hit, getattr(fn, "__module__", "?")))
for label, hit, mod in rows:
    print(f"{label:45} {mod:28} {hit}")
print("count", len(rows))
