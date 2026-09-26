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

import warnings
from typing import Any, Mapping


class RenamedKeyDict(dict):
    """A result dict whose renamed or changing keys warn when they are read.

    ``aliases`` maps each old name to its current one. The old names are not keys:
    iteration, ``len``, ``keys()`` and equality see the current names only, so a caller
    that copies the dict gets the current shape. Reading an old name with ``[]`` or
    ``get`` returns the current key's value and emits a ``DeprecationWarning``; ``in``
    answers True for it, so an existing membership check keeps its branch.

    ``changing`` maps a present key whose meaning changes in the next release to the
    message that says how. Reading it with ``[]`` or ``get`` returns its current value
    and emits that message as a ``FutureWarning``.

    Every warning points at the line that read the key.
    """

    def __init__(self, data: Mapping[str, Any], aliases: Mapping[str, str] = (),
                 changing: Mapping[str, str] = ()):
        super().__init__(data)
        aliases, changing = dict(aliases), dict(changing)
        missing = [k for k in (*aliases.values(), *changing) if not dict.__contains__(self, k)]
        if missing:
            raise KeyError(f"keys named by aliases or changing are absent: {missing}")
        self._aliases = aliases
        self._changing = changing

    def _read(self, key: object, stacklevel: int) -> Any:
        """The value for ``key``, warning as the key requires; ``stacklevel`` counts this frame."""
        if dict.__contains__(self, key):
            if key in self._changing:
                warnings.warn(self._changing[key], FutureWarning, stacklevel=stacklevel)
            return dict.__getitem__(self, key)
        if isinstance(key, str) and key in self._aliases:
            new = self._aliases[key]
            warnings.warn(
                f"result key {key!r} is deprecated and will be removed in the next release; "
                f"read {new!r}.",
                DeprecationWarning,
                stacklevel=stacklevel,
            )
            return dict.__getitem__(self, new)
        raise KeyError(key)

    def __getitem__(self, key: object) -> Any:
        return self._read(key, stacklevel=3)

    def get(self, key: object, default: Any = None) -> Any:
        try:
            return self._read(key, stacklevel=3)
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        return dict.__contains__(self, key) or (isinstance(key, str) and key in self._aliases)


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
