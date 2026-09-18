"""Dict-style read access for the result dataclasses.

Several modules returned plain dicts before they returned dataclasses. Those dataclasses
kept a ``__getitem__``/``get`` pair so the older call sites keep working, and the pair was
copied verbatim into five of them.

The copies did not keep those call sites working. ``__getitem__`` was
``return getattr(self, key)``, so a missing key raised ``AttributeError``: a caller
migrated from a dict writes ``except KeyError`` and does not catch it. And with no
``__contains__`` defined, ``"method" in result`` fell back to the integer-index protocol
and called ``getattr(self, 0)`` -- ``TypeError: attribute name must be string, not
'int'``. Both are the promise in that comment going unkept, five times over.

This mixin is the one definition, and it raises what a dict raises.

Read access only. These results are records of a computation, not mappings to build, so
there is no ``__setitem__`` and no iteration; ``to_dict()`` on each class remains the way
to get a real dict.
"""

from __future__ import annotations

from typing import Any


class DictAccessMixin:
    """``result["field"]``, ``result.get("field", default)``, ``"field" in result``.

    A key is any attribute name the instance carries -- which is what the copied
    implementations accepted, so nothing that resolved before resolves differently. Only
    the behaviour on a key that does not resolve changes.
    """

    __slots__ = ()

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key) from None
        except TypeError:
            # A non-string key. `getattr` refuses to look it up; a dict would simply not
            # find it, and the caller this shim exists for wrote `except KeyError`.
            raise KeyError(key) from None

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and hasattr(self, key)
