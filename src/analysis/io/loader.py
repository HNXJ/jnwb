# core
import os
import re
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
from src.analysis.io.logger import log
from src.analysis.io.eye_mapper import EyeDataMapper

class DataLoader:
    """
    Core data loader utilizing lazy-loading (mmap) for `.npy` array files.
    Automatically parses the canonical session-area mapping.
    """

    CANONICAL_AREAS = ["V1", "V2", "V3d", "V3a", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]
    BLACKLISTED_SESSIONS = ["230901"] # Session 5 (PFC) clipping artifact

    def normalize_area(self, area: str) -> str:
        """
        Normalizes area labels to canonical set.
        - DP, DP (V4) -> V4
        - V3 (exact) -> V3
        - Substrings are not allowed for canonical matching.
        """
        area = area.strip()
        if area in ["DP", "DP (V4)"]:
            return "V4"
        return area

    def __init__(self, data_dir: str = None, mapping_file: str = None):
        # Resolve paths relative to repo root
        root = Path(__file__).parent.parent.parent.parent
        self.data_dir = Path(data_dir) if data_dir else root.parent / "data" / "arrays"
        self.mapping_file = Path(mapping_file) if mapping_file else root / "context" / "overview" / "session-area-mapping.md"
        self.area_map = self._parse_mapping()
        self.eye_mapper = EyeDataMapper()
        log.action(f"Initialized DataLoader (NPY) with mapping from {self.mapping_file}")

    def get_eye_data_path(self, session: str) -> Path:
        """Resolves the exact .bhv2.mat file specifically for oculomotor (EYE) analysis."""
        return self.eye_mapper.get_behavioral_file(session)

    def _parse_mapping(self):
        """Parses the markdown table to build a mapping dict: area -> list of (session, probe, channel_indices)."""
        if not self.mapping_file.exists():
            log.error(f"Mapping file missing: {self.mapping_file}")
            return {}

        area_map = defaultdict(list)
        with open(self.mapping_file, "r") as f:
            lines = f.readlines()

        table_started = False
        for line in lines:
            if "| Session |" in line:
                table_started = True
                continue
            if table_started and line.startswith("|") and not line.startswith("|:---"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    session = parts[0]
                    if session in self.BLACKLISTED_SESSIONS:
                        continue
                    probe = int(parts[1])
                    areas = [a.strip() for a in parts[2].split(",")]
                    total_ch = int(parts[3])

                    n_areas = len(areas)
                    boundaries = np.linspace(0, total_ch, n_areas + 1, dtype=int)

                    for i, area_raw in enumerate(areas):
                        area = self.normalize_area(area_raw)
                        # Filter for canonical areas or V3 (exact match)
                        if area in self.CANONICAL_AREAS or area == "V3":
                            if area == "V3":
                                log.warning(f"Session {session} Probe {probe} uses generic V3. This area is loaded but remains UNRESOLVED (not split into V3d/V3a).")

                            start_ch, end_ch = boundaries[i], boundaries[i+1]
                            area_map[area].append({
                                "session": session,
                                "probe": probe,
                                "start_ch": start_ch,
                                "end_ch": end_ch,
                                "total_ch": total_ch
                            })
                        else:
                            log.warning(f"Area '{area_raw}' (normalized to '{area}') in session {session} is NOT canonical and will be skipped.")
        return dict(area_map)

    def get_omission_onset(self, condition: str):
        """Returns the onset of the omission relative to p1 start (ms)."""
        # Family-aware timing
        if any(f in condition for f in ["AXAB", "BXBA", "RXRR"]): return 1031.0 # p2
        if any(f in condition for f in ["AAXB", "BBXA", "RRXR"]): return 2062.0 # p3
        if any(f in condition for f in ["AAAX", "BBBX", "RRRX"]): return 3093.0 # p4
        return 1031.0 # Default to p2

    def get_signal(self, mode: str, condition: str, area: str, align_to: str = "p1", **kwargs):
        """
        Loads signals with flexible alignment.
        align_to: 'p1' (stimulus onset) or 'omission' (family-aware).
        """
        session = kwargs.get("session")
        pre_ms = kwargs.get("pre_ms", 1000)
        post_ms = kwargs.get("post_ms", 1000)
        log.action(f"Extracting {mode} signal for area {area} in condition {condition} (Align: {align_to}, Session: {session})")

        data_list = self._load_data(mode, condition, area, session=session)
        if not data_list: return None

        if align_to == "omission":
            onset_ms = self.get_omission_onset(condition)
            # Sample 1000 is 0ms (p1 onset). Omission onset sample = 1000 + onset_ms
            onset_sample = 1000 + int(onset_ms)

            aligned_list = []
            for arr in data_list:
                # Crop to [-pre_ms, +post_ms] relative to omission
                start = max(0, onset_sample - pre_ms)
                end = onset_sample + post_ms
                if arr.shape[-1] >= end:
                    aligned_list.append(arr[:, :, start:end])
                else:
                    log.warning(f"Array too short for omission alignment (End: {end}, Shape: {arr.shape[-1]})")
            return aligned_list

        return data_list

    def _load_data(self, mode, condition, area, session: str = None):
        """Internal raw loader."""
        if area not in self.area_map: return None
        area_entries = self.area_map[area]
        data_list = []
        for entry in area_entries:
            # Filter by session if provided
            if session and entry["session"] != session:
                continue

            ses = entry["session"]; p = entry["probe"]; start_ch = entry["start_ch"]; end_ch = entry["end_ch"]; total_ch = entry["total_ch"]
            filename = f"ses{ses}-{'units-probe'+str(p)+'-spk' if mode=='spk' else 'probe'+str(p)+'-lfp'}-{condition}.npy"
            file_path = self.data_dir / filename
            if file_path.exists():
                try:
                    arr = np.load(file_path, mmap_mode='r')
                    if mode == "lfp":
                        arr_slice = arr[:, start_ch:end_ch, :]
                    else:
                        # Heuristic SPK assignment (Loud Warning required by protocol)
                        log.warning(f"SPK unit-area assignment for {ses} {area} (Probe {p}) is HEURISTIC. Metadata 'peak_channel_id' validation deferred.")
                        u_start = int(arr.shape[1] * (start_ch / total_ch))
                        u_end = int(arr.shape[1] * (end_ch / total_ch))
                        arr_slice = arr[:, u_start:u_end, :]
                    data_list.append(arr_slice)
                except Exception: pass
        return data_list

    def get_units_by_area(self, area: str) -> list:
        """Returns a list of unit identifiers available for the specified area."""
        if area not in self.area_map:
            log.warning(f"Area {area} not found in mapping.")
            return []

        units = []
        for entry in self.area_map[area]:
            ses = entry["session"]
            if ses in self.BLACKLISTED_SESSIONS:
                continue
            p = entry["probe"]
            start_ch = entry["start_ch"]
            end_ch = entry["end_ch"]
            total_ch = entry["total_ch"]

            # Check for file availability to get actual unit count
            filename = f"ses{ses}-units-probe{p}-spk-AXAB.npy" # Use AXAB as reference for unit counts
            file_path = self.data_dir / filename
            if file_path.exists():
                try:
                    arr = np.load(file_path, mmap_mode='r')
                    n_total_units = arr.shape[1]

                    # Heuristic fallback warning
                    log.warning(f"Unit indexing for {ses} {area} (Probe {p}) is HEURISTIC. Metadata alignment not confirmed.")
                    u_start = int(n_total_units * (start_ch / total_ch))
                    u_end = int(n_total_units * (end_ch / total_ch))

                    for u_idx in range(u_start, u_end):
                        units.append(f"{ses}-probe{p}-unit{u_idx}")
                except Exception as e:
                    log.error(f"Failed to read unit count from {filename}: {e}")

        log.info(f"Found {len(units)} units for area {area}")
        return units

    def load_unit_spikes(self, unit_id: str, condition: str = "AXAB", epoch: str = "p1"):
        """
        Loads spike data for a single unit.
        unit_id format: 'session-probeN-unitIdx'
        epoch: 'p1', 'p2', etc. (currently p1 is full 4s stim block in these files)
        """
        try:
            parts = unit_id.split("-")
            ses = parts[0]
            probe_str = parts[1] # 'probe1'
            u_idx = int(parts[2].replace("unit", ""))

            filename = f"ses{ses}-units-{probe_str}-spk-{condition}.npy"
            file_path = self.data_dir / filename

            if not file_path.exists():
                return None

            arr = np.load(file_path, mmap_mode='r')
            # Extract single unit: shape (n_trials, n_timepoints)
            unit_data = arr[:, u_idx, :]
            return unit_data
        except Exception as e:
            log.error(f"Failed to load spikes for {unit_id}: {e}")
            return None

    def get_output_dir(self, fig_id: str):
        """Returns the canonical output directory for a specific figure."""
        root = Path(__file__).parent.parent.parent.parent
        dashboard_id = fig_id.replace("_", "-")
        out_dir = root / "outputs" / "oglo-8figs" / dashboard_id
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def get_sessions(self):
        """Returns list of sessions found in data directory."""
        sessions = set()
        for f in self.data_dir.glob("ses*-*.npy"):
            match = re.search(r"ses(\d+)-", f.name)
            if match:
                sessions.add(match.group(1))
        return sorted(list(sessions))

    def get_unit_metrics(self, session: str):
        """Loads metadata CSV for a session."""
        root = Path(__file__).parent.parent.parent.parent
        csv_path = root.parent / "data" / "metadata" / f"units_ses-{session}.csv"
        if csv_path.exists():
            return pd.read_csv(csv_path, index_col=0)
        return None

    def close_all(self):
        pass
