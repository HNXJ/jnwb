import pandas as pd
import numpy as np
from src.analysis.io.loader import DataLoader
from pathlib import Path

def audit_f048_units():
    loader = DataLoader()
    units_found = []
    
    # Probes from f048 output
    probes = [
        ('230629', 0), ('230630', 2), ('230714', 0), ('230719', 0), ('230720', 0), 
        ('230721', 0), ('230816', 2), ('230823', 2), ('230830', 2), ('230629', 1), 
        ('230714', 1), ('230719', 2), ('230720', 1), ('230721', 1), ('230630', 1), 
        ('230719', 1), ('230816', 1), ('230825', 2), ('230830', 1), ('230831', 2), 
        ('230818', 2), ('230823', 1), ('230825', 1), ('230831', 1), ('230818', 1), 
        ('230823', 0), ('230831', 0), ('230630', 0), ('230816', 0), ('230818', 0), 
        ('230825', 0), ('230830', 0)
    ]
    
    for ses, probe in probes:
        # Load SPK data to get n_units
        filename = f"ses{ses}-units-probe{probe}-spk-AXAB.npy"
        path = loader.data_dir / filename
        if path.exists():
            try:
                arr = np.load(path, mmap_mode='r')
                n_units = arr.shape[1]
                for u_idx in range(n_units):
                    res_area, status, caveat = loader.resolve_unit_area(ses, probe, u_idx, allow_heuristic=True)
                    units_found.append({
                        'id': f"{ses}-probe{probe}-unit{u_idx}",
                        'status': status,
                        'area': res_area
                    })
            except:
                continue
                
    df = pd.DataFrame(units_found).drop_duplicates('id')
    print("--- Status Value Counts ---")
    print(df['status'].value_counts())
    print("\n--- Summary Metrics ---")
    print(f"Total Unique Units touched: {len(df)}")
    print(f"Figure Grade (metadata_resolved*): {len(df[df['status'].str.startswith('metadata_resolved')])}")
    print(f"Heuristic Fallback: {len(df[df['status'] == 'heuristic_fallback'])}")
    print(f"Unknown Area: {len(df[df['status'] == 'unknown_area'])}")
    print(f"Unresolved Metadata: {len(df[df['status'] == 'unresolved_metadata'])}")

if __name__ == "__main__":
    audit_f048_units()
