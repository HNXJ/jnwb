"""
Unified Labyrinth Knowledge Graph Compiler
===========================================
Compiles all individual .lab/*.json nodes into single-file unified formats:
1. Markdown (`artifacts/.lab/labyrinth_unified.md`) - **Ultra-compact (~4.7k tokens)**
   Designed specifically for instant, low-cost context injection into LLM prompts.
2. JSON (`artifacts/.lab/labyrinth_unified.json`) - **Structured Full Lossless (~40k tokens)**
   Full lossless representation for programmatic loading or full-context inspection.

Usage:
    python clients/lab_compile.py --lab artifacts/.lab --format unified
    or run standalone: python scripts/compile_unified_labyrinth.py
"""

import json
import pathlib
import sys
from datetime import date


def compile_unified_labyrinth(lab_dir: pathlib.Path, out_dir: pathlib.Path) -> Dict[str, str]:
    lab_files = sorted(list(lab_dir.glob("*.json")))
    # Exclude any previously generated unified json files if placed in same dir
    nodes = []
    for f in lab_files:
        if f.name.startswith("labyrinth_unified") or f.name.startswith("optimized_"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            nodes.append(data)
        except Exception as e:
            print(f"Warning: Failed to parse {f.name}: {e}", file=sys.stderr)

    today = str(date.today())

    # ── 1. Full Lossless JSON ──────────────────────────────────────────────────
    unified_json_struct = {
        "title": "Unified Labyrinth Knowledge Graph",
        "compiled_at": today,
        "node_count": len(nodes),
        "schema_version": 3,
        "nodes": nodes,
    }
    json_path = out_dir / "labyrinth_unified.json"
    json_path.write_text(json.dumps(unified_json_struct, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── 2. Compact Agent-Optimized Markdown ────────────────────────────────────
    md_lines = [
        f"# UNIFIED LABYRINTH KNOWLEDGE GRAPH",
        f"*Compiled: {today} | Total Nodes: {len(nodes)}*",
        "",
        "---",
        "",
    ]

    # Group by kind for fast cognitive scanning
    by_kind = {}
    for n in nodes:
        k = n.get("kind", "note").lower()
        by_kind.setdefault(k, []).append(n)

    kind_order = ["goal", "decision", "evidence", "hypothesis", "plan", "reflection", "note", "checkpoint"]
    ordered_kinds = [k for k in kind_order if k in by_kind] + [k for k in by_kind if k not in kind_order]

    for k in ordered_kinds:
        md_lines.append(f"## {k.upper()}S ({len(by_kind[k])})")
        md_lines.append("")
        for n in by_kind[k]:
            nid = n.get("id", "unknown")
            title = n.get("title", "")
            status = n.get("status", "unconfirmed")
            notes = n.get("notes", [])
            issues = n.get("issues", [])
            plan = n.get("plan", [])
            ver = n.get("verification", {})

            status_symbol = {
                "confirmed": "✓",
                "provisional": "⚡",
                "unconfirmed": "?",
                "completed": "✓",
                "planned": "☐",
                "contested": "✗",
                "superseded": "⟲"
            }.get(status, "•")

            md_lines.append(f"### {status_symbol} `{nid}`: {title}")
            md_lines.append(f"- **Status**: `{status}`")

            if notes:
                md_lines.append(f"- **Notes**:")
                for note in notes:
                    md_lines.append(f"  - {note}")
            if issues:
                md_lines.append(f"- **Issues**:")
                for issue in issues:
                    md_lines.append(f"  - {issue}")
            if plan:
                md_lines.append(f"- **Plan**: {', '.join(plan) if isinstance(plan, list) else plan}")
            if ver:
                md_lines.append(f"- **Verification**: {ver}")
            md_lines.append("")

    md_path = out_dir / "labyrinth_unified.md"
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")

    json_chars = json_path.stat().st_size
    md_chars = len(md_text)

    print(f"Compiled {len(nodes)} Labyrinth nodes:")
    print(f"  1. Markdown : {md_path} ({md_chars:,} chars, ~{md_chars // 4:,} tokens)")
    print(f"  2. JSON     : {json_path} ({json_chars:,} chars, ~{json_chars // 4:,} tokens)")

    return {"markdown": str(md_path), "json": str(json_path)}


if __name__ == "__main__":
    repo_root = pathlib.Path(__file__).parent.parent
    lab_dir = repo_root / "artifacts" / ".lab"
    compile_unified_labyrinth(lab_dir, lab_dir)
