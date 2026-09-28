import json
from pathlib import Path

r = json.loads((Path(__file__).parent / "report.json").read_text(encoding="utf-8"))
print({k: r[k] for k in ("version", "commit", "N", "seeds", "surrogates", "alpha")})
print("\nA: page blocks")
for row in r["A_rows"]:
    print(" ", row["block"], row["status"], row["seconds"], "s", row["warnings"])
print("\nB: rate p<0.05  (X->Y / Y->X), expected, median net")
for name, ests in r["B_rates"].items():
    exp = r["B_expected"][name]
    print(f"  {name}  expected X->Y={exp[0]} Y->X={exp[1]}")
    for est, v in ests.items():
        ok = (v["rate_x_to_y"] >= 0.8 if exp[0] else v["rate_x_to_y"] <= 0.15) and \
             (v["rate_y_to_x"] >= 0.8 if exp[1] else v["rate_y_to_x"] <= 0.15)
        print(f"    {est:18s} {v['rate_x_to_y']:.2f} / {v['rate_y_to_x']:.2f}  net {v['median_net']:+.4f}"
              f"  nan {v['nan_p']}  {'OK' if ok else 'MISS'}")
print("\nC:", json.dumps(r["C"], indent=1))
print("\nD:", json.dumps(r["D"], indent=1))
