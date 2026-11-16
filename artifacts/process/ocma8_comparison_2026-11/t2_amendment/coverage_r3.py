"""Generator revision 3: scored inputs per reader and family at the five matrix seeds.

Usage: python coverage_r3.py <t2_differential_r3.py>
Imports the generator from the given path, generates the inputs at each seed and prints, per mode, a table
reader x family of scored inputs summed over the seeds, then every (mode, reader, family) cell that is 0 at
some seed. A family listed for a mode in FAMILY_SHARES must be scored for a reader at every seed, or the cell
is printed as a gap. Exploratory inputs are counted apart.
"""
import collections
import importlib.util
import sys

SEEDS = (2026111600, 1, 2, 3, 4)


def family_of(rec):
    return next((label[4:] for label in rec["labels"] if label.startswith("fam=")), "existing")


def main(argv):
    spec = importlib.util.spec_from_file_location("t2gen", argv[0])
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    readers = [r[0] for r in gen.READERS]
    modes_of = {name: modes for name, _share, modes in gen.FAMILY_SHARES}
    modes_of["existing"] = ("preserved", "corrected")
    per_seed = {seed: collections.Counter() for seed in SEEDS}
    explor = collections.Counter()
    for seed in SEEDS:
        for rec in gen.generate(seed, gen.DEFAULT_ROWS):
            if rec["bucket"] == "exploratory":
                explor[(rec["mode"], family_of(rec))] += 1
            else:
                per_seed[seed][(rec["mode"], rec["reader"], family_of(rec))] += 1
    families = sorted(modes_of)
    gaps = []
    for mode in ("preserved", "corrected"):
        cols = [f for f in families if mode in modes_of[f]]
        print(f"\nMODE {mode}: scored inputs summed over {len(SEEDS)} seeds (rows {gen.DEFAULT_ROWS} per reader and mode)")
        print("reader | " + " | ".join(cols))
        for reader in readers:
            cells = []
            for fam in cols:
                counts = [per_seed[s][(mode, reader, fam)] for s in SEEDS]
                cells.append(str(sum(counts)))
                if min(counts) == 0:
                    gaps.append(f"{mode} | {reader} | {fam} | per seed {counts}")
            print(f"{reader} | " + " | ".join(cells))
    print("\nGAPS (a scored cell that is 0 at some seed):")
    print("\n".join(gaps) if gaps else "none")
    print("\nEXPLORATORY inputs by mode and family, summed over the seeds:")
    for key in sorted(explor):
        print(f"{key[0]} | {key[1]} | {explor[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
