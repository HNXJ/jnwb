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

def build_manifest(session_id, out_dir, fixture_mode=False, no_meta=False):
    print(f"[action] Building manifest for session {session_id} (Fixture: {fixture_mode}, NoMeta: {no_meta})")
    
    loader = DataLoader()
    
    # Initialize Manifest
    manifest = SessionManifest(
        session_id=session_id,
        subject_id="FixtureSubject" if fixture_mode else loader.get_subject_id(session_id),
        git_commit=get_git_revision_hash() if not no_meta else "REDACTED_FOR_IDEMPOTENCY"
    )
    if no_meta:
        manifest.generated_at = "2026-01-01T00:00:00"
    
    # 1. Signals (Heuristic for now)
    manifest.has_lfp = True
    manifest.has_spk = not fixture_mode # In fixture mode, assume no units unless simulated
    manifest.sampling_rates = {"LFP": 1000.0, "SPK": 30000.0}
    
    # 2. Conditions (Full OGLO Suite)
    conditions = [
        # A-Family
        ("AXAB", "Omission P2 (A)", True, 2),
        ("AAXB", "Omission P3 (A)", True, 3),
        ("AAAX", "Omission P4 (A)", True, 4),
        ("AAAB", "Control (A)", False, None),
        # B-Family
        ("BXBA", "Omission P2 (B)", True, 2),
        ("BBXA", "Omission P3 (B)", True, 3),
        ("BBBX", "Omission P4 (B)", True, 4),
        ("BBBA", "Control (B)", False, None),
        # R-Family
        ("RXRR", "Omission P2 (R)", True, 2),
        ("RRXR", "Omission P3 (R)", True, 3),
        ("RRRX", "Omission P4 (R)", True, 4),
        ("RRRR", "Control (R)", False, None)
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
                # For manifest purposes, we'll store resolved ones.
                # Heuristic: assume probe 1 for now if not specified
                area, status, _ = loader.resolve_unit_area(session_id, 1, i, allow_heuristic=True)
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
    parser.add_argument("--no-meta", action="store_true", help="Strip timestamps and Git SHAs for idempotency")
    args = parser.parse_args()
    
    build_manifest(args.session_id, args.out, args.fixture, args.no_meta)
