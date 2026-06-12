"""Validation for jnwb addresses."""

from __future__ import annotations

from src.analysis.contracts.constants import EVENT_CODE_P1_STIMULUS

from .errors import (
    BLOCKED_AREA_METADATA_MISSING,
    BLOCKED_EMPTY_EPOCHS,
    BLOCKED_SIGNAL_UNAVAILABLE,
    JnwbBlockedError,
)
from .schema import EventAddress, SignalAddress


def validate_signal_address(signal_addr: SignalAddress) -> None:
    """Validate a signal address is usable for loading."""
    if not signal_addr.sessions:
        raise JnwbBlockedError("No sessions in signal address", code=BLOCKED_SIGNAL_UNAVAILABLE)

    for skey in signal_addr.sessions:
        ids = signal_addr.ids_by_session.get(skey, [])
        if not ids:
            raise JnwbBlockedError(
                f"Session {skey} has no signal IDs",
                code=BLOCKED_SIGNAL_UNAVAILABLE,
            )


def validate_event_address(event_addr: EventAddress) -> None:
    """Validate an event address is usable for loading."""
    if event_addr.anchor == "p1" and event_addr.p1_code != EVENT_CODE_P1_STIMULUS:
        raise JnwbBlockedError(
            f"p1 anchor requires code {EVENT_CODE_P1_STIMULUS}, got {event_addr.p1_code}"
        )

    if not event_addr.events_by_session:
        raise JnwbBlockedError("No events in event address", code=BLOCKED_EMPTY_EPOCHS)

    for skey, events in event_addr.events_by_session.items():
        if not events:
            raise JnwbBlockedError(
                f"Empty events for session {skey}",
                code=BLOCKED_EMPTY_EPOCHS,
            )
        for ev in events:
            if ev.get("code") == 100:
                raise JnwbBlockedError("code100 fixation cue found in p1 events")
            if ev.get("code") != EVENT_CODE_P1_STIMULUS:
                raise JnwbBlockedError(f"Non-code101 event in p1 address: {ev.get('code')}")
