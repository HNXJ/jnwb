"""NWB file discovery and lightweight inspection."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .errors import BLOCKED_PYNWB_UNAVAILABLE, JnwbBlockedError
from .schema import NWBFileRecord


def _require_pynwb():
    try:
        from pynwb import NWBHDF5IO  # noqa: F401
    except ImportError as exc:
        raise JnwbBlockedError("PyNWB is required for NWB reads", code=BLOCKED_PYNWB_UNAVAILABLE) from exc
    from pynwb import NWBHDF5IO

    return NWBHDF5IO


def _parse_subject_session(path: Path) -> tuple[str | None, str]:
    stem = path.stem.replace("_rec", "")
    m = re.match(r"(sub-[^_]+)_(ses-[^_]+)", stem)
    if m:
        return m.group(1), m.group(2)
    parts = stem.split("_")
    subject = parts[0] if parts else None
    session = parts[1] if len(parts) > 1 else stem
    return subject, session


def _session_key(subject: str | None, session_id: str) -> str:
    sub = (subject or "unknown").replace("-", "_")
    ses = session_id.replace("-", "_")
    if ses.startswith(f"{sub}_"):
        return ses
    if ses.startswith("sub_") and sub in ses:
        return ses
    return f"{sub}_{ses}"


def _has_signal_flags(nwbfile) -> tuple[bool, bool, bool]:
    has_spk = getattr(nwbfile, "units", None) is not None and len(nwbfile.units) > 0

    has_lfp = False
    has_muae = False

    acquisition = getattr(nwbfile, "acquisition", {})
    for name in acquisition.keys():
        low = name.lower()
        if "lfp" in low:
            has_lfp = True
        if "muae" in low or "mua" in low:
            has_muae = True

    processing = getattr(nwbfile, "processing", {})
    for module in processing.values():
        for data_name in module.data_interfaces.keys():
            low = data_name.lower()
            if "lfp" in low:
                has_lfp = True
            if "muae" in low or "mua" in low:
                has_muae = True

    return has_spk, has_lfp, has_muae


def _task_names(nwbfile) -> list[str]:
    names: list[str] = []
    intervals = getattr(nwbfile, "intervals", None)
    if intervals is not None:
        for name in intervals.keys():
            if "omission" in name.lower() or "task" in name.lower():
                names.append(str(name))
    return sorted(set(names))


def list_nwb_files(root: str | Path, pattern: str = "*.nwb", recursive: bool = True) -> list[NWBFileRecord]:
    """Discover NWB files under root without loading signal data."""
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(f"NWB root not found: {root_path}")

    globber = root_path.rglob if recursive else root_path.glob
    paths = sorted(globber(pattern), key=lambda p: str(p).lower())

    records: list[NWBFileRecord] = []
    for path in paths:
        records.append(inspect_nwb(path))
    return records


def inspect_nwb(nwb_path: str | Path) -> NWBFileRecord:
    """Inspect NWB metadata only (no spike/LFP sample loading)."""
    path = Path(nwb_path)
    if not path.exists():
        raise FileNotFoundError(f"NWB file not found: {path}")

    NWBHDF5IO = _require_pynwb()
    io = NWBHDF5IO(str(path), "r", load_namespaces=True)
    try:
        nwbfile = io.read()
        subject_obj = getattr(nwbfile, "subject", None)
        subject = getattr(subject_obj, "subject_id", None) if subject_obj is not None else None
        if subject is None:
            subject, _ = _parse_subject_session(path)

        session_id = getattr(nwbfile, "session_id", None)
        if not session_id:
            _, session_id = _parse_subject_session(path)

        session_start = getattr(nwbfile, "session_start_time", None)
        date = session_start.isoformat() if isinstance(session_start, datetime) else None

        has_spk, has_lfp, has_muae = _has_signal_flags(nwbfile)
        return NWBFileRecord(
            path=str(path.resolve()),
            session_id=str(session_id),
            subject=str(subject) if subject is not None else None,
            date=date,
            task_names=_task_names(nwbfile),
            has_spk=has_spk,
            has_lfp=has_lfp,
            has_muae=has_muae,
        )
    finally:
        io.close()


def build_session_manifest(nwbfiles: Iterable[NWBFileRecord], out: str | Path | None = None) -> pd.DataFrame:
    """Build a session manifest table from NWB file records."""
    rows = [rec.to_dict() for rec in nwbfiles]
    df = pd.DataFrame(rows)
    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
    return df


def session_key_from_record(rec: NWBFileRecord) -> str:
    return _session_key(rec.subject, rec.session_id)
