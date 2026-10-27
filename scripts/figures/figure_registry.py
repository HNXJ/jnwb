"""The figure registry: one entry per documentation figure, written by the generator's run.

The docs hook reads it to write each figure's state line and its Interactive tab. The figure tests
read it to find a stale entry or an unlisted unconvertible panel. Only the generator writes it,
with `--write-registry`.
"""
from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, Dict

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "figure_registry.toml"
#: The sources whose bytes decide a figure's drawing and its interactive form.
CODE_FILES = ("generate_figures.py", "figure_style.py", "figure_interactive.py")


def code_sha256(folder: Path = HERE) -> str:
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode("ascii") + b"\0" + (folder / name).read_bytes())
    return digest.hexdigest()


def state_line(entry: Dict[str, Any]) -> str:
    seeds = ", ".join(str(seed) for seed in entry["seeds"]) or "none"
    unit = entry["n_unit"] if entry["n"] != 1 else entry["n_unit"][:-1]  # units are plural in the generator
    return (f"Validation: {entry['status']} | N = {entry['n']:,} {unit} | seed {seeds} | "
            f"input {entry['input_sha256'][:12]} | jnwb {entry['jnwb_version']}")


def loads(text: str) -> Dict[str, Dict[str, Any]]:
    return tomllib.loads(text)


def dumps(entries: Dict[str, Dict[str, Any]]) -> str:
    lines = ["# Written by scripts/figures/generate_figures.py --write-registry; do not edit.", ""]
    for name in sorted(entries):
        entry = entries[name]
        lines.append(f"[{json.dumps(name)}]")
        lines.append(f"status = {json.dumps(entry['status'])}")
        lines.append(f"n = {int(entry['n'])}")
        lines.append(f"n_unit = {json.dumps(entry['n_unit'])}")
        lines.append(f"height_px = {int(entry['height_px'])}")
        lines.append("seeds = [" + ", ".join(str(int(seed)) for seed in entry["seeds"]) + "]")
        lines.append(f"input_sha256 = {json.dumps(entry['input_sha256'])}")
        lines.append(f"code_sha256 = {json.dumps(entry['code_sha256'])}")
        lines.append(f"jnwb_version = {json.dumps(entry['jnwb_version'])}")
        lines.append("unconvertible = [" + ", ".join(json.dumps(r) for r in entry["unconvertible"]) + "]")
        lines.append("")
    return "\n".join(lines)
