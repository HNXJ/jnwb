"""Null-scheme scan (fact S10) and RNG-report scan (fact S11)."""

from __future__ import annotations

import ast
import inspect
import re
import textwrap
from typing import Any, Callable, Dict, List, Optional, Tuple
from scripts.fact_graph.source_scans import _dotted, _final

# ------------------------------------------------------------------------ scheme scan (fact S10)

#: The draws the scheme rule reads as a null: a permutation or shuffle, the package's label
#: permutation, a circular shift (``np.roll``), a surrogate and a derangement. A sign flip (a
#: ``choice`` between -1 and +1) is the paired permutation null the docstrings name.
NULL_DRAWS = ("permutation", "shuffle", "permuted", "permute_labels", "roll", "_surrogate_source",
              "_random_derangement")
#: The keys a result names its exchangeability scheme under: ``scheme`` (label permutation),
#: ``surrogate_scheme`` (surrogates and circular shifts), ``null`` (the execution record of
#: ``jrsa``), ``null_method`` (``xflip``) and ``exchangeability_scheme`` (``coherence_bias_floor``).
SCHEME_KEYS = ("scheme", "surrogate_scheme", "null", "null_method", "exchangeability_scheme")
#: The calls whose keywords are keys of a result: ``update``, ``dict`` and a class constructor.
RESULT_CALLS = ("update", "dict")
#: The callables the scheme rule excuses, by (module, qualified name), each with its reason. A
#: listed callable that no longer draws an unnamed null is reported as stale.
S10_EXCUSED: Dict[Tuple[str, str], str] = {
    ("jnwb.wavemap", "wavemap_resolution_sweep"):
        "a unit subsample for the stability sweep: its units are returned and no null is compared",
    ("jnwb.permutation", "permute_labels"):
        "returns a bare label array: no key can be carried",
    ("jnwb.statistics._analysis", "StatisticalAnalysis.exact_sign_flip"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "exact_sign_flip"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "shuffle_pvalue_paired"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "shuffle_pvalue_unpaired"):
        "returns a bare tuple: no key can be carried",
}


def _public_callables(package: Any) -> List[Tuple[str, Any, Any]]:
    """Each callable the package exports, and each public method of an exported class, as
    (qualified name, function, owning class or None), in sorted order. An exported submodule
    is no callable and is not imported: one behind an optional extra raises on import."""
    found = []
    submodules = set(getattr(package, "SUBMODULES", ()))
    for name in sorted(set(package.__all__) - submodules):
        obj = getattr(package, name, None)
        if inspect.isclass(obj):
            for mname, meth in sorted(vars(obj).items()):
                if mname.startswith("_"):
                    continue
                fn = meth.__func__ if isinstance(meth, (staticmethod, classmethod)) else meth
                if inspect.isfunction(fn):
                    found.append((f"{name}.{mname}", fn, obj))
        elif inspect.isfunction(obj):
            found.append((name, obj, None))
    return found


def _skipped_exports(package: Any) -> List[str]:
    """Each export the callable walk does not examine: neither a class nor a function, and not a
    submodule. A constant is counted here rather than dropped without a word."""
    submodules = set(getattr(package, "SUBMODULES", ()))
    return [name for name in sorted(set(package.__all__) - submodules)
            if not inspect.isclass(getattr(package, name, None))
            and not inspect.isfunction(getattr(package, name, None))]


def _sign_flip(call: ast.Call) -> bool:
    """A ``choice`` between -1 and +1: the sign flip of a paired permutation null."""
    if _final(call.func) != "choice" or not call.args:
        return False
    options = ast.unparse(call.args[0])
    return bool(re.search(r"-1(?:\.0)?\b", options)
                and re.search(r"(?<![\w.-])1(?:\.0)?\b", options))


def _draw(call: ast.Call) -> Optional[str]:
    """The name of the null draw a call makes, or None."""
    final = _final(call.func)
    if final in NULL_DRAWS:
        return final
    return "sign flip" if _sign_flip(call) else None


def _result_keys(tree: ast.AST) -> set:
    """The string keys a body sets: dict literals, subscript stores, and the keywords of a call
    that builds a result (``RESULT_CALLS`` and capitalised constructors). A keyword of any other
    call is an argument to it, not a key of a result."""
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys |= {k.value for k in node.keys
                     if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                keys.add(node.slice.value)
        elif isinstance(node, ast.Call):
            final = _final(node.func)
            if final in RESULT_CALLS or final[:1].isupper():
                keys |= {kw.arg for kw in node.keywords if kw.arg}
    return keys


def _callee(fn: Any, dotted_name: str, owner: Any) -> Any:
    """The jnwb function a dotted callee name stands for, read through the function's module
    globals, or through its owning class for ``self.`` and ``cls.``; None for anything else."""
    head, _, rest = dotted_name.partition(".")
    if head in ("self", "cls"):
        obj = getattr(owner, rest, None) if owner is not None and rest else None
    else:
        obj = fn.__globals__.get(head)
        for part in filter(None, rest.split(".")):
            obj = getattr(obj, part, None)
    if isinstance(obj, (staticmethod, classmethod)):
        obj = obj.__func__
    module = getattr(obj, "__module__", None) or ""
    if inspect.isfunction(obj) and (module == "jnwb" or module.startswith("jnwb.")):
        return obj
    return None


def _reach(fn: Any, owner: Any, seen: set, depth: int = 0,
           draw: Callable[[ast.Call], Optional[str]] = None) -> Tuple[set, set]:
    """The draws and result keys of a function and of the jnwb functions it reaches by name.
    ``draw`` names the consuming call (``_draw`` for null draws, ``_resolver_call`` for
    randomness); the default keeps the S10 scan's behaviour. Raises OSError when the source
    cannot be read."""
    if draw is None:
        draw = _draw
    key = (fn.__module__, fn.__qualname__)
    if key in seen or depth > 8:
        return set(), set()
    seen.add(key)
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    draws, keys = set(), _result_keys(tree)
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        drawn = draw(call)
        if drawn is not None:
            draws.add(drawn)
        target = _callee(fn, _dotted(call.func), owner)
        if target is not None:
            more_draws, more_keys = _reach(target, owner, seen, depth + 1, draw)
            draws |= more_draws
            keys |= more_keys
    return draws, keys


def scheme_scan(package: Any) -> Tuple[int, List[List[str]]]:
    """How many public callables the scheme rule examined, and each that draws a null without a
    scheme key among its results (``SCHEME_KEYS``), as sorted [module.name, reason] pairs. A key
    set by a jnwb function that a callable reaches counts for that callable. A callable whose
    source cannot be read is a finding, never a pass."""
    examined, found, flagged = 0, [], set()
    for qualname, fn, owner in _public_callables(package):
        examined += 1
        try:
            draws, keys = _reach(fn, owner, set())
        except (OSError, TypeError, SyntaxError):
            found.append([f"{fn.__module__}.{qualname}", "source unreadable: not checked"])
            continue
        if not draws or keys & set(SCHEME_KEYS):
            continue
        site = (fn.__module__, qualname)
        flagged.add(site)
        if site not in S10_EXCUSED:
            found.append([f"{fn.__module__}.{qualname}",
                          f"draws {', '.join(sorted(draws))} and names no scheme key"])
    for module, qualname in sorted(S10_EXCUSED):
        if (module, qualname) not in flagged:
            found.append([f"{module}.{qualname}",
                          "S10_EXCUSED lists it, but it draws no unnamed null: stale"])
    return examined, sorted(found)


# ------------------------------------------------------------------------ rng scan (fact S11)

#: The keys a result reports the randomness it ran on under. ``surrogate_seed_entropy``
#: is the entropy that rebuilds the draws (None only when a Generator was passed in place,
#: whose position is not recoverable, or where the site documents otherwise);
#: ``xflip_surrogate_seed_entropy`` is that entropy forwarded through curation; ``seed``,
#: ``louvain_seed`` and ``umap_seed`` are the int seeds that ran; ``rng`` and
#: ``random_state`` echo the rng input (an int seed, a Generator, or None).
RNG_KEYS = ("surrogate_seed_entropy", "xflip_surrogate_seed_entropy", "seed",
            "louvain_seed", "umap_seed", "rng", "random_state")
#: The parameter names that take a generator: the ``rng`` the package resolves, the ``seed`` it
#: aliases, and scikit-learn's ``random_state`` and ``random_seed``. A name with a RNG_SUFFIXES
#: suffix takes one too, and so does a parameter annotated as one of RNG_ANNOTATIONS.
RNG_ARGUMENTS = ("rng", "seed", "random_state", "random_seed")
RNG_SUFFIXES = ("_rng", "_seed")
RNG_ANNOTATIONS = ("RNGLike", "Generator", "SeedSequence")
#: The prefix of a count parameter. A drawing call that passes the literal 0 to one draws nothing.
COUNT_PREFIX = "n_"
_POSITIONAL = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
#: The callables the rng rule excuses, by (module, qualified name), each with its reason. A
#: bare array or tuple carries no key: reshaping one to carry it is a public API choice, not
#: a repair. A listed callable that no longer consumes unnamed randomness is stale.
S11_EXCUSED: Dict[Tuple[str, str], str] = {
    ("jnwb.permutation", "permute_labels"):
        "returns a bare label array: no key can be carried",
    ("jnwb.statistics._analysis", "StatisticalAnalysis.exact_sign_flip"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "exact_sign_flip"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "shuffle_pvalue_paired"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "shuffle_pvalue_unpaired"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.viz", "resample_onsets"):
        "returns a bare onset array: no key can be carried",
}


#: The numeric factors a silent unit change scales by, in any spelling: ``1000`` and ``1e3``,
#: ``1000000`` and ``1e6``, ``0.001`` and ``1e-3``, and ``1e-6``.
UNIT_FACTORS = frozenset({1000.0, 0.001, 1000000.0, 1e-06})
#: A parameter carrying one of these suffixes names its unit, so scaling it is not silent.
UNIT_SUFFIXES = ("_ms", "_s", "_sec", "_hz", "_um", "_mm", "_uv", "_mv", "_v", "_us")
#: The callables the unit rule excuses, by (module, qualified name), each with its reason.
#: A listed callable that scales no parameter by a unit factor is reported as stale.
I2_UNIT_EXCUSED: Dict[Tuple[str, str], str] = {
    ("jnwb.laminar._vflip2", "vflip2"):
        "contact_spacing is declared in micrometres in the docstring and converted to the "
        "millimetres the computation uses; no value crosses the boundary in a changed unit",
    ("jnwb.laminar._xflip", "xflip"):
        "contact_spacing is declared in micrometres in the docstring and converted to the "
        "millimetres the computation uses; no value crosses the boundary in a changed unit",
}
#: The callables the wrapper rule excuses, by (module, qualified name), each with its reason.
#: Empty: no silent default change on the live tree is excused. A listed callable that passes
#: no literal over a default is reported as stale.
I2_WRAPPER_EXCUSED: Dict[Tuple[str, str], str] = {}
