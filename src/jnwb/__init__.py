"""jnwb: lightweight NWB data-address layer for omission analysis."""

from .artifacts import load_epoch_artifact, save_epoch_artifact
from .backends import to_backend
from .epochs import load_epochs
from .files import build_session_manifest, inspect_nwb, list_nwb_files
from .qc import validate_event_address, validate_signal_address
from .schema import EpochBatch, EpochSpec, EventAddress, NWBFileRecord, SignalAddress
from .signals import address_signals
from .task import address_events, omission_offset_ms

__all__ = [
    "NWBFileRecord",
    "SignalAddress",
    "EventAddress",
    "EpochSpec",
    "EpochBatch",
    "list_nwb_files",
    "inspect_nwb",
    "build_session_manifest",
    "address_signals",
    "address_events",
    "omission_offset_ms",
    "load_epochs",
    "save_epoch_artifact",
    "load_epoch_artifact",
    "validate_signal_address",
    "validate_event_address",
    "to_backend",
]
