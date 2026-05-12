import json
import argparse
import subprocess
from pathlib import Path
from src.analysis.io.loader import DataLoader
from src.analysis.contracts.session_manifest import SessionManifest, ConditionInfo, AreaMapping, UnitMetadata

def get_git_revision_hash() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
    except:
        return None

def build_manifest(session_id, out_dir, fixture_mode=False):
    print(f"[action] Building manifest for session {session_id} (Fixture: {fixture_mode})")
    
    loader = DataLoader()
    
    # Initialize Manifest
    manifest = SessionManifest(
        session_id=session_id,
        subject_id="FixtureSubject" if fixture_mode else "NHP_A", # Placeholder until real subject metadata is wired
        git_commit=get_git_revision_hash()
    )
    
    # 1. Signals (Heuristic for now)
    manifest.has_lfp = True
    manifest.has_spk = not fixture_mode # In fixture mode, assume no units unless simulated
    manifest.sampling_rates = {"LFP": 1000.0, "SPK": 30000.0}
    
    # 2. Conditions (Canonical list)
    conditions = [
        ("AXAB", "Standard Omission P2", True, 2),
        ("AAXB", "Standard Omission P3", True, 3),
        ("AAAX", "Standard Omission P4", True, 4),
        ("AAAB", "Standard Control", False, None)
    ]
    for code, label, is_om, slot in conditions:
        manifest.conditions.append(ConditionInfo(
            code=code, label=label, trial_count=40, is_omission=is_om, omission_slot=slot
        ))
        
    # 3. Anatomy (From DataLoader's area_map)
    for area, entries in loader.area_map.items():
        for entry in entries:
            if entry["session"] == session_id:
                status = "validated" if area != "V3" else "unresolved"
                manifest.area_mappings.append(AreaMapping(
                    area=area,
                    probe=int(entry["probe"]),
                    start_ch=int(entry["start_ch"]),
                    end_ch=int(entry["end_ch"]),
                    resolution_status=status
                ))
                if status == "unresolved":
                    manifest.warnings.append(f"Area {area} on Probe {entry['probe']} is UNRESOLVED generic V3.")

    # 4. Units (If metadata exists)
    if not fixture_mode:
        df = loader._get_unit_metadata(session_id)
        if df is not None:
            manifest.has_spk = True
            for i, row in df.iterrows():
                # We need to find which probe this unit belongs to
                # For now, use the same logic as loader.resolve_unit_area
                area, status, _ = loader.resolve_unit_area(session_id, 1, i, allow_heuristic=True) # Dummy probe 1 check
                # This part is complex because the CSV is global. 
                # For manifest purposes, we'll just store the ones we can resolve.
                if area:
                    manifest.units.append(UnitMetadata(
                        unit_id=f"{session_id}-unit{i}",
                        probe=-1, # Unknown probe from global CSV without parsing offsets
                        local_idx=int(i),
                        peak_channel=int(row.get("peak_channel_id", -1)),
                        area=area,
                        resolution_status=status
                    ))

    # Save
    out_path = Path(out_dir) / f"session_{session_id}_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2)
    
    print(f"[success] Manifest written to {out_path}")
    return out_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--out", default="artifacts/manifests")
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    
    build_manifest(args.session_id, args.out, args.fixture)
