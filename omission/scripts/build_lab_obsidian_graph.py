#!/usr/bin/env python
"""Render this repo's artifacts/.lab as an Obsidian-style interactive graph.

Why this adapter exists
-----------------------
The renderer lives in the papers repo (see the handout at
``~/.gemini/antigravity/brain/.../obsidian_graph_handout.md``):

    C:/workspace/papers/clients/generate_obsidian_graph_html.py

It cannot be pointed at this repo directly. Measured 2026-08-08 over 374 node files:

* ``LAB_DIR`` / ``OUT_HTML`` are module-level constants hardcoded to ``C:/workspace/papers``.
* It reads edges from ``node["generated"]["links"]`` with a ``target`` key. In this repo
  only 266 of 374 nodes use that shape; 37 use a top-level ``edges`` array and 37 a
  top-level ``links`` array.
* Those edges come in five different key conventions: ``from/to/type`` (28),
  ``rel/target`` (22), ``target/type`` (17), ``from/relation/to`` (5),
  ``reasoning/rel/target`` (3).
* 64 nodes carry ``generated`` as a **string**, which makes the upstream
  ``data.get("generated", {}).get("links", [])`` raise ``AttributeError`` outright --
  the papers loader crashes on this directory rather than degrading.
* 365 nodes key their id as ``id``, 3 as ``node_id``, and 6 have neither.

Run against the papers loader unmodified, the result would be a graph with zero edges
(or a crash). This module normalizes every one of those variants into the single shape
the renderer expects, then hands off to it -- so the visual output stays the upstream
Tokyo-Night Obsidian theme and only the parsing is repo-specific.

Usage
-----
    python scripts/build_lab_obsidian_graph.py                 # both html + md
    python scripts/build_lab_obsidian_graph.py --format md
    python scripts/build_lab_obsidian_graph.py --lab-dir <other>/.lab --format both

Writes ``artifacts/developer/labyrinth/obsidian_graph.{html,md}``.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
from typing import Any, Dict, List

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB_DIR = REPO_ROOT / "artifacts" / ".lab"
OUT_HTML = REPO_ROOT / "artifacts" / "developer" / "labyrinth" / "obsidian_graph.html"
OUT_MD = REPO_ROOT / "artifacts" / "developer" / "labyrinth" / "obsidian_graph.md"
PAPERS_CLIENTS = pathlib.Path("C:/workspace/papers/clients")

SKIP_SUFFIXES = ("-drift.json", "-protocol.json", "-checkpoint.json")

#: Every edge-container / edge-key convention observed in this repo's .lab.
#: Each entry maps an observed dict to (target_id, relation_label).
_TARGET_KEYS = ("to", "target", "dest", "node")
_REL_KEYS = ("type", "rel", "relation", "kind")


def _edge_to_pair(edge: Any) -> tuple[str | None, str]:
    """Normalize one edge record to ``(target_id, relation)``.

    Handles the five key conventions found in this .lab, plus bare-string edges.
    Returns ``(None, "")`` for anything unrecognized rather than raising -- a
    malformed edge should drop out of the graph, not abort the render.
    """
    if isinstance(edge, str):
        return edge, ""
    if not isinstance(edge, dict):
        return None, ""
    target = next((str(edge[k]) for k in _TARGET_KEYS if edge.get(k)), None)
    rel = next((str(edge[k]) for k in _REL_KEYS if edge.get(k)), "")
    return target, rel


def _node_id(data: Dict[str, Any], fallback: str) -> str:
    for key in ("id", "node_id"):
        val = data.get(key)
        if isinstance(val, str) and val:
            return val
    return fallback


def _collect_edges(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Gather edges from every container this repo uses, de-duplicated."""
    raw: List[Any] = []
    for key in ("edges", "links"):
        val = data.get(key)
        if isinstance(val, list):
            raw.extend(val)
    gen = data.get("generated")
    if isinstance(gen, dict) and isinstance(gen.get("links"), list):
        raw.extend(gen["links"])
    # `generated` as a bare string carries no links -- this is what crashes upstream.

    out: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for e in raw:
        target, rel = _edge_to_pair(e)
        if not target:
            continue
        if (target, rel) in seen:
            continue
        seen.add((target, rel))
        out.append({"target": target, "rel": rel})
    return out


def _derive_kind(data: Dict[str, Any], degree: int, max_degree: int) -> str:
    """Assign a colour class. The renderer keys on `kind`; most nodes here lack one.

    Ordering matters: topology (hub) wins over content, because a highly-connected
    node's role in the graph is what the viewer needs to see first.
    """
    explicit = str(data.get("kind") or data.get("type") or "").lower()
    if explicit in {"hub", "root", "bridge", "synthesis", "hypothesis", "claim", "evidence"}:
        if degree >= max(4, 0.5 * max_degree):
            return "hub"
        return explicit

    if degree >= max(4, 0.5 * max_degree):
        return "hub"

    claims = data.get("claims")
    if isinstance(claims, list) and len(claims) >= 4:
        return "synthesis"

    statuses = set()
    if isinstance(claims, list):
        statuses = {str(c.get("status", "")).lower() for c in claims if isinstance(c, dict)}
    node_status = str(data.get("status", "")).lower()
    if node_status:
        statuses.add(node_status)

    if statuses and statuses <= {"confirmed"}:
        return "evidence"
    if "unconfirmed" in statuses or "hypothesis" in statuses:
        return "hypothesis"
    return "evidence" if "confirmed" in statuses else "claim"


def load_normalized_nodes(
    lab_dir: pathlib.Path = LAB_DIR, promote_claims: bool = True
) -> Dict[str, Dict[str, Any]]:
    """Load this repo's .lab and reshape it into what the papers renderer expects.

    Args:
        promote_claims: lift each entry of a node's ``claims[]`` array into its own
            graph node, linked to its parent. This .lab is inconsistent about claim
            granularity -- some claims are their own files (``claim-canonical-
            microcircuit-05`` has degree 37), while 118 others are nested inside 27
            parent nodes. Edges written between nested claims therefore look dangling
            when only files are treated as nodes. Promoting them resolves 13 of the 20
            dangling targets and matches the Obsidian atomic-note model.
    """
    raw: Dict[str, Dict[str, Any]] = {}
    unparseable: List[str] = []

    for fpath in sorted(lab_dir.glob("*.json")):
        if fpath.name.endswith(SKIP_SUFFIXES):
            continue
        try:
            data = json.load(open(fpath, encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - report, don't abort the whole render
            unparseable.append(f"{fpath.name}: {exc}")
            continue
        if not isinstance(data, dict):
            unparseable.append(f"{fpath.name}: top level is {type(data).__name__}, not an object")
            continue
        nid = _node_id(data, fpath.stem)
        raw[nid] = data

    if promote_claims:
        for parent_id in list(raw):
            claims = raw[parent_id].get("claims")
            if not isinstance(claims, list):
                continue
            for c in claims:
                if not isinstance(c, dict):
                    continue
                cid = c.get("id")
                if not isinstance(cid, str) or not cid or cid in raw:
                    continue
                child = dict(c)
                child["id"] = cid
                child["_parent"] = parent_id
                child["title"] = c.get("statement") or c.get("text") or cid
                # child -> parent, so a promoted claim never floats free
                child["edges"] = list(c.get("edges") or []) + [
                    {"to": parent_id, "type": "claim_of"}
                ]
                raw[cid] = child

    # Edges are resolved only against ids that exist -- a dangling target is a real
    # finding (Disconnection), not something to silently invent a node for.
    edges_by_node = {nid: _collect_edges(d) for nid, d in raw.items()}
    known = set(raw)
    dangling: List[str] = []
    degrees = {nid: 0 for nid in raw}
    for nid, edges in edges_by_node.items():
        for e in edges:
            if e["target"] in known:
                degrees[nid] += 1
                degrees[e["target"]] += 1
            else:
                dangling.append(f"{nid} -> {e['target']}")

    max_degree = max(degrees.values()) if degrees else 0

    nodes: Dict[str, Dict[str, Any]] = {}
    for nid, data in raw.items():
        kept = [e for e in edges_by_node[nid] if e["target"] in known]
        out = dict(data)
        out["id"] = nid
        out["generated"] = {"links": kept}
        out["kind"] = _derive_kind(data, degrees[nid], max_degree)
        out.setdefault("title", data.get("title") or data.get("summary") or nid)
        nodes[nid] = out

    load_normalized_nodes.report = {  # type: ignore[attr-defined]
        "files": len(list(lab_dir.glob("*.json"))),
        "nodes": len(nodes),
        "edges": sum(len(n["generated"]["links"]) for n in nodes.values()),
        "dangling": dangling,
        "unparseable": unparseable,
        "isolated": [nid for nid, d in degrees.items() if d == 0],
        "max_degree": max_degree,
        "degrees": degrees,
    }
    return nodes


def _mermaid_id(nid: str) -> str:
    """Mermaid node ids can't contain '-' or start with a digit."""
    safe = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in nid)
    return "n_" + safe


def export_markdown(
    nodes: Dict[str, Dict[str, Any]], report: Dict[str, Any], output_path: pathlib.Path,
    mermaid_top: int = 40,
) -> None:
    """Write an Obsidian-ingestible Markdown view of the graph.

    Two representations, because they answer different questions and neither alone works:

    * A **mermaid diagram** of the top-``mermaid_top`` nodes by degree. Mermaid cannot
      draw the full graph -- 489 nodes / 1190 edges renders as an unreadable hairball
      and is slow to lay out -- so this is deliberately the hub subgraph, and says so
      in the caption rather than pretending to be complete.
    * A **complete node index using ``[[wikilinks]]``**, which is the part Obsidian
      actually reads. Drop this file in a vault and Obsidian's own graph view resolves
      every link, giving the full graph interactively without any renderer.
    """
    deg = report["degrees"]
    order = sorted(nodes, key=lambda n: (-deg.get(n, 0), n))
    top = order[:mermaid_top]
    top_set = set(top)

    kinds = collections.Counter(n.get("kind", "?") for n in nodes.values())
    rels = collections.Counter(
        e["rel"] or "(untyped)" for n in nodes.values() for e in n["generated"]["links"]
    )

    L: List[str] = []
    L.append("# Labyrinth graph — `artifacts/.lab`\n")
    L.append(f"> Generated by `scripts/build_lab_obsidian_graph.py`. "
             f"**{report['nodes']} nodes · {report['edges']} edges · max degree {report['max_degree']}**\n")

    L.append("\n## Health\n")
    L.append("| Metric | Value | Meaning |")
    L.append("|---|---:|---|")
    L.append(f"| Nodes | {report['nodes']} | from {report['files']} JSON files + promoted claims |")
    L.append(f"| Edges | {report['edges']} | resolved against existing ids only |")
    L.append(f"| Isolated (degree 0) | {len(report['isolated'])} | Disconnection — connected to nothing |")
    L.append(f"| Dangling targets | {len(report['dangling'])} | edges pointing at absent nodes |")
    L.append(f"| Unparseable files | {len(report['unparseable'])} | invalid JSON, excluded |")

    if report["dangling"]:
        L.append("\n### Dangling edges\n")
        L.append("Edges whose target does not exist. Each is a real Disconnection finding.\n")
        for d in sorted(set(report["dangling"])):
            src, _, tgt = d.partition(" -> ")
            L.append(f"- `{tgt}` — referenced by [[{src}]]")

    L.append("\n## Composition\n")
    L.append("| Kind | Count |")
    L.append("|---|---:|")
    for k, v in kinds.most_common():
        L.append(f"| {k} | {v} |")

    L.append("\n| Relation | Count |")
    L.append("|---|---:|")
    for k, v in rels.most_common(20):
        L.append(f"| `{k}` | {v} |")

    L.append(f"\n## Hub subgraph — top {len(top)} nodes by degree\n")
    L.append(f"Not the whole graph. The full {report['nodes']}-node graph does not render "
             "legibly as a static diagram; use the node index below in Obsidian, or the "
             "HTML export, for the complete picture.\n")
    L.append("```mermaid")
    L.append("graph LR")
    for nid in top:
        label = str(nodes[nid].get("title") or nid)[:60].replace('"', "'")
        L.append(f'  {_mermaid_id(nid)}["{label}"]')
    seen: set[tuple[str, str]] = set()
    for nid in top:
        for e in nodes[nid]["generated"]["links"]:
            t = e["target"]
            if t not in top_set or (nid, t) in seen:
                continue
            seen.add((nid, t))
            rel = e["rel"]
            arrow = f"-->|{rel}|" if rel else "-->"
            L.append(f"  {_mermaid_id(nid)} {arrow} {_mermaid_id(t)}")
    L.append("```")

    L.append("\n## Node index\n")
    L.append("Every node, by descending degree. The `[[wikilinks]]` are what Obsidian's "
             "graph view resolves — this section IS the graph as far as a vault is concerned.\n")
    for nid in order:
        n = nodes[nid]
        d = deg.get(nid, 0)
        title = str(n.get("title") or nid).replace("\n", " ").strip()
        if len(title) > 140:
            title = title[:137] + "..."
        L.append(f"\n### [[{nid}]]\n")
        L.append(f"*{n.get('kind','?')} · degree {d}*\n")
        if title and title != nid:
            L.append(f"{title}\n")
        links = n["generated"]["links"]
        if links:
            grouped: Dict[str, List[str]] = collections.defaultdict(list)
            for e in links:
                grouped[e["rel"] or "links to"].append(e["target"])
            for rel, tgts in sorted(grouped.items()):
                L.append(f"- **{rel}** → " + ", ".join(f"[[{t}]]" for t in sorted(set(tgts))))
        else:
            L.append("- *(no outgoing links)*")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lab-dir", default=str(LAB_DIR))
    ap.add_argument("--output", default=None,
                    help="output path; defaults to the format's standard location")
    ap.add_argument("--format", choices=("html", "md", "both"), default="both")
    ap.add_argument("--no-claims", action="store_true",
                    help="treat only .json files as nodes; do not promote nested claims[]")
    ap.add_argument("--mermaid-top", type=int, default=40,
                    help="how many top-degree nodes to include in the mermaid diagram")
    args = ap.parse_args()

    nodes = load_normalized_nodes(pathlib.Path(args.lab_dir), promote_claims=not args.no_claims)
    rep = load_normalized_nodes.report  # type: ignore[attr-defined]

    wrote: List[str] = []

    if args.format in ("html", "both"):
        if not PAPERS_CLIENTS.exists():
            print(f"ERROR: HTML renderer not found at {PAPERS_CLIENTS}", file=sys.stderr)
            if args.format == "html":
                return 2
        else:
            sys.path.insert(0, str(PAPERS_CLIENTS))
            import generate_obsidian_graph_html as gen  # noqa: E402

            out = pathlib.Path(args.output) if (args.output and args.format == "html") else OUT_HTML
            out.parent.mkdir(parents=True, exist_ok=True)
            # Redirect the renderer's module-level constants, then let it draw.
            gen.LAB_DIR = pathlib.Path(args.lab_dir)
            gen.OUT_HTML = out
            gen.load_lab_nodes = lambda: nodes
            gen.generate_obsidian_html()
            wrote.append(str(out))

    if args.format in ("md", "both"):
        out_md = pathlib.Path(args.output) if (args.output and args.format == "md") else OUT_MD
        export_markdown(nodes, rep, out_md, mermaid_top=args.mermaid_top)
        wrote.append(str(out_md))

    print(f"\nnodes {rep['nodes']}  edges {rep['edges']}  max degree {rep['max_degree']}")
    print(f"isolated (degree 0): {len(rep['isolated'])}")
    if rep["dangling"]:
        print(f"dangling edge targets: {len(set(rep['dangling']))}")
        for d in sorted(set(rep["dangling"]))[:10]:
            print(f"   {d}")
    if rep["unparseable"]:
        print(f"unparseable: {len(rep['unparseable'])}")
        for u in rep["unparseable"]:
            print(f"   {u}")
    for w in wrote:
        print(f"wrote {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
