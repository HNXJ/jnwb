"""Apply or restore the multi-band `elif` mutant in the lane's connectivity.py, in bytes.

Usage: python mutate_m1.py <worktree> apply|restore
"""
import hashlib
import pathlib
import sys

P = pathlib.Path(sys.argv[1]) / "jnwb" / "connectivity.py"
BACKUP = pathlib.Path(__file__).resolve().parent / "connectivity.m1.pristine"
OLD = (b"                p_coupling = _surrogate_p(null_tot, total, \"two-sided\", scale=n_pairs)\n"
       b"        if jackknife and n_seg >= 3 and jk_per_band:")
NEW = OLD.replace(b"        if jackknife", b"        elif jackknife")

if sys.argv[2] == "restore":
    want = hashlib.sha256(BACKUP.read_bytes()).hexdigest()
    P.write_bytes(BACKUP.read_bytes())
    got = hashlib.sha256(P.read_bytes()).hexdigest()
    assert got == want, (got, want)
    BACKUP.unlink()
    print("restored", got)
else:
    data = P.read_bytes()
    assert data.count(OLD) == 1, data.count(OLD)
    BACKUP.write_bytes(data)
    P.write_bytes(data.replace(OLD, NEW))
    assert P.read_bytes().count(NEW) == 1
    print("pristine", hashlib.sha256(data).hexdigest(),
          "mutant", hashlib.sha256(P.read_bytes()).hexdigest())
