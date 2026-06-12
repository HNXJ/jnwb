"""Signal addressing for SPK, LFP, and MUAe."""

from __future__ import annotations

import re
from typing import Iterable, Literal

import numpy as np

from .errors import (
    BLOCKED_AREA_METADATA_MISSING,
    BLOCKED_SIGNAL_UNAVAILABLE,
    JnwbBlockedError,
)
from .files import NWBFileRecord, _require_pynwb, session_key_from_record
from .schema import SignalAddress

SignalType = Literal["SPK", "LFP", "MUAe"]


def _resolve_unit_area(units_table, unit_idx: int, electrodes, unit_cols: list[str]) -> tuple[str | None, str | None, str | None]:
    """Resolve area, layer, probe for a unit."""
    area: str | None = None
    layer: str | None = None
    probe: str | None = None

    if "area" in unit_cols:
        val = units_table["area"][unit_idx]
        if val is not None and str(val) not in ("nan", "None", ""):
            area = str(val)

    peak_channel = None
    for col in ["peak_channel", "peak_channel_id", "electrode", "electrodes"]:
        if col in unit_cols:
            val = units_table[col][unit_idx]
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                peak_channel = int(float(val))
                break

    if "electrode_group" in unit_cols:
        eg = units_table["electrode_group"][unit_idx]
        eg_name = str(getattr(eg, "name", eg))
        probe = eg_name
        m = re.search(r"probe[\s_]*(\d+)", eg_name, re.IGNORECASE)
        if m:
            probe = f"probe{m.group(1)}"

    if area is None and peak_channel is not None and electrodes is not None:
        if "location" in electrodes.colnames and peak_channel < len(electrodes):
            loc = electrodes["location"][peak_channel]
            if loc is not None and str(loc) not in ("nan", "None", ""):
                area = str(loc)

    if "depth" in unit_cols:
        dval = units_table["depth"][unit_idx]
        if dval is not None and str(dval) not in ("nan", "None", ""):
            layer = str(dval)

    return area, layer, probe


def _find_analog_series(nwbfile, signal: SignalType) -> tuple[str | None, float | None]:
    target = "lfp" if signal == "LFP" else "muae"
    alt = "mua" if signal == "MUAe" else None

    acquisition = getattr(nwbfile, "acquisition", {})
    for name, obj in acquisition.items():
        low = name.lower()
        if target in low or (alt and alt in low):
            rate = float(obj.rate) if hasattr(obj, "rate") and obj.rate is not None else None
            return f"acquisition/{name}", rate

    processing = getattr(nwbfile, "processing", {})
    for module_name, module in processing.items():
        for data_name, obj in module.data_interfaces.items():
            low = data_name.lower()
            if target in low or (alt and alt in low):
                rate = float(obj.rate) if hasattr(obj, "rate") and obj.rate is not None else None
                return f"processing/{module_name}/{data_name}", rate

    return None, None


def address_signals(
    nwbfiles: Iterable[NWBFileRecord],
    signal: SignalType,
    areas: list[str] | None = None,
    layers: list[str] | None = None,
    sessions: list[str] | None = None,
    require_area: bool = False,
    allow_unknown_area: bool = False,
    max_items: int | None = None,
) -> SignalAddress:
    """Address neural signals without loading full time series."""
    file_list = list(nwbfiles)
    input_sessions = set(sessions) if sessions else None
    area_filter = set(areas) if areas else None
    layer_filter = set(layers) if layers else None

    NWBHDF5IO = _require_pynwb()

    sessions_out: list[str] = []
    source_paths: list[str] = []
    object_paths: dict[str, str] = {}
    ids_by_session: dict[str, list[str | int]] = {}
    area_by_id: dict[str, dict[str | int, str | None]] = {}
    layer_by_id: dict[str, dict[str | int, str | None]] = {}
    probe_by_id: dict[str, dict[str | int, str | None]] = {}
    sampling_rate_by_session: dict[str, float | None] = {}
    warnings: list[str] = []
    units_label: str | None = "spikes" if signal == "SPK" else "a.u."

    for rec in file_list:
        skey = session_key_from_record(rec)
        if input_sessions is not None and skey not in input_sessions:
            continue

        if signal == "SPK" and not rec.has_spk:
            warnings.append(f"{skey}: SPK unavailable")
            continue
        if signal == "LFP" and not rec.has_lfp:
            warnings.append(f"{skey}: LFP unavailable")
            continue
        if signal == "MUAe" and not rec.has_muae:
            warnings.append(f"{skey}: MUAe unavailable")
            continue

        io = NWBHDF5IO(rec.path, "r", load_namespaces=True)
        try:
            nwbfile = io.read()

            if signal == "SPK":
                units_table = getattr(nwbfile, "units", None)
                if units_table is None or len(units_table) == 0:
                    warnings.append(f"{skey}: empty units table")
                    continue

                electrodes = getattr(nwbfile, "electrodes", None)
                unit_cols = list(units_table.colnames)
                ids: list[str | int] = []
                area_map: dict[str | int, str | None] = {}
                layer_map: dict[str | int, str | None] = {}
                probe_map: dict[str | int, str | None] = {}

                for unit_idx in range(len(units_table)):
                    if "unit_id" in unit_cols:
                        uid = units_table["unit_id"][unit_idx]
                        unit_id: str | int = str(int(float(uid))) if uid is not None else unit_idx
                    else:
                        unit_id = unit_idx

                    area, layer, probe = _resolve_unit_area(units_table, unit_idx, electrodes, unit_cols)

                    if area_filter is not None and area not in area_filter:
                        continue
                    if layer_filter is not None and layer not in layer_filter:
                        continue
                    if require_area and area is None:
                        raise JnwbBlockedError(
                            f"Area metadata missing for unit {unit_id} in {skey}",
                            code=BLOCKED_AREA_METADATA_MISSING,
                        )
                    if area is None and not allow_unknown_area and area_filter is not None:
                        continue
                    if area is None and allow_unknown_area:
                        warnings.append(f"{skey}: unit {unit_id} has unknown area")

                    ids.append(unit_id)
                    area_map[unit_id] = area
                    layer_map[unit_id] = layer
                    probe_map[unit_id] = probe

                    if max_items is not None and len(ids) >= max_items:
                        break

                if not ids:
                    warnings.append(f"{skey}: no units matched filters")
                    continue

                object_paths[skey] = "units"
                ids_by_session[skey] = ids
                area_by_id[skey] = area_map
                layer_by_id[skey] = layer_map
                probe_by_id[skey] = probe_map
                sampling_rate_by_session[skey] = None

            else:
                obj_path, rate = _find_analog_series(nwbfile, signal)
                if obj_path is None:
                    warnings.append(f"{skey}: {signal} series not found")
                    continue

                electrodes = getattr(nwbfile, "electrodes", None)
                n_ch = len(electrodes) if electrodes is not None else 0
                if n_ch == 0:
                    warnings.append(f"{skey}: no electrodes for {signal}")
                    continue

                ids = list(range(n_ch))
                area_map = {}
                layer_map = {}
                probe_map = {}

                elec_cols = list(electrodes.colnames) if electrodes is not None else []
                for ch in ids:
                    area = None
                    layer = None
                    probe = None
                    if "location" in elec_cols:
                        loc = electrodes["location"][ch]
                        if loc is not None and str(loc) not in ("nan", "None", ""):
                            area = str(loc)
                    if "group" in elec_cols:
                        grp = electrodes["group"][ch]
                        probe = str(getattr(grp, "name", grp))

                    if area_filter is not None and area not in area_filter:
                        continue
                    if require_area and area is None:
                        raise JnwbBlockedError(
                            f"Area metadata missing for channel {ch} in {skey}",
                            code=BLOCKED_AREA_METADATA_MISSING,
                        )

                    area_map[ch] = area
                    layer_map[ch] = layer
                    probe_map[ch] = probe

                if not area_map:
                    warnings.append(f"{skey}: no channels matched filters")
                    continue

                ids = list(area_map.keys())
                if max_items is not None:
                    ids = ids[:max_items]
                    area_map = {k: area_map[k] for k in ids}
                    layer_map = {k: layer_map[k] for k in ids}
                    probe_map = {k: probe_map[k] for k in ids}

                object_paths[skey] = obj_path
                ids_by_session[skey] = ids
                area_by_id[skey] = area_map
                layer_by_id[skey] = layer_map
                probe_by_id[skey] = probe_map
                sampling_rate_by_session[skey] = rate

            sessions_out.append(skey)
            source_paths.append(rec.path)

        finally:
            io.close()

    if not sessions_out:
        raise JnwbBlockedError(
            f"No sessions with signal {signal}",
            code=BLOCKED_SIGNAL_UNAVAILABLE,
            details={"warnings": warnings},
        )

    return SignalAddress(
        signal=signal,
        sessions=sessions_out,
        source_paths=source_paths,
        object_paths=object_paths,
        ids_by_session=ids_by_session,
        area_by_id=area_by_id,
        layer_by_id=layer_by_id,
        probe_by_id=probe_by_id,
        sampling_rate_by_session=sampling_rate_by_session,
        units=units_label,
        warnings=warnings,
    )
