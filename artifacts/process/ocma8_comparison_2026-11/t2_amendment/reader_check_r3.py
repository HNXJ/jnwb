"""Generator revision 3: per-reader mismatches of one tree at the five seeds, and repeat stability.

Usage: python reader_check_r3.py <t2_differential_r3.py> <base> <out dir> <name>=<tree> [...] [--twice NAME]
Runs the differential for each named tree at each seed, stores stdout as <out dir>/<name>_<seed>.txt, and
prints per tree and seed the DIFF lines' mismatches and every reader with a scored mismatch (READER lines).
A tree named by --twice is run a second time per seed and the two outputs are compared byte for byte.
"""
import concurrent.futures
import hashlib
import pathlib
import re
import subprocess
import sys

SEEDS = (2026111600, 1, 2, 3, 4)
DIFF = re.compile(r"^DIFF (preserved|corrected|exploratory) (?:readers=(\d+) )?inputs=(\d+) mismatches=(\d+)", re.M)
READER = re.compile(r"^READER (\S+) \| preserved n=(\d+) mismatch=(\d+) raised=(\d+) nonempty=(\d+) \| "
                    r"corrected n=(\d+) mismatch=(\d+) raised=(\d+) nonempty=(\d+)", re.M)


def run(job):
    script, base, tree, seed = job
    proc = subprocess.run([sys.executable, script, tree, base, "--seed", str(seed)], capture_output=True,
                          stdin=subprocess.DEVNULL)
    return proc.returncode, proc.stdout


def main(argv):
    twice = set()
    while "--twice" in argv:
        i = argv.index("--twice")
        twice.add(argv[i + 1])
        del argv[i:i + 2]
    script, base, out_dir = argv[0], argv[1], pathlib.Path(argv[2])
    trees = dict(a.split("=", 1) for a in argv[3:])
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(name, seed, rep) for name in trees for seed in SEEDS for rep in range(2 if name in twice else 1)]
    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        results = list(pool.map(run, [(script, base, trees[name], seed) for name, seed, _rep in jobs]))
    got = dict(zip(jobs, results))
    bad = 0
    for name in trees:
        for seed in SEEDS:
            rc, raw = got[(name, seed, 0)]
            (out_dir / f"{name}_{seed}.txt").write_bytes(raw)
            text = raw.decode("utf-8")
            diff = {m: (readers, int(n), int(mm)) for m, readers, n, mm in DIFF.findall(text)}
            readers = READER.findall(text)
            hit = [(r[0], int(r[2]), int(r[6])) for r in readers if int(r[2]) or int(r[6])]
            empty = [r[0] for r in readers if int(r[1]) == 0 or int(r[5]) == 0 or int(r[4]) == 0 or int(r[8]) == 0]
            bad += rc != 0 or len(readers) != 17
            print(f"{name} | seed {seed} | rc {rc} | readers {len(readers)} | "
                  + " | ".join(f"{m} {diff[m][2]}/{diff[m][1]}" for m in ("preserved", "corrected", "exploratory") if m in diff)
                  + f" | readers with scored mismatches (name, preserved, corrected): {hit}"
                  + f" | readers with n=0 or nonempty=0 in a scored mode: {empty}")
            if name in twice:
                rc2, raw2 = got[(name, seed, 1)]
                same = raw == raw2 and rc == rc2
                bad += not same
                print(f"{name} | seed {seed} | repeat byte-equal {same} | sha256 {hashlib.sha256(raw).hexdigest()[:16]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
