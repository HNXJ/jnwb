import pandas as pd
import os
from src.analysis.io.logger import log

def analyze_spike_field_coherence(spsam_dir: str = "outputs/spsam"):
    """
    Loads grand_unit_lfp_coupling.csv and extracts coupling strength (PLV)
    across contexts (standard, omission, flash, baseline) for major areas.
    """
    coupling_path = os.path.join(spsam_dir, "grand_unit_lfp_coupling.csv")
    if not os.path.exists(coupling_path):
        log.warning(f"Grand coupling table not found at {coupling_path}")
        return None
        
    log.info(f"Loading SpSAM coupling data from {coupling_path}")
    df = pd.read_csv(coupling_path)
    
    # Standardize area labels (exclude generic probe labels)
    valid_areas = ["V1", "V2", "V4", "MT", "PFC", "FEF"]
    df = df[df["area"].isin(valid_areas)]
    
    results = {}
    
    # Extract mean + SEM for each area, context, and band
    bands = ["theta", "alpha", "beta1", "beta2", "gamma1", "gamma2", "gamma3"]
    
    for area in df["area"].unique():
        results[area] = {}
        area_df = df[df["area"] == area]
        
        for context in ["baseline", "standard", "flash", "omission"]:
            context_df = area_df[area_df["context"] == context]
            if len(context_df) == 0:
                continue
                
            results[area][context] = {}
            for b in bands:
                col = f"{b}_plv"
                vals = context_df[col].dropna()
                if len(vals) > 0:
                    results[area][context][b] = {
                        "mean": vals.mean(),
                        "sem": vals.std() / (len(vals) ** 0.5),
                        "count": len(vals)
                    }
                else:
                    results[area][context][b] = {
                        "mean": 0.0,
                        "sem": 0.0,
                        "count": 0
                    }
                    
    return results
