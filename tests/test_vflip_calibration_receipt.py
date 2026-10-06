"""The vFLIP calibration receipt must describe the estimator that ships.

The 0.2.2 receipt was generated before the support score was density-normalized and the
crossover polarity rule changed, and no generator was kept, so its numbers described a
different estimator and could not be reproduced. The receipt records a hash of the
estimator; changing it without rerunning ``scripts/calibrate_vflip.py`` fails here.

That hash covered ``inspect.getsource(vflip)`` alone, while ``vflip`` delegates the band
normalization to ``_unit_range``. A line-count-preserving defect in that helper left the
receipt reading "current" and this file passing 4 of 4. The hash then covered the
functions of the file defining ``vflip`` only, so the device resolution it calls in
``jnwb._backend`` went unhashed, and it hashed docstrings, so a docstring edit made the
receipt stale. It now covers the code of ``vflip_from_lfp``, which the calibration runs,
and everything it reaches in any jnwb module, without docstrings or comments.
"""

import ast
import importlib.util
import inspect
import json
import pathlib

import pytest

from jnwb.laminar import vflip, vflip_from_lfp

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "artifacts" / "benchmarks" / "vflip_calibration_0.2.4_raw.json"
REPORT = ROOT / "artifacts" / "benchmarks" / "vflip_calibration_0.2.4.md"


def _refuse_constant(token):
    raise ValueError(f"{token} is not JSON; the record must be strict")


def strict_loads(text):
    """``json.loads`` that refuses NaN, Infinity and -Infinity tokens."""
    return json.loads(text, parse_constant=_refuse_constant)


def _raw():
    return strict_loads(RAW.read_text(encoding="utf-8"))


def test_the_raw_record_is_strict_json_and_states_what_null_means():
    """It held 44 bare -Infinity tokens, which a strict parser rejects."""
    raw = _raw()
    assert "null in scores or min_score = support floor, no finite score" in raw["null_score_means"]
    min_scores = [cell["min_score"] for by_val in raw["families"].values()
                  for cell in by_val.values()]
    assert None in min_scores, "no floor score left to encode; the null convention is untested"


def test_receipt_and_generator_exist():
    assert (ROOT / "scripts" / "calibrate_vflip.py").is_file()
    assert RAW.is_file() and REPORT.is_file()


def _generator():
    spec = importlib.util.spec_from_file_location(
        "calibrate_vflip", ROOT / "scripts" / "calibrate_vflip.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _top_level(module_name):
    """Top-level definitions of a jnwb module, and the names it imports from other jnwb
    modules, read from the file itself rather than through the importer."""
    path = ROOT.joinpath(*module_name.split(".")).with_suffix(".py")
    package = module_name.rpartition(".")[0]
    if not path.is_file():  # a package: its names are bound in its __init__
        path = ROOT.joinpath(*module_name.split("."), "__init__.py")
        package = module_name
    tree = ast.parse(path.read_text(encoding="utf-8"))
    defined, imports = {}, {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            defined.update({t.id: node for t in targets if isinstance(t, ast.Name)})
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1])
                origin = base + ("." + node.module if node.module else "")
            elif (node.module or "").split(".")[0] == "jnwb":
                origin = node.module
            else:
                continue
            for alias in node.names:
                imports[alias.asname or alias.name] = (origin, alias.name)
    return defined, imports


def _reachable_from_vflip_from_lfp():
    """The closure, recomputed here rather than taken from the generator."""
    home = vflip_from_lfp.__module__  # the file that defines it, not the path it is imported by
    seen, reached, queue = set(), set(), [(home, "vflip_from_lfp")]
    while queue:
        key = queue.pop(0)
        if key in seen:
            continue
        seen.add(key)
        module_name, name = key
        defined, imports = _top_level(module_name)
        if name in imports:
            queue.append(imports[name])
        elif name in defined:
            reached.add(name if module_name == home else f"{module_name}.{name}")
            for sub in ast.walk(defined[name]):
                if isinstance(sub, ast.Name):
                    queue.append((module_name, sub.id))
                elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                    queue.append((module_name, sub.func.attr))
    return reached


def test_receipt_was_generated_from_the_current_estimator():
    assert _raw()["estimator_sha256"] == _generator().estimator_sha256(), (
        "the estimator changed since the calibration receipt was generated; "
        "rerun `python scripts/calibrate_vflip.py`"
    )


def test_the_receipt_covers_everything_the_estimator_reaches():
    """The receipt has to certify the estimator, not one function or one file of it.

    Hashing `vflip` alone was not a narrower receipt, it was a receipt that could be
    read as current while the estimator had changed: recentring `_unit_range` on its own
    mean moved the median signed bias and left this file passing 4 of 4. Widening the
    hash once would not keep it wide, so the reachable set is recomputed here and
    compared against the set the generator hashes.
    """
    covered = {name for name, _ in _generator().estimator_sources()}
    expected = _reachable_from_vflip_from_lfp()

    for name in ("vflip", "vflip_from_lfp", "_unit_range", "jnwb._backend.resolve_device"):
        assert name in covered, f"the receipt does not hash {name}"
    assert covered == expected, (
        "the generator hashes a different set of definitions than `vflip_from_lfp` reaches: "
        f"missing {sorted(expected - covered)}, extra {sorted(covered - expected)}"
    )
    for name, source in _generator().estimator_sources():
        assert source.strip(), f"{name} hashed as empty source"


def _with_prose_edited(source):
    """``source`` with text added inside every docstring and a comment on every def line."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    lines = source.splitlines(keepends=True)

    def char_col(lineno, byte_col):
        return len(lines[lineno - 1].encode("utf-8")[:byte_col].decode("utf-8"))

    edits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            col = char_col(node.lineno, node.col_offset)
            text = lines[node.lineno - 1]
            quote = col
            while text[quote] not in "'\"":
                quote += 1
            width = 3 if text[quote:quote + 3] in ('"""', "'''") else 1
            edits.append((node.lineno, quote + width, "Edited. "))
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            line = lines[node.lineno - 1]
            edits.append((node.lineno, len(line.rstrip("\r\n")), "  # edited"))
    for lineno, col, text in sorted(edits, reverse=True):
        line = lines[lineno - 1]
        lines[lineno - 1] = line[:col] + text + line[col:]
    return "".join(lines)


def test_a_docstring_or_comment_edit_leaves_the_receipt_current(monkeypatch):
    """P-229: the receipt hashed docstrings, so a docstring edit read as a changed estimator."""
    generator = _generator()
    before = generator.estimator_sha256()
    real = inspect.getsource
    home = inspect.getmodule(vflip)
    assert "Edited. " in _with_prose_edited(real(home))  # the edit is not vacuous

    monkeypatch.setattr(inspect, "getsource", lambda obj: _with_prose_edited(real(obj)))
    assert generator.estimator_sha256() == before, (
        "editing only docstrings and comments changed the receipt hash"
    )


def test_a_code_edit_changes_the_receipt(monkeypatch):
    generator = _generator()
    before = generator.estimator_sha256()
    real = inspect.getsource

    def mutated(obj):
        source = real(obj)
        assert source.count("if span < 1e-12:") <= 1
        return source.replace("if span < 1e-12:", "if span < 2e-12:")

    monkeypatch.setattr(inspect, "getsource", mutated)
    assert generator.estimator_sha256() != before


def test_receipt_threshold_is_the_shipped_default():
    default = inspect.signature(vflip).parameters["min_support_score"].default
    assert _raw()["default_min_support_score"] == default


def test_report_is_rendered_from_the_raw_receipt():
    raw = _raw()
    report = REPORT.read_text(encoding="utf-8")
    assert raw["estimator_sha256"][:16] in report
    for name in ("white_noise", "ar_background", "amplitude_ramp", "parallel_bands"):
        tau = str(raw["operating"]["selected_threshold"])
        rate = raw["families"][name]["None"]["rate_curve"][tau]
        assert f"| `{name}` |" in report
        assert f"{rate:.3f}" in report
