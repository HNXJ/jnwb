"""Signature, signal-class and unit scans (facts I1, I2, I4) and wrapper defaults."""

from __future__ import annotations

import ast
import importlib
import inspect
import textwrap
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple
# Which resolver calls make a parameter stochastic is defined once, beside the resolvers,
# and read by the rng-parameter walk and by this scan alike; the reachability wrapper below
# is shared with the S10 scan.
from jnwb._rng import RESOLVERS
# The declared signal types of fact I1, read by the signature-types scan.
from jnwb import _declarations
from scripts.fact_graph.scheme_rng import COUNT_PREFIX, I2_UNIT_EXCUSED, I2_WRAPPER_EXCUSED, RNG_ANNOTATIONS, RNG_ARGUMENTS, RNG_KEYS, RNG_SUFFIXES, S11_EXCUSED, UNIT_FACTORS, UNIT_SUFFIXES, _POSITIONAL, _callee, _public_callables, _reach
from scripts.fact_graph.source_scans import _dotted, _final, _own_calls, _own_nodes

# ------------------------------------------------------------------------ signature types (fact I1)

#: The signal class each spike or LFP parameter name carries. Only these names put a
#: callable in the scan's domain: a generic name (``x``, ``signal1``, ``signals``) may take
#: either class depending on the call, so it declares nothing. Each side lists the names
#: the tree uses for it, read off the public signatures.
SIGNAL_PARAMETERS: Dict[str, str] = {
    "spike_times": "spikes",
    "spike_times1": "spikes",
    "spike_times2": "spikes",
    "spike_data": "spikes",
    "unit_spike_times": "spikes",
    "spike_waveforms": "spikes",
    "lfp": "lfp",
    "lfp_trace": "lfp",
    "lfp_data": "lfp",
    "lfp_matrix": "lfp",
    "lfp_area1": "lfp",
    "lfp_area2": "lfp",
    "lfp_phase": "lfp",
    "lfp_timestamps": "lfp",
}


def _signal_classes(parameters: set) -> Tuple[FrozenSet[str], List[str]]:
    """The signal classes a signature's parameter names show, and the sorted names that
    show them. A parameter outside ``SIGNAL_PARAMETERS`` shows none."""
    names = sorted(name for name in parameters if name in SIGNAL_PARAMETERS)
    return frozenset(SIGNAL_PARAMETERS[name] for name in names), names


def signature_types_scan(package: Any) -> Tuple[int, List[List[str]]]:
    """How many public callables the signature-types rule examined, and each whose declared
    signal contract fails (``jnwb/_declarations.py`` ``DECLARATIONS``, read here at call
    time), as sorted [module.name, reason] pairs. A callable is in the domain when a
    parameter name is in ``SIGNAL_PARAMETERS``; it fails when it declares no input class,
    declares one that misses a class its parameters show (a declaration may name more, for
    an input whose parameter name is generic), or -- both declared -- calls another public
    callable whose class is not a subset of its own. A declarations key no in-domain
    callable carries is stale. A callable whose source cannot be read is a finding, never
    a pass."""
    declarations = _declarations.DECLARATIONS
    callables = _public_callables(package)
    index = {id(fn): (qualname, owner) for qualname, fn, owner in callables}
    domain = {}
    examined, found = 0, []
    for qualname, fn, owner in callables:
        examined += 1
        try:
            parameters = set(inspect.signature(fn).parameters)
        except (TypeError, ValueError):
            found.append([f"{fn.__module__}.{qualname}", "source unreadable: not checked"])
            continue
        classes, _ = _signal_classes(parameters)
        if not classes:
            continue
        domain[(fn.__module__, qualname)] = (fn, owner, classes)
        key = f"{fn.__module__}.{qualname}"
        declared = declarations.get(key)
        if declared is None:
            found.append([key, "takes signal parameters but declares no input class"])
        elif not set(classes) <= set(declared.input_class):
            found.append([key,
                          f"declares input class {sorted(declared.input_class)} but its "
                          f"signal parameters show {sorted(classes)}"])
    domain_keys = {f"{module}.{qualname}" for module, qualname in domain}
    for key in sorted(declarations):
        # The fact I4 operations take generic inputs, so they lie outside this domain by name;
        # ``signal_class_scan`` checks their declarations. A categorized operation (its
        # ``category`` set) is read by the side-effect scans instead.
        if key not in domain_keys and key not in I4_OPERATIONS and not declarations[key].category:
            found.append([key, "DECLARATIONS lists it, but it takes no signal "
                               "parameter: stale"])
    for (module, qualname), (fn, owner, _) in sorted(domain.items()):
        declared = declarations.get(f"{module}.{qualname}")
        if declared is None:
            continue
        # A public operation reaches another through its private helpers too: the walk
        # follows every private function of the same package it calls, once each.
        queue, seen = [(fn, owner, f"{module}.{qualname}")], {id(fn)}
        while queue:
            body, body_owner, via = queue.pop()
            try:
                tree, first = _own_tree(body)
            except (OSError, TypeError, SyntaxError, ValueError):
                found.append([f"{module}.{qualname}", f"source of {via} unreadable: not checked"])
                continue
            for call in _own_calls(_own_root(tree)):
                dotted = _dotted(call.func)
                target = _public_target(body, dotted, body_owner, index)
                if target is None:
                    helper = _private_helper(body, dotted, body_owner, index)
                    if helper is not None and id(helper) not in seen:
                        seen.add(id(helper))
                        queue.append((helper, None, f"{helper.__module__}.{helper.__qualname__}"))
                    continue
                if target is fn:
                    continue
                gqualname, _ = index[id(target)]
                gkey = f"{target.__module__}.{gqualname}"
                gdeclared = declarations.get(gkey)
                if gdeclared is None:
                    continue
                if not set(gdeclared.input_class) <= set(declared.input_class):
                    found.append([f"{module}.{qualname}",
                                  f"{via} line {first + call.lineno - 1}: calls {gkey} with "
                                  f"declared class {sorted(gdeclared.input_class)} outside its "
                                  f"declared class {sorted(declared.input_class)}"])
    return examined, sorted(found)


def _private_helper(fn: Any, dotted: str, owner: Any, index: Dict[int, Any]) -> Optional[Any]:
    """The private function of ``fn``'s top-level package a dotted callee name stands for,
    resolved as ``_public_target`` resolves; None for a public callable or anything else."""
    head, _, rest = dotted.partition(".")
    if head in ("self", "cls"):
        obj = getattr(owner, rest, None) if owner is not None and rest else None
    else:
        obj = fn.__globals__.get(head)
        for part in filter(None, rest.split(".")):
            obj = getattr(obj, part, None)
    if isinstance(obj, (staticmethod, classmethod)):
        obj = obj.__func__
    if not inspect.isfunction(obj) or id(obj) in index:
        return None
    same_package = obj.__module__.split(".")[0] == fn.__module__.split(".")[0]
    return obj if same_package and obj.__name__.startswith("_") else None


def _is_unit_factor(node: ast.AST) -> bool:
    """Whether a node is a literal spelling of a unit factor: ``1000``, ``1e3``, ``0.001``,
    ``1e-3``, ``1e6``, ``1e-6`` or ``1000000``."""
    return (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool) and float(node.value) in UNIT_FACTORS)


def _declares_unit(parameters: set) -> bool:
    """Whether a function's parameters name the unit: ``units``, ``unit``, or a name ending
    in ``_unit`` or ``_units``."""
    return any(name in ("units", "unit") or name.endswith(("_unit", "_units"))
               for name in parameters)


def _own_tree(fn: Any) -> Tuple[ast.AST, int]:
    """The parsed source of ``fn`` with its first line number in its file. Raises OSError when
    the source cannot be read and SyntaxError when it does not parse."""
    lines, first = inspect.getsourcelines(fn)
    return ast.parse(textwrap.dedent("".join(lines))), first


def _own_root(tree: ast.AST) -> ast.AST:
    """The node whose own statements a scan reads: the defined function when the source holds
    one definition, else the whole tree (a callable assigned to a name)."""
    if len(tree.body) == 1 and isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        return tree.body[0]
    return tree


def _keyword_literal(node: ast.AST) -> Tuple[bool, Any]:
    """Whether a keyword value is a literal constant, or a tuple or list of them, with the
    value it carries."""
    if isinstance(node, ast.Constant):
        return True, node.value
    if isinstance(node, (ast.Tuple, ast.List)) and all(
            isinstance(elt, ast.Constant) for elt in node.elts):
        return True, tuple(elt.value for elt in node.elts)
    return False, None


def _differs(first: Any, second: Any) -> bool:
    """Whether two values differ. A comparison that does not resolve, such as an elementwise
    one over an array default, counts as different rather than silently passing."""
    try:
        return bool(first != second)
    except Exception:  # noqa: BLE001 - any unresolvable comparison is a finding
        return True


def _public_target(fn: Any, dotted: str, owner: Any, index: Dict[int, Any]) -> Optional[Any]:
    """The public callable a dotted callee name stands for, read through the function's module
    globals, or through its owning class for ``self.`` and ``cls.``; None for anything else.
    Membership in the public index decides, so a planted package resolves like the live one."""
    head, _, rest = dotted.partition(".")
    if head in ("self", "cls"):
        obj = getattr(owner, rest, None) if owner is not None and rest else None
    else:
        obj = fn.__globals__.get(head)
        for part in filter(None, rest.split(".")):
            obj = getattr(obj, part, None)
    if isinstance(obj, (staticmethod, classmethod)):
        obj = obj.__func__
    return obj if inspect.isfunction(obj) and id(obj) in index else None


def unit_scan(package: Any) -> Tuple[int, List[List[str]]]:
    """How many public callables the unit rule examined, and each that scales a parameter by
    a unit factor (``UNIT_FACTORS``, by multiplication or division) without naming the unit:
    neither the parameter's suffix (``UNIT_SUFFIXES``) nor a ``units``/``unit`` or
    ``*_unit``/``*_units`` parameter, as sorted [module.name, reason] pairs. A callable whose
    source cannot be read is a finding, never a pass."""
    examined, found, flagged = 0, [], set()
    for qualname, fn, owner in _public_callables(package):
        examined += 1
        try:
            parameters = set(inspect.signature(fn).parameters)
            tree, first = _own_tree(fn)
        except (OSError, TypeError, SyntaxError, ValueError):
            found.append([f"{fn.__module__}.{qualname}", "source unreadable: not checked"])
            continue
        if _declares_unit(parameters):
            continue
        for node in _own_nodes(_own_root(tree)):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div))):
                continue
            for side, other in ((node.left, node.right), (node.right, node.left)):
                if (isinstance(side, ast.Name) and side.id in parameters
                        and _is_unit_factor(other)
                        and not side.id.endswith(UNIT_SUFFIXES)):
                    flagged.add((fn.__module__, qualname))
                    if (fn.__module__, qualname) not in I2_UNIT_EXCUSED:
                        found.append([
                            f"{fn.__module__}.{qualname}",
                            f"line {first + node.lineno - 1}: scales parameter {side.id!r} "
                            f"by {other.value:g} and names no unit"])
    for module, qualname in sorted(I2_UNIT_EXCUSED):
        if (module, qualname) not in flagged:
            found.append([f"{module}.{qualname}",
                          "I2_UNIT_EXCUSED lists it, but it scales no parameter "
                          "by a unit factor: stale"])
    return examined, sorted(found)


def wrapper_scan(package: Any) -> Tuple[int, List[List[str]]]:
    """How many public callables the wrapper rule examined, and each that calls another public
    callable with a literal keyword (an ``ast.Constant``, or a tuple or list of them) its own
    signature does not name, differing from that keyword's default, as sorted [module.name,
    reason] pairs. A callable whose source cannot be read is a finding, never a pass."""
    callables = _public_callables(package)
    index = {id(fn): (qualname, owner) for qualname, fn, owner in callables}
    examined, found, flagged = 0, [], set()
    for qualname, fn, owner in callables:
        examined += 1
        try:
            own = set(inspect.signature(fn).parameters)
            tree, first = _own_tree(fn)
        except (OSError, TypeError, SyntaxError, ValueError):
            found.append([f"{fn.__module__}.{qualname}", "source unreadable: not checked"])
            continue
        for call in _own_calls(_own_root(tree)):
            target = _public_target(fn, _dotted(call.func), owner, index)
            if target is None or target is fn:
                continue
            gqualname, _ = index[id(target)]
            defaults = inspect.signature(target).parameters
            for keyword in call.keywords:
                if not keyword.arg or keyword.arg in own:
                    continue
                gparam = defaults.get(keyword.arg)
                if gparam is None or gparam.default is inspect.Parameter.empty:
                    continue
                literal, value = _keyword_literal(keyword.value)
                if not literal or not _differs(value, gparam.default):
                    continue
                site = (fn.__module__, qualname)
                flagged.add(site)
                if site not in I2_WRAPPER_EXCUSED:
                    found.append([
                        f"{fn.__module__}.{qualname}",
                        f"line {first + call.lineno - 1}: passes {keyword.arg}={value!r} "
                        f"to {target.__module__}.{gqualname}, "
                        f"whose default is {gparam.default!r}"])
    for module, qualname in sorted(I2_WRAPPER_EXCUSED):
        if (module, qualname) not in flagged:
            found.append([f"{module}.{qualname}",
                          "I2_WRAPPER_EXCUSED lists it, but it passes no literal "
                          "over a default: stale"])
    return examined, sorted(found)


def _unwalked_callables(package: Any) -> List[Tuple[str, Any, Any]]:
    """What ``_public_callables`` leaves out, in its form: each public method an exported class
    inherits from a class of the same package rather than defines, and each callable export
    that is neither a function nor a class (a ``functools.partial``, a callable instance)."""
    found = []
    submodules = set(getattr(package, "SUBMODULES", ()))
    top = getattr(package, "__name__", "").split(".")[0]
    for name in sorted(set(package.__all__) - submodules):
        obj = getattr(package, name, None)
        if inspect.isclass(obj):
            for base in obj.__mro__[1:]:
                if base.__module__.split(".")[0] != top:
                    continue
                for mname, meth in sorted(vars(base).items()):
                    if mname.startswith("_") or mname in vars(obj):
                        continue
                    fn = meth.__func__ if isinstance(meth, (staticmethod, classmethod)) else meth
                    if inspect.isfunction(fn) and not any(
                            mname in vars(b) for b in obj.__mro__[1:obj.__mro__.index(base)]):
                        found.append((f"{name}.{mname}", fn, obj))
        elif callable(obj) and not inspect.isfunction(obj):
            found.append((name, obj, None))
    return found


def choice_default_scan(package: Any, names: Sequence[str],
                        exceptions: Sequence[Dict[str, str]]) -> Tuple[int, List[List[str]]]:
    """How many public callables the B3 rule examined, and each with a defaulted parameter
    whose name is in the choice-name lexicon ``names``, as sorted [module.name, reason] pairs.
    A ``window`` whose default is a string names a taper, not a time span, and sits outside
    the lexicon. A row of ``exceptions`` whose Operation is the callable's ``module.qualname``
    or its bare qualname, and whose Parameter is the parameter's name, keeps the default. A
    callable whose signature cannot be read is a finding, never a pass, and a row that matches
    no defaulted lexicon parameter is reported as stale."""
    lexicon, excused = set(names), {(row["Operation"], row["Parameter"]) for row in exceptions}
    examined, found, defaulted = 0, [], set()
    for qualname, fn, owner in _public_callables(package) + _unwalked_callables(package):
        examined += 1
        key = f"{getattr(fn, '__module__', None) or getattr(package, '__name__', '')}.{qualname}"
        if not (inspect.isfunction(fn) or inspect.ismethod(fn)):
            found.append([key, f"a {type(fn).__name__}, not a function: not checked"])
            continue
        try:
            parameters = inspect.signature(fn).parameters
        except (TypeError, ValueError):
            found.append([key, "signature unreadable: not checked"])
            continue
        for pname, parameter in parameters.items():
            if pname not in lexicon or parameter.default is inspect.Parameter.empty:
                continue
            if pname == "window" and isinstance(parameter.default, str):
                continue
            defaulted.add((key, pname))
            defaulted.add((qualname, pname))
            if (key, pname) in excused or (qualname, pname) in excused:
                continue
            found.append([key, f"parameter {pname!r} defaults to {parameter.default!r}"])
    for operation, pname in sorted(excused):
        if (operation, pname) not in defaulted:
            found.append([operation,
                          f"the exceptions table names {pname!r} of {operation}, "
                          "which no defaulted lexicon parameter matches: stale"])
    return examined, sorted(found)


def _resolver_call(call: ast.Call) -> Optional[str]:
    """The name of the rng resolver a call reaches for (``RESOLVERS`` of the rng-parameter
    walk), or None. The walk defines which parameters are stochastic by use; the scan reads
    its rule table rather than retyping it."""
    final = _final(call.func)
    return final if final in RESOLVERS else None


def _generator_name(name: str) -> bool:
    """Whether a parameter name takes a generator: one of ``RNG_ARGUMENTS``, or a ``RNG_SUFFIXES``
    suffix."""
    return name in RNG_ARGUMENTS or name.endswith(RNG_SUFFIXES)


def _generator_parameter(param: inspect.Parameter) -> bool:
    """Whether a callee's parameter takes a generator, by its name or by its annotation."""
    if _generator_name(param.name):
        return True
    annotation = param.annotation
    if annotation is inspect.Parameter.empty:
        return False
    text = annotation if isinstance(annotation, str) else inspect.formatannotation(annotation)
    return any(word in text for word in RNG_ANNOTATIONS)


def _callee_parameters(dotted: str, target: Any) -> List[inspect.Parameter]:
    """The parameters of ``target`` as a call through ``dotted`` sees them: without ``self`` or
    ``cls`` when the call goes through one."""
    params = list(inspect.signature(target).parameters.values())
    return params[1:] if dotted.partition(".")[0] in ("self", "cls") else params


def _passes_rng(call: ast.Call, dotted: str, target: Any) -> bool:
    """Whether a call hands ``target`` a generator: by keyword, or positionally into one of its
    generator parameters. ``*`` and ``**`` arguments are not seen into, so they count as passing;
    a callee with no generator parameter cannot be passed one, so a call to it passes none."""
    if (any(kw.arg is None for kw in call.keywords)
            or any(isinstance(arg, ast.Starred) for arg in call.args)):
        return True
    params = _callee_parameters(dotted, target)
    named = {param.name for param in params if _generator_parameter(param)}
    if any(kw.arg in named or _generator_name(kw.arg) for kw in call.keywords):
        return True
    positional = [param for param in params if param.kind in _POSITIONAL]
    return any(index < len(call.args) and _generator_parameter(param)
               for index, param in enumerate(positional))


def _is_literal_zero(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is int and node.value == 0


def _count_is_zero(call: ast.Call, dotted: str, target: Any) -> bool:
    """Whether a call passes the literal 0 to a count parameter (one named with ``COUNT_PREFIX``),
    so the callee draws nothing on that call."""
    if any(kw.arg and kw.arg.startswith(COUNT_PREFIX) and _is_literal_zero(kw.value)
           for kw in call.keywords):
        return True
    positional = [param for param in _callee_parameters(dotted, target)
                  if param.kind in _POSITIONAL]
    return any(index < len(call.args) and param.name.startswith(COUNT_PREFIX)
               and _is_literal_zero(call.args[index])
               for index, param in enumerate(positional))


def _unnamed_rng_calls(fn: Any, owner: Any, seen: set, depth: int = 0) -> set:
    """The (caller, callee) pairs where ``fn``, or a jnwb function it reaches by name, calls a
    jnwb function that consumes randomness and is passed no generator (``_passes_rng``). A call
    with a literal 0 count draws nothing, so it is neither flagged nor followed
    (``_count_is_zero``). A resolver call is a draw itself, not a callee, so it is not walked."""
    key = (fn.__module__, fn.__qualname__)
    if key in seen or depth > 8:
        return set()
    seen.add(key)
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    found = set()
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if _resolver_call(call) is not None:
            continue
        dotted = _dotted(call.func)
        target = _callee(fn, dotted, owner)
        if target is None or _count_is_zero(call, dotted, target):
            continue
        if not _passes_rng(call, dotted, target) and _reach(
                target, owner, set(), draw=_resolver_call)[0]:
            found.add((fn.__qualname__, dotted))
        found |= _unnamed_rng_calls(target, owner, seen, depth + 1)
    return found


def rng_scan(package: Any) -> Tuple[int, List[List[str]]]:
    """How many public callables the rng rule examined, and each that consumes randomness
    without an rng key among its results (``RNG_KEYS``), or that reaches a jnwb function which
    consumes randomness through a call passed no generator (``_unnamed_rng_calls``), as sorted
    [module.name, reason] pairs. A key set by a jnwb function that a callable reaches counts for
    that callable, so forwarders whose target reports are not findings. A callable whose source
    cannot be read is a finding, never a pass."""
    examined, found, flagged = 0, [], set()
    for qualname, fn, owner in _public_callables(package):
        examined += 1
        try:
            draws, keys = _reach(fn, owner, set(), draw=_resolver_call)
            unnamed = _unnamed_rng_calls(fn, owner, set())
        except (OSError, TypeError, SyntaxError):
            found.append([f"{fn.__module__}.{qualname}", "source unreadable: not checked"])
            continue
        reasons = []
        if draws and not keys & set(RNG_KEYS):
            reasons.append(f"consumes randomness ({', '.join(sorted(draws))}) "
                           "and reports no rng key")
        if unnamed:
            reasons.append("calls a drawing function with no rng argument: " + ", ".join(
                f"{caller} calls {callee}" for caller, callee in sorted(unnamed)))
        if not reasons:
            continue
        site = (fn.__module__, qualname)
        flagged.add(site)
        if site not in S11_EXCUSED:
            found.append([f"{fn.__module__}.{qualname}", "; ".join(reasons)])
    for module, qualname in sorted(S11_EXCUSED):
        if (module, qualname) not in flagged:
            found.append([f"{module}.{qualname}",
                          "S11_EXCUSED lists it, but it consumes no unnamed randomness: stale"])
    return examined, sorted(found)


# ------------------------------------------------------------------------ signal class (fact I4)

#: The operations fact I4 names. Each takes inputs of either signal class, so it carries a
#: keyword-only ``signal_class`` and a declaration in ``jnwb/_declarations.py``. Keys are
#: ``module.qualname``, as in ``DECLARATIONS``.
I4_OPERATIONS: Tuple[str, ...] = (
    "jnwb.connectivity._granger.granger",
    "jnwb.connectivity._network.directed_network",
    "jnwb.spectral._coupling.imaginary_coherency",
)


def signal_class_scan() -> Tuple[int, List[List[str]]]:
    """How many named operations the signal-class rule examined, and each that fails it, as
    sorted [module.qualname, reason] pairs. An operation fails when its live signature has no
    keyword-only ``signal_class``, when ``DECLARATIONS`` holds no entry for it, or when it cannot
    be read. The callable is looked up at call time, so a stand-in is the one checked."""
    examined, found = 0, []
    for key in I4_OPERATIONS:
        examined += 1
        module_name, _, qualname = key.rpartition(".")
        try:
            fn = getattr(importlib.import_module(module_name), qualname)
            parameter = inspect.signature(fn).parameters.get("signal_class")
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            found.append([key, f"not readable: {exc}"])
            continue
        if parameter is None or parameter.kind is not inspect.Parameter.KEYWORD_ONLY:
            found.append([key, "signature has no keyword-only signal_class"])
        if key not in _declarations.DECLARATIONS:
            found.append([key, "declares no input class in jnwb/_declarations.py"])
    return examined, sorted(found)
