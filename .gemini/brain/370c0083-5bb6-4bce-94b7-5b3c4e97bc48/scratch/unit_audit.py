import pandas as pd
import numpy as np
from src.analysis.io.loader import DataLoader
from pathlib import Path

def audit_units():
    loader = DataLoader()
    units_found = []
    
    # Iterate through all sessions/probes defined in the area map
    processed = set()
    for area in loader.CANONICAL_AREAS:
        for entry in loader.area_map.get(area, []):
            ses, probe = entry['session'], entry['probe']
            if (ses, probe) in processed:
                continue
            processed.add((ses, probe))
            
            # Find any SPK file to get unit count
            # We check multiple families to be sure we find at least one
            n_units = 0
            for fam in ["AXAB", "BXBA", "RXRR", "AAAB"]:
                filename = f"ses{ses}-units-probe{probe}-spk-{fam}.npy"
                path = loader.data_dir / filename
                if path.exists():
                    try:
                        arr = np.load(path, mmap_mode='r')
                        n_units = arr.shape[1]
                        break
                    except:
                        continue
            
            if n_units == 0:
                continue
                
            for u_idx in range(n_units):
                res_area, status, caveat = loader.resolve_unit_area(ses, probe, u_idx, allow_heuristic=True)
                units_found.append({
                    'session': ses,
                    'probe': probe,
                    'unit': u_idx,
                    'status': status,
                    'area': res_area
                })
                
    df = pd.DataFrame(units_found).drop_duplicates(['session', 'probe', 'unit'])
    print("--- Status Value Counts ---")
    print(df['status'].value_counts())
    print("\n--- Summary Metrics ---")
    print(f"Total Unique Units touched: {len(df)}")
    print(f"Figure Grade (metadata_resolved*): {len(df[df['status'].str.startswith('metadata_resolved')])}")
    print(f"Heuristic Fallback: {len(df[df['status'] == 'heuristic_fallback'])}")
    print(f"Unresolved Metadata: {len(df[df['status'] == 'unresolved_metadata'])}")
    print(f"Unknown Area: {len(df[df['status'] == 'unknown_area'])}")
    
    # Check if any units are excluded from the area map
    # That shouldn't happen because we iterate OVER the area map
    
    # Check if 1376 + 3727 + X = Total
    fg = len(df[df['status'].str.startswith('metadata_resolved')])
    hf = len(df[df['status'] == 'heuristic_fallback'])
    un = len(df[df['status'] == 'unresolved_metadata'])
    ua = len(df[df['status'] == 'unknown_area'])
    
    print(f"\nAudit Invariant: {fg} (FG) + {hf} (HF) + {un} (UN) + {ua} (UA) = {fg+hf+un+ua}")
    
    # Account for the 18 units
    # If Previous Total was 5121 and Current Total is 5103, and the 18 are "unresolved_metadata"
    # then 1376 + 3727 = 5103.
    # The user says 1376 + 3727 = 5103.
    # Where are the 18? They must be 'unresolved_metadata' that were PREVIOUSLY counted as 'figure_grade'.
    
if __name__ == "__main__":
    audit_units()
