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
        self.subject_file = root / "context" / "overview" / "subjects.json"
        
        self.area_map = self._parse_mapping()
        self.eye_mapper = EyeDataMapper()
        
        # Load subject map
        self.subject_map = {}
        if self.subject_file.exists():
            import json
            with open(self.subject_file, "r") as f:
                self.subject_map = json.load(f)

        # Metadata cache for unit anatomical assignment
        self.unit_metadata_cache = {}
        self.unit_count_cache = {}

        log.action(f"Initialized DataLoader (NPY) with mapping from {self.mapping_file}")

    def get_subject_id(self, session: str) -> str:
        """Returns the subject ID for a given session."""
        return self.subject_map.get(session, "Unknown")

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

    def _get_unit_metadata(self, session: str):
        """Loads and caches unit metadata for a session."""
        if session in self.unit_metadata_cache:
            return self.unit_metadata_cache[session]

        meta_dir = self.data_dir.parent / "metadata"
        csv_path = meta_dir / f"units_ses-{session}.csv"

        if csv_path.exists():
            df = pd.read_csv(csv_path)
            self.unit_metadata_cache[session] = df
            return df
        return None

    def _get_probe_unit_count(self, session: str, probe: int) -> int:
        """Returns number of units for a specific probe in a session."""
        key = (session, probe)
        if key in self.unit_count_cache:
            return self.unit_count_cache[key]

        # Use AXAB as reference file for unit counts
        filename = f"ses{session}-units-probe{probe}-spk-AXAB.npy"
        file_path = self.data_dir / filename
        if file_path.exists():
            arr = np.load(file_path, mmap_mode='r')
            count = arr.shape[1]
            self.unit_count_cache[key] = count
            return count
        return 0

    def resolve_unit_area(self, session: str, probe: int, unit_idx: int, allow_heuristic: bool = False):
        """
        Resolves the anatomical area for a unit using peak_channel_id metadata.
        Returns: (normalized_area, status, warning)
        """
        # 0. Check for blacklisting
        if session in self.BLACKLISTED_SESSIONS:
            return None, "blacklisted", f"Session {session} is blacklisted (reason: clipping/artifact)"

        df = self._get_unit_metadata(session)
        
        # 1. Determine if this probe has ANY mapping info in area_map
        probe_has_mapping = False
        probe_entries = []
        for area_name, entries in self.area_map.items():
            for entry in entries:
                if entry["session"] == session and entry["probe"] == probe:
                    probe_has_mapping = True
                    probe_entries.append((area_name, entry))

        if df is not None:
            # Validate session counts
            n_total_spk_units = 0
            probe_offsets = {}
            for p in range(5): # Check up to 5 probes
                count = self._get_probe_unit_count(session, p)
                if count > 0:
                    probe_offsets[p] = n_total_spk_units
                    n_total_spk_units += count
            
            if len(df) != n_total_spk_units:
                log.warning(f"Session {session} metadata row count ({len(df)}) mismatch with total SPK unit count across probes ({n_total_spk_units}). Indexing may be shifted.")

            if probe in probe_offsets:
                offset = probe_offsets[probe]
                global_idx = offset + unit_idx
                
                if global_idx < len(df):
                    row = df.iloc[global_idx]
                    peak_ch = row["peak_channel_id"]
                    if pd.isna(peak_ch):
                        return None, "unresolved_metadata", "peak_channel_id is NaN"
                    
                    # Global to local channel mapping
                    p_idx = int(peak_ch // 128)
                    local_ch = int(peak_ch % 128)
                    
                    if p_idx != probe:
                        return None, "unresolved_metadata", f"Peak channel {peak_ch} on probe {p_idx} mismatch with data probe {probe}"
                    
                    # Search mapping for this probe
                    for area_name, entry in probe_entries:
                        if entry["start_ch"] <= local_ch < entry["end_ch"]:
                            # Since boundaries are currently derived via np.linspace, status is equal_segment
                            return area_name, "metadata_resolved_equal_segment", None
                    
                    # If we have mapping for the probe but the channel didn't hit an area
                    if probe_has_mapping:
                        return None, "unknown_area", f"Channel {local_ch} does not map to canonical area segment"
        
        # 2. Heuristic fallback (only if allowed)
        if allow_heuristic and probe_has_mapping:
            for area_name, entry in probe_entries:
                n_units = self._get_probe_unit_count(session, probe)
                if n_units > 0:
                    u_start = int(n_units * (entry["start_ch"] / entry["total_ch"]))
                    u_end = int(n_units * (entry["end_ch"] / entry["total_ch"]))
                    if u_start <= unit_idx < u_end:
                        return area_name, "heuristic_fallback", "Metadata missing; used linear partition"
                            
        # 3. Final Fallback: Unmapped or No Match
        if not probe_has_mapping:
            return None, "unresolved_no_probe_mapping", f"Probe {probe} not found in mapping file for session {session}"
        return None, "unknown_area", "No metadata or heuristic match within defined segments"

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

    def _load_data(self, mode, condition, area, session: str = None, allow_heuristic: bool = False):
        """Internal raw loader."""
        if area not in self.area_map: return None
        area_entries = self.area_map[area]
        data_list = []
        for entry in area_entries:
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
                        # SPK: Resolve units by metadata
                        n_units = arr.shape[1]
                        selected_indices = []
                        metadata_count = 0

                        for u_idx in range(n_units):
                            res_area, status, _ = self.resolve_unit_area(ses, p, u_idx, allow_heuristic=allow_heuristic)
                            if res_area == area:
                                selected_indices.append(u_idx)
                                if "metadata_resolved" in status:
                                    metadata_count += 1

                        if not selected_indices:
                            continue

                        # Log summary for this probe-area entry
                        if metadata_count < len(selected_indices):
                            log.warning(f"SPK mapping for {ses} {area} (Probe {p}) partially HEURISTIC ({metadata_count}/{len(selected_indices)} metadata-resolved)")

                        arr_slice = arr[:, selected_indices, :]
                    data_list.append(arr_slice)
                except Exception as e:
                    log.error(f"Error loading {filename}: {e}")
        return data_list

    def get_units_by_area(self, area: str, allow_heuristic: bool = False) -> list:
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

            n_units = self._get_probe_unit_count(ses, p)
            if n_units > 0:
                metadata_count = 0
                entry_units = []
                for u_idx in range(n_units):
                    res_area, status, _ = self.resolve_unit_area(ses, p, u_idx, allow_heuristic=allow_heuristic)
                    if res_area == area:
                        entry_units.append(f"{ses}-probe{p}-unit{u_idx}")
                        if "metadata_resolved" in status:
                            metadata_count += 1

                if entry_units:
                    if metadata_count < len(entry_units):
                        log.warning(f"Unit list for {ses} {area} (Probe {p}) partially HEURISTIC ({metadata_count}/{len(entry_units)} metadata-resolved)")
                    units.extend(entry_units)

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

    def load_session_manifest_fixture(self, session_id: str):
        """
        Loads a session manifest fixture safely, runs validation,
        handles DP normalization, and verifies truth status.
        """
        from src.analysis.contracts import SessionManifest
        import json
        
        # Resolve paths
        root = Path(__file__).parent.parent.parent.parent
        search_paths = [
            root / "artifacts" / "test_manifests" / f"session_{session_id}_manifest.json",
            root / "tests" / "fixtures" / "manifests" / f"session_{session_id}_manifest.json",
            root / "tests" / "fixtures" / "manifests" / f"{session_id}.json"
        ]
        
        manifest_path = None
        for path in search_paths:
            if path.exists():
                manifest_path = path
                break
                
        if not manifest_path:
            raise FileNotFoundError(f"Fixture manifest not found for session '{session_id}'.")
            
        with open(manifest_path, "r") as f:
            data = json.load(f)
            
        manifest = SessionManifest.from_dict(data)
        
        # Normalize DP to V4
        # Normalize in area_mappings
        for mapping in manifest.area_mappings:
            mapping.area = SessionManifest.normalize_area(mapping.area)
        # Normalize in units
        for unit in manifest.units:
            unit.area = SessionManifest.normalize_area(unit.area)
        # Normalize dict keys
        for d in [manifest.channel_counts_by_area, manifest.unit_counts_by_area, manifest.area_resolution_status]:
            if d:
                for k in list(d.keys()):
                    norm_k = SessionManifest.normalize_area(k)
                    if norm_k != k:
                        d[norm_k] = d.pop(k)
                        
        # Validate manifest rules
        errors = manifest.validate()
        if errors:
            raise ValueError(f"Manifest validation failed for session {session_id}: {errors}")
            
        return manifest

    def resolve_unit_area_manifest(self, manifest, probe: int, unit_idx: int, allow_heuristic: bool = False):
        """Resolves the anatomical area for a unit using the loaded manifest."""
        # 1. Search in manifest.units
        for u in manifest.units:
            if u.probe == probe and u.local_idx == unit_idx:
                return u.area, u.resolution_status, None

        # 2. Try using unit_peak_or_anchor_channels and area_mappings
        peak_ch = None
        unit_id = f"{manifest.session_id}-probe{probe}-unit{unit_idx}"
        if manifest.unit_peak_or_anchor_channels and unit_id in manifest.unit_peak_or_anchor_channels:
            peak_ch = manifest.unit_peak_or_anchor_channels[unit_id]
        
        if peak_ch is not None:
            for mapping in manifest.area_mappings:
                if mapping.probe == probe and mapping.start_ch <= peak_ch < mapping.end_ch:
                    return mapping.area, f"metadata_resolved_{mapping.resolution_status}", None

        # 3. Heuristic fallback: linear partition
        if allow_heuristic:
            probe_mappings = [m for m in manifest.area_mappings if m.probe == probe]
            if probe_mappings:
                total_units = 0
                for u in manifest.units:
                    if u.probe == probe:
                        total_units = max(total_units, u.local_idx + 1)
                if total_units == 0 and manifest.unit_counts_by_area:
                    total_units = sum(manifest.unit_counts_by_area.values())
                if total_units == 0:
                    total_units = 10 # Default fallback count for fixture testing

                for mapping in probe_mappings:
                    total_ch = 128
                    u_start = int(total_units * (mapping.start_ch / total_ch))
                    u_end = int(total_units * (mapping.end_ch / total_ch))
                    if u_start <= unit_idx < u_end:
                        return mapping.area, "heuristic_fallback", "Metadata missing; used linear partition"

        return None, "unknown_area", "Could not resolve unit from manifest mappings"

    def make_signal_block(
        self,
        data,
        dims,
        signal_class,
        session_id,
        condition,
        time_base,
        alignment_event,
        window_ms,
        sampling_rate,
        unit_or_channel_ids,
        area_labels,
        baseline_ms=None,
        area_resolution_status=None,
        source_files=None,
        provenance=None,
        truth_status="truth_safe_unverified"
    ):
        """Constructs and validates a SignalBlock."""
        from src.analysis.contracts import make_signal_block
        return make_signal_block(
            data=data,
            dims=dims,
            signal_class=signal_class,
            session_id=session_id,
            condition=condition,
            time_base=time_base,
            alignment_event=alignment_event,
            window_ms=window_ms,
            sampling_rate=sampling_rate,
            unit_or_channel_ids=unit_or_channel_ids,
            area_labels=area_labels,
            baseline_ms=baseline_ms,
            area_resolution_status=area_resolution_status,
            source_files=source_files,
            provenance=provenance,
            truth_status=truth_status
        )
