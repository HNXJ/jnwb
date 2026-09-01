"""omission.jnwb_ext.seed -- deterministic, process-stable PRNG seed derivation.

Provides stable_seed(*args) replacing CPython's builtin hash(), which is salted
per-process by PYTHONHASHSEED and leads to non-reproducible random numbers across
separate Python interpreter runs.
"""
from __future__ import annotations

import zlib
from typing import Any


def stable_seed(*args: Any) -> int:
    """Deterministic, process-stable 31-bit integer seed from arbitrary input parts.

    Uses CRC32 over the canonical string representations of the parts.
    Stable across Python processes, platforms, and interpreter runs.
    """
    key = "|".join(str(a) for a in args).encode("utf-8")
    return zlib.crc32(key) % (2**31)
