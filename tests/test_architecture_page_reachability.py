"""The architecture page is reachable, and no maintained page contradicts what it draws.

The page states two parallel entry paths: a researcher calls the operations directly, and an
agent reaches the same operations through skills. The package is complete without the agent
layer, and skills route to operations that the documentation defines. These tests read the
structure a reader meets -- the navigation, the links, the edges of every Mermaid diagram,
and sentences whose subject is a skill -- rather than comparing prose to a stored copy.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
# `append`, never `insert`: the nav reader is shared from the checkout's tests, but the package
# under test must stay whichever copy is installed first on the path.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from tests.test_docs_user_navigation import nav_targets  # noqa: E402

DOCS = REPO_ROOT / "docs"
MKDOCS = REPO_ROOT / "mkdocs.yml"
PAGE = "architecture.md"

RESEARCHER = re.compile(r"\bresearcher", re.I)
AGENT = re.compile(r"\bagents?\b|\bAI\b|\bskills?\b|\bassistants?\b|\bLLMs?\b", re.I)
OPERATIONS = re.compile(r"\boperations?\b", re.I)

NODE = re.compile(r"([A-Za-z_][\w]*)\s*(?:\[([^\]]*)\]|\(([^)]*)\)|\{([^}]*)\})?")
EDGE = re.compile(r"(-{2,}>|-\.+->|={2,}>)\s*(?:\|([^|]*)\|)?")
#: Mermaid lines that group or orient nodes and draw no edge.
LAYOUT = re.compile(r"^(?:subgraph\b.*|end|direction\s+\w+)$")

#: Phrases that make an agent a precondition of using jnwb.
AGENT_REQUIRED = re.compile(
    r"(?:requires?|needs?|depends? on) an? (?:AI |LLM )?agent|agent[- ](?:first|only)"
    r"|only (?:through|via|with) an? (?:AI|agent)"
    r"|must (?:use|go through|be driven by) an? (?:AI )?agent",
    re.I,
)

#: A skill as the subject of a sentence that makes it the authority over an operation.
SKILL_AUTHORITY = re.compile(
    r"\bskills?\s+(?:is|are|acts? as|serves? as)\s+(?:the\s+)?(?:\w+\s+)?"
    r"(?:authority|authoritative|source of truth|canonical)"
    r"|\bskills?\s+(?:define|defines|implement|implements|specify|specifies|decides? what)\b",
    re.I,
)


def _maintained_pages():
    pages = sorted(DOCS.rglob("*.md")) + [REPO_ROOT / "README.md"]
    return [p for p in pages if p.is_file()]


def _nav_targets():
    return nav_targets(MKDOCS)


def _mermaid_blocks(text):
    return re.findall(r"```mermaid\n(.*?)```", text, re.S)


def _graph(block):
    """Labels by node id and edges as (source, target) ids, from `graph` lines of a block.

    An edge whose label names an agent becomes a node of its own between its ends, so a path
    along that edge passes through an agent as it would through an agent node.
    """
    labels, edges = {}, []
    for line in block.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("%%") or LAYOUT.match(line):
            continue
        parts = EDGE.split(line)
        edge_labels = parts[2::3]
        ids = []
        for chunk in parts[::3]:
            m = NODE.fullmatch(chunk.strip())
            # Fail closed: a line the reader cannot parse would otherwise drop its edges, and a
            # dropped researcher-to-agent edge reads exactly like an absent one.
            assert m, f"diagram line the reader cannot parse: {line!r}"
            node_id = m.group(1)
            label = next((g for g in m.groups()[1:] if g), None)
            if label is not None or node_id not in labels:
                labels[node_id] = label if label is not None else node_id
            ids.append(node_id)
        for (a, b), label in zip(zip(ids, ids[1:]), edge_labels):
            if label and AGENT.search(label):
                via = f"{a}->{b}"
                labels[via] = label
                edges.extend([(a, via), (via, b)])
            else:
                edges.append((a, b))
    return labels, edges


def _paths(labels, edges, start, goal, avoid):
    """Whether some path from `start` reaches a node matching `goal` without entering `avoid`."""
    succ = {}
    for a, b in edges:
        succ.setdefault(a, []).append(b)
    seen, stack = {start}, [start]
    while stack:
        node = stack.pop()
        for nxt in succ.get(node, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            if goal.search(labels[nxt]):
                return True
            if avoid is not None and avoid.search(labels[nxt]):
                continue
            stack.append(nxt)
    return False


def test_the_page_is_a_navigation_target():
    assert PAGE in _nav_targets(), f"mkdocs.yml has no nav entry for docs/{PAGE}"


def test_the_agent_page_links_it():
    text = (DOCS / "agents.md").read_text(encoding="utf-8")
    assert re.search(r"\]\(\s*architecture\.md(?:#[^)]*)?\s*\)", text), (
        "docs/agents.md does not link the architecture page"
    )


def test_the_page_draws_a_researcher_reaching_the_operations_without_an_agent():
    """The positive half: without it, the negative test below could pass on a parse that
    finds no researcher at all."""
    blocks = _mermaid_blocks((DOCS / PAGE).read_text(encoding="utf-8"))
    assert blocks, f"docs/{PAGE} has no Mermaid diagram"
    found = False
    for block in blocks:
        labels, edges = _graph(block)
        for node, label in labels.items():
            if RESEARCHER.search(label):
                found = True
                assert _paths(labels, edges, node, OPERATIONS, avoid=AGENT), (
                    f"docs/{PAGE}: the researcher node {label!r} reaches no operation "
                    f"except through an agent or skill node"
                )
    assert found, f"docs/{PAGE}: no diagram node names a researcher"


def test_no_diagram_routes_a_researcher_through_an_agent():
    offenders = []
    for page in _maintained_pages():
        for block in _mermaid_blocks(page.read_text(encoding="utf-8")):
            labels, edges = _graph(block)
            for node, label in labels.items():
                if RESEARCHER.search(label) and _paths(labels, edges, node, AGENT, avoid=None):
                    offenders.append(f"{page.relative_to(REPO_ROOT).as_posix()}: {label!r}")
    assert not offenders, f"a researcher reaches an agent or skill node: {offenders}"


def test_no_page_makes_an_agent_a_precondition():
    offenders = []
    sources = _maintained_pages() + [REPO_ROOT / "pyproject.toml"]
    for page in sources:
        for m in AGENT_REQUIRED.finditer(page.read_text(encoding="utf-8")):
            offenders.append(f"{page.relative_to(REPO_ROOT).as_posix()}: {m.group(0)!r}")
    assert not offenders, offenders


def test_no_page_or_skill_makes_a_skill_the_authority_over_an_operation():
    offenders = []
    sources = _maintained_pages() + sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
    for page in sources:
        text = re.sub(r"\s+", " ", page.read_text(encoding="utf-8"))
        for m in SKILL_AUTHORITY.finditer(text):
            offenders.append(f"{page.relative_to(REPO_ROOT).as_posix()}: {m.group(0)!r}")
    assert not offenders, offenders


def test_the_diagram_reader_sees_edges_and_labels():
    """The graph reader is the instrument the two diagram tests stand on."""
    labels, edges = _graph(
        "graph LR\n    A[Researcher] --> O[jnwb operations]\n"
        "    B[AI agent: skills] -.->|routes| O\n    O --> V[Verification]\n"
    )
    assert labels == {"A": "Researcher", "O": "jnwb operations", "B": "AI agent: skills",
                      "V": "Verification"}
    assert edges == [("A", "O"), ("B", "O"), ("O", "V")]
    chained, chain_edges = _graph("graph LR\n    R[Researcher] --> A[AI agent] --> O[operations]\n")
    assert _paths(chained, chain_edges, "R", AGENT, avoid=None)
    assert not _paths(chained, chain_edges, "R", OPERATIONS, avoid=AGENT)
    spaced, spaced_edges = _graph("graph LR\n    R[Researcher] --> |asks| A[AI agent]\n")
    assert spaced_edges == [("R", "A")]
    with pytest.raises(AssertionError, match="cannot parse"):
        _graph("graph LR\n    R[Researcher] --> A[agent] & B[skills]\n")
    assert AGENT_REQUIRED.search("Using jnwb needs an AI agent.")
    assert AGENT_REQUIRED.search("Using jnwb requires an LLM agent.")
    assert SKILL_AUTHORITY.search("The skill is authoritative over the estimator.")


@pytest.mark.parametrize("block", [
    "graph LR\n    R[Researcher] -->|asks an AI agent| O[jnwb operations]\n",
    "graph LR\n    R[Researcher] --> A[Assistant] --> O[jnwb operations]\n",
    "graph LR\n    R[Researcher] --> L[LLM] --> O[jnwb operations]\n",
], ids=["agent in an edge label", "Assistant", "LLM"])
def test_the_reader_sees_an_agent_however_it_is_named(block):
    labels, edges = _graph(block)
    assert _paths(labels, edges, "R", AGENT, avoid=None)
    assert not _paths(labels, edges, "R", OPERATIONS, avoid=AGENT)


def test_the_reader_accepts_a_subgraph():
    labels, edges = _graph(
        "graph LR\n    subgraph core [jnwb core]\n    direction TB\n"
        "    O[jnwb operations]\n    end\n    R[Researcher] --> O\n"
    )
    assert edges == [("R", "O")] and labels["O"] == "jnwb operations"


def test_the_dependency_diagram_names_every_runtime_dependency():
    """P-278: the diagram omitted six of the ten libraries jnwb imports at install."""
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {re.split(r"[<>=!~\[; ]", dep, maxsplit=1)[0].lower()
                for dep in project["project"]["dependencies"]}
    assert {"numpy", "pynwb", "joblib"} <= declared, declared
    drawn = [label for block in _mermaid_blocks((DOCS / PAGE).read_text(encoding="utf-8"))
             for label in _graph(block)[0].values() if label and "NumPy" in label]
    assert len(drawn) == 1, drawn
    assert {name.strip().lower() for name in drawn[0].split(",")} == declared
