"""The dict-style shim on the result dataclasses must fail the way a dict fails.

Five result classes carried a copied ``__getitem__``/``get`` pair whose stated purpose was
that "callers written against the older dict-returning functions in this module keep
working". The implementation was ``return getattr(self, key)``, which does not:

* a missing key raised ``AttributeError``, so ``except KeyError`` around a migrated call
  site did not catch it;
* no ``__contains__`` was defined, so ``"method" in result`` fell back to the integer
  index protocol and raised ``TypeError: attribute name must be string, not 'int'``.

The existing coverage only ever asked for keys that were present
(``tests/test_laminar.py``), which is why five copies of a broken promise survived.

These tests discover the classes statically, so a sixth one is covered the moment it
declares the mixin, and a class that goes back to its own copy fails the first test.
"""

import ast
import dataclasses
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "jnwb"
MIXIN = "DictAccessMixin"

# The body that was copied five times. Written as a normalised AST dump so reformatting
# it does not smuggle it back past this test.
COPIED_BODY = ast.dump(ast.parse("return getattr(self, key)"))


def _module_name(py: Path) -> str:
    return "jnwb." + py.relative_to(PKG).with_suffix("").as_posix().replace("/", ".")


def _declaring_classes():
    """(module, class name) for every class in jnwb/ that declares the mixin."""
    out = []
    for py in sorted(PKG.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(b, ast.Name) and b.id == MIXIN for b in node.bases
            ):
                out.append((_module_name(py), node.name))
    return out


DECLARED = _declaring_classes()


def _instance(cls):
    """A constructible instance: every required field gets None.

    None is a legitimate value for these records (a rejected fit has no exponent), and
    none of these dataclasses validates in ``__post_init__``, so this stays valid as
    fields are added.
    """
    kwargs = {
        f.name: None
        for f in dataclasses.fields(cls)
        if f.default is dataclasses.MISSING
        and f.default_factory is dataclasses.MISSING
        and f.init
    }
    return cls(**kwargs)


@pytest.fixture(scope="module", params=DECLARED, ids=lambda d: f"{d[0]}.{d[1]}")
def result(request):
    mod, name = request.param
    return _instance(getattr(importlib.import_module(mod), name))


def test_the_classes_were_found():
    """If discovery silently returns nothing, every test below passes vacuously."""
    assert len(DECLARED) >= 5, DECLARED


def test_no_class_keeps_its_own_copy_of_the_shim():
    offenders = []
    for py in sorted(PKG.rglob("*.py")):
        if "__pycache__" in py.parts or py.name == "_dictlike.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in ("__getitem__", "get"):
                continue
            if ast.dump(ast.parse(ast.unparse(node.body[-1]))) == COPIED_BODY:
                offenders.append(f"{py.relative_to(ROOT).as_posix()}:{node.lineno}")
    assert not offenders, (
        "`return getattr(self, key)` is back, and it raises AttributeError where the "
        f"caller it exists for expects KeyError: {offenders}"
    )


def test_a_missing_key_raises_keyerror(result):
    with pytest.raises(KeyError):
        result["no_such_field"]


def test_a_missing_key_is_catchable_as_a_dict_miss(result):
    """The promise in the deleted comment, stated as the thing a caller actually writes."""
    try:
        value = result["no_such_field"]
    except KeyError:
        value = "default"
    assert value == "default"


def test_a_non_string_key_is_a_miss_not_a_typeerror(result):
    with pytest.raises(KeyError):
        result[0]


def test_membership_does_not_raise(result):
    field = dataclasses.fields(type(result))[0].name
    assert field in result
    assert "no_such_field" not in result
    assert 0 not in result


def test_a_present_field_still_resolves(result):
    for f in dataclasses.fields(type(result)):
        assert result[f.name] is getattr(result, f.name)


def test_get_returns_the_stored_value_not_the_default(result):
    field = dataclasses.fields(type(result))[0].name
    assert result.get(field, "sentinel") is getattr(result, field)


def test_get_returns_the_default_on_a_miss(result):
    assert result.get("no_such_field", "sentinel") == "sentinel"
    assert result.get("no_such_field") is None


def test_the_shim_is_read_only():
    """Deliberately not a mapping: these are records, so there is no __setitem__."""
    from jnwb._dictlike import DictAccessMixin

    assert not hasattr(DictAccessMixin, "__setitem__")
    assert not hasattr(DictAccessMixin, "__iter__")
