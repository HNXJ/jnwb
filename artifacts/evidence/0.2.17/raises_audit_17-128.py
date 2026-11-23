"""17-128: list public functions whose own body raises a type their Raises section omits.

The walk lives in ``tests/test_public_raises_documented.py`` (one home); this prints its result.
Run from the tree under test: ``python artifacts/evidence/0.2.17/raises_audit_17-128.py``.
Exit 0 when nothing is undocumented outside the test's exclusions, 1 otherwise, 2 when nothing
was examined.

Receipts: at baseline fc0d61da, 163 functions examined, 10 undocumented (assert_mergeable,
bipolar_reference, causal_exp_smooth, causal_gaussian_smooth, epoch_continuous, granger,
inspect, label_layers, probe_geometry, repair_nwb), 0 unresolved. With the walk extended to
nested functions the public function uses, at 75a6312a: 2 undocumented (acquisition_channel,
assert_mergeable).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(
        "raises_walk", ROOT / "tests" / "test_public_raises_documented.py")
    walk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(walk)
    missing, unresolved, examined = walk.audit()
    for name, (path, line, excs) in sorted(missing.items()):
        tag = " (excluded)" if name in walk.EXCLUDED else ""
        print(f"{Path(path).resolve().relative_to(ROOT).as_posix()}:{line} {name}: "
              f"{', '.join(excs)}{tag}")
    for name, path, line, why in unresolved:
        print(f"UNRESOLVED {name} {path}:{line}: {why}")
    print(f"functions examined: {len(examined)}; undocumented: {len(missing)}; "
          f"unresolved raises: {len(unresolved)}")
    if not examined:
        return 2
    return 1 if set(missing) - set(walk.EXCLUDED) or unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
