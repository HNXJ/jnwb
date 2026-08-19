---
name: lab-graph-export
description: |
  Render a Labyrinth `.lab/` knowledge-graph directory as an interactive
  Obsidian-style HTML graph and/or an Obsidian-ingestible Markdown graph
  (mermaid hub diagram + full [[wikilink]] node index). Also reports graph
  health: dangling edges, isolated nodes, unparseable files, relation mix.
  Use whenever asked to visualize, render, draw, or export the knowledge graph,
  the .lab directory, or "the obsidian graph" — or to audit graph health.
---

# Exporting `.lab/` to an Obsidian graph

One command, both formats:

```bash
python scripts/build_lab_obsidian_graph.py
```

Writes `artifacts/developer/labyrinth/obsidian_graph.html` and `.md`.

| Flag | Effect |
|---|---|
| `--format html \| md \| both` | default `both` |
| `--lab-dir <path>` | point at another repo's `.lab` |
| `--output <path>` | override destination (single-format runs only) |
| `--no-claims` | treat only `.json` files as nodes (see *Claim promotion*) |
| `--mermaid-top N` | nodes in the mermaid diagram, default 40 |

## The two outputs answer different questions

**HTML** — interactive force-directed graph, upstream Tokyo Night theme, click a node
for its claims and receipts. Delivered via `SendUserFile` with `display: "render"`.
It pulls `vis-network` and Google Fonts from CDNs, so it **needs a network connection**
and cannot be published as an Artifact (strict CSP blocks external hosts).

**Markdown** — two representations in one file, because neither alone works:
- a **mermaid diagram of the top-N nodes by degree**. Mermaid cannot draw the full
  graph — 489 nodes / 1,190 edges is an illegible hairball — so this is deliberately
  the hub subgraph and the caption says so rather than implying completeness;
- a **complete node index using `[[wikilinks]]`**, which is the part Obsidian reads.
  Drop the file in a vault and Obsidian's own graph view resolves every link, giving
  the full interactive graph with no renderer at all.

## Why an adapter exists instead of calling the upstream script

The renderer lives in the papers repo (`C:/workspace/papers/clients/`), per the handout
at `~/.gemini/antigravity/brain/.../obsidian_graph_handout.md`. **Pointed at this repo's
`.lab` it crashes** — `AttributeError`, not a degraded graph. Measured over 374 files:

| Upstream assumes | This repo |
|---|---|
| `LAB_DIR`/`OUT_HTML` are constants at `C:/workspace/papers` | not parameters |
| edges at `generated.links` | 266 yes; 37 top-level `edges`; 37 top-level `links` |
| one edge key convention | **five**: `from/to/type`, `rel/target`, `target/type`, `from/relation/to`, `reasoning/rel/target` |
| `generated` is a dict | **64 nodes have it as a string** → `"str".get()` raises |
| id at `id` | 365 yes, 3 `node_id`, 6 neither (falls back to filename stem) |

Past the crash it would emit **zero edges** — a plausible-looking graph of disconnected
dots. `scripts/build_lab_obsidian_graph.py` normalizes all of it, then hands the
normalized nodes to the upstream renderer, so the visuals stay upstream and only the
parsing is repo-specific.

**If you point this at a new `.lab`, re-run the shape census first.** These counts are
this repo's, measured on one date; another graph will differ.

## Claim promotion (on by default)

This `.lab` is inconsistent about whether a claim is a node. Some are their own files
(`claim-canonical-microcircuit-05`, degree 37); 118 more are nested inside 27 parents'
`claims[]` arrays. Edges written *between nested claims* therefore look dangling when
only files count as nodes.

Promoting nested claims to nodes (each linked `claim_of` → parent) took the graph
371 → 489 nodes and dangling targets 25 → 9. It also matches Obsidian's atomic-note
model. `--no-claims` disables it if you want a file-level view.

## Read the health report, don't just look at the picture

Every run prints, and the Markdown embeds, the numbers that matter more than the layout:

- **Dangling targets** — edges pointing at absent nodes. Disconnection. Each one is a
  real finding; a missing root can strand a whole subgraph.
- **Isolated nodes (degree 0)** — connected to nothing. On this graph that was 50 of
  489, about a tenth.
- **Unparseable files** — reported and excluded, never silently skipped.
- **Relation mix** — a graph that is 90% one untyped relation is not a graph.

Dangling edges also surface cross-repo leakage: two of this repo's pointed at
`papers-protocol`, a node belonging to a different project's `.lab`.

## Verify the render, don't assume it

Exporting without looking is not verification (project doctrine, and it applies to
graphs). After generating:

```python
# via the browser tools, on the file:// URL
{visLoaded: typeof vis !== 'undefined',
 canvases: document.querySelectorAll('canvas').length,
 drawnNodes: nodesDataSet.length, drawnEdges: edgesDataSet.length}
```

Confirm `drawnNodes`/`drawnEdges` match the script's reported counts. A CDN failure
yields a blank page with no console error, which looks identical to an empty graph.

For the Markdown, check link integrity — **strip fenced blocks and inline code first**,
since Obsidian does not resolve wikilinks inside code spans and a naive regex will
report false positives:

```python
stripped = re.sub(r'```.*?```', '', md, flags=re.S)
stripped = re.sub(r'`[^`\n]*`', '', stripped)
links = set(re.findall(r'\[\[([^\]]+)\]\]', stripped))
headers = set(re.findall(r'^### \[\[([^\]]+)\]\]', md, re.M))
assert not (links - headers)
```
