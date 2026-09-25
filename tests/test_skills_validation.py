"""
tests/test_skills_validation.py -- Deterministic verification of canonical repository skills.
"""
from pathlib import Path
from typing import List, Tuple
import ast
import dataclasses
import inspect
import re
try:
    import yaml
    def _yaml_load(s: str) -> dict:
        return yaml.safe_load(s)
except ImportError:
    try:
        import ruamel.yaml as ruamel_yaml
        _ryaml = ruamel_yaml.YAML(typ="safe")
        def _yaml_load(s: str) -> dict:
            return _ryaml.load(s)
    except ImportError:
        def _yaml_load(s: str) -> dict:
            res = {}
            for line in s.splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    res[k.strip()] = v.strip()
            return res

import numpy as np
import pytest
import pandas as pd
import jnwb

CANONICAL_SKILLS = {
    "jnwb",
    "jnwb-fact-action",
    "jnwb-nwb-data",
    "jnwb-spiking",
    "jnwb-lfp-spectral",
    "jnwb-statistics",
    "jnwb-population",
    "jnwb-connectivity",
    "jnwb-figures",
    "jnwb-landmark-viz",
}

ROOT_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT_DIR / "skills"
DOCS_DIR = ROOT_DIR / "docs"


def _executable_source(text: str) -> str:
    """`text` with comments and docstrings removed, so a probe reads code and not prose.

    A file-level co-occurrence probe over raw text cannot tell a write call from a sentence
    about one. `scripts/harness_gate.py` lists `fact_stack.md` as a gated vocabulary term and
    explains in a docstring that `Path.write_text` rewrites line endings on Windows; read as
    raw text those two facts make it a file that "could rewrite the fact stack", and it does
    not write anything at all.

    Narrowing a check is how a blind spot gets made, so the narrowing is stated precisely: a
    comment and a docstring cannot execute, therefore removing them cannot hide a real writer.
    Anything that runs survives. `ast.unparse` drops comments as a consequence of round-tripping
    the tree; the docstrings are removed explicitly. A file that does not parse is returned
    unchanged, so a syntax error makes the probe more conservative rather than blind.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)
            if not body:
                body.append(ast.Pass())
    return ast.unparse(ast.fix_missing_locations(tree))


def _scopes(text: str) -> List[Tuple[str, str]]:
    """`(name, source)` for each executable scope: every function, plus what is left of the
    module once the functions are lifted out of it.

    A co-occurrence probe over a whole file asks "does this file mention the fact stack
    anywhere, and call a write anywhere", which are two different places in a file of any
    size. `scripts/harness_gate.py` names `fact_stack.md` in its gated-vocabulary tuple and
    names `write_text` in a violation message four hundred lines away, telling an author which
    API caused a line-ending conversion. Neither is a write of the fact stack, and no amount of
    stripping prose changes that, because both are executable.

    Scoping the question to one function narrows it to something a writer cannot escape: code
    that writes a named file holds the name and the call in the same body. The residual module
    scope is kept for the same reason, since a module-level statement can write too.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [("<unparsed>", text)]

    functions: List[Tuple[str, str]] = []

    class _Lift(ast.NodeTransformer):
        def _take(self, node):
            functions.append((node.name, ast.unparse(ast.fix_missing_locations(node))))
            return ast.Pass()

        visit_FunctionDef = _take
        visit_AsyncFunctionDef = _take

    residual = _Lift().visit(ast.parse(text))
    return [("<module>", ast.unparse(ast.fix_missing_locations(residual)))] + functions


def _sentence_units(text: str) -> List[str]:
    """`text` split into sentences, for prose that may carry a bullet list.

    Two splits, and the second exists because the first is not enough on a docstring. A period
    followed by a capital or a backtick ends a sentence -- written that way so
    `jnwb.fit_exponential_onset` and `docs/common_mistakes.md` are not cut in half, and neither
    is a decimal such as `-0.118`. But `causal_exp_smooth`'s docstring opens with a heading and
    a bullet list whose lines end in colons and formulae, none of which is a period before a
    capital, so that rule alone glues the entire block into one span.

    That is not a pedantic distinction. A first draft of the 06-95 assertions used the period
    rule alone, and the sentence it reported as carrying the filter-delay instruction was the
    whole `ESTIMATOR LATENCY PROPERTIES & HAZARD` block -- which contains every word the
    assertions look for, somewhere. The check passed while pinning nothing, which is the exact
    shape those assertions exist to prevent. Structural breaks are therefore taken first: a
    blank line, a line-ending colon, and a line opening a bullet.
    """
    units = re.split(r"(?m):[ \t]*\n|\n[ \t]*\n|\n(?=[ \t]*[-*][ \t])", text)
    out: List[str] = []
    for unit in units:
        collapsed = " ".join(unit.split())
        if collapsed:
            out.extend(re.split(r"(?<=\.)\s+(?=[A-Z`])", collapsed))
    return out


def _delay_sentences(text: str) -> List[str]:
    """Sentences of `text` that instruct removing a filter or group delay from something.

    One definition serves the spiking skill's safeguards section and `causal_exp_smooth`'s
    docstring, so the two faces of the rule are held to one reading rather than to two copies
    of it that can drift.

    The delay is named four ways and the removal four, because the unscoped instruction this
    guard exists for read "Never compare onset latencies without accounting for estimator
    delay", which matched neither the old `(filter|group) delay` nor `subtract|remove|correct`.
    "Shift" is left out: the docstring uses it as a noun ("a group delay and time shift") in a
    sentence that instructs nothing.
    """
    return [
        s for s in _sentence_units(text)
        if re.search(r"(filter|group|estimator|smoothing)\s+(delay|lag)", s, re.I)
        and re.search(r"\b(subtract|remove|correct|account)", s, re.I)
    ]


_WRITE_CALL = re.compile(r"""write_text|write_bytes|open\([^)]*['"][wa]""")


def _fact_stack_writers(paths) -> List[str]:
    """The paths among `paths` holding a scope that names the fact stack and writes a file."""
    offenders = []
    for path in paths:
        source = _executable_source(Path(path).read_text(encoding="utf-8"))
        for _name, scope in _scopes(source):
            if "fact_stack" in scope and _WRITE_CALL.search(scope):
                offenders.append(str(path))
                break
    return offenders


def test_canonical_skills_directories_exist():
    """Verify exactly the intended canonical skill directories exist."""
    assert SKILLS_DIR.exists(), f"Skills directory missing: {SKILLS_DIR}"
    actual_skills = {d.name for d in SKILLS_DIR.iterdir() if d.is_dir()}
    assert actual_skills == CANONICAL_SKILLS, f"Skills mismatch: {actual_skills ^ CANONICAL_SKILLS}"


def test_skills_frontmatter_and_openai_yaml():
    """Verify each skill has valid YAML frontmatter in SKILL.md and agents/openai.yaml."""
    for skill_name in CANONICAL_SKILLS:
        skill_path = SKILLS_DIR / skill_name
        skill_md = skill_path / "SKILL.md"
        agent_yaml = skill_path / "agents" / "openai.yaml"

        assert skill_md.exists(), f"Missing SKILL.md for {skill_name}"
        assert agent_yaml.exists(), f"Missing agents/openai.yaml for {skill_name}"

        # Parse frontmatter from SKILL.md
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---"), f"{skill_name}/SKILL.md missing frontmatter start"
        parts = text.split("---", 2)
        assert len(parts) >= 3, f"{skill_name}/SKILL.md malformed frontmatter"
        frontmatter = _yaml_load(parts[1])
        assert isinstance(frontmatter, dict)
        assert frontmatter.get("name") == skill_name
        assert "description" in frontmatter and len(frontmatter["description"]) > 10

        # Parse agents/openai.yaml
        agent_data = _yaml_load(agent_yaml.read_text(encoding="utf-8"))
        assert isinstance(agent_data, dict)
        assert "interface" in agent_data
        assert agent_data["interface"].get("display_name") == skill_name
        assert "description" in agent_data["interface"]
        assert agent_data.get("policy", {}).get("allow_implicit_invocation") is True


#: Every inline ``jnwb.name(`` occurrence, counted by a pattern that does no parsing.
#: `_routing_calls` walks parentheses to extract arguments; this one only finds openings.
#: Two independent readings of the same corpus, which is the point -- see
#: `test_every_inline_routing_call_is_reached_by_the_parser`.
_CALL_OPENING = re.compile(r"`jnwb\.(?:\w+\.)*\w+\(")


def _routing_matrix_section(skill_text: str) -> str:
    """The text routing rows are read from: the whole file.

    This used to return only the ``## 2. Task-to-Primitive Routing Matrix`` window, so a
    default-bearing row written anywhere else was invisible. Widening it to the whole file
    changed the corpus from 116 rows to 116: **no row currently lives outside the window**,
    in any of the nine skills. The widening is therefore worth nothing today and is kept
    because it removes the class rather than the instance -- a row added to ``## 3.`` is now
    checked instead of silently skipped.

    Fenced code blocks stay out on their own: every pattern here requires a leading
    backtick, and a ``## 4. Minimal Workflow`` block is not inline code. That is why the two
    counts agree rather than the window having been doing useful work.
    """
    return skill_text


def _routing_calls(skill_text: str):
    r"""Every ``jnwb.name(...)`` in the routing matrix, with balanced parentheses.

    The previous pattern was ``\(([^)]*)\)``, which cannot span a nested parenthesis, so
    it silently skipped every row carrying a tuple default -- 7 of the 61 rows, including
    ``assign_outer_folds``, ``zflip``, ``wpli`` and ``save_figure_suite``. A row that is not
    matched is not checked, and nothing said so.
    """
    section = _routing_matrix_section(skill_text)
    # Dotted attributes too: `jnwb.StatisticalAnalysis.exploratory_compare(...)` did not match
    # `jnwb\.(\w+)\(` at all, so every StatisticalAnalysis row went unchecked -- which is how
    # a row stating n_bootstrap=10000 against a live default of 2000 passed this file.
    for match in re.finditer(r"`jnwb\.((?:\w+\.)*\w+)\(", section):
        depth, i = 1, match.end()
        while i < len(section) and depth:
            depth += {"(": 1, ")": -1}.get(section[i], 0)
            i += 1
        if depth == 0:
            yield match.group(1), section[match.end():i - 1]


def _mentioned_parameters(args_str: str):
    """(name, written_default_or_None, written_positionally) for each argument in a row.

    ``...`` as a value means the row is declining to state the default, which is allowed;
    it is returned as the string ``"..."`` and compared against nothing.
    """
    out, depth, token, keyword_only = [], 0, "", False
    for ch in args_str + ",":
        if ch == "," and depth == 0:
            token = token.strip()
            if token == "*":
                # Everything a row writes after a bare * is keyword-only, as in the signature.
                keyword_only = True
            elif token and token not in ("...", "/") and not token.startswith("**"):
                name, sep, default = token.partition("=")
                name = name.split(":")[0].strip()
                out.append((name, default.strip() if sep else None,
                            not sep and not keyword_only))
            token = ""
            continue
        depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(ch, 0)
        token += ch
    return out


def _is_enumeration(written: str) -> bool:
    """``scheme="within_group"|"global"`` states the admissible values, not a default.

    A row may say what a required argument accepts; that is routing information and the
    reason several rows use this notation. It is not a claim about a default, so the default
    checks do not apply to it -- but the parameter must still exist and still be in order.
    """
    return "|" in written


def _live_default_matches(live, written: str) -> bool:
    """Compare a stated default against the live one by value, then by text."""
    try:
        return ast.literal_eval(written) == live
    except (ValueError, SyntaxError):
        return str(live) == written


#: The corpus held 120 inline routing calls when this was set. A floor far below the count
#: only trips on mass deletion; this one fails once more than three rows disappear.
_ROUTING_ROWS_FLOOR = 117


def test_skill_routing_signatures_match_runtime():
    """Routing rows must be callable as written, not merely name real parameters.

    The previous test asserted ``pname in sig.parameters`` and nothing else. Every one of
    these passed it: ``paired_fire_prob_test(fires_null, fires_target, ...)`` with the first
    two arguments swapped, which negates ``risk_difference`` and raises nothing;
    ``epoch_continuous(data, onsets, win_s, fs)`` against a keyword-only signature;
    ``nested_cv_linear_svm(..., n_splits=5)`` where ``n_splits`` has no default;
    ``band_power(..., normalize=False)`` where the live default is ``True`` and raises
    without a baseline.
    """
    checked = 0
    for skill_name in CANONICAL_SKILLS:
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        for func_name, args_str in _routing_calls(content):
            target = jnwb
            for attr in func_name.split("."):
                assert hasattr(target, attr), (
                    f"{skill_name}: jnwb.{func_name} referenced in routing matrix is missing"
                )
                target = getattr(target, attr)
            checked += 1
            sig = inspect.signature(target)
            order = list(sig.parameters)
            written = _mentioned_parameters(args_str)
            where = f"{skill_name}: jnwb.{func_name}({args_str})"

            for name, default, positional in written:
                param = sig.parameters.get(name)
                assert param is not None, (
                    f"{where} has no parameter {name!r}; live: {order!r}"
                )
                if positional:
                    assert param.kind is not param.KEYWORD_ONLY, (
                        f"{where} passes {name!r} positionally, but it is keyword-only"
                    )
                # `rng=...` says "pass something here", not "the default is ...", so it
                # states nothing about a default and is checked for neither.
                if default is not None and default != "..." and not _is_enumeration(default):
                    assert param.default is not param.empty, (
                        f"{where} gives {name}={default}, but {name!r} has no default"
                    )
                    assert _live_default_matches(param.default, default), (
                        f"{where} gives {name}={default}; the live default is "
                        f"{param.default!r}"
                    )

            # Only positionally written arguments have an order to be wrong about: a row
            # that writes `groups=None, scheme=...` is calling by keyword, and keyword order
            # is free. A positional argument, though, binds by position, so the k-th one
            # written must be the k-th parameter -- which is what
            # `paired_fire_prob_test(fires_null, fires_target, ...)` was not.
            for k, name in enumerate(n for n, _, positional in written if positional):
                assert order.index(name) == k, (
                    f"{where} passes {name!r} as positional argument {k}, but it is "
                    f"parameter {order.index(name)} of {order!r}"
                )

            required = [
                n for n, p in sig.parameters.items()
                if p.default is p.empty
                and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
            ]
            named = {n for n, _, _ in written}
            missing = [n for n in required if n not in named]
            assert not missing, (
                f"{where} omits required parameter(s) {missing!r}; a reader copying this row "
                f"gets a TypeError, or supplies them in the wrong order"
            )

    assert checked >= _ROUTING_ROWS_FLOOR, (
        f"only {checked} routing rows were matched against a floor of {_ROUTING_ROWS_FLOOR}; "
        f"rows that are not matched are not checked, which is how 7 tuple-bearing rows and "
        f"4 StatisticalAnalysis rows went unread. Removing rows on purpose lowers the floor "
        f"in the same change"
    )


def test_every_inline_routing_call_is_reached_by_the_parser():
    """The parser must read every routing row that exists, not every row it can parse.

    `_routing_calls` decides its own corpus twice over: it picks a section, then walks
    parentheses, and a row lost at either step is a row nothing checks. That has happened --
    7 tuple-bearing rows and 4 dotted `StatisticalAnalysis` rows were each silently dropped,
    and the count assertion below them stayed green because it only ever saw the survivors.

    So the corpus here is counted by `_CALL_OPENING`, which finds call openings and parses
    nothing. A test whose case set comes from the machinery under test cannot reach the case
    that machinery loses; these two readings are independent, so a divergence is a dropped
    row and names the skill it was dropped from.
    """
    divergences = []
    total_found = 0
    for skill_name in sorted(CANONICAL_SKILLS):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        found = len(_CALL_OPENING.findall(content))
        parsed = len(list(_routing_calls(content)))
        total_found += found
        if found != parsed:
            divergences.append(
                f"{skill_name}: {found} inline `jnwb.<name>(` openings in the file, "
                f"{parsed} reached by _routing_calls"
            )
    assert divergences == [], (
        "routing rows exist that the parser never yields, so nothing checks them: "
        + "; ".join(divergences)
    )
    assert total_found >= _ROUTING_ROWS_FLOOR, (
        f"only {total_found} routing rows found in the whole skill corpus; agreement "
        f"between two readings of an empty corpus is not evidence of anything"
    )


#: `jnwb.<name>` references that are not public API and are not routing targets.
#: `__all__` and `__version__` are the package's own metadata, named when a skill talks
#: about the API rather than routing to a function.
_PACKAGE_METADATA = re.compile(r"^__\w+__$")

#: Known breaches of the publicity invariant. Asserted by **equality**: a new private route
#: fails, and repairing one of these without deleting its entry also fails, so the quarantine
#: cannot outlive the defect. Empty since `jnwb-nwb-data` stopped routing at
#: `jnwb.nwb_inspect.CONTINUOUS_KEYS` and wrote the keys out instead;
#: `test_the_continuous_keys_the_skill_lists_are_the_live_ones` holds that list to the code.
_NON_PUBLIC_ROUTES_PENDING_REPAIR: set = set()


def test_all_referenced_symbols_exist():
    """A routed symbol must be *public*, not merely reachable by attribute.

    This asserted `hasattr(jnwb, symbol)` and nothing else. Every submodule satisfies that,
    so the test green-lit `jnwb.nwb_inspect.CONTINUOUS_KEYS` -- a private constant behind a
    submodule that `__all__` does not export and `docs/` does not document. Reachability is
    the proxy; membership of `__all__` is the invariant, because `__all__` is the
    authoritative symbol list and what the API docs are
    generated from. An import that works today and is renamed tomorrow without a
    deprecation is exactly what routing an agent at a non-export buys.

    Both halves are asserted: a name in `__all__` that does not resolve is equally a broken
    route, and asserting only membership would trade one proxy for another.
    """
    pattern = re.compile(r"\bjnwb\.([a-zA-Z0-9_]+)")
    public = set(jnwb.__all__)

    checked = 0
    breaches = set()
    for skill_name in sorted(CANONICAL_SKILLS):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        for symbol in pattern.findall(content):
            if _PACKAGE_METADATA.match(symbol):
                continue
            checked += 1
            assert hasattr(jnwb, symbol), (
                f"jnwb.{symbol} referenced in {skill_name} does not resolve"
            )
            if symbol not in public:
                breaches.add((skill_name, symbol))

    assert checked >= 100, (
        f"only {checked} jnwb.<symbol> references were examined across the skill corpus; "
        f"a pattern that stops matching passes this test without checking anything"
    )
    assert breaches == _NON_PUBLIC_ROUTES_PENDING_REPAIR, (
        "skills route at symbols that jnwb.__all__ does not export.\n"
        f"  newly private: {sorted(breaches - _NON_PUBLIC_ROUTES_PENDING_REPAIR)}\n"
        f"  repaired, delete from the quarantine: "
        f"{sorted(_NON_PUBLIC_ROUTES_PENDING_REPAIR - breaches)}"
    )

    unresolved = [s for s in jnwb.__all__ if not hasattr(jnwb, s)]
    assert unresolved == [], f"jnwb.__all__ exports names that do not resolve: {unresolved}"


#: A row saying the return is of some named type, optionally naming fields on it.
_CLAIM_RETURN_TYPE = re.compile(
    r"[Rr]eturn(?:s|ing)\s+`([A-Z]\w*)`(?:\s+with\s+((?:`\w+`(?:,\s*)?(?:and\s+)?)+))?"
)
#: A row saying the return carries a record of something.
_CLAIM_CARRIES = re.compile(r"\b(?:named|recorded) in the result\b", re.I)
#: A row saying the return carries no record -- the negative of the above, and equally a
#: claim about contents. An agent acts on it by storing the choice itself.
_CLAIM_BARE_ARRAY = re.compile(r"\bbare array\b", re.I)
_CLAIM_RECORDS_NO = re.compile(r"\brecords no (\w+)\b", re.I)

#: `jnwb-nwb-data` states its returns as ``call` → `Type``, which none of the sentence
#: patterns above can match -- they all require the word "return". Every one of that file's
#: seven arrow rows was therefore invisible to this harness: `inspect` → `dict`, `events` →
#: `EventTable`, `event_onsets` → `numpy.ndarray` and two tuple returns were carried by the
#: skill and checked by nothing here. The arrow must follow the row's closing backtick, so
#: the `trials` → `sole table` resolution chain inside `resolve_interval_table`'s prose is
#: not read as a return type.
_CLAIM_ARROW_TYPE = re.compile(r"`\s*→\s*(?:structured\s+)?`([A-Za-z_][\w.]*)`")
#: The same form when the return is a tuple written out: ``→ `(data, rate_hz)``.
_CLAIM_ARROW_TUPLE = re.compile(r"`\s*→\s*`\(([^`)]*)\)`")
#: A routing row written as an arrow, counted independently of what the patterns above
#: extract from it, so a row that yields no claim is named rather than skipped.
_ARROW_ROW = re.compile(r"^- `jnwb\.((?:\w+\.)*\w+)\([^`]*\)`\s*(?:.*?)→")

#: Arrow rows whose text after the arrow is prose rather than a return type, so there is no
#: type claim to execute. Asserted by **equality**: a new prose arrow row fails here, and
#: rewriting one of these to name a type without deleting its entry also fails.
#:
#: `resolve_interval_table` writes a resolution *order* after its arrow ("table name using
#: `trials` → sole table → `AmbiguousIntervalTableError`"); `unit_spike_times` writes
#: "spike times in seconds", a unit rather than a type.
_ARROW_ROWS_WITHOUT_A_TYPE_CLAIM = {
    ("jnwb-nwb-data", "resolve_interval_table"),
    ("jnwb-nwb-data", "unit_spike_times"),
}


def _resolve_type_name(name: str):
    """The class a row names, or None when the token names nothing importable."""
    import builtins

    if "." in name:
        head, _, tail = name.partition(".")
        module = {"numpy": np, "np": np, "pandas": pd, "pd": pd}.get(head)
        return getattr(module, tail, None) if module is not None else None
    return getattr(builtins, name, None) or getattr(jnwb, name, None)


def _logical_rows(content: str):
    """(first line number, joined text) for each ``- `` bullet and its continuation lines.

    Reading the file line by line split every wrapped row in half, and a claim landing on
    the second half was attributed to no symbol at all -- `jnwb.events(...)` ends its first
    line on the arrow itself, so the `EventTable` it returns sat on a line with no row head
    above it and was never read.
    """
    rows, start, buf = [], None, []
    for line_no, line in enumerate(content.splitlines(), 1):
        if line.startswith("- "):
            if buf:
                rows.append((start, " ".join(buf)))
            start, buf = line_no, [line]
        elif buf and line.startswith("  ") and line.strip():
            buf.append(line.strip())
        elif buf:
            rows.append((start, " ".join(buf)))
            start, buf = None, []
    if buf:
        rows.append((start, " ".join(buf)))
    return rows


def _probe_complex_tfr():
    rng = np.random.default_rng(7)
    return jnwb.complex_tfr(rng.normal(size=(2, 128)), fs=1000.0,
                            freqs=np.array([10.0, 20.0, 40.0]))


def _probe_vflip():
    freqs = np.linspace(1.0, 150.0, 80)
    psd = np.stack([
        (3.0 if c < 8 else 0.5) * np.exp(-((freqs - 20.0) ** 2) / 50.0)
        + (0.5 if c < 8 else 3.0) * np.exp(-((freqs - 90.0) ** 2) / 400.0)
        + 1.0 / freqs
        for c in range(16)
    ])
    return jnwb.vflip(psd, freqs)


def _probe_xflip():
    rng = np.random.default_rng(3)
    a, b = rng.normal(size=300), rng.normal(size=300)
    data = np.stack([(a if c < 6 else b) + 0.3 * rng.normal(size=300) for c in range(12)])
    return jnwb.xflip(data, n_surrogates=20, rng=np.random.default_rng(1))


def _probe_aperiodic_fit():
    freqs = np.linspace(2.0, 100.0, 60)
    return jnwb.aperiodic_fit(freqs, 10.0 * freqs ** -1.5, (2.0, 100.0))


def _probe_directed_connectivity():
    rng = np.random.default_rng(11)
    X = rng.normal(size=200)
    Y = np.zeros(200)
    Y[1:] = 0.5 * X[:-1] + 0.5 * rng.normal(size=199)
    return jnwb.directed_connectivity(X, Y, method="granger", order=2,
                                      n_surrogates=10, seed=42)


def _probe_relative_power():
    rng = np.random.default_rng(5)
    return jnwb.relative_power(rng.random((4, 8)) + 1.0, rng.random((4, 8)) + 1.0,
                               model="mean_of_ratios", axis=1)


#: Built once and reused: the arrow rows all take the same file, and writing it per claim
#: would rebuild it five times for one assertion each.
_NWB_FIXTURE: List[Path] = []


def _probe_nwb_path() -> Path:
    """A small real NWB file with one acquisition, one interval table and one unit."""
    if _NWB_FIXTURE:
        return _NWB_FIXTURE[0]
    import tempfile
    from datetime import datetime, timezone

    import pynwb
    from pynwb.ecephys import ElectricalSeries

    rng = np.random.default_rng(19)
    path = Path(tempfile.mkdtemp(prefix="skill_routing_")) / "probe.nwb"
    nwb = pynwb.NWBFile(session_description="s", identifier="i",
                        session_start_time=datetime.now(timezone.utc))
    device = nwb.create_device(name="probeA")
    group = nwb.create_electrode_group(name="shank0", description="d", location="V1",
                                       device=device)
    for i in range(4):
        nwb.add_electrode(x=0.0, y=0.0, z=float(i) * 100.0, imp=1.0, location="V1",
                          filtering="none", group=group, group_name="shank0")
    region = nwb.create_electrode_table_region(list(range(4)), "all")
    nwb.add_acquisition(ElectricalSeries(name="lfp", data=rng.normal(size=(1000, 4)),
                                         electrodes=region, rate=1000.0, starting_time=0.0))
    nwb.add_trial_column(name="codes", description="c")
    for i in range(5):
        nwb.add_trial(start_time=float(i), stop_time=float(i) + 0.4, codes=f"c{i % 2}")
    nwb.add_unit(spike_times=np.sort(rng.uniform(0.0, 5.0, 30)))
    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    _NWB_FIXTURE.append(path)
    return path


def _probe_inspect():
    return jnwb.inspect(_probe_nwb_path())


def _probe_events():
    return jnwb.events(_probe_nwb_path())


def _probe_event_onsets():
    return jnwb.event_onsets(_probe_nwb_path())


def _probe_acquisition_channel():
    return jnwb.acquisition_channel(_probe_nwb_path())


def _probe_epoch_continuous():
    rng = np.random.default_rng(23)
    return jnwb.epoch_continuous(rng.normal(size=5000), np.array([1.0, 2.0, 3.0]),
                                 win_s=(-0.1, 0.3), fs=1000.0)


class _ProbeSession:
    """The two methods `build_time_resolved_matrix` reads from a session, and nothing else."""

    def get_units(self, quality=None, area=None):
        return pd.DataFrame({"area": ["V1"] * 3}, index=[0, 1, 2])

    def get_spike_times(self, unit_id):
        return np.sort(np.random.default_rng(unit_id).uniform(0.0, 10.0, 200))


def _probe_build_time_resolved_matrix():
    epochs = pd.DataFrame({"start_time": [1.0, 3.0, 5.0, 7.0]})
    return jnwb.build_time_resolved_matrix(_ProbeSession(), "V1", epochs,
                                           time_window_ms=(-100.0, 200.0))


def _probe_repair_lfp_trials():
    seg = np.random.default_rng(4).normal(0, 1, (12, 4, 200))
    seg[3, :, 50:60] += 40.0
    return jnwb.repair_lfp_trials(seg)


def _probe_repair_band_artifacts():
    power = np.random.default_rng(6).random((10, 5, 40)) + 1.0
    return jnwb.repair_band_artifacts(power, np.linspace(5.0, 80.0, 5))


def _probe_rdm_similarity():
    rng = np.random.default_rng(8)
    return jnwb.rdm_similarity(jnwb.rdm(rng.normal(size=(5, 8))),
                               jnwb.rdm(rng.normal(size=(5, 8))))


#: One executed call per routed symbol that makes a claim about its return's contents.
#: The oracle is the returned object. A return *annotation* would be the same authors'
#: second claim about the same thing, and `-> ComplexTFR` on a function that returns a
#: dict reads identically to one that does not.
_RETURN_CONTENT_PROBES = {
    "complex_tfr": _probe_complex_tfr,
    "vflip": _probe_vflip,
    "xflip": _probe_xflip,
    "aperiodic_fit": _probe_aperiodic_fit,
    "directed_connectivity": _probe_directed_connectivity,
    "relative_power": _probe_relative_power,
    "inspect": _probe_inspect,
    "events": _probe_events,
    "event_onsets": _probe_event_onsets,
    "acquisition_channel": _probe_acquisition_channel,
    "epoch_continuous": _probe_epoch_continuous,
    "raster_psth": lambda: jnwb.raster_psth(
        np.sort(np.random.default_rng(1).uniform(0.0, 10.0, 200)),
        np.array([1.0, 3.0, 5.0]), (-100.0, 400.0), 10.0),
    "compute_psd": lambda: jnwb.compute_psd(np.random.default_rng(2).normal(size=2000), 1000.0),
    "exact_sign_flip": lambda: jnwb.exact_sign_flip(np.random.default_rng(3).normal(0.5, 1, 10)),
    "rdm_similarity": _probe_rdm_similarity,
    "repair_lfp_trials": _probe_repair_lfp_trials,
    "repair_band_artifacts": _probe_repair_band_artifacts,
    "build_time_resolved_matrix": _probe_build_time_resolved_matrix,
}


def _is_record(obj) -> bool:
    """Can this object carry a named field at all?"""
    return dataclasses.is_dataclass(type(obj)) or hasattr(type(obj), "_fields")


def _return_content_claims():
    """(skill, line, symbol, kind, payload) for every claim a row makes about its return."""
    for skill_name in sorted(CANONICAL_SKILLS):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        for line_no, line in _logical_rows(content):
            head = re.match(r"- `jnwb\.((?:\w+\.)*\w+)\(", line)
            if not head:
                continue
            sym = head.group(1)
            for m in _CLAIM_RETURN_TYPE.finditer(line):
                fields = re.findall(r"`(\w+)`", m.group(2)) if m.group(2) else []
                yield skill_name, line_no, sym, "type", (m.group(1), fields)
            if _CLAIM_CARRIES.search(line):
                yield skill_name, line_no, sym, "carries", None
            if _CLAIM_BARE_ARRAY.search(line):
                yield skill_name, line_no, sym, "bare", None
            for m in _CLAIM_RECORDS_NO.finditer(line):
                yield skill_name, line_no, sym, "records_no", m.group(1)
            arrow_type = _CLAIM_ARROW_TYPE.search(line)
            if arrow_type:
                yield skill_name, line_no, sym, "arrow_type", arrow_type.group(1)
            arrow_tuple = _CLAIM_ARROW_TUPLE.search(line)
            if arrow_tuple:
                names = [p.strip() for p in arrow_tuple.group(1).split(",") if p.strip()]
                yield skill_name, line_no, sym, "arrow_tuple", names


def test_skill_return_contents_claims_match_runtime():
    """What a row says the return *contains* is settled by calling it.

    The signature harness above reads `inspect.signature`, so it cannot see one word of
    this: `relative_power` was documented as naming its estimand in the result, and returns
    a bare `float64` array with no `model` anywhere on it. `mean_of_ratios` and
    `ratio_of_means` differ by 7% on the same input here, so an agent that believed the row
    had no way to tell two different quantities apart downstream.

    The case set is the skill text, because the skill text is the claim; the oracle is the
    live call, because the library is the truth. Every claim must have a probe -- a claim
    nobody executes is the defect, not an exemption -- and both directions are checked, so
    a row asserting an absence fails once the API grows the field.
    """
    claims = list(_return_content_claims())
    assert len(claims) >= 5, (
        f"only {len(claims)} return-contents claims were recognised in the skill corpus; "
        f"a claim pattern that stops matching passes this test by finding nothing"
    )

    uncovered = sorted({c[2] for c in claims} - set(_RETURN_CONTENT_PROBES))
    assert uncovered == [], (
        f"these routed symbols claim something about their return and no probe calls them, "
        f"so the claim is unverified: {uncovered}"
    )

    live = {name: probe() for name, probe in _RETURN_CONTENT_PROBES.items()}

    for skill_name, line_no, sym, kind, payload in claims:
        out = live[sym]
        where = f"{skill_name}/SKILL.md:{line_no} jnwb.{sym}"
        if kind == "type":
            claimed_type, claimed_fields = payload
            assert type(out).__name__ == claimed_type, (
                f"{where} says it returns `{claimed_type}`; the call returns "
                f"{type(out).__name__}"
            )
            missing = [f for f in claimed_fields if not hasattr(out, f)]
            assert not missing, (
                f"{where} names {missing!r} on the returned `{claimed_type}`; the object "
                f"has no such attribute"
            )
        elif kind == "carries":
            assert _is_record(out), (
                f"{where} says a value is named in the result, but the call returns "
                f"{type(out).__name__}, which carries no named field at all"
            )
        elif kind == "bare":
            assert not _is_record(out), (
                f"{where} calls the return a bare array; the call returns "
                f"{type(out).__name__}, which does carry named fields -- the row now "
                f"understates what an agent can read back"
            )
        elif kind == "records_no":
            assert not hasattr(out, payload), (
                f"{where} says the return records no {payload!r}; the returned "
                f"{type(out).__name__} has that attribute, so the row is stale"
            )
        elif kind == "arrow_type":
            cls = _resolve_type_name(payload)
            assert cls is not None, (
                f"{where} says it returns `{payload}`, which names no importable type -- "
                f"a row whose type token cannot be resolved is a row nothing can check"
            )
            assert isinstance(out, cls), (
                f"{where} says it returns `{payload}`; the call returns "
                f"{type(out).__name__}"
            )
        elif kind == "arrow_tuple":
            assert isinstance(out, tuple), (
                f"{where} writes its return as the tuple {tuple(payload)!r}; the call "
                f"returns {type(out).__name__}"
            )
            assert len(out) == len(payload), (
                f"{where} writes {len(payload)} return values {tuple(payload)!r}; the call "
                f"returns {len(out)}"
            )


def test_every_arrow_row_states_a_return_the_harness_executes():
    """`jnwb-nwb-data` writes returns after an arrow, and nothing used to read them.

    The claim patterns all require the word "return", so a whole skill file's return
    contract -- seven rows -- produced zero claims and passed
    `test_skill_return_contents_claims_match_runtime` by being invisible to it. Counting
    arrow rows here independently of what the claim patterns extract means a row that stops
    being read is named, instead of quietly leaving the corpus.
    """
    claimed = {
        (skill, sym) for skill, _, sym, kind, _ in _return_content_claims()
        if kind in ("arrow_type", "arrow_tuple")
    }
    silent = set()
    arrow_rows = 0
    for skill_name in sorted(CANONICAL_SKILLS):
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        for line_no, line in _logical_rows(content):
            row = _ARROW_ROW.match(line)
            if not row:
                continue
            arrow_rows += 1
            if (skill_name, row.group(1)) not in claimed:
                silent.add((skill_name, row.group(1)))

    assert arrow_rows >= 7, (
        f"only {arrow_rows} arrow rows found in the skill corpus; a pattern that stops "
        f"matching passes this test by finding nothing to check"
    )
    assert silent == _ARROW_ROWS_WITHOUT_A_TYPE_CLAIM, (
        f"arrow rows yielding no executable return claim: {sorted(silent)}; the declared "
        f"set is {sorted(_ARROW_ROWS_WITHOUT_A_TYPE_CLAIM)}"
    )


def test_all_referenced_docs_paths_exist():
    """Verify every referenced docs/*.md file exists in docs/."""
    pattern = re.compile(r"docs/(\d\d_[a-zA-Z0-9_]+\.md)")

    for skill_name in CANONICAL_SKILLS:
        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        matches = pattern.findall(content)

        for doc_file in matches:
            target_path = DOCS_DIR / doc_file
            assert target_path.exists(), f"Doc file {doc_file} referenced in {skill_name} missing at {target_path}"


def test_no_forbidden_skill_trees_or_ide_authority():
    """Verify no .claude/skills, .cursor, or .agents directory exists in skills/ or acts as skill authority."""
    assert not (SKILLS_DIR / ".claude").exists()
    assert not (SKILLS_DIR / ".cursor").exists()
    assert not (SKILLS_DIR / ".agents").exists()
    assert not (ROOT_DIR / ".claude" / "skills").exists()


def test_no_omission_leakage_in_generic_skills():
    """Verify generic skills contain no omission-specific semantics or terms."""
    forbidden_terms = [
        "omission_identity",
        "condition_code",
        "target_trial",
        "cue_onset",
        "sub-C31o",
        "ses-230831",
    ]

    for skill_name in CANONICAL_SKILLS:
        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term.lower() not in content, f"Forbidden term '{term}' leaked into generic skill {skill_name}"


def test_representative_routing_probes():
    """Run representative routing probes across all 7 domain areas."""
    rng = np.random.default_rng(42)

    # 1. NWB metadata & addressing
    elec_df = pd.DataFrame({"location": ["V1"], "z": [1200.0], "depth_unit": ["um"]}, index=[10])
    assert jnwb.map_peak_channel_to_area(10, elec_df) == "V1"
    assert jnwb.classify_layer_from_depth(10, elec_df) == "Deep"

    # 2. PSTH & onset fitting
    spikes = np.sort(rng.uniform(0.0, 10.0, 100))
    events = np.array([1.0, 3.0, 5.0, 7.0])
    time_bins, rate_hz, _ = jnwb.raster_psth(spikes, events, win_ms=(-100.0, 400.0), bin_ms=10.0)
    smooth_hz = jnwb.causal_exp_smooth(rate_hz, bin_ms=10.0, tau_ms=25.0)
    fit = jnwb.fit_exponential_onset(time_bins, smooth_hz, t0_bounds=(0.0, 200.0))
    assert "t0" in fit and "bound_status" in fit

    # 3. Complex TFR & accumulator
    fs = 1000.0
    freqs = np.array([10.0, 20.0, 40.0])
    acc = jnwb.TFRAccumulator(shape=(2, len(freqs), 100))
    for _ in range(3):
        trial = rng.normal(size=(2, 100))
        tfr = jnwb.complex_tfr(trial, fs=fs, freqs=freqs)
        acc.add_trial(tfr.z, valid=tfr.coi_mask)
    assert acc.power().shape == (2, len(freqs), 100)

    # 4. Permutation & statistics
    g1 = rng.normal(1.0, 1.0, 20)
    g2 = rng.normal(0.0, 1.0, 20)
    res = jnwb.StatisticalAnalysis.compare_groups(g1, g2)
    p_raw = res["parametric"]["pval"]
    q_vals = jnwb.StatisticalAnalysis.fdr_correct([p_raw, 0.04, 0.01])
    assert len(q_vals) == 3
    labels = np.array([0, 1, 0, 1])
    groups = np.array([1, 1, 2, 2])
    plan = jnwb.build_permutation_plan(labels, groups, n_permutations=5, seed=42)
    assert plan["n_permutations"] == 5

    # 5. Decoding
    X = rng.normal(size=(30, 10))
    y = np.array([0] * 15 + [1] * 15)
    dec = jnwb.nested_cv_linear_svm(X, y, n_splits=3)
    assert dec["accuracy"] >= 0.0

    # 6. Directional coupling
    T = 200
    X_ts = rng.normal(size=T)
    Y_ts = np.zeros(T)
    Y_ts[1:] = 0.5 * X_ts[:-1] + 0.5 * rng.normal(size=T - 1)
    gr = jnwb.granger(X_ts, Y_ts, order=2, n_surrogates=10, seed=42)
    assert gr.x_to_y >= 0.0

    # 7. Publication graphics
    jnwb.setup_vector_graphics()


class TestSkillsDoNotCarryDriftingCounts:
    """A count written into a skill file goes stale silently and misleads an agent.

    skills/jnwb/SKILL.md claimed "All 101 exports resolve" against a live 111, and
    "passes 446+ tests" against 527. Both had drifted without failing anything.
    """

    SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills"

    def _skill_files(self):
        files = sorted(self.SKILL_ROOT.glob("*/SKILL.md"))
        assert files, "no skill files found; this test would pass vacuously"
        return files

    def test_no_hardcoded_export_or_test_counts(self):
        patterns = [
            re.compile(r"\b\d{2,5}\s+(?:public\s+|exported\s+)?(?:exports?|symbols?)\b", re.I),
            re.compile(r"\b\d{2,5}\+?\s+tests?\b", re.I),
            re.compile(r"\bpasses\s+\d{2,5}", re.I),
        ]
        offenders = []
        for path in self._skill_files():
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if any(p.search(line) for p in patterns):
                    offenders.append(f"{path.parent.name}/SKILL.md:{line_no}: {line.strip()}")
        assert offenders == [], (
            "skill files must not state counts; run the check and let jnwb.__all__ be the "
            "source of truth: " + "; ".join(offenders)
        )

    def test_skills_do_not_reference_a_removed_docs_toolchain(self):
        """A skill telling an agent to run a command that no longer exists wastes a turn."""
        repo_root = self.SKILL_ROOT.parent
        has_sphinx = (repo_root / "docs" / "conf.py").exists()
        offenders = []
        for path in self._skill_files():
            text = path.read_text(encoding="utf-8")
            if "sphinx" in text.lower() and not has_sphinx:
                offenders.append(path.parent.name)
        assert offenders == [], (
            f"these skills reference sphinx, which this repo no longer builds: {offenders}"
        )


class TestAmbiguousUnitProbes:
    """0.2.4-09: a skill that routes on depth must not let a unit be guessed.

    Depth in a cortical column is the one quantity where a factor of 1000 still looks
    plausible: 1200 um and 1.2 mm are the same place, and 1.2 um is a different answer
    rather than an obviously broken one. These pin that jnwb never infers the unit from
    the magnitude, that declaring the wrong one changes the answer, and that an
    undeclared or unsupported unit yields no classification at all.
    """

    @staticmethod
    def _row(z, unit=None, index=10):
        data = {"location": ["V1"], "z": [z]}
        if unit is not None:
            data["depth_unit"] = [unit]
        return pd.DataFrame(data, index=[index])

    def test_the_same_physical_depth_classifies_the_same_in_either_unit(self):
        assert jnwb.classify_layer_from_depth(10, self._row(1200.0, "um")) == "Deep"
        assert jnwb.classify_layer_from_depth(10, self._row(1.2, "mm")) == "Deep"

    def test_the_unit_is_never_inferred_from_the_magnitude(self):
        """1.2 declared as um is 1.2 um, not a mislabelled 1.2 mm."""
        assert jnwb.classify_layer_from_depth(10, self._row(1.2, "um")) == "Superficial"

    def test_an_undeclared_unit_is_not_guessed(self):
        assert jnwb.classify_layer_from_depth(10, self._row(1200.0)) == "Unknown"

    @pytest.mark.parametrize("unit", ["furlong", "", "px"])
    def test_an_unsupported_unit_refuses_to_classify(self, unit):
        """Documented invariant: unknown or unsupported units give 'Unknown', never a
        layer. A wrong label here would be silently wrong; 'Unknown' is visibly missing."""
        assert jnwb.classify_layer_from_depth(10, self._row(1200.0, unit)) == "Unknown"

    @pytest.mark.parametrize("spelling", ["um", "UM", " um ", "micron", "microns", "micrometer"])
    def test_accepted_spellings_agree(self, spelling):
        assert jnwb.classify_layer_from_depth(10, self._row(1200.0, spelling)) == "Deep"

    def test_an_explicit_argument_overrides_a_conflicting_table_column(self):
        """Evidence conflict with a deterministic, documented resolution: the caller's
        explicit declaration wins, and the outcome differs, so the conflict is never
        silently averaged or ignored."""
        table_mm = self._row(1200.0, "mm")
        assert jnwb.classify_layer_from_depth(10, table_mm) == "Unknown"
        assert jnwb.classify_layer_from_depth(10, table_mm, depth_unit="um") == "Deep"

    def test_probe_geometry_takes_the_declared_unit_literally(self):
        """Millimetre coordinates declared as micrometres give a 0.05 um pitch rather
        than a silently corrected one. The library does not second-guess the caller, so a
        skill must declare the unit it actually has."""
        millimetres = pd.DataFrame(
            {"location": ["V1"] * 4, "x": [0.0] * 4, "y": [0.0] * 4,
             "z": [0.0, 0.05, 0.10, 0.15]}
        )
        assert jnwb.probe_geometry(millimetres, units="um").nominal_pitch == pytest.approx(0.05)
        micrometres = pd.DataFrame(
            {"location": ["V1"] * 4, "x": [0.0] * 4, "y": [0.0] * 4,
             "z": [0.0, 50.0, 100.0, 150.0]}
        )
        assert jnwb.probe_geometry(micrometres, units="um").nominal_pitch == pytest.approx(50.0)

    def test_probe_geometry_rejects_an_unsupported_unit(self):
        table = pd.DataFrame(
            {"location": ["V1"] * 4, "x": [0.0] * 4, "y": [0.0] * 4,
             "z": [0.0, 50.0, 100.0, 150.0]}
        )
        with pytest.raises(ValueError, match="(?i)unit"):
            jnwb.probe_geometry(table, units="furlong")


class TestEvidenceConflictProbes:
    """0.2.4-09: the fact stack is human-authorized, and nothing may quietly edit it."""

    def test_no_shipped_code_writes_the_fact_stack(self):
        """`jnwb-fact-action` states that agents may read and challenge facts but must
        never autonomously add, edit or delete them. That is only a rule if no code path
        can do it."""
        # Rooted at the checkout: run from elsewhere, a bare `Path("jnwb")` globbed nothing and
        # this passed having read no file.
        scanned = list((ROOT_DIR / "jnwb").rglob("*.py")) + list(
            (ROOT_DIR / "scripts").rglob("*.py")
        )
        assert len(scanned) > 20, f"only {len(scanned)} files scanned; the glob is wrong"
        offenders = _fact_stack_writers(scanned)
        assert not offenders, f"code that could rewrite the fact stack: {offenders}"

    def test_the_probe_still_catches_a_real_writer(self, tmp_path: Path):
        """The discriminator for the narrowing above, in both scope kinds.

        The live answer is zero offenders, and a zero proves nothing on its own. A writer at
        module level and a writer inside a function are each planted and each caught.
        """
        (tmp_path / "top.py").write_text(
            "from pathlib import Path\nPath('artifacts/fact_stack.md').write_text('x')\n",
            encoding="utf-8",
        )
        (tmp_path / "nested.py").write_text(
            "from pathlib import Path\n\n\n"
            "def repair():\n"
            "    target = Path('artifacts/fact_stack.md')\n"
            "    target.write_text('x')\n",
            encoding="utf-8",
        )
        caught = _fact_stack_writers(sorted(tmp_path.glob("*.py")))
        assert len(caught) == 2, caught

    def test_the_probe_ignores_a_comment_about_writing(self, tmp_path: Path):
        """Prose naming the API is not a call of it."""
        (tmp_path / "prose.py").write_text(
            "# Path('fact_stack.md').write_text('x') would be wrong\n"
            '"""fact_stack.md is named here, and write_text is explained here."""\n'
            "value = 1\n",
            encoding="utf-8",
        )
        assert _fact_stack_writers([tmp_path / "prose.py"]) == []

    def test_two_unrelated_mentions_in_one_file_are_not_a_writer(self, tmp_path: Path):
        """The case that forced the scoping, reduced to its shape.

        `scripts/harness_gate.py` names `fact_stack.md` in its gated-vocabulary tuple and names
        `write_text` in a violation message that tells an author which API converted their line
        endings. Both are executable, so stripping prose does not separate them -- but they are
        four hundred lines and two scopes apart, and neither writes anything.
        """
        (tmp_path / "gate.py").write_text(
            "TERMS = ('fact_stack.md', 'todo_stack.md')\n\n\n"
            "def explain():\n"
            "    return 'use newline= or write bytes; write_text translates line endings'\n",
            encoding="utf-8",
        )
        assert _fact_stack_writers([tmp_path / "gate.py"]) == []

    def test_the_probe_reads_the_real_harness_gate(self):
        """The file the scoping was built for is actually scanned, and actually clears."""
        gate = ROOT_DIR / "scripts" / "harness_gate.py"
        assert gate.is_file(), f"{gate} is gone; the case above no longer has a subject"
        text = gate.read_text(encoding="utf-8")
        assert "fact_stack.md" in text and "write_text" in text, (
            "harness_gate.py no longer carries both halves of the co-occurrence, so this test "
            "would pass for a reason that has nothing to do with the scoping"
        )
        assert _fact_stack_writers([gate]) == []

    # Both read through SKILLS_DIR rather than a bare relative path: a path relative to
    # the current directory resolves only when pytest is run from the repository root.
    def test_the_conflict_rule_is_still_stated_in_the_skill(self):
        text = (SKILLS_DIR / "jnwb-fact-action" / "SKILL.md").read_text(encoding="utf-8")
        assert "MUST NOT autonomously add, edit, or delete facts" in text
        assert "empirical receipts and discriminating tests" in text

    def test_conflicting_conclusions_are_resolved_by_receipts_not_consensus(self):
        text = (SKILLS_DIR / "jnwb-fact-action" / "SKILL.md").read_text(encoding="utf-8")
        assert "never through voting or consensus" in text


class TestCausalFilterDelayIsScopedToAThresholdCrossing:
    """P-58. The spiking skill told an agent to subtract a filter delay from a fitted onset.

    `causal_exp_smooth` delays a threshold crossing by about tau*ln2, and the skill carried
    that correction as an unscoped instruction while routing onsets only to
    `fit_exponential_onset`, which is a parametric fit rather than a crossing. Measured on a
    1 ms unit step at a true t0 of 100 ms: the crossing lands +5.9, +16.2, +33.3 and +67.6 ms
    late for tau_ms of 10, 25, 50 and 100, while the fit holds a tau-invariant -0.9 ms that
    tracks bin_ms. Obeying the instruction turned -0.9 ms into -18.2 ms at tau_ms=25, silently,
    in scientific output.

    What would make these assertions pass while the invariant is violated: checking that the
    words "subtract" and "threshold crossing" each occur somewhere in the section. The
    repaired paragraph states both more than once, so deleting the scope from the instruction
    would leave the words behind and the check would stay green. That is how two mutants
    survived the first repair of P-88. Each assertion below therefore pins one sentence and
    requires it to carry the instruction and its scope together, so removing either half kills
    it.
    """

    SKILL = Path(__file__).resolve().parents[1] / "skills" / "jnwb-spiking" / "SKILL.md"
    HEADING = "## 3. Invariants & Safeguards"

    def _section(self):
        """The raw text of the safeguards section. The file is CRLF."""
        text = self.SKILL.read_text(encoding="utf-8")
        assert self.HEADING in text, (
            f"{self.SKILL.name} has no {self.HEADING!r} section, so every assertion below "
            "would pass vacuously"
        )
        return text.split(self.HEADING, 1)[1].split("\n## ", 1)[0]

    def _sentences(self):
        """Sentences of the safeguards section, by the shared split."""
        sentences = _sentence_units(self._section())
        assert len(sentences) > 1, "the safeguards section did not split into sentences"
        return sentences

    def _delay_corrections(self):
        """Sentences that speak about removing a filter or group delay from something.

        `_delay_sentences` is the shared definition, read here against the raw section so the
        skill and the docstring are held to one rule rather than to two copies of it.
        """
        self._sentences()  # keeps the heading assertion on the path
        return _delay_sentences(self._section())

    def test_the_correction_names_its_readout_in_the_sentence_that_gives_it(self):
        giving = [s for s in self._delay_corrections() if "fit_exponential_onset" not in s]
        assert len(giving) == 1, (
            "expected exactly one sentence instructing a filter-delay correction without "
            f"naming the fit; found {len(giving)}: {giving}"
        )
        assert re.search(r"threshold crossing", giving[0], re.I), (
            "the filter-delay correction does not name the readout it applies to, so it reads "
            "as applying to whatever onset the agent is holding -- including a fitted t0, "
            f"where subtracting tau*ln2 injects about -18 ms at tau_ms=25: {giving[0]!r}"
        )
        assert re.search(r"\bonly\b", giving[0], re.I), (
            "the correction mentions a crossing but does not restrict itself to one, so it "
            f"still reads as permitting the same correction on a fitted onset: {giving[0]!r}"
        )

    def test_the_fit_is_withheld_from_the_correction_in_one_sentence(self):
        about_fit = [s for s in self._delay_corrections() if "fit_exponential_onset" in s]
        assert len(about_fit) == 1, (
            "expected exactly one sentence relating fit_exponential_onset to the filter-delay "
            f"correction; found {len(about_fit)}: {about_fit}"
        )
        assert re.search(r"\bnot\b", about_fit[0]), (
            "the sentence naming fit_exponential_onset alongside the filter-delay correction "
            f"does not withhold the correction from it: {about_fit[0]!r}"
        )
        assert re.search(r"threshold crossing", about_fit[0], re.I), (
            "the exemption does not say what fit_exponential_onset is being distinguished "
            f"from, so a reader cannot match it against their own readout: {about_fit[0]!r}"
        )

    def test_the_tau_contrast_that_identifies_the_readout_is_one_sentence(self):
        contrast = [
            s for s in self._sentences()
            if re.search(r"crossing", s, re.I) and re.search(r"invariant", s, re.I)
        ]
        assert len(contrast) == 1, (
            "no single sentence contrasts the crossing's tau-scaling against the fit's "
            "tau-invariance. That contrast is the only way a reader tells which readout they "
            "hold: the crossing error scales with tau_ms, the fit's -0.9 ms bias does not and "
            f"tracks bin_ms instead (found {len(contrast)} candidate sentences)"
        )

    def test_the_docstring_carries_the_same_scope_as_the_skill(self):
        """The skill was scoped and the docstring next to the code was not.

        `causal_exp_smooth`'s docstring stated `t_observed = t_signal + t_estimator` as a
        general identity and then told the reader not to compare latencies without accounting
        for estimator delay, with no scope at all. A reader holding a fitted t0 -- which is the
        only onset this module produces -- would apply the correction and turn a -0.9 ms bias
        into about -18 ms at tau_ms=25.

        The three assertions below are the skill's own three, run against the docstring, so the
        two faces cannot drift apart: whichever one is edited, the other must state the same
        rule or this fails. They are reused rather than restated, because a second copy of an
        assertion is a second thing to keep in step.
        """
        from jnwb.onset_fitting import causal_exp_smooth

        doc = causal_exp_smooth.__doc__
        assert doc, "causal_exp_smooth has no docstring, so every assertion here is vacuous"
        sentences = _delay_sentences(doc)

        giving = [s for s in sentences if "fit_exponential_onset" not in s]
        assert len(giving) == 1, (
            "expected exactly one docstring sentence instructing a filter-delay correction "
            f"without naming the fit; found {len(giving)}: {giving}"
        )
        assert re.search(r"threshold crossing", giving[0], re.I), (
            "the docstring's filter-delay correction does not name the readout it applies to, "
            f"so it reads as applying to a fitted t0 as well: {giving[0]!r}"
        )
        assert re.search(r"\bonly\b", giving[0], re.I), (
            "the docstring mentions a crossing but does not restrict the correction to one: "
            f"{giving[0]!r}"
        )

        about_fit = [s for s in sentences if "fit_exponential_onset" in s]
        assert len(about_fit) == 1, (
            "expected exactly one docstring sentence relating fit_exponential_onset to the "
            f"filter-delay correction; found {len(about_fit)}: {about_fit}"
        )
        assert re.search(r"\bnot\b", about_fit[0]), (
            "the docstring names fit_exponential_onset alongside the correction without "
            f"withholding the correction from it: {about_fit[0]!r}"
        )

        contrast = [
            s for s in _sentence_units(doc)
            if re.search(r"crossing", s, re.I) and re.search(r"invariant", s, re.I)
        ]
        assert len(contrast) == 1, (
            "no single docstring sentence contrasts the crossing's tau-scaling against the "
            "fit's tau-invariance, which is the only way a reader tells which readout they "
            f"hold (found {len(contrast)})"
        )

    def test_a_second_unscoped_instruction_in_the_docstring_is_caught(self):
        """The mutant 06-93 settled on, applied to the docstring.

        Every word of the repaired text is left intact and one more unscoped instruction is
        added. A check for the presence of "subtract" and "threshold crossing" would stay green
        -- the repaired text states both more than once -- which is how two mutants survived
        the first repair of P-88. Pinning one sentence is what kills it.
        """
        from jnwb.onset_fitting import causal_exp_smooth

        mutant = causal_exp_smooth.__doc__ + (
            "\n    Subtract the filter delay from the onset before comparing conditions.\n"
        )
        giving = [s for s in _delay_sentences(mutant) if "fit_exponential_onset" not in s]
        assert len(giving) == 2, (
            "the added unscoped instruction was not seen as a second correction-giving "
            f"sentence, so this discriminator does not discriminate: {giving}"
        )

    @pytest.mark.parametrize("instruction", [
        "Never compare onset latencies without accounting for estimator delay.",
        "Correct every onset for the smoothing lag before comparing conditions.",
    ])
    def test_the_original_unscoped_wordings_are_seen(self, instruction):
        """P-110's own wording survived the guard: it names neither a filter nor a group delay
        and says "accounting for" rather than subtract, remove or correct."""
        from jnwb.onset_fitting import causal_exp_smooth

        mutant = causal_exp_smooth.__doc__ + f"\n    {instruction}\n"
        giving = [s for s in _delay_sentences(mutant) if "fit_exponential_onset" not in s]
        assert len(giving) == 2, giving

    def test_tau_ms_is_still_held_fixed_across_compared_conditions(self):
        """The half of the original safeguard that was correct and is load-bearing."""
        fixed = [
            s for s in self._sentences()
            if re.search(r"`tau_ms` fixed", s) and re.search(r"compar", s, re.I)
        ]
        assert len(fixed) == 1, (
            "the instruction to hold tau_ms fixed across compared conditions was dropped; a "
            "latency difference between two traces smoothed at different tau_ms is a "
            f"difference between the filters (found {len(fixed)})"
        )


class TestClaimsTheSignatureCannotCarry:
    """Rows whose defect survives every check above, because none of it is in the call.

    `inspect.signature` reads names, kinds and defaults, so a row can be signature-perfect
    and still tell an agent something false about what the call does with what it is given,
    what units come back, or which keys exist under which branch. Each test here names the
    sentence it is checking, so rewording the row moves the sentence check rather than
    leaving an assertion that no longer corresponds to anything the skill says.
    """

    def _skill(self, name: str) -> str:
        return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")

    def test_a_single_figure_is_not_a_figure_suite(self, tmp_path: Path):
        """`save_figure_suite` iterates `figures`; the row used to say "one or more".

        The signature is `figures: List[plt.Figure]` and the body is a `for` loop, so one
        figure passed as itself raises `TypeError: 'Figure' object is not iterable` before
        anything is written. The row read as though the singular case worked, and every
        check in this file passed it -- the parameter exists, is positional, and is first.
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        try:
            with pytest.raises(TypeError):
                jnwb.save_figure_suite(fig, tmp_path, "solo")
            assert not list(tmp_path.iterdir()), (
                "a rejected call still wrote files, so the row's singular reading is only "
                "half wrong and the failure is partial"
            )

            jnwb.save_figure_suite([fig], tmp_path, "solo")
            assert sorted(p.name for p in tmp_path.iterdir()) == [
                "solo_page1.pdf", "solo_page1.png"
            ], "the default `formats` in the row no longer describe what lands on disk"
        finally:
            plt.close("all")

        row = [
            line for line in self._skill("jnwb-figures").splitlines()
            if line.startswith("- `jnwb.save_figure_suite(")
        ]
        assert len(row) == 1 and "list" in row[0].lower() and "[fig]" in row[0], (
            f"the row no longer says a list is required, so a reader is back where they "
            f"started: {row!r}"
        )

    def test_naming_a_primary_test_drops_the_other_block(self):
        """`exploratory_compare`'s `test` argument changes the returned keys.

        The row says "`test` names the primary test and the other is then not computed",
        which is a claim about the return schema under a branch -- the class of defect
        `cross_modal_comparison` was repaired for in 0.2.5, where a key existed only under
        an unstated branch. Here the branch is stated and the keys really do disappear, so
        the check is that they disappear in both directions rather than that the sentence
        exists.
        """
        rng = np.random.default_rng(12)
        g1, g2 = rng.normal(1.0, 1.0, 25), rng.normal(0.0, 1.0, 25)
        both = jnwb.StatisticalAnalysis.exploratory_compare(g1, g2)
        parametric = jnwb.StatisticalAnalysis.exploratory_compare(g1, g2, test="parametric")
        nonparametric = jnwb.StatisticalAnalysis.exploratory_compare(
            g1, g2, test="nonparametric"
        )

        assert {"parametric", "non_parametric"} <= set(both), (
            f"the default no longer runs two tests; keys: {sorted(both)}"
        )
        assert set(both) - set(parametric) == {"non_parametric", "significant_nonparametric"}, (
            f"test='parametric' no longer withholds exactly the non-parametric block: "
            f"{sorted(set(both) - set(parametric))}"
        )
        assert set(both) - set(nonparametric) == {"parametric", "significant_parametric"}, (
            f"test='nonparametric' no longer withholds exactly the parametric block: "
            f"{sorted(set(both) - set(nonparametric))}"
        )

        # The other half of the same row: what separates this entry point from its sibling.
        confirmatory = jnwb.StatisticalAnalysis.compare_groups(g1, g2)
        assert set(confirmatory) - set(both) == {"multiple_comparison"}, (
            f"the row says `exploratory_compare` is `compare_groups` without the "
            f"`multiple_comparison` block; the live difference is "
            f"{sorted(set(confirmatory) - set(both))}"
        )

        text = self._skill("jnwb-statistics")
        assert "the other is then not computed" in text, (
            "the conditional-schema sentence this test executes is gone from the row"
        )

    @pytest.mark.parametrize("spelling", [
        "spike_mutual_information",
        "binary_occupancy_mutual_information",
        "spike_count_mutual_information",
    ])
    def test_mutual_information_is_reported_in_bits_and_is_symmetric(self, spelling):
        """The row's two claims about the number, neither of them in the signature.

        "in **bits** ($\\log_2$)" is a unit, and a unit is invisible to
        `inspect.signature`: the same call returning nats would satisfy every other check
        in this file. Two spike trains occupying exactly the same bins carry 1 bit of
        mutual information under $\\log_2$ and 0.693 under $\\ln$, which is what makes this
        a discriminator rather than a range check.
        """
        fn = getattr(jnwb, spelling)
        rng = np.random.default_rng(4)
        bin_s, n_bins = 0.010, 2000
        centres = (np.arange(n_bins) + 0.5) * bin_s
        occupied = rng.random(n_bins) < 0.5
        same = centres[occupied]
        window = (0.0, n_bins * bin_s)

        mi = fn(same, same.copy(), time_window_s=window, bin_size_ms=10.0)
        assert mi == pytest.approx(1.0, abs=0.01), (
            f"{spelling}: identical occupancy carries {mi} -- 1.0 in bits, 0.693 in nats"
        )

        other = centres[rng.random(n_bins) < 0.5]
        ab = fn(same, other, time_window_s=window, bin_size_ms=10.0)
        ba = fn(other, same, time_window_s=window, bin_size_ms=10.0)
        assert ab == pytest.approx(ba), (
            f"{spelling}: the row says MI carries no direction however the arguments are "
            f"ordered, but {ab} != {ba}"
        )

        text = self._skill("jnwb-connectivity")
        assert "**bits**" in text and "MI is symmetric" in text, (
            "the unit and symmetry claims this test executes are gone from the row"
        )


def _row_text(skill: str, symbol: str) -> str:
    """The one routing row in `skill` whose call opens with `jnwb.<symbol>(`, joined."""
    content = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
    rows = [text for _, text in _logical_rows(content)
            if re.match(rf"- `jnwb\.{re.escape(symbol)}\(", text)]
    assert len(rows) == 1, f"{skill}: expected one routing row for jnwb.{symbol}, found {len(rows)}"
    return rows[0]


def test_the_continuous_keys_the_skill_lists_are_the_live_ones():
    """The skill writes the continuous-entry keys out rather than routing at a private tuple.

    A written-out list is a copy, and a copy drifts; this holds it to the code in both
    directions and to what `inspect` actually returns. What would pass while the list is
    wrong: comparing against the skill's own sentence, or only checking a subset.
    """
    from jnwb.nwb_inspect import CONTINUOUS_KEYS

    text = (SKILLS_DIR / "jnwb-nwb-data" / "SKILL.md").read_text(encoding="utf-8")
    sentence = re.search(r"Every continuous entry always carries(.*?)when unknown", text, re.S)
    assert sentence, "the sentence listing the continuous-entry keys is gone"
    listed = re.findall(r"`(\w+)`", sentence.group(1))
    listed = [k for k in listed if k != "None"]
    assert sorted(listed) == sorted(CONTINUOUS_KEYS), (listed, CONTINUOUS_KEYS)

    entry = jnwb.inspect(_probe_nwb_path())["acquisitions"][0]
    assert set(CONTINUOUS_KEYS) <= set(entry), sorted(set(CONTINUOUS_KEYS) - set(entry))


def _deprecated_granger_causality():
    rng = np.random.default_rng(11)
    x = rng.normal(size=200)
    y = np.r_[0.0, 0.5 * x[:-1]] + 0.5 * rng.normal(size=200)
    with pytest.deprecated_call():
        return jnwb.granger_causality(x, y, order=2)


def _folds_frame(cycles):
    n = len(cycles)
    return pd.DataFrame({"session": ["s"] * n, "analysis": ["a"] * n, "slot_key": ["k"] * n,
                         "cycle": cycles, "trial_id": np.arange(n)})


class TestRowsAgainstTheLiveCall:
    """Row claims about keys, units, axes and failure behaviour, each settled by a call.

    `inspect.signature` sees none of these. Each case was wrong or unstated in a row before it
    was checked here: `compute_response_metrics` promised a modulation index it does not
    compute; `compute_psd` was described as producing `vflip`'s channels-by-frequency input at
    an `axis` that reads the transpose; `apply_tight_auto_axis` was called auto-scaling while it
    pins x and clips negative y; `resample_onsets` was called subsampling while it repeats
    onsets when short.
    """

    @pytest.mark.parametrize("skill, symbol, call, keys", [
        ("jnwb-spiking", "compute_response_metrics",
         lambda: jnwb.compute_response_metrics(
             np.sort(np.random.default_rng(0).uniform(0.0, 10.0, 400)),
             np.array([1.0, 3.0, 5.0, 7.0]),
             baseline_window_s=(-0.2, 0.0), response_window_s=(0.0, 0.2)),
         ["baseline_rate", "response_rate", "response_count", "response_zscore", "latency",
          "n_trials"]),
        ("jnwb-population", "nested_cv_linear_svm",
         lambda: jnwb.nested_cv_linear_svm(np.random.default_rng(6).normal(size=(40, 6)),
                                           np.array([0, 1] * 20), 3),
         ["accuracy", "fold_accuracies", "f1", "auc", "best_params",
          "majority_baseline_accuracy"]),
        ("jnwb-population", "compute_population_trajectory",
         lambda: jnwb.compute_population_trajectory(
             _ProbeSession(), "V1", pd.DataFrame({"start_time": [1.0, 3.0, 5.0, 7.0]}),
             time_window_ms=(-100.0, 200.0)),
         ["trajectory", "explained_variance", "unit_ids", "bin_centers"]),
        ("jnwb-population", "build_representation_ladder",
         lambda: jnwb.build_representation_ladder(np.random.default_rng(1).normal(size=(4, 3, 5))),
         ["X_rate", "X_vec", "X_structured", "contract"]),
        ("jnwb-population", "assign_outer_folds",
         lambda: jnwb.assign_outer_folds(_folds_frame([0, 0, 1, 1])),
         ["outer_fold", "outer_group", "outer_fold_status"]),
        ("jnwb-connectivity", "granger_causality", _deprecated_granger_causality,
         ["F_1_to_2", "F_2_to_1"]),
    ])
    def test_the_keys_a_row_names_are_returned(self, skill, symbol, call, keys):
        """Both directions: the row names each key, and the call returns each key."""
        row = _row_text(skill, symbol)
        out = call()
        unnamed = [k for k in keys if f"`{k}`" not in row]
        missing = [k for k in keys if k not in out]
        assert not unnamed, f"{skill} row for {symbol} no longer names {unnamed}"
        assert not missing, f"jnwb.{symbol} no longer returns {missing}; keys: {list(out)}"
        assert not [k for k in out if "modulation" in str(k)], (
            f"jnwb.{symbol} now returns a modulation key the row says it does not compute"
        )

    def test_compute_psd_reads_time_along_axis_and_composes_with_vflip(self):
        lfp = np.random.default_rng(16).normal(size=(16, 3000))
        freqs, psd = jnwb.compute_psd(lfp, 1000.0, axis=-1)
        assert psd.shape == (16, freqs.size) and freqs.size > 100

        wrong_freqs, wrong_psd = jnwb.compute_psd(lfp, 1000.0)
        assert wrong_freqs.size < 16 and wrong_psd.shape == (wrong_freqs.size, 3000), (
            "a channels-by-time array at axis=0 no longer yields a few-bin spectrum over "
            "channels, so the row's warning describes something that does not happen"
        )

        composed, direct = jnwb.vflip(psd, freqs), jnwb.vflip_from_lfp(lfp, 1000.0)
        assert composed.support_score == pytest.approx(direct.support_score)
        assert (composed.accepted, composed.crossover_contact) == (
            direct.accepted, direct.crossover_contact)

    def test_the_two_exponents_have_opposite_signs_and_a_batch_is_a_list(self):
        """`exponent` means a positive decay rate in one function and a signed slope in the
        other. A 1/f-like trace must give opposite signs, or the row's warning is wrong."""
        trace = np.random.default_rng(21).normal(size=4000).cumsum()
        tilt = jnwb.spectral_tilt(trace, fs=1000.0)
        freqs, psd = jnwb.compute_psd(trace, 1000.0)
        freqs, psd = freqs[1:], psd[1:]  # aperiodic_fit refuses the 0 Hz bin
        fit = jnwb.aperiodic_fit(freqs, psd, (2.0, 100.0))
        assert fit.accepted and fit.exponent > 0 > tilt["exponent"], (fit, tilt)

        batch = jnwb.aperiodic_fit(freqs, np.stack([psd, psd, psd]), (2.0, 100.0))
        assert isinstance(batch, list) and len(batch) == 3
        assert all(isinstance(r, jnwb.AperiodicFitResult) for r in batch)

    def test_plotting_helpers_do_what_their_rows_say(self):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        try:
            ax.plot([0.0, 5.0, 10.0], [-1.0, 1.0, 0.5])
            jnwb.apply_tight_auto_axis(ax, x_span=(0.0, 10.0))
            assert ax.get_xlim() == (0.0, 10.0)
            assert ax.get_ylim()[0] == 0.0, "the lower y-limit is no longer floored at 0"
            jnwb.apply_tight_auto_axis(ax)
            assert ax.get_xlim() == (-500.0, 4124.0), "x is no longer pinned to x_span"
        finally:
            plt.close(fig)

        short = jnwb.resample_onsets(np.arange(10.0), target_n=25)
        assert short.size == 25 and np.unique(short).size <= 10
        long = jnwb.resample_onsets(np.arange(50.0), target_n=20)
        assert long.size == 20 and np.unique(long).size == 20

        spikes = np.sort(np.random.default_rng(2).uniform(0.0, 5.0, 100))
        _, rate, sem = jnwb.raster_psth(spikes, np.array([1.0]), (-100.0, 400.0), 10.0)
        assert np.isfinite(rate).all() and np.isnan(sem).all()
        _, rate, sem = jnwb.raster_psth(spikes, np.array([]), (-100.0, 400.0), 10.0)
        assert np.isnan(rate).all() and np.isnan(sem).all()

    def test_an_explicit_code_column_must_exist_and_the_implicit_one_need_not(self, tmp_path):
        from datetime import datetime, timezone

        import pynwb

        nwbfile = pynwb.NWBFile(session_description="s", identifier="i",
                                session_start_time=datetime.now(timezone.utc))
        for i in range(3):
            nwbfile.add_trial(start_time=float(i), stop_time=float(i) + 0.5)
        nwb = tmp_path / "no_codes.nwb"
        with pynwb.NWBHDF5IO(str(nwb), "w") as io:
            io.write(nwbfile)

        assert jnwb.event_onsets(nwb).tolist() == [0.0, 1.0, 2.0]
        with pytest.warns(UserWarning, match="codes"):
            assert jnwb.events(nwb).code_column is None
        with pytest.raises(jnwb.ColumnNotFoundError):
            jnwb.event_onsets(nwb, code_column="label")
        with pytest.raises(jnwb.ColumnNotFoundError):
            jnwb.events(nwb, code_column="label")

    def test_tiers_census_and_folds_refuse_or_label_what_their_rows_say(self):
        tier = jnwb.assign_quality_tier(
            pd.Series([0, 1, 1, 2, np.nan]),
            pd.Series([0.99, 0.99, 0.98, 0.99, 0.99]),
            pd.Series([1.0, 1.0, 1.0, 1.0, 1.0]),
        )
        assert tier.tolist() == ["mua", "stable", "unstable", "unstable", "unstable"]

        with pytest.raises(KeyError):
            jnwb.unit_census_report(pd.DataFrame(
                {"session_id": ["s"], "area": ["V1"], "depth_class": ["Deep"], "unit_id": [0]}
            ))

        with pytest.raises(ValueError, match="trial_id"):
            jnwb.assign_outer_folds(_folds_frame([0, 1]).drop(columns="trial_id"))
        single = jnwb.assign_outer_folds(_folds_frame([0, 0, 0]))
        assert set(single["outer_fold"]) == {-1}
        assert set(single["outer_fold_status"]) == {"insufficient_groups"}

    def test_exact_enumeration_uses_no_rng_and_shuffles_floor_at_one_over_n_plus_one(self):
        diffs = np.random.default_rng(5).normal(0.5, 1.0, 12)
        assert jnwb.exact_sign_flip(diffs, rng=1)[1] == jnwb.exact_sign_flip(diffs, rng=2)[1]

        a, b = np.arange(20.0) + 100.0, np.arange(20.0)
        for fn in (jnwb.shuffle_pvalue_paired, jnwb.shuffle_pvalue_unpaired):
            assert fn(a, b, 49, np.random.default_rng(0))[1] == pytest.approx(1.0 / 50.0), fn

        plan = jnwb.build_permutation_plan([0, 1, 0, 1], [1, 1, 2, 2], n_permutations=2, rng=3)
        digests = plan["draw_manifest"]["label_digest"]
        assert all(re.fullmatch(r"[0-9a-f]{64}", d) for d in digests), list(digests)

    def test_the_laminar_derivative_row_states_the_shape_and_offset_the_call_returns(self):
        """Output row `k` of both second-derivative calls sits on input channel `k + 1`.

        A reader who plots the output against the input depths without that offset draws every
        sink and source one contact too shallow. The impulse is the discriminator: a unit
        potential on channel 3 alone puts the curvature minimum on output row 2, not row 3.
        """
        row = _row_text("jnwb-lfp-spectral", "current_source_density_1d")
        assert "two fewer channels" in row, row
        assert re.search(r"output row `k` is input channel `k \+ 1`", row), row

        pitch_um, sigma = 100.0, 0.3
        dz2 = (pitch_um * 1e-6) ** 2
        lfp = np.random.default_rng(31).normal(size=(6, 40))
        curvature = jnwb.voltage_curvature_1d(lfp, pitch_um=pitch_um)
        csd = jnwb.current_source_density_1d(lfp, pitch_um=pitch_um, conductivity_s_per_m=sigma)
        assert curvature.shape == csd.shape == (4, 40)
        for k in range(4):
            np.testing.assert_allclose(
                curvature[k], (lfp[k + 2] - 2.0 * lfp[k + 1] + lfp[k]) / dz2, rtol=1e-12
            )
        np.testing.assert_allclose(csd, -sigma * curvature, rtol=1e-12)

        impulse = np.zeros((6, 1))
        impulse[3] = 1.0
        assert int(np.argmin(jnwb.voltage_curvature_1d(impulse, pitch_um=pitch_um))) == 2

    def test_fdr_is_named_as_benjamini_hochberg_and_never_as_family_wise(self):
        """FDR and family-wise error control are different guarantees; a label joining them
        tells a reader that `fdr_correct` controls the error rate it does not."""
        texts = {}
        for skill in sorted(CANONICAL_SKILLS):
            texts[f"{skill}/SKILL.md"] = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
            texts[f"{skill}/agents/openai.yaml"] = (
                SKILLS_DIR / skill / "agents" / "openai.yaml"
            ).read_text(encoding="utf-8")
        joined = [
            name for name, text in texts.items()
            if re.search(r"family[- ]wise\s+(?:FDR|false discovery)", " ".join(text.split()), re.I)
        ]
        assert joined == [], f"these files call FDR family-wise: {joined}"
        for name in ("jnwb-statistics/SKILL.md", "jnwb-statistics/agents/openai.yaml"):
            assert "FDR (Benjamini-Hochberg)" in " ".join(texts[name].split()), name

    def test_the_decoding_chance_line_is_the_measured_baseline(self):
        """A chance line at 1/K overstates decoding whenever classes are unbalanced; the
        population skill's rule is the majority baseline, so every figure sentence about
        chance has to route there."""
        text = (SKILLS_DIR / "jnwb-landmark-viz" / "SKILL.md").read_text(encoding="utf-8")
        chance = [s for s in _sentence_units(text) if re.search(r"\bchance\b", s, re.I)]
        assert chance, "the figure skill no longer says where a decoding chance line goes"
        unrouted = [s for s in chance if "majority_baseline" not in s]
        assert unrouted == [], f"chance sentences that do not route to the baseline: {unrouted}"
