"""The xFLIP calibration receipt must describe the estimator that ships.

`xflip_calibration_0.2.3.md` was produced under 0.2.3 with no generator, so it could not be
regenerated, and two changes had already invalidated it: 0.2.4 made `xflip` reject a
zero-variance channel rather than report its correlation as 0, and the smooth-gradient drop
gate turned out to be skipped on the `contiguous=False` path, so its null rates were
conditional on a setting it did not name. It is replaced by `xflip_calibration_0.2.5.md`
and a generator, and the receipt records a hash of the estimator; changing the estimator
without rerunning `scripts/calibrate_xflip.py` fails here.

The hash covers every top-level function, class and constant that `xflip` can reach, in any jnwb
module, not `xflip` alone. Hashing one function of an estimator is not a narrower receipt, it is one
that can be read as current while the estimator has changed -- `tests/test_vflip_calibration_receipt.py`
records where that happened.
"""

import ast
import importlib.util
import inspect
import json
import pathlib
import sys

import pytest

from jnwb import laminar
from jnwb.laminar import xflip

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
from tests.test_vflip_calibration_receipt import _with_prose_edited  # noqa: E402

RAW = ROOT / "artifacts" / "benchmarks" / "xflip_calibration_0.2.5_raw.json"
REPORT = ROOT / "artifacts" / "benchmarks" / "xflip_calibration_0.2.5.md"


def _raw():
    return json.loads(RAW.read_text(encoding="utf-8"))


def _generator():
    spec = importlib.util.spec_from_file_location(
        "calibrate_xflip", ROOT / "scripts" / "calibrate_xflip.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _top_level(module_name):
    """Top-level functions, classes and assigned names of a jnwb module, and the names it imports
    from other jnwb modules, read from the file itself rather than through the importer."""
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
            elif node.level == 0 and (node.module or "").split(".")[0] == "jnwb":
                origin = node.module
            else:
                continue
            for alias in node.names:
                imports[alias.asname or alias.name] = (origin, alias.name)
    return defined, imports


def _reachable_from_xflip():
    """The closure, recomputed here rather than taken from the generator.

    An oracle that imports the thing it checks certifies nothing, so this walk is written
    out a second time on purpose. It follows names across jnwb modules, constants included:
    the tie rule xflip counts its surrogates with lives in `jnwb.permutation`.
    """
    home = xflip.__module__  # the file that defines xflip, not the path it is imported by
    seen, reached, queue = set(), set(), [(home, "xflip")]
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


def test_receipt_and_generator_exist():
    assert (ROOT / "scripts" / "calibrate_xflip.py").is_file()
    assert RAW.is_file() and REPORT.is_file()


def test_the_receipt_without_a_generator_is_gone():
    """The defect repaired here was a receipt nobody could reproduce, not its contents."""
    for stale in ("xflip_calibration_0.2.3.md", "xflip_calibration_raw.json"):
        assert not (ROOT / "artifacts" / "benchmarks" / stale).exists(), (
            f"{stale} is a calibration receipt with no generator; it was replaced by "
            "xflip_calibration_0.2.5.md and scripts/calibrate_xflip.py"
        )


def test_receipt_was_generated_from_the_current_estimator():
    assert _raw()["estimator_sha256"] == _generator().estimator_sha256(), (
        "the estimator changed since the calibration receipt was generated; "
        "rerun `python scripts/calibrate_xflip.py`"
    )


def test_the_receipt_covers_every_helper_xflip_reaches():
    covered = {name for name, _ in _generator().estimator_sources()}
    expected = _reachable_from_xflip()

    assert "xflip" in covered
    assert covered == expected, (
        "the generator hashes a different set of functions than `xflip` reaches: "
        f"missing {sorted(expected - covered)}, extra {sorted(covered - expected)}"
    )
    for name, source in _generator().estimator_sources():
        assert source.strip(), f"{name} hashed as empty source"


@pytest.mark.parametrize("edited", ["a\n\n    b", "a  \n    b", "a\n    b  "])
def test_an_edit_inside_a_multi_line_string_literal_changes_the_receipt(monkeypatch, edited):
    """The hash rule dropped blank lines and trailing spaces everywhere, inside string
    literals too, so editing a literal's blank line left the receipt current."""
    generator = _generator()
    real = inspect.getsource
    anchor = '    gen, seed_entropy = recorded_rng(rng, "xflip")\n'

    def with_literal(body):
        def source(obj):
            text = real(obj)
            if obj is not inspect.getmodule(xflip):
                return text
            assert text.count(anchor) == 1
            return text.replace(anchor, f'    _literal = """{body}"""\n' + anchor)
        return source

    monkeypatch.setattr(inspect, "getsource", with_literal("a\n    b"))
    plain = generator.estimator_sha256()
    monkeypatch.setattr(inspect, "getsource", with_literal(edited))
    assert generator.estimator_sha256() != plain


def test_a_docstring_or_comment_edit_leaves_the_receipt_current(monkeypatch):
    """P-285: the receipt hashed comments, so a comment edit read as a changed estimator."""
    generator = _generator()
    before = generator.estimator_sha256()
    real = inspect.getsource
    assert "  # edited" in _with_prose_edited(real(inspect.getmodule(xflip)))

    monkeypatch.setattr(inspect, "getsource", lambda obj: _with_prose_edited(real(obj)))
    assert generator.estimator_sha256() == before, (
        "editing only docstrings and comments changed the receipt hash"
    )


def test_a_code_edit_changes_the_receipt(monkeypatch):
    """The hash rule must not strip code: the tie width in `jnwb.permutation` is code."""
    generator = _generator()
    before = generator.estimator_sha256()
    real = inspect.getsource
    monkeypatch.setattr(inspect, "getsource",
                        lambda obj: real(obj).replace("_TIE_RTOL = ", "_TIE_RTOL = 2 * "))
    assert generator.estimator_sha256() != before


def test_the_operating_point_is_the_shipped_default_where_it_claims_to_be():
    """`alpha` is recorded from the signature, so a changed default cannot go unnoticed."""
    assert _raw()["alpha"] == inspect.signature(xflip).parameters["alpha"].default


def test_report_is_rendered_from_the_raw_receipt():
    raw = _raw()
    report = REPORT.read_text(encoding="utf-8")
    assert raw["estimator_sha256"][:16] in report
    for name, cell in raw["nulls"].items():
        assert f"| `{name}` |" in report
        assert f"{cell['false_positive_rate']:.3f}" in report
    for row in raw["auto_count"]["rows"]:
        assert (
            f"| `{row['null']}` | `{row['contiguous']}` | {row['n_seeds']} | "
            f"{row['rate_n_blocks_None']:.3f} | {row['rate_n_blocks_2']:.3f} |"
        ) in report


def test_the_report_reads_the_gradient_row_rather_than_only_reporting_it():
    """A 0.000 acceptance rate on the gradient null invites the opposite conclusion.

    Every gradient is maximally significant under the omnibus permutation test -- median,
    min and max p all sit at the 1/(surrogates+1) floor -- and the local boundary-drop gate
    produces the rejections, not the acceptances. That gate was once skipped on the
    unrestricted path, where the same nulls were accepted 15/15. A receipt that prints the
    rate without that sentence reads as though the permutation test rejects gradients.
    """
    raw = _raw()
    grad = raw["nulls"]["smooth_spatial_gradient"]
    floor = 1.0 / (raw["n_surrogates"] + 1)

    assert grad["median_p"] == grad["min_p"] == grad["max_p"]
    assert abs(grad["median_p"] - floor) < 1e-12, (
        "the gradient null is no longer pinned at the permutation floor, so the explanation "
        "in the report no longer describes the measurement; rerun the generator"
    )
    n = raw["n_seeds"]
    assert grad["n_rejected_by_surrogates"] == 0
    assert grad["n_rejected_by_boundary_drop"] == n - round(grad["false_positive_rate"] * n)
    report = " ".join(REPORT.read_text(encoding="utf-8").split())
    assert (
        f"the local boundary-drop gate rejects {grad['n_rejected_by_boundary_drop']} of {n}"
        in report
    )
    assert "acceptance rate is produced" not in report
