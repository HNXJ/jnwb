"""Write the declared core dependency floors of ./pyproject.toml to argv[1], as the floors job does."""
import pathlib
import sys

sys.path.insert(0, ".")
from scripts.release_gate import declared_dependency_floors  # noqa: E402

core = [(name, floor) for extra, name, floor in declared_dependency_floors() if not extra]
pathlib.Path(sys.argv[1]).write_text("".join(f"{n}>={f}\n" for n, f in core))
print(f"{len(core)} core floor(s) written")
