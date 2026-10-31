"""Prose claim vocabulary (todo 17-07): each measure class uses its estimand's words.

Phase measures read as lead or lag; transfer entropy and Granger as predictive
information; correlation and coherence as co-variation or coupling. A sentence that
names an estimator and reaches for a higher claim class (a causal or drive word, or
the phrases "information flow", "flow of information", "synchrony",
"driver/receiver") is a hit. Each hit must carry a row in PROSE_EXCEPTIONS with a
reviewed reason; each row must still match a sentence, so a fixed sentence retires
its row instead of lingering.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

from scripts import build_fact_graph  # noqa: E402

#: Reviewed exceptions: (relative path, quoted substring of the hit sentence, reason).
#: Reason is one of: negation, cited claim, defined statistic, method name, caveat.
PROSE_EXCEPTIONS = [
    ("skills/jnwb-connectivity/SKILL.md",
     "it does not identify a driver",
     "negation"),
    ("skills/jnwb-connectivity/SKILL.md",
     "PSI is positive for the driver and negative for the receiver",
     "defined statistic"),
    ("skills/jnwb/SKILL.md",
     "not anatomical or physical causality",
     "negation"),
    ("docs/common_mistakes.md",
     "as perturbational causal mechanisms",
     "caveat"),
    ("docs/common_mistakes.md",
     "A common driver with asymmetric conduction delays",
     "caveat"),
    ("docs/common_mistakes.md",
     "An unrecorded source drives both signals and leaves a Granger",
     "caveat"),
    ("docs/architecture.md",
     "that one site drives another",
     "negation"),
    ("docs/architecture.md",
     "non-directional association",
     "negation"),
    ("docs/08_directed_connectivity_and_information.md",
     "Association} \\neq \\text{Directionality} \\neq \\text{Causality}",
     "negation"),
    ("docs/documentation_form.md",
     "the causal-step and narrowband-PSI figures",
     "method name"),
    ("docs/references.md",
     "rather than a causal effect",
     "cited claim"),
    ("docs/references.md",
     "The causal factor",
     "defined statistic"),
    ("jnwb/connectivity/_granger.py",
     "rather than a causal effect",
     "defined statistic"),
    ("jnwb/connectivity/_granger.py",
     "its causal part with the zero and Nyquist lags",
     "defined statistic"),
]

REASONS = ("negation", "cited claim", "defined statistic", "method name", "caveat")

#: Estimator names: LABEL_NAMES keys and values, matched as words with ``_`` read as
#: space, plus "correlation" and "mutual information", which the claim table's
#: Magnitude row (docs/architecture.md) estimates magnitude with and the 17-07 check
#: scopes under "correlation and coherence". Without "correlation" the
#: correlate_areas interpretation string is unreadable to the scan.
_ESTIMATOR_NAMES = sorted(
    set(build_fact_graph.LABEL_NAMES)
    | set(build_fact_graph.LABEL_NAMES.values())
    | {"correlation", "mutual information"}
)


def _patterns(names):
    return [build_fact_graph._phrase(name.replace("_", " ")) for name in names]


_ESTIMATOR_PATTERNS = _patterns(_ESTIMATOR_NAMES)
_INFERENCE_PATTERNS = _patterns(build_fact_graph.HIGHER_CLASS_TERMS["inference"]["words"])
_PHRASE_PATTERNS = _patterns(
    ("information flow", "flow of information", "synchrony", "driver/receiver")
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;:])\s+")
#: Blank lines divide blocks, and so does a table row: cells must not read across rows.
_BLOCK_SPLIT = re.compile(r"\n[ \t]*\n|\n(?=[ \t]*\|)")


def _sentences(text: str):
    """Block text split into sentences; single newlines join, blank lines divide."""
    out = []
    for block in _BLOCK_SPLIT.split(text):
        flat = re.sub(r"\s+", " ", block).strip()
        if flat:
            out.extend(piece.strip() for piece in _SENTENCE_SPLIT.split(flat) if piece.strip())
    return out


def _hit(sentence: str) -> bool:
    """A sentence naming an estimator that holds an inference word or a mechanism phrase."""
    if not any(pattern.search(sentence) for pattern in _ESTIMATOR_PATTERNS):
        return False
    cleaned = build_fact_graph._GRANGER_METHOD.sub(" ", sentence)
    if any(pattern.search(cleaned) for pattern in _INFERENCE_PATTERNS):
        return True
    return any(pattern.search(sentence) for pattern in _PHRASE_PATTERNS)


def _is_docstring_statement(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _strings_in(node: ast.AST):
    return [
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]


def _py_units(path: Path):
    """One unit per docstring and per code statement's string literals.

    Docstrings split into English sentences; a code statement's literals join into
    one unit, so a user-visible string reads with the statement that carries it
    (the correlate_areas interpretation string beside its ``'correlation'`` key).
    Comments are not AST strings and never enter.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    units = []
    for statement in tree.body:
        if _is_docstring_statement(statement):
            units.append(statement.value.value)
        else:
            texts = _strings_in(statement)
            if texts:
                units.append(" ".join(texts))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docstring = ast.get_docstring(node)
            if docstring:
                units.append(docstring)
            for statement in node.body:
                if _is_docstring_statement(statement):
                    continue
                texts = _strings_in(statement)
                if texts:
                    units.append(" ".join(texts))
    return units


def _scan():
    """Every examined (path, sentence) pair and the subset that is a hit."""
    examined: dict = {}
    hits: dict = {}
    for path in sorted((REPO_ROOT / "docs").rglob("*.md")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for sentence in _sentences(path.read_text(encoding="utf-8")):
            examined.setdefault((rel, sentence))
            if _hit(sentence):
                hits.setdefault((rel, sentence))
    for path in sorted((REPO_ROOT / "skills").rglob("SKILL.md")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for sentence in _sentences(path.read_text(encoding="utf-8")):
            examined.setdefault((rel, sentence))
            if _hit(sentence):
                hits.setdefault((rel, sentence))
    for path in sorted((REPO_ROOT / "jnwb").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for unit in _py_units(path):
            for sentence in _sentences(unit):
                examined.setdefault((rel, sentence))
                if _hit(sentence):
                    hits.setdefault((rel, sentence))
    return examined, hits


def _excepted(rel: str, sentence: str) -> bool:
    return any(row[0] == rel and row[1] in sentence for row in PROSE_EXCEPTIONS)


def _short(sentence: str, width: int = 240) -> str:
    return sentence if len(sentence) <= width else sentence[:width] + "..."


def test_no_unexcepted_claim_vocabulary_hit():
    examined, hits = _scan()
    assert len(examined) > 0, "the scan examined no sentences"
    bad = [row for row in PROSE_EXCEPTIONS if row[2] not in REASONS]
    assert not bad, f"exception rows with an unknown reason: {bad}"
    unexcepted = sorted((rel, sentence) for (rel, sentence) in hits if not _excepted(rel, sentence))
    assert not unexcepted, (
        "unexcepted claim-vocabulary hits:\n"
        + "\n".join(f"{rel}: {_short(sentence)}" for rel, sentence in unexcepted)
    )


def test_no_stale_claim_vocabulary_exception():
    examined, _ = _scan()
    by_path: dict = {}
    for rel, sentence in examined:
        by_path.setdefault(rel, []).append(sentence)
    stale = [
        row for row in PROSE_EXCEPTIONS
        if not any(row[1] in sentence for sentence in by_path.get(row[0], []))
    ]
    assert not stale, f"exception rows matching no sentence: {stale}"
