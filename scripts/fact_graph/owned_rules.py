"""Owned-rule scan: registered signature expressions outside their owner."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Sequence, Tuple
from scripts.fact_graph.source_scans import _bindings, _final, _target

# ----------------------------------------------------------------------- owned rules

#: Each rule with its owner (module path, qualified name) and the signature expression the scan
#: matches; that expression outside its owner is a retyped rule.
OWNED_RULES: Tuple[Tuple[str, str, str, str], ...] = (
    ("dB aggregation", "jnwb/spectral/_decibels.py", "aggregate_to_db",
     "10 * log10 of an average, or to_db of an average"),
    ("R2", "jnwb/_spread.py", "r_squared", "1 - A / B"),
    ("robust z, MAD with a mean-absolute-deviation fallback", "jnwb/artifact_detection.py",
     "_robust_z_zero_fallback", "a MAD scale and mean(abs(d)) * 1.253314 in one function"),
    ("robust z, MAD with a standard-deviation fallback", "jnwb/laminar_curation.py",
     "_robust_z_std_fallback", "a MAD scale and a standard deviation in one function"),
    ("FDR", "jnwb/statistics/_analysis.py", "StatisticalAnalysis.fdr_correct",
     "false_discovery_control(...)"),
    ("Clopper-Pearson", "jnwb/statistics/_tests.py", "clopper_pearson",
     "beta.ppf whose first argument divides by 2"),
    ("percentile bootstrap", "jnwb/_spread.py", "percentile_interval",
     "a percentile interval: two levels in a list, or two calls on one array"),
    ("robust z, MAD with an absolute floor of 1e-9", "jnwb/artifact_repair.py",
     "_floored_robust_z", "a MAD scale floored by np.where(s < 1e-9, 1e-9, s)"),
    ("robust z, pooled MAD scale, zero-guarded at the call site", "jnwb/artifact_repair.py",
     "_pooled_robust_z", "a residual over 1.4826 * scale"),
    ("modified z, 0.6745 over the median deviation", "jnwb/unit_quality.py",
     "_modified_z", "0.6745 * deviation over the median of the deviation"),
)
#: R2 matches that are not a coefficient of determination, each read by hand:
#: (module path, enclosing function, expression text) -> reason.
R2_EXEMPT: Dict[Tuple[str, str, str], str] = {
    ("scripts/figures/generate_figures.py", "_inches_axes", "1 - (top + height) / h"):
        "the figure fraction of an axes' bottom edge, measured from the top",
    ("jnwb/jrsa/_inference.py", "_one_sided_parametric_p", "1.0 - p2 / 2.0"):
        "the one-sided p-value on the side away from the effect",
    ("jnwb/statistics/_tests.py", "clopper_pearson", "1.0 - alpha / 2.0"):
        "the upper Beta quantile of the Clopper-Pearson interval",
    ("jnwb/testing/synth.py", "synth_laminar_motif",
     "1.0 - (ch - c_crossover) / max(n_channels - 1 - c_crossover, 1.0)"):
        "a linear weight across the channels of a synthetic laminar profile",
    ("jnwb/unit_quality.py", "refractory_contamination",
     "1.0 - 2.0 * n_v * total / ((tau_r - tau_c) * n * n)"):
        "the discriminant of the quadratic in the refractory-period contamination estimate",
    ("jnwb/vis/canvas.py", "PlotlyPublicationCanvas._compute_domains",
     "1.0 - row_y_top_px[r] / H"):
        "a plotly domain coordinate of a row's top edge",
    ("jnwb/vis/canvas.py", "PlotlyPublicationCanvas._compute_domains",
     "1.0 - (row_y_top_px[r] + row_heights_px[r]) / H"):
        "a plotly domain coordinate of a row's bottom edge",
}
#: Percentile intervals that are not bootstraps, each read by hand, keyed as R2_EXEMPT.
PERCENTILE_EXEMPT: Dict[Tuple[str, str, str], str] = {
    ("jnwb/statistics/_regression.py", "shuffle_r2_ci", "np.percentile(null, 2.5)"):
        "a shuffle null interval, not a bootstrap",
    ("jnwb/statistics/_regression.py", "shuffle_r2_ci", "np.percentile(null, 97.5)"):
        "a shuffle null interval, not a bootstrap",
}
REVIEWED_EXEMPT: Dict[str, Dict[Tuple[str, str, str], str]] = {
    "R2": R2_EXEMPT,
    "percentile bootstrap": PERCENTILE_EXEMPT,
}
#: Modules whose figure functions are read: the docs figure generators and the plotting modules.
FIGURE_FILES = ("scripts/figures/generate_figures.py", "jnwb/visual_qc.py")
FIGURE_TREES = ("jnwb/vis/",)
#: Code the scan reads, as (tree prefix, suffix): the package, the docs figure modules, the examples
#: (scripts and notebooks) and the skills' python fences.
OWNED_SCOPE = (("jnwb/", ".py"), ("docs/", ".py"), ("scripts/figures/", ".py"), ("examples/", ".py"),
               ("examples/", ".ipynb"), ("skills/", ".md"))
_PYTHON_FENCE = re.compile(r"^```python[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
_MAGIC_LINE = re.compile(r"^\s*[%!]")
_AVERAGING = ("mean", "nanmean", "average")
_PERCENTILES = ("percentile", "nanpercentile")
_MAD = ("median", "nanmedian")
_MEAN_AD = ("mean", "nanmean")
_SD = ("std", "nanstd")


def _is_number(node: ast.AST, values: Tuple[float, ...]) -> bool:
    return (isinstance(node, ast.Constant) and not isinstance(node.value, bool)
            and node.value in values)


def _scopes(tree: ast.AST) -> Dict[ast.AST, str]:
    """Each node's innermost enclosing function or class, by qualified name (``""`` at module
    level)."""
    scope: Dict[ast.AST, str] = {}

    def visit(node: ast.AST, qualname: str) -> None:
        for child in ast.iter_child_nodes(node):
            scope[child] = qualname
            inner = qualname
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                inner = f"{qualname}.{child.name}" if qualname else child.name
            visit(child, inner)

    visit(tree, "")
    return scope


def _averages(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Call) and _final(n.func) in _AVERAGING for n in ast.walk(node))


def _statistic_of_abs(node: ast.AST, statistics: Tuple[str, ...], constant: float,
                      name: str) -> bool:
    """Whether ``node`` is ``statistic(abs(...)) * scale``, the scale being ``constant`` or the
    name ``name``."""
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult)):
        return False
    for call, scale in ((node.left, node.right), (node.right, node.left)):
        if (isinstance(call, ast.Call) and _final(call.func) in statistics and call.args
                and any(isinstance(n, ast.Call) and _final(n.func) == "abs"
                        for n in ast.walk(call.args[0]))
                and (_is_number(scale, (constant,))
                     or (isinstance(scale, ast.Name) and scale.id == name))):
            return True
    return False


def _db_nodes(tree: ast.AST, parents: Dict[ast.AST, ast.AST]):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        times = parents.get(node)
        if _final(node.func) == "to_db" and _averages(node.args[0]):
            yield node
        elif (_final(node.func) == "log10" and _averages(node.args[0])
              and isinstance(times, ast.BinOp) and isinstance(times.op, ast.Mult)
              and (_is_number(times.left, (10, 20)) or _is_number(times.right, (10, 20)))):
            yield node


def _r2_nodes(tree: ast.AST):
    for node in ast.walk(tree):
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub)
                and _is_number(node.left, (1,))
                and isinstance(node.right, ast.BinOp) and isinstance(node.right.op, ast.Div)):
            yield node


def _mad_scopes(tree: ast.AST, scope: Dict[ast.AST, str]) -> set:
    """The functions that take a MAD scale, read as ``median(abs(d)) * 1.4826``."""
    return {scope.get(node, "") for node in ast.walk(tree)
            if _statistic_of_abs(node, _MAD, 1.4826, "MAD_SCALE")}


def _robust_z_nodes(tree: ast.AST, scope: Dict[ast.AST, str]):
    """The fallbacks of a robust z: the mean-absolute-deviation scale and a standard deviation,
    read in a function that also takes a MAD scale."""
    mad_scopes = _mad_scopes(tree, scope)
    for node in ast.walk(tree):
        if scope.get(node, "") not in mad_scopes:
            continue
        if _statistic_of_abs(node, _MEAN_AD, 1.253314, "MEAN_AD_SCALE"):
            yield node, "robust z, MAD with a mean-absolute-deviation fallback"
        elif isinstance(node, ast.Call) and _final(node.func) in _SD:
            yield node, "robust z, MAD with a standard-deviation fallback"


def _floor_nodes(tree: ast.AST, scope: Dict[ast.AST, str]):
    """The 1e-9 floor of a MAD scale, ``np.where(s < 1e-9, 1e-9, s)``, in a function that
    takes one."""
    mad_scopes = _mad_scopes(tree, scope)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _final(node.func) == "where" and len(node.args) == 3
                and scope.get(node, "") in mad_scopes):
            continue
        test, floor, kept = node.args
        if (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Lt)
                and _is_number(test.comparators[0], (1e-9,)) and _is_number(floor, (1e-9,))
                and ast.unparse(kept) == ast.unparse(test.left)):
            yield node


def _pooled_nodes(tree: ast.AST):
    """A residual over ``1.4826 * scale``: the normal-consistent MAD of a pooled scale."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                and isinstance(node.right, ast.BinOp) and isinstance(node.right.op, ast.Mult)
                and (_is_number(node.right.left, (1.4826,))
                     or _is_number(node.right.right, (1.4826,)))):
            yield node


def _modified_nodes(tree: ast.AST):
    """``0.6745 * d / median(d)``: the modified z-score of a deviation, with no fallback."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                and isinstance(node.left, ast.BinOp) and isinstance(node.left.op, ast.Mult)
                and (_is_number(node.left.left, (0.6745,))
                     or _is_number(node.left.right, (0.6745,)))
                and isinstance(node.right, ast.Call) and _final(node.right.func) in _MAD):
            yield node


def _owned_nodes(source: str) -> List[Tuple[int, str, str, str]]:
    """Each node in one module that matches a registered expression, as (line, enclosing
    function, rule, expression text), before owners and exemptions are removed."""
    tree = ast.parse(source)
    bound = _bindings(tree)
    scope = _scopes(tree)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    found = [(node, "dB aggregation") for node in _db_nodes(tree, parents)]
    found += [(node, "R2") for node in _r2_nodes(tree)]
    found += list(_robust_z_nodes(tree, scope))
    found += [(node, "robust z, MAD with an absolute floor of 1e-9")
              for node in _floor_nodes(tree, scope)]
    found += [(node, "robust z, pooled MAD scale, zero-guarded at the call site")
              for node in _pooled_nodes(tree)]
    found += [(node, "modified z, 0.6745 over the median deviation")
              for node in _modified_nodes(tree)]
    found += [(node, "FDR") for node in ast.walk(tree)
              if isinstance(node, ast.Call) and _target(node.func, bound).endswith(
                  "false_discovery_control")]
    found += [(node, "Clopper-Pearson") for node in ast.walk(tree)
              if isinstance(node, ast.Call) and node.args
              and _target(node.func, bound).endswith("beta.ppf")
              and any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)
                      and _is_number(n.right, (2,)) for n in ast.walk(node.args[0]))]
    pairs: Dict[Tuple[str, str], List[ast.AST]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _final(node.func) in _PERCENTILES
                and len(node.args) >= 2):
            continue
        if isinstance(node.args[1], (ast.List, ast.Tuple)):
            if len(node.args[1].elts) == 2:
                found.append((node, "percentile bootstrap"))
        else:
            pairs.setdefault((scope.get(node, ""), ast.unparse(node.args[0])), []).append(node)
    found += [(node, "percentile bootstrap") for group in pairs.values()
              if len(group) >= 2 for node in group]
    return [(node.lineno, scope.get(node, ""), rule, ast.unparse(node)) for node, rule in found]


def owned_rule_sites(path: str, source: str) -> List[str]:
    """Reasons for each registered expression in one module that sits outside its owner and is
    not a reviewed exemption. Raises ``SyntaxError`` on source it cannot parse."""
    owners = {rule: (owner, name) for rule, owner, name, _ in OWNED_RULES}
    reasons = []
    for line, function, rule, text in sorted(_owned_nodes(source)):
        owner, name = owners[rule]
        if (path, function) == (owner, name):
            continue
        if (path, function, text) in REVIEWED_EXEMPT.get(rule, {}):
            continue
        reasons.append(f"line {line}: {function or '<module>'} evaluates {rule} ({text}) "
                       f"outside its owner {owner}:{name}")
    return reasons


def _owned_units(rel: str, text: str) -> List[Tuple[str, str]]:
    """Python sources of one tracked file, each with the prefix its reasons carry: the file,
    each notebook code cell, or each skill python fence."""
    if rel.endswith(".py"):
        return [("", text)]
    if rel.endswith(".ipynb"):
        units = []
        for index, cell in enumerate(json.loads(text)["cells"], 1):
            if cell.get("cell_type") == "code":
                lines = "".join(cell["source"]).splitlines()
                units.append((f"cell {index}, ", "\n".join(
                    line for line in lines if not _MAGIC_LINE.match(line))))
        return units
    return [(f"fence {index}, ", match.group(1))
            for index, match in enumerate(_PYTHON_FENCE.finditer(text), 1)]


def owned_rule_scans(root: Path, tracked: Sequence[str]) -> Tuple[Dict[str, int],
                                                                  Dict[str, List[List[str]]]]:
    """Violations as sorted [file, reason] pairs under ``owned_rules`` and ``figure_owner_calls``,
    and what was examined: python units and figure functions. A unit that cannot be read or
    parsed is a violation, not a skip."""
    examined = {"units": 0, "figure_functions": 0}
    owned: List[List[str]] = []
    figures: List[List[str]] = []
    for rel in tracked:
        if not any(rel.startswith(prefix) and rel.endswith(suffix)
                   for prefix, suffix in OWNED_SCOPE):
            continue
        figure = rel in FIGURE_FILES or rel.startswith(FIGURE_TREES)
        try:
            units = _owned_units(rel, (root / rel).read_text(encoding="utf-8"))
        except (ValueError, KeyError) as error:
            owned.append([rel, f"cannot be read ({error})"])
            continue
        for prefix, source in units:
            try:
                reasons = owned_rule_sites(rel, source)
                functions = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                                for n in ast.walk(ast.parse(source))) if figure else 0
            except SyntaxError as error:
                owned.append([rel, f"{prefix}cannot be parsed ({error.msg})"])
                continue
            examined["units"] += 1
            examined["figure_functions"] += functions
            owned.extend([rel, f"{prefix}{reason}"] for reason in reasons)
            if figure:
                figures.extend([rel, f"{prefix}{reason}"] for reason in reasons)
    return examined, {"owned_rules": sorted(owned), "figure_owner_calls": sorted(figures)}
