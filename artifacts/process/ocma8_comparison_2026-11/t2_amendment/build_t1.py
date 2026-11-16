"""Build negative control t1: the corrected reference with a splitter that drops an escaped pipe ending the last cell."""
import pathlib
import subprocess
import sys

base, reference, out = (pathlib.Path(a) for a in sys.argv[1:4])
subprocess.run(["git", "clone", "-q", "--shared", str(base), str(out)], check=True, stdin=subprocess.DEVNULL)
for path in sorted((reference / "scripts").glob("*.py")):
    target = out / "scripts" / path.name
    data = path.read_bytes()
    if not target.exists() or target.read_bytes() != data:
        target.write_bytes(data)
path = out / "scripts" / "md_cells.py"
source = path.read_bytes()
old = b'    return [cell.strip() for cell in re.split(r"(?<!\\\\)\\|", body)]'
assert source.count(old) == 1, source.count(old)
nl = b"\r\n" if b"\r\n" in source else b"\n"
new = (b'    cells = [cell.strip() for cell in re.split(r"(?<!\\\\)\\|", body)]' + nl
       + b'    cells[-1] = cells[-1].removesuffix("\\\\|").rstrip()' + nl + b"    return cells")
path.write_bytes(source.replace(old, new))
print(path.read_bytes().decode()[-330:])
