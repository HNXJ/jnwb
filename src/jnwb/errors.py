"""Typed errors and blockers for jnwb."""

from __future__ import annotations


class JnwbError(RuntimeError):
    """Base error for jnwb operations."""

    code: str = "JNWB_ERROR"

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        self.details = details or {}
        if code is not None:
            self.code = code
        super().__init__(f"{self.code}: {message}")


class JnwbBlockedError(JnwbError):
    """Operation blocked with a typed code."""

    code = "BLOCKED"


BLOCKED_BACKEND_CUPY_UNAVAILABLE = "BLOCKED_BACKEND_CUPY_UNAVAILABLE"
BLOCKED_BACKEND_JAX_UNAVAILABLE = "BLOCKED_BACKEND_JAX_UNAVAILABLE"
BLOCKED_SIGNAL_UNAVAILABLE = "BLOCKED_SIGNAL_UNAVAILABLE"
BLOCKED_EMPTY_EPOCHS = "BLOCKED_EMPTY_EPOCHS"
BLOCKED_AREA_METADATA_MISSING = "BLOCKED_AREA_METADATA_MISSING"
BLOCKED_SESSION_SILENTLY_DROPPED = "BLOCKED_SESSION_SILENTLY_DROPPED"
BLOCKED_EVENTS_TABLE_MISSING = "BLOCKED_EVENTS_TABLE_MISSING"
BLOCKED_NO_EVENTS = "BLOCKED_NO_EVENTS"
BLOCKED_PYNWB_UNAVAILABLE = "BLOCKED_PYNWB_UNAVAILABLE"
