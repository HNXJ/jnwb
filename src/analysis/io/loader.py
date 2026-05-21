# core
import os
import re
import json
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
from typing import Optional, List, Dict, Any, Union
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

    def get_data_root(self) -> Optional[Path]:
        """Returns the data root path from OMISSION_DATA_ROOT environment variable, or None if absent."""
        env_val = os.environ.get("OMISSION_DATA_ROOT")
        if env_val:
            return Path(env_val)
        return None

    def discover_session_manifest_paths(self, data_root: Optional[Path] = None) -> list:
        """
        Scans data_root recursively for candidate session manifest files.
        Only inspects metadata/manifests config-like JSON files.
        """
        root_path = data_root or self.get_data_root()
        if not root_path or not root_path.exists():
            return []
            
        candidate_paths = []
        # Checks manifests/ metadata/ session_manifests/ folders first
        search_dirs = [root_path / "manifests", root_path / "metadata", root_path / "session_manifests"]
        for s_dir in search_dirs:
            if s_dir.exists() and s_dir.is_dir():
                candidate_paths.extend(list(s_dir.glob("*.json")))
                
        # Also check root_path itself for manifest-like files
        for p in root_path.glob("*.json"):
            if "manifest" in p.name.lower():
                candidate_paths.append(p)
        for p in root_path.glob("*/*.json"):
            if "manifest" in p.name.lower():
                candidate_paths.append(p)
                
        return sorted(list(set(candidate_paths)))

    def load_session_manifest(self, session_id: str, *, data_root: Optional[Path] = None, allow_fixture: bool = False):
        """
        Loads a session manifest by scanning the data_root candidate locations.
        If allow_fixture=True and no real manifest is found, falls back to the fixture path.
        """
        from src.analysis.contracts import SessionManifest
        import json
        
        # 1. Discover all manifests in data_root
        root_path = data_root or self.get_data_root()
        candidates = []
        if root_path and root_path.exists():
            all_manifests = self.discover_session_manifest_paths(root_path)
            for p in all_manifests:
                if session_id in p.name:
                    candidates.append(p)
                    
        manifest_path = None
        if candidates:
            candidates = sorted(list(set(candidates)))
            if len(candidates) > 1:
                log.warning(f"Multiple candidate manifests found for session '{session_id}': {[p.name for p in candidates]}. Selecting deterministically.")
            
            # Deterministic selection: prefer f"session_{session_id}_manifest.json"
            for p in candidates:
                if f"session_{session_id}_manifest.json" in p.name:
                    manifest_path = p
                    break
            if not manifest_path:
                for p in candidates:
                    if f"{session_id}_manifest.json" in p.name:
                        manifest_path = p
                        break
            if not manifest_path:
                manifest_path = candidates[0]
                
        # 2. Fallback to fixture if allowed and no real manifest found
        if not manifest_path:
            if allow_fixture:
                try:
                    return self.load_session_manifest_fixture(session_id)
                except FileNotFoundError:
                    return None
            return None
            
        # 3. Load the chosen real manifest
        with open(manifest_path, "r") as f:
            data = json.load(f)
            
        manifest = SessionManifest.from_dict(data)
        
        # Normalize DP to V4
        for mapping in manifest.area_mappings:
            mapping.area = SessionManifest.normalize_area(mapping.area)
        for unit in manifest.units:
            unit.area = SessionManifest.normalize_area(unit.area)
        for d in [manifest.channel_counts_by_area, manifest.unit_counts_by_area, manifest.area_resolution_status]:
            if d:
                for k in list(d.keys()):
                    norm_k = SessionManifest.normalize_area(k)
                    if norm_k != k:
                        d[norm_k] = d.pop(k)
                        
        return manifest

    def validate_session_manifest(self, session_id: str, *, data_root: Optional[Path] = None) -> dict:
        """
        Validates the session manifest for the given session_id.
        Returns a validation status dictionary.
        """
        from src.analysis.contracts import SessionManifest
        import json
        
        root_path = data_root or self.get_data_root()
        if not root_path or not root_path.exists():
            return {
                "status": "unavailable",
                "session_id": session_id,
                "manifest_path": None,
                "errors": ["Data root unavailable."],
                "warnings": [],
                "truth_status": None
            }
            
        # Discover candidate manifest files for this session
        all_manifests = self.discover_session_manifest_paths(root_path)
        candidates = [p for p in all_manifests if session_id in p.name]
        
        if not candidates:
            return {
                "status": "invalid",
                "session_id": session_id,
                "manifest_path": None,
                "errors": [f"No candidate manifest file found for session '{session_id}'."],
                "warnings": [],
                "truth_status": None
            }
            
        # Check for ambiguity
        is_ambiguous = len(candidates) > 1
        warnings = []
        if is_ambiguous:
            warnings.append(f"Multiple candidate manifests found for session '{session_id}': {[p.name for p in candidates]}")
            
        # Deterministic path selection
        manifest_path = None
        for p in candidates:
            if f"session_{session_id}_manifest.json" in p.name:
                manifest_path = p
                break
        if not manifest_path:
            for p in candidates:
                if f"{session_id}_manifest.json" in p.name:
                    manifest_path = p
                    break
        if not manifest_path:
            manifest_path = candidates[0]
            
        try:
            with open(manifest_path, "r") as f:
                data = json.load(f)
            raw_manifest = SessionManifest.from_dict(data)
        except Exception as e:
            return {
                "status": "invalid",
                "session_id": session_id,
                "manifest_path": str(manifest_path),
                "errors": [f"Failed to load or parse manifest JSON: {e}"],
                "warnings": warnings,
                "truth_status": None
            }
            
        errors = raw_manifest.validate()
        
        # Guard: check if fixture manifest is placed under real data root
        if raw_manifest.is_fixture():
            errors.append("Fixture/Synthetic manifest found in real data directory.")
            
        # Check DP to V4 mappings
        for m in raw_manifest.area_mappings:
            if m.area in ["DP", "DP (V4)"]:
                errors.append(f"Area {m.area} is not normalized to V4 in area_mappings.")
        for area in raw_manifest.channel_counts_by_area.keys():
            if area in ["DP", "DP (V4)"]:
                errors.append(f"Area {area} is not normalized to V4 in channel_counts_by_area.")
                
        # warnings from the manifest itself
        warnings.extend(raw_manifest.warnings)
        
        # Status determination
        if errors:
            status = "invalid"
        elif is_ambiguous:
            status = "ambiguous"
        else:
            status = "valid"
            
        return {
            "status": status,
            "session_id": session_id,
            "manifest_path": str(manifest_path) if manifest_path else None,
            "errors": errors,
            "warnings": warnings,
            "truth_status": raw_manifest.truth_status
        }

    def discover_data_sources(self, data_root: Optional[Path] = None, session_id: Optional[str] = None):
        """
        Phase 2F data source discovery scaffold.
        Scans shallow known folders inside data_root to classify and index files
        without opening or reading high-density neural array payloads.
        """
        from src.analysis.contracts.data_source_index import DataSourceIndex, DataSourceRecord
        import os
        import re

        root_path = data_root or self.get_data_root()
        if not root_path or not root_path.exists():
            return DataSourceIndex(
                data_root=str(root_path) if root_path else None,
                records=[],
                warnings=[],
                errors=["Data root unavailable."],
                truth_status="truth_safe_unverified"
            )

        records = []
        warnings = []
        errors = []

        # Shallow known folders to scan
        known_subdirs = ["manifests", "metadata", "session_manifests", "behavior", "arrays", "nwb"]
        
        # Gather candidate files (shallow: only root and known subdirectories)
        candidate_files = []
        
        # Check root itself (files only)
        try:
            for entry in os.scandir(root_path):
                if entry.is_file():
                    candidate_files.append(Path(entry.path))
        except Exception as e:
            errors.append(f"Error scanning data_root: {e}")

        # Check known subdirectories
        for subdir in known_subdirs:
            subdir_path = root_path / subdir
            if subdir_path.exists() and subdir_path.is_dir():
                try:
                    for entry in os.scandir(subdir_path):
                        if entry.is_file():
                            candidate_files.append(Path(entry.path))
                except Exception as e:
                    warnings.append(f"Error scanning subdirectory '{subdir}': {e}")

        for p in candidate_files:
            file_name = p.name.lower()
            ext = p.suffix.lower()
            
            # Size check from directory metadata
            try:
                size_bytes = p.stat().st_size
            except Exception:
                size_bytes = None

            # 1. Parse session_id
            parsed_session = None
            session_match = re.search(r"(\d{6})", p.name)
            if session_match:
                parsed_session = session_match.group(1)
            elif "fixture" in file_name:
                parsed_session = "fixture"

            # Filter by session_id if requested
            if session_id and parsed_session != session_id:
                continue

            # 2. Determine Role
            role = "unknown"
            if "manifest" in file_name:
                role = "manifest"
            elif ext in [".json", ".csv", ".tsv", ".yaml", ".yml", ".txt", ".md"] and any(x in p.parts for x in ["metadata", "manifests", "session_manifests"]):
                role = "metadata"
                if "manifest" in file_name:
                    role = "manifest"
            elif "behavior" in file_name or "bhv" in file_name or "eye" in file_name or "behavior" in p.parts:
                role = "behavior"
            elif ext in [".nwb", ".mat", ".h5", ".hdf5", ".npy", ".npz"]:
                role = "raw_neural_array"
            else:
                role = "unknown"

            # 3. Determine Signal Class
            signal_class = None
            if "spk" in file_name or "sua" in file_name or "spike" in file_name:
                signal_class = "SPK"
            elif "mua" in file_name:
                signal_class = "MUAe"
            elif "lfp" in file_name:
                signal_class = "LFP"
            elif role == "behavior":
                signal_class = "behavior"

            # 4. Enforce read policies and statuses
            readable_for_phase2 = True
            reason_not_read = None
            
            if ext in [".nwb", ".mat", ".h5", ".hdf5", ".npy", ".npz"]:
                readable_for_phase2 = False
                reason_not_read = "Blocked raw neural payload under Phase 2 doctrine."
                source_status = "discovered_raw_blocked"
            elif role == "manifest":
                source_status = "discovered_manifest"
            elif role == "metadata" or role == "behavior":
                source_status = "discovered_metadata"
            else:
                source_status = "ambiguous" if ext == ".json" else "invalid"

            record = DataSourceRecord(
                path=str(p),
                session_id=parsed_session,
                signal_class=signal_class,
                file_type=ext,
                size_bytes=size_bytes,
                role=role,
                readable_for_phase2=readable_for_phase2,
                reason_not_read=reason_not_read,
                source_status=source_status,
                warnings=[],
                truth_status="truth_safe_unverified"
            )
            records.append(record)

        return DataSourceIndex(
            data_root=str(root_path) if root_path else None,
            records=records,
            warnings=warnings,
            errors=errors,
            truth_status="truth_safe_unverified"
        )

    def get_signal_source_status(self, session_id: str, signal_class: str, *, data_root: Optional[Path] = None) -> dict:
        """
        Retrieves the discovery and availability status of a specific signal class for a session
        without loading the raw neural array payload.
        """
        root_path = data_root or self.get_data_root()
        if not root_path or not root_path.exists():
            return {
                "status": "unavailable",
                "session_id": session_id,
                "signal_class": signal_class,
                "path": None,
                "size_bytes": None,
                "warnings": ["Data root unavailable."],
                "truth_status": "truth_safe_unverified"
            }
            
        index = self.discover_data_sources(root_path, session_id=session_id)
        
        # Search for record matching the signal class
        matching_record = None
        for record in index.records:
            if record.signal_class == signal_class:
                matching_record = record
                break
                
        if matching_record:
            status = "discovered_candidate" if matching_record.role == "raw_neural_array" else matching_record.source_status
            return {
                "status": status,
                "session_id": session_id,
                "signal_class": signal_class,
                "path": matching_record.path,
                "size_bytes": matching_record.size_bytes,
                "warnings": matching_record.warnings,
                "truth_status": "truth_safe_unverified"
            }
            
        return {
            "status": "unavailable",
            "session_id": session_id,
            "signal_class": signal_class,
            "path": None,
            "size_bytes": None,
            "warnings": [f"No source files found for session {session_id} signal {signal_class}."],
            "truth_status": "truth_safe_unverified"
        }

    def make_fixture_signal_block(
        self,
        signal_class: str,
        session_id: str = "fixture_session",
        condition: str = "AAAB",
        n_trials: int = 2,
        n_units_or_channels: int = 3,
        n_time: int = 10,
        time_base: str = "p1_relative",
        alignment_event: str = "p1_onset",
        window_ms: Tuple[int, int] = (-1000, 4000),
        baseline_ms: Optional[Tuple[int, int]] = None,
        sampling_rate: Optional[float] = None,
        area_labels: Optional[List[str]] = None,
        area_resolution_status: Optional[Union[List[str], Dict[str, str]]] = None,
        fill_value: float = 0.0
    ):
        """
        Wrapper to generate a pure synthetic fixture SignalBlock.
        """
        from src.analysis.contracts.fixture_signal_blocks import make_fixture_signal_block
        return make_fixture_signal_block(
            signal_class=signal_class,
            session_id=session_id,
            condition=condition,
            n_trials=n_trials,
            n_units_or_channels=n_units_or_channels,
            n_time=n_time,
            time_base=time_base,
            alignment_event=alignment_event,
            window_ms=window_ms,
            baseline_ms=baseline_ms,
            sampling_rate=sampling_rate,
            area_labels=area_labels,
            area_resolution_status=area_resolution_status,
            fill_value=fill_value
        )

    def load_fixture_signal_block(
        self,
        signal_class: str,
        session_id: str = "fixture_session",
        condition: str = "AAAB",
        n_trials: int = 2,
        n_units_or_channels: int = 3,
        n_time: int = 10,
        time_base: str = "p1_relative",
        alignment_event: str = "p1_onset",
        window_ms: Tuple[int, int] = (-1000, 4000),
        baseline_ms: Optional[Tuple[int, int]] = None,
        sampling_rate: Optional[float] = None,
        area_labels: Optional[List[str]] = None,
        area_resolution_status: Optional[Union[List[str], Dict[str, str]]] = None,
        fill_value: float = 0.0
    ):
        """
        Wrapper to load/generate a pure synthetic fixture SignalBlock.
        """
        return self.make_fixture_signal_block(
            signal_class=signal_class,
            session_id=session_id,
            condition=condition,
            n_trials=n_trials,
            n_units_or_channels=n_units_or_channels,
            n_time=n_time,
            time_base=time_base,
            alignment_event=alignment_event,
            window_ms=window_ms,
            baseline_ms=baseline_ms,
            sampling_rate=sampling_rate,
            area_labels=area_labels,
            area_resolution_status=area_resolution_status,
            fill_value=fill_value
        )

    def load_bounded_signal_slice(
        self,
        request: Union[Any, str] = None,
        *,
        signal_class: Optional[str] = None,
        source_path: Optional[str] = None,
        max_trials: int = 1,
        max_units_or_channels: int = 2,
        max_timepoints: int = 100,
        max_bytes: int = 1048576,
        allow_real_data: bool = False
    ) -> Any:
        """
        Phase 2I Bounded Real-Data SignalBlock slice smoke.
        Default is safe, returning a fixture block or skipping.
        """
        from src.analysis.contracts.bounded_slice import (
            BoundedSliceRequest,
            make_bounded_fixture_slice,
            load_bounded_real_slice
        )
        
        if isinstance(request, BoundedSliceRequest):
            req = request
        else:
            session_id = request if isinstance(request, str) else "fixture_session"
            req = BoundedSliceRequest(
                session_id=session_id,
                signal_class=signal_class or "SPK",
                source_path=source_path,
                max_trials=max_trials,
                max_units_or_channels=max_units_or_channels,
                max_timepoints=max_timepoints,
                max_bytes=max_bytes,
                allow_real_data=allow_real_data
            )
            
        if req.allow_real_data:
            return load_bounded_real_slice(req)
        else:
            return make_bounded_fixture_slice(req)




