"""Local notebook cell executor via exec() — not SSH/remote.

For remote SSH/SCP workflows, see:
  .agents/skills/remote-ssh-and-file-management/SKILL.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def run_notebook(path: Path) -> bool:
    print(f"=== Executing Notebook (local): {path} ===")
    with path.open("r", encoding="utf-8") as f:
        nb = json.load(f)

    namespace: dict = {}
    try:
        import matplotlib

        matplotlib.use("Agg")
    except ImportError:
        pass

    for idx, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if not source.strip():
            continue
        print(f"--- Running Cell {idx} ---")
        try:
            exec(source, namespace)
        except Exception as exc:
            print(f"Error in Cell {idx}: {exc}")
            import traceback

            traceback.print_exc()
            return False
    print(f"=== Successfully executed: {path} ===\n")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebook", type=Path, help="Path to .ipynb file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.notebook.is_file():
        print(f"Notebook not found: {args.notebook}", file=sys.stderr)
        sys.exit(2)
    ok = run_notebook(args.notebook)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
