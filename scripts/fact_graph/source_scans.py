"""Source and prose scans: RNG seeding, dB averages, immunity vocabulary, skill contracts and silent handlers."""

from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from scripts.gates.boundary import git

# ------------------------------------------------------------------------ source scans

#: The global random state's seed, under the dotted names NumPy and the standard library export.
GLOBAL_SEEDS = ("numpy.random.seed", "random.seed")
#: Calls into the random modules that draw nothing and create no stream.
RNG_BOOKKEEPING = ("numpy.random.SeedSequence", "numpy.random.Generator",
                   "numpy.random.BitGenerator")
RNG_PARAMETER = "rng"
#: The keyword of an rng-like seed (scikit-learn's spelling). A draw seeded by it, or by a
#: parameter annotated ``SeedSequence`` (a worker's child of the caller's rng), needs no ``rng``.
RNG_LIKE_PARAMETER = "random_state"
SEED_SEQUENCE_ANNOTATION = "SeedSequence"
#: The trees whose functions take an ``rng`` parameter when they draw from a random module.
#: ``scripts/`` is outside the rule.
SCANNED_FOR_RNG = ("jnwb/",)
#: The package whose averages of dB values the dB rule reads.
DB_PACKAGE = "jnwb/"
#: The context that makes a vocabulary word a claim about volume conduction or reference.
IMMUNITY_CONTEXT = (r"volume[- ]conduction", r"reference", r"zero-lag", r"zero-phase",
                    r"field spread", r"common[- ]average",
                    r"reference[- ](?:contamination|induced|electrode)", r"re-?referenc\w*",
                    r"shared[- ]reference", r"zero[- ]lag (?:leakage|mixing)")
#: The immunity vocabulary beyond the fact stack's ``immunity vocabulary`` constant.
IMMUNITY_PATTERNS = (r"\bimmun(?:e|ity)\b", r"\binsensitive to\b", r"\brobust to\b",
                     r"\bunaffected by\b", r"\beliminat(?:e|es|ed|ing)\b",
                     r"\bcomplete(?:ly)? suppress(?:es|ed|ion)?\b", r"\bfree (?:of|from)\b")
#: The words that negate a vocabulary word when they precede it in the same clause.
NEGATIONS = ("not", "no", "never", "nor", "without")
#: Clause breaks: a colon, parenthesis, comma, semicolon or spaced dash.
CLAUSE_BREAKS = r"[,;:()]|\s[—-]\s"
#: "not only", "not just" and "not merely" are no negation.
NOT_MERELY = r"\bnot (?:only|just|merely)\b"
#: The text the immunity rule reads: every tracked file with one of these suffixes, and every
#: file under the ``PROSE_ANY`` trees, outside the ``PROSE_EXEMPT`` trees and files.
PROSE_SUFFIXES = (".md", ".py", ".ipynb", ".txt", ".yml", ".yaml")
PROSE_ANY = ("skills/", ".github/")
#: The trees (ending in ``/``) and files the immunity rule does not read. The rule files and the builder's modules are
#: exempt because their docstrings define the vocabulary and the context.
PROSE_EXEMPT = ("tests/", "artifacts/", "scripts/build_fact_graph.py",
                 "scripts/fact_gate.py", "scripts/fact_graph/")
#: A list item (a bullet or a number) begins a sentence of its own.
LIST_ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s")
#: The package whose comments, docstrings and except handlers the text rules read.
JNWB_PACKAGE = "jnwb/"
#: The skill-contract rule's terms. A sentence naming a carrier and saying the contract is
#: carried by or extends it is exempt.
MANIFEST_TERMS = ("manifest", "receipt")
CONTRACT_TERMS = (r"contract", r"schema", r"must write", r"must produce", r"required[- ]fields",
                  r"must (?:contain|include|list|record)\b.*\bfields")
CONTRACT_CARRIERS = ("inspect", "Result", "Provenance", "Lineage")
CARRY_WORDS = r"\b(?:extends?|extended|carried by|carries|via)\b"
#: The exceptions an optional dependency's absence raises; a handler for them alone is a fallback.
OPTIONAL_IMPORT_ERRORS = ("ImportError", "ModuleNotFoundError")
#: The logger methods that report a problem.
LOGGER_WARNINGS = ("warning", "error", "exception")
#: The except handlers the silent_handlers scan skips, by (module path, qualified function): the
#: probes and controls whose silence is the answer, each read by hand against its handler (fact S9).
#: Non-finite inputs need no handler: every public numeric function refuses them by name, as
#: tests/test_nonfinite_inputs.py checks, or documents their propagation or missingness.
#: A key that matches no flagged handler is reported as stale.
S9_EXCUSED: Dict[Tuple[str, str], str] = {
    ("jnwb/_backend.py", "_probe"): "backend probe: False when the backend will not load",
    ("jnwb/_backend.py", "jax_metal_available"): "backend probe: False when no Metal device",
    ("jnwb/_dictlike.py", "DictAccessMixin.get"): "dict.get contract: the caller's default",
    ("jnwb/addressing.py", "enrich_units_dataframe._enrich"): "cache miss, computed next",
    ("jnwb/compression.py", "_repaired_reference"): "warns at the next line",
    ("jnwb/connectivity/_granger.py", "_adf_pvalue"): "reported as 'stationarity_not_tested'",
    ("jnwb/io.py", "_stored_seek_is_reliable"): "seek probe, same values either way",
    ("jnwb/jrsa/_backends.py", "_ensure_np"): "retry: np.asarray converts or raises",
    ("jnwb/jrsa/_result.py", "JRSAResult.__repr__"): "repr only",
    ("jnwb/jrsa/_stages.py", "_reduce_one"): "same number by percentile 50",
    ("jnwb/laminar/_xflip.py", "_window_rows"): "raise on the next line",
    ("jnwb/laminar/_xflip.py", "_homogeneous_factor"): "raise after the jitter loop",
    ("jnwb/laminar/_zflip.py", "_window_rows"): "raise on the next line",
    ("jnwb/mcp_server/nwb_tools.py", "_resolves"): "probe: no reader to name",
    ("jnwb/metadata.py", "_session_id_from_path"): "documented fallback to (raw, raw)",
    ("jnwb/nwb_validate.py", "_version"): "not installed",
    ("jnwb/nwb_write.py", "_spec_chain"): "a namespace without the type is the next namespace's turn",
    ("jnwb/nwb_write.py", "_declared_scalar"): "an undeclared attribute is not scalar; the repair refuses",
    ("jnwb/nwb_write.py", "_plan_vector_index_types.visit"): "an unreadable target is a dangling one, repointed",
    ("jnwb/vis/canvas.py", "_is_written"): "caller raises",
}


def _dotted(node: ast.AST) -> str:
    """The dotted spelling of a name or attribute chain, or ``""`` for any other expression."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    parts.append(node.id)
    return ".".join(reversed(parts))


def _final(node: ast.AST) -> str:
    """The last name of a spelling: ``mean`` for ``np.mean``."""
    return _dotted(node).rpartition(".")[2]


def _bindings(tree: ast.AST) -> Dict[str, str]:
    """Each name an import binds, mapped to the dotted path it stands for."""
    bound: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bound[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    bound[top] = top
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                bound[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return bound


def _target(node: ast.AST, bound: Dict[str, str]) -> str:
    """The dotted path a callee stands for, read through the module's own imports."""
    head, dot, rest = _dotted(node).partition(".")
    return bound.get(head, head) + dot + rest


def global_seed_calls(source: str) -> List[str]:
    """Each call that seeds the global random state, read through the module's own imports:
    ``np.random.seed``, ``random.seed``, and the same seed reached by an alias or a ``from``
    import. A seeded instance (``random.Random(0).seed``) is not the global state."""
    tree = ast.parse(source)
    bound = _bindings(tree)
    hits = sorted((node.lineno, _dotted(node.func)) for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and _target(node.func, bound) in GLOBAL_SEEDS)
    return [f"line {line}: {spelled}" for line, spelled in hits]


def _own_calls(fn: ast.AST):
    """The calls in a function's own statements, not in the functions and lambdas it defines."""
    pending = list(fn.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(node, ast.Call):
            yield node
        pending.extend(ast.iter_child_nodes(node))


def _parameters(fn: ast.AST) -> set:
    args = fn.args
    named = args.posonlyargs + args.args + args.kwonlyargs + [args.vararg, args.kwarg]
    return {arg.arg for arg in named if arg is not None}


def _draws(target: str) -> bool:
    """Whether a callee draws from, or constructs, a stream of NumPy's or the standard library's
    random module; bookkeeping such as ``SeedSequence`` does not."""
    return target.startswith(("numpy.random.", "random.")) and target not in RNG_BOOKKEEPING


def _seed_children(fn: ast.AST) -> set:
    """The parameters annotated ``SeedSequence``: a worker's seed, a child of the caller's rng."""
    args = fn.args
    named = args.posonlyargs + args.args + args.kwonlyargs
    return {arg.arg for arg in named
            if arg.annotation is not None and _final(arg.annotation) == SEED_SEQUENCE_ANNOTATION}


def _traces_to_caller(call: ast.Call, children: set) -> bool:
    """Whether a draw is seeded by a ``random_state`` or by a SeedSequence child of the caller."""
    seed = call.args[0] if call.args else next(
        (k.value for k in call.keywords if k.arg == "seed"), None)
    if isinstance(seed, ast.Attribute):
        return seed.attr == RNG_LIKE_PARAMETER
    return isinstance(seed, ast.Name) and (seed.id == RNG_LIKE_PARAMETER or seed.id in children)


def _workers_of_an_rng(tree: ast.AST) -> set:
    """The ids of the functions defined inside a function that takes ``rng``: workers whose own
    parameters carry seeds drawn from the caller's rng."""
    found = set()
    for outer in ast.walk(tree):
        if (isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef))
                and RNG_PARAMETER in _parameters(outer)):
            found.update(id(node) for node in ast.walk(outer) if node is not outer
                         and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    return found


def rng_violations(source: str) -> List[str]:
    """Each function that draws from a random module and takes no parameter named ``rng``, unless
    every draw in it is seeded by a ``random_state``, by a SeedSequence child, or, in a worker
    defined inside a function that takes ``rng``, by one of the worker's own parameters. Code
    outside any function, such as a script's self-test, is not a function and is not read."""
    tree = ast.parse(source)
    bound = _bindings(tree)
    workers = _workers_of_an_rng(tree)
    found = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        draws = [call for call in _own_calls(fn) if _draws(_target(call.func, bound))]
        children = _seed_children(fn)
        if id(fn) in workers:
            children |= _parameters(fn)
        traced = all(_traces_to_caller(call, children) for call in draws)
        if draws and RNG_PARAMETER not in _parameters(fn) and not traced:
            found.append((fn.lineno, fn.name))
    return [f"line {line}: {name} draws without an rng parameter" for line, name in sorted(found)]


def _lexicon(forms: Sequence[str]) -> Tuple[set, set, set]:
    """The call names, the name suffixes and the sum numerators that a lexicon's forms name:
    ``10*log10`` names ``log10``, ``*_db`` names any name ending in ``_db``, ``sum / count``
    names the numerator ``sum``."""
    names, suffixes, numerators = set(), set(), set()
    for form in forms:
        if " / " in form:
            numerators.add(form.split(" / ")[0].strip())
        elif form.startswith("*"):
            suffixes.add(form[1:])
        else:
            names.add(form.split("*")[-1])
    return names, suffixes, numerators


def db_average_violations(source: str, constants: Dict[str, List[str]]) -> List[str]:
    """Each average in one module of a dB value: an averaging call, or a sum divided by a count,
    whose input is a dB conversion or holds a name assigned from one in the same function. A
    median of dB values is not an average, and an average taken before the log is not read here.
    The centre of a squared deviation, ``(x - mean(x)) ** 2``, is a log-space fit statistic and is
    not read either.
    """
    for key in ("dB log forms", "dB averaging forms"):
        if key not in constants:
            raise ValueError(f"the constants name no {key}")
    log_names, log_suffixes, _ = _lexicon(constants["dB log forms"])
    avg_names, _, numerators = _lexicon(constants["dB averaging forms"])
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def is_log(call: ast.Call) -> bool:
        name = _final(call.func)
        return name in log_names or any(name.endswith(suffix) for suffix in log_suffixes)

    def dB_valued(expr: ast.AST, tainted: set) -> bool:
        return any((isinstance(n, ast.Call) and is_log(n))
                   or (isinstance(n, ast.Name) and n.id in tainted) for n in ast.walk(expr))

    def averaged(node: ast.AST):
        """The inputs of an averaging node and its wording, or None."""
        if isinstance(node, ast.Call) and _final(node.func) in avg_names:
            inputs = list(node.args)
            if isinstance(node.func, ast.Attribute):
                inputs.append(node.func.value)  # the method form: ``x.mean()``
            return inputs, f"{_dotted(node.func)} over a dB value"
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                and isinstance(node.left, ast.Call) and _final(node.left.func) in numerators):
            return [node.left], f"{_dotted(node.left.func)} over a dB value divided by a count"
        return None

    def centres_a_squared_deviation(node: ast.AST) -> bool:
        """Whether an average is the centre of a squared deviation, ``(x - mean(x)) ** 2``: the
        total sum of squares of a fit statistic computed in log space, which the rule exempts."""
        sub = parents.get(node)
        power = parents.get(sub)
        return (isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Sub)
                and isinstance(power, ast.BinOp) and isinstance(power.op, ast.Pow)
                and isinstance(power.right, ast.Constant) and power.right.value == 2)

    def named_dB(fn: ast.AST) -> set:
        """The names a function assigns a dB value, to a fixpoint through other such names."""
        tainted: set = set()
        assigns = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)]
        grew = True
        while grew:
            grew = False
            for assign in assigns:
                if not dB_valued(assign.value, tainted):
                    continue
                for target in assign.targets:
                    for name in ast.walk(target):
                        if isinstance(name, ast.Name) and name.id not in tainted:
                            tainted.add(name.id)
                            grew = True
        return tainted

    scopes = [(tree, set())] + [(fn, named_dB(fn)) for fn in ast.walk(tree)
                                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))]
    found = set()
    for scope, tainted in scopes:
        for node in ast.walk(scope):
            hit = averaged(node)
            if not hit or centres_a_squared_deviation(node):
                continue
            if any(dB_valued(expr, tainted) for expr in hit[0]):
                found.add((node.lineno, hit[1]))
    return [f"line {line}: {wording}" for line, wording in sorted(found)]


def _negated(before: str) -> bool:
    """Whether a negation word occurs in the clause that ends at a vocabulary word: the text
    after the last clause break before it, with ``not only``, ``not just`` and ``not merely``
    taken out."""
    clause = re.sub(NOT_MERELY, "", re.split(CLAUSE_BREAKS, before)[-1])
    return any(re.search(rf"\b{word}\b", clause) for word in NEGATIONS)


def _paragraphs(text: str) -> List[List[Tuple[int, str]]]:
    """Each run of consecutive non-blank lines of ``text``, as (line number, stripped line). A
    list item begins a run of its own."""
    paragraphs: List[List[Tuple[int, str]]] = []
    current: List[Tuple[int, str]] = []
    for number, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(current)
                current = []
            continue
        if LIST_ITEM.match(stripped) and current:
            paragraphs.append(current)
            current = []
        current.append((number, stripped))
    if current:
        paragraphs.append(current)
    return paragraphs


def _joined(paragraph: List[Tuple[int, str]]) -> Tuple[str, List[Tuple[int, int]]]:
    """A paragraph's lines joined by spaces, and the (offset, line number) at which each line
    begins in the join."""
    joined = " ".join(line for _, line in paragraph)
    begins, position = [], 0
    for number, line in paragraph:
        begins.append((position, number))
        position += len(line) + 1
    return joined, begins


def _line_of(begins: List[Tuple[int, int]], offset: int) -> int:
    """The line number that holds an offset of a joined paragraph."""
    return max(number for begin, number in begins if begin <= offset)


def _sentence_spans(joined: str) -> List[Tuple[int, int]]:
    """The (start, end) offsets of each sentence of a paragraph. A sentence ends at ``. ``,
    ``? ``, ``! `` or ``;``; the mark is not part of it."""
    spans, start = [], 0
    for mark in re.finditer(r"\. |\? |! |;", joined):
        spans.append((start, mark.start()))
        start = mark.end()
    spans.append((start, len(joined)))
    return spans


def immunity_violations(text: str, vocabulary: Sequence[str]) -> List[str]:
    """Each sentence of ``text`` that holds a value of the immunity vocabulary beside a term of
    ``IMMUNITY_CONTEXT``, case-insensitively, where the value
    is not negated in its clause. A sentence is read across the lines of its paragraph, so a
    negation can end one line and the value start the next. ``text`` is markdown, or the
    ``python_prose`` of a module; the line reported is the line of the value."""
    if not vocabulary:
        raise ValueError("the constants name no immunity vocabulary")
    words = re.compile("|".join([re.escape(word.lower()) for word in vocabulary]
                                + list(IMMUNITY_PATTERNS)))
    found = []
    for paragraph in _paragraphs(text):
        joined, begins = _joined(paragraph)
        for start, end in _sentence_spans(joined):
            lowered = joined[start:end].lower()
            if not any(re.search(term, lowered) for term in IMMUNITY_CONTEXT):
                continue
            hits = sorted((start + hit.start(), hit.group(0)) for hit in words.finditer(lowered)
                          if not _negated(lowered[:hit.start()]))
            if hits:
                line_of_value = _line_of(begins, hits[0][0])
                found.append(f"line {line_of_value}: {', '.join(dict.fromkeys(w for _, w in hits))}")
    return found


def _code_prose(source: str) -> str:
    """A notebook code cell's comments and docstrings. A cell that does not parse, such as one
    with a magic, keeps only its whole-line comments."""
    try:
        return python_prose(source)
    except (SyntaxError, tokenize.TokenError):
        return "\n".join(line.strip().lstrip("#").strip() if line.strip().startswith("#") else ""
                         for line in source.split("\n"))


def immunity_scan(rel: str, text: str, vocabulary: Sequence[str]) -> List[str]:
    """The immunity violations of one tracked text file: a Python file's comments and docstrings,
    a notebook's markdown cells and code-cell comments (each reason names its cell), or the whole
    of any other file."""
    if rel.endswith(".ipynb"):
        found = []
        for index, cell in enumerate(json.loads(text)["cells"]):
            source = cell.get("source", "")
            source = "".join(source) if isinstance(source, list) else source
            if cell.get("cell_type") == "markdown":
                prose = source
            elif cell.get("cell_type") == "code":
                prose = _code_prose(source)
            else:
                continue
            found += [f"cell {index} {reason}" for reason in immunity_violations(prose, vocabulary)]
        return found
    if rel.endswith(".py"):
        return immunity_violations(python_prose(text), vocabulary)
    return immunity_violations(text, vocabulary)


def python_prose(source: str) -> str:
    """The source with only its comments and docstrings kept, one line for each source line, so
    a line number in the result is the source's own."""
    lines = [""] * (source.count("\n") + 1)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            lines[token.start[0] - 1] = token.string.lstrip("#").strip()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        first = node.body[0] if node.body else None
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            for offset, line in enumerate(first.value.value.split("\n")):
                index = first.lineno - 1 + offset
                lines[index] = f"{lines[index]} {line}".strip()
    return "\n".join(lines)


def skill_contract_violations(text: str) -> List[str]:
    """Each sentence of ``text``, read across the lines of its paragraph, that names a manifest or
    receipt, or a plural of one, beside a ``CONTRACT_TERMS`` pattern. A sentence that names a
    ``CONTRACT_CARRIERS`` word as a whole word and says the contract is carried by or extends it
    is exempt. The terms match case-insensitively; the carriers match as written."""
    found = []
    for paragraph in _paragraphs(text):
        joined, begins = _joined(paragraph)
        for start, end in _sentence_spans(joined):
            sentence = joined[start:end]
            lowered = sentence.lower()
            hits = sorted((start + hit.start(), term) for term in MANIFEST_TERMS
                          for hit in re.finditer(rf"\b{term}s?\b", lowered))
            if not hits:
                continue
            carried = (any(re.search(rf"\b{carrier}\b", sentence) for carrier in CONTRACT_CARRIERS)
                       and bool(re.search(CARRY_WORDS, lowered)))
            if any(re.search(pattern, lowered) for pattern in CONTRACT_TERMS) and not carried:
                terms = dict.fromkeys(term for _, term in hits)
                found.append(f"line {_line_of(begins, hits[0][0])}: {', '.join(terms)}")
    return found


def _is_logger_report(call: ast.Call) -> bool:
    """Whether a call is a logger's warning, error or exception: its receiver is named for a
    logger (``logger``, ``log``, ``logging``) or is a ``getLogger(...)`` call."""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in LOGGER_WARNINGS:
        return False
    receiver = func.value.func if isinstance(func.value, ast.Call) else func.value
    return "log" in _final(receiver).lower()


def _own_nodes(fn: ast.AST):
    """The nodes of a function's own statements; the functions, lambdas and classes it defines
    are skipped."""
    pending = list(fn.body)
    while pending:
        node = pending.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        pending.extend(ast.iter_child_nodes(node))


def _body_reports(fn: ast.AST, bound: Dict[str, str]) -> bool:
    """Whether a function's own body raises, calls ``warnings.warn``, or calls a logger's warning,
    error or exception."""
    return any(isinstance(node, ast.Raise)
               or (isinstance(node, ast.Call) and (_target(node.func, bound) == "warnings.warn"
                                                   or _is_logger_report(node)))
               for node in _own_nodes(fn))


def _top_defs(tree: ast.AST) -> Dict[str, ast.AST]:
    """The functions a module defines at its top level, by name."""
    return {node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _relative_imports(tree: ast.AST, path: str) -> Dict[str, Tuple[str, str]]:
    """Each name bound by ``from .module import name`` or ``from ..module import name``, at any
    level, as alias -> (the module's path without its suffix, name), resolved from ``path``."""
    bound: Dict[str, Tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level >= 1 and node.module:
            package = PurePosixPath(path).parent
            for _ in range(node.level - 1):
                package = package.parent
            base = (package / node.module.replace(".", "/")).as_posix()
            for alias in node.names:
                bound[alias.asname or alias.name] = (base, alias.name)
    return bound


def _callee_reports(name: str, defs: Dict[str, ast.AST], bound: Dict[str, str],
                    imports: Dict[str, Tuple[str, str]],
                    read: Callable[[str], Optional[str]]) -> bool:
    """Whether the function ``name`` resolves to reports in its own body: a function of this
    module, or the function a relative import names, read through ``read`` from the tracked
    file. One level only: the functions that function calls are not followed."""
    if name in defs:
        return _body_reports(defs[name], bound)
    if name not in imports:
        return False
    base, original = imports[name]
    for candidate in (f"{base}.py", f"{base}/__init__.py"):
        text = read(candidate)
        if text is not None:
            tree = ast.parse(text)
            defs_of = _top_defs(tree)
            return original in defs_of and _body_reports(defs_of[original], _bindings(tree))
    return False


def _handler_loud(handler: ast.ExceptHandler, bound: Dict[str, str],
                  callee_reports: Callable[[str], bool]) -> bool:
    """Whether a handler's body reports or uses its exception: it raises, calls ``warnings.warn``
    or a logger's warning, error or exception, calls a function that reports (``callee_reports``),
    or reads the bound exception name anywhere in its body, returned values included."""
    body = [node for stmt in handler.body for node in ast.walk(stmt)]
    if any(isinstance(node, ast.Raise) for node in body):
        return True
    if any(isinstance(node, ast.Call) and (_target(node.func, bound) == "warnings.warn"
                                           or _is_logger_report(node)) for node in body):
        return True
    if handler.name and any(isinstance(node, ast.Name) and node.id == handler.name
                            and isinstance(node.ctx, ast.Load) for node in body):
        return True
    return any(callee_reports(node.func.id) for node in body
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Name))


def _handler_owners(tree: ast.AST) -> Dict[int, str]:
    """The qualified name of the function each except handler sits in (``Class.method``,
    ``outer.inner``), by ``id`` of the handler; ``<module>`` outside any function."""
    owners: Dict[int, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = prefix
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}.{child.name}" if prefix else child.name
            if isinstance(child, ast.ExceptHandler):
                owners[id(child)] = prefix or "<module>"
            visit(child, name)

    visit(tree, "")
    return owners


def silent_handler_sites(source: str, path: str,
                         read: Callable[[str], Optional[str]]) -> List[Tuple[str, str]]:
    """Each except handler of one module that swallows its exception (``_handler_loud``), unless
    it catches only ``OPTIONAL_IMPORT_ERRORS``: an absent optional dependency is a documented
    fallback. A bare handler catches everything and is spelled ``(bare)``. Each violation is
    spelled by the line of its handler's first body statement, with that line's text, and paired
    with the qualified name of the function it sits in (``_handler_owners``)."""
    lines = source.split("\n")
    tree = ast.parse(source)
    bound = _bindings(tree)
    defs = _top_defs(tree)
    imports = _relative_imports(tree, path)
    owners = _handler_owners(tree)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            spelled, caught = "(bare)", set()
        else:
            spelled = ast.unparse(node.type)
            names = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
            caught = {_final(name) for name in names}
        if caught and caught <= set(OPTIONAL_IMPORT_ERRORS):
            continue
        if _handler_loud(node, bound, lambda name: _callee_reports(
                name, defs, bound, imports, read)):
            continue
        first = node.body[0].lineno
        found.append((first, spelled, lines[first - 1].strip(), owners[id(node)]))
    return [(function, f"line {first}: except {spelled}: {text}")
            for first, spelled, text, function in sorted(found)]


def silent_handler_violations(source: str, path: str,
                              read: Callable[[str], Optional[str]]) -> List[str]:
    """The violations ``silent_handler_sites`` reports, spelled without their function."""
    return [text for _, text in silent_handler_sites(source, path, read)]


def _tracked_files(root: Path) -> List[str]:
    """Every tracked file of the repository, as sorted posix paths."""
    listed = git("-C", str(root), "ls-files", encoding="utf-8")
    listed.check_returncode()
    return sorted(line for line in listed.stdout.splitlines() if line)


def _exempt(path: str) -> bool:
    """Whether a path is a ``PROSE_EXEMPT`` file, or lies under a ``PROSE_EXEMPT`` tree. A file
    name matches only itself, so a sibling such as ``scripts/fact_gate_rules.py`` is read."""
    return any(path == entry or (entry.endswith("/") and path.startswith(entry))
               for entry in PROSE_EXEMPT)


def _prose_files(tracked: Sequence[str]) -> List[str]:
    """The text files the immunity rule reads: every tracked file with a ``PROSE_SUFFIXES``
    suffix and every file under a ``PROSE_ANY`` tree, unless ``_exempt``."""
    return [path for path in tracked
            if not _exempt(path)
            and (path.endswith(PROSE_SUFFIXES) or path.startswith(PROSE_ANY))]


def _skill_files(tracked: Sequence[str]) -> List[str]:
    """Every tracked ``SKILL.md`` under ``skills/``."""
    return [path for path in tracked
            if path.startswith("skills/") and path.rsplit("/", 1)[-1] == "SKILL.md"]


def _text_scans(root: Path, prose: Sequence[str], skill_files: Sequence[str],
                python: Sequence[str], constants: Dict[str, List[str]]):
    """Each text rule's violations as sorted [file, reason] pairs."""
    if "immunity vocabulary" not in constants:
        raise ValueError("the constants name no immunity vocabulary")
    scans: Dict[str, List[List[str]]] = {"immunity_vocabulary": [], "skill_contracts": [],
                                         "silent_handlers": []}
    for rel in prose:
        text = (root / rel).read_text(encoding="utf-8")
        scans["immunity_vocabulary"].extend(
            [rel, reason] for reason in immunity_scan(rel, text, constants["immunity vocabulary"]))
    for rel in skill_files:
        text = (root / rel).read_text(encoding="utf-8")
        scans["skill_contracts"].extend([rel, reason] for reason in skill_contract_violations(text))
    package = {rel: (root / rel).read_text(encoding="utf-8")
               for rel in python if rel.startswith(JNWB_PACKAGE)}
    flagged = set()
    for rel, text in package.items():
        for function, reason in silent_handler_sites(text, rel, package.get):
            flagged.add((rel, function))
            if (rel, function) not in S9_EXCUSED:
                scans["silent_handlers"].append([rel, reason])
    for rel, function in sorted(S9_EXCUSED):
        if (rel, function) not in flagged:
            scans["silent_handlers"].append(
                [rel, f"S9_EXCUSED lists {function}, which no flagged handler matches: stale"])
    return {name: sorted(pairs) for name, pairs in scans.items()}


def _tracked_python(root: Path) -> List[str]:
    """Every tracked Python file of the repository, as sorted posix paths."""
    listed = git("-C", str(root), "ls-files", "--", "*.py", encoding="utf-8")
    listed.check_returncode()
    return sorted(line for line in listed.stdout.splitlines() if line)


def _source_scans(root: Path, python: Sequence[str], constants: Dict[str, List[str]]):
    """Each scan's violations as sorted [file, reason] pairs."""
    scans: Dict[str, List[List[str]]] = {"global_seeds": [], "rng_parameters": [],
                                         "db_averages": []}
    for rel in python:
        text = (root / rel).read_text(encoding="utf-8")
        if rel.startswith(JNWB_PACKAGE):  # S5 reads the package; tests/ is outside it
            scans["global_seeds"].extend([rel, reason] for reason in global_seed_calls(text))
        if rel.startswith(SCANNED_FOR_RNG):
            scans["rng_parameters"].extend([rel, reason] for reason in rng_violations(text))
        if rel.startswith(DB_PACKAGE):
            scans["db_averages"].extend(
                [rel, reason] for reason in db_average_violations(text, constants))
    return {name: sorted(pairs) for name, pairs in scans.items()}
