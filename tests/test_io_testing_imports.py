"""The static detector that keeps library modules off `jnwb.testing`.

The scan itself is written inline in `tests/test_api_surface.py`, which is not a file this change
may write. This file runs that module's two helpers, `_imported_modules` and `_is_testing`, over a
planted library tree, so a detector that stops flagging `import jnwb.testing` fails here too.

Not covered: `importlib.import_module` and `__import__`. The static walk does not see either form.
No current jnwb path loads `jnwb.testing` that way; `jnwb/__init__.py` loads only its export table.
"""

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Appended, not prepended, as in the other test modules: the wheel leg runs without the checkout.
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from tests import test_api_surface as surface  # noqa: E402

REPO_ROOT = Path(surface.__file__).resolve().parents[1]


def _violations(root: Path) -> list[str]:
    """What the no-generators scan reports for the library tree `root/jnwb`, one line per module."""
    found = []
    for path in sorted((root / "jnwb").rglob("*.py")):
        rel = path.relative_to(root / "jnwb")
        if "__pycache__" in rel.parts or rel.parts[0] == "testing":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        flagged = sorted(m for m in surface._imported_modules(tree, ["jnwb", *rel.parts[:-1]])
                         if surface._is_testing(m))
        if flagged:
            found.append(f"jnwb/{rel.as_posix()} imports {flagged}")
    return found


@pytest.mark.parametrize("source, flagged", [
    ("import jnwb.testing.synth\n", True),
    ("from jnwb.testing import nwb_fixtures\n", True),
    ("def f():\n    from ..testing.synth import x\n", True),
    ("import numpy as np\nfrom jnwb import spectral\n", False),
], ids=["import", "from-import", "relative-from-a-subpackage", "clean"])
def test_each_import_form_of_the_generators_is_flagged_in_a_planted_module(
    tmp_path, source, flagged
):
    module = tmp_path / "jnwb" / "analysis" / "planted.py"
    module.parent.mkdir(parents=True)
    module.write_text(source, encoding="utf-8")
    found = _violations(tmp_path)
    if flagged:
        assert len(found) == 1 and "analysis/planted.py" in found[0], found
    else:
        assert found == []


def test_the_shipped_library_has_no_module_that_imports_the_generators():
    assert _violations(REPO_ROOT) == []
