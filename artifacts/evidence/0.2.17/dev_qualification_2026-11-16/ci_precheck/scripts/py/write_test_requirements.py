"""Write the test, docs, vis and wavemap extras of ./pyproject.toml to the file named in argv[1]."""
import pathlib
import sys
import tomllib

extras = tomllib.load(open("pyproject.toml", "rb"))["project"]["optional-dependencies"]
requirements = extras["test"] + extras["docs"] + extras["vis"] + extras["wavemap"]
pathlib.Path(sys.argv[1]).write_text("\n".join(requirements))
print(f"{len(requirements)} requirement(s) written")
