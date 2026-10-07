"""Words that state a causal or delay claim appear on the public surfaces only in listed uses.

"causes", "time delay", "propagation delay" and "latency" each have a legitimate use here -- a
unit's onset latency, the delay a filter imposes, a caveat that forbids the claim -- and a use
that asserts what the directed measures cannot establish: that one site causes another, or that
a phase relation is a physical delay (`docs/08` and the connectivity skill state the conditions).
A word list cannot tell the two apart, so every use is listed below with the reason it is the
legitimate kind. A new use fails until someone reads it and lists it, and a listed use that no
longer occurs fails too, so the list cannot keep excusing a sentence that was rewritten.

The surfaces are every page under `docs/` and `skills/`, `README.md`, and the docstrings of
public modules, classes and functions in `jnwb/` -- what a caller reads through `help()`.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Appended, not prepended: an installed copy must not be shadowed by the source tree.
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts.mutation_harness import source_path  # noqa: E402
from tests._sources import read_sources, unread_by  # noqa: E402

TERMS = re.compile(
    r"\b(causes?|caused|causing|time[\s-]+delays?|propagation[\s-]+delays?|latenc(?:y|ies))\b",
    re.IGNORECASE,
)

# Why a listed use is legitimate. Each use below names one.
ONSET = "a unit's response onset time on its own trace; no claim about travel between sites"
FILTER = "the delay a filter imposes on its own output, a property of the filter"
CAVEAT = "forbids the claim, or states the condition under which it may be made"
METHOD = "what an input or an analysis choice does to a result; no claim about neural causes"
SYNTHETIC = "a parameter of a synthetic signal, true by construction"

#: (path, fragment containing the term, reason). The fragment must enclose the matched word.
ALLOWED: tuple[tuple[str, str, str], ...] = (
    ("docs/architecture.md", "onset latency modeling", ONSET),
    ("docs/architecture.md", "bounded onset latency fitting", ONSET),
    ("docs/architecture.md", "a physical cause, or an effect", CAVEAT),
    ("docs/architecture.md", "none for a cause, which takes a perturbation", CAVEAT),
    ("docs/architecture.md", "a cause from any row above", CAVEAT),
    ("docs/06_spikes_psth_and_onset_dynamics.md", "response_zscore, latency", ONSET),
    ("docs/06_spikes_psth_and_onset_dynamics.md", "response onset latency accurately", ONSET),
    ("docs/06_spikes_psth_and_onset_dynamics.md", "deterministic time delay", FILTER),
    ("docs/06_spikes_psth_and_onset_dynamics.md", "Mathematical Latency Properties", ONSET),
    ("docs/06_spikes_psth_and_onset_dynamics.md", "belong to a latency read", ONSET),
    ("docs/06_spikes_psth_and_onset_dynamics.md", "only such a latency is corrected", ONSET),
    ("docs/06_spikes_psth_and_onset_dynamics.md", "Onset Latency Fit]", ONSET),
    ("docs/07_statistical_inference_and_nulls.md", "false discoveries caused by", METHOD),
    ("docs/09_decoding_and_visual_qc.md", "in only one group always causes", METHOD),
    ("docs/agents.md", "asymmetry a cause", CAVEAT),
    ("docs/agents.md", "PSTH, onset latency, response", ONSET),
    ("docs/common_mistakes.md", "distorting latency estimates", ONSET),
    ("docs/common_mistakes.md", "a time delay $\\Delta t$ and a constant phase offset", CAVEAT),
    ("docs/common_mistakes.md", "Group Delay in Onset Latency", ONSET),
    ("docs/common_mistakes.md", "Comparing onset latencies across", CAVEAT),
    ("docs/common_mistakes.md", "biological latency is erroneous", CAVEAT),
    ("docs/quickstart.md", "Spiking & latencies", ONSET),
    ("docs/quickstart.md", "parametric latency model", ONSET),
    ("docs/tutorials/03_spiking.md", "fit onset latencies", ONSET),
    ("docs/tutorials/09_open_data.md", "excludes any LFP latency", CAVEAT),
    ("skills/jnwb/SKILL.md", "PSTH, onset latency, response", ONSET),
    ("skills/jnwb-connectivity/SKILL.md", "Latency delay ($d\\phi/df", CAVEAT),
    ("skills/jnwb-population/SKILL.md", "in only one group always causes", METHOD),
    ("skills/jnwb-spiking/SKILL.md", "physiological latency estimation", ONSET),
    ("skills/jnwb-spiking/SKILL.md", "PSTH & Latency Estimation", ONSET),
    ("skills/jnwb-spiking/SKILL.md", "onset latencies, or unit", ONSET),
    ("skills/jnwb-spiking/SKILL.md", "never measure an onset latency on a smoothed", CAVEAT),
    ("skills/jnwb-spiking/SKILL.md", "for onset latency $t_0$", ONSET),
    ("skills/jnwb-spiking/SKILL.md", "first-spike `latency` in seconds", ONSET),
    ("skills/jnwb-spiking/SKILL.md", "estimating response latency", ONSET),
    ("skills/jnwb-spiking/SKILL.md", "only from a latency read as a threshold", ONSET),
    ("skills/jnwb-spiking/SKILL.md", "a latency difference between two traces", CAVEAT),
    ("skills/jnwb-spiking/agents/openai.yaml", "physiological latency estimation", ONSET),
    ("jnwb/onset_fitting.py", "onset-latency fit", ONSET),
    ("jnwb/onset_fitting.py", "ESTIMATOR LATENCY PROPERTIES", ONSET),
    ("jnwb/onset_fitting.py", "For a latency read as a threshold crossing", ONSET),
    ("jnwb/onset_fitting.py", "onset latency differences as biological", CAVEAT),
    ("jnwb/onset_fitting.py", "a latency difference between two traces", CAVEAT),
    (source_path("relative_power", "contains zeros causing"), "contains zeros causing", METHOD),
    ("jnwb/spiking.py", "firing rate/latency/z-score", ONSET),
    ("jnwb/spiking.py", "- latency: Time to first spike", ONSET),
    ("jnwb/testing/synth.py", "Latency increment per contact", SYNTHETIC),
    ("jnwb/testing/synth.py", "known PSTH latency", SYNTHETIC),
    ("jnwb/vis/hierarchy.py", "metric (latency, prevalence)", ONSET),
    ("jnwb/vis/hierarchy.py", "prevalence or onset latency", ONSET),
    ("jnwb/vis/hierarchy.py", '"Onset latency (ms)"', ONSET),
    ("jnwb/vis/spiking.py", "by latency or response category", ONSET),
)


def _public_docstrings(path: Path, text: str) -> list[tuple[int, str]]:
    """Docstrings `help()` shows: the module's, unless it is private, and each public def's; in a
    private submodule of a package, a def is public where the package's `__init__` re-exports it."""
    tree = ast.parse(text)
    out: list[tuple[int, str]] = []

    def visit(node: ast.AST, public: bool) -> None:
        doc = ast.get_docstring(node, clean=False)  # type: ignore[arg-type]
        if doc and public:
            out.append((node.body[0].lineno, doc))  # type: ignore[attr-defined]
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit(child, public and not child.name.startswith("_"))

    if not path.name.startswith("_") or path.name == "__init__.py":
        visit(tree, True)
        return out
    # A private submodule of a package: its defs are public where the package re-exports them.
    init = path.with_name("__init__.py")
    exported: set[str] = set()
    if init.is_file():
        for node in ast.walk(ast.parse(init.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module == path.stem:
                exported.update(alias.name for alias in node.names)
    for child in ast.iter_child_nodes(tree):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            visit(child, child.name in exported and not child.name.startswith("_"))
    return out


def _surface_lines() -> list[tuple[str, int, str]]:
    lines: list[tuple[str, int, str]] = []
    pages = sorted((ROOT / "docs").rglob("*.md")) + sorted((ROOT / "skills").rglob("*.md"))
    pages += sorted((ROOT / "skills").rglob("*.yaml")) + [ROOT / "README.md"]
    for page in pages:
        rel = page.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
            lines.append((rel, lineno, line))
    for source in read_sources("claim-wording"):
        rel = source.path.relative_to(ROOT).as_posix()
        for start, doc in _public_docstrings(source.path, source.text):
            for offset, line in enumerate(doc.splitlines()):
                lines.append((rel, start + offset, line))
    return lines


def _uses(lines: list[tuple[str, int, str]]) -> list[tuple[str, int, str, re.Match]]:
    return [(rel, n, line, m) for rel, n, line in lines for m in TERMS.finditer(line)]


def _covering(rel: str, line: str, match: re.Match) -> list[int]:
    """Indices of the listed uses whose fragment encloses this match on this line."""
    hits = []
    for i, (path, fragment, _) in enumerate(ALLOWED):
        if path != rel:
            continue
        for found in re.finditer(re.escape(fragment), line):
            if found.start() <= match.start() and match.end() <= found.end():
                hits.append(i)
    return hits


def _unlisted_and_unused(lines):
    unlisted, used = [], set()
    for rel, n, line, match in _uses(lines):
        covering = _covering(rel, line, match)
        used.update(covering)
        if not covering:
            unlisted.append(f"{rel}:{n}: {match.group(0)!r} in {line.strip()[:120]!r}")
    unused = [ALLOWED[i][:2] for i in range(len(ALLOWED)) if i not in used]
    return unlisted, unused


def test_every_use_on_the_public_surfaces_is_listed_and_every_listing_is_used() -> None:
    lines = _surface_lines()
    assert len({rel for rel, _, _ in lines if rel.startswith("jnwb/")}) >= 20, (
        "the docstring sweep found too few modules; it stopped reading the package"
    )
    assert len(_uses(lines)) >= len(ALLOWED), "the term sweep found fewer uses than it lists"
    unlisted, unused = _unlisted_and_unused(lines)
    assert not unlisted, (
        "a causal or delay word appears in an unlisted use. If it is one of the legitimate "
        "kinds named in this file, list it with its reason; otherwise reword it:\n  "
        + "\n  ".join(unlisted)
    )
    assert not unused, f"listed uses that no longer occur; remove them: {unused}"


def test_the_docstring_sweep_reads_every_file_that_defines_a_public_name() -> None:
    _surface_lines()
    assert unread_by("claim-wording") == []


@pytest.mark.parametrize("sentence", [
    "Granger shows that V1 causes V4.",
    "PSI estimates the time delay between the two sites.",
    "zFLIP returns the propagation delay across the laminae.",
    "The coherence phase gives the inter-areal latency.",
    "The phase slope gives the time-delay between contacts.",
])
def test_the_sweep_flags_the_claims_it_exists_to_stop(sentence: str) -> None:
    for path in ("docs/08_directed_connectivity_and_information.md", source_path("granger")):
        unlisted, _ = _unlisted_and_unused([(path, 1, sentence)])
        assert unlisted, f"{sentence!r} in {path} passed the sweep"


def test_a_listed_fragment_excuses_only_the_word_it_encloses() -> None:
    line = "response onset latency accurately, and the latency between areas"
    unlisted, _ = _unlisted_and_unused(
        [("docs/06_spikes_psth_and_onset_dynamics.md", 1, line)]
    )
    assert len(unlisted) == 1, unlisted
