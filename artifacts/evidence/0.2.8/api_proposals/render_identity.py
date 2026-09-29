"""Render identity.json as the per-operation markdown tables of execution_identity.md."""
import json
import pathlib
import sys

# LF on every platform: on Windows the default text stdout writes CRLF, and pasting that into an
# LF page produced a file with mixed line endings.
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
CUDA_RTOL = 1e-9


def g(x):
    return "0" if x == 0 else f"{x:.1e}"


dev = {}
for r in data["device"]:
    dev.setdefault(r["op"], {})[r["size"]] = r
nj = {}
for r in data["n_jobs"]:
    nj.setdefault(r["op"], {})[r["size"]] = r
be = {}
for r in data["backend"]:
    be.setdefault(r["size"], []).append(r)
comb = {r["size"]: r for r in data["combined"]}

ops = list(dev) + [o for o in nj if o not in dev]
for op in ops:
    print(f"### `{op}`\n")
    print("| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |")
    print("|---|---|---|---|---|---|---|---|")
    for size in ("small", "large"):
        r = dev.get(op, {}).get(size)
        if r:
            if "error" in r:
                print(f"| `device` | cuda vs cpu | rel. 1e-9 | {size} | error: {r['error'][:80]} | | | ERROR |")
                continue
            cpu_only = r["warned"] and r["recorded"] in ("cpu", None)
            what = "cuda (warns, runs CPU) vs cpu" if cpu_only else "cuda vs cpu"
            verdict = "within" if r["gap"] <= CUDA_RTOL else "EXCEEDS"
            if not r["cpu_repeat_identical"]:
                verdict += "; CPU repeat not identical"
            print(f"| `device` | {what} | rel. 1e-9 | {size} | {g(r['gap'])} | {'yes' if r['bit_identical'] else 'no'} "
                  f"| {r['recorded'] if r['recorded'] is not None else 'not recorded'} | {verdict} |")
    for size in ("small", "large"):
        r = nj.get(op, {}).get(size)
        if r:
            if "error" in r:
                print(f"| `n_jobs` | 2, 4, 8, -1 vs 1 | bit equality | {size} | error: {r['error'][:80]} | | | ERROR |")
                continue
            gaps = [r[f"n{n}"]["gap"] for n in (2, 4, 8, -1)]
            ident = all(r[f"n{n}"]["bit_identical"] for n in (2, 4, 8, -1))
            print(f"| `n_jobs` | 2, 4, 8, -1 vs 1 | bit equality | {size} | worst {g(max(gaps))} "
                  f"| {'yes' if ident else 'no'} | n/a | {'within' if ident else 'EXCEEDS'} |")
    if op == "jrsa":
        for size in ("small", "large"):
            for r in be.get(size, []):
                print(f"| `backend` | {r['backend']} vs numpy | bit equality | {size} | {g(r['gap'])} "
                      f"| {'yes' if r['bit_identical'] else 'no'} | {r['recorded']} | "
                      f"{'within' if r['bit_identical'] else 'EXCEEDS'}{'; warns' if r['warned'] else ''} |")
    if op == "cross_area_coherence":
        for size in ("small", "large"):
            r = comb[size]
            print(f"| `device` + `n_jobs` | cuda, 8 vs cpu, 1 | rel. 1e-9 | {size} | {g(r['gap'])} "
                  f"| {'yes' if r['bit_identical'] else 'no'} | {r['recorded']} | {'within' if r['gap'] <= CUDA_RTOL else 'EXCEEDS'} |")
    print()

print("### Timing (seconds, one call, this machine)\n")
print("| Operation | Size | cpu | cuda |")
print("|---|---|---|---|")
for op, sizes in dev.items():
    for size in ("small", "large"):
        r = sizes.get(size)
        if r and "error" not in r:
            print(f"| `{op}` | {size} | {r['t_cpu_s']} | {r['t_cuda_s']} |")
print()
print("| Operation | Size | n_jobs=1 | 2 | 4 | 8 | -1 |")
print("|---|---|---|---|---|---|---|")
for op, sizes in nj.items():
    for size in ("small", "large"):
        r = sizes.get(size)
        if r and "error" not in r:
            print(f"| `{op}` | {size} | {r['t_n1_s']} | " + " | ".join(str(r[f'n{n}']['t_s']) for n in (2, 4, 8, -1)) + " |")
print()
print("machine:", json.dumps(data["machine"]))
