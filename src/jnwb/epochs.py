"""Epoch loading from addressed signals and events."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import Iterable

import numpy as np
import pandas as pd

from .backends import to_backend
from .errors import BLOCKED_EMPTY_EPOCHS, BLOCKED_SESSION_SILENTLY_DROPPED, JnwbBlockedError
from .files import NWBFileRecord, _require_pynwb, session_key_from_record
from .schema import EpochBatch, EpochSpec, EventAddress, SignalAddress


def _bin_edges(window_ms: tuple[int, int], bin_ms: float) -> tuple[np.ndarray, np.ndarray]:
    pre_ms, post_ms = window_ms
    edges = np.arange(pre_ms, post_ms + bin_ms, bin_ms)
    centers = (edges[:-1] + edges[1:]) / 2.0
    return edges, centers


def _extract_spk_epoch(
    units_table,
    unit_indices: list[int],
    event_times_s: np.ndarray,
    window_ms: tuple[int, int],
    bin_ms: float,
) -> np.ndarray:
    edges, _ = _bin_edges(window_ms, bin_ms)
    pre_ms, post_ms = window_ms
    n_trials = len(event_times_s)
    n_units = len(unit_indices)
    n_bins = len(edges) - 1
    out = np.zeros((n_trials, n_units, n_bins), dtype=np.float32)

    for t_idx, onset_s in enumerate(event_times_s):
        onset_ms = float(onset_s) * 1000.0
        for u_idx, unit_row in enumerate(unit_indices):
            spike_times = units_table["spike_times"][unit_row]
            if hasattr(spike_times, "data"):
                spike_times = np.asarray(spike_times.data[:])
            else:
                spike_times = np.asarray(spike_times)
            aligned_ms = spike_times * 1000.0 - onset_ms
            in_window = (aligned_ms >= pre_ms) & (aligned_ms < post_ms)
            if in_window.any():
                counts, _ = np.histogram(aligned_ms[in_window], bins=edges)
                out[t_idx, u_idx, :] = counts.astype(np.float32)
    return out


def _unit_row_indices(units_table, unit_ids: list[str | int]) -> list[int]:
    unit_cols = list(units_table.colnames)
    indices: list[int] = []
    for uid in unit_ids:
        if isinstance(uid, int):
            indices.append(uid)
            continue
        found = None
        if "unit_id" in unit_cols:
            for i in range(len(units_table)):
                val = units_table["unit_id"][i]
                if val is not None and str(int(float(val))) == str(uid):
                    found = i
                    break
        if found is None:
            try:
                found = int(uid)
            except (TypeError, ValueError):
                raise JnwbBlockedError(f"Cannot resolve unit id {uid}")
        indices.append(found)
    return indices


def _path_by_session(nwbfiles: Iterable[NWBFileRecord]) -> dict[str, NWBFileRecord]:
    return {session_key_from_record(rec): rec for rec in nwbfiles}


def _trial_metadata_rows(events: list[dict], skey: str, trial_offset: int = 0) -> list[dict]:
    return [
        {
            "trial_global": trial_offset + t_idx,
            "trial_in_session": t_idx,
            "session_id": skey,
            "condition": ev["condition"],
            "condition_number": ev["condition_number"],
            "onset_s": ev["onset_s"],
            "anchor": ev["anchor"],
            "omission_offset_ms": ev.get("omission_offset_ms"),
        }
        for t_idx, ev in enumerate(events)
    ]


def _signal_metadata_rows(signal_addr: SignalAddress, skey: str) -> pd.DataFrame:
    unit_ids = signal_addr.ids_by_session[skey]
    return pd.DataFrame(
        [
            {
                "session_id": skey,
                "signal_id": uid,
                "global_unit_index": local_idx,
                "signal_class": signal_addr.signal,
                "area": signal_addr.area_by_id[skey].get(uid),
                "layer": signal_addr.layer_by_id[skey].get(uid),
                "probe": signal_addr.probe_by_id[skey].get(uid),
            }
            for local_idx, uid in enumerate(unit_ids)
        ]
    )


def _iter_spk_session_chunks(
    rec: NWBFileRecord,
    signal_addr: SignalAddress,
    event_addr: EventAddress,
    skey: str,
    events: list[dict],
    window_ms: tuple[int, int],
    bin_ms: float,
    chunk_size: int,
    spec: EpochSpec,
    time_centers: np.ndarray,
    backend: str,
    fail_on_empty: bool,
) -> Iterator[EpochBatch]:
    """Yield trial chunks for one session without allocating the full session array."""
    unit_ids = signal_addr.ids_by_session[skey]
    signal_df = _signal_metadata_rows(signal_addr, skey)
    n_trials = len(events)
    if n_trials == 0:
        if fail_on_empty:
            raise JnwbBlockedError(f"No events for session {skey}", code=BLOCKED_EMPTY_EPOCHS)
        return

    effective_chunk = n_trials if chunk_size <= 0 else chunk_size
    NWBHDF5IO = _require_pynwb()
    io = NWBHDF5IO(rec.path, "r", load_namespaces=True)
    try:
        nwbfile = io.read()
        units_table = nwbfile.units
        unit_indices = _unit_row_indices(units_table, unit_ids)

        for start in range(0, n_trials, effective_chunk):
            end = min(start + effective_chunk, n_trials)
            chunk_events = events[start:end]
            event_times = np.array([e["onset_s"] for e in chunk_events], dtype=np.float64)
            data = _extract_spk_epoch(units_table, unit_indices, event_times, window_ms, bin_ms)
            if data.size == 0 and fail_on_empty:
                raise JnwbBlockedError(f"Empty epochs for {skey}", code=BLOCKED_EMPTY_EPOCHS)

            trial_df = pd.DataFrame(_trial_metadata_rows(chunk_events, skey, trial_offset=start))
            manifest = {
                "spec": spec.to_dict(),
                "shape": tuple(data.shape),
                "dtype": str(data.dtype),
                "sessions": [skey],
                "session_id": skey,
                "conditions": event_addr.conditions,
                "bin_ms": spec.bin_ms,
                "anchor": event_addr.anchor,
                "p1_code": event_addr.p1_code,
                "chunk_start": start,
                "chunk_end": end,
            }
            yield EpochBatch(
                data=to_backend(data, backend),
                time_ms=to_backend(time_centers, backend),
                trial_metadata=trial_df.reset_index(drop=True),
                signal_metadata=signal_df,
                manifest=manifest,
            )
    finally:
        io.close()


def load_epochs(
    nwbfiles: Iterable[NWBFileRecord],
    signal_addr: SignalAddress,
    event_addr: EventAddress,
    window_ms: tuple[int, int],
    chunk_size: int = 32,
    backend: str = "numpy",
    bin_ms: float | None = None,
    fail_on_empty: bool = True,
) -> EpochBatch | Iterator[EpochBatch]:
    """Load trial-preserving epochs in bounded-memory chunks.

    SPK returns trial x unit x time per chunk (binned spike counts, not smoothed).
    Multi-chunk or multi-session calls return a lazy iterator; only one chunk is
    materialized at a time.
    """
    file_list = list(nwbfiles)
    path_map = _path_by_session(file_list)

    sig_sessions = set(signal_addr.sessions)
    ev_sessions = set(event_addr.sessions)
    if sig_sessions != ev_sessions:
        dropped = sig_sessions.symmetric_difference(ev_sessions)
        raise JnwbBlockedError(
            f"Session mismatch between signal and event addresses: {sorted(dropped)}",
            code=BLOCKED_SESSION_SILENTLY_DROPPED,
        )

    if signal_addr.signal == "SPK":
        if bin_ms is None:
            bin_ms = 1.0
        shape_contract = "trial x unit x time"
    else:
        shape_contract = "trial x channel x time"
        raise JnwbBlockedError(
            f"{signal_addr.signal} epoch loading not yet implemented",
            code="BLOCKED_SIGNAL_LOAD_NOT_IMPLEMENTED",
        )

    spec = EpochSpec(
        signal=signal_addr.signal,
        alignment=event_addr.anchor,
        window_ms=window_ms,
        output_shape_contract=shape_contract,
        bin_ms=bin_ms,
        chunk_size=chunk_size,
        backend=backend,
    )

    _, time_centers = _bin_edges(window_ms, bin_ms)

    def _iter_batches() -> Iterator[EpochBatch]:
        for skey in signal_addr.sessions:
            events = event_addr.events_by_session.get(skey, [])
            if not events:
                raise JnwbBlockedError(f"No events for session {skey}", code=BLOCKED_EMPTY_EPOCHS)

            rec = path_map.get(skey)
            if rec is None:
                raise JnwbBlockedError(f"No NWB record for session {skey}")

            yield from _iter_spk_session_chunks(
                rec,
                signal_addr,
                event_addr,
                skey,
                events,
                window_ms,
                bin_ms,
                chunk_size,
                spec,
                time_centers,
                backend,
                fail_on_empty,
            )

    gen = _iter_batches()
    try:
        first = next(gen)
    except StopIteration:
        if fail_on_empty:
            raise JnwbBlockedError("No trials loaded", code=BLOCKED_EMPTY_EPOCHS) from None
        return EpochBatch(
            data=np.zeros((0, 0, 0)),
            time_ms=np.array([]),
            trial_metadata=pd.DataFrame(),
            signal_metadata=pd.DataFrame(),
            manifest={"spec": spec.to_dict(), "empty": True},
        )

    try:
        second = next(gen)
    except StopIteration:
        return first

    return itertools.chain([first, second], gen)
