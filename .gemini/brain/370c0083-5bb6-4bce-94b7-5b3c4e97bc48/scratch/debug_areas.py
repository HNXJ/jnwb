import pandas as pd
import numpy as np
from src.analysis.io.loader import DataLoader
from src.analysis.profile_search import ProfileSearcher

def debug_areas():
    loader = DataLoader()
    searcher = ProfileSearcher(loader=loader)
    areas = loader.CANONICAL_AREAS
    sp_map = searcher._get_sp_map(areas)
    
    analyzed_units = []
    for (ses, probe), entries in sp_map.items():
        n_units = 0
        for fam in ["AXAB", "AAAB"]:
            filename = f"ses{ses}-units-probe{probe}-spk-{fam}.npy"
            path = loader.data_dir / filename
            if path.exists():
                try:
                    arr = np.load(path, mmap_mode='r')
                    n_units = arr.shape[1]
                    break
                except: continue
        if n_units == 0: continue
        for u_idx in range(n_units):
            res_area, status, caveat = loader.resolve_unit_area(ses, probe, u_idx, allow_heuristic=True)
            analyzed_units.append({
                'id': f"{ses}-probe{probe}-unit{u_idx}",
                'area': res_area,
                'status': status
            })
            
    df = pd.DataFrame(analyzed_units).drop_duplicates('id')
    print("--- All Units Area Counts (including non-canonical) ---")
    print(df['area'].value_counts())
    
    canonical_set = set(loader.CANONICAL_AREAS)
    non_canonical = df[~df['area'].isin(canonical_set)]
    print(f"\nTotal Non-Canonical Units: {len(non_canonical)}")
    print(non_canonical['area'].value_counts())

if __name__ == "__main__":
    debug_areas()
