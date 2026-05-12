import pandas as pd
import numpy as np
from src.analysis.io.loader import DataLoader
from src.analysis.profile_search import ProfileSearcher

def debug_missing_units():
    loader = DataLoader()
    searcher = ProfileSearcher(loader=loader)
    
    # Mirror f048's call
    # spk_df = searcher.search_omission_profiles(mode="spk")
    
    areas = loader.CANONICAL_AREAS
    sp_map = searcher._get_sp_map(areas)
    
    total_on_probes = 0
    analyzed_units = []
    
    for (ses, probe), entries in sp_map.items():
        # Find unit count
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
        
        total_on_probes += n_units
        
        for u_idx in range(n_units):
            res_area, status, caveat = loader.resolve_unit_area(ses, probe, u_idx, allow_heuristic=True)
            analyzed_units.append({
                'id': f"{ses}-probe{probe}-unit{u_idx}",
                'area': res_area,
                'status': status
            })
            
    df = pd.DataFrame(analyzed_units).drop_duplicates('id')
    print(f"Total Unique Units on analyzed probes: {len(df)}")
    print(df['status'].value_counts())
    print(df['area'].isna().sum(), "units have None area")
    
    # Check if any have status 'unresolved_metadata' or 'unknown_area'
    bad_units = df[df['area'].isna()]
    if not bad_units.empty:
        print("\n--- Units with missing area ---")
        print(bad_units.head(20))
        print(f"Total missing area: {len(bad_units)}")

if __name__ == "__main__":
    debug_missing_units()
